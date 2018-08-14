"""Transform a mypy AST to the IR form (Intermediate Representation).

For example, consider a function like this:

   def f(x: int) -> int:
       return x * 2 + 1

It would be translated to something that conceptually looks like this:

   r0 = 2
   r1 = 1
   r2 = x * i0 :: int
   r3 = r2 + r1 :: int
   return r3
"""
from typing import Callable, Dict, List, Tuple, Optional, Union, Sequence, Set, Any, cast, overload
from abc import abstractmethod
import sys
import traceback
import itertools

from mypy.build import Graph
from mypy.nodes import (
    Node, MypyFile, SymbolNode, Statement, FuncItem, FuncDef, ReturnStmt, AssignmentStmt, OpExpr,
    IntExpr, NameExpr, LDEF, Var, IfStmt, UnaryExpr, ComparisonExpr, WhileStmt, Argument, CallExpr,
    IndexExpr, Block, Expression, ListExpr, ExpressionStmt, MemberExpr, ForStmt, RefExpr, Lvalue,
    BreakStmt, ContinueStmt, ConditionalExpr, OperatorAssignmentStmt, TupleExpr, ClassDef,
    TypeInfo, Import, ImportFrom, ImportAll, DictExpr, StrExpr, CastExpr, TempNode,
    MODULE_REF, PassStmt, PromoteExpr, AwaitExpr, BackquoteExpr, AssertStmt, BytesExpr,
    ComplexExpr, Decorator, DelStmt, DictionaryComprehension, EllipsisExpr, EnumCallExpr, ExecStmt,
    FloatExpr, GeneratorExpr, GlobalDecl, LambdaExpr, ListComprehension, SetComprehension,
    NamedTupleExpr, NewTypeExpr, NonlocalDecl, OverloadedFuncDef, PrintStmt, RaiseStmt,
    RevealExpr, SetExpr, SliceExpr, StarExpr, SuperExpr, TryStmt, TypeAliasExpr, TypeApplication,
    TypeVarExpr, TypedDictExpr, UnicodeExpr, WithStmt, YieldFromExpr, YieldExpr, GDEF, ARG_POS,
    ARG_OPT, ARG_NAMED, ARG_STAR, ARG_STAR2, is_class_var
)
import mypy.nodes
from mypy.types import (
    Type, Instance, CallableType, NoneTyp, TupleType, UnionType, AnyType, TypeVarType, PartialType,
    TypeType, FunctionLike, Overloaded, TypeOfAny, UninhabitedType,
)
from mypy.visitor import ExpressionVisitor, StatementVisitor
from mypy.subtypes import is_named_instance
from mypy.checkexpr import map_actuals_to_formals

from mypyc.common import (
    ENV_ATTR_NAME, NEXT_LABEL_ATTR_NAME, TEMP_ATTR_NAME, LAMBDA_NAME,
    MAX_SHORT_INT, TOP_LEVEL_NAME
)
from mypyc.freevariables import FreeVariablesVisitor
from mypyc.ops import (
    BasicBlock, AssignmentTarget, AssignmentTargetRegister, AssignmentTargetIndex,
    AssignmentTargetAttr, AssignmentTargetTuple, Environment, Op, LoadInt, RType, Value, Register,
    Return, FuncIR, Assign, Branch, Goto, RuntimeArg, Call, Box, Unbox, Cast, RTuple, Unreachable,
    TupleGet, TupleSet, ClassIR, RInstance, ModuleIR, GetAttr, SetAttr, LoadStatic, InitStatic,
    MethodCall, INVALID_FUNC_DEF, int_rprimitive, float_rprimitive, bool_rprimitive,
    list_rprimitive, is_list_rprimitive, dict_rprimitive, set_rprimitive, str_rprimitive,
    tuple_rprimitive, none_rprimitive, is_none_rprimitive, object_rprimitive, exc_rtuple,
    PrimitiveOp, ControlOp, LoadErrorValue, ERR_FALSE, OpDescription, RegisterOp,
    is_object_rprimitive, LiteralsMap, FuncSignature, VTableAttr, VTableMethod, VTableEntries,
    NAMESPACE_TYPE, RaiseStandardError, LoadErrorValue, NO_TRACEBACK_LINE_NO, FuncDecl,
    FUNC_NORMAL, FUNC_STATICMETHOD, FUNC_CLASSMETHOD,
    RUnion, is_optional_type, optional_value_type
)
from mypyc.ops_primitive import binary_ops, unary_ops, func_ops, method_ops, name_ref_ops
from mypyc.ops_list import (
    list_append_op, list_extend_op, list_len_op, list_get_item_op, list_set_item_op, new_list_op,
)
from mypyc.ops_tuple import list_tuple_op
from mypyc.ops_dict import new_dict_op, dict_get_item_op, dict_set_item_op, dict_update_op
from mypyc.ops_set import new_set_op, set_add_op
from mypyc.ops_misc import (
    none_op, true_op, false_op, iter_op, next_op, py_getattr_op, py_setattr_op, py_delattr_op,
    py_call_op, py_call_with_kwargs_op, py_method_call_op,
    fast_isinstance_op, bool_op, new_slice_op,
    type_op, pytype_from_template_op, import_op, ellipsis_op,
)
from mypyc.ops_exc import (
    no_err_occurred_op, raise_exception_op, raise_exception_with_tb_op, reraise_exception_op,
    error_catch_op, restore_exc_info_op, exc_matches_op, get_exc_value_op,
    get_exc_info_op, keep_propagating_op,
)
from mypyc.subtype import is_subtype
from mypyc.sametype import is_same_type, is_same_method_signature
from mypyc.crash import catch_errors

GenFunc = Callable[[], None]


def build_ir(modules: List[MypyFile],
             graph: Graph,
             types: Dict[Expression, Type]) -> List[Tuple[str, ModuleIR]]:
    result = []
    mapper = Mapper()

    # Collect all classes defined in the compilation unit.
    classes = []
    for module in modules:
        module_classes = [node for node in module.defs if isinstance(node, ClassDef)]
        classes.extend([(module, cdef) for cdef in module_classes])

    # Collect all class mappings so that we can bind arbitrary class name
    # references even if there are import cycles.
    for module, cdef in classes:
        class_ir = ClassIR(cdef.name, module.fullname(), is_trait(cdef))
        mapper.type_to_ir[cdef.info] = class_ir

    # Populate structural information in class IR.
    for module, cdef in classes:
        with catch_errors(module.path, cdef.line):
            prepare_class_def(module.fullname(), cdef, mapper)

    # Collect all the functions also
    for module in modules:
        for node in module.defs:
            if isinstance(node, FuncDef):  # TODO: what else??
                prepare_func_def(module.fullname(), None, node, mapper)

    # Generate IR for all modules.
    module_names = [mod.fullname() for mod in modules]
    class_irs = []

    for module in modules:
        # First pass to determine free symbols.
        fvv = FreeVariablesVisitor()
        module.accept(fvv)

        # Second pass.
        builder = IRBuilder(types, graph, mapper, module_names, fvv)
        builder.visit_mypy_file(module)
        module_ir = ModuleIR(
            builder.imports,
            mapper.literals,
            builder.functions,
            builder.classes
        )
        result.append((module.fullname(), module_ir))
        class_irs.extend(builder.classes)

    # Compute vtables.
    for cir in class_irs:
        compute_vtable(cir)

    return result


def is_trait(cdef: ClassDef) -> bool:
    return any(d.fullname == 'mypy_extensions.trait' for d in cdef.decorators
               if isinstance(d, NameExpr))


def specialize_parent_vtable(cls: ClassIR, parent: ClassIR) -> VTableEntries:
    """Generate the part of a vtable corresponding to a parent class or trait"""
    updated = []
    for entry in parent.vtable_entries:
        if isinstance(entry, VTableMethod):
            method = entry.method
            child_method = None
            if method.name in cls.methods:
                child_method = cls.methods[method.name]
            elif method.name in cls.properties:
                child_method = cls.properties[method.name]
            if child_method is not None:
                # TODO: emit a wrapper for __init__ that raises or something
                if (is_same_method_signature(method.sig, child_method.sig)
                        or method.name == '__init__'):
                    entry = VTableMethod(cls, entry.name, child_method)
                else:
                    entry = VTableMethod(cls, entry.name,
                                         cls.glue_methods[(entry.cls, method.name)])
            elif parent.is_trait:
                assert cls.vtable is not None
                entry = cls.vtable_entries[cls.vtable[entry.name]]
        else:
            # If it is an attribute from a trait, we need to find out real class it got
            # mixed in at and point to that.
            if parent.is_trait:
                assert cls.vtable is not None
                entry = cls.vtable_entries[cls.vtable[entry.name] + int(entry.is_setter)]
        updated.append(entry)
    return updated


def compute_vtable(cls: ClassIR) -> None:
    """Compute the vtable structure for a class."""
    if cls.vtable is not None: return

    # Merge attributes from traits into the class
    for t in cls.mro[1:]:
        if not t.is_trait:
            continue
        for name, typ in t.attributes.items():
            if not cls.is_trait and not any(name in b.attributes for b in cls.base_mro):
                cls.attributes[name] = typ

    cls.vtable = {}
    if cls.base:
        compute_vtable(cls.base)
        assert cls.base.vtable is not None
        cls.vtable.update(cls.base.vtable)
        cls.vtable_entries = specialize_parent_vtable(cls, cls.base)

    # Include the vtable from the parent classes, but handle method overrides.
    entries = cls.vtable_entries

    for attr in cls.attributes:
        cls.vtable[attr] = len(entries)
        entries.append(VTableAttr(cls, attr, is_setter=False))
        entries.append(VTableAttr(cls, attr, is_setter=True))

    for t in [cls] + cls.traits:
        for fn in itertools.chain(t.properties.values(), t.methods.values()):
            # TODO: don't generate a new entry when we overload without changing the type
            if fn == cls.get_method(fn.name):
                cls.vtable[fn.name] = len(entries)
                entries.append(VTableMethod(t, fn.name, fn))

    # Compute vtables for all of the traits that the class implements
    all_traits = [t for t in cls.mro if t.is_trait]
    if not cls.is_trait:
        for trait in all_traits:
            compute_vtable(trait)
            cls.trait_vtables[trait] = specialize_parent_vtable(cls, trait)


class Mapper:
    """Keep track of mappings from mypy concepts to IR concepts.

    This state is shared across all modules in a compilation unit.
    """

    def __init__(self) -> None:
        self.type_to_ir = {}  # type: Dict[TypeInfo, ClassIR]
        self.func_to_decl = {}  # type: Dict[SymbolNode, FuncDecl]
        # Maps integer, float, and unicode literals to a static name
        self.literals = {}  # type: LiteralsMap

    def type_to_rtype(self, typ: Type) -> RType:
        if isinstance(typ, Instance):
            if typ.type.fullname() == 'builtins.int':
                return int_rprimitive
            elif typ.type.fullname() == 'builtins.float':
                return float_rprimitive
            elif typ.type.fullname() == 'builtins.str':
                return str_rprimitive
            elif typ.type.fullname() == 'builtins.bool':
                return bool_rprimitive
            elif typ.type.fullname() == 'builtins.list':
                return list_rprimitive
            elif typ.type.fullname() == 'builtins.dict':
                return dict_rprimitive
            elif typ.type.fullname() == 'builtins.set':
                return set_rprimitive
            elif typ.type.fullname() == 'builtins.tuple':
                return tuple_rprimitive  # Varying-length tuple
            elif typ.type in self.type_to_ir:
                return RInstance(self.type_to_ir[typ.type])
            else:
                return object_rprimitive
        elif isinstance(typ, TupleType):
            # Use our unboxed tuples for raw tuples but fall back to
            # being boxed for NamedTuple.
            if typ.fallback.type.fullname() == 'builtins.tuple':
                return RTuple([self.type_to_rtype(t) for t in typ.items])
            else:
                return tuple_rprimitive
        elif isinstance(typ, CallableType):
            return object_rprimitive
        elif isinstance(typ, NoneTyp):
            return none_rprimitive
        elif isinstance(typ, UnionType):
            return RUnion([self.type_to_rtype(item)
                           for item in typ.items])
        elif isinstance(typ, AnyType):
            return object_rprimitive
        elif isinstance(typ, TypeType):
            return object_rprimitive
        elif isinstance(typ, TypeVarType):
            # Erase type variable to upper bound.
            # TODO: Erase to object if object has value restriction -- or union (once supported)?
            assert not typ.values, 'TypeVar with value restriction not supported'
            return self.type_to_rtype(typ.upper_bound)
        elif isinstance(typ, PartialType):
            assert typ.var.type is not None
            return self.type_to_rtype(typ.var.type)
        elif isinstance(typ, Overloaded):
            return object_rprimitive
        elif isinstance(typ, UninhabitedType):
            # Sure, whatever!
            return object_rprimitive
        assert False, '%s unsupported' % type(typ)

    def fdef_to_sig(self, fdef: FuncDef) -> FuncSignature:
        assert isinstance(fdef.type, CallableType)
        args = [RuntimeArg(arg.variable.name(), self.type_to_rtype(fdef.type.arg_types[i]),
                arg.kind)
                for i, arg in enumerate(fdef.arguments)]
        ret = self.type_to_rtype(fdef.type.ret_type)
        # We force certain dunder methods to return objects to support letting them
        # return NotImplemented. It also avoids some pointless boxing and unboxing,
        # since tp_richcompare needs an object anyways.
        if fdef.name() in ('__eq__', '__ne__', '__lt__', '__gt__', '__le__', '__ge__'):
            ret = object_rprimitive
        return FuncSignature(args, ret)

    def literal_static_name(self, value: Union[int, float, str, bytes]) -> str:
        # Include type to distinguish between 1 and 1.0, and so on.
        key = (type(value), value)
        if key not in self.literals:
            if isinstance(value, str):
                prefix = 'unicode_'
            elif isinstance(value, float):
                prefix = 'float_'
            elif isinstance(value, bytes):
                prefix = 'bytes_'
            else:
                assert isinstance(value, int)
                prefix = 'int_'
            self.literals[key] = prefix + str(len(self.literals))
        return self.literals[key]


def prepare_func_def(module_name: str, class_name: Optional[str],
                     fdef: FuncDef, mapper: Mapper) -> FuncDecl:
    kind = FUNC_STATICMETHOD if fdef.is_static else (
        FUNC_CLASSMETHOD if fdef.is_class else FUNC_NORMAL)
    decl = FuncDecl(fdef.name(), class_name, module_name, mapper.fdef_to_sig(fdef), kind)
    mapper.func_to_decl[fdef] = decl
    return decl


def prepare_class_def(module_name: str, cdef: ClassDef, mapper: Mapper) -> None:
    ir = mapper.type_to_ir[cdef.info]
    info = cdef.info
    for name, node in info.names.items():
        if isinstance(node.node, Var):
            assert node.node.type, "Class member missing type"
            if not node.node.is_classvar and name != '__slots__':
                ir.attributes[name] = mapper.type_to_rtype(node.node.type)
        elif isinstance(node.node, FuncDef):
            ir.method_decls[name] = prepare_func_def(module_name, cdef.name, node.node, mapper)
        elif isinstance(node.node, Decorator):
            # meaningful decorators (@property, @abstractmethod) are removed from this list by mypy
            assert node.node.decorators == []
            # TODO: do something about abstract methods here. Currently, they are handled just like
            # normal methods.
            decl = prepare_func_def(module_name, cdef.name, node.node.func, mapper)
            ir.method_decls[name] = decl
            if node.node.func.is_property:
                assert node.node.func.type
                ir.property_types[name] = decl.sig.ret_type

    # Set up a constructor decl
    init_node = cdef.info['__init__'].node
    if not ir.is_trait and isinstance(init_node, FuncDef):
        init_sig = mapper.fdef_to_sig(init_node)
        ctor_sig = FuncSignature(init_sig.args[1:], RInstance(ir))
        ir.ctor = FuncDecl(cdef.name, None, module_name, ctor_sig)
        mapper.func_to_decl[cdef.info] = ir.ctor

    # Set up the parent class
    bases = [mapper.type_to_ir[base.type] for base in info.bases
             if base.type in mapper.type_to_ir]
    assert all(c.is_trait for c in bases[1:]), "Non trait bases must be first"
    ir.traits = [c for c in bases if c.is_trait]

    mro = []
    base_mro = []
    for cls in info.mro:
        if cls not in mapper.type_to_ir:
            if cls.name != 'builtins.object':
                ir.inherits_python = True
            continue
        base_ir = mapper.type_to_ir[cls]
        if not base_ir.is_trait:
            base_mro.append(base_ir)
        mro.append(base_ir)

    base_idx = 1 if not ir.is_trait else 0
    if len(base_mro) > base_idx:
        ir.base = base_mro[base_idx]
    assert all(base_mro[i].base == base_mro[i + 1] for i in range(len(base_mro) - 1)), (
        "non-trait MRO must be linear")
    ir.mro = mro
    ir.base_mro = base_mro

    # We need to know whether any children of a class have a __bool__
    # method in order to know whether we can assume it is always true.
    if ir.has_method('__bool__'):
        for base in ir.mro:
            base.has_bool = True


class FuncInfo(object):
    """Contains information about functions as they are generated."""
    def __init__(self,
                 fitem: FuncItem = INVALID_FUNC_DEF,
                 name: str = '',
                 namespace: str = '',
                 is_nested: bool = False,
                 contains_nested: bool = False) -> None:
        self.fitem = fitem
        self.name = name
        self.ns = namespace
        # Callable classes implement the '__call__' method, and are used to represent functions
        # that are nested inside of other functions.
        self._callable_class = None  # type: Optional[ImplicitClass]
        # Environment classes are ClassIR instances that contain attributes representing the
        # variables in the environment of the function they correspond to. Environment classes are
        # generated for functions that contain nested functions.
        self._env_class = None  # type: Optional[ClassIR]
        # Generator classes implement the '__next__' method, and are used to represent generators
        # returned by generator functions.
        self._generator_class = None  # type: Optional[GeneratorClass]
        # Environment class registers are the local registers associated with instances of an
        # environment class, used for getting and setting attributes. curr_env_reg is the register
        # associated with the current environment.
        self._curr_env_reg = None  # type: Optional[Value]
        # These are flags denoting whether a given function is nested or contains a nested
        # function.
        self._is_nested = is_nested
        self._contains_nested = contains_nested

        # TODO: add field for ret_type: RType = none_rprimitive

    @property
    def is_generator(self) -> bool:
        return self.fitem.is_generator

    @property
    def is_nested(self) -> bool:
        return self._is_nested

    @property
    def contains_nested(self) -> bool:
        return self._contains_nested

    @property
    def callable_class(self) -> 'ImplicitClass':
        assert self._callable_class is not None
        return self._callable_class

    @callable_class.setter
    def callable_class(self, cls: 'ImplicitClass') -> None:
        self._callable_class = cls

    @property
    def env_class(self) -> ClassIR:
        assert self._env_class is not None
        return self._env_class

    @env_class.setter
    def env_class(self, ir: ClassIR) -> None:
        self._env_class = ir

    @property
    def generator_class(self) -> 'GeneratorClass':
        assert self._generator_class is not None
        return self._generator_class

    @generator_class.setter
    def generator_class(self, cls: 'GeneratorClass') -> None:
        self._generator_class = cls

    @property
    def curr_env_reg(self) -> Value:
        assert self._curr_env_reg is not None
        return self._curr_env_reg


class ImplicitClass(object):
    """Contains information regarding classes that are generated as a result of nested functions or
    generated functions, but not explicitly defined in the source code.
    """
    def __init__(self, ir: ClassIR) -> None:
        # The ClassIR instance associated with this class.
        self.ir = ir
        # The register associated with the 'self' instance for this generator class.
        self._self_reg = None  # type: Optional[Value]
        # Environment class registers are the local registers associated with instances of an
        # environment class, used for getting and setting attributes. curr_env_reg is the register
        # associated with the current environment. prev_env_reg is the self.__mypyc_env__ field
        # associated with the previous environment.
        self._curr_env_reg = None  # type: Optional[Value]
        self._prev_env_reg = None  # type: Optional[Value]

    @property
    def self_reg(self) -> Value:
        assert self._self_reg is not None
        return self._self_reg

    @self_reg.setter
    def self_reg(self, reg: Value) -> None:
        self._self_reg = reg

    @property
    def curr_env_reg(self) -> Value:
        assert self._curr_env_reg is not None
        return self._curr_env_reg

    @curr_env_reg.setter
    def curr_env_reg(self, reg: Value) -> None:
        self._curr_env_reg = reg

    @property
    def prev_env_reg(self) -> Value:
        assert self._prev_env_reg is not None
        return self._prev_env_reg

    @prev_env_reg.setter
    def prev_env_reg(self, reg: Value) -> None:
        self._prev_env_reg = reg


class GeneratorClass(ImplicitClass):
    def __init__(self, ir: ClassIR) -> None:
        super().__init__(ir)
        # This register holds the label number that the '__next__' function should go to the next
        # time it is called.
        self._next_label_reg = None  # type: Optional[Value]
        self._next_label_target = None  # type: Optional[AssignmentTarget]

        # These registers hold the error values for the generator object for the case that the
        # 'throw' function is called.
        self.exc_regs = None  # type: Optional[Tuple[Value, Value, Value]]

        # The switch block is used to decide which instruction to go using the value held in the
        # next-label register.
        self.switch_block = BasicBlock()
        self.blocks = []  # type: List[BasicBlock]

    @property
    def next_label_reg(self) -> Value:
        assert self._next_label_reg is not None
        return self._next_label_reg

    @next_label_reg.setter
    def next_label_reg(self, reg: Value) -> None:
        self._next_label_reg = reg

    @property
    def next_label_target(self) -> AssignmentTarget:
        assert self._next_label_target is not None
        return self._next_label_target

    @next_label_target.setter
    def next_label_target(self, target: AssignmentTarget) -> None:
        self._next_label_target = target


class NonlocalControl:
    """Represents a stack frame of constructs that modify nonlocal control flow.

    The nonlocal control flow constructs are break, continue, and
    return, and their behavior is modified by a number of other
    constructs.  The most obvious is loop, which override where break
    and continue jump to, but also `except` (which needs to clear
    exc_info when left) and (eventually) finally blocks (which need to
    ensure that the finally block is always executed when leaving the
    try/except blocks).
    """
    @abstractmethod
    def gen_break(self, builder: 'IRBuilder') -> None: pass

    @abstractmethod
    def gen_continue(self, builder: 'IRBuilder') -> None: pass

    @abstractmethod
    def gen_return(self, builder: 'IRBuilder', value: Value) -> None: pass


class BaseNonlocalControl(NonlocalControl):
    def gen_break(self, builder: 'IRBuilder') -> None:
        assert False, "break outside of loop"

    def gen_continue(self, builder: 'IRBuilder') -> None:
        assert False, "continue outside of loop"

    def gen_return(self, builder: 'IRBuilder', value: Value) -> None:
        builder.add(Return(value))


class CleanupNonlocalControl(NonlocalControl):
    """Abstract nonlocal control that runs some cleanup code. """
    def __init__(self, outer: NonlocalControl) -> None:
        self.outer = outer

    @abstractmethod
    def gen_cleanup(self, builder: 'IRBuilder') -> None: ...

    def gen_break(self, builder: 'IRBuilder') -> None:
        self.gen_cleanup(builder)
        self.outer.gen_break(builder)

    def gen_continue(self, builder: 'IRBuilder') -> None:
        self.gen_cleanup(builder)
        self.outer.gen_continue(builder)

    def gen_return(self, builder: 'IRBuilder', value: Value) -> None:
        self.gen_cleanup(builder)
        self.outer.gen_return(builder, value)


class GeneratorNonlocalControl(BaseNonlocalControl):
    def gen_return(self, builder: 'IRBuilder', value: Value) -> None:
        # Assign an invalid next label number so that the next time __next__ is called, we jump to
        # the case in which StopIteration is raised.
        builder.assign(builder.fn_info.generator_class.next_label_target,
                       builder.add(LoadInt(-1)),
                       builder.fn_info.fitem.line)
        # Raise a StopIteration containing a field for the value that should be returned. Before
        # doing so, create a new block without an error handler set so that the implicitly thrown
        # StopIteration isn't caught by except blocks inside of the generator function.
        builder.error_handlers.append(None)
        builder.goto_new_block()
        builder.add(RaiseStandardError(RaiseStandardError.STOP_ITERATION, value,
                                       builder.fn_info.fitem.line))
        builder.add(Unreachable())
        builder.error_handlers.pop()


class IRBuilder(ExpressionVisitor[Value], StatementVisitor[None]):
    def __init__(self,
                 types: Dict[Expression, Type],
                 graph: Graph,
                 mapper: Mapper,
                 modules: List[str],
                 fvv: FreeVariablesVisitor) -> None:
        self.types = types
        self.graph = graph
        self.environment = Environment()
        self.environments = [self.environment]
        self.ret_types = []  # type: List[RType]
        self.blocks = []  # type: List[List[BasicBlock]]
        self.functions = []  # type: List[FuncIR]
        self.classes = []  # type: List[ClassIR]
        self.modules = set(modules)
        self.callable_class_names = set()  # type: Set[str]

        # These variables keep track of the number of lambdas, implicit indices, and implicit
        # iterators instantiated so we avoid name conflicts. The indices and iterators are
        # instantiated from for-loops.
        self.lambda_counter = 0
        self.temp_counter = 0

        # These variables are populated from the first-pass FreeVariablesVisitor.
        self.free_variables = fvv.free_variables
        self.encapsulating_fitems = fvv.encapsulating_funcs
        self.nested_fitems = fvv.nested_funcs

        # This list operates similarly to a function call stack for nested functions. Whenever a
        # function definition begins to be generated, a FuncInfo instance is added to the stack,
        # and information about that function (e.g. whether it is nested, its environment class to
        # be generated) is stored in that FuncInfo instance. When the function is done being
        # generated, its corresponding FuncInfo is popped off the stack.
        self.fn_info = FuncInfo(INVALID_FUNC_DEF, '', '')
        self.fn_infos = [self.fn_info]  # type: List[FuncInfo]

        # This list operates as a stack of constructs that modify the
        # behavior of nonlocal control flow constructs.
        self.nonlocal_control = []  # type: List[NonlocalControl]
        # Stack of except handler entry blocks
        self.error_handlers = [None]  # type: List[Optional[BasicBlock]]

        self.mapper = mapper
        self.imports = []  # type: List[str]

    def visit_mypy_file(self, mypyfile: MypyFile) -> None:
        if mypyfile.fullname() in ('typing', 'abc'):
            # These module are special; their contents are currently all
            # built-in primitives.
            return

        self.module_path = mypyfile.path
        self.module_name = mypyfile.fullname()

        classes = [node for node in mypyfile.defs if isinstance(node, ClassDef)]

        # Collect all classes.
        for cls in classes:
            ir = self.mapper.type_to_ir[cls.info]
            self.classes.append(ir)

        self.enter(FuncInfo(name='<top level>'))

        # Make sure we have a builtins import
        self.gen_import('builtins', -1)

        # Generate ops.
        for node in mypyfile.defs:
            self.accept(node)
        self.maybe_add_implicit_return()

        # Generate special function representing module top level.
        blocks, env, ret_type, _ = self.leave()
        sig = FuncSignature([], none_rprimitive)
        func_ir = FuncIR(FuncDecl(TOP_LEVEL_NAME, None, self.module_name, sig), blocks, env)
        self.functions.append(func_ir)

    def visit_method(self, cdef: ClassDef, fdef: FuncDef) -> None:
        name = fdef.name()
        class_ir = self.mapper.type_to_ir[cdef.info]
        func_ir, _ = self.gen_func_item(fdef, fdef.name(), class_ir.method_sig(fdef.name()),
                                        cdef.name)
        self.functions.append(func_ir)
        if fdef.is_property:
            class_ir.properties[name] = func_ir
        else:
            class_ir.methods[name] = func_ir

        # If this overrides a parent class method with a different type, we need
        # to generate a glue method to mediate between them.
        for cls in class_ir.mro[1:]:
            if (name in cls.method_decls and name != '__init__'
                    and not is_same_method_signature(class_ir.method_decls[name].sig,
                                                     cls.method_decls[name].sig)):
                if fdef.is_property:
                    f = self.gen_glue_property(cls.method_decls[name].sig, func_ir, class_ir,
                                               cls, fdef.line)
                else:
                    f = self.gen_glue_method(cls.method_decls[name].sig, func_ir, class_ir,
                                             cls, fdef.line)
                class_ir.glue_methods[(cls, name)] = f
                self.functions.append(f)

    def is_approximately_constant(self, e: Expression) -> bool:
        """Check whether we allow an expression to appear as a default value.

        We don't currently properly support storing the evaluated values for default
        arguments and default attribute values, so we restrict what expressions we allow.
        We allow literals of primitives types, None, and references to global variables
        whose names are in all caps (as an unsound and very hacky proxy for whether they
        are a constant).
        Additionally in a totally defensely hack we whitelist some other names.
        """
        # TODO: This is a hack, #336
        ALLOWED_NAMES = ('_dummy',)
        return (isinstance(e, (StrExpr, BytesExpr, IntExpr, FloatExpr))
                or (isinstance(e, UnaryExpr) and e.op == '-'
                    and isinstance(e.expr, (IntExpr, FloatExpr)))
                or (isinstance(e, TupleExpr)
                    and all(self.is_approximately_constant(e) for e in e.items))
                or (isinstance(e, RefExpr) and e.kind == GDEF
                    and (e.fullname in ('builtins.True', 'builtins.False', 'builtins.None')
                         or (e.node is not None and (e.node.name().upper() == e.node.name()
                                                     or e.node.name() in ALLOWED_NAMES)))))

    def generate_attr_defaults(self, cdef: ClassDef) -> None:
        """Generate an initialization method for default attr values (from class vars)"""
        cls = self.mapper.type_to_ir[cdef.info]

        # Pull out all assignments in classes in the mro so we can initialize them
        # TODO: Support nested statements
        default_assignments = []
        for info in cdef.info.mro:
            if info not in self.mapper.type_to_ir:
                continue
            for stmt in info.defn.defs.body:
                if (isinstance(stmt, AssignmentStmt)
                        and isinstance(stmt.lvalues[0], NameExpr)
                        and not is_class_var(stmt.lvalues[0])
                        and not isinstance(stmt.rvalue, TempNode)):
                    if stmt.lvalues[0].name == '__slots__':
                        continue

                    default_assignments.append(stmt)

        if not default_assignments:
            return

        self.enter(FuncInfo())
        self.ret_types[-1] = bool_rprimitive

        rt_args = (RuntimeArg('self', RInstance(cls)),)
        self_var = self.read(self.add_self_to_env(cls), -1)

        for stmt in default_assignments:
            lvalue = stmt.lvalues[0]
            assert isinstance(lvalue, NameExpr)
            with self.catch_errors(stmt.line):
                assert self.is_approximately_constant(stmt.rvalue), (
                    "Unsupported default attribute value")

            # If the attribute is initialized to None and type isn't optional,
            # don't initialize it to anything.
            attr_type = cls.attr_type(lvalue.name)
            if isinstance(stmt.rvalue, RefExpr) and stmt.rvalue.fullname == 'builtins.None':
                if (not is_optional_type(attr_type) and not is_object_rprimitive(attr_type)
                        and not is_none_rprimitive(attr_type)):
                    continue

            val = self.coerce(self.accept(stmt.rvalue), attr_type, stmt.line)
            self.add(SetAttr(self_var, lvalue.name, val, -1))

        self.add(Return(self.primitive_op(true_op, [], -1)))

        blocks, env, ret_type, _ = self.leave()
        ir = FuncIR(
            FuncDecl('__mypyc_defaults_setup',
                     cls.name, self.module_name,
                     FuncSignature(rt_args, ret_type)),
            blocks, env)
        self.functions.append(ir)
        cls.methods[ir.name] = ir

    def visit_class_def(self, cdef: ClassDef) -> None:
        self.allocate_class(cdef)

        for stmt in cdef.defs.body:
            if isinstance(stmt, FuncDef):
                with self.catch_errors(stmt.line):
                    self.visit_method(cdef, stmt)
            elif isinstance(stmt, Decorator):
                with self.catch_errors(stmt.line):
                    self.visit_method(cdef, stmt.func)
            elif isinstance(stmt, PassStmt):
                continue
            elif isinstance(stmt, AssignmentStmt):
                # Variable declaration with no body
                if isinstance(stmt.rvalue, TempNode):
                    continue
                assert len(stmt.lvalues) == 1
                lvalue = stmt.lvalues[0]
                assert isinstance(lvalue, NameExpr)
                # Only treat marked class variables as class variables.
                if not is_class_var(lvalue):
                    continue

                typ = self.load_native_type_object(cdef.fullname)
                value = self.accept(stmt.rvalue)
                self.primitive_op(
                    py_setattr_op, [typ, self.load_static_unicode(lvalue.name), value], stmt.line)
            elif isinstance(stmt, ExpressionStmt) and isinstance(stmt.expr, StrExpr):
                # Docstring. Ignore
                pass
            else:
                with self.catch_errors(stmt.line):
                    assert False, "Unsupported statement in class body"

        self.generate_attr_defaults(cdef)
        self.create_ne_from_eq(cdef)

    def allocate_class(self, cdef: ClassDef) -> None:
        # OK AND NOW THE FUN PART
        base_exprs = cdef.base_type_exprs + cdef.removed_base_type_exprs
        if base_exprs:
            bases = [self.accept(x) for x in base_exprs]
            tp_bases = self.box(self.add(TupleSet(bases, cdef.line)))
        else:
            tp_bases = self.add(LoadErrorValue(object_rprimitive, is_borrowed=True))
        modname = self.load_static_unicode(self.module_name)
        template = self.add(LoadStatic(object_rprimitive, cdef.name + "_template",
                                       self.module_name, NAMESPACE_TYPE))
        # Create the class
        tp = self.primitive_op(pytype_from_template_op,
                               [template, tp_bases, modname], cdef.line)
        # Immediately fix up the trait vtables, before doing anything with the class.
        self.add(Call(
            FuncDecl(cdef.name + '_trait_vtable_setup',
                     None, self.module_name,
                     FuncSignature([], bool_rprimitive)), [], -1))
        # Save the class
        self.add(InitStatic(tp, cdef.name, self.module_name, NAMESPACE_TYPE))

        # Add it to the dict
        self.primitive_op(dict_set_item_op,
                          [self.load_globals_dict(), self.load_static_unicode(cdef.name),
                           tp], cdef.line)

    def gen_import(self, id: str, line: int) -> None:
        # Unfortunate hack:
        if id == 'os':
            self.gen_import('os.path', line)
            self.gen_import('posix', line)

        self.imports.append(id)

        needs_import, out = BasicBlock(), BasicBlock()
        first_load = self.add(LoadStatic(object_rprimitive, 'module', id))
        comparison = self.binary_op(first_load, self.none(), 'is not', line)
        self.add_bool_branch(comparison, out, needs_import)

        self.activate_block(needs_import)
        value = self.primitive_op(import_op, [self.load_static_unicode(id)], line)
        self.add(InitStatic(value, 'module', id))
        self.goto_and_activate(out)

    def visit_import(self, node: Import) -> None:
        if node.is_unreachable or node.is_mypy_only:
            return
        for node_id, _ in node.ids:
            self.gen_import(node_id, node.line)

    def visit_import_from(self, node: ImportFrom) -> None:
        if node.is_unreachable or node.is_mypy_only:
            return
        # TODO support these?
        assert not node.relative

        self.gen_import(node.id, node.line)
        module = self.add(LoadStatic(object_rprimitive, 'module', node.id))

        # Copy everything into our module's dict.
        # Note that we miscompile import from inside of functions here,
        # since that case *shouldn't* load it into the globals dict.
        # This probably doesn't matter much and the code runs basically right.
        globals = self.load_globals_dict()
        for name, maybe_as_name in node.names:
            # If one of the things we are importing is a module,
            # import it as a module also.
            fullname = node.id + '.' + name
            if fullname in self.graph or fullname in self.graph[self.module_name].suppressed:
                self.gen_import(fullname, node.line)

            as_name = maybe_as_name or name
            obj = self.py_get_attr(module, name, node.line)
            self.translate_special_method_call(
                globals, '__setitem__', [self.load_static_unicode(as_name), obj],
                result_type=None, line=node.line)

    def visit_import_all(self, node: ImportAll) -> None:
        if node.is_unreachable or node.is_mypy_only:
            return
        self.gen_import(node.id, node.line)

    def gen_glue_method(self, sig: FuncSignature, target: FuncIR,
                        cls: ClassIR, base: ClassIR, line: int) -> FuncIR:
        """Generate glue methods that mediate between different method types in subclasses.

        For example, if we have:

        class A:
            def f(self, x: int) -> object: ...

        then it is totally permissable to have a subclass

        class B(A):
            def f(self, x: object) -> int: ...

        since '(object) -> int' is a subtype of '(int) -> object' by the usual
        contra/co-variant function subtyping rules.

        The trickiness here is that int and object have different
        runtime representations in mypyc, so A.f and B.f have
        different signatures at the native C level. To deal with this,
        we need to generate glue methods that mediate between the
        different versions by coercing the arguments and return
        values.
        """
        self.enter(FuncInfo())

        rt_args = (RuntimeArg(sig.args[0].name, RInstance(cls)),) + sig.args[1:]

        # The environment operates on Vars, so we make some up
        fake_vars = [(Var(arg.name), arg.type) for arg in rt_args]
        args = [self.read(self.environment.add_local_reg(var, type, is_arg=True), line)
                for var, type in fake_vars]  # type: List[Value]
        self.ret_types[-1] = sig.ret_type

        args = self.coerce_native_call_args(args, target.sig, line)
        retval = self.add(MethodCall(args[0], target.name, args[1:], line))
        retval = self.coerce(retval, sig.ret_type, line)
        self.add(Return(retval))

        blocks, env, ret_type, _ = self.leave()
        return FuncIR(
            FuncDecl(target.name + '__' + base.name + '_glue',
                     cls.name, self.module_name,
                     FuncSignature(rt_args, ret_type)),
            blocks, env)

    def gen_glue_property(self, sig: FuncSignature, target: FuncIR, cls: ClassIR, base: ClassIR,
                          line: int) -> FuncIR:
        """Similarly to methods, properties of derived types can be covariantly subtyped. Thus,
        properties also require glue. However, this only requires the return type to change.
        Further, instead of a method call, an attribute get is performed."""
        self.enter(FuncInfo())

        rt_arg = RuntimeArg('self', RInstance(cls))
        arg = self.read(self.add_self_to_env(cls), line)
        self.ret_types[-1] = sig.ret_type

        retval = self.add(GetAttr(arg, target.name, line))
        retbox = self.coerce(retval, sig.ret_type, line)
        self.add(Return(retbox))

        blocks, env, return_type, _ = self.leave()
        return FuncIR(
            FuncDecl(target.name + '__' + base.name + '_glue',
                     cls.name, self.module_name, FuncSignature([rt_arg], return_type)),
            blocks, env)

    def assign_if_null(self, target: AssignmentTargetRegister,
                       get_val: Callable[[], Value], line: int) -> None:
        """Generate blocks for registers that NULL values."""
        error_block, body_block = BasicBlock(), BasicBlock()
        self.add(Branch(target.register, error_block, body_block, Branch.IS_ERROR))
        self.activate_block(error_block)
        self.add(Assign(target.register, self.coerce(get_val(), target.register.type, line)))
        self.goto(body_block)
        self.activate_block(body_block)

    def gen_glue_ne_method(self, cls: ClassIR, line: int) -> FuncIR:
        """Generate a __ne__ method from a __eq__ method. """
        self.enter(FuncInfo())

        rt_args = (RuntimeArg("self", RInstance(cls)), RuntimeArg("rhs", object_rprimitive))

        # The environment operates on Vars, so we make some up
        fake_vars = [(Var(arg.name), arg.type) for arg in rt_args]
        args = [self.read(self.environment.add_local_reg(var, type, is_arg=True), line)
                for var, type in fake_vars]  # type: List[Value]
        self.ret_types[-1] = bool_rprimitive

        retval = self.add(MethodCall(args[0], '__eq__', [args[1]], line))
        retval = self.unary_op(retval, 'not', line)
        self.add(Return(retval))

        blocks, env, ret_type, _ = self.leave()
        return FuncIR(
            FuncDecl('__ne__', cls.name, self.module_name,
                     FuncSignature(rt_args, ret_type)),
            blocks, env)

    def create_ne_from_eq(self, cdef: ClassDef) -> None:
        cls = self.mapper.type_to_ir[cdef.info]
        if cls.has_method('__eq__') and not cls.has_method('__ne__'):
            f = self.gen_glue_ne_method(cls, cdef.line)
            cls.method_decls['__ne__'] = f.decl
            cls.methods['__ne__'] = f
            self.functions.append(f)

    def gen_arg_default(self) -> None:
        """Generate blocks for arguments that have default values.

        If the passed value is an error value, then assign the default value to the argument.
        """
        fitem = self.fn_info.fitem
        for arg in fitem.arguments:
            if arg.initializer:
                with self.catch_errors(arg.initializer.line):
                    assert self.is_approximately_constant(arg.initializer), (
                        "Unsupported default argument")
                target = self.environment.lookup(arg.variable)
                assert isinstance(target, AssignmentTargetRegister)
                self.assign_if_null(target,
                                    lambda: self.accept(cast(Expression, arg.initializer)),
                                    arg.initializer.line)

    def gen_func_item(self, fitem: FuncItem, name: str, sig: FuncSignature,
                      class_name: Optional[str] = None) -> Tuple[FuncIR, Optional[Value]]:
        # TODO: do something about abstract methods.

        """Generates and returns the FuncIR for a given FuncDef.

        If the given FuncItem is a nested function, then we generate a callable class representing
        the function and use that instead of the actual function. if the given FuncItem contains a
        nested function, then we generate an environment class so that inner nested functions can
        access the environment of the given FuncDef.

        Consider the following nested function.
        def a() -> None:
            def b() -> None:
                def c() -> None:
                    return None
                return None
            return None

        The classes generated would look something like the following.

                    has pointer to        +-------+
            +-------------------------->  | a_env |
            |                             +-------+
            |                                 ^
            |                                 | has pointer to
        +-------+     associated with     +-------+
        | b_obj |   ------------------->  | b_env |
        +-------+                         +-------+
                                              ^
                                              |
        +-------+         has pointer to      |
        | c_obj |   --------------------------+
        +-------+
        """
        assert not any(kind in (ARG_STAR, ARG_STAR2) for kind in fitem.arg_kinds)

        func_reg = None  # type: Optional[Value]

        is_nested = fitem in self.nested_fitems
        contains_nested = fitem in self.encapsulating_fitems
        self.enter(FuncInfo(fitem, name, self.gen_func_ns(), is_nested, contains_nested))

        if self.fn_info.is_nested:
            self.setup_callable_class()

        # Functions that contain nested functions need an environment class to store variables that
        # are free in their nested functions. Generator functions need an environment class to
        # store a variable denoting the next instruction to be executed when the __next__ function
        # is called, along with all the variables inside the function itself.
        if self.fn_info.contains_nested or self.fn_info.is_generator:
            self.setup_env_class()

        if self.fn_info.is_generator:
            # Do a first-pass and generate a function that just returns a generator object.
            self.gen_generator_func()
            blocks, env, ret_type, fn_info = self.leave()
            func_ir, func_reg = self.gen_func_ir(blocks, sig, env, fn_info, class_name)

            # Re-enter the FuncItem and visit the body of the function this time.
            self.enter(fn_info)
            self.setup_env_for_generator_class()
            self.load_outer_envs(self.fn_info.generator_class)
            self.create_switch_for_generator_class()
            self.add_raise_exception_blocks_to_generator_class(fitem.line)
        else:
            self.load_env_registers()
            self.gen_arg_default()

        if self.fn_info.contains_nested and not self.fn_info.is_generator:
            self.finalize_env_class()

        self.ret_types[-1] = sig.ret_type

        self.accept(fitem.body)
        self.maybe_add_implicit_return()

        if self.fn_info.is_generator:
            self.populate_switch_for_generator_class()

        blocks, env, ret_type, fn_info = self.leave()

        if fn_info.is_generator:
            helper_fn_decl = self.add_helper_to_generator_class(blocks, sig, env, fn_info)
            self.add_next_to_generator_class(fn_info, helper_fn_decl, sig)
            self.add_iter_to_generator_class(fn_info)
            self.add_throw_to_generator_class(fn_info, helper_fn_decl, sig)
        else:
            func_ir, func_reg = self.gen_func_ir(blocks, sig, env, fn_info, class_name)

        return (func_ir, func_reg)

    def gen_func_ir(self,
                    blocks: List[BasicBlock],
                    sig: FuncSignature,
                    env: Environment,
                    fn_info: FuncInfo,
                    class_name: Optional[str]) -> Tuple[FuncIR, Optional[Value]]:
        """Generates the FuncIR for a function given the blocks, environment, and function info of
        a particular function and returns it. If the function is nested, also returns the register
        containing the instance of the corresponding callable class.
        """
        func_reg = None  # type: Optional[Value]
        if fn_info.is_nested:
            func_ir = self.add_call_to_callable_class(blocks, sig, env, fn_info)
            func_reg = self.instantiate_callable_class(fn_info)
        else:
            assert isinstance(fn_info.fitem, FuncDef)
            func_ir = FuncIR(self.mapper.func_to_decl[fn_info.fitem], blocks, env)
        return (func_ir, func_reg)

    def maybe_add_implicit_return(self) -> None:
        if (is_none_rprimitive(self.ret_types[-1]) or
                is_object_rprimitive(self.ret_types[-1])):
            self.add_implicit_return()
        else:
            self.add_implicit_unreachable()

    def visit_func_def(self, fdef: FuncDef) -> None:
        func_ir, func_reg = self.gen_func_item(fdef, fdef.name(), self.mapper.fdef_to_sig(fdef))

        # If the function that was visited was a nested function, then either look it up in our
        # current environment or define it if it was not already defined.
        if func_reg:
            if fdef.original_def:
                # Get the target associated with the previously defined FuncDef.
                func_target = self.environment.lookup(fdef.original_def)
            else:
                # The return type is 'object' instead of an RInstance of the callable class because
                # differently defined functions with the same name and signature across conditional
                # blocks will generate different callable classes, so the callable class that gets
                # instantiated must be generic.
                if self.fn_info.is_generator:
                    func_target = self.add_var_to_env_class(fdef, object_rprimitive,
                                                            self.fn_info.generator_class,
                                                            reassign=False)
                else:
                    func_target = self.environment.add_local_reg(fdef, object_rprimitive)
            self.assign(func_target, func_reg, fdef.line)

        self.functions.append(func_ir)

    def add_implicit_return(self) -> None:
        block = self.blocks[-1][-1]
        if not block.ops or not isinstance(block.ops[-1], ControlOp):
            retval = self.none()
            self.nonlocal_control[-1].gen_return(self, retval)

    def add_implicit_unreachable(self) -> None:
        block = self.blocks[-1][-1]
        if not block.ops or not isinstance(block.ops[-1], ControlOp):
            self.add(Unreachable())

    def visit_block(self, block: Block) -> None:
        for stmt in block.body:
            self.accept(stmt)

    def visit_expression_stmt(self, stmt: ExpressionStmt) -> None:
        self.accept(stmt.expr)

    def visit_return_stmt(self, stmt: ReturnStmt) -> None:
        if stmt.expr:
            retval = self.accept(stmt.expr)
            retval = self.coerce(retval, self.ret_types[-1], stmt.line)
        else:
            retval = self.none()
        self.nonlocal_control[-1].gen_return(self, retval)

    def disallow_class_assignments(self, lvalues: List[Lvalue]) -> None:
        # Some best-effort attempts to disallow assigning to class
        # variables that aren't marked ClassVar, since we blatantly
        # miscompile the interaction between instance and class
        # variables.
        for lvalue in lvalues:
            if (isinstance(lvalue, MemberExpr)
                    and isinstance(lvalue.expr, RefExpr)
                    and isinstance(lvalue.expr.node, TypeInfo)):
                var = lvalue.expr.node[lvalue.name].node
                assert not isinstance(var, Var) or var.is_classvar, (
                    "mypyc only supports assignment to classvars defined as ClassVar")

    def visit_assignment_stmt(self, stmt: AssignmentStmt) -> None:
        assert len(stmt.lvalues) >= 1
        self.disallow_class_assignments(stmt.lvalues)
        lvalue = stmt.lvalues[0]
        if stmt.type and isinstance(stmt.rvalue, TempNode):
            # This is actually a variable annotation without initializer. Don't generate
            # an assignment but we need to call get_assignment_target since it adds a
            # name binding as a side effect.
            self.get_assignment_target(lvalue)
            return

        line = stmt.rvalue.line
        rvalue_reg = self.accept(stmt.rvalue)
        for lvalue in stmt.lvalues:
            target = self.get_assignment_target(lvalue)
            self.assign(target, rvalue_reg, line)

    def visit_operator_assignment_stmt(self, stmt: OperatorAssignmentStmt) -> None:
        """Operator assignment statement such as x += 1"""
        self.disallow_class_assignments([stmt.lvalue])
        target = self.get_assignment_target(stmt.lvalue)
        target_value = self.read(target, stmt.line)
        rreg = self.accept(stmt.rvalue)
        # the Python parser strips the '=' from operator assignment statements, so re-add it
        op = stmt.op + '='
        res = self.binary_op(target_value, rreg, op, stmt.line)
        # usually operator assignments are done in-place
        # but when target doesn't support that we need to manually assign
        self.assign(target, res, res.line)

    def get_assignment_target(self, lvalue: Lvalue) -> AssignmentTarget:
        if isinstance(lvalue, NameExpr):
            # Assign to local variable.
            assert isinstance(lvalue.node, SymbolNode)  # TODO: Can this fail?
            symbol = lvalue.node
            if lvalue.kind == LDEF:
                if symbol not in self.environment.symtable:
                    # If the function contains a nested function and the symbol is a free symbol,
                    # or if the function is a generator function, then first define a new variable
                    # in the current function's environment class. Next, define a target that
                    # refers to the newly defined variable in that environment class. Add the
                    # target to the table containing class environment variables, as well as the
                    # current environment.
                    if self.fn_info.is_generator:
                        return self.add_var_to_env_class(symbol, self.node_type(lvalue),
                                                         self.fn_info.generator_class,
                                                         reassign=False)

                    if self.fn_info.contains_nested and self.is_free_variable(symbol):
                        return self.add_var_to_env_class(symbol, self.node_type(lvalue),
                                                         self.fn_info, reassign=False)

                    # Otherwise define a new local variable.
                    return self.environment.add_local_reg(symbol, self.node_type(lvalue))
                else:
                    # Assign to a previously defined variable.
                    return self.environment.lookup(symbol)
            elif lvalue.kind == GDEF:
                globals_dict = self.load_globals_dict()
                name = self.load_static_unicode(lvalue.name)
                return AssignmentTargetIndex(globals_dict, name)
            else:
                assert False, lvalue.kind
        elif isinstance(lvalue, IndexExpr):
            # Indexed assignment x[y] = e
            base = self.accept(lvalue.base)
            index = self.accept(lvalue.index)
            return AssignmentTargetIndex(base, index)
        elif isinstance(lvalue, MemberExpr):
            # Attribute assignment x.y = e
            obj = self.accept(lvalue.expr)
            return AssignmentTargetAttr(obj, lvalue.name)
        elif isinstance(lvalue, TupleExpr):
            # Multiple assignment a, ..., b = e
            lvalues = [self.get_assignment_target(item)
                       for item in lvalue.items]
            return AssignmentTargetTuple(lvalues)

        assert False, 'Unsupported lvalue: %r' % lvalue

    def read(self, target: Union[Value, AssignmentTarget], line: int = -1) -> Value:
        if isinstance(target, Value):
            return target
        if isinstance(target, AssignmentTargetRegister):
            return target.register
        if isinstance(target, AssignmentTargetIndex):
            reg = self.translate_special_method_call(target.base,
                                                     '__getitem__',
                                                     [target.index],
                                                     None,
                                                     line)
            if reg is not None:
                return reg
            assert False, target.base.type
        if isinstance(target, AssignmentTargetAttr):
            if isinstance(target.obj.type, RInstance):
                return self.add(GetAttr(target.obj, target.attr, line))
            else:
                return self.py_get_attr(target.obj, target.attr, line)

        assert False, 'Unsupported lvalue: %r' % target

    def assign(self, target: Union[Register, AssignmentTarget],
               rvalue_reg: Value, line: int) -> None:
        if isinstance(target, Register):
            self.add(Assign(target, rvalue_reg))
        elif isinstance(target, AssignmentTargetRegister):
            rvalue_reg = self.coerce(rvalue_reg, target.type, line)
            self.add(Assign(target.register, rvalue_reg))
        elif isinstance(target, AssignmentTargetAttr):
            if isinstance(target.obj_type, RInstance):
                rvalue_reg = self.coerce(rvalue_reg, target.type, line)
                self.add(SetAttr(target.obj, target.attr, rvalue_reg, line))
            else:
                key = self.load_static_unicode(target.attr)
                boxed_reg = self.box(rvalue_reg)
                self.add(PrimitiveOp([target.obj, key, boxed_reg], py_setattr_op, line))
        elif isinstance(target, AssignmentTargetIndex):
            target_reg2 = self.translate_special_method_call(
                target.base,
                '__setitem__',
                [target.index, rvalue_reg],
                None,
                line)
            assert target_reg2 is not None, target.base.type
        elif isinstance(target, AssignmentTargetTuple):
            if isinstance(rvalue_reg.type, RTuple):
                rtypes = rvalue_reg.type.types
                assert len(rtypes) == len(target.items)
                for i in range(len(rtypes)):
                    item_value = self.add(TupleGet(rvalue_reg, i, line))
                    self.assign(target.items[i], item_value, line)
            else:
                self.process_iterator_tuple_assignment(target, rvalue_reg, line)
        else:
            assert False, 'Unsupported assignment target'

    def process_iterator_tuple_assignment(self,
                                          target: AssignmentTargetTuple,
                                          rvalue_reg: Value,
                                          line: int) -> None:
        iterator = self.primitive_op(iter_op, [rvalue_reg], line)
        for litem in target.items:
            error_block, ok_block = BasicBlock(), BasicBlock()
            ritem = self.primitive_op(next_op, [iterator], line)
            self.add(Branch(ritem, error_block, ok_block, Branch.IS_ERROR))

            self.activate_block(error_block)
            self.add(RaiseStandardError(RaiseStandardError.VALUE_ERROR,
                                        'not enough values to unpack', line))
            self.add(Unreachable())

            self.activate_block(ok_block)
            self.assign(litem, ritem, line)
        extra = self.primitive_op(next_op, [iterator], line)
        error_block, ok_block = BasicBlock(), BasicBlock()
        self.add(Branch(extra, ok_block, error_block, Branch.IS_ERROR))

        self.activate_block(error_block)
        self.add(RaiseStandardError(RaiseStandardError.VALUE_ERROR,
                                    'too many values to unpack', line))
        self.add(Unreachable())

        self.activate_block(ok_block)

    def visit_if_stmt(self, stmt: IfStmt) -> None:
        if_body, next = BasicBlock(), BasicBlock()
        else_body = BasicBlock() if stmt.else_body else next

        # If statements are normalized
        assert len(stmt.expr) == 1

        self.process_conditional(stmt.expr[0], if_body, else_body)
        self.activate_block(if_body)
        self.accept(stmt.body[0])
        self.goto(next)
        if stmt.else_body:
            self.activate_block(else_body)
            self.accept(stmt.else_body)
            self.goto(next)
        self.activate_block(next)

    class LoopNonlocalControl(NonlocalControl):
        def __init__(self, outer: NonlocalControl,
                     continue_block: BasicBlock, break_block: BasicBlock) -> None:
            self.outer = outer
            self.continue_block = continue_block
            self.break_block = break_block

        def gen_break(self, builder: 'IRBuilder') -> None:
            builder.add(Goto(self.break_block))

        def gen_continue(self, builder: 'IRBuilder') -> None:
            builder.add(Goto(self.continue_block))

        def gen_return(self, builder: 'IRBuilder', value: Value) -> None:
            self.outer.gen_return(builder, value)

    def push_loop_stack(self, continue_block: BasicBlock, break_block: BasicBlock) -> None:
        self.nonlocal_control.append(
            IRBuilder.LoopNonlocalControl(self.nonlocal_control[-1], continue_block, break_block))

    def pop_loop_stack(self) -> None:
        self.nonlocal_control.pop()

    def visit_while_stmt(self, s: WhileStmt) -> None:
        body, next, top, else_block = BasicBlock(), BasicBlock(), BasicBlock(), BasicBlock()
        normal_loop_exit = else_block if s.else_body is not None else next

        self.push_loop_stack(top, next)

        # Split block so that we get a handle to the top of the loop.
        self.goto_and_activate(top)
        self.process_conditional(s.expr, body, normal_loop_exit)

        self.activate_block(body)
        self.accept(s.body)
        # Add branch to the top at the end of the body.
        self.goto(top)

        self.pop_loop_stack()

        if s.else_body is not None:
            self.activate_block(else_block)
            self.accept(s.else_body)
            self.goto(next)

        self.activate_block(next)

    def visit_for_stmt(self, s: ForStmt) -> None:
        def body() -> None:
            self.accept(s.body)

        def else_block() -> None:
            assert s.else_body is not None
            self.accept(s.else_body)

        self.for_loop_helper(s.index, s.expr, body, else_block if s.else_body else None, s.line)

    def spill(self, value: Value) -> AssignmentTarget:
        """Moves a given Value instance into the generator class' environment class."""
        name = '{}{}'.format(TEMP_ATTR_NAME, self.temp_counter)
        self.temp_counter += 1
        target = self.add_var_to_env_class(Var(name), value.type, self.fn_info.generator_class)
        # Shouldn't be able to fail, so -1 for line
        self.assign(target, value, -1)
        return target

    def maybe_spill(self, value: Value) -> Union[Value, AssignmentTarget]:
        """
        Moves a given Value instance into the environment class for generator functions. For
        non-generator functions, leaves the Value instance as it is.

        Returns an AssignmentTarget associated with the Value for generator functions and the
        original Value itself for non-generator functions.
        """
        if self.fn_info.is_generator:
            return self.spill(value)
        return value

    def maybe_spill_assignable(self, value: Value) -> Union[Register, AssignmentTarget]:
        """
        Moves a given Value instance into the environment class for generator functions. For
        non-generator functions, allocate a temporary Register.

        Returns an AssignmentTarget associated with the Value for generator functions and an
        assignable Register for non-generator functions.
        """
        if self.fn_info.is_generator:
            return self.spill(value)

        if isinstance(value, Register):
            return value

        # Allocate a temporary register for the assignable value.
        reg = self.alloc_temp(value.type)
        self.assign(reg, value, -1)
        return reg

    def for_loop_helper(self, index: Lvalue, expr: Expression,
                        body_insts: GenFunc, else_insts: Optional[GenFunc], line: int) -> None:
        """Generate IR for a loop.

        "index" is the loop index Lvalue
        "expr" is the expression to iterate over
        "body_insts" is a function to generate the body of the loop.
        """
        body_block, exit_block, increment_block = BasicBlock(), BasicBlock(), BasicBlock()
        # Block for the else clause, if we need it.
        else_block = BasicBlock()

        # Determine where we want to exit, if our condition check fails.
        normal_loop_exit = else_block if else_insts is not None else exit_block

        # Only support 1 and 2 arg forms for now
        if (isinstance(expr, CallExpr)
                and isinstance(expr.callee, RefExpr)
                and expr.callee.fullname == 'builtins.range'
                and len(expr.args) <= 2):

            condition_block = BasicBlock()
            self.push_loop_stack(increment_block, exit_block)

            # Special case for x in range(...)
            # TODO: Check argument counts and kinds; check the lvalue
            if len(expr.args) == 1:
                start_reg = self.add(LoadInt(0))
                end_reg = self.accept(expr.args[0])
            else:
                start_reg = self.accept(expr.args[0])
                end_reg = self.accept(expr.args[1])

            end_target = self.maybe_spill(end_reg)

            # Initialize loop index to 0. Assert that the index target is assignable.
            index_target = self.get_assignment_target(
                index)  # type: Union[Register, AssignmentTarget]
            self.assign(index_target, start_reg, line)
            self.goto(condition_block)

            # Add loop condition check.
            self.activate_block(condition_block)
            comparison = self.binary_op(self.read(index_target, line),
                                        self.read(end_target, line), '<', line)
            self.add_bool_branch(comparison, body_block, normal_loop_exit)

            self.activate_block(body_block)
            body_insts()

            self.goto_and_activate(increment_block)

            # Increment index register.
            self.assign(index_target, self.binary_op(self.read(index_target, line),
                                                     self.add(LoadInt(1)), '+', line), line)

            # Go back to loop condition check.
            self.goto(condition_block)

            self.pop_loop_stack()

        elif is_list_rprimitive(self.node_type(expr)):
            self.push_loop_stack(increment_block, exit_block)

            # Define targets to contain the expression, along with the index that will be used
            # for the for-loop. If we are inside of a generator function, spill these into the
            # environment class.
            expr_reg = self.accept(expr)
            index_reg = self.add(LoadInt(0))
            expr_target = self.maybe_spill(expr_reg)
            index_target = self.maybe_spill_assignable(index_reg)

            condition_block = self.goto_new_block()

            # For compatibility with python semantics we recalculate the length
            # at every iteration.
            len_reg = self.add(PrimitiveOp([self.read(expr_target, line)], list_len_op, line))
            comparison = self.binary_op(self.read(index_target, line), len_reg, '<', line)
            self.add_bool_branch(comparison, body_block, normal_loop_exit)

            self.activate_block(body_block)
            target_list_type = self.types[expr]
            assert isinstance(target_list_type, Instance)
            target_type = self.type_to_rtype(target_list_type.args[0])

            value_box = self.add(PrimitiveOp([self.read(expr_target, line),
                                              self.read(index_target, line)],
                                             list_get_item_op, line))

            self.assign(self.get_assignment_target(index),
                        self.unbox_or_cast(value_box, target_type, line), line)

            body_insts()

            self.goto_and_activate(increment_block)
            self.assign(index_target, self.binary_op(self.read(index_target, line),
                                                     self.add(LoadInt(1)), '+', line), line)
            self.goto(condition_block)

            self.pop_loop_stack()

        else:
            error_check_block = BasicBlock()

            self.push_loop_stack(increment_block, exit_block)

            # Define targets to contain the expression, along with the iterator that will be used
            # for the for-loop. If we are inside of a generator function, spill these into the
            # environment class.
            expr_reg = self.accept(expr)
            iter_reg = self.primitive_op(iter_op, [expr_reg], line)
            expr_target = self.maybe_spill(expr_reg)
            iter_target = self.maybe_spill(iter_reg)

            # Create a block for where the __next__ function will be called on the iterator and
            # checked to see if the value returned is NULL, which would signal either the end of
            # the Iterable being traversed or an exception being raised. Note that Branch.IS_ERROR
            # checks only for NULL (an exception does not necessarily have to be raised).
            self.goto_and_activate(increment_block)
            next_reg = self.primitive_op(next_op, [self.read(iter_target, line)], line)
            self.add(Branch(next_reg, error_check_block, body_block, Branch.IS_ERROR))

            # Create a new block for the body of the loop. Set the previous branch to go here if
            # the conditional evaluates to false. Assign the value obtained from __next__ to the
            # lvalue so that it can be referenced by code in the body of the loop. At the end of
            # the body, goto the label that calls the iterator's __next__ function again.
            self.activate_block(body_block)
            self.assign(self.get_assignment_target(index), next_reg, line)
            body_insts()
            self.goto(increment_block)

            # Create a new block for when the loop is finished. Set the branch to go here if the
            # conditional evaluates to true. If an exception was raised during the loop, then
            # err_reg wil be set to True. If no_err_occurred_op returns False, then the exception
            # will be propagated using the ERR_FALSE flag.
            self.activate_block(error_check_block)
            self.primitive_op(no_err_occurred_op, [], line)
            self.goto(normal_loop_exit)

            self.pop_loop_stack()

        if else_insts is not None:
            self.activate_block(else_block)
            else_insts()
            self.goto(exit_block)
        self.activate_block(exit_block)

    def visit_break_stmt(self, node: BreakStmt) -> None:
        self.nonlocal_control[-1].gen_break(self)

    def visit_continue_stmt(self, node: ContinueStmt) -> None:
        self.nonlocal_control[-1].gen_continue(self)

    def visit_unary_expr(self, expr: UnaryExpr) -> Value:
        return self.unary_op(self.accept(expr.expr), expr.op, expr.line)

    def visit_op_expr(self, expr: OpExpr) -> Value:
        if expr.op in ('and', 'or'):
            return self.shortcircuit_expr(expr)
        return self.binary_op(self.accept(expr.left), self.accept(expr.right), expr.op, expr.line)

    def matching_primitive_op(self,
                              candidates: List[OpDescription],
                              args: List[Value],
                              line: int,
                              result_type: Optional[RType] = None) -> Optional[Value]:
        # Find the highest-priority primitive op that matches.
        matching = None  # type: Optional[OpDescription]
        for desc in candidates:
            if len(desc.arg_types) != len(args):
                continue
            if all(is_subtype(actual.type, formal)
                   for actual, formal in zip(args, desc.arg_types)):
                if matching:
                    assert matching.priority != desc.priority, 'Ambiguous:\n1) %s\n2) %s' % (
                        matching, desc)
                    if desc.priority > matching.priority:
                        matching = desc
                else:
                    matching = desc
        if matching:
            target = self.primitive_op(matching, args, line)
            if result_type and not is_same_type(target.type, result_type):
                if is_none_rprimitive(result_type):
                    # Special case None return. The actual result may actually be a bool
                    # and so we can't just coerce it.
                    target = self.none()
                else:
                    target = self.coerce(target, result_type, line)
            return target
        return None

    def binary_op(self,
                  lreg: Value,
                  rreg: Value,
                  expr_op: str,
                  line: int) -> Value:
        ops = binary_ops.get(expr_op, [])
        target = self.matching_primitive_op(ops, [lreg, rreg], line)
        assert target, 'Unsupported binary operation: %s' % expr_op
        return target

    def unary_op(self,
                 lreg: Value,
                 expr_op: str,
                 line: int) -> Value:
        ops = unary_ops.get(expr_op, [])
        target = self.matching_primitive_op(ops, [lreg], line)
        assert target, 'Unsupported unary operation: %s' % expr_op
        return target

    def visit_index_expr(self, expr: IndexExpr) -> Value:
        base = self.accept(expr.base)

        if isinstance(base.type, RTuple):
            assert isinstance(expr.index, IntExpr)  # TODO
            return self.add(TupleGet(base, expr.index.value, expr.line))

        index_reg = self.accept(expr.index)
        return self.gen_method_call(
            base, '__getitem__', [index_reg], self.node_type(expr), expr.line)

    def visit_int_expr(self, expr: IntExpr) -> Value:
        if expr.value > MAX_SHORT_INT:
            return self.load_static_int(expr.value)
        return self.add(LoadInt(expr.value))

    def visit_float_expr(self, expr: FloatExpr) -> Value:
        return self.load_static_float(expr.value)

    def visit_bytes_expr(self, expr: BytesExpr) -> Value:
        value = bytes(expr.value, 'utf8').decode('unicode-escape').encode('raw-unicode-escape')
        return self.load_static_bytes(value)

    def is_native_ref_expr(self, expr: RefExpr) -> bool:
        if expr.node is None:
            return False
        if '.' in expr.node.fullname():
            module_name = '.'.join(expr.node.fullname().split('.')[:-1])
            return module_name in self.modules
        return True

    def is_native_module_ref_expr(self, expr: RefExpr) -> bool:
        return self.is_native_ref_expr(expr) and expr.kind == GDEF

    def is_synthetic_type(self, typ: TypeInfo) -> bool:
        """Is a type something other than just a class we've created?"""
        return typ.is_named_tuple or typ.is_newtype or typ.typeddict_type is not None

    def is_free_variable(self, symbol: SymbolNode) -> bool:
        fitem = self.fn_info.fitem
        return fitem in self.free_variables and symbol in self.free_variables[fitem]

    def visit_name_expr(self, expr: NameExpr) -> Value:
        assert expr.node, "RefExpr not resolved"
        fullname = expr.node.fullname()
        if fullname in name_ref_ops:
            # Use special access op for this particular name.
            desc = name_ref_ops[fullname]
            assert desc.result_type is not None
            return self.add(PrimitiveOp([], desc, expr.line))

        # TODO: Behavior currently only defined for Var and FuncDef node types.
        if expr.kind == LDEF:
            try:
                return self.read(self.environment.lookup(expr.node), expr.line)
            except KeyError:
                # If there is a KeyError, then the target could not be found in the current scope.
                # Search environment stack to see if the target was defined in an outer scope.
                return self.read(self.get_assignment_target(expr), expr.line)
        else:
            return self.load_global(expr)

    def is_module_member_expr(self, expr: MemberExpr) -> bool:
        return isinstance(expr.expr, RefExpr) and expr.expr.kind == MODULE_REF

    def visit_member_expr(self, expr: MemberExpr) -> Value:
        if self.is_module_member_expr(expr):
            return self.load_module_attr(expr)
        else:
            obj = self.accept(expr.expr)
            return self.get_attr(obj, expr.name, self.node_type(expr), expr.line)

    def get_attr(self, obj: Value, attr: str, result_type: RType, line: int) -> Value:
        if isinstance(obj.type, RInstance) and obj.type.class_ir.has_attr(attr):
            return self.add(GetAttr(obj, attr, line))
        elif isinstance(obj.type, RUnion):
            return self.union_get_attr(obj, obj.type, attr, result_type, line)
        else:
            return self.py_get_attr(obj, attr, line)

    def union_get_attr(self,
                       obj: Value,
                       rtype: RUnion,
                       attr: str,
                       result_type: RType,
                       line: int) -> Value:
        def get_item_attr(value: Value) -> Value:
            return self.get_attr(value, attr, result_type, line)

        return self.decompose_union_helper(obj, rtype, result_type, get_item_attr, line)

    def decompose_union_helper(self,
                               obj: Value,
                               rtype: RUnion,
                               result_type: RType,
                               process_item: Callable[[Value], Value],
                               line: int) -> Value:
        """Generate isinstance() + specialized operations for union items.

        Say, for Union[A, B] generate ops resembling this (pseudocode):

            if isinstance(obj, A):
                result = <result of process_item(cast(A, obj)>
            else:
                result = <result of process_item(cast(B, obj)>

        Args:
            obj: value with a union type
            rtype: the union type
            result_type: result of the operation
            process_item: callback to generate op for a single union item (arg is coerced
                to union item type)
            line: line number
        """
        # TODO: Optimize cases where a single operation can handle multiple union items
        #     (say a method is implemented in a common base class)
        fast_items = []
        rest_items = []
        for item in rtype.items:
            if isinstance(item, RInstance):
                fast_items.append(item)
            else:
                # For everything but RInstance we fall back to C API
                rest_items.append(item)
        exit_block = BasicBlock()
        result = self.alloc_temp(result_type)
        for i, item in enumerate(fast_items):
            more_types = i < len(fast_items) - 1 or rest_items
            if more_types:
                # We are not at the final item so we need one more branch
                op = self.isinstance(obj, item, line)
                true_block, false_block = BasicBlock(), BasicBlock()
                self.add_bool_branch(op, true_block, false_block)
                self.activate_block(true_block)
            coerced = self.coerce(obj, item, line)
            temp = process_item(coerced)
            temp2 = self.coerce(temp, result_type, line)
            self.add(Assign(result, temp2))
            self.goto(exit_block)
            if more_types:
                self.activate_block(false_block)
        if rest_items:
            # For everything else we use generic operation. Use force=True to drop the
            # union type.
            coerced = self.coerce(obj, object_rprimitive, line, force=True)
            temp = process_item(coerced)
            temp2 = self.coerce(temp, result_type, line)
            self.add(Assign(result, temp2))
            self.goto(exit_block)
        self.activate_block(exit_block)
        return result

    def isinstance(self, obj: Value, rtype: RInstance, line: int) -> Value:
        class_ir = rtype.class_ir
        fullname = '%s.%s' % (class_ir.module_name, class_ir.name)
        type_obj = self.load_native_type_object(fullname)
        return self.primitive_op(fast_isinstance_op, [obj, type_obj], line)

    def py_get_attr(self, obj: Value, attr: str, line: int) -> Value:
        key = self.load_static_unicode(attr)
        return self.add(PrimitiveOp([obj, key], py_getattr_op, line))

    def py_call(self,
                function: Value,
                arg_values: List[Value],
                line: int,
                arg_kinds: Optional[List[int]] = None,
                arg_names: Optional[List[Optional[str]]] = None) -> Value:
        """Use py_call_op or py_call_with_kwargs_op for function call."""
        # If all arguments are positional, we can use py_call_op.
        if (arg_kinds is None) or all(kind == ARG_POS for kind in arg_kinds):
            return self.primitive_op(py_call_op, [function] + arg_values, line)

        # Otherwise fallback to py_call_with_kwargs_op.
        assert arg_names is not None

        pos_arg_values = []
        kw_arg_key_value_pairs = []
        star_arg_values = []
        star2_arg_values = []
        for value, kind, name in zip(arg_values, arg_kinds, arg_names):
            if kind == ARG_POS:
                pos_arg_values.append(value)
            elif kind == ARG_NAMED:
                assert name is not None
                key = self.load_static_unicode(name)
                kw_arg_key_value_pairs.append((key, value))
            elif kind == ARG_STAR:
                star_arg_values.append(value)
            elif kind == ARG_STAR2:
                star2_arg_values.append(value)
            else:
                assert False, ("Argument kind should not be possible:", kind)

        if len(star_arg_values) == 0:
            # We can directly construct a tuple if there are no star args.
            pos_args_tuple = self.add(TupleSet(pos_arg_values, line))
        else:
            # Otherwise we construct a list and call extend it with the star args, since tuples
            # don't have an extend method.
            pos_args_list = self.primitive_op(new_list_op, pos_arg_values, line)
            for star_arg_value in star_arg_values:
                self.primitive_op(list_extend_op, [pos_args_list, star_arg_value], line)
            pos_args_tuple = self.primitive_op(list_tuple_op, [pos_args_list], line)

        kw_args_dict = self.make_dict(kw_arg_key_value_pairs, line)
        # NOTE: mypy currently only supports a single ** arg, but python supports multiple.
        # This code supports multiple primarily to make the logic easier to follow.
        for star2_arg_value in star2_arg_values:
            self.primitive_op(dict_update_op, [kw_args_dict, star2_arg_value], line)

        return self.primitive_op(
            py_call_with_kwargs_op, [function, pos_args_tuple, kw_args_dict], line)

    def py_method_call(self,
                       obj: Value,
                       method_name: str,
                       arg_values: List[Value],
                       line: int,
                       arg_kinds: Optional[List[int]] = None,
                       arg_names: Optional[List[Optional[str]]] = None) -> Value:
        if (arg_kinds is None) or all(kind == ARG_POS for kind in arg_kinds):
            method_name_reg = self.load_static_unicode(method_name)
            return self.primitive_op(py_method_call_op, [obj, method_name_reg] + arg_values, line)
        else:
            method = self.py_get_attr(obj, method_name, line)
            return self.py_call(method, arg_values, line, arg_kinds=arg_kinds, arg_names=arg_names)

    def coerce_native_call_args(self,
                                args: Sequence[Value],
                                sig: FuncSignature,
                                line: int) -> List[Value]:
        coerced_arg_regs = []
        for reg, arg in zip(args, sig.args):
            coerced_arg_regs.append(self.coerce(reg, arg.type, line))
        return coerced_arg_regs

    def call(self, decl: FuncDecl, args: Sequence[Value],
             arg_kinds: List[int],
             arg_names: List[Optional[str]],
             line: int) -> Value:
        # Normalize keyword args to positionals.
        arg_values_with_nones = self.keyword_args_to_positional(
            args, arg_kinds, arg_names, decl.sig)
        # Put in errors for missing args
        args = self.missing_args_to_error_values(arg_values_with_nones, decl.sig)

        args = self.coerce_native_call_args(args, decl.sig, line)
        return self.add(Call(decl, args, line))

    def visit_call_expr(self, expr: CallExpr) -> Value:
        if isinstance(expr.analyzed, CastExpr):
            return self.translate_cast_expr(expr.analyzed)

        callee = expr.callee
        if isinstance(callee, IndexExpr) and isinstance(callee.analyzed, TypeApplication):
            callee = callee.analyzed.expr  # Unwrap type application

        if isinstance(callee, MemberExpr):
            return self.translate_method_call(expr, callee)
        elif isinstance(callee, SuperExpr):
            return self.translate_super_method_call(expr, callee)
        else:
            return self.translate_call(expr, callee)

    def translate_call(self, expr: CallExpr, callee: Expression) -> Value:
        # The common case of calls is refexprs
        if isinstance(callee, RefExpr):
            return self.translate_refexpr_call(expr, callee)

        function = self.accept(callee)
        args = [self.accept(arg) for arg in expr.args]
        return self.py_call(function, args, expr.line,
                            arg_kinds=expr.arg_kinds, arg_names=expr.arg_names)

    def translate_refexpr_call(self, expr: CallExpr, callee: RefExpr) -> Value:
        """Translate a non-method call."""
        # Gen the argument values
        arg_values = [self.accept(arg) for arg in expr.args]

        # TODO: Allow special cases to have default args or named args. Currently they don't since
        # they check that everything in arg_kinds is ARG_POS.

        # TODO: Generalize special cases

        # Special case builtins.len
        if (callee.fullname == 'builtins.len'
                and len(expr.args) == 1
                and expr.arg_kinds == [ARG_POS]):
            expr_rtype = arg_values[0].type
            if isinstance(expr_rtype, RTuple):
                # len() of fixed-length tuple can be trivially determined statically.
                return self.add(LoadInt(len(expr_rtype.types)))

        # Special case builtins.isinstance
        if (callee.fullname == 'builtins.isinstance'
                and len(expr.args) == 2
                and expr.arg_kinds == [ARG_POS, ARG_POS]
                and isinstance(expr.args[1], RefExpr)
                and isinstance(expr.args[1].node, TypeInfo)
                and self.is_native_module_ref_expr(expr.args[1])):
            # Special case native isinstance() checks as this makes them much faster.
            return self.primitive_op(fast_isinstance_op, arg_values, expr.line)

        # Special case builtins.globals
        if (callee.fullname == 'builtins.globals'
                and len(expr.args) == 0):
            return self.load_globals_dict()

        # Handle data-driven special-cased primitive call ops.
        if callee.fullname is not None and expr.arg_kinds == [ARG_POS] * len(arg_values):
            ops = func_ops.get(callee.fullname, [])
            target = self.matching_primitive_op(ops, arg_values, expr.line)
            if target:
                return target

        # Standard native call if signature and fullname are good and all arguments are positional
        # or named.
        if (callee.node is not None
                and callee.fullname is not None
                and callee.node in self.mapper.func_to_decl
                and all(kind in (ARG_POS, ARG_NAMED) for kind in expr.arg_kinds)):
            decl = self.mapper.func_to_decl[callee.node]

            return self.call(decl, arg_values, expr.arg_kinds, expr.arg_names, expr.line)

        # Fall back to a Python call
        function = self.accept(callee)
        return self.py_call(function, arg_values, expr.line,
                            arg_kinds=expr.arg_kinds, arg_names=expr.arg_names)

    def missing_args_to_error_values(self,
                                     args: List[Optional[Value]],
                                     sig: FuncSignature) -> List[Value]:
        """Generate LoadErrorValues for missing arguments.

        These get resolved to default values if they exist for the function in question. See
        gen_arg_default.
        """
        ret_args = []  # type: List[Value]
        for reg, arg in zip(args, sig.args):
            if reg is None:
                reg = self.add(LoadErrorValue(arg.type, is_borrowed=True))
            ret_args.append(reg)
        return ret_args

    def translate_method_call(self, expr: CallExpr, callee: MemberExpr) -> Value:
        """Generate IR for an arbitrary call of form e.m(...).

        This can also deal with calls to module-level functions.
        """
        if self.is_native_ref_expr(callee):
            # Call to module-level native function or such
            return self.translate_call(expr, callee)
        elif isinstance(callee.expr, RefExpr) and callee.expr.node in self.mapper.type_to_ir:
            # Call a method via the *class*
            assert isinstance(callee.expr.node, TypeInfo)
            ir = self.mapper.type_to_ir[callee.expr.node]
            decl = ir.method_decl(callee.name)
            args = []
            arg_kinds, arg_names = expr.arg_kinds[:], expr.arg_names[:]
            if decl.kind == FUNC_CLASSMETHOD:  # Add the class argument for class methods
                args.append(self.load_native_type_object(callee.expr.node.fullname()))
                arg_kinds.insert(0, ARG_POS)
                arg_names.insert(0, None)
            args += [self.accept(arg) for arg in expr.args]

            return self.call(decl, args, arg_kinds, arg_names, expr.line)

        elif self.is_module_member_expr(callee):
            # Fall back to a PyCall for non-native module calls
            function = self.accept(callee)
            args = [self.accept(arg) for arg in expr.args]
            return self.py_call(function, args, expr.line,
                                arg_kinds=expr.arg_kinds, arg_names=expr.arg_names)
        else:
            args = [self.accept(arg) for arg in expr.args]
            obj = self.accept(callee.expr)
            return self.gen_method_call(obj,
                                        callee.name,
                                        args,
                                        self.node_type(expr),
                                        expr.line,
                                        expr.arg_kinds,
                                        expr.arg_names)

    def translate_super_method_call(self, expr: CallExpr, callee: SuperExpr) -> Value:
        if callee.info is None or callee.call.args:
            return self.translate_call(expr, callee)
        ir = self.mapper.type_to_ir[callee.info]
        # Search for the method in the mro, skipping ourselves.
        for base in ir.mro[1:]:
            if callee.name in base.method_decls:
                break
        else:
            return self.translate_call(expr, callee)

        decl = base.method_decl(callee.name)
        arg_values = [self.accept(arg) for arg in expr.args]
        arg_kinds, arg_names = expr.arg_kinds[:], expr.arg_names[:]

        if decl.kind != FUNC_STATICMETHOD:
            vself = next(iter(self.environment.indexes))  # grab first argument
            if decl.kind == FUNC_CLASSMETHOD:
                vself = self.primitive_op(type_op, [vself], expr.line)
            arg_values.insert(0, vself)
            arg_kinds.insert(0, ARG_POS)
            arg_names.insert(0, None)

        return self.call(decl, arg_values, arg_kinds, arg_names, expr.line)

    def gen_method_call(self,
                        base: Value,
                        name: str,
                        arg_values: List[Value],
                        return_rtype: RType,
                        line: int,
                        arg_kinds: Optional[List[int]] = None,
                        arg_names: Optional[List[Optional[str]]] = None) -> Value:
        # If arg_kinds contains values other than arg_pos and arg_named, then fallback to
        # Python method call.
        if (arg_kinds is not None
                and not all(kind in (ARG_POS, ARG_NAMED) for kind in arg_kinds)):
            return self.py_method_call(base, name, arg_values, base.line, arg_kinds, arg_names)

        # If the base type is one of ours, do a MethodCall
        if isinstance(base.type, RInstance):
            if base.type.class_ir.has_method(name):
                decl = base.type.class_ir.method_decl(name)
                if arg_kinds is None:
                    assert arg_names is None, "arg_kinds not present but arg_names is"
                    arg_kinds = [ARG_POS for _ in arg_values]
                    arg_names = [None for _ in arg_values]
                else:
                    assert arg_names is not None, "arg_kinds present but arg_names is not"

                # Normalize keyword args to positionals.
                assert decl.bound_sig
                arg_values_with_nones = self.keyword_args_to_positional(
                    arg_values, arg_kinds, arg_names, decl.bound_sig)
                arg_values = self.missing_args_to_error_values(arg_values_with_nones,
                                                               decl.bound_sig)
                arg_values = self.coerce_native_call_args(arg_values, decl.bound_sig, base.line)

                return self.add(MethodCall(base, name, arg_values, line))
        elif isinstance(base.type, RUnion):
            return self.union_method_call(base, base.type, name, arg_values, return_rtype, line,
                                          arg_kinds, arg_names)

        # Try to do a special-cased method call
        target = self.translate_special_method_call(base, name, arg_values, return_rtype, line)
        if target:
            return target

        # Fall back to Python method call
        return self.py_method_call(base, name, arg_values, base.line, arg_kinds, arg_names)

    def union_method_call(self,
                          base: Value,
                          obj_type: RUnion,
                          name: str,
                          arg_values: List[Value],
                          return_rtype: RType,
                          line: int,
                          arg_kinds: Optional[List[int]],
                          arg_names: Optional[List[Optional[str]]]) -> Value:
        def call_union_item(value: Value) -> Value:
            return self.gen_method_call(value, name, arg_values, return_rtype, line,
                                        arg_kinds, arg_names)

        return self.decompose_union_helper(base, obj_type, return_rtype, call_union_item, line)

    def translate_cast_expr(self, expr: CastExpr) -> Value:
        src = self.accept(expr.expr)
        target_type = self.type_to_rtype(expr.type)
        return self.coerce(src, target_type, expr.line)

    def shortcircuit_helper(self, op: str,
                            expr_type: RType,
                            left: Callable[[], Value],
                            right: Callable[[], Value], line: int) -> Value:
        # Having actual Phi nodes would be really nice here!
        target = self.alloc_temp(expr_type)
        # left_body takes the value of the left side, right_body the right
        left_body, right_body, next = BasicBlock(), BasicBlock(), BasicBlock()
        # true_body is taken if the left is true, false_body if it is false.
        # For 'and' the value is the right side if the left is true, and for 'or'
        # it is the right side if the left is false.
        true_body, false_body = (
            (right_body, left_body) if op == 'and' else (left_body, right_body))

        left_value = left()
        self.add_bool_branch(left_value, true_body, false_body)

        self.activate_block(left_body)
        left_coerced = self.coerce(left_value, expr_type, line)
        self.add(Assign(target, left_coerced))
        self.goto(next)

        self.activate_block(right_body)
        right_value = right()
        right_coerced = self.coerce(right_value, expr_type, line)
        self.add(Assign(target, right_coerced))
        self.goto(next)

        self.activate_block(next)
        return target

    def shortcircuit_expr(self, expr: OpExpr) -> Value:
        return self.shortcircuit_helper(
            expr.op, self.node_type(expr),
            lambda: self.accept(expr.left),
            lambda: self.accept(expr.right),
            expr.line
        )

    def visit_conditional_expr(self, expr: ConditionalExpr) -> Value:
        if_body, else_body, next = BasicBlock(), BasicBlock(), BasicBlock()

        self.process_conditional(expr.cond, if_body, else_body)
        expr_type = self.node_type(expr)
        # Having actual Phi nodes would be really nice here!
        target = self.alloc_temp(expr_type)

        self.activate_block(if_body)
        true_value = self.accept(expr.if_expr)
        true_value = self.coerce(true_value, expr_type, expr.line)
        self.add(Assign(target, true_value))
        self.goto(next)

        self.activate_block(else_body)
        false_value = self.accept(expr.else_expr)
        false_value = self.coerce(false_value, expr_type, expr.line)
        self.add(Assign(target, false_value))
        self.goto(next)

        self.activate_block(next)

        return target

    def translate_special_method_call(self,
                                      base_reg: Value,
                                      name: str,
                                      args: List[Value],
                                      result_type: Optional[RType],
                                      line: int) -> Optional[Value]:
        """Translate a method call which is handled nongenerically.

        These are special in the sense that we have code generated specifically for them.
        They tend to be method calls which have equivalents in C that are more direct
        than calling with the PyObject api.

        Return None if no translation found; otherwise return the target register.
        """
        ops = method_ops.get(name, [])
        return self.matching_primitive_op(ops, [base_reg] + args, line, result_type=result_type)

    def visit_list_expr(self, expr: ListExpr) -> Value:
        items = [self.accept(item) for item in expr.items]
        return self.primitive_op(new_list_op, items, expr.line)

    def visit_tuple_expr(self, expr: TupleExpr) -> Value:
        tuple_type = self.node_type(expr)
        # When handling NamedTuple et. al we might not have proper type info,
        # so make some up if we need it.
        types = (tuple_type.types if isinstance(tuple_type, RTuple)
                 else [object_rprimitive] * len(expr.items))

        items = []
        for item_expr, item_type in zip(expr.items, types):
            reg = self.accept(item_expr)
            items.append(self.coerce(reg, item_type, item_expr.line))
        return self.add(TupleSet(items, expr.line))

    def visit_dict_expr(self, expr: DictExpr) -> Value:
        """First accepts all keys and values, then makes a dict out of them."""
        key_value_pairs = []
        for key_expr, value_expr in expr.items:
            key = self.accept(key_expr)
            value = self.accept(value_expr)
            key_value_pairs.append((key, value))

        return self.make_dict(key_value_pairs, expr.line)

    def visit_set_expr(self, expr: SetExpr) -> Value:
        set_reg = self.primitive_op(new_set_op, [], expr.line)
        for key_expr in expr.items:
            key_reg = self.accept(key_expr)
            self.primitive_op(set_add_op, [set_reg, key_reg], expr.line)
        return set_reg

    def visit_str_expr(self, expr: StrExpr) -> Value:
        return self.load_static_unicode(expr.value)

    # Conditional expressions

    def process_conditional(self, e: Expression, true: BasicBlock, false: BasicBlock) -> None:
        if isinstance(e, OpExpr) and e.op in ['and', 'or']:
            if e.op == 'and':
                # Short circuit 'and' in a conditional context.
                new = BasicBlock()
                self.process_conditional(e.left, new, false)
                self.activate_block(new)
                self.process_conditional(e.right, true, false)
            else:
                # Short circuit 'or' in a conditional context.
                new = BasicBlock()
                self.process_conditional(e.left, true, new)
                self.activate_block(new)
                self.process_conditional(e.right, true, false)
        elif isinstance(e, UnaryExpr) and e.op == 'not':
            self.process_conditional(e.expr, false, true)
        # Catch-all for arbitrary expressions.
        else:
            reg = self.accept(e)
            self.add_bool_branch(reg, true, false)

    def visit_basic_comparison(self, op: str, left: Value, right: Value, line: int) -> Value:
        negate = False
        if op == 'is not':
            op, negate = 'is', True
        elif op == 'not in':
            op, negate = 'in', True

        target = self.binary_op(left, right, op, line)

        if negate:
            target = self.unary_op(target, 'not', line)
        return target

    def visit_comparison_expr(self, e: ComparisonExpr) -> Value:
        # TODO: Don't produce an expression when used in conditional context

        # All of the trickiness here is due to support for chained conditionals
        # (`e1 < e2 > e3`, etc). `e1 < e2 > e3` is approximately equivalent to
        # `e1 < e2 and e2 > e3` except that `e2` is only evaluated once.
        expr_type = self.node_type(e)

        # go(i, prev) generates code for `ei opi e{i+1} op{i+1} ... en`,
        # assuming that prev contains the value of `ei`.
        def go(i: int, prev: Value) -> Value:
            if i == len(e.operators) - 1:
                return self.visit_basic_comparison(
                    e.operators[i], prev, self.accept(e.operands[i + 1]), e.line)

            next = self.accept(e.operands[i + 1])
            return self.shortcircuit_helper(
                'and', expr_type,
                lambda: self.visit_basic_comparison(
                    e.operators[i], prev, next, e.line),
                lambda: go(i + 1, next),
                e.line)

        return go(0, self.accept(e.operands[0]))

    def add_bool_branch(self, value: Value, true: BasicBlock, false: BasicBlock) -> None:
        if is_same_type(value.type, int_rprimitive):
            zero = self.add(LoadInt(0))
            value = self.binary_op(value, zero, '!=', value.line)
        elif is_same_type(value.type, list_rprimitive):
            length = self.primitive_op(list_len_op, [value], value.line)
            zero = self.add(LoadInt(0))
            value = self.binary_op(length, zero, '!=', value.line)
        else:
            value_type = optional_value_type(value.type)
            if value_type is not None:
                is_none = self.binary_op(value, self.none(), 'is not', value.line)
                branch = Branch(is_none, true, false, Branch.BOOL_EXPR)
                self.add(branch)
                if isinstance(value_type, RInstance) and not value_type.class_ir.has_bool:
                    # Optional[X] where X is always truthy
                    pass
                else:
                    # Optional[X] where X may be falsey and requires a check
                    branch.true = self.new_block()
                    # unbox_or_cast instead of coerce because we want the
                    # type to change even if it is a subtype.
                    remaining = self.unbox_or_cast(value, value_type, value.line)
                    self.add_bool_branch(remaining, true, false)
                return
            elif not is_same_type(value.type, bool_rprimitive):
                value = self.primitive_op(bool_op, [value], value.line)
        self.add(Branch(value, true, false, Branch.BOOL_EXPR))

    def visit_nonlocal_decl(self, o: NonlocalDecl) -> None:
        pass

    def visit_slice_expr(self, expr: SliceExpr) -> Value:
        def get_arg(arg: Optional[Expression]) -> Value:
            if arg is None:
                return self.none()
            else:
                return self.accept(arg)

        args = [get_arg(expr.begin_index),
                get_arg(expr.end_index),
                get_arg(expr.stride)]
        return self.primitive_op(new_slice_op, args, expr.line)

    def visit_raise_stmt(self, s: RaiseStmt) -> None:
        if s.expr is None:
            self.primitive_op(reraise_exception_op, [], NO_TRACEBACK_LINE_NO)
            self.add(Unreachable())
            return

        exc = self.accept(s.expr)
        self.primitive_op(raise_exception_op, [exc], s.line)
        self.add(Unreachable())

    class ExceptNonlocalControl(CleanupNonlocalControl):
        """Nonlocal control for except blocks.

        Just makes sure that sys.exc_info always gets restored when we leave.
        This is super annoying.
        """
        def __init__(self, outer: NonlocalControl, saved: Value) -> None:
            super().__init__(outer)
            self.saved = saved

        def gen_cleanup(self, builder: 'IRBuilder') -> None:
            # Don't bother plumbing a line through because it can't fail
            builder.primitive_op(restore_exc_info_op, [self.saved], -1)

    def visit_try_except(self,
                         body: GenFunc,
                         handlers: Sequence[
                             Tuple[Optional[Expression], Optional[Expression], GenFunc]],
                         else_body: Optional[GenFunc],
                         line: int) -> None:
        """Generalized try/except/else handling that takes functions to gen the bodies.

        The point of this is to also be able to support with."""
        assert handlers, "try needs except"

        except_entry, exit_block, cleanup_block = BasicBlock(), BasicBlock(), BasicBlock()
        double_except_block = BasicBlock()
        # If there is an else block, jump there after the try, otherwise just leave
        else_block = BasicBlock() if else_body else exit_block

        # Compile the try block with an error handler
        self.error_handlers.append(except_entry)
        self.goto_and_activate(BasicBlock())
        body()
        self.goto(else_block)
        self.error_handlers.pop()

        # The error handler catches the error and then checks it
        # against the except clauses. We compile the error handler
        # itself with an error handler so that it can properly restore
        # the *old* exc_info if an exception occurs.
        # The exception chaining will be done automatically when the
        # exception is raised, based on the exception in exc_info.
        self.error_handlers.append(double_except_block)
        self.activate_block(except_entry)
        old_exc = self.primitive_op(error_catch_op, [], line)
        # Compile the except blocks with the nonlocal control flow overridden to clear exc_info
        self.nonlocal_control.append(
            IRBuilder.ExceptNonlocalControl(self.nonlocal_control[-1], old_exc))

        # Process the bodies
        next_block = None
        for type, var, handler_body in handlers:
            if type:
                next_block, body_block = BasicBlock(), BasicBlock()
                matches = self.primitive_op(exc_matches_op, [self.accept(type)], type.line)
                self.add(Branch(matches, body_block, next_block, Branch.BOOL_EXPR))
                self.activate_block(body_block)
            if var:
                target = self.get_assignment_target(var)
                self.assign(target, self.primitive_op(get_exc_value_op, [], var.line), var.line)
            handler_body()
            self.goto(cleanup_block)
            if next_block:
                self.activate_block(next_block)

        # Reraise the exception if needed
        if next_block:
            self.primitive_op(reraise_exception_op, [], NO_TRACEBACK_LINE_NO)
            self.add(Unreachable())

        self.nonlocal_control.pop()
        self.error_handlers.pop()

        # Cleanup for if we leave except through normal control flow:
        # restore the saved exc_info information and continue propagating
        # the exception if it exists.
        self.activate_block(cleanup_block)
        self.primitive_op(restore_exc_info_op, [old_exc], line)
        self.goto(exit_block)

        # Cleanup for if we leave except through a raised exception:
        # restore the saved exc_info information and continue propagating
        # the exception.
        self.activate_block(double_except_block)
        self.primitive_op(restore_exc_info_op, [old_exc], line)
        self.primitive_op(keep_propagating_op, [], NO_TRACEBACK_LINE_NO)
        self.add(Unreachable())

        # If present, compile the else body in the obvious way
        if else_body:
            self.activate_block(else_block)
            else_body()
            self.goto(exit_block)

        self.activate_block(exit_block)

    def visit_try_except_stmt(self, t: TryStmt) -> None:
        def body() -> None:
            self.accept(t.body)

        # Work around scoping woes
        def make_handler(body: Block) -> GenFunc:
            return lambda: self.accept(body)

        handlers = [(type, var, make_handler(body)) for type, var, body in
                    zip(t.types, t.vars, t.handlers)]
        else_body = (lambda: self.accept(t.else_body)) if t.else_body else None
        self.visit_try_except(body, handlers, else_body, t.line)

    class TryFinallyNonlocalControl(NonlocalControl):
        def __init__(self, target: BasicBlock) -> None:
            self.target = target
            self.ret_reg = None  # type: Optional[Register]

        def gen_break(self, builder: 'IRBuilder') -> None:
            assert False, "unimplemented"

        def gen_continue(self, builder: 'IRBuilder') -> None:
            assert False, "unimplemented"

        def gen_return(self, builder: 'IRBuilder', value: Value) -> None:
            if self.ret_reg is None:
                self.ret_reg = builder.alloc_temp(builder.ret_types[-1])

            builder.add(Assign(self.ret_reg, value))
            builder.add(Goto(self.target))

    class FinallyNonlocalControl(CleanupNonlocalControl):
        """Nonlocal control for finally blocks.

        Just makes sure that sys.exc_info always gets restored when we
        leave and the return register is decrefed if it isn't null.
        """
        def __init__(self, outer: NonlocalControl, ret_reg: Optional[Value], saved: Value) -> None:
            super().__init__(outer)
            self.ret_reg = ret_reg
            self.saved = saved

        def gen_cleanup(self, builder: 'IRBuilder') -> None:
            # Do an error branch on the return value register, which
            # may be undefined. This will allow it to be properly
            # decrefed if it is not null. This is kind of a hack.
            if self.ret_reg:
                target = BasicBlock()
                builder.add(Branch(self.ret_reg, target, target, Branch.IS_ERROR))
                builder.activate_block(target)

            # Restore the old exc_info
            # Don't bother plumbing a line through because it can't fail
            target, cleanup = BasicBlock(), BasicBlock()
            builder.add(Branch(self.saved, target, cleanup, Branch.IS_ERROR))
            builder.activate_block(cleanup)
            builder.primitive_op(restore_exc_info_op, [self.saved], -1)
            builder.goto_and_activate(target)

    def try_finally_try(self, err_handler: BasicBlock, return_entry: BasicBlock,
                        main_entry: BasicBlock, try_body: GenFunc) -> Optional[Register]:
        # Compile the try block with an error handler
        control = IRBuilder.TryFinallyNonlocalControl(return_entry)
        self.error_handlers.append(err_handler)

        self.nonlocal_control.append(control)
        self.goto_and_activate(BasicBlock())
        try_body()
        self.goto(main_entry)
        self.nonlocal_control.pop()
        self.error_handlers.pop()

        return control.ret_reg

    def try_finally_entry_blocks(self,
                                 err_handler: BasicBlock, return_entry: BasicBlock,
                                 main_entry: BasicBlock, finally_block: BasicBlock,
                                 ret_reg: Optional[Register]) -> Value:
        old_exc = self.alloc_temp(exc_rtuple)

        # Entry block for non-exceptional flow
        self.activate_block(main_entry)
        if ret_reg:
            self.add(Assign(ret_reg, self.add(LoadErrorValue(self.ret_types[-1]))))
        self.goto(return_entry)

        self.activate_block(return_entry)
        self.add(Assign(old_exc, self.add(LoadErrorValue(exc_rtuple))))
        self.goto(finally_block)

        # Entry block for errors
        self.activate_block(err_handler)
        if ret_reg:
            self.add(Assign(ret_reg, self.add(LoadErrorValue(self.ret_types[-1]))))
        self.add(Assign(old_exc, self.primitive_op(error_catch_op, [], -1)))
        self.goto(finally_block)

        return old_exc

    def try_finally_body(
            self, finally_block: BasicBlock, finally_body: GenFunc,
            ret_reg: Optional[Value], old_exc: Value) -> Tuple[BasicBlock, FinallyNonlocalControl]:
        cleanup_block = BasicBlock()
        # Compile the finally block with the nonlocal control flow overridden to restore exc_info
        self.error_handlers.append(cleanup_block)
        finally_control = IRBuilder.FinallyNonlocalControl(
            self.nonlocal_control[-1], ret_reg, old_exc)
        self.nonlocal_control.append(finally_control)
        self.activate_block(finally_block)
        finally_body()
        self.nonlocal_control.pop()

        return cleanup_block, finally_control

    def try_finally_resolve_control(self, cleanup_block: BasicBlock,
                                    finally_control: FinallyNonlocalControl,
                                    old_exc: Value, ret_reg: Optional[Value]) -> BasicBlock:
        """Resolve the control flow out of a finally block.

        This means returning if there was a return, propagating
        exceptions, break/continue (soon), or just continuing on.
        """
        reraise, rest = BasicBlock(), BasicBlock()
        self.add(Branch(old_exc, rest, reraise, Branch.IS_ERROR))

        # Reraise the exception if there was one
        self.activate_block(reraise)
        self.primitive_op(reraise_exception_op, [], NO_TRACEBACK_LINE_NO)
        self.add(Unreachable())
        self.error_handlers.pop()

        # If there was a return, keep returning
        if ret_reg:
            self.activate_block(rest)
            return_block, rest = BasicBlock(), BasicBlock()
            self.add(Branch(ret_reg, rest, return_block, Branch.IS_ERROR))

            self.activate_block(return_block)
            self.nonlocal_control[-1].gen_return(self, ret_reg)

        # TODO: handle break/continue
        self.activate_block(rest)
        out_block = BasicBlock()
        self.goto(out_block)

        # If there was an exception, restore again
        self.activate_block(cleanup_block)
        finally_control.gen_cleanup(self)
        self.primitive_op(keep_propagating_op, [], NO_TRACEBACK_LINE_NO)
        self.add(Unreachable())

        return out_block

    def visit_try_finally_stmt(self, try_body: GenFunc, finally_body: GenFunc) -> None:
        """Generalized try/finally handling that takes functions to gen the bodies.

        The point of this is to also be able to support with."""
        # Finally is a big pain, because there are so many ways that
        # exits can occur. We emit 10+ basic blocks for every finally!

        err_handler, main_entry, return_entry, finally_block = (
            BasicBlock(), BasicBlock(), BasicBlock(), BasicBlock())

        # Compile the body of the try
        ret_reg = self.try_finally_try(
            err_handler, return_entry, main_entry, try_body)

        # Set up the entry blocks for the finally statement
        old_exc = self.try_finally_entry_blocks(
            err_handler, return_entry, main_entry, finally_block, ret_reg)

        # Compile the body of the finally
        cleanup_block, finally_control = self.try_finally_body(
            finally_block, finally_body, ret_reg, old_exc)

        # Resolve the control flow out of the finally block
        out_block = self.try_finally_resolve_control(
            cleanup_block, finally_control, old_exc, ret_reg)

        self.activate_block(out_block)

    def visit_try_stmt(self, t: TryStmt) -> None:
        # Our compilation strategy for try/except/else/finally is to
        # treat try/except/else and try/finally as separate language
        # constructs that we compile separately. When we have a
        # try/except/else/finally, we treat the try/except/else as the
        # body of a try/finally block.
        if t.finally_body:
            def visit_try_body() -> None:
                if t.handlers:
                    self.visit_try_except_stmt(t)
                else:
                    self.accept(t.body)
            body = t.finally_body

            self.visit_try_finally_stmt(visit_try_body, lambda: self.accept(body))
        else:
            self.visit_try_except_stmt(t)

    def get_sys_exc_info(self) -> List[Value]:
        exc_info = self.primitive_op(get_exc_info_op, [], -1)
        return [self.add(TupleGet(exc_info, i, -1)) for i in range(3)]

    def visit_with(self, expr: Expression, target: Optional[Lvalue],
                   body: GenFunc, line: int) -> None:

        # This is basically a straight transcription of the Python code in PEP 343.
        # I don't actually understand why a bunch of it is the way it is.
        # We could probably optimize the case where the manager is compiled by us,
        # but that is not our common case at all, so.
        mgr_v = self.accept(expr)
        typ = self.primitive_op(type_op, [mgr_v], line)
        exit_ = self.maybe_spill(self.py_get_attr(typ, '__exit__', line))
        value = self.py_call(self.py_get_attr(typ, '__enter__', line), [mgr_v], line)
        mgr = self.maybe_spill(mgr_v)
        exc = self.maybe_spill_assignable(self.primitive_op(true_op, [], -1))

        def try_body() -> None:
            if target:
                self.assign(self.get_assignment_target(target), value, line)
            body()

        def except_body() -> None:
            self.assign(exc, self.primitive_op(false_op, [], -1), line)
            out_block, reraise_block = BasicBlock(), BasicBlock()
            self.add_bool_branch(self.py_call(self.read(exit_),
                                              [self.read(mgr)] + self.get_sys_exc_info(), line),
                                 out_block, reraise_block)
            self.activate_block(reraise_block)
            self.primitive_op(reraise_exception_op, [], NO_TRACEBACK_LINE_NO)
            self.add(Unreachable())
            self.activate_block(out_block)

        def finally_body() -> None:
            out_block, exit_block = BasicBlock(), BasicBlock()
            self.add(Branch(self.read(exc), exit_block, out_block, Branch.BOOL_EXPR))
            self.activate_block(exit_block)
            none = self.none()
            self.py_call(self.read(exit_), [self.read(mgr), none, none, none], line)
            self.goto_and_activate(out_block)

        self.visit_try_finally_stmt(
            lambda: self.visit_try_except(try_body, [(None, None, except_body)], None, line),
            finally_body)

    def visit_with_stmt(self, o: WithStmt) -> None:
        # Generate separate logic for each expr in it, left to right
        def generate(i: int) -> None:
            if i >= len(o.expr):
                self.accept(o.body)
            else:
                self.visit_with(o.expr[i], o.target[i], lambda: generate(i + 1), o.line)

        generate(0)

    def visit_lambda_expr(self, expr: LambdaExpr) -> Value:
        typ = self.types[expr]
        assert isinstance(typ, CallableType)

        runtime_args = []
        for arg, arg_type in zip(expr.arguments, typ.arg_types):
            arg.variable.type = arg_type
            runtime_args.append(RuntimeArg(arg.variable.name(), self.type_to_rtype(arg_type)))
        ret_type = self.type_to_rtype(typ.ret_type)

        fsig = FuncSignature(runtime_args, ret_type)

        fname = '{}{}'.format(LAMBDA_NAME, self.lambda_counter)
        func_ir, func_reg = self.gen_func_item(expr, fname, fsig)
        assert func_reg is not None

        self.functions.append(func_ir)
        return func_reg

    def visit_pass_stmt(self, o: PassStmt) -> None:
        pass

    def visit_global_decl(self, o: GlobalDecl) -> None:
        # Pure declaration -- no runtime effect
        pass

    def visit_assert_stmt(self, a: AssertStmt) -> None:
        cond = self.accept(a.expr)
        ok_block, error_block = BasicBlock(), BasicBlock()
        self.add_bool_branch(cond, ok_block, error_block)
        self.activate_block(error_block)
        if a.msg is None:
            # Special case (for simpler generated code)
            self.add(RaiseStandardError(RaiseStandardError.ASSERTION_ERROR, None, a.line))
        elif isinstance(a.msg, StrExpr):
            # Another special case
            self.add(RaiseStandardError(RaiseStandardError.ASSERTION_ERROR, a.msg.value,
                                        a.line))
        else:
            # The general case -- explicitly construct an exception instance
            message = self.accept(a.msg)
            exc_type = self.load_module_attr_by_fullname('builtins.AssertionError', a.line)
            exc = self.py_call(exc_type, [message], a.line)
            self.primitive_op(raise_exception_op, [exc], a.line)
        self.add(Unreachable())
        self.activate_block(ok_block)

    def visit_cast_expr(self, o: CastExpr) -> Value:
        assert False, "CastExpr handled in CallExpr"

    def visit_list_comprehension(self, o: ListComprehension) -> Value:
        gen = o.generator
        list_ops = self.primitive_op(new_list_op, [], o.line)
        loop_params = list(zip(gen.indices, gen.sequences, gen.condlists))

        def gen_inner_stmts() -> None:
            e = self.accept(gen.left_expr)
            self.primitive_op(list_append_op, [list_ops, e], o.line)

        self.comprehension_helper(loop_params, gen_inner_stmts, o.line)
        return list_ops

    def visit_set_comprehension(self, o: SetComprehension) -> Value:
        gen = o.generator
        set_ops = self.primitive_op(new_set_op, [], o.line)
        loop_params = list(zip(gen.indices, gen.sequences, gen.condlists))

        def gen_inner_stmts() -> None:
            e = self.accept(gen.left_expr)
            self.primitive_op(set_add_op, [set_ops, e], o.line)

        self.comprehension_helper(loop_params, gen_inner_stmts, o.line)
        return set_ops

    def visit_dictionary_comprehension(self, o: DictionaryComprehension) -> Value:
        d = self.primitive_op(new_dict_op, [], o.line)
        loop_params = list(zip(o.indices, o.sequences, o.condlists))

        def gen_inner_stmts() -> None:
            k = self.accept(o.key)
            v = self.accept(o.value)
            self.primitive_op(dict_set_item_op, [d, k, v], o.line)

        self.comprehension_helper(loop_params, gen_inner_stmts, o.line)
        return d

    def visit_generator_expr(self, o: GeneratorExpr) -> Value:
        print('{}:{}: Warning: treating generator comprehension as list'.format(
            self.module_path, o.line))

        gen = o
        list_ops = self.primitive_op(new_list_op, [], o.line)
        loop_params = list(zip(gen.indices, gen.sequences, gen.condlists))

        def gen_inner_stmts() -> None:
            e = self.accept(gen.left_expr)
            self.primitive_op(list_append_op, [list_ops, e], o.line)

        self.comprehension_helper(loop_params, gen_inner_stmts, o.line)
        return list_ops

    def comprehension_helper(self,
                             loop_params: List[Tuple[Lvalue, Expression, List[Expression]]],
                             gen_inner_stmts: Callable[[], None],
                             line: int) -> None:
        """Helper function for list comprehensions.

        "loop_params" is a list of (index, expr, [conditions]) tuples defining nested loops:
            - "index" is the Lvalue indexing that loop;
            - "expr" is the expression for the object to be iterated over;
            - "conditions" is a list of conditions, evaluated in order with short-circuiting,
                that must all be true for the loop body to be executed
        "gen_inner_stmts" is a function to generate the IR for the body of the innermost loop
        """
        def handle_loop(loop_params: List[Tuple[Lvalue, Expression, List[Expression]]]) -> None:
            """Generate IR for a loop.

            Given a list of (index, expression, [conditions]) tuples, generate IR
            for the nested loops the list defines.
            """
            index, expr, conds = loop_params[0]
            self.for_loop_helper(index, expr,
                                 lambda: loop_contents(conds, loop_params[1:]),
                                 None, line)

        def loop_contents(
                conds: List[Expression],
                remaining_loop_params: List[Tuple[Lvalue, Expression, List[Expression]]],
        ) -> None:
            """Generate the body of the loop.

            "conds" is a list of conditions to be evaluated (in order, with short circuiting)
                to gate the body of the loop.
            "remaining_loop_params" is the parameters for any further nested loops; if it's empty
                we'll instead evaluate the "gen_inner_stmts" function.
            """
            # Check conditions, in order, short circuiting them.
            for cond in conds:
                cond_val = self.accept(cond)
                cont_block, rest_block = BasicBlock(), BasicBlock()
                # If the condition is true we'll skip the continue.
                self.add_bool_branch(cond_val, rest_block, cont_block)
                self.activate_block(cont_block)
                self.nonlocal_control[-1].gen_continue(self)
                self.goto_and_activate(rest_block)

            if remaining_loop_params:
                # There's another nested level, so the body of this loop is another loop.
                return handle_loop(remaining_loop_params)
            else:
                # We finally reached the actual body of the generator.
                # Generate the IR for the inner loop body.
                gen_inner_stmts()

        handle_loop(loop_params)

    def visit_del_stmt(self, o: DelStmt) -> None:
        if isinstance(o.expr, TupleExpr):
            for expr_item in o.expr.items:
                self.visit_del_item(expr_item)
        else:
            self.visit_del_item(o.expr)

    def visit_del_item(self, expr: Expression) -> None:
        if isinstance(expr, IndexExpr):
            base_reg = self.accept(expr.base)
            index_reg = self.accept(expr.index)
            self.translate_special_method_call(
                base_reg,
                '__delitem__',
                [index_reg],
                result_type=None,
                line=expr.line
            )
        elif isinstance(expr, MemberExpr):
            base_reg = self.accept(expr.expr)
            key = self.load_static_unicode(expr.name)
            self.add(PrimitiveOp([base_reg, key], py_delattr_op, expr.line))
        else:
            assert False, 'Unsupported del operation'

    def visit_super_expr(self, o: SuperExpr) -> Value:
        sup_val = self.load_module_attr_by_fullname('builtins.super', o.line)
        if o.call.args:
            args = [self.accept(arg) for arg in o.call.args]
        else:
            assert o.info is not None
            typ = self.load_native_type_object(o.info.fullname())
            vself = next(iter(self.environment.indexes))  # grab first argument
            args = [typ, vself]
        res = self.py_call(sup_val, args, o.line)
        return self.py_get_attr(res, o.name, o.line)

    def visit_yield_expr(self, expr: YieldExpr) -> Value:
        self.goto_new_block()
        if expr.expr:
            retval = self.accept(expr.expr)
            retval = self.coerce(retval, self.ret_types[-1], expr.line)
        else:
            retval = self.none()

        cls = self.fn_info.generator_class
        # Create a new block for the instructions immediately following the yield expression, and
        # set the next label so that the next time '__next__' is called on the generator object,
        # the function continues at the new block.
        next_block = BasicBlock()
        next_label = len(cls.blocks)
        cls.blocks.append(next_block)
        self.assign(cls.next_label_target, self.add(LoadInt(next_label)), expr.line)
        self.add(Return(retval))
        self.activate_block(next_block)

        self.add_raise_exception_blocks_to_generator_class(expr.line)

        # TODO: Replace this value with the value that is sent into the generator when we support
        #       the 'send' function.
        return self.none()

    def visit_ellipsis(self, o: EllipsisExpr) -> Value:
        return self.primitive_op(ellipsis_op, [], o.line)

    # Unimplemented constructs
    # TODO: some of these are actually things that should never show up,
    # so properly sort those out.

    def visit__promote_expr(self, o: PromoteExpr) -> Value:
        raise NotImplementedError

    def visit_await_expr(self, o: AwaitExpr) -> Value:
        raise NotImplementedError

    def visit_backquote_expr(self, o: BackquoteExpr) -> Value:
        raise NotImplementedError

    def visit_complex_expr(self, o: ComplexExpr) -> Value:
        raise NotImplementedError

    def visit_decorator(self, o: Decorator) -> None:
        raise NotImplementedError

    def visit_enum_call_expr(self, o: EnumCallExpr) -> Value:
        raise NotImplementedError

    def visit_exec_stmt(self, o: ExecStmt) -> None:
        raise NotImplementedError

    def visit_namedtuple_expr(self, o: NamedTupleExpr) -> Value:
        raise NotImplementedError

    def visit_newtype_expr(self, o: NewTypeExpr) -> Value:
        raise NotImplementedError

    def visit_overloaded_func_def(self, o: OverloadedFuncDef) -> None:
        raise NotImplementedError

    def visit_print_stmt(self, o: PrintStmt) -> None:
        raise NotImplementedError

    def visit_reveal_expr(self, o: RevealExpr) -> Value:
        raise NotImplementedError

    def visit_star_expr(self, o: StarExpr) -> Value:
        raise NotImplementedError

    def visit_temp_node(self, o: TempNode) -> Value:
        raise NotImplementedError

    def visit_type_alias_expr(self, o: TypeAliasExpr) -> Value:
        raise NotImplementedError

    def visit_type_application(self, o: TypeApplication) -> Value:
        raise NotImplementedError

    def visit_type_var_expr(self, o: TypeVarExpr) -> Value:
        raise NotImplementedError

    def visit_typeddict_expr(self, o: TypedDictExpr) -> Value:
        raise NotImplementedError

    def visit_unicode_expr(self, o: UnicodeExpr) -> Value:
        raise NotImplementedError

    def visit_var(self, o: Var) -> None:
        raise NotImplementedError

    def visit_yield_from_expr(self, o: YieldFromExpr) -> Value:
        raise NotImplementedError

    # Helpers

    def enter(self, fn_info: FuncInfo) -> None:
        self.environment = Environment(fn_info.name)
        self.environments.append(self.environment)
        self.fn_info = fn_info
        self.fn_infos.append(self.fn_info)
        self.ret_types.append(none_rprimitive)
        self.error_handlers.append(None)
        if fn_info.is_generator:
            self.nonlocal_control.append(GeneratorNonlocalControl())
        else:
            self.nonlocal_control.append(BaseNonlocalControl())
        self.blocks.append([])
        self.new_block()

    def activate_block(self, block: BasicBlock) -> None:
        block.error_handler = self.error_handlers[-1]
        self.blocks[-1].append(block)

    def goto_and_activate(self, block: BasicBlock) -> None:
        self.goto(block)
        self.activate_block(block)

    def new_block(self) -> BasicBlock:
        block = BasicBlock()
        self.activate_block(block)
        return block

    def goto_new_block(self) -> BasicBlock:
        block = BasicBlock()
        self.goto_and_activate(block)
        return block

    def leave(self) -> Tuple[List[BasicBlock], Environment, RType, FuncInfo]:
        blocks = self.blocks.pop()
        env = self.environments.pop()
        ret_type = self.ret_types.pop()
        fn_info = self.fn_infos.pop()
        self.error_handlers.pop()
        self.nonlocal_control.pop()
        self.environment = self.environments[-1]
        self.fn_info = self.fn_infos[-1]
        return blocks, env, ret_type, fn_info

    def add(self, op: Op) -> Value:
        if self.blocks[-1][-1].ops:
            assert not isinstance(self.blocks[-1][-1].ops[-1], ControlOp), (
                "Can't add to finished block")

        self.blocks[-1][-1].ops.append(op)
        if isinstance(op, RegisterOp):
            self.environment.add_op(op)
        return op

    def goto(self, target: BasicBlock) -> None:
        if not self.blocks[-1][-1].ops or not isinstance(self.blocks[-1][-1].ops[-1], ControlOp):
            self.add(Goto(target))

    def primitive_op(self, desc: OpDescription, args: List[Value], line: int) -> Value:
        assert desc.result_type is not None
        coerced = []
        for i, arg in enumerate(args):
            formal_type = self.op_arg_type(desc, i)
            arg = self.coerce(arg, formal_type, line)
            coerced.append(arg)
        target = self.add(PrimitiveOp(coerced, desc, line))
        return target

    def op_arg_type(self, desc: OpDescription, n: int) -> RType:
        if n >= len(desc.arg_types):
            assert desc.is_var_arg
            return desc.arg_types[-1]
        return desc.arg_types[n]

    @overload
    def accept(self, node: Expression) -> Value: ...

    @overload
    def accept(self, node: Statement) -> None: ...

    def accept(self, node: Union[Statement, Expression]) -> Optional[Value]:
        with self.catch_errors(node.line):
            if isinstance(node, Expression):
                res = node.accept(self)
                res = self.coerce(res, self.node_type(node), node.line)
                return res
            else:
                node.accept(self)
                return None

    def alloc_temp(self, type: RType) -> Register:
        return self.environment.add_temp(type)

    def type_to_rtype(self, typ: Type) -> RType:
        return self.mapper.type_to_rtype(typ)

    def node_type(self, node: Expression) -> RType:
        if isinstance(node, IntExpr):
            # TODO: Don't special case IntExpr
            return int_rprimitive
        if node not in self.types:
            return object_rprimitive
        mypy_type = self.types[node]
        return self.type_to_rtype(mypy_type)

    def box(self, src: Value) -> Value:
        if src.type.is_unboxed:
            return self.add(Box(src))
        else:
            return src

    def unbox_or_cast(self, src: Value, target_type: RType, line: int) -> Value:
        if target_type.is_unboxed:
            return self.add(Unbox(src, target_type, line))
        else:
            return self.add(Cast(src, target_type, line))

    def box_expr(self, expr: Expression) -> Value:
        return self.box(self.accept(expr))

    def make_dict(self, key_value_pairs: List[Tuple[Value, Value]], line: int) -> Value:
        dict_reg = self.add(PrimitiveOp([], new_dict_op, line))
        for key, value in key_value_pairs:
            self.translate_special_method_call(
                dict_reg,
                '__setitem__',
                [key, value],
                result_type=None,
                line=line)
        return dict_reg

    def none(self) -> Value:
        return self.add(PrimitiveOp([], none_op, line=-1))

    def load_outer_env(self, base: Value, outer_env: Environment) -> Value:
        """Loads the environment class for a given base into a register.

        Additionally, iterates through all of the SymbolNode and AssignmentTarget instances of the
        environment at the given index's symtable, and adds those instances to the environment of
        the current environment. This is done so that the current environment can access outer
        environment variables without having to reload all of the environment registers.

        Returns the register where the environment class was loaded.
        """
        env = self.add(GetAttr(base, ENV_ATTR_NAME, self.fn_info.fitem.line))
        assert isinstance(env.type, RInstance), '{} must be of type RInstance'.format(env)

        for symbol, target in outer_env.symtable.items():
            env.type.class_ir.attributes[symbol.name()] = target.type
            symbol_target = AssignmentTargetAttr(env, symbol.name())
            self.environment.add_target(symbol, symbol_target)

        return env

    def load_outer_envs(self, base: ImplicitClass) -> None:
        index = len(self.environments) - 2

        # Load the first outer environment. This one is special because it gets saved in the
        # FuncInfo instance's prev_env_reg field.
        if index > 1:
            # outer_env = self.fn_infos[index].environment
            outer_env = self.environments[index]
            if isinstance(base, GeneratorClass):
                base.prev_env_reg = self.load_outer_env(base.curr_env_reg, outer_env)
            else:
                base.prev_env_reg = self.load_outer_env(base.self_reg, outer_env)
            env_reg = base.prev_env_reg
            index -= 1

        # Load the remaining outer environments into registers.
        while index > 1:
            # outer_env = self.fn_infos[index].environment
            outer_env = self.environments[index]
            env_reg = self.load_outer_env(env_reg, outer_env)
            index -= 1

    def load_env_registers(self) -> None:
        """Loads the registers for a given FuncDef.

        Adds the arguments of the FuncDef to the environment. If the FuncDef is nested inside of
        another function, then this also loads all of the outer environments of the FuncDef into
        registers so that they can be used when accessing free variables.
        """
        self.add_args_to_env(local=True)
        if self.fn_info.is_nested:
            self.load_outer_envs(self.fn_info.callable_class)

    def add_var_to_env_class(self,
                             var: SymbolNode,
                             rtype: RType,
                             base: Union[FuncInfo, ImplicitClass],
                             reassign: bool = False) -> AssignmentTarget:
        # First, define the variable name as an attribute of the environment class, and then
        # construct a target for that attribute.
        self.fn_info.env_class.attributes[var.name()] = rtype
        attr_target = AssignmentTargetAttr(base.curr_env_reg, var.name())

        if reassign:
            # Read the local definition of the variable, and set the corresponding attribute of
            # the environment class' variable to be that value.
            reg = self.read(self.environment.lookup(var), self.fn_info.fitem.line)
            self.add(SetAttr(base.curr_env_reg, var.name(), reg, self.fn_info.fitem.line))

        # Override the local definition of the variable to instead point at the variable in
        # the environment class.
        return self.environment.add_target(var, attr_target)

    def setup_env_for_generator_class(self) -> None:
        """Populates the environment for a generator class."""
        fitem = self.fn_info.fitem
        cls = self.fn_info.generator_class
        self_target = self.add_self_to_env(cls.ir)

        # Add the type, value, and traceback variables to the environment.

        exc_type = self.environment.add_local(Var('type'), object_rprimitive, is_arg=True)
        exc_val = self.environment.add_local(Var('value'), object_rprimitive, is_arg=True)
        exc_tb = self.environment.add_local(Var('traceback'), object_rprimitive, is_arg=True)

        cls.exc_regs = (exc_type, exc_val, exc_tb)

        cls.self_reg = self.read(self_target, fitem.line)
        cls.curr_env_reg = self.load_outer_env(cls.self_reg, self.environment)

        # Define a variable representing the label to go to the next time the '__next__' function
        # of the generator is called, and add it as an attribute to the environment class.
        cls.next_label_target = self.add_var_to_env_class(Var(NEXT_LABEL_ATTR_NAME),
                                                          int_rprimitive,
                                                          cls,
                                                          reassign=False)

        # Add arguments from the original generator function to the generator class' environment.
        self.add_args_to_env(local=False, base=cls, reassign=False)

        # Set the next label register for the generator class.
        cls.next_label_reg = self.read(cls.next_label_target, fitem.line)

    def add_args_to_env(self, local: bool = True,
                        base: Optional[Union[FuncInfo, ImplicitClass]] = None,
                        reassign: bool = True) -> None:
        fn_info = self.fn_info
        if local:
            for arg in fn_info.fitem.arguments:
                assert arg.variable.type, "Function argument missing type"
                rtype = self.type_to_rtype(arg.variable.type)
                self.environment.add_local_reg(arg.variable, rtype, is_arg=True)
        else:
            for arg in fn_info.fitem.arguments:
                assert arg.variable.type, "Function argument missing type"
                if self.is_free_variable(arg.variable) or fn_info.is_generator:
                    rtype = self.type_to_rtype(arg.variable.type)
                    assert base is not None, 'base cannot be None for adding nonlocal args'
                    self.add_var_to_env_class(arg.variable, rtype, base, reassign=reassign)

    def gen_func_ns(self) -> str:
        """Generates a namespace for a nested function using its outer function names."""
        return '_'.join(env.name for env in self.environments
                        if env.name and env.name != '<top level>')

    def setup_callable_class(self) -> None:
        """Generates a callable class representing a nested function and sets up the 'self'
        variable for that class.

        This takes the most recently visited function and returns a ClassIR to represent that
        function. Each callable class contains an environment attribute with points to another
        ClassIR representing the environment class where some of its variables can be accessed.
        Note that its '__call__' method is not yet implemented, and is implemented in the
        add_call_to_callable_class function.

        Returns a newly constructed ClassIR representing the callable class for the nested
        function.
        """

        # Check to see that the name has not already been taken. If so, rename the class. We allow
        # multiple uses of the same function name because this is valid in if-else blocks. Example:
        #     if True:
        #         def foo():          ---->    foo_obj()
        #             return True
        #     else:
        #         def foo():          ---->    foo_obj_0()
        #             return False
        name = '{}_{}_obj'.format(self.fn_info.name, self.fn_info.ns)
        count = 0
        while name in self.callable_class_names:
            name += '_' + str(count)
        self.callable_class_names.add(name)

        # Define the actual callable class ClassIR, and set its environment to point at the
        # previously defined environment class.
        callable_class_ir = ClassIR(name, self.module_name, is_generated=True)
        callable_class_ir.attributes[ENV_ATTR_NAME] = RInstance(self.fn_infos[-2].env_class)
        callable_class_ir.mro = [callable_class_ir]
        self.fn_info.callable_class = ImplicitClass(callable_class_ir)
        self.classes.append(callable_class_ir)

        # Add a 'self' variable to the callable class' environment, and store that variable in a
        # register to be accessed later.
        self_target = self.add_self_to_env(callable_class_ir)
        self.fn_info.callable_class.self_reg = self.read(self_target, self.fn_info.fitem.line)

    def add_call_to_callable_class(self,
                                   blocks: List[BasicBlock],
                                   sig: FuncSignature,
                                   env: Environment,
                                   fn_info: FuncInfo) -> FuncIR:
        """Generates a '__call__' method for a callable class representing a nested function.

        This takes the blocks, signature, and environment associated with a function definition and
        uses those to build the '__call__' method of a given callable class, used to represent that
        function. Note that a 'self' parameter is added to its list of arguments, as the nested
        function becomes a class method.
        """
        sig = FuncSignature((RuntimeArg('self', object_rprimitive),) + sig.args, sig.ret_type)
        call_fn_decl = FuncDecl('__call__', fn_info.callable_class.ir.name, self.module_name, sig)
        call_fn_ir = FuncIR(call_fn_decl, blocks, env)
        fn_info.callable_class.ir.methods['__call__'] = call_fn_ir
        return call_fn_ir

    def instantiate_callable_class(self, fn_info: FuncInfo) -> Value:
        """
        Assigns a callable class to a register named after the given function definition. Note
        that fn_info refers to the function being assigned, whereas self.fn_info refers to the
        function encapsulating the function being turned into a callable class.
        """
        fitem = fn_info.fitem

        func_reg = self.add(Call(fn_info.callable_class.ir.ctor, [], fitem.line))

        # Set the callable class' environment attribute to point at the environment class
        # defined in the callable class' immediate outer scope. Note that there are three possible
        # environment class registers we may use. If the encapsulating function is:
        # - a generator function, then the callable class is instantiated from the generator class'
        #   __next__' function, and hence the generator class' environment register is used.
        # - a nested function, then the callable class is instantiated from the current callable
        #   class' '__call__' function, and hence the callable class' environment register is used.
        # - neither, then we use the environment register of the original function.
        if self.fn_info.is_generator:
            curr_env_reg = self.fn_info.generator_class.curr_env_reg
        elif self.fn_info.is_nested:
            curr_env_reg = self.fn_info.callable_class.curr_env_reg
        else:
            curr_env_reg = self.fn_info.curr_env_reg
        self.add(SetAttr(func_reg, ENV_ATTR_NAME, curr_env_reg, fitem.line))
        return func_reg

    def setup_env_class(self) -> ClassIR:
        """Generates a class representing a function environment.

        Note that the variables in the function environment are not actually populated here. This
        is because when the environment class is generated, the function environment has not yet
        been visited. This behavior is allowed so that when the compiler visits nested functions,
        it can use the returned ClassIR instance to figure out free variables it needs to access.
        The remaining attributes of the environment class are populated when the environment
        registers are loaded.

        Returns a ClassIR representing an environment for a function containing a nested function.
        """
        env_class = ClassIR('{}_{}_env'.format(self.fn_info.name, self.fn_info.ns),
                            self.module_name)
        env_class.attributes['self'] = RInstance(env_class)
        if self.fn_info.is_nested:
            # If the function is nested, its environment class must contain an environment
            # attribute pointing to its encapsulating functions' environment class.
            env_class.attributes[ENV_ATTR_NAME] = RInstance(self.fn_infos[-2].env_class)
        env_class.mro = [env_class]
        self.fn_info.env_class = env_class
        self.classes.append(env_class)
        return env_class

    def finalize_env_class(self) -> None:
        """Generates, instantiates, and sets up the environment of an environment class."""

        self.instantiate_env_class()

        # Iterate through the function arguments and replace local definitions (using registers)
        # that were previously added to the environment with references to the function's
        # environment class.
        if self.fn_info.is_nested:
            self.add_args_to_env(local=False, base=self.fn_info.callable_class)
        else:
            self.add_args_to_env(local=False, base=self.fn_info)

    def instantiate_env_class(self) -> Value:
        """Assigns an environment class to a register named after the given function definition."""
        curr_env_reg = self.add(Call(self.fn_info.env_class.ctor, [], self.fn_info.fitem.line))

        if self.fn_info.is_nested:
            self.fn_info.callable_class._curr_env_reg = curr_env_reg
            self.add(SetAttr(curr_env_reg,
                             ENV_ATTR_NAME,
                             self.fn_info.callable_class.prev_env_reg,
                             self.fn_info.fitem.line))
        else:
            self.fn_info._curr_env_reg = curr_env_reg

        return curr_env_reg

    def gen_generator_func(self) -> None:
        self.setup_generator_class()
        self.load_env_registers()
        self.gen_arg_default()
        self.finalize_env_class()
        self.add(Return(self.instantiate_generator_class()))

    def setup_generator_class(self) -> ClassIR:
        name = '{}_{}_gen'.format(self.fn_info.name, self.fn_info.ns)

        generator_class_ir = ClassIR(name, self.module_name)
        generator_class_ir.attributes[ENV_ATTR_NAME] = RInstance(self.fn_info.env_class)
        generator_class_ir.mro = [generator_class_ir]

        self.classes.append(generator_class_ir)
        self.fn_info.generator_class = GeneratorClass(generator_class_ir)
        return generator_class_ir

    def add_helper_to_generator_class(self,
                                      blocks: List[BasicBlock],
                                      sig: FuncSignature,
                                      env: Environment,
                                      fn_info: FuncInfo) -> FuncDecl:
        """Generates a helper method for a generator class, called by '__next__' and 'throw'."""
        sig = FuncSignature((RuntimeArg('self', object_rprimitive),
                             RuntimeArg('type', object_rprimitive),
                             RuntimeArg('value', object_rprimitive),
                             RuntimeArg('traceback', object_rprimitive)), sig.ret_type)
        helper_fn_decl = FuncDecl('__mypyc_generator_helper__', fn_info.generator_class.ir.name,
                                  self.module_name, sig)
        helper_fn_ir = FuncIR(helper_fn_decl, blocks, env)
        fn_info.generator_class.ir.methods['__mypyc_generator_helper__'] = helper_fn_ir
        self.functions.append(helper_fn_ir)
        return helper_fn_decl

    def add_iter_to_generator_class(self, fn_info: FuncInfo) -> None:
        """Generates the '__iter__' method for a generator class."""
        self.enter(fn_info)
        self_target = self.add_self_to_env(fn_info.generator_class.ir)
        self.add(Return(self.read(self_target, fn_info.fitem.line)))
        blocks, env, _, fn_info = self.leave()

        # Next, add the actual function as a method of the generator class.
        sig = FuncSignature((RuntimeArg('self', object_rprimitive),), object_rprimitive)
        iter_fn_decl = FuncDecl('__iter__', fn_info.generator_class.ir.name, self.module_name, sig)
        iter_fn_ir = FuncIR(iter_fn_decl, blocks, env)
        fn_info.generator_class.ir.methods['__iter__'] = iter_fn_ir
        self.functions.append(iter_fn_ir)

    def add_next_to_generator_class(self,
                                    fn_info: FuncInfo,
                                    fn_decl: FuncDecl,
                                    sig: FuncSignature) -> None:
        """Generates the '__next__' method for a generator class."""
        self.enter(fn_info)
        self_reg = self.read(self.add_self_to_env(fn_info.generator_class.ir))
        none_reg = self.none()

        # Call the helper function with error flags set to Py_None, and return that result.
        result = self.add(Call(fn_decl, [self_reg, none_reg, none_reg, none_reg],
                               fn_info.fitem.line))
        self.add(Return(result))
        blocks, env, _, fn_info = self.leave()

        sig = FuncSignature((RuntimeArg('self', object_rprimitive),), sig.ret_type)
        next_fn_decl = FuncDecl('__next__', fn_info.generator_class.ir.name, self.module_name, sig)
        next_fn_ir = FuncIR(next_fn_decl, blocks, env)
        fn_info.generator_class.ir.methods['__next__'] = next_fn_ir
        self.functions.append(next_fn_ir)

    def add_throw_to_generator_class(self,
                                     fn_info: FuncInfo,
                                     fn_decl: FuncDecl,
                                     sig: FuncSignature) -> None:
        """Generates the 'throw' method for a generator class."""
        self.enter(fn_info)
        self_reg = self.read(self.add_self_to_env(fn_info.generator_class.ir))

        # Add the type, value, and traceback variables to the environment.
        typ = self.environment.add_local_reg(Var('type'), object_rprimitive, True)
        val = self.environment.add_local_reg(Var('value'), object_rprimitive, True)
        tb = self.environment.add_local_reg(Var('traceback'), object_rprimitive, True)

        # Because the value and traceback arguments are optional and hence can be NULL if not
        # passed in, we have to assign them Py_None if they are not passed in.
        none_reg = self.none()
        self.assign_if_null(val, lambda: none_reg, self.fn_info.fitem.line)
        self.assign_if_null(tb, lambda: none_reg, self.fn_info.fitem.line)

        # Call the helper function using the arguments passed in, and return that result.
        result = self.add(Call(fn_decl, [self_reg, self.read(typ), self.read(val), self.read(tb)],
                               fn_info.fitem.line))
        self.add(Return(result))
        blocks, env, _, fn_info = self.leave()

        # Create the FuncSignature for the throw function. NOte that the value and traceback fields
        # are optional, and are assigned to if they are not passed in inside the body of the throw
        # function.
        sig = FuncSignature((RuntimeArg('self', object_rprimitive),
                             RuntimeArg('type', object_rprimitive),
                             RuntimeArg('value', object_rprimitive, ARG_OPT),
                             RuntimeArg('traceback', object_rprimitive, ARG_OPT)),
                            sig.ret_type)

        throw_fn_decl = FuncDecl('throw', fn_info.generator_class.ir.name, self.module_name, sig)
        throw_fn_ir = FuncIR(throw_fn_decl, blocks, env)
        fn_info.generator_class.ir.methods['throw'] = throw_fn_ir
        self.functions.append(throw_fn_ir)

    def create_switch_for_generator_class(self) -> None:
        self.add(Goto(self.fn_info.generator_class.switch_block))
        self.fn_info.generator_class.blocks.append(self.new_block())

    def populate_switch_for_generator_class(self) -> None:
        cls = self.fn_info.generator_class
        line = self.fn_info.fitem.line

        self.activate_block(cls.switch_block)
        for label, true_block in enumerate(cls.blocks):
            false_block = BasicBlock()
            comparison = self.binary_op(cls.next_label_reg, self.add(LoadInt(label)), '==', line)
            self.add_bool_branch(comparison, true_block, false_block)
            self.activate_block(false_block)

        self.add(RaiseStandardError(RaiseStandardError.STOP_ITERATION, None, line))
        self.add(Unreachable())

    def instantiate_generator_class(self) -> Value:
        fitem = self.fn_info.fitem
        generator_reg = self.add(Call(self.fn_info.generator_class.ir.ctor, [], fitem.line))

        # Get the current environment register. If the current function is nested, then the
        # generator class gets instantiated from the callable class' '__call__' method, and hence
        # we use the callable class' environment register. Otherwise, we use the original
        # function's environment register.
        if self.fn_info.is_nested:
            curr_env_reg = self.fn_info.callable_class.curr_env_reg
        else:
            curr_env_reg = self.fn_info.curr_env_reg

        # Set the generator class' environment attribute to point at the environment class
        # defined in the current scope.
        self.add(SetAttr(generator_reg, ENV_ATTR_NAME, curr_env_reg, fitem.line))

        # Set the generator class' environment class' NEXT_LABEL_ATTR_NAME attribute to 0.
        zero_reg = self.add(LoadInt(0))
        self.add(SetAttr(curr_env_reg, NEXT_LABEL_ATTR_NAME, zero_reg, fitem.line))
        return generator_reg

    def add_raise_exception_blocks_to_generator_class(self, line: int) -> None:
        """
        Generates blocks to check if error flags are set while calling the helper method for
        generator functions, and raises an exception if those flags are set.
        """
        cls = self.fn_info.generator_class
        assert cls.exc_regs is not None
        exc_type, exc_val, exc_tb = cls.exc_regs

        # Check to see if an exception was raised.
        error_block = BasicBlock()
        ok_block = BasicBlock()
        comparison = self.binary_op(exc_type, self.none(), 'is not', line)
        self.add_bool_branch(comparison, error_block, ok_block)

        self.activate_block(error_block)
        self.primitive_op(raise_exception_with_tb_op, [exc_type, exc_val, exc_tb], line)
        self.add(Unreachable())
        self.goto_and_activate(ok_block)

    def add_self_to_env(self, cls: ClassIR) -> AssignmentTargetRegister:
        return self.environment.add_local_reg(Var('self'),
                                              RInstance(cls),
                                              is_arg=True)

    def is_builtin_ref_expr(self, expr: RefExpr) -> bool:
        assert expr.node, "RefExpr not resolved"
        return '.' in expr.node.fullname() and expr.node.fullname().split('.')[0] == 'builtins'

    def load_global(self, expr: NameExpr) -> Value:
        """Loads a Python-level global.

        This takes a NameExpr and uses its name as a key to retrieve the corresponding PyObject *
        from the _globals dictionary in the C-generated code.
        """
        # If the global is from 'builtins', turn it into a module attr load instead
        if self.is_builtin_ref_expr(expr):
            return self.load_module_attr(expr)
        if (self.is_native_module_ref_expr(expr) and isinstance(expr.node, TypeInfo)
                and not self.is_synthetic_type(expr.node)):
            assert expr.fullname is not None
            return self.load_native_type_object(expr.fullname)
        _globals = self.load_globals_dict()
        reg = self.load_static_unicode(expr.name)
        return self.add(PrimitiveOp([_globals, reg], dict_get_item_op, expr.line))

    def load_globals_dict(self) -> Value:
        return self.add(LoadStatic(object_rprimitive, 'globals', self.module_name))

    def load_static_int(self, value: int) -> Value:
        """Loads a static integer Python 'int' object into a register."""
        static_symbol = self.mapper.literal_static_name(value)
        return self.add(LoadStatic(int_rprimitive, static_symbol, ann=value))

    def load_static_float(self, value: float) -> Value:
        """Loads a static float value into a register."""
        static_symbol = self.mapper.literal_static_name(value)
        return self.add(LoadStatic(float_rprimitive, static_symbol, ann=value))

    def load_static_bytes(self, value: bytes) -> Value:
        """Loads a static bytes value into a register."""
        static_symbol = self.mapper.literal_static_name(value)
        return self.add(LoadStatic(object_rprimitive, static_symbol, ann=value))

    def load_static_unicode(self, value: str) -> Value:
        """Loads a static unicode value into a register.

        This is useful for more than just unicode literals; for example, method calls
        also require a PyObject * form for the name of the method.
        """
        static_symbol = self.mapper.literal_static_name(value)
        return self.add(LoadStatic(str_rprimitive, static_symbol, ann=value))

    def load_module_attr(self, expr: RefExpr) -> Value:
        assert expr.node, "RefExpr not resolved"
        return self.load_module_attr_by_fullname(expr.node.fullname(), expr.line)

    def load_module_attr_by_fullname(self, fullname: str, line: int) -> Value:
        module, _, name = fullname.rpartition('.')
        left = self.add(LoadStatic(object_rprimitive, 'module', module))
        return self.py_get_attr(left, name, line)

    def load_native_type_object(self, fullname: str) -> Value:
        module, name = fullname.rsplit('.', 1)
        return self.add(LoadStatic(object_rprimitive, name, module, NAMESPACE_TYPE))

    def coerce(self, src: Value, target_type: RType, line: int, force: bool = False) -> Value:
        """Generate a coercion/cast from one type to other (only if needed).

        For example, int -> object boxes the source int; int -> int emits nothing;
        object -> int unboxes the object. All conversions preserve object value.

        If force is true, always generate an op (even if it is just an assignment) so
        that the result will have exactly target_type as the type.

        Returns the register with the converted value (may be same as src).
        """
        if src.type.is_unboxed and not target_type.is_unboxed:
            return self.box(src)
        if ((src.type.is_unboxed and target_type.is_unboxed)
                and not is_same_type(src.type, target_type)):
            # To go from one unboxed type to another, we go through a boxed
            # in-between value, for simplicity.
            tmp = self.box(src)
            return self.unbox_or_cast(tmp, target_type, line)
        if ((not src.type.is_unboxed and target_type.is_unboxed)
                or not is_subtype(src.type, target_type)):
            return self.unbox_or_cast(src, target_type, line)
        elif force:
            tmp = self.alloc_temp(target_type)
            self.add(Assign(tmp, src))
            return tmp
        return src

    def keyword_args_to_positional(self,
                                   args: Sequence[Value],
                                   arg_kinds: List[int],
                                   arg_names: List[Optional[str]],
                                   sig: FuncSignature) -> List[Optional[Value]]:
        # NOTE: This doesn't support *args or **kwargs.
        sig_arg_kinds = [arg.kind for arg in sig.args]
        sig_arg_names = [arg.name for arg in sig.args]
        formal_to_actual = map_actuals_to_formals(arg_kinds,
                                                  arg_names,
                                                  sig_arg_kinds,
                                                  sig_arg_names,
                                                  lambda n: AnyType(TypeOfAny.special_form))
        assert all(len(lst) <= 1 for lst in formal_to_actual)
        return [None if len(lst) == 0 else args[lst[0]] for lst in formal_to_actual]

    # Lacks a good type because there wasn't a reasonable type in 3.5 :(
    def catch_errors(self, line: int) -> Any:
        return catch_errors(self.module_path, line)
