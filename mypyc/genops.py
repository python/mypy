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
from typing import Dict, List, Tuple, Optional, Union, Sequence, Set
from abc import abstractmethod

from mypy.nodes import (
    Node, MypyFile, SymbolNode, Statement, FuncItem, FuncDef, ReturnStmt, AssignmentStmt, OpExpr,
    IntExpr, NameExpr, LDEF, Var, IfStmt, UnaryExpr, ComparisonExpr, WhileStmt, Argument, CallExpr,
    IndexExpr, Block, Expression, ListExpr, ExpressionStmt, MemberExpr, ForStmt, RefExpr, Lvalue,
    BreakStmt, ContinueStmt, ConditionalExpr, OperatorAssignmentStmt, TupleExpr, ClassDef,
    TypeInfo, Import, ImportFrom, ImportAll, DictExpr, StrExpr, CastExpr, TempNode, ARG_POS,
    MODULE_REF, PassStmt, PromoteExpr, AwaitExpr, BackquoteExpr, AssertStmt, BytesExpr,
    ComplexExpr, Decorator, DelStmt, DictionaryComprehension, EllipsisExpr, EnumCallExpr, ExecStmt,
    FloatExpr, GeneratorExpr, GlobalDecl, LambdaExpr, ListComprehension, SetComprehension,
    NamedTupleExpr, NewTypeExpr, NonlocalDecl, OverloadedFuncDef, PrintStmt, RaiseStmt,
    RevealExpr, SetExpr, SliceExpr, StarExpr, SuperExpr, TryStmt, TypeAliasExpr,
    TypeApplication, TypeVarExpr, TypedDictExpr, UnicodeExpr, WithStmt, YieldFromExpr, YieldExpr,
    GDEF
)
import mypy.nodes
from mypy.types import (
    Type, Instance, CallableType, NoneTyp, TupleType, UnionType, AnyType, TypeVarType, PartialType,
    TypeType, FunctionLike, Overloaded
)
from mypy.visitor import NodeVisitor
from mypy.subtypes import is_named_instance
from mypy.checkmember import bind_self

from mypyc.common import ENV_ATTR_NAME, MAX_SHORT_INT, TOP_LEVEL_NAME
from mypyc.freevariables import FreeVariablesVisitor
from mypyc.ops import (
    BasicBlock, AssignmentTarget, AssignmentTargetRegister, AssignmentTargetIndex,
    AssignmentTargetAttr, AssignmentTargetTuple, Environment, Op, LoadInt, RType, Value, Register,
    Return, FuncIR, Assign, Branch, Goto, RuntimeArg, Call, Box, Unbox, Cast, RTuple, Unreachable,
    TupleGet, TupleSet, ClassIR, RInstance, ModuleIR, GetAttr, SetAttr, LoadStatic, ROptional,
    MethodCall, INVALID_VALUE, INVALID_CLASS, INVALID_FUNC_DEF, int_rprimitive, float_rprimitive,
    bool_rprimitive, list_rprimitive, is_list_rprimitive, dict_rprimitive, str_rprimitive,
    tuple_rprimitive, none_rprimitive, is_none_rprimitive, object_rprimitive, PrimitiveOp,
    ERR_FALSE, OpDescription, RegisterOp, is_object_rprimitive, LiteralsMap, FuncSignature,
    VTableAttr, VTableMethod, VTableEntries,
    NAMESPACE_TYPE, RaiseStandardError,
)
from mypyc.ops_primitive import binary_ops, unary_ops, func_ops, method_ops, name_ref_ops
from mypyc.ops_list import list_len_op, list_get_item_op, list_set_item_op, new_list_op
from mypyc.ops_dict import new_dict_op, dict_get_item_op
from mypyc.ops_misc import (
    none_op, iter_op, next_op, py_getattr_op, py_setattr_op,
    py_call_op, py_method_call_op, fast_isinstance_op, bool_op, new_slice_op,
    is_none_op, type_op,
)
from mypyc.ops_exc import (
    no_err_occurred_op, raise_exception_op, reraise_exception_op, clear_exception_op,
    error_catch_op, clear_exc_info_op,
)
from mypyc.subtype import is_subtype
from mypyc.sametype import is_same_type, is_same_method_signature


def build_ir(modules: List[MypyFile],
             types: Dict[Expression, Type]) -> List[Tuple[str, ModuleIR]]:
    result = []
    mapper = Mapper()

    # Collect all classes defined in the compilation unit.
    classes = []
    for module in modules:
        module_classes = [node for node in module.defs if isinstance(node, ClassDef)]
        classes.extend([(module.fullname(), cdef) for cdef in module_classes])

    # Collect all class mappings so that we can bind arbitrary class name
    # references even if there are import cycles.
    for module_name, cdef in classes:
        class_ir = ClassIR(cdef.name, module_name, is_trait(cdef))
        mapper.type_to_ir[cdef.info] = class_ir

    # Populate structural information in class IR.
    for _, cdef in classes:
        prepare_class_def(cdef, mapper)

    # Generate IR for all modules.
    module_names = [mod.fullname() for mod in modules]
    class_irs = []

    for module in modules:
        # First pass to determine free symbols.
        fvv = FreeVariablesVisitor()
        module.accept(fvv)

        # Second pass.
        builder = IRBuilder(types, mapper, module_names, fvv)
        module.accept(builder)
        module_ir = ModuleIR(
            builder.imports,
            builder.from_imports,
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
            if method.name in cls.methods:
                # TODO: emit a wrapper for __init__ that raises or something
                if (is_same_method_signature(method.sig, cls.methods[method.name].sig)
                        or method.name == '__init__'):
                    entry = VTableMethod(cls, entry.name, cls.methods[method.name])
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
        for fn in t.methods.values():
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
            elif typ.type.fullname() == 'builtins.tuple':
                return tuple_rprimitive  # Varying-length tuple
            elif typ.type in self.type_to_ir:
                return RInstance(self.type_to_ir[typ.type])
            else:
                return object_rprimitive
        elif isinstance(typ, TupleType):
            return RTuple([self.type_to_rtype(t) for t in typ.items])
        elif isinstance(typ, CallableType):
            return object_rprimitive
        elif isinstance(typ, NoneTyp):
            return none_rprimitive
        elif isinstance(typ, UnionType):
            assert len(typ.items) == 2 and any(isinstance(it, NoneTyp) for it in typ.items)
            if isinstance(typ.items[0], NoneTyp):
                value_type = typ.items[1]
            else:
                value_type = typ.items[0]
            return ROptional(self.type_to_rtype(value_type))
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
        assert False, '%s unsupported' % type(typ)

    def fdef_to_sig(self, fdef: FuncDef) -> FuncSignature:
        assert isinstance(fdef.type, CallableType)
        args = [RuntimeArg(arg.variable.name(), self.type_to_rtype(fdef.type.arg_types[i]))
                for i, arg in enumerate(fdef.arguments)]
        ret = self.type_to_rtype(fdef.type.ret_type)
        return FuncSignature(args, ret)

    def literal_static_name(self, value: Union[int, float, str]) -> str:
        # Include type to distinguish between 1 and 1.0, and so on.
        key = (type(value), value)
        if key not in self.literals:
            if isinstance(value, str):
                prefix = 'unicode_'
            elif isinstance(value, float):
                prefix = 'float_'
            else:
                assert isinstance(value, int)
                prefix = 'int_'
            self.literals[key] = prefix + str(len(self.literals))
        return self.literals[key]


def prepare_class_def(cdef: ClassDef, mapper: Mapper) -> None:
    ir = mapper.type_to_ir[cdef.info]
    info = cdef.info
    for name, node in info.names.items():
        if isinstance(node.node, Var):
            assert node.node.type, "Class member missing type"
            ir.attributes[name] = mapper.type_to_rtype(node.node.type)
        elif isinstance(node.node, FuncDef):
            ir.method_types[name] = mapper.fdef_to_sig(node.node)

    # Set up the parent class
    bases = [mapper.type_to_ir[base.type] for base in info.bases
             if base.type.fullname() != 'builtins.object']
    assert all(c.is_trait for c in bases[1:]), "Non trait bases must be first"
    ir.traits = [c for c in bases if c.is_trait]

    mro = []
    base_mro = []
    for cls in info.mro:
        if cls.fullname() == 'builtins.object': continue
        assert cls in mapper.type_to_ir, "Can't subclass cpython types"
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


class FuncInfo(object):
    """Contains information about functions as they are generated."""
    def __init__(self, fitem: FuncItem = INVALID_FUNC_DEF, name: str = '',
                 namespace: str = '') -> None:
        self.fitem = fitem
        self.name = name
        self.ns = namespace
        # Callable classes are ClassIR instances implementing the '__call__' method, used to
        # represent functions that are nested inside of other functions.
        self.callable_class = INVALID_CLASS
        # Environment classes are ClassIR instances that contain attributes representing the
        # variables in the environment of the function they correspond to. Environment classes are
        # generated for functions that contain nested functions.
        self.env_class = INVALID_CLASS
        # The register associated with the 'self' instance for function classes.
        self.self_reg = INVALID_VALUE  # type: Value
        # Environment class registers are the local registers associated with instances of an
        # environment class, used for getting and setting attributes. env_reg is the register
        # associated with the current environment, and prev_env_reg is the self.__mypyc_env__ field
        # associated with the previous environment.
        self.env_reg = INVALID_VALUE  # type: Value
        self.prev_env_reg = INVALID_VALUE  # type: Value
        # These are flags denoting whether a given function is nested or contains a nested
        # function.
        self.is_nested = False
        self.contains_nested = False
        # TODO: add field for ret_type: RType = none_rprimitive


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


class IRBuilder(NodeVisitor[Value]):
    def __init__(self,
                 types: Dict[Expression, Type],
                 mapper: Mapper,
                 modules: List[str],
                 fvv: FreeVariablesVisitor) -> None:
        self.types = types
        self.environment = Environment()
        self.environments = [self.environment]
        self.ret_types = []  # type: List[RType]
        self.blocks = []  # type: List[List[BasicBlock]]
        self.functions = []  # type: List[FuncIR]
        self.classes = []  # type: List[ClassIR]
        self.modules = set(modules)
        self.callable_class_names = set()  # type: Set[str]

        self.lambda_counter = 0

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
        self.from_imports = {}  # type: Dict[str, List[Tuple[str, str]]]
        self.imports = []  # type: List[str]

        self.current_module_name = None  # type: Optional[str]

    def visit_mypy_file(self, mypyfile: MypyFile) -> Value:
        if mypyfile.fullname() in ('typing', 'abc'):
            # These module are special; their contents are currently all
            # built-in primitives.
            return INVALID_VALUE

        self.module_name = mypyfile.fullname()

        classes = [node for node in mypyfile.defs if isinstance(node, ClassDef)]

        # Collect all classes.
        for cls in classes:
            ir = self.mapper.type_to_ir[cls.info]
            self.classes.append(ir)

        self.current_module_name = mypyfile.fullname()
        self.enter(FuncInfo(name='<top level>'))

        # Generate ops.
        for node in mypyfile.defs:
            node.accept(self)
        self.maybe_add_implicit_return()

        # Generate special function representing module top level.
        blocks, env, ret_type, _ = self.leave()
        sig = FuncSignature([], none_rprimitive)
        func_ir = FuncIR(TOP_LEVEL_NAME, None, self.module_name, sig, blocks, env)
        self.functions.append(func_ir)

        return INVALID_VALUE

    def visit_class_def(self, cdef: ClassDef) -> Value:
        class_ir = self.mapper.type_to_ir[cdef.info]
        for name, node in sorted(cdef.info.names.items(), key=lambda x: x[0]):
            if isinstance(node.node, FuncDef):
                fdef = node.node
                func_ir, _ = self.gen_func_def(fdef, fdef.name(), class_ir.method_sig(fdef.name()),
                                               cdef.name)

                self.functions.append(func_ir)
                class_ir.methods[fdef.name()] = func_ir

                # If this overrides a parent class method with a different type, we need
                # to generate a glue method to mediate between them.
                for cls in class_ir.mro[1:]:
                    if (name in cls.method_types and name != '__init__'
                            and not is_same_method_signature(class_ir.method_types[name],
                                                             cls.method_types[name])):
                        f = self.gen_glue_method(cls.method_types[name], func_ir, class_ir, cls,
                                                 fdef.line)
                        class_ir.glue_methods[(cls, name)] = f
                        self.functions.append(f)

        return INVALID_VALUE

    def visit_import(self, node: Import) -> Value:
        if node.is_unreachable or node.is_mypy_only:
            pass
        if not node.is_top_level:
            assert False, "non-toplevel imports not supported"

        for node_id, _ in node.ids:
            self.imports.append(node_id)

        return INVALID_VALUE

    def visit_import_from(self, node: ImportFrom) -> Value:
        if node.is_unreachable or node.is_mypy_only:
            pass

        # TODO support these?
        assert not node.relative

        if node.id not in self.from_imports:
            self.from_imports[node.id] = []

        for name, maybe_as_name in node.names:
            as_name = maybe_as_name or name
            self.from_imports[node.id].append((name, as_name))

        return INVALID_VALUE

    def visit_import_all(self, node: ImportAll) -> Value:
        if node.is_unreachable or node.is_mypy_only:
            pass
        if not node.is_top_level:
            assert False, "non-toplevel imports not supported"

        self.imports.append(node.id)

        return INVALID_VALUE

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
        args = [self.read_from_target(self.environment.add_local_reg(var, type, is_arg=True), line)
                for var, type in fake_vars]  # type: List[Value]
        self.ret_types[-1] = sig.ret_type

        arg_types = [arg.type for arg in target.sig.args]
        args = self.coerce_native_call_args(args, arg_types, line)
        retval = self.add(MethodCall(target.ret_type,
                                     args[0],
                                     target.name,
                                     args[1:],
                                     line))
        retval = self.coerce(retval, sig.ret_type, line)
        self.add(Return(retval))

        blocks, env, ret_type, _ = self.leave()
        return FuncIR(target.name + '__' + base.name + '_glue',
                      cls.name, self.module_name,
                      FuncSignature(rt_args, ret_type), blocks, env)

    def gen_func_def(self, fitem: FuncItem, name: str, sig: FuncSignature,
                     class_name: Optional[str] = None) -> Tuple[FuncIR, Value]:
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
        self.enter(FuncInfo(fitem, name, self.gen_func_ns()))

        # The top-most environment is for the module top level.
        self.fn_info.is_nested = fitem in self.nested_fitems
        self.fn_info.contains_nested = fitem in self.encapsulating_fitems

        if self.fn_info.is_nested:
            self.setup_callable_class()
        if self.fn_info.contains_nested:
            self.setup_env_class()

        self.load_env_registers()

        if self.fn_info.contains_nested:
            self.finalize_env_class()

        self.ret_types[-1] = sig.ret_type

        fitem.body.accept(self)
        self.maybe_add_implicit_return()

        blocks, env, ret_type, fn_info = self.leave()

        if fn_info.is_nested:
            func_ir = self.add_call_to_callable_class(blocks, sig, env, fn_info)
            func_reg = self.instantiate_callable_class(fn_info)
        else:
            func_ir = FuncIR(fn_info.name, class_name, self.module_name, sig, blocks, env)
            func_reg = INVALID_VALUE

        return (func_ir, func_reg)

    def maybe_add_implicit_return(self) -> None:
        if (is_none_rprimitive(self.ret_types[-1]) or
                is_object_rprimitive(self.ret_types[-1])):
            self.add_implicit_return()
        else:
            self.add_implicit_unreachable()

    def visit_func_def(self, fdef: FuncDef) -> Value:
        func_ir, func_reg = self.gen_func_def(fdef, fdef.name(), self.mapper.fdef_to_sig(fdef))

        # If the function that was visited was a nested function, then either look it up in our
        # current environment or define it if it was not already defined.
        if self.fn_info.contains_nested:
            if fdef.original_def:
                # Get the target associated with the previously defined FuncDef.
                func_target = self.environment.lookup(fdef.original_def)
            else:
                # The return type is 'object' instead of an RInstance of the callable class because
                # differently defined functions with the same name and signature in conditional
                # blocks will generate different callable classes, so the callable class that gets
                # instantiated must be generic.
                func_target = self.environment.add_local_reg(fdef, object_rprimitive)
            self.assign_to_target(func_target, func_reg, fdef.line)

        self.functions.append(func_ir)
        return INVALID_VALUE

    def add_implicit_return(self) -> None:
        block = self.blocks[-1][-1]
        if not block.ops or not isinstance(block.ops[-1], Return):
            retval = self.add(PrimitiveOp([], none_op, line=-1))
            self.add(Return(retval))

    def add_implicit_unreachable(self) -> None:
        block = self.blocks[-1][-1]
        if not block.ops or not isinstance(block.ops[-1], Return):
            self.add(Unreachable())

    def visit_block(self, block: Block) -> Value:
        for stmt in block.body:
            stmt.accept(self)
        return INVALID_VALUE

    def visit_expression_stmt(self, stmt: ExpressionStmt) -> Value:
        self.accept(stmt.expr)
        return INVALID_VALUE

    def visit_return_stmt(self, stmt: ReturnStmt) -> Value:
        if stmt.expr:
            retval = self.accept(stmt.expr)
            retval = self.coerce(retval, self.ret_types[-1], stmt.line)
        else:
            retval = self.add(PrimitiveOp([], none_op, line=-1))
        self.nonlocal_control[-1].gen_return(self, retval)
        return INVALID_VALUE

    def visit_assignment_stmt(self, stmt: AssignmentStmt) -> Value:
        assert len(stmt.lvalues) == 1
        if isinstance(stmt.rvalue, CallExpr) and isinstance(stmt.rvalue.analyzed, TypeVarExpr):
            # Just ignore type variable declarations -- they are a compile-time only thing.
            # TODO: It would be nice to actually construct TypeVar objects to match Python
            #       semantics.
            return INVALID_VALUE
        lvalue = stmt.lvalues[0]
        if stmt.type and isinstance(stmt.rvalue, TempNode):
            # This is actually a variable annotation without initializer. Don't generate
            # an assignment but we need to call get_assignment_target since it adds a
            # name binding as a side effect.
            self.get_assignment_target(lvalue)
            return INVALID_VALUE
        self.assign(lvalue, stmt.rvalue)
        return INVALID_VALUE

    def visit_operator_assignment_stmt(self, stmt: OperatorAssignmentStmt) -> Value:
        target = self.get_assignment_target(stmt.lvalue)
        rreg = self.accept(stmt.rvalue)
        res = self.read_from_target(target, stmt.line)
        res = self.binary_op(res, rreg, stmt.op, stmt.line)
        self.assign_to_target(target, res, res.line)
        return INVALID_VALUE

    def get_assignment_target(self, lvalue: Lvalue) -> AssignmentTarget:
        if isinstance(lvalue, NameExpr):
            # Assign to local variable.
            assert isinstance(lvalue.node, SymbolNode)  # TODO: Can this fail?
            symbol = lvalue.node
            if lvalue.kind == LDEF:
                if symbol not in self.environment.symtable:
                    # If the function contains a nested function and the symbol is a free symbol,
                    # then first define a new variable in the current function's environment class.
                    # Next, define a target that refers to the newly defined variable in that
                    # environment class. Add the target to the table containing class environment
                    # variables, as well as the current environment.
                    if self.fn_info.contains_nested and self.is_free_variable(symbol):
                        self.fn_info.env_class.attributes[symbol.name()] = self.node_type(lvalue)
                        target = AssignmentTargetAttr(self.fn_info.env_reg, symbol.name())
                        return self.environment.add_target(symbol, target)

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

    def read_from_target(self, target: AssignmentTarget, line: int) -> Value:
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

    def assign_to_target(self,
                         target: AssignmentTarget,
                         rvalue_reg: Value,
                         line: int) -> None:
        if isinstance(target, AssignmentTargetRegister):
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
                    self.assign_to_target(target.items[i], item_value, line)
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
            self.assign_to_target(litem, ritem, line)
        extra = self.primitive_op(next_op, [iterator], line)
        error_block, ok_block = BasicBlock(), BasicBlock()
        self.add(Branch(extra, ok_block, error_block, Branch.IS_ERROR))

        self.activate_block(error_block)
        self.add(RaiseStandardError(RaiseStandardError.VALUE_ERROR,
                                    'too many values to unpack', line))
        self.add(Unreachable())

        self.activate_block(ok_block)

    def assign(self,
               lvalue: Lvalue,
               rvalue: Expression) -> AssignmentTarget:
        target = self.get_assignment_target(lvalue)
        rvalue_reg = self.accept(rvalue)
        self.assign_to_target(target, rvalue_reg, rvalue.line)
        return target

    def visit_if_stmt(self, stmt: IfStmt) -> Value:
        if_body, next = BasicBlock(), BasicBlock()
        else_body = BasicBlock() if stmt.else_body else next

        # If statements are normalized
        assert len(stmt.expr) == 1

        self.process_conditional(stmt.expr[0], if_body, else_body)
        self.activate_block(if_body)
        stmt.body[0].accept(self)
        self.add_leave(next)
        if stmt.else_body:
            self.activate_block(else_body)
            stmt.else_body.accept(self)
            self.add_leave(next)
        self.activate_block(next)
        return INVALID_VALUE

    def add_leave(self, target: BasicBlock) -> None:
        if not self.blocks[-1][-1].ops or not isinstance(self.blocks[-1][-1].ops[-1], Return):
            self.add(Goto(target))

    class LoopNonlocalControl(NonlocalControl):
        def __init__(self, outer: NonlocalControl,
                     continue_block: BasicBlock, break_block: BasicBlock) -> None:
            self.outer = outer
            self.continue_block = continue_block
            self.break_block = break_block

        def gen_break(self, builder: 'IRBuilder') -> None:
            builder.add(Goto(self.break_block))
            builder.new_block()

        def gen_continue(self, builder: 'IRBuilder') -> None:
            builder.add(Goto(self.continue_block))
            builder.new_block()

        def gen_return(self, builder: 'IRBuilder', value: Value) -> None:
            self.outer.gen_return(builder, value)

    def push_loop_stack(self, continue_block: BasicBlock, break_block: BasicBlock) -> None:
        self.nonlocal_control.append(
            IRBuilder.LoopNonlocalControl(self.nonlocal_control[-1], continue_block, break_block))

    def pop_loop_stack(self) -> None:
        self.nonlocal_control.pop()

    def visit_while_stmt(self, s: WhileStmt) -> Value:
        body, next, top = BasicBlock(), BasicBlock(), BasicBlock()

        self.push_loop_stack(top, next)

        # Split block so that we get a handle to the top of the loop.
        self.goto_and_activate(top)
        self.process_conditional(s.expr, body, next)

        self.activate_block(body)
        s.body.accept(self)
        # Add branch to the top at the end of the body.
        self.add(Goto(top))

        self.activate_block(next)

        self.pop_loop_stack()
        return INVALID_VALUE

    def visit_for_stmt(self, s: ForStmt) -> Value:
        if (isinstance(s.expr, CallExpr)
                and isinstance(s.expr.callee, RefExpr)
                and s.expr.callee.fullname == 'builtins.range'):
            body, next, top, end_block = BasicBlock(), BasicBlock(), BasicBlock(), BasicBlock()

            self.push_loop_stack(end_block, next)

            # Special case for x in range(...)
            # TODO: Check argument counts and kinds; check the lvalue
            end = s.expr.args[0]
            end_reg = self.accept(end)

            # Initialize loop index to 0.
            index_target = self.assign(s.index, IntExpr(0))
            self.add(Goto(top))

            # Add loop condition check.
            self.activate_block(top)
            index_reg = self.read_from_target(index_target, s.line)
            comparison = self.binary_op(index_reg, end_reg, '<', s.line)
            self.add_bool_branch(comparison, body, next)

            self.activate_block(body)
            s.body.accept(self)

            self.goto_and_activate(end_block)

            # Increment index register.
            one_reg = self.add(LoadInt(1))
            self.assign_to_target(index_target,
                                  self.binary_op(index_reg, one_reg, '+', s.line), s.line)

            # Go back to loop condition check.
            self.add(Goto(top))
            self.activate_block(next)

            self.pop_loop_stack()
            return INVALID_VALUE

        elif is_list_rprimitive(self.node_type(s.expr)):
            body_block, next_block, end_block = BasicBlock(), BasicBlock(), BasicBlock()

            self.push_loop_stack(end_block, next_block)

            expr_reg = self.accept(s.expr)

            index_reg = self.alloc_temp(int_rprimitive)
            self.add(Assign(index_reg, self.add(LoadInt(0))))

            one_reg = self.add(LoadInt(1))

            assert isinstance(s.index, NameExpr)
            assert isinstance(s.index.node, Var)
            lvalue = self.environment.add_local_reg(s.index.node, self.node_type(s.index))

            condition_block = self.goto_new_block()

            # For compatibility with python semantics we recalculate the length
            # at every iteration.
            len_reg = self.add(PrimitiveOp([expr_reg], list_len_op, s.line))

            comparison = self.binary_op(index_reg, len_reg, '<', s.line)
            self.add_bool_branch(comparison, body_block, next_block)

            self.activate_block(body_block)
            target_list_type = self.types[s.expr]
            assert isinstance(target_list_type, Instance)
            target_type = self.type_to_rtype(target_list_type.args[0])
            value_box = self.add(PrimitiveOp([expr_reg, index_reg], list_get_item_op, s.line))

            self.assign_to_target(lvalue,
                                  self.unbox_or_cast(value_box, target_type, s.line), s.line)

            s.body.accept(self)

            self.goto_and_activate(end_block)
            self.add(Assign(index_reg, self.binary_op(index_reg, one_reg, '+', s.line)))
            self.add(Goto(condition_block))

            self.activate_block(next_block)

            self.pop_loop_stack()

            return INVALID_VALUE

        else:
            body_block, end_block, next_block = BasicBlock(), BasicBlock(), BasicBlock()

            self.push_loop_stack(next_block, end_block)

            assert isinstance(s.index, NameExpr)
            assert isinstance(s.index.node, Var)
            lvalue = self.environment.add_local_reg(s.index.node, object_rprimitive)

            # Define registers to contain the expression, along with the iterator that will be used
            # for the for-loop.
            expr_reg = self.accept(s.expr)
            iter_reg = self.add(PrimitiveOp([expr_reg], iter_op, s.line))

            # Create a block for where the __next__ function will be called on the iterator and
            # checked to see if the value returned is NULL, which would signal either the end of
            # the Iterable being traversed or an exception being raised. Note that Branch.IS_ERROR
            # checks only for NULL (an exception does not necessarily have to be raised).
            self.goto_and_activate(next_block)
            next_reg = self.add(PrimitiveOp([iter_reg], next_op, s.line))
            self.add(Branch(next_reg, end_block, body_block, Branch.IS_ERROR))

            # Create a new block for the body of the loop. Set the previous branch to go here if
            # the conditional evaluates to false. Assign the value obtained from __next__ to the
            # lvalue so that it can be referenced by code in the body of the loop. At the end of
            # the body, goto the label that calls the iterator's __next__ function again.
            self.activate_block(body_block)
            self.assign_to_target(lvalue, next_reg, s.line)
            s.body.accept(self)
            self.add(Goto(next_block))

            # Create a new block for when the loop is finished. Set the branch to go here if the
            # conditional evaluates to true. If an exception was raised during the loop, then
            # err_reg wil be set to True. If no_err_occurred_op returns False, then the exception
            # will be propagated using the ERR_FALSE flag.
            self.activate_block(end_block)
            self.add(PrimitiveOp([], no_err_occurred_op, s.line))

            self.pop_loop_stack()

            return INVALID_VALUE

    def visit_break_stmt(self, node: BreakStmt) -> Value:
        self.nonlocal_control[-1].gen_break(self)
        return INVALID_VALUE

    def visit_continue_stmt(self, node: ContinueStmt) -> Value:
        self.nonlocal_control[-1].gen_continue(self)
        return INVALID_VALUE

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
                    target = self.add(PrimitiveOp([], none_op, line))
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
        target_reg = self.translate_special_method_call(
            base,
            '__getitem__',
            [index_reg],
            self.node_type(expr),
            expr.line)
        if target_reg is not None:
            return target_reg

        assert False, 'Unsupported indexing operation'

    def visit_int_expr(self, expr: IntExpr) -> Value:
        if expr.value > MAX_SHORT_INT:
            return self.load_static_int(expr.value)
        return self.add(LoadInt(expr.value))

    def visit_float_expr(self, expr: FloatExpr) -> Value:
        return self.load_static_float(expr.value)

    def is_native_ref_expr(self, expr: RefExpr) -> bool:
        if expr.node is None:
            return False
        if '.' in expr.node.fullname():
            module_name = '.'.join(expr.node.fullname().split('.')[:-1])
            return module_name in self.modules
        return True

    def is_native_module_ref_expr(self, expr: RefExpr) -> bool:
        return self.is_native_ref_expr(expr) and expr.kind == GDEF

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
                return self.read_from_target(self.environment.lookup(expr.node), expr.line)
            except KeyError:
                # If there is a KeyError, then the target could not be found in the current scope.
                # Search environment stack to see if the target was defined in an outer scope.
                return self.read_from_target(self.get_assignment_target(expr), expr.line)
        else:
            return self.load_global(expr)

    def is_module_member_expr(self, expr: MemberExpr) -> bool:
        return isinstance(expr.expr, RefExpr) and expr.expr.kind == MODULE_REF

    def visit_member_expr(self, expr: MemberExpr) -> Value:
        if self.is_module_member_expr(expr):
            return self.load_module_attr(expr)
        else:
            obj = self.accept(expr.expr)
            if isinstance(obj.type, RInstance):
                return self.add(GetAttr(obj, expr.name, expr.line))
            else:
                return self.py_get_attr(obj, expr.name, expr.line)

    def py_get_attr(self, obj: Value, attr: str, line: int) -> Value:
        key = self.load_static_unicode(attr)
        return self.add(PrimitiveOp([obj, key], py_getattr_op, line))

    def py_call(self, function: Value, args: List[Value], line: int) -> Value:
        arg_boxes = [self.box(arg) for arg in args]  # type: List[Value]
        return self.add(PrimitiveOp([function] + arg_boxes, py_call_op, line))

    def py_method_call(self, obj: Value, method: Value, args: List[Value], line: int) -> Value:
        arg_boxes = [self.box(arg) for arg in args]  # type: List[Value]
        return self.add(PrimitiveOp([obj, method] + arg_boxes, py_method_call_op, line))

    def coerce_native_call_args(self,
                                args: Sequence[Value],
                                arg_types: Sequence[RType],
                                line: int) -> List[Value]:
        coerced_arg_regs = []
        for reg, arg_type in zip(args, arg_types):
            coerced_arg_regs.append(self.coerce(reg, arg_type, line))
        return coerced_arg_regs

    def visit_call_expr(self, expr: CallExpr) -> Value:
        if isinstance(expr.analyzed, CastExpr):
            return self.translate_cast_expr(expr.analyzed)

        callee = expr.callee
        if isinstance(callee, IndexExpr) and isinstance(callee.analyzed, TypeApplication):
            callee = callee.analyzed.expr  # Unwrap type application

        if isinstance(callee, MemberExpr):
            if self.is_native_ref_expr(callee):
                # Call to module-level function or such
                return self.translate_call(expr, callee)
            else:
                return self.translate_method_call(expr, callee)
        else:
            return self.translate_call(expr, callee)

    def translate_call(self, expr: CallExpr, callee: Expression) -> Value:
        """Translate a non-method call."""
        assert isinstance(callee, RefExpr)  # TODO: Allow arbitrary callees

        # Gen the args
        fullname = callee.fullname
        args = [self.accept(arg) for arg in expr.args]

        if fullname == 'builtins.len' and len(expr.args) == 1 and expr.arg_kinds == [ARG_POS]:
            expr_rtype = args[0].type
            if isinstance(expr_rtype, RTuple):
                # len() of fixed-length tuple can be trivially determined statically.
                return self.add(LoadInt(len(expr_rtype.types)))
        if (fullname == 'builtins.isinstance'
                and len(expr.args) == 2
                and expr.arg_kinds == [ARG_POS, ARG_POS]
                and isinstance(expr.args[1], RefExpr)
                and isinstance(expr.args[1].node, TypeInfo)
                and self.is_native_module_ref_expr(expr.args[1])):
            # Special case native isinstance() checks as this makes them much faster.
            return self.primitive_op(fast_isinstance_op, args, expr.line)

        # Handle data-driven special-cased primitive call ops.
        if fullname is not None and expr.arg_kinds == [ARG_POS] * len(args):
            ops = func_ops.get(fullname, [])
            target = self.matching_primitive_op(ops, args, expr.line)
            if target:
                return target

        fn = callee.fullname
        # Try to generate a native call. Don't rely on the inferred callee
        # type, since it may have type variable substitutions that aren't
        # valid at runtime (due to type erasure). Instead pick the declared
        # signature of the native function as the true signature.
        signature = self.get_native_signature(callee)
        if signature and fn:
            # Native call
            arg_types = [self.type_to_rtype(arg_type) for arg_type in signature.arg_types]
            args = self.coerce_native_call_args(args, arg_types, expr.line)
            ret_type = self.type_to_rtype(signature.ret_type)
            return self.add(Call(ret_type, fn, args, expr.line))
        else:
            # Fall back to a Python call
            function = self.accept(callee)
            return self.py_call(function, args, expr.line)

    def get_native_signature(self, callee: RefExpr) -> Optional[CallableType]:
        """Get the signature of a native function, or return None if not available.

        This only works for normal functions, not methods.
        """
        signature = None
        if self.is_native_module_ref_expr(callee):
            node = callee.node
            if isinstance(node, TypeInfo):
                node = node['__init__'].node
                if isinstance(node, FuncDef) and isinstance(node.type, CallableType):
                    signature = bind_self(node.type)
                    # "__init__" has None return, but the type object returns
                    # in instance.  Take the instance return type from the
                    # inferred callee type, which we can trust since it can't
                    # be erased from a type variable.
                    inferred_sig = self.types[callee]
                    assert isinstance(inferred_sig, CallableType)
                    signature = signature.copy_modified(ret_type=inferred_sig.ret_type)
            elif isinstance(node, FuncDef) and isinstance(node.type, CallableType):
                signature = node.type
        return signature

    def translate_method_call(self, expr: CallExpr, callee: MemberExpr) -> Value:
        if self.is_module_member_expr(callee):
            # Fall back to a PyCall for module calls
            function = self.accept(callee)
            args = [self.accept(arg) for arg in expr.args]
            return self.py_call(function, args, expr.line)
        else:
            obj = self.accept(callee.expr)
            args = [self.accept(arg) for arg in expr.args]
            assert callee.expr in self.types
            receiver_rtype = self.node_type(callee.expr)

            # First try to do a special-cased method call
            target = self.translate_special_method_call(
                obj, callee.name, args, self.node_type(expr), expr.line)
            if target:
                return target

            # If the base type is one of ours, do a MethodCall
            if isinstance(receiver_rtype, RInstance):
                # Look up the declared signature of the method, since the
                # inferred signature can have type variable substitutions which
                # aren't valid at runtime due to type erasure.
                typ = self.types[callee.expr]
                assert isinstance(typ, Instance)
                method = typ.type.get(callee.name)
                if method and isinstance(method.node, FuncDef) and isinstance(method.node.type,
                                                                              CallableType):
                    sig = method.node.type
                    arg_types = [self.type_to_rtype(arg_type)
                                 for arg_type in sig.arg_types[1:]]
                    arg_regs = self.coerce_native_call_args(args, arg_types, expr.line)
                    target_type = self.type_to_rtype(sig.ret_type)
                    return self.add(MethodCall(target_type, obj, callee.name,
                                               arg_regs, expr.line))

            # Fall back to Python method call
            method_name = self.load_static_unicode(callee.name)
            return self.py_method_call(obj, method_name, args, expr.line)

    def translate_cast_expr(self, expr: CastExpr) -> Value:
        src = self.accept(expr.expr)
        target_type = self.type_to_rtype(expr.type)
        return self.coerce(src, target_type, expr.line)

    def shortcircuit_expr(self, expr: OpExpr) -> Value:
        expr_type = self.node_type(expr)
        # Having actual Phi nodes would be really nice here!
        target = self.alloc_temp(expr_type)
        left_body, right_body, next = BasicBlock(), BasicBlock(), BasicBlock()
        true_body, false_body = (
            (right_body, left_body) if expr.op == 'and' else (left_body, right_body))

        left_value = self.accept(expr.left)
        self.add_bool_branch(left_value, true_body, false_body)

        self.activate_block(left_body)
        left_coerced = self.coerce(left_value, expr_type, expr.line)
        self.add(Assign(target, left_coerced))
        self.add(Goto(next))

        self.activate_block(right_body)
        right_value = self.accept(expr.right)
        right_coerced = self.coerce(right_value, expr_type, expr.line)
        self.add(Assign(target, right_coerced))
        self.add(Goto(next))

        self.activate_block(next)
        return target

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
        self.add(Goto(next))

        self.activate_block(else_body)
        false_value = self.accept(expr.else_expr)
        false_value = self.coerce(false_value, expr_type, expr.line)
        self.add(Assign(target, false_value))
        self.add(Goto(next))

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
        assert isinstance(tuple_type, RTuple)

        items = []
        for item_expr, item_type in zip(expr.items, tuple_type.types):
            reg = self.accept(item_expr)
            items.append(self.coerce(reg, item_type, item_expr.line))
        return self.add(TupleSet(items, expr.line))

    def visit_dict_expr(self, expr: DictExpr) -> Value:
        dict_reg = self.add(PrimitiveOp([], new_dict_op, expr.line))
        for key_expr, value_expr in expr.items:
            key_reg = self.accept(key_expr)
            value_reg = self.accept(value_expr)
            self.translate_special_method_call(
                dict_reg,
                '__setitem__',
                [key_reg, value_reg],
                result_type=None,
                line=expr.line)
        return dict_reg

    def visit_str_expr(self, expr: StrExpr) -> Value:
        return self.load_static_unicode(expr.value)

    # Conditional expressions

    def process_conditional(self, e: Node, true: BasicBlock, false: BasicBlock) -> None:
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

    def visit_comparison_expr(self, e: ComparisonExpr) -> Value:
        assert len(e.operators) == 1, 'more than 1 operator not supported'
        op = e.operators[0]
        negate = False
        if op == 'is not':
            op, negate = 'is', True
        elif op == 'not in':
            op, negate = 'in', True

        rhs = e.operands[1]
        if (op == 'is' and isinstance(rhs, NameExpr) and rhs.node
                and rhs.node.fullname() == 'builtins.None'):
            # Special case 'is None' checks.
            left = self.accept(e.operands[0])
            target = self.add(PrimitiveOp([left], is_none_op, e.line))
        else:
            left = self.accept(e.operands[0])
            right = self.accept(e.operands[1])
            target = self.binary_op(left, right, op, e.line)

        if negate:
            target = self.unary_op(target, 'not', e.line)
        return target

    def add_bool_branch(self, value: Value, true: BasicBlock, false: BasicBlock) -> None:
        if is_same_type(value.type, int_rprimitive):
            zero = self.add(LoadInt(0))
            value = self.binary_op(value, zero, '!=', value.line)
        elif is_same_type(value.type, list_rprimitive):
            length = self.primitive_op(list_len_op, [value], value.line)
            zero = self.add(LoadInt(0))
            value = self.binary_op(length, zero, '!=', value.line)
        elif isinstance(value.type, ROptional):
            is_none = self.binary_op(value, self.add(PrimitiveOp([], none_op, value.line)),
                                     'is not', value.line)
            branch = Branch(is_none, true, false, Branch.BOOL_EXPR)
            self.add(branch)
            value_type = value.type.value_type
            if isinstance(value_type, RInstance):
                # Optional[X] where X is always truthy
                # TODO: Support __bool__
                pass
            else:
                # Optional[X] where X may be falsey and requires a check
                branch.true = self.new_block()
                remaining = self.coerce(value, value.type.value_type, value.line)
                self.add_bool_branch(remaining, true, false)
            return
        elif not is_same_type(value.type, bool_rprimitive):
            value = self.primitive_op(bool_op, [value], value.line)
        self.add(Branch(value, true, false, Branch.BOOL_EXPR))

    def visit_nonlocal_decl(self, o: NonlocalDecl) -> Value:
        return INVALID_VALUE

    def visit_slice_expr(self, expr: SliceExpr) -> Value:
        def get_arg(arg: Optional[Expression]) -> Value:
            if arg is None:
                return self.primitive_op(none_op, [], expr.line)
            else:
                return self.accept(arg)

        args = [get_arg(expr.begin_index),
                get_arg(expr.end_index),
                get_arg(expr.stride)]
        return self.primitive_op(new_slice_op, args, expr.line)

    def visit_raise_stmt(self, s: RaiseStmt) -> Value:
        if s.expr is None:
            self.primitive_op(reraise_exception_op, [], s.line)
            self.add(Unreachable())
            return INVALID_VALUE

        assert s.expr is not None, "re-raise not implemented yet"
        assert s.from_expr is None, "from_expr not implemented"

        # TODO: Do we want to dynamically handle the case where the
        # type is Any so we don't statically know what to do?
        typ = self.types[s.expr]
        if isinstance(typ, TypeType):
            typ = typ.item
        assert not isinstance(typ, AnyType), "can't raise Any"

        if isinstance(typ, FunctionLike) and typ.is_type_obj():
            etyp = self.accept(s.expr)
            exc = self.primitive_op(py_call_op, [etyp], s.expr.line)
        else:
            exc = self.accept(s.expr)
            etyp = self.primitive_op(type_op, [exc], s.expr.line)

        self.primitive_op(raise_exception_op, [etyp, exc], s.line)
        self.add(Unreachable())
        return INVALID_VALUE

    class ExceptNonlocalControl(NonlocalControl):
        """Nonlocal control for except blocks.

        Just makes sure that sys.exc_info always gets cleared when we leave.
        This is super annoying.
        """
        def __init__(self, outer: NonlocalControl, line: int) -> None:
            self.outer = outer
            self.line = line

        def gen_cleanup(self, builder: 'IRBuilder') -> None:
            # TODO: skip generating the clear if we just generated one
            builder.primitive_op(clear_exc_info_op, [], self.line)

        def gen_break(self, builder: 'IRBuilder') -> None:
            self.gen_cleanup(builder)
            self.outer.gen_break(builder)

        def gen_continue(self, builder: 'IRBuilder') -> None:
            self.gen_cleanup(builder)
            self.outer.gen_continue(builder)

        def gen_return(self, builder: 'IRBuilder', value: Value) -> None:
            self.outer.gen_return(builder, value)

    def visit_try_stmt(self, t: TryStmt) -> Value:
        assert len(t.handlers) == 1 and t.types[0] is None and t.vars[0] is None, (
            "Only bare except supported")
        assert not t.else_body, "try/else not implemented"
        assert not t.finally_body, "try/finally not implemented"

        except_entry, exit_block = BasicBlock(), BasicBlock()

        # Compile the try block with an error handler
        self.error_handlers.append(except_entry)
        self.goto_and_activate(BasicBlock())
        self.accept(t.body)
        self.add(Goto(exit_block))
        self.error_handlers.pop()

        # Compile the except block with the nonlocal control flow overridden to clear exc_info
        self.activate_block(except_entry)
        except_body = t.handlers[0]
        self.primitive_op(error_catch_op, [], except_body.line)  # TODO: use this value

        self.nonlocal_control.append(
            IRBuilder.ExceptNonlocalControl(self.nonlocal_control[-1], except_body.line))
        self.accept(except_body)
        self.nonlocal_control.pop()

        self.primitive_op(clear_exc_info_op, [], except_body.line)
        self.add(Goto(exit_block))

        self.activate_block(exit_block)

        return INVALID_VALUE

    def visit_lambda_expr(self, expr: LambdaExpr) -> Value:
        typ = self.types[expr]
        assert isinstance(typ, CallableType)

        runtime_args = []
        for arg, arg_type in zip(expr.arguments, typ.arg_types):
            arg.variable.type = arg_type
            runtime_args.append(RuntimeArg(arg.variable.name(), self.type_to_rtype(arg_type)))
        ret_type = self.type_to_rtype(typ.ret_type)

        fsig = FuncSignature(runtime_args, ret_type)

        fname = '__mypyc_lambda_{}__'.format(self.lambda_counter)
        func_ir, func_reg = self.gen_func_def(expr, fname, fsig)

        self.functions.append(func_ir)
        return func_reg

    def visit_pass_stmt(self, o: PassStmt) -> Value:
        return INVALID_VALUE

    def visit_global_decl(self, o: GlobalDecl) -> Value:
        # Pure declaration -- no runtime effect
        return INVALID_VALUE

    def visit_assert_stmt(self, a: AssertStmt) -> Value:
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
            exc = self.primitive_op(py_call_op, [exc_type, message], a.line)
            self.primitive_op(raise_exception_op, [exc_type, exc], a.line)
        self.add(Unreachable())
        self.activate_block(ok_block)
        return INVALID_VALUE

    def visit_cast_expr(self, o: CastExpr) -> Value:
        assert False, "CastExpr handled in CallExpr"

    # Unimplemented constructs
    # TODO: some of these are actually things that should never show up,
    # so properly sort those out.
    def visit__promote_expr(self, o: PromoteExpr) -> Value:
        raise NotImplementedError

    def visit_await_expr(self, o: AwaitExpr) -> Value:
        raise NotImplementedError

    def visit_backquote_expr(self, o: BackquoteExpr) -> Value:
        raise NotImplementedError

    def visit_bytes_expr(self, o: BytesExpr) -> Value:
        raise NotImplementedError

    def visit_complex_expr(self, o: ComplexExpr) -> Value:
        raise NotImplementedError

    def visit_decorator(self, o: Decorator) -> Value:
        raise NotImplementedError

    def visit_del_stmt(self, o: DelStmt) -> Value:
        raise NotImplementedError

    def visit_dictionary_comprehension(self, o: DictionaryComprehension) -> Value:
        raise NotImplementedError

    def visit_ellipsis(self, o: EllipsisExpr) -> Value:
        raise NotImplementedError

    def visit_enum_call_expr(self, o: EnumCallExpr) -> Value:
        raise NotImplementedError

    def visit_exec_stmt(self, o: ExecStmt) -> Value:
        raise NotImplementedError

    def visit_generator_expr(self, o: GeneratorExpr) -> Value:
        raise NotImplementedError

    def visit_list_comprehension(self, o: ListComprehension) -> Value:
        raise NotImplementedError

    def visit_set_comprehension(self, o: SetComprehension) -> Value:
        raise NotImplementedError

    def visit_namedtuple_expr(self, o: NamedTupleExpr) -> Value:
        raise NotImplementedError

    def visit_newtype_expr(self, o: NewTypeExpr) -> Value:
        raise NotImplementedError

    def visit_overloaded_func_def(self, o: OverloadedFuncDef) -> Value:
        raise NotImplementedError

    def visit_print_stmt(self, o: PrintStmt) -> Value:
        raise NotImplementedError

    def visit_reveal_expr(self, o: RevealExpr) -> Value:
        raise NotImplementedError

    def visit_set_expr(self, o: SetExpr) -> Value:
        raise NotImplementedError

    def visit_star_expr(self, o: StarExpr) -> Value:
        raise NotImplementedError

    def visit_super_expr(self, o: SuperExpr) -> Value:
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

    def visit_var(self, o: Var) -> Value:
        raise NotImplementedError

    def visit_with_stmt(self, o: WithStmt) -> Value:
        raise NotImplementedError

    def visit_yield_from_expr(self, o: YieldFromExpr) -> Value:
        raise NotImplementedError

    def visit_yield_expr(self, o: YieldExpr) -> Value:
        raise NotImplementedError

    # Helpers

    def enter(self, fn_info: FuncInfo) -> None:
        self.environment = Environment(fn_info.name)
        self.environments.append(self.environment)
        self.fn_info = fn_info
        self.fn_infos.append(self.fn_info)
        self.ret_types.append(none_rprimitive)
        self.error_handlers.append(None)
        self.nonlocal_control.append(BaseNonlocalControl())
        self.blocks.append([])
        self.new_block()

    def activate_block(self, block: BasicBlock) -> None:
        block.error_handler = self.error_handlers[-1]
        self.blocks[-1].append(block)

    def goto_and_activate(self, block: BasicBlock) -> None:
        self.add(Goto(block))
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
        self.blocks[-1][-1].ops.append(op)
        if isinstance(op, RegisterOp):
            self.environment.add_op(op)
        return op

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

    def accept(self, node: Node) -> Value:
        res = node.accept(self)
        if isinstance(node, Expression):
            assert res != INVALID_VALUE
            res = self.coerce(res, self.node_type(node), node.line)
        return res

    def alloc_temp(self, type: RType) -> Register:
        return self.environment.add_temp(type)

    def type_to_rtype(self, typ: Type) -> RType:
        return self.mapper.type_to_rtype(typ)

    def node_type(self, node: Expression) -> RType:
        if isinstance(node, IntExpr):
            # TODO: Don't special case IntExpr
            return int_rprimitive
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

    def load_env_registers(self) -> None:
        """Loads the registers for a given FuncDef.

        Adds the arguments of the FuncDef to the environment. If the FuncDef is nested inside of
        another function, then this also loads all of the outer environments of the FuncDef into
        registers so that they can be used when accessing free variables.
        """
        self.add_args_to_env(local=True)

        if self.fn_info.is_nested:
            index = len(self.environments) - 2

            # Load the first outer environment. This one is special because it gets saved in the
            # FuncInfo instance's prev_env_reg field.
            if index > 1:
                outer_env = self.environments[index]
                self.fn_info.prev_env_reg = self.load_outer_env(self.fn_info.self_reg, outer_env)
                index -= 1

            # Load the remaining outer environments into registers.
            env_reg = self.fn_info.prev_env_reg
            while index > 1:
                outer_env = self.environments[index]
                env_reg = self.load_outer_env(env_reg, outer_env)
                index -= 1

    def add_args_to_env(self, local: bool = True) -> None:
        fitem = self.fn_info.fitem
        if local:
            for arg in fitem.arguments:
                assert arg.variable.type, "Function argument missing type"
                rtype = self.type_to_rtype(arg.variable.type)
                self.environment.add_local_reg(arg.variable, rtype, is_arg=True)
        else:
            for arg in fitem.arguments:
                assert arg.variable.type, "Function argument missing type"

                # If the variable is not a free symbol, then we keep it in a local register.
                # Otherwise, we load them into environment classes below.
                if not self.is_free_variable(arg.variable):
                    continue

                # First, define the variable name as an attribute of the environment class, and
                # then construct a target for that attribute.
                rtype = self.type_to_rtype(arg.variable.type)
                self.fn_info.env_class.attributes[arg.variable.name()] = rtype
                attr_target = AssignmentTargetAttr(self.fn_info.env_reg, arg.variable.name())

                # Read the local definition of the variable, and set the corresponding attribute of
                # the environment class' variable to be that value.
                var = self.read_from_target(self.environment.lookup(arg.variable), fitem.line)
                self.add(SetAttr(self.fn_info.env_reg, arg.variable.name(), var, fitem.line))

                # Override the local definition of the variable to instead point at the variable in
                # the environment class.
                self.environment.add_target(arg.variable, attr_target)

    def gen_func_ns(self) -> str:
        """Generates a namespace for a nested function using its outer function names."""
        return '_'.join(env.name for env in self.environments
                        if env.name and env.name != '<top level>')

    def setup_callable_class(self) -> ClassIR:
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
        #         def foo():
        #             return True
        #     else:
        #         def foo():
        #             return False
        name = '{}_{}_obj'.format(self.fn_info.name, self.fn_info.ns)
        count = 0
        while name in self.callable_class_names:
            name += '_' + str(count)
        self.callable_class_names.add(name)

        # Define the actual callable class ClassIR, and set its environment to point at the
        # previously defined environment class.
        callable_class = ClassIR(name, self.module_name)
        callable_class.attributes[ENV_ATTR_NAME] = RInstance(self.fn_infos[-2].env_class)
        callable_class.mro = [callable_class]
        self.fn_info.callable_class = callable_class
        self.classes.append(callable_class)

        # Add a 'self' variable to the callable class' environment, and store that variable in a
        # register to be accessed later.
        self_target = self.environment.add_local_reg(Var('self'),
                                                     RInstance(callable_class),
                                                     is_arg=True)
        self.fn_info.self_reg = self.read_from_target(self_target, self.fn_info.fitem.line)
        return callable_class

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
        call = FuncIR('__call__', fn_info.callable_class.name, self.module_name, sig, blocks, env)
        fn_info.callable_class.methods['__call__'] = call
        return call

    def instantiate_callable_class(self, fn_info: FuncInfo) -> Value:
        """Assigns a callable class to a register named after the given function definition."""
        fitem = fn_info.fitem

        fullname = '{}.{}'.format(self.module_name, fn_info.callable_class.name)
        func_reg = self.add(Call(RInstance(fn_info.callable_class), fullname, [], fitem.line))

        # Set the callable class' environment attribute to point at the environment class
        # defined in the callable class' immediate outer scope.
        self.add(SetAttr(func_reg, ENV_ATTR_NAME, self.fn_info.env_reg, fitem.line))
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
            # If the function is nested, its environment class must contain and environment
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
        self.add_args_to_env(local=False)

    def instantiate_env_class(self) -> Value:
        """Assigns an environment class to a register named after the given function definition."""
        fullname = '{}.{}'.format(self.module_name, self.fn_info.env_class.name)
        self.fn_info.env_reg = self.add(Call(RInstance(self.fn_info.env_class), fullname, [],
                                             self.fn_info.fitem.line))

        if self.fn_info.is_nested:
            self.add(SetAttr(self.fn_info.env_reg, ENV_ATTR_NAME, self.fn_info.prev_env_reg,
                             self.fn_info.fitem.line))

        return self.fn_info.env_reg

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
        if self.is_native_module_ref_expr(expr) and isinstance(expr.node, TypeInfo):
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

    def coerce(self, src: Value, target_type: RType, line: int) -> Value:
        """Generate a coercion/cast from one type to other (only if needed).

        For example, int -> object boxes the source int; int -> int emits nothing;
        object -> int unboxes the object. All conversions preserve object value.

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
        return src
