"""Transform a mypy AST to the IR form (Intermediate Representation).

For example, consider a function like this:

   def f(x: int) -> int:
       return x * 2 + 1

It would be translated to something that conceptually looks like this:

   r0 = 2
   r1 = 1
   r2 = x * r0 :: int
   r3 = r2 + r1 :: int
   return r3
"""
from typing import (
    TypeVar, Callable, Dict, List, Tuple, Optional, Union, Sequence, Set, Any, Iterable, cast
)
from typing_extensions import overload, NoReturn
from collections import OrderedDict
from abc import abstractmethod
import importlib.util
import itertools

from mypy.build import Graph
from mypy.nodes import (
    MypyFile, SymbolNode, Statement, FuncItem, FuncDef, ReturnStmt, AssignmentStmt, OpExpr,
    IntExpr, NameExpr, LDEF, Var, IfStmt, UnaryExpr, ComparisonExpr, WhileStmt, CallExpr,
    IndexExpr, Block, Expression, ListExpr, ExpressionStmt, MemberExpr, ForStmt, RefExpr, Lvalue,
    BreakStmt, ContinueStmt, ConditionalExpr, OperatorAssignmentStmt, TupleExpr, ClassDef,
    TypeInfo, Import, ImportFrom, ImportAll, DictExpr, StrExpr, CastExpr, TempNode,
    PassStmt, PromoteExpr, AssignmentExpr, AwaitExpr, BackquoteExpr, AssertStmt, BytesExpr,
    ComplexExpr, Decorator, DelStmt, DictionaryComprehension, EllipsisExpr, EnumCallExpr, ExecStmt,
    FloatExpr, GeneratorExpr, GlobalDecl, LambdaExpr, ListComprehension, SetComprehension,
    NamedTupleExpr, NewTypeExpr, NonlocalDecl, OverloadedFuncDef, PrintStmt, RaiseStmt,
    RevealExpr, SetExpr, SliceExpr, StarExpr, SuperExpr, TryStmt, TypeAliasExpr, TypeApplication,
    TypeVarExpr, TypedDictExpr, UnicodeExpr, WithStmt, YieldFromExpr, YieldExpr, GDEF, ARG_POS,
    ARG_OPT, ARG_NAMED, ARG_NAMED_OPT, ARG_STAR, ARG_STAR2, is_class_var, op_methods
)
from mypy.types import (
    Type, Instance, CallableType, NoneTyp, TupleType, UnionType, AnyType, TypeVarType, PartialType,
    TypeType, Overloaded, TypeOfAny, UninhabitedType, UnboundType, TypedDictType,
    LiteralType,
    get_proper_type,
)
from mypy.visitor import ExpressionVisitor, StatementVisitor
from mypy.checkexpr import map_actuals_to_formals
from mypy.state import strict_optional_set
from mypy.util import split_target

from mypyc.common import (
    ENV_ATTR_NAME, NEXT_LABEL_ATTR_NAME, TEMP_ATTR_NAME, LAMBDA_NAME,
    MAX_LITERAL_SHORT_INT, TOP_LEVEL_NAME, SELF_NAME, decorator_helper_name,
    FAST_ISINSTANCE_MAX_SUBCLASSES, PROPSET_PREFIX
)
from mypyc.prebuildvisitor import PreBuildVisitor
from mypyc.ops import (
    BasicBlock, AssignmentTarget, AssignmentTargetRegister, AssignmentTargetIndex,
    AssignmentTargetAttr, AssignmentTargetTuple, Environment, Op, LoadInt, RType, Value, Register,
    Return, FuncIR, Assign, Branch, Goto, RuntimeArg, Call, Box, Unbox, Cast, RTuple, Unreachable,
    TupleGet, TupleSet, ClassIR, NonExtClassInfo, RInstance, ModuleIR, ModuleIRs, GetAttr, SetAttr,
    LoadStatic, InitStatic, MethodCall, INVALID_FUNC_DEF, int_rprimitive, float_rprimitive,
    bool_rprimitive, list_rprimitive, is_list_rprimitive, dict_rprimitive, set_rprimitive,
    str_rprimitive, tuple_rprimitive, none_rprimitive, is_none_rprimitive, object_rprimitive,
    exc_rtuple,
    PrimitiveOp, ControlOp, OpDescription, RegisterOp,
    is_object_rprimitive, LiteralsMap, FuncSignature, VTableAttr, VTableMethod, VTableEntries,
    NAMESPACE_TYPE, NAMESPACE_MODULE,
    RaiseStandardError, LoadErrorValue, NO_TRACEBACK_LINE_NO, FuncDecl,
    FUNC_NORMAL, FUNC_STATICMETHOD, FUNC_CLASSMETHOD,
    RUnion, is_optional_type, optional_value_type, all_concrete_classes,
    DeserMaps,
)
from mypyc.ops_primitive import binary_ops, unary_ops, func_ops, method_ops, name_ref_ops
from mypyc.ops_list import (
    list_append_op, list_extend_op, list_len_op, new_list_op, to_list, list_pop_last
)
from mypyc.ops_tuple import list_tuple_op, new_tuple_op
from mypyc.ops_dict import (
    new_dict_op, dict_get_item_op, dict_set_item_op, dict_update_in_display_op,
)
from mypyc.ops_set import new_set_op, set_add_op, set_update_op
from mypyc.ops_misc import (
    none_op, none_object_op, true_op, false_op, iter_op, next_op, next_raw_op,
    check_stop_op, send_op, yield_from_except_op, coro_op,
    py_getattr_op, py_setattr_op, py_delattr_op, py_hasattr_op,
    py_call_op, py_call_with_kwargs_op, py_method_call_op,
    fast_isinstance_op, bool_op, new_slice_op, not_implemented_op,
    type_op, pytype_from_template_op, import_op, get_module_dict_op,
    ellipsis_op, method_new_op, type_is_op, type_object_op, py_calc_meta_op,
    dataclass_sleight_of_hand,
)
from mypyc.ops_exc import (
    raise_exception_op, raise_exception_with_tb_op, reraise_exception_op,
    error_catch_op, restore_exc_info_op, exc_matches_op, get_exc_value_op,
    get_exc_info_op, keep_propagating_op, set_stop_iteration_value,
)
from mypyc.genops_for import ForGenerator, ForRange, ForList, ForIterable, ForEnumerate, ForZip
from mypyc.rt_subtype import is_runtime_subtype
from mypyc.subtype import is_subtype
from mypyc.sametype import is_same_type, is_same_method_signature
from mypyc.crash import catch_errors
from mypyc.options import CompilerOptions
from mypyc.errors import Errors

GenFunc = Callable[[], None]
DictEntry = Tuple[Optional[Value], Value]


class UnsupportedException(Exception):
    pass


# The stubs for callable contextmanagers are busted so cast it to the
# right type...
F = TypeVar('F', bound=Callable[..., Any])
strict_optional_dec = cast(Callable[[F], F], strict_optional_set(True))


def build_type_map(mapper: 'Mapper',
                   modules: List[MypyFile],
                   graph: Graph,
                   types: Dict[Expression, Type],
                   options: CompilerOptions,
                   errors: Errors) -> None:
    # Collect all classes defined in everything we are compiling
    classes = []
    for module in modules:
        module_classes = [node for node in module.defs if isinstance(node, ClassDef)]
        classes.extend([(module, cdef) for cdef in module_classes])

    # Collect all class mappings so that we can bind arbitrary class name
    # references even if there are import cycles.
    for module, cdef in classes:
        class_ir = ClassIR(cdef.name, module.fullname, is_trait(cdef),
                           is_abstract=cdef.info.is_abstract)
        class_ir.is_ext_class = is_extension_class(cdef)
        # If global optimizations are disabled, turn of tracking of class children
        if not options.global_opts:
            class_ir.children = None
        mapper.type_to_ir[cdef.info] = class_ir

    # Populate structural information in class IR for extension classes.
    for module, cdef in classes:
        with catch_errors(module.path, cdef.line):
            if mapper.type_to_ir[cdef.info].is_ext_class:
                prepare_class_def(module.path, module.fullname, cdef, errors, mapper)
            else:
                prepare_non_ext_class_def(module.path, module.fullname, cdef, errors, mapper)

    # Collect all the functions also. We collect from the symbol table
    # so that we can easily pick out the right copy of a function that
    # is conditionally defined.
    for module in modules:
        for func in get_module_func_defs(module):
            prepare_func_def(module.fullname, None, func, mapper)
            # TODO: what else?


def load_type_map(mapper: 'Mapper',
                  modules: List[MypyFile],
                  deser_ctx: DeserMaps) -> None:
    """Populate a Mapper with deserialized IR from a list of modules."""
    for module in modules:
        for name, node in module.names.items():
            if isinstance(node.node, TypeInfo):
                ir = deser_ctx.classes[node.node.fullname]
                mapper.type_to_ir[node.node] = ir
                mapper.func_to_decl[node.node] = ir.ctor

    for module in modules:
        for func in get_module_func_defs(module):
            mapper.func_to_decl[func] = deser_ctx.functions[func.fullname].decl


@strict_optional_dec  # Turn on strict optional for any type manipulations we do
def build_ir(modules: List[MypyFile],
             graph: Graph,
             types: Dict[Expression, Type],
             mapper: 'Mapper',
             options: CompilerOptions,
             errors: Errors) -> ModuleIRs:

    build_type_map(mapper, modules, graph, types, options, errors)

    result = OrderedDict()  # type: ModuleIRs

    # Generate IR for all modules.
    class_irs = []

    for module in modules:
        # First pass to determine free symbols.
        pbv = PreBuildVisitor()
        module.accept(pbv)

        # Second pass.
        builder = IRBuilder(
            module.fullname, types, graph, errors, mapper, pbv, options
        )
        builder.visit_mypy_file(module)
        module_ir = ModuleIR(
            module.fullname,
            list(builder.imports),
            builder.functions,
            builder.classes,
            builder.final_names
        )
        result[module.fullname] = module_ir
        class_irs.extend(builder.classes)

    # Compute vtables.
    for cir in class_irs:
        if cir.is_ext_class:
            compute_vtable(cir)

    return result


def is_trait_decorator(d: Expression) -> bool:
    return isinstance(d, RefExpr) and d.fullname == 'mypy_extensions.trait'


def is_trait(cdef: ClassDef) -> bool:
    return any(is_trait_decorator(d) for d in cdef.decorators)


def is_dataclass_decorator(d: Expression) -> bool:
    return (
        (isinstance(d, RefExpr) and d.fullname == 'dataclasses.dataclass')
        or (
            isinstance(d, CallExpr)
            and isinstance(d.callee, RefExpr)
            and d.callee.fullname == 'dataclasses.dataclass'
        )
    )


def is_dataclass(cdef: ClassDef) -> bool:
    return any(is_dataclass_decorator(d) for d in cdef.decorators)


def get_mypyc_attr_literal(e: Expression) -> Any:
    """Convert an expression from a mypyc_attr decorator to a value.

    Supports a pretty limited range."""
    if isinstance(e, (StrExpr, IntExpr, FloatExpr)):
        return e.value
    elif isinstance(e, RefExpr) and e.fullname == 'builtins.True':
        return True
    elif isinstance(e, RefExpr) and e.fullname == 'builtins.False':
        return False
    elif isinstance(e, RefExpr) and e.fullname == 'builtins.None':
        return None
    return NotImplemented


def get_mypyc_attr_call(d: Expression) -> Optional[CallExpr]:
    """Check if an expression is a call to mypyc_attr and return it if so."""
    if (
        isinstance(d, CallExpr)
        and isinstance(d.callee, RefExpr)
        and d.callee.fullname == 'mypy_extensions.mypyc_attr'
    ):
        return d
    return None


def get_mypyc_attrs(stmt: Union[ClassDef, Decorator]) -> Dict[str, Any]:
    """Collect all the mypyc_attr attributes on a class definition or a function."""
    attrs = {}  # type: Dict[str, Any]
    for dec in stmt.decorators:
        d = get_mypyc_attr_call(dec)
        if d:
            for name, arg in zip(d.arg_names, d.args):
                if name is None:
                    if isinstance(arg, StrExpr):
                        attrs[arg.value] = True
                else:
                    attrs[name] = get_mypyc_attr_literal(arg)

    return attrs


def is_extension_class(cdef: ClassDef) -> bool:
    if any(
        not is_trait_decorator(d)
        and not is_dataclass_decorator(d)
        and not get_mypyc_attr_call(d)
        for d in cdef.decorators
    ):
        return False
    elif (cdef.info.metaclass_type and cdef.info.metaclass_type.type.fullname not in (
            'abc.ABCMeta', 'typing.TypingMeta', 'typing.GenericMeta')):
        return False
    return True


def get_func_def(op: Union[FuncDef, Decorator, OverloadedFuncDef]) -> FuncDef:
    if isinstance(op, OverloadedFuncDef):
        assert op.impl
        op = op.impl
    if isinstance(op, Decorator):
        op = op.func
    return op


def get_module_func_defs(module: MypyFile) -> Iterable[FuncDef]:
    """Collect all of the (non-method) functions declared in a module."""
    for name, node in module.names.items():
        # We need to filter out functions that are imported or
        # aliases.  The best way to do this seems to be by
        # checking that the fullname matches.
        if (isinstance(node.node, (FuncDef, Decorator, OverloadedFuncDef))
                and node.fullname == module.fullname + '.' + name):
            yield get_func_def(node.node)


def specialize_parent_vtable(cls: ClassIR, parent: ClassIR) -> VTableEntries:
    """Generate the part of a vtable corresponding to a parent class or trait"""
    updated = []
    for entry in parent.vtable_entries:
        if isinstance(entry, VTableMethod):
            # Find the original method corresponding to this vtable entry.
            # (This may not be the method in the entry, if it was overridden.)
            orig_parent_method = entry.cls.get_method(entry.name)
            assert orig_parent_method
            method_cls = cls.get_method_and_class(entry.name)
            if method_cls:
                child_method, defining_cls = method_cls
                # TODO: emit a wrapper for __init__ that raises or something
                if (is_same_method_signature(orig_parent_method.sig, child_method.sig)
                        or orig_parent_method.name == '__init__'):
                    entry = VTableMethod(entry.cls, entry.name, child_method, entry.shadow_method)
                else:
                    entry = VTableMethod(entry.cls, entry.name,
                                         defining_cls.glue_methods[(entry.cls, entry.name)],
                                         entry.shadow_method)
        else:
            # If it is an attribute from a trait, we need to find out
            # the real class it got mixed in at and point to that.
            if parent.is_trait:
                _, origin_cls = cls.attr_details(entry.name)
                entry = VTableAttr(origin_cls, entry.name, entry.is_setter)
        updated.append(entry)
    return updated


def compute_vtable(cls: ClassIR) -> None:
    """Compute the vtable structure for a class."""
    if cls.vtable is not None: return

    if not cls.is_generated:
        cls.has_dict = any(x.inherits_python for x in cls.mro)

    for t in cls.mro[1:]:
        # Make sure all ancestors are processed first
        compute_vtable(t)
        # Merge attributes from traits into the class
        if not t.is_trait:
            continue
        for name, typ in t.attributes.items():
            if not cls.is_trait and not any(name in b.attributes for b in cls.base_mro):
                cls.attributes[name] = typ

    cls.vtable = {}
    if cls.base:
        assert cls.base.vtable is not None
        cls.vtable.update(cls.base.vtable)
        cls.vtable_entries = specialize_parent_vtable(cls, cls.base)

    # Include the vtable from the parent classes, but handle method overrides.
    entries = cls.vtable_entries

    # Traits need to have attributes in the vtable, since the
    # attributes can be at different places in different classes, but
    # regular classes can just directly get them.
    if cls.is_trait:
        # Traits also need to pull in vtable entries for non-trait
        # parent classes explicitly.
        for t in cls.mro:
            for attr in t.attributes:
                if attr in cls.vtable:
                    continue
                cls.vtable[attr] = len(entries)
                entries.append(VTableAttr(t, attr, is_setter=False))
                entries.append(VTableAttr(t, attr, is_setter=True))

    all_traits = [t for t in cls.mro if t.is_trait]

    for t in [cls] + cls.traits:
        for fn in itertools.chain(t.methods.values()):
            # TODO: don't generate a new entry when we overload without changing the type
            if fn == cls.get_method(fn.name):
                cls.vtable[fn.name] = len(entries)
                # If the class contains a glue method referring to itself, that is a
                # shadow glue method to support interpreted subclasses.
                shadow = cls.glue_methods.get((cls, fn.name))
                entries.append(VTableMethod(t, fn.name, fn, shadow))

    # Compute vtables for all of the traits that the class implements
    if not cls.is_trait:
        for trait in all_traits:
            compute_vtable(trait)
            cls.trait_vtables[trait] = specialize_parent_vtable(cls, trait)


class Mapper:
    """Keep track of mappings from mypy concepts to IR concepts.

    This state is shared across all modules being compiled in all
    compilation groups.
    """

    def __init__(self, group_map: Dict[str, Optional[str]]) -> None:
        self.group_map = group_map
        self.type_to_ir = {}  # type: Dict[TypeInfo, ClassIR]
        self.func_to_decl = {}  # type: Dict[SymbolNode, FuncDecl]
        # LiteralsMap maps literal values to a static name. Each
        # compilation group has its own LiteralsMap. (Since they can't
        # share literals.)
        self.literals = {
            v: OrderedDict() for v in group_map.values()
        }  # type: Dict[Optional[str], LiteralsMap]

    def type_to_rtype(self, typ: Optional[Type]) -> RType:
        if typ is None:
            return object_rprimitive

        typ = get_proper_type(typ)
        if isinstance(typ, Instance):
            if typ.type.fullname == 'builtins.int':
                return int_rprimitive
            elif typ.type.fullname == 'builtins.float':
                return float_rprimitive
            elif typ.type.fullname == 'builtins.str':
                return str_rprimitive
            elif typ.type.fullname == 'builtins.bool':
                return bool_rprimitive
            elif typ.type.fullname == 'builtins.list':
                return list_rprimitive
            # Dict subclasses are at least somewhat common and we
            # specifically support them, so make sure that dict operations
            # get optimized on them.
            elif any(cls.fullname == 'builtins.dict' for cls in typ.type.mro):
                return dict_rprimitive
            elif typ.type.fullname == 'builtins.set':
                return set_rprimitive
            elif typ.type.fullname == 'builtins.tuple':
                return tuple_rprimitive  # Varying-length tuple
            elif typ.type in self.type_to_ir:
                return RInstance(self.type_to_ir[typ.type])
            else:
                return object_rprimitive
        elif isinstance(typ, TupleType):
            # Use our unboxed tuples for raw tuples but fall back to
            # being boxed for NamedTuple.
            if typ.partial_fallback.type.fullname == 'builtins.tuple':
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
            # TODO: Erase to union if object has value restriction?
            return self.type_to_rtype(typ.upper_bound)
        elif isinstance(typ, PartialType):
            assert typ.var.type is not None
            return self.type_to_rtype(typ.var.type)
        elif isinstance(typ, Overloaded):
            return object_rprimitive
        elif isinstance(typ, TypedDictType):
            return dict_rprimitive
        elif isinstance(typ, LiteralType):
            return self.type_to_rtype(typ.fallback)
        elif isinstance(typ, (UninhabitedType, UnboundType)):
            # Sure, whatever!
            return object_rprimitive

        # I think we've covered everything that is supposed to
        # actually show up, so anything else is a bug somewhere.
        assert False, 'unexpected type %s' % type(typ)

    def get_arg_rtype(self, typ: Type, kind: int) -> RType:
        if kind == ARG_STAR:
            return tuple_rprimitive
        elif kind == ARG_STAR2:
            return dict_rprimitive
        else:
            return self.type_to_rtype(typ)

    def fdef_to_sig(self, fdef: FuncDef) -> FuncSignature:
        if isinstance(fdef.type, CallableType):
            arg_types = [self.get_arg_rtype(typ, kind)
                         for typ, kind in zip(fdef.type.arg_types, fdef.type.arg_kinds)]
            ret = self.type_to_rtype(fdef.type.ret_type)
        else:
            # Handle unannotated functions
            arg_types = [object_rprimitive for arg in fdef.arguments]
            ret = object_rprimitive

        args = [RuntimeArg(arg_name, arg_type, arg_kind)
                for arg_name, arg_kind, arg_type in zip(fdef.arg_names, fdef.arg_kinds, arg_types)]

        # We force certain dunder methods to return objects to support letting them
        # return NotImplemented. It also avoids some pointless boxing and unboxing,
        # since tp_richcompare needs an object anyways.
        if fdef.name in ('__eq__', '__ne__', '__lt__', '__gt__', '__le__', '__ge__'):
            ret = object_rprimitive
        return FuncSignature(args, ret)

    def literal_static_name(self, module: str,
                            value: Union[int, float, complex, str, bytes]) -> str:
        # Literals are shared between modules in a compilation group
        # but not outside the group.
        literals = self.literals[self.group_map.get(module)]

        # Include type to distinguish between 1 and 1.0, and so on.
        key = (type(value), value)
        if key not in literals:
            if isinstance(value, str):
                prefix = 'unicode_'
            else:
                prefix = type(value).__name__ + '_'
            literals[key] = prefix + str(len(literals))
        return literals[key]


def prepare_func_def(module_name: str, class_name: Optional[str],
                     fdef: FuncDef, mapper: Mapper) -> FuncDecl:
    kind = FUNC_STATICMETHOD if fdef.is_static else (
        FUNC_CLASSMETHOD if fdef.is_class else FUNC_NORMAL)
    decl = FuncDecl(fdef.name, class_name, module_name, mapper.fdef_to_sig(fdef), kind)
    mapper.func_to_decl[fdef] = decl
    return decl


def prepare_method_def(ir: ClassIR, module_name: str, cdef: ClassDef, mapper: Mapper,
                       node: Union[FuncDef, Decorator]) -> None:
    if isinstance(node, FuncDef):
        ir.method_decls[node.name] = prepare_func_def(module_name, cdef.name, node, mapper)
    elif isinstance(node, Decorator):
        # TODO: do something about abstract methods here. Currently, they are handled just like
        # normal methods.
        decl = prepare_func_def(module_name, cdef.name, node.func, mapper)
        if not node.decorators:
            ir.method_decls[node.name] = decl
        elif isinstance(node.decorators[0], MemberExpr) and node.decorators[0].name == 'setter':
            # Make property setter name different than getter name so there are no
            # name clashes when generating C code, and property lookup at the IR level
            # works correctly.
            decl.name = PROPSET_PREFIX + decl.name
            decl.is_prop_setter = True
            ir.method_decls[PROPSET_PREFIX + node.name] = decl

        if node.func.is_property:
            assert node.func.type
            decl.is_prop_getter = True
            ir.property_types[node.name] = decl.sig.ret_type


def is_valid_multipart_property_def(prop: OverloadedFuncDef) -> bool:
    # Checks to ensure supported property decorator semantics
    if len(prop.items) == 2:
        getter = prop.items[0]
        setter = prop.items[1]
        if isinstance(getter, Decorator) and isinstance(setter, Decorator):
            if getter.func.is_property and len(setter.decorators) == 1:
                if isinstance(setter.decorators[0], MemberExpr):
                    if setter.decorators[0].name == "setter":
                        return True
    return False


def can_subclass_builtin(builtin_base: str) -> bool:
    # BaseException and dict are special cased.
    return builtin_base in (
        ('builtins.Exception', 'builtins.LookupError', 'builtins.IndexError',
        'builtins.Warning', 'builtins.UserWarning', 'builtins.ValueError',
        'builtins.object', ))


def prepare_class_def(path: str, module_name: str, cdef: ClassDef,
                      errors: Errors, mapper: Mapper) -> None:

    ir = mapper.type_to_ir[cdef.info]
    info = cdef.info

    attrs = get_mypyc_attrs(cdef)
    if attrs.get("allow_interpreted_subclasses") is True:
        ir.allow_interpreted_subclasses = True

    # We sort the table for determinism here on Python 3.5
    for name, node in sorted(info.names.items()):
        # Currenly all plugin generated methods are dummies and not included.
        if node.plugin_generated:
            continue

        if isinstance(node.node, Var):
            assert node.node.type, "Class member %s missing type" % name
            if not node.node.is_classvar and name != '__slots__':
                ir.attributes[name] = mapper.type_to_rtype(node.node.type)
        elif isinstance(node.node, (FuncDef, Decorator)):
            prepare_method_def(ir, module_name, cdef, mapper, node.node)
        elif isinstance(node.node, OverloadedFuncDef):
            # Handle case for property with both a getter and a setter
            if node.node.is_property:
                if is_valid_multipart_property_def(node.node):
                    for item in node.node.items:
                        prepare_method_def(ir, module_name, cdef, mapper, item)
                else:
                    errors.error("Unsupported property decorator semantics", path, cdef.line)

            # Handle case for regular function overload
            else:
                assert node.node.impl
                prepare_method_def(ir, module_name, cdef, mapper, node.node.impl)

    # Check for subclassing from builtin types
    for cls in info.mro:
        # Special case exceptions and dicts
        # XXX: How do we handle *other* things??
        if cls.fullname == 'builtins.BaseException':
            ir.builtin_base = 'PyBaseExceptionObject'
        elif cls.fullname == 'builtins.dict':
            ir.builtin_base = 'PyDictObject'
        elif cls.fullname.startswith('builtins.'):
            if not can_subclass_builtin(cls.fullname):
                # Note that if we try to subclass a C extension class that
                # isn't in builtins, bad things will happen and we won't
                # catch it here! But this should catch a lot of the most
                # common pitfalls.
                errors.error("Inheriting from most builtin types is unimplemented",
                             path, cdef.line)

    if ir.builtin_base:
        ir.attributes.clear()

    # Set up a constructor decl
    init_node = cdef.info['__init__'].node
    if not ir.is_trait and not ir.builtin_base and isinstance(init_node, FuncDef):
        init_sig = mapper.fdef_to_sig(init_node)

        defining_ir = mapper.type_to_ir.get(init_node.info)
        # If there is a nontrivial __init__ that wasn't defined in an
        # extension class, we need to make the constructor take *args,
        # **kwargs so it can call tp_init.
        if ((defining_ir is None or not defining_ir.is_ext_class
             or cdef.info['__init__'].plugin_generated)
                and init_node.info.fullname != 'builtins.object'):
            init_sig = FuncSignature(
                [init_sig.args[0],
                 RuntimeArg("args", tuple_rprimitive, ARG_STAR),
                 RuntimeArg("kwargs", dict_rprimitive, ARG_STAR2)],
                init_sig.ret_type)

        ctor_sig = FuncSignature(init_sig.args[1:], RInstance(ir))
        ir.ctor = FuncDecl(cdef.name, None, module_name, ctor_sig)
        mapper.func_to_decl[cdef.info] = ir.ctor

    # Set up the parent class
    bases = [mapper.type_to_ir[base.type] for base in info.bases
             if base.type in mapper.type_to_ir]
    if not all(c.is_trait for c in bases[1:]):
        errors.error("Non-trait bases must appear first in parent list", path, cdef.line)
    ir.traits = [c for c in bases if c.is_trait]

    mro = []
    base_mro = []
    for cls in info.mro:
        if cls not in mapper.type_to_ir:
            if cls.fullname != 'builtins.object':
                ir.inherits_python = True
            continue
        base_ir = mapper.type_to_ir[cls]
        if not base_ir.is_trait:
            base_mro.append(base_ir)
        mro.append(base_ir)

        if cls.defn.removed_base_type_exprs or not base_ir.is_ext_class:
            ir.inherits_python = True

    base_idx = 1 if not ir.is_trait else 0
    if len(base_mro) > base_idx:
        ir.base = base_mro[base_idx]
    ir.mro = mro
    ir.base_mro = base_mro

    for base in bases:
        if base.children is not None:
            base.children.append(ir)

    if is_dataclass(cdef):
        ir.is_augmented = True


def prepare_non_ext_class_def(path: str, module_name: str, cdef: ClassDef,
                              errors: Errors, mapper: Mapper) -> None:

    ir = mapper.type_to_ir[cdef.info]
    info = cdef.info

    for name, node in info.names.items():
        if isinstance(node.node, (FuncDef, Decorator)):
            prepare_method_def(ir, module_name, cdef, mapper, node.node)
        elif isinstance(node.node, OverloadedFuncDef):
            # Handle case for property with both a getter and a setter
            if node.node.is_property:
                if not is_valid_multipart_property_def(node.node):
                    errors.error("Unsupported property decorator semantics", path, cdef.line)
                for item in node.node.items:
                    prepare_method_def(ir, module_name, cdef, mapper, item)
            # Handle case for regular function overload
            else:
                prepare_method_def(ir, module_name, cdef, mapper, get_func_def(node.node))

    if any(
        cls in mapper.type_to_ir and mapper.type_to_ir[cls].is_ext_class for cls in info.mro
    ):
        errors.error(
            "Non-extension classes may not inherit from extension classes", path, cdef.line)


def concrete_arg_kind(kind: int) -> int:
    """Find the concrete version of an arg kind that is being passed."""
    if kind == ARG_OPT:
        return ARG_POS
    elif kind == ARG_NAMED_OPT:
        return ARG_NAMED
    else:
        return kind


class FuncInfo(object):
    """Contains information about functions as they are generated."""
    def __init__(self,
                 fitem: FuncItem = INVALID_FUNC_DEF,
                 name: str = '',
                 class_name: Optional[str] = None,
                 namespace: str = '',
                 is_nested: bool = False,
                 contains_nested: bool = False,
                 is_decorated: bool = False,
                 in_non_ext: bool = False) -> None:
        self.fitem = fitem
        self.name = name if not is_decorated else decorator_helper_name(name)
        self.class_name = class_name
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
        # These are flags denoting whether a given function is nested, contains a nested function,
        # is decorated, or is within a non-extension class.
        self.is_nested = is_nested
        self.contains_nested = contains_nested
        self.is_decorated = is_decorated
        self.in_non_ext = in_non_ext

        # TODO: add field for ret_type: RType = none_rprimitive

    def namespaced_name(self) -> str:
        return '_'.join(x for x in [self.name, self.class_name, self.ns] if x)

    @property
    def is_generator(self) -> bool:
        return self.fitem.is_generator or self.fitem.is_coroutine

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

        # Holds the arg passed to send
        self.send_arg_reg = None  # type: Optional[Value]

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


# Infrastructure for special casing calls to builtin functions in a
# programmatic way.  Most special cases should be handled using the
# data driven "primitive ops" system, but certain operations require
# special handling that has access to the AST/IR directly and can make
# decisions/optimizations based on it.
#
# For example, we use specializers to statically emit the length of a
# fixed length tuple and to emit optimized code for any/all calls with
# generator comprehensions as the argument.
#
# Specalizers are attempted before compiling the arguments to the
# function.  Specializers can return None to indicate that they failed
# and the call should be compiled normally. Otherwise they should emit
# code for the call and return a value containing the result.
#
# Specializers take three arguments: the IRBuilder, the CallExpr being
# compiled, and the RefExpr that is the left hand side of the call.
#
# Specializers can operate on methods as well, and are keyed on the
# name and RType in that case.
Specializer = Callable[['IRBuilder', CallExpr, RefExpr], Optional[Value]]

specializers = {}  # type: Dict[Tuple[str, Optional[RType]], Specializer]


def specialize_function(
        name: str, typ: Optional[RType] = None) -> Callable[[Specializer], Specializer]:
    """Decorator to register a function as being a specializer."""
    def wrapper(f: Specializer) -> Specializer:
        specializers[name, typ] = f
        return f
    return wrapper


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
    def gen_break(self, builder: 'IRBuilder', line: int) -> None: pass

    @abstractmethod
    def gen_continue(self, builder: 'IRBuilder', line: int) -> None: pass

    @abstractmethod
    def gen_return(self, builder: 'IRBuilder', value: Value, line: int) -> None: pass


class BaseNonlocalControl(NonlocalControl):
    def gen_break(self, builder: 'IRBuilder', line: int) -> None:
        assert False, "break outside of loop"

    def gen_continue(self, builder: 'IRBuilder', line: int) -> None:
        assert False, "continue outside of loop"

    def gen_return(self, builder: 'IRBuilder', value: Value, line: int) -> None:
        builder.add(Return(value))


class LoopNonlocalControl(NonlocalControl):
    def __init__(self, outer: NonlocalControl,
                 continue_block: BasicBlock, break_block: BasicBlock) -> None:
        self.outer = outer
        self.continue_block = continue_block
        self.break_block = break_block

    def gen_break(self, builder: 'IRBuilder', line: int) -> None:
        builder.add(Goto(self.break_block))

    def gen_continue(self, builder: 'IRBuilder', line: int) -> None:
        builder.add(Goto(self.continue_block))

    def gen_return(self, builder: 'IRBuilder', value: Value, line: int) -> None:
        self.outer.gen_return(builder, value, line)


class GeneratorNonlocalControl(BaseNonlocalControl):
    def gen_return(self, builder: 'IRBuilder', value: Value, line: int) -> None:
        # Assign an invalid next label number so that the next time __next__ is called, we jump to
        # the case in which StopIteration is raised.
        builder.assign(builder.fn_info.generator_class.next_label_target,
                       builder.add(LoadInt(-1)),
                       line)
        # Raise a StopIteration containing a field for the value that should be returned. Before
        # doing so, create a new block without an error handler set so that the implicitly thrown
        # StopIteration isn't caught by except blocks inside of the generator function.
        builder.error_handlers.append(None)
        builder.goto_new_block()
        # Skip creating a traceback frame when we raise here, because
        # we don't care about the traceback frame and it is kind of
        # expensive since raising StopIteration is an extremely common case.
        # Also we call a special internal function to set StopIteration instead of
        # using RaiseStandardError because the obvious thing doesn't work if the
        # value is a tuple (???).
        builder.primitive_op(set_stop_iteration_value, [value], NO_TRACEBACK_LINE_NO)
        builder.add(Unreachable())
        builder.error_handlers.pop()


class CleanupNonlocalControl(NonlocalControl):
    """Abstract nonlocal control that runs some cleanup code. """
    def __init__(self, outer: NonlocalControl) -> None:
        self.outer = outer

    @abstractmethod
    def gen_cleanup(self, builder: 'IRBuilder', line: int) -> None: ...

    def gen_break(self, builder: 'IRBuilder', line: int) -> None:
        self.gen_cleanup(builder, line)
        self.outer.gen_break(builder, line)

    def gen_continue(self, builder: 'IRBuilder', line: int) -> None:
        self.gen_cleanup(builder, line)
        self.outer.gen_continue(builder, line)

    def gen_return(self, builder: 'IRBuilder', value: Value, line: int) -> None:
        self.gen_cleanup(builder, line)
        self.outer.gen_return(builder, value, line)


class TryFinallyNonlocalControl(NonlocalControl):
    def __init__(self, target: BasicBlock) -> None:
        self.target = target
        self.ret_reg = None  # type: Optional[Register]

    def gen_break(self, builder: 'IRBuilder', line: int) -> None:
        builder.error("break inside try/finally block is unimplemented", line)

    def gen_continue(self, builder: 'IRBuilder', line: int) -> None:
        builder.error("continue inside try/finally block is unimplemented", line)

    def gen_return(self, builder: 'IRBuilder', value: Value, line: int) -> None:
        if self.ret_reg is None:
            self.ret_reg = builder.alloc_temp(builder.ret_types[-1])

        builder.add(Assign(self.ret_reg, value))
        builder.add(Goto(self.target))


class ExceptNonlocalControl(CleanupNonlocalControl):
    """Nonlocal control for except blocks.

    Just makes sure that sys.exc_info always gets restored when we leave.
    This is super annoying.
    """
    def __init__(self, outer: NonlocalControl, saved: Union[Value, AssignmentTarget]) -> None:
        super().__init__(outer)
        self.saved = saved

    def gen_cleanup(self, builder: 'IRBuilder', line: int) -> None:
        builder.primitive_op(restore_exc_info_op, [builder.read(self.saved)], line)


class FinallyNonlocalControl(CleanupNonlocalControl):
    """Nonlocal control for finally blocks.

    Just makes sure that sys.exc_info always gets restored when we
    leave and the return register is decrefed if it isn't null.
    """
    def __init__(self, outer: NonlocalControl, ret_reg: Optional[Value], saved: Value) -> None:
        super().__init__(outer)
        self.ret_reg = ret_reg
        self.saved = saved

    def gen_cleanup(self, builder: 'IRBuilder', line: int) -> None:
        # Do an error branch on the return value register, which
        # may be undefined. This will allow it to be properly
        # decrefed if it is not null. This is kind of a hack.
        if self.ret_reg:
            target = BasicBlock()
            builder.add(Branch(self.ret_reg, target, target, Branch.IS_ERROR))
            builder.activate_block(target)

        # Restore the old exc_info
        target, cleanup = BasicBlock(), BasicBlock()
        builder.add(Branch(self.saved, target, cleanup, Branch.IS_ERROR))
        builder.activate_block(cleanup)
        builder.primitive_op(restore_exc_info_op, [self.saved], line)
        builder.goto_and_activate(target)


class IRBuilder(ExpressionVisitor[Value], StatementVisitor[None]):
    def __init__(self,
                 current_module: str,
                 types: Dict[Expression, Type],
                 graph: Graph,
                 errors: Errors,
                 mapper: Mapper,
                 pbv: PreBuildVisitor,
                 options: CompilerOptions) -> None:
        self.current_module = current_module
        self.types = types
        self.graph = graph
        self.environment = Environment()
        self.environments = [self.environment]
        self.ret_types = []  # type: List[RType]
        self.blocks = []  # type: List[List[BasicBlock]]
        self.functions = []  # type: List[FuncIR]
        self.classes = []  # type: List[ClassIR]
        self.final_names = []  # type: List[Tuple[str, RType]]
        self.callable_class_names = set()  # type: Set[str]
        self.options = options

        # These variables keep track of the number of lambdas, implicit indices, and implicit
        # iterators instantiated so we avoid name conflicts. The indices and iterators are
        # instantiated from for-loops.
        self.lambda_counter = 0
        self.temp_counter = 0

        # These variables are populated from the first-pass PreBuildVisitor.
        self.free_variables = pbv.free_variables
        self.prop_setters = pbv.prop_setters
        self.encapsulating_funcs = pbv.encapsulating_funcs
        self.nested_fitems = pbv.nested_funcs.keys()
        self.fdefs_to_decorators = pbv.funcs_to_decorators

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

        self.errors = errors
        self.mapper = mapper
        # Notionally a list of all of the modules imported by the
        # module being compiled, but stored as an OrderedDict so we
        # can also do quick lookups.
        self.imports = OrderedDict()  # type: OrderedDict[str, None]

    def visit_mypy_file(self, mypyfile: MypyFile) -> None:
        if mypyfile.fullname in ('typing', 'abc'):
            # These module are special; their contents are currently all
            # built-in primitives.
            return

        self.module_path = mypyfile.path
        self.module_name = mypyfile.fullname

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
        func_ir = FuncIR(FuncDecl(TOP_LEVEL_NAME, None, self.module_name, sig), blocks, env,
                         traceback_name="<module>")
        self.functions.append(func_ir)

    def handle_ext_method(self, cdef: ClassDef, fdef: FuncDef) -> None:
        # Perform the function of visit_method for methods inside extension classes.
        name = fdef.name
        class_ir = self.mapper.type_to_ir[cdef.info]
        func_ir, func_reg = self.gen_func_item(fdef, name, self.mapper.fdef_to_sig(fdef), cdef)
        self.functions.append(func_ir)

        if self.is_decorated(fdef):
            # Obtain the the function name in order to construct the name of the helper function.
            _, _, name = fdef.fullname.rpartition('.')
            helper_name = decorator_helper_name(name)
            # Read the PyTypeObject representing the class, get the callable object
            # representing the non-decorated method
            typ = self.load_native_type_object(cdef.fullname)
            orig_func = self.py_get_attr(typ, helper_name, fdef.line)

            # Decorate the non-decorated method
            decorated_func = self.load_decorated_func(fdef, orig_func)

            # Set the callable object representing the decorated method as an attribute of the
            # extension class.
            self.primitive_op(py_setattr_op,
                              [typ, self.load_static_unicode(name), decorated_func], fdef.line)

        if fdef.is_property:
            # If there is a property setter, it will be processed after the getter,
            # We populate the optional setter field with none for now.
            assert name not in class_ir.properties
            class_ir.properties[name] = (func_ir, None)

        elif fdef in self.prop_setters:
            # The respective property getter must have been processed already
            assert name in class_ir.properties
            getter_ir, _ = class_ir.properties[name]
            class_ir.properties[name] = (getter_ir, func_ir)

        class_ir.methods[func_ir.decl.name] = func_ir

        # If this overrides a parent class method with a different type, we need
        # to generate a glue method to mediate between them.
        for base in class_ir.mro[1:]:
            if (name in base.method_decls and name != '__init__'
                    and not is_same_method_signature(class_ir.method_decls[name].sig,
                                                     base.method_decls[name].sig)):

                # TODO: Support contravariant subtyping in the input argument for
                # property setters. Need to make a special glue method for handling this,
                # similar to gen_glue_property.

                f = self.gen_glue(base.method_decls[name].sig, func_ir, class_ir, base, fdef)
                class_ir.glue_methods[(base, name)] = f
                self.functions.append(f)

        # If the class allows interpreted children, create glue
        # methods that dispatch via the Python API. These will go in a
        # "shadow vtable" that will be assigned to interpreted
        # children.
        if class_ir.allow_interpreted_subclasses:
            f = self.gen_glue(func_ir.sig, func_ir, class_ir, class_ir, fdef, do_py_ops=True)
            class_ir.glue_methods[(class_ir, name)] = f
            self.functions.append(f)

    def handle_non_ext_method(
            self, non_ext: NonExtClassInfo, cdef: ClassDef, fdef: FuncDef) -> None:
        # Perform the function of visit_method for methods inside non-extension classes.
        name = fdef.name
        func_ir, func_reg = self.gen_func_item(fdef, name, self.mapper.fdef_to_sig(fdef), cdef)
        assert func_reg is not None
        self.functions.append(func_ir)

        if self.is_decorated(fdef):
            # The undecorated method is a generated callable class
            orig_func = func_reg
            func_reg = self.load_decorated_func(fdef, orig_func)

        # TODO: Support property setters in non-extension classes
        if fdef.is_property:
            prop = self.load_module_attr_by_fullname('builtins.property', fdef.line)
            func_reg = self.py_call(prop, [func_reg], fdef.line)

        elif self.mapper.func_to_decl[fdef].kind == FUNC_CLASSMETHOD:
            cls_meth = self.load_module_attr_by_fullname('builtins.classmethod', fdef.line)
            func_reg = self.py_call(cls_meth, [func_reg], fdef.line)

        elif self.mapper.func_to_decl[fdef].kind == FUNC_STATICMETHOD:
            stat_meth = self.load_module_attr_by_fullname('builtins.staticmethod', fdef.line)
            func_reg = self.py_call(stat_meth, [func_reg], fdef.line)

        self.add_to_non_ext_dict(non_ext, name, func_reg, fdef.line)

    def visit_method(
            self, cdef: ClassDef, non_ext: Optional[NonExtClassInfo], fdef: FuncDef) -> None:
        if non_ext:
            self.handle_non_ext_method(non_ext, cdef, fdef)
        else:
            self.handle_ext_method(cdef, fdef)

    def is_constant(self, e: Expression) -> bool:
        """Check whether we allow an expression to appear as a default value.

        We don't currently properly support storing the evaluated
        values for default arguments and default attribute values, so
        we restrict what expressions we allow.  We allow literals of
        primitives types, None, and references to Final global
        variables.
        """
        return (isinstance(e, (StrExpr, BytesExpr, IntExpr, FloatExpr))
                or (isinstance(e, UnaryExpr) and e.op == '-'
                    and isinstance(e.expr, (IntExpr, FloatExpr)))
                or (isinstance(e, TupleExpr)
                    and all(self.is_constant(e) for e in e.items))
                or (isinstance(e, RefExpr) and e.kind == GDEF
                    and (e.fullname in ('builtins.True', 'builtins.False', 'builtins.None')
                         or (isinstance(e.node, Var) and e.node.is_final))))

    def generate_attr_defaults(self, cdef: ClassDef) -> None:
        """Generate an initialization method for default attr values (from class vars)"""
        cls = self.mapper.type_to_ir[cdef.info]
        if cls.builtin_base:
            return

        # Pull out all assignments in classes in the mro so we can initialize them
        # TODO: Support nested statements
        default_assignments = []
        for info in reversed(cdef.info.mro):
            if info not in self.mapper.type_to_ir:
                continue
            for stmt in info.defn.defs.body:
                if (isinstance(stmt, AssignmentStmt)
                        and isinstance(stmt.lvalues[0], NameExpr)
                        and not is_class_var(stmt.lvalues[0])
                        and not isinstance(stmt.rvalue, TempNode)):
                    if stmt.lvalues[0].name == '__slots__':
                        continue

                    # Skip type annotated assignments in dataclasses
                    if is_dataclass(cdef) and stmt.type:
                        continue

                    default_assignments.append(stmt)

        if not default_assignments:
            return

        self.enter(FuncInfo())
        self.ret_types[-1] = bool_rprimitive

        rt_args = (RuntimeArg(SELF_NAME, RInstance(cls)),)
        self_var = self.read(self.add_self_to_env(cls), -1)

        for stmt in default_assignments:
            lvalue = stmt.lvalues[0]
            assert isinstance(lvalue, NameExpr)
            if not stmt.is_final_def and not self.is_constant(stmt.rvalue):
                self.warning('Unsupported default attribute value', stmt.rvalue.line)

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

    def finish_non_ext_dict(self, non_ext: NonExtClassInfo, line: int) -> None:
        # Add __annotations__ to the class dict.
        self.primitive_op(dict_set_item_op,
                          [non_ext.dict, self.load_static_unicode('__annotations__'),
                           non_ext.anns], -1)

        # We add a __doc__ attribute so if the non-extension class is decorated with the
        # dataclass decorator, dataclass will not try to look for __text_signature__.
        # https://github.com/python/cpython/blob/3.7/Lib/dataclasses.py#L957
        filler_doc_str = 'mypyc filler docstring'
        self.add_to_non_ext_dict(
            non_ext, '__doc__', self.load_static_unicode(filler_doc_str), line)
        self.add_to_non_ext_dict(
            non_ext, '__module__', self.load_static_unicode(self.module_name), line)

    def load_non_ext_class(self, ir: ClassIR, non_ext: NonExtClassInfo, line: int) -> Value:
        cls_name = self.load_static_unicode(ir.name)

        self.finish_non_ext_dict(non_ext, line)

        class_type_obj = self.py_call(non_ext.metaclass,
                                      [cls_name, non_ext.bases, non_ext.dict],
                                      line)
        return class_type_obj

    def load_decorated_class(self, cdef: ClassDef, type_obj: Value) -> Value:
        """
        Given a decorated ClassDef and a register containing a non-extension representation of the
        ClassDef created via the type constructor, applies the corresponding decorator functions
        on that decorated ClassDef and returns a register containing the decorated ClassDef.
        """
        decorators = cdef.decorators
        dec_class = type_obj
        for d in reversed(decorators):
            decorator = d.accept(self)
            assert isinstance(decorator, Value)
            dec_class = self.py_call(decorator, [dec_class], dec_class.line)
        return dec_class

    def populate_non_ext_bases(self, cdef: ClassDef) -> Value:
        """
        Populate the base-class tuple passed to the metaclass constructor
        for non-extension classes.
        """
        ir = self.mapper.type_to_ir[cdef.info]
        bases = []
        for cls in cdef.info.mro[1:]:
            if cls.fullname == 'builtins.object':
                continue
            # Add the current class to the base classes list of concrete subclasses
            if cls in self.mapper.type_to_ir:
                base_ir = self.mapper.type_to_ir[cls]
                if base_ir.children is not None:
                    base_ir.children.append(ir)

            base = self.load_global_str(cls.name, cdef.line)
            bases.append(base)
        return self.primitive_op(new_tuple_op, bases, cdef.line)

    def add_to_non_ext_dict(self, non_ext: NonExtClassInfo,
                            key: str, val: Value, line: int) -> None:
        # Add an attribute entry into the class dict of a non-extension class.
        key_unicode = self.load_static_unicode(key)
        self.primitive_op(dict_set_item_op, [non_ext.dict, key_unicode, val], line)

    def add_non_ext_class_attr(self, non_ext: NonExtClassInfo, lvalue: NameExpr,
                               stmt: AssignmentStmt, cdef: ClassDef,
                               attr_to_cache: List[Lvalue]) -> None:
        """
        Add a class attribute to __annotations__ of a non-extension class. If the
        attribute is assigned to a value, it is also added to __dict__.
        """

        # We populate __annotations__ because dataclasses uses it to determine
        # which attributes to compute on.
        # TODO: Maybe generate more precise types for annotations
        key = self.load_static_unicode(lvalue.name)
        typ = self.primitive_op(type_object_op, [], stmt.line)
        self.primitive_op(dict_set_item_op, [non_ext.anns, key, typ], stmt.line)

        # Only add the attribute to the __dict__ if the assignment is of the form:
        # x: type = value (don't add attributes of the form 'x: type' to the __dict__).
        if not isinstance(stmt.rvalue, TempNode):
            rvalue = self.accept(stmt.rvalue)
            self.add_to_non_ext_dict(non_ext, lvalue.name, rvalue, stmt.line)
            # We cache enum attributes to speed up enum attribute lookup since they
            # are final.
            if (
                cdef.info.bases
                and cdef.info.bases[0].type.fullname == 'enum.Enum'
                # Skip "_order_", since Enum will remove it
                and lvalue.name != '_order_'
            ):
                attr_to_cache.append(lvalue)

    def find_non_ext_metaclass(self, cdef: ClassDef, bases: Value) -> Value:
        """Find the metaclass of a class from its defs and bases. """
        if cdef.metaclass:
            declared_metaclass = self.accept(cdef.metaclass)
        else:
            declared_metaclass = self.primitive_op(type_object_op, [], cdef.line)

        return self.primitive_op(py_calc_meta_op, [declared_metaclass, bases], cdef.line)

    def setup_non_ext_dict(self, cdef: ClassDef, metaclass: Value, bases: Value) -> Value:
        """
        Initialize the class dictionary for a non-extension class. This class dictionary
        is passed to the metaclass constructor.
        """

        # Check if the metaclass defines a __prepare__ method, and if so, call it.
        has_prepare = self.primitive_op(py_hasattr_op,
                                        [metaclass,
                                        self.load_static_unicode('__prepare__')], cdef.line)

        non_ext_dict = self.alloc_temp(dict_rprimitive)

        true_block, false_block, exit_block, = BasicBlock(), BasicBlock(), BasicBlock()
        self.add_bool_branch(has_prepare, true_block, false_block)

        self.activate_block(true_block)
        cls_name = self.load_static_unicode(cdef.name)
        prepare_meth = self.py_get_attr(metaclass, '__prepare__', cdef.line)
        prepare_dict = self.py_call(prepare_meth, [cls_name, bases], cdef.line)
        self.assign(non_ext_dict, prepare_dict, cdef.line)
        self.goto(exit_block)

        self.activate_block(false_block)
        self.assign(non_ext_dict, self.primitive_op(new_dict_op, [], cdef.line), cdef.line)
        self.goto(exit_block)
        self.activate_block(exit_block)

        return non_ext_dict

    def cache_class_attrs(self, attrs_to_cache: List[Lvalue], cdef: ClassDef) -> None:
        """Add class attributes to be cached to the global cache"""
        typ = self.load_native_type_object(cdef.fullname)
        for lval in attrs_to_cache:
            assert isinstance(lval, NameExpr)
            rval = self.py_get_attr(typ, lval.name, cdef.line)
            self.init_final_static(lval, rval, cdef.name)

    def dataclass_non_ext_info(self, cdef: ClassDef) -> Optional[NonExtClassInfo]:
        """Set up a NonExtClassInfo to track dataclass attributes.

        In addition to setting up a normal extension class for dataclasses,
        we also collect its class attributes like a non-extension class so
        that we can hand them to the dataclass decorator.
        """
        if is_dataclass(cdef):
            return NonExtClassInfo(
                self.primitive_op(new_dict_op, [], cdef.line),
                self.add(TupleSet([], cdef.line)),
                self.primitive_op(new_dict_op, [], cdef.line),
                self.primitive_op(type_object_op, [], cdef.line),
            )
        else:
            return None

    def dataclass_finalize(
            self, cdef: ClassDef, non_ext: NonExtClassInfo, type_obj: Value) -> None:
        """Generate code to finish instantiating a dataclass.

        This works by replacing all of the attributes on the class
        (which will be descriptors) with whatever they would be in a
        non-extension class, calling dataclass, then switching them back.

        The resulting class is an extension class and instances of it do not
        have a __dict__ (unless something else requires it).
        All methods written explicitly in the source are compiled and
        may be called through the vtable while the methods generated
        by dataclasses are interpreted and may not be.

        (If we just called dataclass without doing this, it would think that all
        of the descriptors for our attributes are default values and generate an
        incorrect constructor. We need to do the switch so that dataclass gets the
        appropriate defaults.)
        """
        self.finish_non_ext_dict(non_ext, cdef.line)
        dec = self.accept(next(d for d in cdef.decorators if is_dataclass_decorator(d)))
        self.primitive_op(
            dataclass_sleight_of_hand, [dec, type_obj, non_ext.dict, non_ext.anns], cdef.line)

    def visit_class_def(self, cdef: ClassDef) -> None:
        ir = self.mapper.type_to_ir[cdef.info]

        # We do this check here because the base field of parent
        # classes aren't necessarily populated yet at
        # prepare_class_def time.
        if any(ir.base_mro[i].base != ir. base_mro[i + 1] for i in range(len(ir.base_mro) - 1)):
            self.error("Non-trait MRO must be linear", cdef.line)

        if ir.allow_interpreted_subclasses:
            for parent in ir.mro:
                if not parent.allow_interpreted_subclasses:
                    self.error(
                        'Base class "{}" does not allow interpreted subclasses'.format(
                            parent.fullname), cdef.line)

        # Currently, we only create non-extension classes for classes that are
        # decorated or inherit from Enum. Classes decorated with @trait do not
        # apply here, and are handled in a different way.
        if ir.is_ext_class:
            # If the class is not decorated, generate an extension class for it.
            type_obj = self.allocate_class(cdef)  # type: Optional[Value]
            non_ext = None  # type: Optional[NonExtClassInfo]
            dataclass_non_ext = self.dataclass_non_ext_info(cdef)
        else:
            non_ext_bases = self.populate_non_ext_bases(cdef)
            non_ext_metaclass = self.find_non_ext_metaclass(cdef, non_ext_bases)
            non_ext_dict = self.setup_non_ext_dict(cdef, non_ext_metaclass, non_ext_bases)
            # We populate __annotations__ for non-extension classes
            # because dataclasses uses it to determine which attributes to compute on.
            # TODO: Maybe generate more precise types for annotations
            non_ext_anns = self.primitive_op(new_dict_op, [], cdef.line)
            non_ext = NonExtClassInfo(non_ext_dict, non_ext_bases, non_ext_anns, non_ext_metaclass)
            dataclass_non_ext = None
            type_obj = None

        attrs_to_cache = []  # type: List[Lvalue]

        for stmt in cdef.defs.body:
            if isinstance(stmt, OverloadedFuncDef) and stmt.is_property:
                if not ir.is_ext_class:
                    # properties with both getters and setters in non_extension
                    # classes not supported
                    self.error("Property setters not supported in non-extension classes",
                               stmt.line)
                for item in stmt.items:
                    with self.catch_errors(stmt.line):
                        self.visit_method(cdef, non_ext, get_func_def(item))
            elif isinstance(stmt, (FuncDef, Decorator, OverloadedFuncDef)):
                # Ignore plugin generated methods (since they have no
                # bodies to compile and will need to have the bodies
                # provided by some other mechanism.)
                if cdef.info.names[stmt.name].plugin_generated:
                    continue
                with self.catch_errors(stmt.line):
                    self.visit_method(cdef, non_ext, get_func_def(stmt))
            elif isinstance(stmt, PassStmt):
                continue
            elif isinstance(stmt, AssignmentStmt):
                if len(stmt.lvalues) != 1:
                    self.error("Multiple assignment in class bodies not supported", stmt.line)
                    continue
                lvalue = stmt.lvalues[0]
                if not isinstance(lvalue, NameExpr):
                    self.error("Only assignment to variables is supported in class bodies",
                               stmt.line)
                    continue
                # We want to collect class variables in a dictionary for both real
                # non-extension classes and fake dataclass ones.
                var_non_ext = non_ext or dataclass_non_ext
                if var_non_ext:
                    self.add_non_ext_class_attr(var_non_ext, lvalue, stmt, cdef, attrs_to_cache)
                    if non_ext:
                        continue
                # Variable declaration with no body
                if isinstance(stmt.rvalue, TempNode):
                    continue
                # Only treat marked class variables as class variables.
                if not (is_class_var(lvalue) or stmt.is_final_def):
                    continue
                typ = self.load_native_type_object(cdef.fullname)
                value = self.accept(stmt.rvalue)
                self.primitive_op(
                    py_setattr_op, [typ, self.load_static_unicode(lvalue.name), value], stmt.line)
                if self.non_function_scope() and stmt.is_final_def:
                    self.init_final_static(lvalue, value, cdef.name)
            elif isinstance(stmt, ExpressionStmt) and isinstance(stmt.expr, StrExpr):
                # Docstring. Ignore
                pass
            else:
                self.error("Unsupported statement in class body", stmt.line)

        if not non_ext:  # That is, an extension class
            self.generate_attr_defaults(cdef)
            self.create_ne_from_eq(cdef)
            if dataclass_non_ext:
                assert type_obj
                self.dataclass_finalize(cdef, dataclass_non_ext, type_obj)
        else:
            # Dynamically create the class via the type constructor
            non_ext_class = self.load_non_ext_class(ir, non_ext, cdef.line)
            non_ext_class = self.load_decorated_class(cdef, non_ext_class)

            # Save the decorated class
            self.add(InitStatic(non_ext_class, cdef.name, self.module_name, NAMESPACE_TYPE))

            # Add the non-extension class to the dict
            self.primitive_op(dict_set_item_op,
                              [self.load_globals_dict(), self.load_static_unicode(cdef.name),
                               non_ext_class], cdef.line)

            # Cache any cachable class attributes
            self.cache_class_attrs(attrs_to_cache, cdef)

            # Set this attribute back to None until the next non-extension class is visited.
            self.non_ext_info = None

    def create_mypyc_attrs_tuple(self, ir: ClassIR, line: int) -> Value:
        attrs = [name for ancestor in ir.mro for name in ancestor.attributes]
        if ir.inherits_python:
            attrs.append('__dict__')
        return self.primitive_op(new_tuple_op,
                                 [self.load_static_unicode(attr) for attr in attrs],
                                 line)

    def allocate_class(self, cdef: ClassDef) -> Value:
        # OK AND NOW THE FUN PART
        base_exprs = cdef.base_type_exprs + cdef.removed_base_type_exprs
        if base_exprs:
            bases = [self.accept(x) for x in base_exprs]
            tp_bases = self.primitive_op(new_tuple_op, bases, cdef.line)
        else:
            tp_bases = self.add(LoadErrorValue(object_rprimitive, is_borrowed=True))
        modname = self.load_static_unicode(self.module_name)
        template = self.add(LoadStatic(object_rprimitive, cdef.name + "_template",
                                       self.module_name, NAMESPACE_TYPE))
        # Create the class
        tp = self.primitive_op(pytype_from_template_op,
                               [template, tp_bases, modname], cdef.line)
        # Immediately fix up the trait vtables, before doing anything with the class.
        ir = self.mapper.type_to_ir[cdef.info]
        if not ir.is_trait and not ir.builtin_base:
            self.add(Call(
                FuncDecl(cdef.name + '_trait_vtable_setup',
                         None, self.module_name,
                         FuncSignature([], bool_rprimitive)), [], -1))
        # Populate a '__mypyc_attrs__' field containing the list of attrs
        self.primitive_op(py_setattr_op, [
            tp, self.load_static_unicode('__mypyc_attrs__'),
            self.create_mypyc_attrs_tuple(self.mapper.type_to_ir[cdef.info], cdef.line)],
            cdef.line)

        # Save the class
        self.add(InitStatic(tp, cdef.name, self.module_name, NAMESPACE_TYPE))

        # Add it to the dict
        self.primitive_op(dict_set_item_op,
                          [self.load_globals_dict(), self.load_static_unicode(cdef.name),
                           tp], cdef.line)

        return tp

    def gen_import(self, id: str, line: int) -> None:
        self.imports[id] = None

        needs_import, out = BasicBlock(), BasicBlock()
        first_load = self.load_module(id)
        comparison = self.binary_op(first_load, self.none_object(), 'is not', line)
        self.add_bool_branch(comparison, out, needs_import)

        self.activate_block(needs_import)
        value = self.primitive_op(import_op, [self.load_static_unicode(id)], line)
        self.add(InitStatic(value, id, namespace=NAMESPACE_MODULE))
        self.goto_and_activate(out)

    def visit_import(self, node: Import) -> None:
        if node.is_mypy_only:
            return
        globals = self.load_globals_dict()
        for node_id, as_name in node.ids:
            self.gen_import(node_id, node.line)

            # Update the globals dict with the appropriate module:
            # * For 'import foo.bar as baz' we add 'foo.bar' with the name 'baz'
            # * For 'import foo.bar' we add 'foo' with the name 'foo'
            # Typically we then ignore these entries and access things directly
            # via the module static, but we will use the globals version for modules
            # that mypy couldn't find, since it doesn't analyze module references
            # from those properly.

            # Miscompiling imports inside of functions, like below in import from.
            if as_name:
                name = as_name
                base = node_id
            else:
                base = name = node_id.split('.')[0]

            # Python 3.7 has a nice 'PyImport_GetModule' function that we can't use :(
            mod_dict = self.primitive_op(get_module_dict_op, [], node.line)
            obj = self.primitive_op(dict_get_item_op,
                                    [mod_dict, self.load_static_unicode(base)], node.line)
            self.translate_special_method_call(
                globals, '__setitem__', [self.load_static_unicode(name), obj],
                result_type=None, line=node.line)

    def visit_import_from(self, node: ImportFrom) -> None:
        if node.is_mypy_only:
            return

        module_state = self.graph[self.module_name]
        if module_state.ancestors is not None and module_state.ancestors:
            module_package = module_state.ancestors[0]
        else:
            module_package = ''

        id = importlib.util.resolve_name('.' * node.relative + node.id, module_package)

        self.gen_import(id, node.line)
        module = self.load_module(id)

        # Copy everything into our module's dict.
        # Note that we miscompile import from inside of functions here,
        # since that case *shouldn't* load it into the globals dict.
        # This probably doesn't matter much and the code runs basically right.
        globals = self.load_globals_dict()
        for name, maybe_as_name in node.names:
            # If one of the things we are importing is a module,
            # import it as a module also.
            fullname = id + '.' + name
            if fullname in self.graph or fullname in module_state.suppressed:
                self.gen_import(fullname, node.line)

            as_name = maybe_as_name or name
            obj = self.py_get_attr(module, name, node.line)
            self.translate_special_method_call(
                globals, '__setitem__', [self.load_static_unicode(as_name), obj],
                result_type=None, line=node.line)

    def visit_import_all(self, node: ImportAll) -> None:
        if node.is_mypy_only:
            return
        self.gen_import(node.id, node.line)

    def gen_glue(self, sig: FuncSignature, target: FuncIR,
                 cls: ClassIR, base: ClassIR, fdef: FuncItem,
                 *,
                 do_py_ops: bool = False
                 ) -> FuncIR:
        """Generate glue methods that mediate between different method types in subclasses.

        Works on both properties and methods. See gen_glue_methods below for more details.

        If do_py_ops is True, then the glue methods should use generic
        C API operations instead of direct calls, to enable generating
        "shadow" glue methods that work with interpreted subclasses.
        """
        if fdef.is_property:
            return self.gen_glue_property(sig, target, cls, base, fdef.line, do_py_ops)
        else:
            return self.gen_glue_method(sig, target, cls, base, fdef.line, do_py_ops)

    def gen_glue_method(self, sig: FuncSignature, target: FuncIR,
                        cls: ClassIR, base: ClassIR, line: int,
                        do_pycall: bool,
                        ) -> FuncIR:
        """Generate glue methods that mediate between different method types in subclasses.

        For example, if we have:

        class A:
            def f(self, x: int) -> object: ...

        then it is totally permissible to have a subclass

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

        If do_pycall is True, then make the call using the C API
        instead of a native call.
        """
        self.enter(FuncInfo())
        self.ret_types[-1] = sig.ret_type

        rt_args = list(sig.args)
        if target.decl.kind == FUNC_NORMAL:
            rt_args[0] = RuntimeArg(sig.args[0].name, RInstance(cls))

        # The environment operates on Vars, so we make some up
        fake_vars = [(Var(arg.name), arg.type) for arg in rt_args]
        args = [self.read(self.environment.add_local_reg(var, type, is_arg=True), line)
                for var, type in fake_vars]
        arg_names = [arg.name for arg in rt_args]
        arg_kinds = [concrete_arg_kind(arg.kind) for arg in rt_args]

        if do_pycall:
            retval = self.py_method_call(
                args[0], target.name, args[1:], line, arg_kinds[1:], arg_names[1:])
        else:
            retval = self.call(target.decl, args, arg_kinds, arg_names, line)
        retval = self.coerce(retval, sig.ret_type, line)
        self.add(Return(retval))

        blocks, env, ret_type, _ = self.leave()
        return FuncIR(
            FuncDecl(target.name + '__' + base.name + '_glue',
                     cls.name, self.module_name,
                     FuncSignature(rt_args, ret_type),
                     target.decl.kind),
            blocks, env)

    def gen_glue_property(self, sig: FuncSignature, target: FuncIR, cls: ClassIR, base: ClassIR,
                          line: int,
                          do_pygetattr: bool) -> FuncIR:
        """Generate glue methods for properties that mediate between different subclass types.

        Similarly to methods, properties of derived types can be covariantly subtyped. Thus,
        properties also require glue. However, this only requires the return type to change.
        Further, instead of a method call, an attribute get is performed.

        If do_pygetattr is True, then get the attribute using the C
        API instead of a native call.
        """
        self.enter(FuncInfo())

        rt_arg = RuntimeArg(SELF_NAME, RInstance(cls))
        arg = self.read(self.add_self_to_env(cls), line)
        self.ret_types[-1] = sig.ret_type
        if do_pygetattr:
            retval = self.py_get_attr(arg, target.name, line)
        else:
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
        self.ret_types[-1] = object_rprimitive

        # If __eq__ returns NotImplemented, then __ne__ should also
        not_implemented_block, regular_block = BasicBlock(), BasicBlock()
        eqval = self.add(MethodCall(args[0], '__eq__', [args[1]], line))
        not_implemented = self.primitive_op(not_implemented_op, [], line)
        self.add(Branch(
            self.binary_op(eqval, not_implemented, 'is', line),
            not_implemented_block,
            regular_block,
            Branch.BOOL_EXPR))

        self.activate_block(regular_block)
        retval = self.coerce(self.unary_op(eqval, 'not', line), object_rprimitive, line)
        self.add(Return(retval))

        self.activate_block(not_implemented_block)
        self.add(Return(not_implemented))

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

    def calculate_arg_defaults(self,
                               fn_info: FuncInfo,
                               env: Environment,
                               func_reg: Optional[Value]) -> None:
        """Calculate default argument values and store them.

        They are stored in statics for top level functions and in
        the function objects for nested functions (while constants are
        still stored computed on demand).
        """
        fitem = fn_info.fitem
        for arg in fitem.arguments:
            # Constant values don't get stored but just recomputed
            if arg.initializer and not self.is_constant(arg.initializer):
                value = self.coerce(self.accept(arg.initializer),
                                    env.lookup(arg.variable).type, arg.line)
                if not fn_info.is_nested:
                    name = fitem.fullname + '.' + arg.variable.name
                    self.add(InitStatic(value, name, self.module_name))
                else:
                    assert func_reg is not None
                    self.add(SetAttr(func_reg, arg.variable.name, value, arg.line))

    def gen_arg_defaults(self) -> None:
        """Generate blocks for arguments that have default values.

        If the passed value is an error value, then assign the default
        value to the argument.
        """
        fitem = self.fn_info.fitem
        for arg in fitem.arguments:
            if arg.initializer:
                target = self.environment.lookup(arg.variable)

                def get_default() -> Value:
                    assert arg.initializer is not None

                    # If it is constant, don't bother storing it
                    if self.is_constant(arg.initializer):
                        return self.accept(arg.initializer)

                    # Because gen_arg_defaults runs before calculate_arg_defaults, we
                    # add the static/attribute to final_names/the class here.
                    elif not self.fn_info.is_nested:
                        name = fitem.fullname + '.' + arg.variable.name
                        self.final_names.append((name, target.type))
                        return self.add(LoadStatic(target.type, name, self.module_name))
                    else:
                        name = arg.variable.name
                        self.fn_info.callable_class.ir.attributes[name] = target.type
                        return self.add(
                            GetAttr(self.fn_info.callable_class.self_reg, name, arg.line))
                assert isinstance(target, AssignmentTargetRegister)
                self.assign_if_null(target,
                                    get_default,
                                    arg.initializer.line)

    def gen_func_item(self,
                      fitem: FuncItem,
                      name: str,
                      sig: FuncSignature,
                      cdef: Optional[ClassDef] = None,
                      ) -> Tuple[FuncIR, Optional[Value]]:
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

        func_reg = None  # type: Optional[Value]

        # We treat lambdas as always being nested because we always generate
        # a class for lambdas, no matter where they are. (It would probably also
        # work to special case toplevel lambdas and generate a non-class function.)
        is_nested = fitem in self.nested_fitems or isinstance(fitem, LambdaExpr)
        contains_nested = fitem in self.encapsulating_funcs.keys()
        is_decorated = fitem in self.fdefs_to_decorators
        in_non_ext = False
        class_name = None
        if cdef:
            ir = self.mapper.type_to_ir[cdef.info]
            in_non_ext = not ir.is_ext_class
            class_name = cdef.name

        self.enter(FuncInfo(fitem, name, class_name, self.gen_func_ns(),
                            is_nested, contains_nested, is_decorated, in_non_ext))

        # Functions that contain nested functions need an environment class to store variables that
        # are free in their nested functions. Generator functions need an environment class to
        # store a variable denoting the next instruction to be executed when the __next__ function
        # is called, along with all the variables inside the function itself.
        if self.fn_info.contains_nested or self.fn_info.is_generator:
            self.setup_env_class()

        if self.fn_info.is_nested or self.fn_info.in_non_ext:
            self.setup_callable_class()

        if self.fn_info.is_generator:
            # Do a first-pass and generate a function that just returns a generator object.
            self.gen_generator_func()
            blocks, env, ret_type, fn_info = self.leave()
            func_ir, func_reg = self.gen_func_ir(blocks, sig, env, fn_info, cdef)

            # Re-enter the FuncItem and visit the body of the function this time.
            self.enter(fn_info)
            self.setup_env_for_generator_class()
            self.load_outer_envs(self.fn_info.generator_class)
            if self.fn_info.is_nested and isinstance(fitem, FuncDef):
                self.setup_func_for_recursive_call(fitem, self.fn_info.generator_class)
            self.create_switch_for_generator_class()
            self.add_raise_exception_blocks_to_generator_class(fitem.line)
        else:
            self.load_env_registers()
            self.gen_arg_defaults()

        if self.fn_info.contains_nested and not self.fn_info.is_generator:
            self.finalize_env_class()

        self.ret_types[-1] = sig.ret_type

        # Add all variables and functions that are declared/defined within this
        # function and are referenced in functions nested within this one to this
        # function's environment class so the nested functions can reference
        # them even if they are declared after the nested function's definition.
        # Note that this is done before visiting the body of this function.

        env_for_func = self.fn_info  # type: Union[FuncInfo, ImplicitClass]
        if self.fn_info.is_generator:
            env_for_func = self.fn_info.generator_class
        elif self.fn_info.is_nested or self.fn_info.in_non_ext:
            env_for_func = self.fn_info.callable_class

        if self.fn_info.fitem in self.free_variables:
            # Sort the variables to keep things deterministic
            for var in sorted(self.free_variables[self.fn_info.fitem], key=lambda x: x.name):
                if isinstance(var, Var):
                    rtype = self.type_to_rtype(var.type)
                    self.add_var_to_env_class(var, rtype, env_for_func, reassign=False)

        if self.fn_info.fitem in self.encapsulating_funcs:
            for nested_fn in self.encapsulating_funcs[self.fn_info.fitem]:
                if isinstance(nested_fn, FuncDef):
                    # The return type is 'object' instead of an RInstance of the
                    # callable class because differently defined functions with
                    # the same name and signature across conditional blocks
                    # will generate different callable classes, so the callable
                    # class that gets instantiated must be generic.
                    self.add_var_to_env_class(nested_fn, object_rprimitive,
                                              env_for_func, reassign=False)

        self.accept(fitem.body)
        self.maybe_add_implicit_return()

        if self.fn_info.is_generator:
            self.populate_switch_for_generator_class()

        blocks, env, ret_type, fn_info = self.leave()

        if fn_info.is_generator:
            helper_fn_decl = self.add_helper_to_generator_class(blocks, sig, env, fn_info)
            self.add_next_to_generator_class(fn_info, helper_fn_decl, sig)
            self.add_send_to_generator_class(fn_info, helper_fn_decl, sig)
            self.add_iter_to_generator_class(fn_info)
            self.add_throw_to_generator_class(fn_info, helper_fn_decl, sig)
            self.add_close_to_generator_class(fn_info)
            if fitem.is_coroutine:
                self.add_await_to_generator_class(fn_info)

        else:
            func_ir, func_reg = self.gen_func_ir(blocks, sig, env, fn_info, cdef)

        self.calculate_arg_defaults(fn_info, env, func_reg)

        return (func_ir, func_reg)

    def gen_func_ir(self,
                    blocks: List[BasicBlock],
                    sig: FuncSignature,
                    env: Environment,
                    fn_info: FuncInfo,
                    cdef: Optional[ClassDef]) -> Tuple[FuncIR, Optional[Value]]:
        """Generates the FuncIR for a function given the blocks, environment, and function info of
        a particular function and returns it. If the function is nested, also returns the register
        containing the instance of the corresponding callable class.
        """
        func_reg = None  # type: Optional[Value]
        if fn_info.is_nested or fn_info.in_non_ext:
            func_ir = self.add_call_to_callable_class(blocks, sig, env, fn_info)
            self.add_get_to_callable_class(fn_info)
            func_reg = self.instantiate_callable_class(fn_info)
        else:
            assert isinstance(fn_info.fitem, FuncDef)
            func_decl = self.mapper.func_to_decl[fn_info.fitem]
            if fn_info.is_decorated:
                class_name = None if cdef is None else cdef.name
                func_decl = FuncDecl(fn_info.name, class_name, self.module_name, sig,
                                     func_decl.kind,
                                     func_decl.is_prop_getter, func_decl.is_prop_setter)
                func_ir = FuncIR(func_decl, blocks, env, fn_info.fitem.line,
                                 traceback_name=fn_info.fitem.name)
            else:
                func_ir = FuncIR(func_decl, blocks, env,
                                 fn_info.fitem.line, traceback_name=fn_info.fitem.name)
        return (func_ir, func_reg)

    def load_decorated_func(self, fdef: FuncDef, orig_func_reg: Value) -> Value:
        """
        Given a decorated FuncDef and the register containing an instance of the callable class
        representing that FuncDef, applies the corresponding decorator functions on that decorated
        FuncDef and returns a register containing an instance of the callable class representing
        the decorated function.
        """
        if not self.is_decorated(fdef):
            # If there are no decorators associated with the function, then just return the
            # original function.
            return orig_func_reg

        decorators = self.fdefs_to_decorators[fdef]
        func_reg = orig_func_reg
        for d in reversed(decorators):
            decorator = d.accept(self)
            assert isinstance(decorator, Value)
            func_reg = self.py_call(decorator, [func_reg], func_reg.line)
        return func_reg

    def maybe_add_implicit_return(self) -> None:
        if is_none_rprimitive(self.ret_types[-1]) or is_object_rprimitive(self.ret_types[-1]):
            self.add_implicit_return()
        else:
            self.add_implicit_unreachable()

    def visit_func_def(self, fdef: FuncDef) -> None:
        func_ir, func_reg = self.gen_func_item(fdef, fdef.name, self.mapper.fdef_to_sig(fdef))

        # If the function that was visited was a nested function, then either look it up in our
        # current environment or define it if it was not already defined.
        if func_reg:
            self.assign(self.get_func_target(fdef), func_reg, fdef.line)
        self.functions.append(func_ir)

    def visit_overloaded_func_def(self, o: OverloadedFuncDef) -> None:
        # Handle regular overload case
        assert o.impl
        self.accept(o.impl)

    def add_implicit_return(self) -> None:
        block = self.blocks[-1][-1]
        if not block.ops or not isinstance(block.ops[-1], ControlOp):
            retval = self.coerce(self.none(), self.ret_types[-1], -1)
            self.nonlocal_control[-1].gen_return(self, retval, self.fn_info.fitem.line)

    def add_implicit_unreachable(self) -> None:
        block = self.blocks[-1][-1]
        if not block.ops or not isinstance(block.ops[-1], ControlOp):
            self.add(Unreachable())

    def visit_block(self, block: Block) -> None:
        if not block.is_unreachable:
            for stmt in block.body:
                self.accept(stmt)
        # Raise a RuntimeError if we hit a non-empty unreachable block.
        # Don't complain about empty unreachable blocks, since mypy inserts
        # those after `if MYPY`.
        elif block.body:
            self.add(RaiseStandardError(RaiseStandardError.RUNTIME_ERROR,
                                        'Reached allegedly unreachable code!',
                                        block.line))
            self.add(Unreachable())

    def visit_expression_stmt(self, stmt: ExpressionStmt) -> None:
        if isinstance(stmt.expr, StrExpr):
            # Docstring. Ignore
            return
        # ExpressionStmts do not need to be coerced like other Expressions.
        stmt.expr.accept(self)

    def visit_return_stmt(self, stmt: ReturnStmt) -> None:
        if stmt.expr:
            retval = self.accept(stmt.expr)
        else:
            retval = self.none()
        retval = self.coerce(retval, self.ret_types[-1], stmt.line)
        self.nonlocal_control[-1].gen_return(self, retval, stmt.line)

    def disallow_class_assignments(self, lvalues: List[Lvalue], line: int) -> None:
        # Some best-effort attempts to disallow assigning to class
        # variables that aren't marked ClassVar, since we blatantly
        # miscompile the interaction between instance and class
        # variables.
        for lvalue in lvalues:
            if (isinstance(lvalue, MemberExpr)
                    and isinstance(lvalue.expr, RefExpr)
                    and isinstance(lvalue.expr.node, TypeInfo)):
                var = lvalue.expr.node[lvalue.name].node
                if isinstance(var, Var) and not var.is_classvar:
                    self.error(
                        "Only class variables defined as ClassVar can be assigned to",
                        line)

    def non_function_scope(self) -> bool:
        # Currently the stack always has at least two items: dummy and top-level.
        return len(self.fn_infos) <= 2

    def init_final_static(self, lvalue: Lvalue, rvalue_reg: Value,
                          class_name: Optional[str] = None) -> None:
        assert isinstance(lvalue, NameExpr)
        assert isinstance(lvalue.node, Var)
        if lvalue.node.final_value is None:
            if class_name is None:
                name = lvalue.name
            else:
                name = '{}.{}'.format(class_name, lvalue.name)
            assert name is not None, "Full name not set for variable"
            self.final_names.append((name, rvalue_reg.type))
            self.add(InitStatic(rvalue_reg, name, self.module_name))

    def load_final_static(self, fullname: str, typ: RType, line: int,
                          error_name: Optional[str] = None) -> Value:
        if error_name is None:
            error_name = fullname
        ok_block, error_block = BasicBlock(), BasicBlock()
        split_name = split_target(self.graph, fullname)
        assert split_name is not None
        value = self.add(LoadStatic(typ, split_name[1], split_name[0], line=line))
        self.add(Branch(value, error_block, ok_block, Branch.IS_ERROR, rare=True))
        self.activate_block(error_block)
        self.add(RaiseStandardError(RaiseStandardError.VALUE_ERROR,
                                    'value for final name "{}" was not set'.format(error_name),
                                    line))
        self.add(Unreachable())
        self.activate_block(ok_block)
        return value

    def load_final_literal_value(self, val: Union[int, str, bytes, float, bool],
                                 line: int) -> Value:
        """Load value of a final name or class-level attribute."""
        if isinstance(val, bool):
            if val:
                return self.primitive_op(true_op, [], line)
            else:
                return self.primitive_op(false_op, [], line)
        elif isinstance(val, int):
            # TODO: take care of negative integer initializers
            # (probably easier to fix this in mypy itself).
            if val > MAX_LITERAL_SHORT_INT:
                return self.load_static_int(val)
            return self.add(LoadInt(val))
        elif isinstance(val, float):
            return self.load_static_float(val)
        elif isinstance(val, str):
            return self.load_static_unicode(val)
        elif isinstance(val, bytes):
            return self.load_static_bytes(val)
        else:
            assert False, "Unsupported final literal value"

    def visit_assignment_stmt(self, stmt: AssignmentStmt) -> None:
        assert len(stmt.lvalues) >= 1
        self.disallow_class_assignments(stmt.lvalues, stmt.line)
        lvalue = stmt.lvalues[0]
        if stmt.type and isinstance(stmt.rvalue, TempNode):
            # This is actually a variable annotation without initializer. Don't generate
            # an assignment but we need to call get_assignment_target since it adds a
            # name binding as a side effect.
            self.get_assignment_target(lvalue, stmt.line)
            return

        line = stmt.rvalue.line
        rvalue_reg = self.accept(stmt.rvalue)
        if self.non_function_scope() and stmt.is_final_def:
            self.init_final_static(lvalue, rvalue_reg)
        for lvalue in stmt.lvalues:
            target = self.get_assignment_target(lvalue)
            self.assign(target, rvalue_reg, line)

    def visit_operator_assignment_stmt(self, stmt: OperatorAssignmentStmt) -> None:
        """Operator assignment statement such as x += 1"""
        self.disallow_class_assignments([stmt.lvalue], stmt.line)
        target = self.get_assignment_target(stmt.lvalue)
        target_value = self.read(target, stmt.line)
        rreg = self.accept(stmt.rvalue)
        # the Python parser strips the '=' from operator assignment statements, so re-add it
        op = stmt.op + '='
        res = self.binary_op(target_value, rreg, op, stmt.line)
        # usually operator assignments are done in-place
        # but when target doesn't support that we need to manually assign
        self.assign(target, res, res.line)

    def get_assignment_target(self, lvalue: Lvalue,
                              line: int = -1) -> AssignmentTarget:
        if isinstance(lvalue, NameExpr):
            # If we are visiting a decorator, then the SymbolNode we really want to be looking at
            # is the function that is decorated, not the entire Decorator node itself.
            symbol = lvalue.node
            if isinstance(symbol, Decorator):
                symbol = symbol.func
            if symbol is None:
                # New semantic analyzer doesn't create ad-hoc Vars for special forms.
                assert lvalue.is_special_form
                symbol = Var(lvalue.name)
            if lvalue.kind == LDEF:
                if symbol not in self.environment.symtable:
                    # If the function is a generator function, then first define a new variable
                    # in the current function's environment class. Next, define a target that
                    # refers to the newly defined variable in that environment class. Add the
                    # target to the table containing class environment variables, as well as the
                    # current environment.
                    if self.fn_info.is_generator:
                        return self.add_var_to_env_class(symbol, self.node_type(lvalue),
                                                         self.fn_info.generator_class,
                                                         reassign=False)

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
            star_idx = None  # type: Optional[int]
            lvalues = []
            for idx, item in enumerate(lvalue.items):
                targ = self.get_assignment_target(item)
                lvalues.append(targ)
                if isinstance(item, StarExpr):
                    if star_idx is not None:
                        self.error("Two starred expressions in assignment", line)
                    star_idx = idx

            return AssignmentTargetTuple(lvalues, star_idx)

        elif isinstance(lvalue, StarExpr):
            return self.get_assignment_target(lvalue.expr)

        assert False, 'Unsupported lvalue: %r' % lvalue

    def read(self, target: Union[Value, AssignmentTarget], line: int = -1) -> Value:
        if isinstance(target, Value):
            return target
        if isinstance(target, AssignmentTargetRegister):
            return target.register
        if isinstance(target, AssignmentTargetIndex):
            reg = self.gen_method_call(
                target.base, '__getitem__', [target.index], target.type, line)
            if reg is not None:
                return reg
            assert False, target.base.type
        if isinstance(target, AssignmentTargetAttr):
            if isinstance(target.obj.type, RInstance) and target.obj.type.class_ir.is_ext_class:
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
            target_reg2 = self.gen_method_call(
                target.base, '__setitem__', [target.index, rvalue_reg], None, line)
            assert target_reg2 is not None, target.base.type
        elif isinstance(target, AssignmentTargetTuple):
            if isinstance(rvalue_reg.type, RTuple) and target.star_idx is None:
                rtypes = rvalue_reg.type.types
                assert len(rtypes) == len(target.items)
                for i in range(len(rtypes)):
                    item_value = self.add(TupleGet(rvalue_reg, i, line))
                    self.assign(target.items[i], item_value, line)
            else:
                self.process_iterator_tuple_assignment(target, rvalue_reg, line)
        else:
            assert False, 'Unsupported assignment target'

    def process_iterator_tuple_assignment_helper(self,
                                                 litem: AssignmentTarget,
                                                 ritem: Value, line: int) -> None:
        error_block, ok_block = BasicBlock(), BasicBlock()
        self.add(Branch(ritem, error_block, ok_block, Branch.IS_ERROR))

        self.activate_block(error_block)
        self.add(RaiseStandardError(RaiseStandardError.VALUE_ERROR,
                                    'not enough values to unpack', line))
        self.add(Unreachable())

        self.activate_block(ok_block)
        self.assign(litem, ritem, line)

    def process_iterator_tuple_assignment(self,
                                          target: AssignmentTargetTuple,
                                          rvalue_reg: Value,
                                          line: int) -> None:

        iterator = self.primitive_op(iter_op, [rvalue_reg], line)

        # This may be the whole lvalue list if there is no starred value
        split_idx = target.star_idx if target.star_idx is not None else len(target.items)

        # Assign values before the first starred value
        for litem in target.items[:split_idx]:
            ritem = self.primitive_op(next_op, [iterator], line)
            error_block, ok_block = BasicBlock(), BasicBlock()
            self.add(Branch(ritem, error_block, ok_block, Branch.IS_ERROR))

            self.activate_block(error_block)
            self.add(RaiseStandardError(RaiseStandardError.VALUE_ERROR,
                                        'not enough values to unpack', line))
            self.add(Unreachable())

            self.activate_block(ok_block)

            self.assign(litem, ritem, line)

        # Assign the starred value and all values after it
        if target.star_idx is not None:
            post_star_vals = target.items[split_idx + 1:]
            iter_list = self.primitive_op(to_list, [iterator], line)
            iter_list_len = self.primitive_op(list_len_op, [iter_list], line)
            post_star_len = self.add(LoadInt(len(post_star_vals)))
            condition = self.binary_op(post_star_len, iter_list_len, '<=', line)

            error_block, ok_block = BasicBlock(), BasicBlock()
            self.add(Branch(condition, ok_block, error_block, Branch.BOOL_EXPR))

            self.activate_block(error_block)
            self.add(RaiseStandardError(RaiseStandardError.VALUE_ERROR,
                                        'not enough values to unpack', line))
            self.add(Unreachable())

            self.activate_block(ok_block)

            for litem in reversed(post_star_vals):
                ritem = self.primitive_op(list_pop_last, [iter_list], line)
                self.assign(litem, ritem, line)

            # Assign the starred value
            self.assign(target.items[target.star_idx], iter_list, line)

        # There is no starred value, so check if there are extra values in rhs that
        # have not been assigned.
        else:
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

    def push_loop_stack(self, continue_block: BasicBlock, break_block: BasicBlock) -> None:
        self.nonlocal_control.append(
            LoopNonlocalControl(self.nonlocal_control[-1], continue_block, break_block))

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

        self.for_loop_helper(s.index, s.expr, body,
                             else_block if s.else_body else None, s.line)

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
                        body_insts: GenFunc, else_insts: Optional[GenFunc],
                        line: int) -> None:
        """Generate IR for a loop.

        Args:
            index: the loop index Lvalue
            expr: the expression to iterate over
            body_insts: a function that generates the body of the loop
            else_insts: a function that generates the else block instructions
        """
        # Body of the loop
        body_block = BasicBlock()
        # Block that steps to the next item
        step_block = BasicBlock()
        # Block for the else clause, if we need it
        else_block = BasicBlock()
        # Block executed after the loop
        exit_block = BasicBlock()

        # Determine where we want to exit, if our condition check fails.
        normal_loop_exit = else_block if else_insts is not None else exit_block

        for_gen = self.make_for_loop_generator(index, expr, body_block, normal_loop_exit, line)

        self.push_loop_stack(step_block, exit_block)
        condition_block = self.goto_new_block()

        # Add loop condition check.
        for_gen.gen_condition()

        # Generate loop body.
        self.activate_block(body_block)
        for_gen.begin_body()
        body_insts()

        # We generate a separate step block (which might be empty).
        self.goto_and_activate(step_block)
        for_gen.gen_step()
        # Go back to loop condition.
        self.goto(condition_block)

        for_gen.add_cleanup(normal_loop_exit)
        self.pop_loop_stack()

        if else_insts is not None:
            self.activate_block(else_block)
            else_insts()
            self.goto(exit_block)

        self.activate_block(exit_block)

    def extract_int(self, e: Expression) -> Optional[int]:
        if isinstance(e, IntExpr):
            return e.value
        elif isinstance(e, UnaryExpr) and e.op == '-' and isinstance(e.expr, IntExpr):
            return -e.expr.value
        else:
            return None

    def make_for_loop_generator(self,
                                index: Lvalue,
                                expr: Expression,
                                body_block: BasicBlock,
                                loop_exit: BasicBlock,
                                line: int,
                                nested: bool = False) -> ForGenerator:
        """Return helper object for generating a for loop over an iterable.

        If "nested" is True, this is a nested iterator such as "e" in "enumerate(e)".
        """

        if is_list_rprimitive(self.node_type(expr)):
            # Special case "for x in <list>".
            expr_reg = self.accept(expr)
            target_list_type = get_proper_type(self.types[expr])
            assert isinstance(target_list_type, Instance)
            target_type = self.type_to_rtype(target_list_type.args[0])

            for_list = ForList(self, index, body_block, loop_exit, line, nested)
            for_list.init(expr_reg, target_type, reverse=False)
            return for_list

        if (isinstance(expr, CallExpr)
                and isinstance(expr.callee, RefExpr)):
            if (expr.callee.fullname == 'builtins.range'
                    and (len(expr.args) <= 2
                         or (len(expr.args) == 3
                             and self.extract_int(expr.args[2]) is not None))
                    and set(expr.arg_kinds) == {ARG_POS}):
                # Special case "for x in range(...)".
                # We support the 3 arg form but only for int literals, since it doesn't
                # seem worth the hassle of supporting dynamically determining which
                # direction of comparison to do.
                if len(expr.args) == 1:
                    start_reg = self.add(LoadInt(0))
                    end_reg = self.accept(expr.args[0])
                else:
                    start_reg = self.accept(expr.args[0])
                    end_reg = self.accept(expr.args[1])
                if len(expr.args) == 3:
                    step = self.extract_int(expr.args[2])
                    assert step is not None
                    if step == 0:
                        self.error("range() step can't be zero", expr.args[2].line)
                else:
                    step = 1

                for_range = ForRange(self, index, body_block, loop_exit, line, nested)
                for_range.init(start_reg, end_reg, step)
                return for_range

            elif (expr.callee.fullname == 'builtins.enumerate'
                    and len(expr.args) == 1
                    and expr.arg_kinds == [ARG_POS]
                    and isinstance(index, TupleExpr)
                    and len(index.items) == 2):
                # Special case "for i, x in enumerate(y)".
                lvalue1 = index.items[0]
                lvalue2 = index.items[1]
                for_enumerate = ForEnumerate(self, index, body_block, loop_exit, line,
                                             nested)
                for_enumerate.init(lvalue1, lvalue2, expr.args[0])
                return for_enumerate

            elif (expr.callee.fullname == 'builtins.zip'
                    and len(expr.args) >= 2
                    and set(expr.arg_kinds) == {ARG_POS}
                    and isinstance(index, TupleExpr)
                    and len(index.items) == len(expr.args)):
                # Special case "for x, y in zip(a, b)".
                for_zip = ForZip(self, index, body_block, loop_exit, line, nested)
                for_zip.init(index.items, expr.args)
                return for_zip

            if (expr.callee.fullname == 'builtins.reversed'
                    and len(expr.args) == 1
                    and expr.arg_kinds == [ARG_POS]
                    and is_list_rprimitive(self.node_type(expr.args[0]))):
                # Special case "for x in reversed(<list>)".
                expr_reg = self.accept(expr.args[0])
                target_list_type = get_proper_type(self.types[expr.args[0]])
                assert isinstance(target_list_type, Instance)
                target_type = self.type_to_rtype(target_list_type.args[0])

                for_list = ForList(self, index, body_block, loop_exit, line, nested)
                for_list.init(expr_reg, target_type, reverse=True)
                return for_list

        # Default to a generic for loop.
        expr_reg = self.accept(expr)
        for_obj = ForIterable(self, index, body_block, loop_exit, line, nested)
        item_type = self._analyze_iterable_item_type(expr)
        item_rtype = self.type_to_rtype(item_type)
        for_obj.init(expr_reg, item_rtype)
        return for_obj

    def _analyze_iterable_item_type(self, expr: Expression) -> Type:
        """Return the item type given by 'expr' in an iterable context."""
        # This logic is copied from mypy's TypeChecker.analyze_iterable_item_type.
        iterable = get_proper_type(self.types[expr])
        echk = self.graph[self.module_name].type_checker().expr_checker
        iterator = echk.check_method_call_by_name('__iter__', iterable, [], [], expr)[0]

        from mypy.join import join_types
        if isinstance(iterable, TupleType):
            joined = UninhabitedType()  # type: Type
            for item in iterable.items:
                joined = join_types(joined, item)
            return joined
        else:
            # Non-tuple iterable.
            return echk.check_method_call_by_name('__next__', iterator, [], [], expr)[0]

    def visit_break_stmt(self, node: BreakStmt) -> None:
        self.nonlocal_control[-1].gen_break(self, node.line)

    def visit_continue_stmt(self, node: ContinueStmt) -> None:
        self.nonlocal_control[-1].gen_continue(self, node.line)

    def visit_unary_expr(self, expr: UnaryExpr) -> Value:
        return self.unary_op(self.accept(expr.expr), expr.op, expr.line)

    def visit_op_expr(self, expr: OpExpr) -> Value:
        if expr.op in ('and', 'or'):
            return self.shortcircuit_expr(expr)
        return self.binary_op(self.accept(expr.left), self.accept(expr.right), expr.op, expr.line)

    def translate_eq_cmp(self,
                         lreg: Value,
                         rreg: Value,
                         expr_op: str,
                         line: int) -> Optional[Value]:
        ltype = lreg.type
        rtype = rreg.type
        if not (isinstance(ltype, RInstance) and ltype == rtype):
            return None

        class_ir = ltype.class_ir
        # Check whether any subclasses of the operand redefines __eq__
        # or it might be redefined in a Python parent class or by
        # dataclasses
        cmp_varies_at_runtime = (
            not class_ir.is_method_final('__eq__')
            or not class_ir.is_method_final('__ne__')
            or class_ir.inherits_python
            or class_ir.is_augmented
        )

        if cmp_varies_at_runtime:
            # We might need to call left.__eq__(right) or right.__eq__(left)
            # depending on which is the more specific type.
            return None

        if not class_ir.has_method('__eq__'):
            # There's no __eq__ defined, so just use object identity.
            identity_ref_op = 'is' if expr_op == '==' else 'is not'
            return self.binary_op(lreg, rreg, identity_ref_op, line)

        return self.gen_method_call(
            lreg,
            op_methods[expr_op],
            [rreg],
            ltype,
            line
        )

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
            if result_type and not is_runtime_subtype(target.type, result_type):
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
        # Special case == and != when we can resolve the method call statically.
        value = None
        if expr_op in ('==', '!='):
            value = self.translate_eq_cmp(lreg, rreg, expr_op, line)
        if value is not None:
            return value

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

        if isinstance(base.type, RTuple) and isinstance(expr.index, IntExpr):
            return self.add(TupleGet(base, expr.index.value, expr.line))

        index_reg = self.accept(expr.index)
        return self.gen_method_call(
            base, '__getitem__', [index_reg], self.node_type(expr), expr.line)

    def visit_int_expr(self, expr: IntExpr) -> Value:
        if expr.value > MAX_LITERAL_SHORT_INT:
            return self.load_static_int(expr.value)
        return self.add(LoadInt(expr.value))

    def visit_float_expr(self, expr: FloatExpr) -> Value:
        return self.load_static_float(expr.value)

    def visit_complex_expr(self, expr: ComplexExpr) -> Value:
        return self.load_static_complex(expr.value)

    def visit_bytes_expr(self, expr: BytesExpr) -> Value:
        value = bytes(expr.value, 'utf8').decode('unicode-escape').encode('raw-unicode-escape')
        return self.load_static_bytes(value)

    def is_native_module(self, module: str) -> bool:
        """Is the given module one compiled by mypyc?"""
        return module in self.mapper.group_map

    def is_native_ref_expr(self, expr: RefExpr) -> bool:
        if expr.node is None:
            return False
        if '.' in expr.node.fullname:
            return self.is_native_module(expr.node.fullname.rpartition('.')[0])
        return True

    def is_native_module_ref_expr(self, expr: RefExpr) -> bool:
        return self.is_native_ref_expr(expr) and expr.kind == GDEF

    def is_synthetic_type(self, typ: TypeInfo) -> bool:
        """Is a type something other than just a class we've created?"""
        return typ.is_named_tuple or typ.is_newtype or typ.typeddict_type is not None

    def is_decorated(self, fdef: FuncDef) -> bool:
        return fdef in self.fdefs_to_decorators

    def is_free_variable(self, symbol: SymbolNode) -> bool:
        fitem = self.fn_info.fitem
        return fitem in self.free_variables and symbol in self.free_variables[fitem]

    def get_final_ref(self, expr: MemberExpr) -> Optional[Tuple[str, Var, bool]]:
        """Check if `expr` is a final attribute.

        This needs to be done differently for class and module attributes to
        correctly determine fully qualified name. Return a tuple that consists of
        the qualified name, the corresponding Var node, and a flag indicating whether
        the final name was defined in a compiled module. Return None if `expr` does not
        refer to a final attribute.
        """
        final_var = None
        if isinstance(expr.expr, RefExpr) and isinstance(expr.expr.node, TypeInfo):
            # a class attribute
            sym = expr.expr.node.get(expr.name)
            if sym and isinstance(sym.node, Var):
                # Enum attribute are treated as final since they are added to the global cache
                expr_fullname = expr.expr.node.bases[0].type.fullname
                is_final = sym.node.is_final or expr_fullname == 'enum.Enum'
                if is_final:
                    final_var = sym.node
                    fullname = '{}.{}'.format(sym.node.info.fullname, final_var.name)
                    native = self.is_native_module(expr.expr.node.module_name)
        elif self.is_module_member_expr(expr):
            # a module attribute
            if isinstance(expr.node, Var) and expr.node.is_final:
                final_var = expr.node
                fullname = expr.node.fullname
                native = self.is_native_ref_expr(expr)
        if final_var is not None:
            return fullname, final_var, native
        return None

    def emit_load_final(self, final_var: Var, fullname: str,
                        name: str, native: bool, typ: Type, line: int) -> Optional[Value]:
        """Emit code for loading value of a final name (if possible).

        Args:
            final_var: Var corresponding to the final name
            fullname: its qualified name
            name: shorter name to show in errors
            native: whether the name was defined in a compiled module
            typ: its type
            line: line number where loading occurs
        """
        if final_var.final_value is not None:  # this is safe even for non-native names
            return self.load_final_literal_value(final_var.final_value, line)
        elif native:
            return self.load_final_static(fullname, self.mapper.type_to_rtype(typ),
                                          line, name)
        else:
            return None

    def visit_name_expr(self, expr: NameExpr) -> Value:
        assert expr.node, "RefExpr not resolved"
        fullname = expr.node.fullname
        if fullname in name_ref_ops:
            # Use special access op for this particular name.
            desc = name_ref_ops[fullname]
            assert desc.result_type is not None
            return self.add(PrimitiveOp([], desc, expr.line))

        if isinstance(expr.node, Var) and expr.node.is_final:
            value = self.emit_load_final(expr.node, fullname, expr.name,
                                         self.is_native_ref_expr(expr), self.types[expr],
                                         expr.line)
            if value is not None:
                return value

        if isinstance(expr.node, MypyFile) and expr.node.fullname in self.imports:
            return self.load_module(expr.node.fullname)

        # If the expression is locally defined, then read the result from the corresponding
        # assignment target and return it. Otherwise if the expression is a global, load it from
        # the globals dictionary.
        # Except for imports, that currently always happens in the global namespace.
        if expr.kind == LDEF and not (isinstance(expr.node, Var)
                                      and expr.node.is_suppressed_import):
            # Try to detect and error when we hit the irritating mypy bug
            # where a local variable is cast to None. (#5423)
            if (isinstance(expr.node, Var) and is_none_rprimitive(self.node_type(expr))
                    and expr.node.is_inferred):
                self.error(
                    "Local variable '{}' has inferred type None; add an annotation".format(
                        expr.node.name),
                    expr.node.line)

            # TODO: Behavior currently only defined for Var and FuncDef node types.
            return self.read(self.get_assignment_target(expr), expr.line)

        return self.load_global(expr)

    def is_module_member_expr(self, expr: MemberExpr) -> bool:
        return isinstance(expr.expr, RefExpr) and isinstance(expr.expr.node, MypyFile)

    def visit_member_expr(self, expr: MemberExpr) -> Value:
        # First check if this is maybe a final attribute.
        final = self.get_final_ref(expr)
        if final is not None:
            fullname, final_var, native = final
            value = self.emit_load_final(final_var, fullname, final_var.name, native,
                                         self.types[expr], expr.line)
            if value is not None:
                return value

        if isinstance(expr.node, MypyFile) and expr.node.fullname in self.imports:
            return self.load_module(expr.node.fullname)

        obj = self.accept(expr.expr)
        return self.get_attr(obj, expr.name, self.node_type(expr), expr.line)

    def get_attr(self, obj: Value, attr: str, result_type: RType, line: int) -> Value:
        if (isinstance(obj.type, RInstance) and obj.type.class_ir.is_ext_class
                and obj.type.class_ir.has_attr(attr)):
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
                op = self.isinstance_native(obj, item.class_ir, line)
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

    def isinstance_helper(self, obj: Value, class_irs: List[ClassIR], line: int) -> Value:
        """Fast path for isinstance() that checks against a list of native classes."""
        if not class_irs:
            return self.primitive_op(false_op, [], line)
        ret = self.isinstance_native(obj, class_irs[0], line)
        for class_ir in class_irs[1:]:
            def other() -> Value:
                return self.isinstance_native(obj, class_ir, line)
            ret = self.shortcircuit_helper('or', bool_rprimitive, lambda: ret, other, line)
        return ret

    def isinstance_native(self, obj: Value, class_ir: ClassIR, line: int) -> Value:
        """Fast isinstance() check for a native class.

        If there three or less concrete (non-trait) classes among the class and all
        its children, use even faster type comparison checks `type(obj) is typ`.
        """
        concrete = all_concrete_classes(class_ir)
        if concrete is None or len(concrete) > FAST_ISINSTANCE_MAX_SUBCLASSES + 1:
            return self.primitive_op(fast_isinstance_op,
                                     [obj, self.get_native_type(class_ir)],
                                     line)
        if not concrete:
            # There can't be any concrete instance that matches this.
            return self.primitive_op(false_op, [], line)
        type_obj = self.get_native_type(concrete[0])
        ret = self.primitive_op(type_is_op, [obj, type_obj], line)
        for c in concrete[1:]:
            def other() -> Value:
                return self.primitive_op(type_is_op, [obj, self.get_native_type(c)], line)
            ret = self.shortcircuit_helper('or', bool_rprimitive, lambda: ret, other, line)
        return ret

    def get_native_type(self, cls: ClassIR) -> Value:
        fullname = '%s.%s' % (cls.module_name, cls.name)
        return self.load_native_type_object(fullname)

    def py_get_attr(self, obj: Value, attr: str, line: int) -> Value:
        key = self.load_static_unicode(attr)
        return self.add(PrimitiveOp([obj, key], py_getattr_op, line))

    def py_call(self,
                function: Value,
                arg_values: List[Value],
                line: int,
                arg_kinds: Optional[List[int]] = None,
                arg_names: Optional[Sequence[Optional[str]]] = None) -> Value:
        """Use py_call_op or py_call_with_kwargs_op for function call."""
        # If all arguments are positional, we can use py_call_op.
        if (arg_kinds is None) or all(kind == ARG_POS for kind in arg_kinds):
            return self.primitive_op(py_call_op, [function] + arg_values, line)

        # Otherwise fallback to py_call_with_kwargs_op.
        assert arg_names is not None

        pos_arg_values = []
        kw_arg_key_value_pairs = []  # type: List[DictEntry]
        star_arg_values = []
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
                # NOTE: mypy currently only supports a single ** arg, but python supports multiple.
                # This code supports multiple primarily to make the logic easier to follow.
                kw_arg_key_value_pairs.append((None, value))
            else:
                assert False, ("Argument kind should not be possible:", kind)

        if len(star_arg_values) == 0:
            # We can directly construct a tuple if there are no star args.
            pos_args_tuple = self.primitive_op(new_tuple_op, pos_arg_values, line)
        else:
            # Otherwise we construct a list and call extend it with the star args, since tuples
            # don't have an extend method.
            pos_args_list = self.primitive_op(new_list_op, pos_arg_values, line)
            for star_arg_value in star_arg_values:
                self.primitive_op(list_extend_op, [pos_args_list, star_arg_value], line)
            pos_args_tuple = self.primitive_op(list_tuple_op, [pos_args_list], line)

        kw_args_dict = self.make_dict(kw_arg_key_value_pairs, line)

        return self.primitive_op(
            py_call_with_kwargs_op, [function, pos_args_tuple, kw_args_dict], line)

    def py_method_call(self,
                       obj: Value,
                       method_name: str,
                       arg_values: List[Value],
                       line: int,
                       arg_kinds: Optional[List[int]],
                       arg_names: Optional[Sequence[Optional[str]]]) -> Value:
        if (arg_kinds is None) or all(kind == ARG_POS for kind in arg_kinds):
            method_name_reg = self.load_static_unicode(method_name)
            return self.primitive_op(py_method_call_op, [obj, method_name_reg] + arg_values, line)
        else:
            method = self.py_get_attr(obj, method_name, line)
            return self.py_call(method, arg_values, line, arg_kinds=arg_kinds, arg_names=arg_names)

    def call(self, decl: FuncDecl, args: Sequence[Value],
             arg_kinds: List[int],
             arg_names: Sequence[Optional[str]],
             line: int) -> Value:
        # Normalize args to positionals.
        args = self.native_args_to_positional(
            args, arg_kinds, arg_names, decl.sig, line)
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

        # TODO: Allow special cases to have default args or named args. Currently they don't since
        # they check that everything in arg_kinds is ARG_POS.

        # If there is a specializer for this function, try calling it.
        if callee.fullname and (callee.fullname, None) in specializers:
            val = specializers[callee.fullname, None](self, expr, callee)
            if val is not None:
                return val

        # Gen the argument values
        arg_values = [self.accept(arg) for arg in expr.args]

        return self.call_refexpr_with_args(expr, callee, arg_values)

    def call_refexpr_with_args(
            self, expr: CallExpr, callee: RefExpr, arg_values: List[Value]) -> Value:

        # Handle data-driven special-cased primitive call ops.
        if callee.fullname is not None and expr.arg_kinds == [ARG_POS] * len(arg_values):
            ops = func_ops.get(callee.fullname, [])
            target = self.matching_primitive_op(ops, arg_values, expr.line, self.node_type(expr))
            if target:
                return target

        # Standard native call if signature and fullname are good and all arguments are positional
        # or named.
        callee_node = callee.node
        if isinstance(callee_node, OverloadedFuncDef):
            callee_node = callee_node.impl
        if (callee_node is not None
                and callee.fullname is not None
                and callee_node in self.mapper.func_to_decl
                and all(kind in (ARG_POS, ARG_NAMED) for kind in expr.arg_kinds)):
            decl = self.mapper.func_to_decl[callee_node]
            return self.call(decl, arg_values, expr.arg_kinds, expr.arg_names, expr.line)

        # Fall back to a Python call
        function = self.accept(callee)
        return self.py_call(function, arg_values, expr.line,
                            arg_kinds=expr.arg_kinds, arg_names=expr.arg_names)

    def translate_method_call(self, expr: CallExpr, callee: MemberExpr) -> Value:
        """Generate IR for an arbitrary call of form e.m(...).

        This can also deal with calls to module-level functions.
        """
        if self.is_native_ref_expr(callee):
            # Call to module-level native function or such
            return self.translate_call(expr, callee)
        elif (
            isinstance(callee.expr, RefExpr)
            and isinstance(callee.expr.node, TypeInfo)
            and callee.expr.node in self.mapper.type_to_ir
            and self.mapper.type_to_ir[callee.expr.node].has_method(callee.name)
        ):
            # Call a method via the *class*
            assert isinstance(callee.expr.node, TypeInfo)
            ir = self.mapper.type_to_ir[callee.expr.node]
            decl = ir.method_decl(callee.name)
            args = []
            arg_kinds, arg_names = expr.arg_kinds[:], expr.arg_names[:]
            # Add the class argument for class methods in extension classes
            if decl.kind == FUNC_CLASSMETHOD and ir.is_ext_class:
                args.append(self.load_native_type_object(callee.expr.node.fullname))
                arg_kinds.insert(0, ARG_POS)
                arg_names.insert(0, None)
            args += [self.accept(arg) for arg in expr.args]

            if ir.is_ext_class:
                return self.call(decl, args, arg_kinds, arg_names, expr.line)
            else:
                obj = self.accept(callee.expr)
                return self.gen_method_call(obj,
                                            callee.name,
                                            args,
                                            self.node_type(expr),
                                            expr.line,
                                            expr.arg_kinds,
                                            expr.arg_names)

        elif self.is_module_member_expr(callee):
            # Fall back to a PyCall for non-native module calls
            function = self.accept(callee)
            args = [self.accept(arg) for arg in expr.args]
            return self.py_call(function, args, expr.line,
                                arg_kinds=expr.arg_kinds, arg_names=expr.arg_names)
        else:
            receiver_typ = self.node_type(callee.expr)

            # If there is a specializer for this method name/type, try calling it.
            if (callee.name, receiver_typ) in specializers:
                val = specializers[callee.name, receiver_typ](self, expr, callee)
                if val is not None:
                    return val

            obj = self.accept(callee.expr)
            args = [self.accept(arg) for arg in expr.args]
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
            elif self.fn_info.is_generator:
                # For generator classes, the self target is the 6th value
                # in the symbol table (which is an ordered dict). This is sort
                # of ugly, but we can't search by name since the 'self' parameter
                # could be named anything, and it doesn't get added to the
                # environment indexes.
                self_targ = list(self.environment.symtable.values())[6]
                vself = self.read(self_targ, self.fn_info.fitem.line)
            arg_values.insert(0, vself)
            arg_kinds.insert(0, ARG_POS)
            arg_names.insert(0, None)

        return self.call(decl, arg_values, arg_kinds, arg_names, expr.line)

    def gen_method_call(self,
                        base: Value,
                        name: str,
                        arg_values: List[Value],
                        return_rtype: Optional[RType],
                        line: int,
                        arg_kinds: Optional[List[int]] = None,
                        arg_names: Optional[List[Optional[str]]] = None) -> Value:
        # If arg_kinds contains values other than arg_pos and arg_named, then fallback to
        # Python method call.
        if (arg_kinds is not None
                and not all(kind in (ARG_POS, ARG_NAMED) for kind in arg_kinds)):
            return self.py_method_call(base, name, arg_values, base.line, arg_kinds, arg_names)

        # If the base type is one of ours, do a MethodCall
        if (isinstance(base.type, RInstance) and base.type.class_ir.is_ext_class
                and not base.type.class_ir.builtin_base):
            if base.type.class_ir.has_method(name):
                decl = base.type.class_ir.method_decl(name)
                if arg_kinds is None:
                    assert arg_names is None, "arg_kinds not present but arg_names is"
                    arg_kinds = [ARG_POS for _ in arg_values]
                    arg_names = [None for _ in arg_values]
                else:
                    assert arg_names is not None, "arg_kinds present but arg_names is not"

                # Normalize args to positionals.
                assert decl.bound_sig
                arg_values = self.native_args_to_positional(
                    arg_values, arg_kinds, arg_names, decl.bound_sig, line)
                return self.add(MethodCall(base, name, arg_values, line))
            elif base.type.class_ir.has_attr(name):
                function = self.add(GetAttr(base, name, line))
                return self.py_call(function, arg_values, line,
                                    arg_kinds=arg_kinds, arg_names=arg_names)

        elif isinstance(base.type, RUnion):
            return self.union_method_call(base, base.type, name, arg_values, return_rtype, line,
                                          arg_kinds, arg_names)

        # Try to do a special-cased method call
        if not arg_kinds or arg_kinds == [ARG_POS] * len(arg_values):
            target = self.translate_special_method_call(base, name, arg_values, return_rtype, line)
            if target:
                return target

        # Fall back to Python method call
        return self.py_method_call(base, name, arg_values, line, arg_kinds, arg_names)

    def union_method_call(self,
                          base: Value,
                          obj_type: RUnion,
                          name: str,
                          arg_values: List[Value],
                          return_rtype: Optional[RType],
                          line: int,
                          arg_kinds: Optional[List[int]],
                          arg_names: Optional[List[Optional[str]]]) -> Value:
        # Union method call needs a return_rtype for the type of the output register.
        # If we don't have one, use object_rprimitive.
        return_rtype = return_rtype or object_rprimitive

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
        return self._visit_list_display(expr.items, expr.line)

    def _visit_list_display(self, items: List[Expression], line: int) -> Value:
        return self._visit_display(
            items,
            new_list_op,
            list_append_op,
            list_extend_op,
            line
        )

    def _visit_display(self,
                       items: List[Expression],
                       constructor_op: OpDescription,
                       append_op: OpDescription,
                       extend_op: OpDescription,
                       line: int
                       ) -> Value:
        accepted_items = []
        for item in items:
            if isinstance(item, StarExpr):
                accepted_items.append((True, self.accept(item.expr)))
            else:
                accepted_items.append((False, self.accept(item)))

        result = None  # type: Union[Value, None]
        initial_items = []
        for starred, value in accepted_items:
            if result is None and not starred and constructor_op.is_var_arg:
                initial_items.append(value)
                continue

            if result is None:
                result = self.primitive_op(constructor_op, initial_items, line)

            self.primitive_op(extend_op if starred else append_op, [result, value], line)

        if result is None:
            result = self.primitive_op(constructor_op, initial_items, line)

        return result

    def visit_tuple_expr(self, expr: TupleExpr) -> Value:
        if any(isinstance(item, StarExpr) for item in expr.items):
            # create a tuple of unknown length
            return self._visit_tuple_display(expr)

        # create an tuple of fixed length (RTuple)
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

    def _visit_tuple_display(self, expr: TupleExpr) -> Value:
        """Create a list, then turn it into a tuple."""
        val_as_list = self._visit_list_display(expr.items, expr.line)
        return self.primitive_op(list_tuple_op, [val_as_list], expr.line)

    def visit_dict_expr(self, expr: DictExpr) -> Value:
        """First accepts all keys and values, then makes a dict out of them."""
        key_value_pairs = []
        for key_expr, value_expr in expr.items:
            key = self.accept(key_expr) if key_expr is not None else None
            value = self.accept(value_expr)
            key_value_pairs.append((key, value))

        return self.make_dict(key_value_pairs, expr.line)

    def visit_set_expr(self, expr: SetExpr) -> Value:
        return self._visit_display(
            expr.items,
            new_set_op,
            set_add_op,
            set_update_op,
            expr.line
        )

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
        if is_runtime_subtype(value.type, int_rprimitive):
            zero = self.add(LoadInt(0))
            value = self.binary_op(value, zero, '!=', value.line)
        elif is_same_type(value.type, list_rprimitive):
            length = self.primitive_op(list_len_op, [value], value.line)
            zero = self.add(LoadInt(0))
            value = self.binary_op(length, zero, '!=', value.line)
        elif (isinstance(value.type, RInstance) and value.type.class_ir.is_ext_class
                and value.type.class_ir.has_method('__bool__')):
            # Directly call the __bool__ method on classes that have it.
            value = self.gen_method_call(value, '__bool__', [], bool_rprimitive, value.line)
        else:
            value_type = optional_value_type(value.type)
            if value_type is not None:
                is_none = self.binary_op(value, self.none_object(), 'is not', value.line)
                branch = Branch(is_none, true, false, Branch.BOOL_EXPR)
                self.add(branch)
                always_truthy = False
                if isinstance(value_type, RInstance):
                    # check whether X.__bool__ is always just the default (object.__bool__)
                    if (not value_type.class_ir.has_method('__bool__')
                            and value_type.class_ir.is_method_final('__bool__')):
                        always_truthy = True

                if not always_truthy:
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
                return self.none_object()
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
        old_exc = self.maybe_spill(self.primitive_op(error_catch_op, [], line))
        # Compile the except blocks with the nonlocal control flow overridden to clear exc_info
        self.nonlocal_control.append(
            ExceptNonlocalControl(self.nonlocal_control[-1], old_exc))

        # Process the bodies
        for type, var, handler_body in handlers:
            next_block = None
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
        self.primitive_op(restore_exc_info_op, [self.read(old_exc)], line)
        self.goto(exit_block)

        # Cleanup for if we leave except through a raised exception:
        # restore the saved exc_info information and continue propagating
        # the exception.
        self.activate_block(double_except_block)
        self.primitive_op(restore_exc_info_op, [self.read(old_exc)], line)
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

    def try_finally_try(self, err_handler: BasicBlock, return_entry: BasicBlock,
                        main_entry: BasicBlock, try_body: GenFunc) -> Optional[Register]:
        # Compile the try block with an error handler
        control = TryFinallyNonlocalControl(return_entry)
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
            ret_reg: Optional[Value], old_exc: Value) -> Tuple[BasicBlock,
                                                               'FinallyNonlocalControl']:
        cleanup_block = BasicBlock()
        # Compile the finally block with the nonlocal control flow overridden to restore exc_info
        self.error_handlers.append(cleanup_block)
        finally_control = FinallyNonlocalControl(
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
            self.nonlocal_control[-1].gen_return(self, ret_reg, -1)

        # TODO: handle break/continue
        self.activate_block(rest)
        out_block = BasicBlock()
        self.goto(out_block)

        # If there was an exception, restore again
        self.activate_block(cleanup_block)
        finally_control.gen_cleanup(self, -1)
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
            none = self.none_object()
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
        typ = get_proper_type(self.types[expr])
        assert isinstance(typ, CallableType)

        runtime_args = []
        for arg, arg_type in zip(expr.arguments, typ.arg_types):
            arg.variable.type = arg_type
            runtime_args.append(
                RuntimeArg(arg.variable.name, self.type_to_rtype(arg_type), arg.kind))
        ret_type = self.type_to_rtype(typ.ret_type)

        fsig = FuncSignature(runtime_args, ret_type)

        fname = '{}{}'.format(LAMBDA_NAME, self.lambda_counter)
        self.lambda_counter += 1
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
        if self.options.strip_asserts:
            return
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

    def translate_list_comprehension(self, gen: GeneratorExpr) -> Value:
        list_ops = self.primitive_op(new_list_op, [], gen.line)
        loop_params = list(zip(gen.indices, gen.sequences, gen.condlists))

        def gen_inner_stmts() -> None:
            e = self.accept(gen.left_expr)
            self.primitive_op(list_append_op, [list_ops, e], gen.line)

        self.comprehension_helper(loop_params, gen_inner_stmts, gen.line)
        return list_ops

    def visit_list_comprehension(self, o: ListComprehension) -> Value:
        return self.translate_list_comprehension(o.generator)

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
        self.warning('Treating generator comprehension as list', o.line)
        return self.primitive_op(iter_op, [self.translate_list_comprehension(o)], o.line)

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
                self.nonlocal_control[-1].gen_continue(self, cond.line)
                self.goto_and_activate(rest_block)

            if remaining_loop_params:
                # There's another nested level, so the body of this loop is another loop.
                return handle_loop(remaining_loop_params)
            else:
                # We finally reached the actual body of the generator.
                # Generate the IR for the inner loop body.
                gen_inner_stmts()

        handle_loop(loop_params)

    def visit_decorator(self, dec: Decorator) -> None:
        func_ir, func_reg = self.gen_func_item(dec.func, dec.func.name,
                                               self.mapper.fdef_to_sig(dec.func))

        if dec.func in self.nested_fitems:
            assert func_reg is not None
            decorated_func = self.load_decorated_func(dec.func, func_reg)
            self.assign(self.get_func_target(dec.func), decorated_func, dec.func.line)
            func_reg = decorated_func
        else:
            # Obtain the the function name in order to construct the name of the helper function.
            name = dec.func.fullname.split('.')[-1]
            helper_name = decorator_helper_name(name)

            # Load the callable object representing the non-decorated function, and decorate it.
            orig_func = self.load_global_str(helper_name, dec.line)
            decorated_func = self.load_decorated_func(dec.func, orig_func)

            # Set the callable object representing the decorated function as a global.
            self.primitive_op(dict_set_item_op,
                              [self.load_globals_dict(),
                               self.load_static_unicode(dec.func.name), decorated_func],
                              decorated_func.line)

        self.functions.append(func_ir)

    def visit_del_stmt(self, o: DelStmt) -> None:
        self.visit_del_item(self.get_assignment_target(o.expr), o.line)

    def visit_del_item(self, target: AssignmentTarget, line: int) -> None:
        if isinstance(target, AssignmentTargetIndex):
            self.translate_special_method_call(
                target.base,
                '__delitem__',
                [target.index],
                result_type=None,
                line=line
            )
        elif isinstance(target, AssignmentTargetAttr):
            key = self.load_static_unicode(target.attr)
            self.add(PrimitiveOp([target.obj, key], py_delattr_op, line))
        elif isinstance(target, AssignmentTargetRegister):
            # Delete a local by assigning an error value to it, which will
            # prompt the insertion of uninit checks.
            self.add(Assign(target.register,
                            self.add(LoadErrorValue(target.type, undefines=True))))
        elif isinstance(target, AssignmentTargetTuple):
            for subtarget in target.items:
                self.visit_del_item(subtarget, line)

    def visit_super_expr(self, o: SuperExpr) -> Value:
        # self.warning('can not optimize super() expression', o.line)
        sup_val = self.load_module_attr_by_fullname('builtins.super', o.line)
        if o.call.args:
            args = [self.accept(arg) for arg in o.call.args]
        else:
            assert o.info is not None
            typ = self.load_native_type_object(o.info.fullname)
            ir = self.mapper.type_to_ir[o.info]
            iter_env = iter(self.environment.indexes)
            vself = next(iter_env)  # grab first argument
            if self.fn_info.is_generator:
                # grab sixth argument (see comment in translate_super_method_call)
                self_targ = list(self.environment.symtable.values())[6]
                vself = self.read(self_targ, self.fn_info.fitem.line)
            elif not ir.is_ext_class:
                vself = next(iter_env)  # second argument is self if non_extension class
            args = [typ, vself]
        res = self.py_call(sup_val, args, o.line)
        return self.py_get_attr(res, o.name, o.line)

    def visit_yield_expr(self, expr: YieldExpr) -> Value:
        if expr.expr:
            retval = self.accept(expr.expr)
        else:
            retval = self.none()
        return self.emit_yield(retval, expr.line)

    def emit_yield(self, val: Value, line: int) -> Value:
        retval = self.coerce(val, self.ret_types[-1], line)

        cls = self.fn_info.generator_class
        # Create a new block for the instructions immediately following the yield expression, and
        # set the next label so that the next time '__next__' is called on the generator object,
        # the function continues at the new block.
        next_block = BasicBlock()
        next_label = len(cls.blocks)
        cls.blocks.append(next_block)
        self.assign(cls.next_label_target, self.add(LoadInt(next_label)), line)
        self.add(Return(retval))
        self.activate_block(next_block)

        self.add_raise_exception_blocks_to_generator_class(line)

        assert cls.send_arg_reg is not None
        return cls.send_arg_reg

    def handle_yield_from_and_await(self, o: Union[YieldFromExpr, AwaitExpr]) -> Value:
        # This is basically an implementation of the code in PEP 380.

        # TODO: do we want to use the right types here?
        result = self.alloc_temp(object_rprimitive)
        to_yield_reg = self.alloc_temp(object_rprimitive)
        received_reg = self.alloc_temp(object_rprimitive)

        if isinstance(o, YieldFromExpr):
            iter_val = self.primitive_op(iter_op, [self.accept(o.expr)], o.line)
        else:
            iter_val = self.primitive_op(coro_op, [self.accept(o.expr)], o.line)

        iter_reg = self.maybe_spill_assignable(iter_val)

        stop_block, main_block, done_block = BasicBlock(), BasicBlock(), BasicBlock()
        _y_init = self.primitive_op(next_raw_op, [self.read(iter_reg)], o.line)
        self.add(Branch(_y_init, stop_block, main_block, Branch.IS_ERROR))

        # Try extracting a return value from a StopIteration and return it.
        # If it wasn't, this reraises the exception.
        self.activate_block(stop_block)
        self.assign(result, self.primitive_op(check_stop_op, [], o.line), o.line)
        self.goto(done_block)

        self.activate_block(main_block)
        self.assign(to_yield_reg, _y_init, o.line)

        # OK Now the main loop!
        loop_block = BasicBlock()
        self.goto_and_activate(loop_block)

        def try_body() -> None:
            self.assign(received_reg, self.emit_yield(self.read(to_yield_reg), o.line), o.line)

        def except_body() -> None:
            # The body of the except is all implemented in a C function to
            # reduce how much code we need to generate. It returns a value
            # indicating whether to break or yield (or raise an exception).
            res = self.primitive_op(yield_from_except_op, [self.read(iter_reg)], o.line)
            to_stop = self.add(TupleGet(res, 0, o.line))
            val = self.add(TupleGet(res, 1, o.line))

            ok, stop = BasicBlock(), BasicBlock()
            self.add(Branch(to_stop, stop, ok, Branch.BOOL_EXPR))

            # The exception got swallowed. Continue, yielding the returned value
            self.activate_block(ok)
            self.assign(to_yield_reg, val, o.line)
            self.nonlocal_control[-1].gen_continue(self, o.line)

            # The exception was a StopIteration. Stop iterating.
            self.activate_block(stop)
            self.assign(result, val, o.line)
            self.nonlocal_control[-1].gen_break(self, o.line)

        def else_body() -> None:
            # Do a next() or a .send(). It will return NULL on exception
            # but it won't automatically propagate.
            _y = self.primitive_op(send_op, [self.read(iter_reg), self.read(received_reg)], o.line)
            ok, stop = BasicBlock(), BasicBlock()
            self.add(Branch(_y, stop, ok, Branch.IS_ERROR))

            # Everything's fine. Yield it.
            self.activate_block(ok)
            self.assign(to_yield_reg, _y, o.line)
            self.nonlocal_control[-1].gen_continue(self, o.line)

            # Try extracting a return value from a StopIteration and return it.
            # If it wasn't, this rereaises the exception.
            self.activate_block(stop)
            self.assign(result, self.primitive_op(check_stop_op, [], o.line), o.line)
            self.nonlocal_control[-1].gen_break(self, o.line)

        self.push_loop_stack(loop_block, done_block)
        self.visit_try_except(try_body, [(None, None, except_body)], else_body, o.line)
        self.pop_loop_stack()

        self.goto_and_activate(done_block)
        return self.read(result)

    def visit_yield_from_expr(self, o: YieldFromExpr) -> Value:
        return self.handle_yield_from_and_await(o)

    def visit_ellipsis(self, o: EllipsisExpr) -> Value:
        return self.primitive_op(ellipsis_op, [], o.line)

    # Builtin function special cases

    @specialize_function('builtins.globals')
    def translate_globals(self, expr: CallExpr, callee: RefExpr) -> Optional[Value]:
        # Special case builtins.globals
        if len(expr.args) == 0:
            return self.load_globals_dict()
        return None

    @specialize_function('builtins.len')
    def translate_len(
            self, expr: CallExpr, callee: RefExpr) -> Optional[Value]:
        # Special case builtins.len
        if (len(expr.args) == 1
                and expr.arg_kinds == [ARG_POS]):
            expr_rtype = self.node_type(expr.args[0])
            if isinstance(expr_rtype, RTuple):
                # len() of fixed-length tuple can be trivially determined statically,
                # though we still need to evaluate it.
                self.accept(expr.args[0])
                return self.add(LoadInt(len(expr_rtype.types)))
        return None

    # Special cases for things that consume iterators where we know we
    # can safely compile a generator into a list.
    @specialize_function('builtins.tuple')
    @specialize_function('builtins.set')
    @specialize_function('builtins.dict')
    @specialize_function('builtins.sum')
    @specialize_function('builtins.min')
    @specialize_function('builtins.max')
    @specialize_function('builtins.sorted')
    @specialize_function('collections.OrderedDict')
    @specialize_function('join', str_rprimitive)
    @specialize_function('extend', list_rprimitive)
    @specialize_function('update', dict_rprimitive)
    @specialize_function('update', set_rprimitive)
    def translate_safe_generator_call(self, expr: CallExpr, callee: RefExpr) -> Optional[Value]:
        if (len(expr.args) > 0
                and expr.arg_kinds[0] == ARG_POS
                and isinstance(expr.args[0], GeneratorExpr)):
            if isinstance(callee, MemberExpr):
                return self.gen_method_call(
                    self.accept(callee.expr), callee.name,
                    ([self.translate_list_comprehension(expr.args[0])]
                        + [self.accept(arg) for arg in expr.args[1:]]),
                    self.node_type(expr), expr.line, expr.arg_kinds, expr.arg_names)
            else:
                return self.call_refexpr_with_args(
                    expr, callee,
                    ([self.translate_list_comprehension(expr.args[0])]
                        + [self.accept(arg) for arg in expr.args[1:]]))
        return None

    @specialize_function('builtins.any')
    def translate_any_call(self, expr: CallExpr, callee: RefExpr) -> Optional[Value]:
        if (len(expr.args) == 1
                and expr.arg_kinds == [ARG_POS]
                and isinstance(expr.args[0], GeneratorExpr)):
            return self.any_all_helper(expr.args[0], false_op, lambda x: x, true_op)
        return None

    @specialize_function('builtins.all')
    def translate_all_call(self, expr: CallExpr, callee: RefExpr) -> Optional[Value]:
        if (len(expr.args) == 1
                and expr.arg_kinds == [ARG_POS]
                and isinstance(expr.args[0], GeneratorExpr)):
            return self.any_all_helper(expr.args[0],
                                       true_op,
                                       lambda x: self.unary_op(x, 'not', expr.line),
                                       false_op)
        return None

    # Special case for 'dataclasses.field' and 'attr.Factory' function calls
    # because the results of such calls are typechecked by mypy using the types
    # of the arguments to their respective functions, resulting in attempted
    # coercions by mypyc that throw a runtime error.
    @specialize_function('dataclasses.field')
    @specialize_function('attr.Factory')
    def translate_dataclasses_field_call(self, expr: CallExpr, callee: RefExpr) -> Optional[Value]:
        self.types[expr] = AnyType(TypeOfAny.from_error)
        return None

    def any_all_helper(self,
                       gen: GeneratorExpr,
                       initial_value_op: OpDescription,
                       modify: Callable[[Value], Value],
                       new_value_op: OpDescription) -> Value:
        retval = self.alloc_temp(bool_rprimitive)
        self.assign(retval, self.primitive_op(initial_value_op, [], -1), -1)
        loop_params = list(zip(gen.indices, gen.sequences, gen.condlists))
        true_block, false_block, exit_block = BasicBlock(), BasicBlock(), BasicBlock()

        def gen_inner_stmts() -> None:
            comparison = modify(self.accept(gen.left_expr))
            self.add_bool_branch(comparison, true_block, false_block)
            self.activate_block(true_block)
            self.assign(retval, self.primitive_op(new_value_op, [], -1), -1)
            self.goto(exit_block)
            self.activate_block(false_block)

        self.comprehension_helper(loop_params, gen_inner_stmts, gen.line)
        self.goto_and_activate(exit_block)

        return retval

    # Special case for calling next() on a generator expression, an
    # idiom that shows up some in mypy.
    #
    # For example, next(x for x in l if x.id == 12, None) will
    # generate code that searches l for an element where x.id == 12
    # and produce the first such object, or None if no such element
    # exists.
    @specialize_function('builtins.next')
    def translate_next_call(self, expr: CallExpr, callee: RefExpr) -> Optional[Value]:
        if not (expr.arg_kinds in ([ARG_POS], [ARG_POS, ARG_POS])
                and isinstance(expr.args[0], GeneratorExpr)):
            return None

        gen = expr.args[0]

        retval = self.alloc_temp(self.node_type(expr))
        default_val = None
        if len(expr.args) > 1:
            default_val = self.accept(expr.args[1])

        exit_block = BasicBlock()

        def gen_inner_stmts() -> None:
            # next takes the first element of the generator, so if
            # something gets produced, we are done.
            self.assign(retval, self.accept(gen.left_expr), gen.left_expr.line)
            self.goto(exit_block)

        loop_params = list(zip(gen.indices, gen.sequences, gen.condlists))
        self.comprehension_helper(loop_params, gen_inner_stmts, gen.line)

        # Now we need the case for when nothing got hit. If there was
        # a default value, we produce it, and otherwise we raise
        # StopIteration.
        if default_val:
            self.assign(retval, default_val, gen.left_expr.line)
            self.goto(exit_block)
        else:
            self.add(RaiseStandardError(RaiseStandardError.STOP_ITERATION, None, expr.line))
            self.add(Unreachable())

        self.activate_block(exit_block)
        return retval

    @specialize_function('builtins.isinstance')
    def translate_isinstance(self, expr: CallExpr, callee: RefExpr) -> Optional[Value]:
        # Special case builtins.isinstance
        if (len(expr.args) == 2
                and expr.arg_kinds == [ARG_POS, ARG_POS]
                and isinstance(expr.args[1], (RefExpr, TupleExpr))):
            irs = self.flatten_classes(expr.args[1])
            if irs is not None:
                return self.isinstance_helper(self.accept(expr.args[0]), irs, expr.line)
        return None

    def flatten_classes(self, arg: Union[RefExpr, TupleExpr]) -> Optional[List[ClassIR]]:
        """Flatten classes in isinstance(obj, (A, (B, C))).

        If at least one item is not a reference to a native class, return None.
        """
        if isinstance(arg, RefExpr):
            if isinstance(arg.node, TypeInfo) and self.is_native_module_ref_expr(arg):
                ir = self.mapper.type_to_ir.get(arg.node)
                if ir:
                    return [ir]
            return None
        else:
            res = []  # type: List[ClassIR]
            for item in arg.items:
                if isinstance(item, (RefExpr, TupleExpr)):
                    item_part = self.flatten_classes(item)
                    if item_part is None:
                        return None
                    res.extend(item_part)
                else:
                    return None
            return res

    def visit_await_expr(self, o: AwaitExpr) -> Value:
        return self.handle_yield_from_and_await(o)

    # Unimplemented constructs
    def visit_assignment_expr(self, o: AssignmentExpr) -> Value:
        self.bail("I Am The Walrus (unimplemented)", o.line)

    # Unimplemented constructs that shouldn't come up because they are py2 only
    def visit_backquote_expr(self, o: BackquoteExpr) -> Value:
        self.bail("Python 2 features are unsupported", o.line)

    def visit_exec_stmt(self, o: ExecStmt) -> None:
        self.bail("Python 2 features are unsupported", o.line)

    def visit_print_stmt(self, o: PrintStmt) -> None:
        self.bail("Python 2 features are unsupported", o.line)

    def visit_unicode_expr(self, o: UnicodeExpr) -> Value:
        self.bail("Python 2 features are unsupported", o.line)

    # Constructs that shouldn't ever show up
    def visit_enum_call_expr(self, o: EnumCallExpr) -> Value:
        assert False, "can't compile analysis-only expressions"

    def visit__promote_expr(self, o: PromoteExpr) -> Value:
        assert False, "can't compile analysis-only expressions"

    def visit_namedtuple_expr(self, o: NamedTupleExpr) -> Value:
        assert False, "can't compile analysis-only expressions"

    def visit_newtype_expr(self, o: NewTypeExpr) -> Value:
        assert False, "can't compile analysis-only expressions"

    def visit_temp_node(self, o: TempNode) -> Value:
        assert False, "can't compile analysis-only expressions"

    def visit_type_alias_expr(self, o: TypeAliasExpr) -> Value:
        assert False, "can't compile analysis-only expressions"

    def visit_type_application(self, o: TypeApplication) -> Value:
        assert False, "can't compile analysis-only expressions"

    def visit_type_var_expr(self, o: TypeVarExpr) -> Value:
        assert False, "can't compile analysis-only expressions"

    def visit_typeddict_expr(self, o: TypedDictExpr) -> Value:
        assert False, "can't compile analysis-only expressions"

    def visit_reveal_expr(self, o: RevealExpr) -> Value:
        assert False, "can't compile analysis-only expressions"

    def visit_var(self, o: Var) -> None:
        assert False, "can't compile Var; should have been handled already?"

    def visit_cast_expr(self, o: CastExpr) -> Value:
        assert False, "CastExpr should have been handled in CallExpr"

    def visit_star_expr(self, o: StarExpr) -> Value:
        assert False, "should have been handled in Tuple/List/Set/DictExpr or CallExpr"

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
        if self.blocks[-1]:
            assert isinstance(self.blocks[-1][-1].ops[-1], ControlOp)

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
                try:
                    res = node.accept(self)
                    res = self.coerce(res, self.node_type(node), node.line)
                # If we hit an error during compilation, we want to
                # keep trying, so we can produce more error
                # messages. Generate a temp of the right type to keep
                # from causing more downstream trouble.
                except UnsupportedException:
                    res = self.alloc_temp(self.node_type(node))
                return res
            else:
                try:
                    node.accept(self)
                except UnsupportedException:
                    pass
                return None

    def alloc_temp(self, type: RType) -> Register:
        return self.environment.add_temp(type)

    def type_to_rtype(self, typ: Optional[Type]) -> RType:
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

    def make_dict(self, key_value_pairs: Sequence[DictEntry], line: int) -> Value:
        result = None  # type: Union[Value, None]
        initial_items = []  # type: List[Value]
        for key, value in key_value_pairs:
            if key is not None:
                # key:value
                if result is None:
                    initial_items.extend((key, value))
                    continue

                self.translate_special_method_call(
                    result,
                    '__setitem__',
                    [key, value],
                    result_type=None,
                    line=line)
            else:
                # **value
                if result is None:
                    result = self.primitive_op(new_dict_op, initial_items, line)

                self.primitive_op(
                    dict_update_in_display_op,
                    [result, value],
                    line=line
                )

        if result is None:
            result = self.primitive_op(new_dict_op, initial_items, line)

        return result

    def none(self) -> Value:
        return self.add(PrimitiveOp([], none_op, line=-1))

    def none_object(self) -> Value:
        return self.add(PrimitiveOp([], none_object_op, line=-1))

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
            env.type.class_ir.attributes[symbol.name] = target.type
            symbol_target = AssignmentTargetAttr(env, symbol.name)
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
        """Loads the registers for the current FuncItem being visited.

        Adds the arguments of the FuncItem to the environment. If the FuncItem is nested inside of
        another function, then this also loads all of the outer environments of the FuncItem into
        registers so that they can be used when accessing free variables.
        """
        self.add_args_to_env(local=True)

        fn_info = self.fn_info
        fitem = fn_info.fitem
        if fn_info.is_nested:
            self.load_outer_envs(fn_info.callable_class)
            # If this is a FuncDef, then make sure to load the FuncDef into its own environment
            # class so that the function can be called recursively.
            if isinstance(fitem, FuncDef):
                self.setup_func_for_recursive_call(fitem, fn_info.callable_class)

    def add_var_to_env_class(self,
                             var: SymbolNode,
                             rtype: RType,
                             base: Union[FuncInfo, ImplicitClass],
                             reassign: bool = False) -> AssignmentTarget:
        # First, define the variable name as an attribute of the environment class, and then
        # construct a target for that attribute.
        self.fn_info.env_class.attributes[var.name] = rtype
        attr_target = AssignmentTargetAttr(base.curr_env_reg, var.name)

        if reassign:
            # Read the local definition of the variable, and set the corresponding attribute of
            # the environment class' variable to be that value.
            reg = self.read(self.environment.lookup(var), self.fn_info.fitem.line)
            self.add(SetAttr(base.curr_env_reg, var.name, reg, self.fn_info.fitem.line))

        # Override the local definition of the variable to instead point at the variable in
        # the environment class.
        return self.environment.add_target(var, attr_target)

    def setup_func_for_recursive_call(self, fdef: FuncDef, base: ImplicitClass) -> None:
        """
        Adds the instance of the callable class representing the given FuncDef to a register in the
        environment so that the function can be called recursively. Note that this needs to be done
        only for nested functions.
        """
        # First, set the attribute of the environment class so that GetAttr can be called on it.
        prev_env = self.fn_infos[-2].env_class
        prev_env.attributes[fdef.name] = self.type_to_rtype(fdef.type)

        if isinstance(base, GeneratorClass):
            # If we are dealing with a generator class, then we need to first get the register
            # holding the current environment class, and load the previous environment class from
            # there.
            prev_env_reg = self.add(GetAttr(base.curr_env_reg, ENV_ATTR_NAME, -1))
        else:
            prev_env_reg = base.prev_env_reg

        # Obtain the instance of the callable class representing the FuncDef, and add it to the
        # current environment.
        val = self.add(GetAttr(prev_env_reg, fdef.name, -1))
        target = self.environment.add_local_reg(fdef, object_rprimitive)
        self.assign(target, val, -1)

    def setup_env_for_generator_class(self) -> None:
        """Populates the environment for a generator class."""
        fitem = self.fn_info.fitem
        cls = self.fn_info.generator_class
        self_target = self.add_self_to_env(cls.ir)

        # Add the type, value, and traceback variables to the environment.
        exc_type = self.environment.add_local(Var('type'), object_rprimitive, is_arg=True)
        exc_val = self.environment.add_local(Var('value'), object_rprimitive, is_arg=True)
        exc_tb = self.environment.add_local(Var('traceback'), object_rprimitive, is_arg=True)
        # TODO: Use the right type here instead of object?
        exc_arg = self.environment.add_local(Var('arg'), object_rprimitive, is_arg=True)

        cls.exc_regs = (exc_type, exc_val, exc_tb)
        cls.send_arg_reg = exc_arg

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

    def add_args_to_env(self,
                        local: bool = True,
                        base: Optional[Union[FuncInfo, ImplicitClass]] = None,
                        reassign: bool = True) -> None:
        fn_info = self.fn_info
        if local:
            for arg in fn_info.fitem.arguments:
                rtype = self.type_to_rtype(arg.variable.type)
                self.environment.add_local_reg(arg.variable, rtype, is_arg=True)
        else:
            for arg in fn_info.fitem.arguments:
                if self.is_free_variable(arg.variable) or fn_info.is_generator:
                    rtype = self.type_to_rtype(arg.variable.type)
                    assert base is not None, 'base cannot be None for adding nonlocal args'
                    self.add_var_to_env_class(arg.variable, rtype, base, reassign=reassign)

    def gen_func_ns(self) -> str:
        """Generates a namespace for a nested function using its outer function names."""
        return '_'.join(info.name + ('' if not info.class_name else '_' + info.class_name)
                        for info in self.fn_infos
                        if info.name and info.name != '<top level>')

    def setup_callable_class(self) -> None:
        """Generates a callable class representing a nested function or a function within a
        non-extension class and sets up the 'self' variable for that class.

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
        name = base_name = '{}_obj'.format(self.fn_info.namespaced_name())
        count = 0
        while name in self.callable_class_names:
            name = base_name + '_' + str(count)
            count += 1
        self.callable_class_names.add(name)

        # Define the actual callable class ClassIR, and set its environment to point at the
        # previously defined environment class.
        callable_class_ir = ClassIR(name, self.module_name, is_generated=True)

        # The functools @wraps decorator attempts to call setattr on nested functions, so
        # we create a dict for these nested functions.
        # https://github.com/python/cpython/blob/3.7/Lib/functools.py#L58
        if self.fn_info.is_nested:
            callable_class_ir.has_dict = True

        # If the enclosing class doesn't contain nested (which will happen if
        # this is a toplevel lambda), don't set up an environment.
        if self.fn_infos[-2].contains_nested:
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
        sig = FuncSignature((RuntimeArg(SELF_NAME, object_rprimitive),) + sig.args, sig.ret_type)
        call_fn_decl = FuncDecl('__call__', fn_info.callable_class.ir.name, self.module_name, sig)
        call_fn_ir = FuncIR(call_fn_decl, blocks, env,
                            fn_info.fitem.line, traceback_name=fn_info.fitem.name)
        fn_info.callable_class.ir.methods['__call__'] = call_fn_ir
        return call_fn_ir

    def add_get_to_callable_class(self, fn_info: FuncInfo) -> None:
        """Generates the '__get__' method for a callable class."""
        line = fn_info.fitem.line
        self.enter(fn_info)

        vself = self.read(self.environment.add_local_reg(Var(SELF_NAME), object_rprimitive, True))
        instance = self.environment.add_local_reg(Var('instance'), object_rprimitive, True)
        self.environment.add_local_reg(Var('owner'), object_rprimitive, True)

        # If accessed through the class, just return the callable
        # object. If accessed through an object, create a new bound
        # instance method object.
        instance_block, class_block = BasicBlock(), BasicBlock()
        comparison = self.binary_op(self.read(instance), self.none_object(), 'is', line)
        self.add_bool_branch(comparison, class_block, instance_block)

        self.activate_block(class_block)
        self.add(Return(vself))

        self.activate_block(instance_block)
        self.add(Return(self.primitive_op(method_new_op, [vself, self.read(instance)], line)))

        blocks, env, _, fn_info = self.leave()

        sig = FuncSignature((RuntimeArg(SELF_NAME, object_rprimitive),
                             RuntimeArg('instance', object_rprimitive),
                             RuntimeArg('owner', object_rprimitive)),
                            object_rprimitive)
        get_fn_decl = FuncDecl('__get__', fn_info.callable_class.ir.name, self.module_name, sig)
        get_fn_ir = FuncIR(get_fn_decl, blocks, env)
        fn_info.callable_class.ir.methods['__get__'] = get_fn_ir
        self.functions.append(get_fn_ir)

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
        curr_env_reg = None
        if self.fn_info.is_generator:
            curr_env_reg = self.fn_info.generator_class.curr_env_reg
        elif self.fn_info.is_nested:
            curr_env_reg = self.fn_info.callable_class.curr_env_reg
        elif self.fn_info.contains_nested:
            curr_env_reg = self.fn_info.curr_env_reg
        if curr_env_reg:
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
        env_class = ClassIR('{}_env'.format(self.fn_info.namespaced_name()),
                            self.module_name, is_generated=True)
        env_class.attributes[SELF_NAME] = RInstance(env_class)
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
        self.gen_arg_defaults()
        self.finalize_env_class()
        self.add(Return(self.instantiate_generator_class()))

    def setup_generator_class(self) -> ClassIR:
        name = '{}_gen'.format(self.fn_info.namespaced_name())

        generator_class_ir = ClassIR(name, self.module_name, is_generated=True)
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
        sig = FuncSignature((RuntimeArg(SELF_NAME, object_rprimitive),
                             RuntimeArg('type', object_rprimitive),
                             RuntimeArg('value', object_rprimitive),
                             RuntimeArg('traceback', object_rprimitive),
                             RuntimeArg('arg', object_rprimitive)
                             ), sig.ret_type)
        helper_fn_decl = FuncDecl('__mypyc_generator_helper__', fn_info.generator_class.ir.name,
                                  self.module_name, sig)
        helper_fn_ir = FuncIR(helper_fn_decl, blocks, env,
                              fn_info.fitem.line, traceback_name=fn_info.fitem.name)
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
        sig = FuncSignature((RuntimeArg(SELF_NAME, object_rprimitive),), object_rprimitive)
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
        none_reg = self.none_object()

        # Call the helper function with error flags set to Py_None, and return that result.
        result = self.add(Call(fn_decl, [self_reg, none_reg, none_reg, none_reg, none_reg],
                               fn_info.fitem.line))
        self.add(Return(result))
        blocks, env, _, fn_info = self.leave()

        sig = FuncSignature((RuntimeArg(SELF_NAME, object_rprimitive),), sig.ret_type)
        next_fn_decl = FuncDecl('__next__', fn_info.generator_class.ir.name, self.module_name, sig)
        next_fn_ir = FuncIR(next_fn_decl, blocks, env)
        fn_info.generator_class.ir.methods['__next__'] = next_fn_ir
        self.functions.append(next_fn_ir)

    def add_send_to_generator_class(self,
                                    fn_info: FuncInfo,
                                    fn_decl: FuncDecl,
                                    sig: FuncSignature) -> None:
        """Generates the 'send' method for a generator class."""
        # FIXME: this is basically the same as add_next...
        self.enter(fn_info)
        self_reg = self.read(self.add_self_to_env(fn_info.generator_class.ir))
        arg = self.environment.add_local_reg(Var('arg'), object_rprimitive, True)
        none_reg = self.none_object()

        # Call the helper function with error flags set to Py_None, and return that result.
        result = self.add(Call(fn_decl, [self_reg, none_reg, none_reg, none_reg, self.read(arg)],
                               fn_info.fitem.line))
        self.add(Return(result))
        blocks, env, _, fn_info = self.leave()

        sig = FuncSignature((RuntimeArg(SELF_NAME, object_rprimitive),
                             RuntimeArg('arg', object_rprimitive),), sig.ret_type)
        next_fn_decl = FuncDecl('send', fn_info.generator_class.ir.name, self.module_name, sig)
        next_fn_ir = FuncIR(next_fn_decl, blocks, env)
        fn_info.generator_class.ir.methods['send'] = next_fn_ir
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
        none_reg = self.none_object()
        self.assign_if_null(val, lambda: none_reg, self.fn_info.fitem.line)
        self.assign_if_null(tb, lambda: none_reg, self.fn_info.fitem.line)

        # Call the helper function using the arguments passed in, and return that result.
        result = self.add(Call(fn_decl,
                               [self_reg, self.read(typ), self.read(val), self.read(tb), none_reg],
                               fn_info.fitem.line))
        self.add(Return(result))
        blocks, env, _, fn_info = self.leave()

        # Create the FuncSignature for the throw function. NOte that the value and traceback fields
        # are optional, and are assigned to if they are not passed in inside the body of the throw
        # function.
        sig = FuncSignature((RuntimeArg(SELF_NAME, object_rprimitive),
                             RuntimeArg('type', object_rprimitive),
                             RuntimeArg('value', object_rprimitive, ARG_OPT),
                             RuntimeArg('traceback', object_rprimitive, ARG_OPT)),
                            sig.ret_type)

        throw_fn_decl = FuncDecl('throw', fn_info.generator_class.ir.name, self.module_name, sig)
        throw_fn_ir = FuncIR(throw_fn_decl, blocks, env)
        fn_info.generator_class.ir.methods['throw'] = throw_fn_ir
        self.functions.append(throw_fn_ir)

    def add_close_to_generator_class(self, fn_info: FuncInfo) -> None:
        """Generates the '__close__' method for a generator class."""
        # TODO: Currently this method just triggers a runtime error,
        # we should fill this out eventually.
        self.enter(fn_info)
        self.add_self_to_env(fn_info.generator_class.ir)
        self.add(RaiseStandardError(RaiseStandardError.RUNTIME_ERROR,
                                    'close method on generator classes uimplemented',
                                    fn_info.fitem.line))
        self.add(Unreachable())
        blocks, env, _, fn_info = self.leave()

        # Next, add the actual function as a method of the generator class.
        sig = FuncSignature((RuntimeArg(SELF_NAME, object_rprimitive),), object_rprimitive)
        close_fn_decl = FuncDecl('close', fn_info.generator_class.ir.name, self.module_name, sig)
        close_fn_ir = FuncIR(close_fn_decl, blocks, env)
        fn_info.generator_class.ir.methods['close'] = close_fn_ir
        self.functions.append(close_fn_ir)

    def add_await_to_generator_class(self, fn_info: FuncInfo) -> None:
        """Generates the '__await__' method for a generator class."""
        self.enter(fn_info)
        self_target = self.add_self_to_env(fn_info.generator_class.ir)
        self.add(Return(self.read(self_target, fn_info.fitem.line)))
        blocks, env, _, fn_info = self.leave()

        # Next, add the actual function as a method of the generator class.
        sig = FuncSignature((RuntimeArg(SELF_NAME, object_rprimitive),), object_rprimitive)
        await_fn_decl = FuncDecl('__await__', fn_info.generator_class.ir.name,
                                 self.module_name, sig)
        await_fn_ir = FuncIR(await_fn_decl, blocks, env)
        fn_info.generator_class.ir.methods['__await__'] = await_fn_ir
        self.functions.append(await_fn_ir)

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
        comparison = self.binary_op(exc_type, self.none_object(), 'is not', line)
        self.add_bool_branch(comparison, error_block, ok_block)

        self.activate_block(error_block)
        self.primitive_op(raise_exception_with_tb_op, [exc_type, exc_val, exc_tb], line)
        self.add(Unreachable())
        self.goto_and_activate(ok_block)

    def add_self_to_env(self, cls: ClassIR) -> AssignmentTargetRegister:
        return self.environment.add_local_reg(Var(SELF_NAME),
                                              RInstance(cls),
                                              is_arg=True)

    def is_builtin_ref_expr(self, expr: RefExpr) -> bool:
        assert expr.node, "RefExpr not resolved"
        return '.' in expr.node.fullname and expr.node.fullname.split('.')[0] == 'builtins'

    def load_global(self, expr: NameExpr) -> Value:
        """Loads a Python-level global.

        This takes a NameExpr and uses its name as a key to retrieve the corresponding PyObject *
        from the _globals dictionary in the C-generated code.
        """
        # If the global is from 'builtins', turn it into a module attr load instead
        if self.is_builtin_ref_expr(expr):
            assert expr.node, "RefExpr not resolved"
            return self.load_module_attr_by_fullname(expr.node.fullname, expr.line)
        if (self.is_native_module_ref_expr(expr) and isinstance(expr.node, TypeInfo)
                and not self.is_synthetic_type(expr.node)):
            assert expr.fullname is not None
            return self.load_native_type_object(expr.fullname)
        return self.load_global_str(expr.name, expr.line)

    def load_global_str(self, name: str, line: int) -> Value:
        _globals = self.load_globals_dict()
        reg = self.load_static_unicode(name)
        return self.primitive_op(dict_get_item_op, [_globals, reg], line)

    def load_globals_dict(self) -> Value:
        return self.add(LoadStatic(dict_rprimitive, 'globals', self.module_name))

    def literal_static_name(self, value: Union[int, float, complex, str, bytes]) -> str:
        return self.mapper.literal_static_name(self.current_module, value)

    def load_static_int(self, value: int) -> Value:
        """Loads a static integer Python 'int' object into a register."""
        static_symbol = self.literal_static_name(value)
        return self.add(LoadStatic(int_rprimitive, static_symbol, ann=value))

    def load_static_float(self, value: float) -> Value:
        """Loads a static float value into a register."""
        static_symbol = self.literal_static_name(value)
        return self.add(LoadStatic(float_rprimitive, static_symbol, ann=value))

    def load_static_bytes(self, value: bytes) -> Value:
        """Loads a static bytes value into a register."""
        static_symbol = self.literal_static_name(value)
        return self.add(LoadStatic(object_rprimitive, static_symbol, ann=value))

    def load_static_complex(self, value: complex) -> Value:
        """Loads a static complex value into a register."""
        static_symbol = self.literal_static_name(value)
        return self.add(LoadStatic(object_rprimitive, static_symbol, ann=value))

    def load_static_unicode(self, value: str) -> Value:
        """Loads a static unicode value into a register.

        This is useful for more than just unicode literals; for example, method calls
        also require a PyObject * form for the name of the method.
        """
        static_symbol = self.literal_static_name(value)
        return self.add(LoadStatic(str_rprimitive, static_symbol, ann=value))

    def load_module(self, name: str) -> Value:
        return self.add(LoadStatic(object_rprimitive, name, namespace=NAMESPACE_MODULE))

    def load_module_attr_by_fullname(self, fullname: str, line: int) -> Value:
        module, _, name = fullname.rpartition('.')
        left = self.load_module(module)
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
                and not is_runtime_subtype(src.type, target_type)):
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

    def native_args_to_positional(self,
                                  args: Sequence[Value],
                                  arg_kinds: List[int],
                                  arg_names: Sequence[Optional[str]],
                                  sig: FuncSignature,
                                  line: int) -> List[Value]:
        """Prepare arguments for a native call.

        Given args/kinds/names and a target signature for a native call, map
        keyword arguments to their appropriate place in the argument list,
        fill in error values for unspecified default arguments,
        package arguments that will go into *args/**kwargs into a tuple/dict,
        and coerce arguments to the appropriate type.
        """

        sig_arg_kinds = [arg.kind for arg in sig.args]
        sig_arg_names = [arg.name for arg in sig.args]
        formal_to_actual = map_actuals_to_formals(arg_kinds,
                                                  arg_names,
                                                  sig_arg_kinds,
                                                  sig_arg_names,
                                                  lambda n: AnyType(TypeOfAny.special_form))

        # Flatten out the arguments, loading error values for default
        # arguments, constructing tuples/dicts for star args, and
        # coercing everything to the expected type.
        output_args = []
        for lst, arg in zip(formal_to_actual, sig.args):
            output_arg = None
            if arg.kind == ARG_STAR:
                output_arg = self.primitive_op(new_tuple_op, [args[i] for i in lst], line)
            elif arg.kind == ARG_STAR2:
                dict_entries = [(self.load_static_unicode(cast(str, arg_names[i])), args[i])
                                for i in lst]
                output_arg = self.make_dict(dict_entries, line)
            elif not lst:
                output_arg = self.add(LoadErrorValue(arg.type, is_borrowed=True))
            else:
                output_arg = args[lst[0]]
            output_args.append(self.coerce(output_arg, arg.type, line))

        return output_args

    def get_func_target(self, fdef: FuncDef) -> AssignmentTarget:
        """
        Given a FuncDef, return the target associated the instance of its callable class. If the
        function was not already defined somewhere, then define it and add it to the current
        environment.
        """
        if fdef.original_def:
            # Get the target associated with the previously defined FuncDef.
            return self.environment.lookup(fdef.original_def)

        if self.fn_info.is_generator or self.fn_info.contains_nested:
            return self.environment.lookup(fdef)

        return self.environment.add_local_reg(fdef, object_rprimitive)

    # Lacks a good type because there wasn't a reasonable type in 3.5 :(
    def catch_errors(self, line: int) -> Any:
        return catch_errors(self.module_path, line)

    def warning(self, msg: str, line: int) -> None:
        self.errors.warning(msg, self.module_path, line)

    def error(self, msg: str, line: int) -> None:
        self.errors.error(msg, self.module_path, line)

    def bail(self, msg: str, line: int) -> 'NoReturn':
        """Reports an error and aborts compilation up until the last accept() call

        (accept() catches the UnsupportedException and keeps on
        processing. This allows errors to be non-blocking without always
        needing to write handling for them.
        """
        self.error(msg, line)
        raise UnsupportedException()
