"""Transform class definitions from the mypy AST form to IR."""

from __future__ import annotations

from abc import abstractmethod
from typing import Callable, Final

from mypy.nodes import (
    EXCLUDED_ENUM_ATTRIBUTES,
    TYPE_VAR_TUPLE_KIND,
    AssignmentStmt,
    CallExpr,
    ClassDef,
    Decorator,
    EllipsisExpr,
    ExpressionStmt,
    FuncDef,
    Lvalue,
    MemberExpr,
    NameExpr,
    OverloadedFuncDef,
    PassStmt,
    RefExpr,
    StrExpr,
    TempNode,
    TypeInfo,
    TypeParam,
    is_class_var,
)
from mypy.types import Instance, UnboundType, get_proper_type
from mypyc.common import PROPSET_PREFIX
from mypyc.ir.class_ir import ClassIR, NonExtClassInfo
from mypyc.ir.func_ir import FuncDecl, FuncSignature
from mypyc.ir.ops import (
    NAMESPACE_TYPE,
    BasicBlock,
    Branch,
    Call,
    InitStatic,
    LoadAddress,
    LoadErrorValue,
    LoadStatic,
    MethodCall,
    Register,
    Return,
    SetAttr,
    TupleSet,
    Value,
)
from mypyc.ir.rtypes import (
    RType,
    bool_rprimitive,
    dict_rprimitive,
    is_none_rprimitive,
    is_object_rprimitive,
    is_optional_type,
    object_rprimitive,
)
from mypyc.irbuild.builder import IRBuilder, create_type_params
from mypyc.irbuild.function import (
    gen_property_getter_ir,
    gen_property_setter_ir,
    handle_ext_method,
    handle_non_ext_method,
    load_type,
)
from mypyc.irbuild.prepare import GENERATOR_HELPER_NAME
from mypyc.irbuild.util import dataclass_type, get_func_def, is_constant, is_dataclass_decorator
from mypyc.primitives.dict_ops import dict_new_op, dict_set_item_op
from mypyc.primitives.generic_ops import (
    iter_op,
    next_op,
    py_get_item_op,
    py_hasattr_op,
    py_setattr_op,
)
from mypyc.primitives.misc_ops import (
    dataclass_sleight_of_hand,
    import_op,
    not_implemented_op,
    py_calc_meta_op,
    pytype_from_template_op,
    type_object_op,
)
from mypyc.subtype import is_subtype


def transform_class_def(builder: IRBuilder, cdef: ClassDef) -> None:
    """Create IR for a class definition.

    This can generate both extension (native) and non-extension
    classes.  These are generated in very different ways. In the
    latter case we construct a Python type object at runtime by doing
    the equivalent of "type(name, bases, dict)" in IR. Extension
    classes are defined via C structs that are generated later in
    mypyc.codegen.emitclass.

    This is the main entry point to this module.
    """
    if cdef.info not in builder.mapper.type_to_ir:
        builder.error("Nested class definitions not supported", cdef.line)
        return

    ir = builder.mapper.type_to_ir[cdef.info]

    # We do this check here because the base field of parent
    # classes aren't necessarily populated yet at
    # prepare_class_def time.
    if any(ir.base_mro[i].base != ir.base_mro[i + 1] for i in range(len(ir.base_mro) - 1)):
        builder.error("Multiple inheritance is not supported (except for traits)", cdef.line)

    if ir.allow_interpreted_subclasses:
        for parent in ir.mro:
            if not parent.allow_interpreted_subclasses:
                builder.error(
                    'Base class "{}" does not allow interpreted subclasses'.format(
                        parent.fullname
                    ),
                    cdef.line,
                )

    # Currently, we only create non-extension classes for classes that are
    # decorated or inherit from Enum. Classes decorated with @trait do not
    # apply here, and are handled in a different way.
    if ir.is_ext_class:
        cls_type = dataclass_type(cdef)
        if cls_type is None:
            cls_builder: ClassBuilder = ExtClassBuilder(builder, cdef)
        elif cls_type in ["dataclasses", "attr-auto"]:
            cls_builder = DataClassBuilder(builder, cdef)
        elif cls_type == "attr":
            cls_builder = AttrsClassBuilder(builder, cdef)
        else:
            raise ValueError(cls_type)
    else:
        cls_builder = NonExtClassBuilder(builder, cdef)

    for stmt in cdef.defs.body:
        if (
            isinstance(stmt, (FuncDef, Decorator, OverloadedFuncDef))
            and stmt.name == GENERATOR_HELPER_NAME
        ):
            builder.error(
                f'Method name "{stmt.name}" is reserved for mypyc internal use', stmt.line
            )

        if isinstance(stmt, OverloadedFuncDef) and stmt.is_property:
            if isinstance(cls_builder, NonExtClassBuilder):
                # properties with both getters and setters in non_extension
                # classes not supported
                builder.error("Property setters not supported in non-extension classes", stmt.line)
            for item in stmt.items:
                with builder.catch_errors(stmt.line):
                    cls_builder.add_method(get_func_def(item))
        elif isinstance(stmt, (FuncDef, Decorator, OverloadedFuncDef)):
            # Ignore plugin generated methods (since they have no
            # bodies to compile and will need to have the bodies
            # provided by some other mechanism.)
            if cdef.info.names[stmt.name].plugin_generated:
                continue
            with builder.catch_errors(stmt.line):
                cls_builder.add_method(get_func_def(stmt))
        elif isinstance(stmt, PassStmt) or (
            isinstance(stmt, ExpressionStmt) and isinstance(stmt.expr, EllipsisExpr)
        ):
            continue
        elif isinstance(stmt, AssignmentStmt):
            if len(stmt.lvalues) != 1:
                builder.error("Multiple assignment in class bodies not supported", stmt.line)
                continue
            lvalue = stmt.lvalues[0]
            if not isinstance(lvalue, NameExpr):
                builder.error(
                    "Only assignment to variables is supported in class bodies", stmt.line
                )
                continue
            # We want to collect class variables in a dictionary for both real
            # non-extension classes and fake dataclass ones.
            cls_builder.add_attr(lvalue, stmt)

        elif isinstance(stmt, ExpressionStmt) and isinstance(stmt.expr, StrExpr):
            # Docstring. Ignore
            pass
        else:
            builder.error("Unsupported statement in class body", stmt.line)

    # Generate implicit property setters/getters
    for name, decl in ir.method_decls.items():
        if decl.implicit and decl.is_prop_getter:
            getter_ir = gen_property_getter_ir(builder, decl, cdef, ir.is_trait)
            builder.functions.append(getter_ir)
            ir.methods[getter_ir.decl.name] = getter_ir

            setter_ir = None
            setter_name = PROPSET_PREFIX + name
            if setter_name in ir.method_decls:
                setter_ir = gen_property_setter_ir(
                    builder, ir.method_decls[setter_name], cdef, ir.is_trait
                )
                builder.functions.append(setter_ir)
                ir.methods[setter_name] = setter_ir

            ir.properties[name] = (getter_ir, setter_ir)
            # TODO: Generate glue method if needed?
            # TODO: Do we need interpreted glue methods? Maybe not?

    cls_builder.finalize(ir)


class ClassBuilder:
    """Create IR for a class definition.

    This is an abstract base class.
    """

    def __init__(self, builder: IRBuilder, cdef: ClassDef) -> None:
        self.builder = builder
        self.cdef = cdef
        self.attrs_to_cache: list[tuple[Lvalue, RType]] = []

    @abstractmethod
    def add_method(self, fdef: FuncDef) -> None:
        """Add a method to the class IR"""

    @abstractmethod
    def add_attr(self, lvalue: NameExpr, stmt: AssignmentStmt) -> None:
        """Add an attribute to the class IR"""

    @abstractmethod
    def finalize(self, ir: ClassIR) -> None:
        """Perform any final operations to complete the class IR"""


class NonExtClassBuilder(ClassBuilder):
    def __init__(self, builder: IRBuilder, cdef: ClassDef) -> None:
        super().__init__(builder, cdef)
        self.non_ext = self.create_non_ext_info()

    def create_non_ext_info(self) -> NonExtClassInfo:
        non_ext_bases = populate_non_ext_bases(self.builder, self.cdef)
        non_ext_metaclass = find_non_ext_metaclass(self.builder, self.cdef, non_ext_bases)
        non_ext_dict = setup_non_ext_dict(
            self.builder, self.cdef, non_ext_metaclass, non_ext_bases
        )
        # We populate __annotations__ for non-extension classes
        # because dataclasses uses it to determine which attributes to compute on.
        # TODO: Maybe generate more precise types for annotations
        non_ext_anns = self.builder.call_c(dict_new_op, [], self.cdef.line)
        return NonExtClassInfo(non_ext_dict, non_ext_bases, non_ext_anns, non_ext_metaclass)

    def add_method(self, fdef: FuncDef) -> None:
        handle_non_ext_method(self.builder, self.non_ext, self.cdef, fdef)

    def add_attr(self, lvalue: NameExpr, stmt: AssignmentStmt) -> None:
        add_non_ext_class_attr_ann(self.builder, self.non_ext, lvalue, stmt)
        add_non_ext_class_attr(
            self.builder, self.non_ext, lvalue, stmt, self.cdef, self.attrs_to_cache
        )

    def finalize(self, ir: ClassIR) -> None:
        # Dynamically create the class via the type constructor
        non_ext_class = load_non_ext_class(self.builder, ir, self.non_ext, self.cdef.line)
        non_ext_class = load_decorated_class(self.builder, self.cdef, non_ext_class)

        # Try to avoid contention when using free threading.
        self.builder.set_immortal_if_free_threaded(non_ext_class, self.cdef.line)

        # Save the decorated class
        self.builder.add(
            InitStatic(non_ext_class, self.cdef.name, self.builder.module_name, NAMESPACE_TYPE)
        )

        # Add the non-extension class to the dict
        self.builder.primitive_op(
            dict_set_item_op,
            [
                self.builder.load_globals_dict(),
                self.builder.load_str(self.cdef.name),
                non_ext_class,
            ],
            self.cdef.line,
        )

        # Cache any cacheable class attributes
        cache_class_attrs(self.builder, self.attrs_to_cache, self.cdef)


class ExtClassBuilder(ClassBuilder):
    def __init__(self, builder: IRBuilder, cdef: ClassDef) -> None:
        super().__init__(builder, cdef)
        # If the class is not decorated, generate an extension class for it.
        self.type_obj: Value | None = allocate_class(builder, cdef)

    def skip_attr_default(self, name: str, stmt: AssignmentStmt) -> bool:
        """Controls whether to skip generating a default for an attribute."""
        return False

    def add_method(self, fdef: FuncDef) -> None:
        handle_ext_method(self.builder, self.cdef, fdef)

    def add_attr(self, lvalue: NameExpr, stmt: AssignmentStmt) -> None:
        # Variable declaration with no body
        if isinstance(stmt.rvalue, TempNode):
            return
        # Only treat marked class variables as class variables.
        if not (is_class_var(lvalue) or stmt.is_final_def):
            return
        typ = self.builder.load_native_type_object(self.cdef.fullname)
        value = self.builder.accept(stmt.rvalue)
        self.builder.primitive_op(
            py_setattr_op, [typ, self.builder.load_str(lvalue.name), value], stmt.line
        )
        if self.builder.non_function_scope() and stmt.is_final_def:
            self.builder.init_final_static(lvalue, value, self.cdef.name)

    def finalize(self, ir: ClassIR) -> None:
        attrs_with_defaults, default_assignments = find_attr_initializers(
            self.builder, self.cdef, self.skip_attr_default
        )
        ir.attrs_with_defaults.update(attrs_with_defaults)
        generate_attr_defaults_init(self.builder, self.cdef, default_assignments)
        create_ne_from_eq(self.builder, self.cdef)


class DataClassBuilder(ExtClassBuilder):
    # controls whether an __annotations__ attribute should be added to the class
    # __dict__.  This is not desirable for attrs classes where auto_attribs is
    # disabled, as attrs will reject it.
    add_annotations_to_dict = True

    def __init__(self, builder: IRBuilder, cdef: ClassDef) -> None:
        super().__init__(builder, cdef)
        self.non_ext = self.create_non_ext_info()

    def create_non_ext_info(self) -> NonExtClassInfo:
        """Set up a NonExtClassInfo to track dataclass attributes.

        In addition to setting up a normal extension class for dataclasses,
        we also collect its class attributes like a non-extension class so
        that we can hand them to the dataclass decorator.
        """
        return NonExtClassInfo(
            self.builder.call_c(dict_new_op, [], self.cdef.line),
            self.builder.add(TupleSet([], self.cdef.line)),
            self.builder.call_c(dict_new_op, [], self.cdef.line),
            self.builder.add(LoadAddress(type_object_op.type, type_object_op.src, self.cdef.line)),
        )

    def skip_attr_default(self, name: str, stmt: AssignmentStmt) -> bool:
        return stmt.type is not None

    def get_type_annotation(self, stmt: AssignmentStmt) -> TypeInfo | None:
        # We populate __annotations__ because dataclasses uses it to determine
        # which attributes to compute on.
        ann_type = get_proper_type(stmt.type)
        if isinstance(ann_type, Instance):
            return ann_type.type
        return None

    def add_attr(self, lvalue: NameExpr, stmt: AssignmentStmt) -> None:
        add_non_ext_class_attr_ann(
            self.builder, self.non_ext, lvalue, stmt, self.get_type_annotation
        )
        add_non_ext_class_attr(
            self.builder, self.non_ext, lvalue, stmt, self.cdef, self.attrs_to_cache
        )
        super().add_attr(lvalue, stmt)

    def finalize(self, ir: ClassIR) -> None:
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
        super().finalize(ir)
        assert self.type_obj
        add_dunders_to_non_ext_dict(
            self.builder, self.non_ext, self.cdef.line, self.add_annotations_to_dict
        )
        dec = self.builder.accept(
            next(d for d in self.cdef.decorators if is_dataclass_decorator(d))
        )
        dataclass_type_val = self.builder.load_str(dataclass_type(self.cdef) or "unknown")
        self.builder.call_c(
            dataclass_sleight_of_hand,
            [dec, self.type_obj, self.non_ext.dict, self.non_ext.anns, dataclass_type_val],
            self.cdef.line,
        )


class AttrsClassBuilder(DataClassBuilder):
    """Create IR for an attrs class where auto_attribs=False (the default).

    When auto_attribs is enabled, attrs classes behave similarly to dataclasses
    (i.e. types are stored as annotations on the class) and are thus handled
    by DataClassBuilder, but when auto_attribs is disabled the types are
    provided via attr.ib(type=...)
    """

    add_annotations_to_dict = False

    def skip_attr_default(self, name: str, stmt: AssignmentStmt) -> bool:
        return True

    def get_type_annotation(self, stmt: AssignmentStmt) -> TypeInfo | None:
        if isinstance(stmt.rvalue, CallExpr):
            # find the type arg in `attr.ib(type=str)`
            callee = stmt.rvalue.callee
            if (
                isinstance(callee, MemberExpr)
                and callee.fullname in ["attr.ib", "attr.attr"]
                and "type" in stmt.rvalue.arg_names
            ):
                index = stmt.rvalue.arg_names.index("type")
                type_name = stmt.rvalue.args[index]
                if isinstance(type_name, NameExpr) and isinstance(type_name.node, TypeInfo):
                    lvalue = stmt.lvalues[0]
                    assert isinstance(lvalue, NameExpr), lvalue
                    return type_name.node
        return None


def allocate_class(builder: IRBuilder, cdef: ClassDef) -> Value:
    # OK AND NOW THE FUN PART
    base_exprs = cdef.base_type_exprs + cdef.removed_base_type_exprs
    new_style_type_args = cdef.type_args
    if new_style_type_args:
        bases = [make_generic_base_class(builder, cdef.fullname, new_style_type_args, cdef.line)]
    else:
        bases = []

    if base_exprs or new_style_type_args:
        bases.extend([builder.accept(x) for x in base_exprs])
        tp_bases = builder.new_tuple(bases, cdef.line)
    else:
        tp_bases = builder.add(LoadErrorValue(object_rprimitive, is_borrowed=True))
    modname = builder.load_str(builder.module_name)
    template = builder.add(
        LoadStatic(object_rprimitive, cdef.name + "_template", builder.module_name, NAMESPACE_TYPE)
    )
    # Create the class
    tp = builder.call_c(pytype_from_template_op, [template, tp_bases, modname], cdef.line)

    # Set type object to be immortal if free threaded, as otherwise reference count contention
    # can cause a big performance hit.
    builder.set_immortal_if_free_threaded(tp, cdef.line)

    # Immediately fix up the trait vtables, before doing anything with the class.
    ir = builder.mapper.type_to_ir[cdef.info]
    if not ir.is_trait and not ir.builtin_base:
        builder.add(
            Call(
                FuncDecl(
                    cdef.name + "_trait_vtable_setup",
                    None,
                    builder.module_name,
                    FuncSignature([], bool_rprimitive),
                ),
                [],
                -1,
            )
        )
    # Populate a '__mypyc_attrs__' field containing the list of attrs
    builder.primitive_op(
        py_setattr_op,
        [
            tp,
            builder.load_str("__mypyc_attrs__"),
            create_mypyc_attrs_tuple(builder, builder.mapper.type_to_ir[cdef.info], cdef.line),
        ],
        cdef.line,
    )

    # Save the class
    builder.add(InitStatic(tp, cdef.name, builder.module_name, NAMESPACE_TYPE))

    # Add it to the dict
    builder.primitive_op(
        dict_set_item_op, [builder.load_globals_dict(), builder.load_str(cdef.name), tp], cdef.line
    )

    return tp


def make_generic_base_class(
    builder: IRBuilder, fullname: str, type_args: list[TypeParam], line: int
) -> Value:
    """Construct Generic[...] base class object for a new-style generic class (Python 3.12)."""
    mod = builder.call_c(import_op, [builder.load_str("_typing")], line)
    tvs = create_type_params(builder, mod, type_args, line)
    args = []
    for tv, type_param in zip(tvs, type_args):
        if type_param.kind == TYPE_VAR_TUPLE_KIND:
            # Evaluate *Ts for a TypeVarTuple
            it = builder.primitive_op(iter_op, [tv], line)
            tv = builder.call_c(next_op, [it], line)
        args.append(tv)

    gent = builder.py_get_attr(mod, "Generic", line)
    if len(args) == 1:
        arg = args[0]
    else:
        arg = builder.new_tuple(args, line)

    base = builder.primitive_op(py_get_item_op, [gent, arg], line)
    return base


# Mypy uses these internally as base classes of TypedDict classes. These are
# lies and don't have any runtime equivalent.
MAGIC_TYPED_DICT_CLASSES: Final[tuple[str, ...]] = (
    "typing._TypedDict",
    "typing_extensions._TypedDict",
)


def populate_non_ext_bases(builder: IRBuilder, cdef: ClassDef) -> Value:
    """Create base class tuple of a non-extension class.

    The tuple is passed to the metaclass constructor.
    """
    is_named_tuple = cdef.info.is_named_tuple
    ir = builder.mapper.type_to_ir[cdef.info]
    bases = []
    for cls in (b.type for b in cdef.info.bases):
        if cls.fullname == "builtins.object":
            continue
        if is_named_tuple and cls.fullname in (
            "typing.Sequence",
            "typing.Iterable",
            "typing.Collection",
            "typing.Reversible",
            "typing.Container",
            "typing.Sized",
        ):
            # HAX: Synthesized base classes added by mypy don't exist at runtime, so skip them.
            #      This could break if they were added explicitly, though...
            continue
        # Add the current class to the base classes list of concrete subclasses
        if cls in builder.mapper.type_to_ir:
            base_ir = builder.mapper.type_to_ir[cls]
            if base_ir.children is not None:
                base_ir.children.append(ir)

        if cls.fullname in MAGIC_TYPED_DICT_CLASSES:
            # HAX: Mypy internally represents TypedDict classes differently from what
            #      should happen at runtime. Replace with something that works.
            module = "typing"
            name = "_TypedDict"
            base = builder.get_module_attr(module, name, cdef.line)
        elif is_named_tuple and cls.fullname == "builtins.tuple":
            name = "_NamedTuple"
            base = builder.get_module_attr("typing", name, cdef.line)
        else:
            cls_module = cls.fullname.rsplit(".", 1)[0]
            if cls_module == builder.current_module:
                base = builder.load_global_str(cls.name, cdef.line)
            else:
                base = builder.load_module_attr_by_fullname(cls.fullname, cdef.line)
        bases.append(base)
        if cls.fullname in MAGIC_TYPED_DICT_CLASSES:
            # The remaining base classes are synthesized by mypy and should be ignored.
            break
    return builder.new_tuple(bases, cdef.line)


def find_non_ext_metaclass(builder: IRBuilder, cdef: ClassDef, bases: Value) -> Value:
    """Find the metaclass of a class from its defs and bases."""
    if cdef.metaclass:
        declared_metaclass = builder.accept(cdef.metaclass)
    else:
        if cdef.info.typeddict_type is not None:
            # In Python 3.9, the metaclass for class-based TypedDict is typing._TypedDictMeta.
            # We can't easily calculate it generically, so special case it.
            return builder.get_module_attr("typing", "_TypedDictMeta", cdef.line)
        elif cdef.info.is_named_tuple:
            # In Python 3.9, the metaclass for class-based NamedTuple is typing.NamedTupleMeta.
            # We can't easily calculate it generically, so special case it.
            return builder.get_module_attr("typing", "NamedTupleMeta", cdef.line)

        declared_metaclass = builder.add(
            LoadAddress(type_object_op.type, type_object_op.src, cdef.line)
        )

    return builder.call_c(py_calc_meta_op, [declared_metaclass, bases], cdef.line)


def setup_non_ext_dict(
    builder: IRBuilder, cdef: ClassDef, metaclass: Value, bases: Value
) -> Value:
    """Initialize the class dictionary for a non-extension class.

    This class dictionary is passed to the metaclass constructor.
    """
    # Check if the metaclass defines a __prepare__ method, and if so, call it.
    has_prepare = builder.primitive_op(
        py_hasattr_op, [metaclass, builder.load_str("__prepare__")], cdef.line
    )

    non_ext_dict = Register(dict_rprimitive)

    true_block, false_block, exit_block = BasicBlock(), BasicBlock(), BasicBlock()
    builder.add_bool_branch(has_prepare, true_block, false_block)

    builder.activate_block(true_block)
    cls_name = builder.load_str(cdef.name)
    prepare_meth = builder.py_get_attr(metaclass, "__prepare__", cdef.line)
    prepare_dict = builder.py_call(prepare_meth, [cls_name, bases], cdef.line)
    builder.assign(non_ext_dict, prepare_dict, cdef.line)
    builder.goto(exit_block)

    builder.activate_block(false_block)
    builder.assign(non_ext_dict, builder.call_c(dict_new_op, [], cdef.line), cdef.line)
    builder.goto(exit_block)
    builder.activate_block(exit_block)

    return non_ext_dict


def add_non_ext_class_attr_ann(
    builder: IRBuilder,
    non_ext: NonExtClassInfo,
    lvalue: NameExpr,
    stmt: AssignmentStmt,
    get_type_info: Callable[[AssignmentStmt], TypeInfo | None] | None = None,
) -> None:
    """Add a class attribute to __annotations__ of a non-extension class."""
    # FIXME: try to better preserve the special forms and type parameters of generics.
    typ: Value | None = None
    if get_type_info is not None:
        type_info = get_type_info(stmt)
        if type_info:
            # NOTE: Using string type information is similar to using
            # `from __future__ import annotations` in standard python.
            # NOTE: For string types we need to use the fullname since it
            # includes the module. If string type doesn't have the module,
            # @dataclass will try to get the current module and fail since the
            # current module is not in sys.modules.
            if builder.current_module == type_info.module_name and stmt.line < type_info.line:
                typ = builder.load_str(type_info.fullname)
            else:
                typ = load_type(builder, type_info, stmt.unanalyzed_type, stmt.line)

    if typ is None:
        # FIXME: if get_type_info is not provided, don't fall back to stmt.type?
        ann_type = get_proper_type(stmt.type)
        if (
            isinstance(stmt.unanalyzed_type, UnboundType)
            and stmt.unanalyzed_type.original_str_expr is not None
        ):
            # Annotation is a forward reference, so don't attempt to load the actual
            # type and load the string instead.
            #
            # TODO: is it possible to determine whether a non-string annotation is
            # actually a forward reference due to the __annotations__ future?
            typ = builder.load_str(stmt.unanalyzed_type.original_str_expr)
        elif isinstance(ann_type, Instance):
            typ = load_type(builder, ann_type.type, stmt.unanalyzed_type, stmt.line)
        else:
            typ = builder.add(LoadAddress(type_object_op.type, type_object_op.src, stmt.line))

    key = builder.load_str(lvalue.name)
    builder.primitive_op(dict_set_item_op, [non_ext.anns, key, typ], stmt.line)


def add_non_ext_class_attr(
    builder: IRBuilder,
    non_ext: NonExtClassInfo,
    lvalue: NameExpr,
    stmt: AssignmentStmt,
    cdef: ClassDef,
    attr_to_cache: list[tuple[Lvalue, RType]],
) -> None:
    """Add a class attribute to __dict__ of a non-extension class."""
    # Only add the attribute to the __dict__ if the assignment is of the form:
    # x: type = value (don't add attributes of the form 'x: type' to the __dict__).
    if not isinstance(stmt.rvalue, TempNode):
        rvalue = builder.accept(stmt.rvalue)
        builder.add_to_non_ext_dict(non_ext, lvalue.name, rvalue, stmt.line)
        # We cache enum attributes to speed up enum attribute lookup since they
        # are final.
        if (
            cdef.info.bases
            # Enum class must be the last parent class.
            and cdef.info.bases[-1].type.is_enum
            # Skip these since Enum will remove it
            and lvalue.name not in EXCLUDED_ENUM_ATTRIBUTES
        ):
            # Enum values are always boxed, so use object_rprimitive.
            attr_to_cache.append((lvalue, object_rprimitive))


def find_attr_initializers(
    builder: IRBuilder, cdef: ClassDef, skip: Callable[[str, AssignmentStmt], bool] | None = None
) -> tuple[set[str], list[AssignmentStmt]]:
    """Find initializers of attributes in a class body.

    If provided, the skip arg should be a callable which will return whether
    to skip generating a default for an attribute.  It will be passed the name of
    the attribute and the corresponding AssignmentStmt.
    """
    cls = builder.mapper.type_to_ir[cdef.info]
    if cls.builtin_base:
        return set(), []

    attrs_with_defaults = set()

    # Pull out all assignments in classes in the mro so we can initialize them
    # TODO: Support nested statements
    default_assignments = []
    for info in reversed(cdef.info.mro):
        if info not in builder.mapper.type_to_ir:
            continue
        for stmt in info.defn.defs.body:
            if (
                isinstance(stmt, AssignmentStmt)
                and isinstance(stmt.lvalues[0], NameExpr)
                and not is_class_var(stmt.lvalues[0])
                and not isinstance(stmt.rvalue, TempNode)
            ):
                name = stmt.lvalues[0].name
                if name == "__slots__":
                    continue

                if name == "__deletable__":
                    check_deletable_declaration(builder, cls, stmt.line)
                    continue

                if skip is not None and skip(name, stmt):
                    continue

                attr_type = cls.attr_type(name)

                # If the attribute is initialized to None and type isn't optional,
                # doesn't initialize it to anything (special case for "# type:" comments).
                if isinstance(stmt.rvalue, RefExpr) and stmt.rvalue.fullname == "builtins.None":
                    if (
                        not is_optional_type(attr_type)
                        and not is_object_rprimitive(attr_type)
                        and not is_none_rprimitive(attr_type)
                    ):
                        continue

                attrs_with_defaults.add(name)
                default_assignments.append(stmt)

    return attrs_with_defaults, default_assignments


def generate_attr_defaults_init(
    builder: IRBuilder, cdef: ClassDef, default_assignments: list[AssignmentStmt]
) -> None:
    """Generate an initialization method for default attr values (from class vars)."""
    if not default_assignments:
        return
    cls = builder.mapper.type_to_ir[cdef.info]
    if cls.builtin_base:
        return

    with builder.enter_method(cls, "__mypyc_defaults_setup", bool_rprimitive):
        self_var = builder.self()
        for stmt in default_assignments:
            lvalue = stmt.lvalues[0]
            assert isinstance(lvalue, NameExpr), lvalue
            if not stmt.is_final_def and not is_constant(stmt.rvalue):
                builder.warning("Unsupported default attribute value", stmt.rvalue.line)

            attr_type = cls.attr_type(lvalue.name)
            val = builder.coerce(builder.accept(stmt.rvalue), attr_type, stmt.line)
            init = SetAttr(self_var, lvalue.name, val, -1)
            init.mark_as_initializer()
            builder.add(init)

        builder.add(Return(builder.true()))


def check_deletable_declaration(builder: IRBuilder, cl: ClassIR, line: int) -> None:
    for attr in cl.deletable:
        if attr not in cl.attributes:
            if not cl.has_attr(attr):
                builder.error(f'Attribute "{attr}" not defined', line)
                continue
            for base in cl.mro:
                if attr in base.property_types:
                    builder.error(f'Cannot make property "{attr}" deletable', line)
                    break
            else:
                _, base = cl.attr_details(attr)
                builder.error(
                    ('Attribute "{}" not defined in "{}" ' + '(defined in "{}")').format(
                        attr, cl.name, base.name
                    ),
                    line,
                )


def create_ne_from_eq(builder: IRBuilder, cdef: ClassDef) -> None:
    """Create a "__ne__" method from a "__eq__" method (if only latter exists)."""
    cls = builder.mapper.type_to_ir[cdef.info]
    if cls.has_method("__eq__") and not cls.has_method("__ne__"):
        gen_glue_ne_method(builder, cls, cdef.line)


def gen_glue_ne_method(builder: IRBuilder, cls: ClassIR, line: int) -> None:
    """Generate a "__ne__" method from a "__eq__" method."""
    func_ir = cls.get_method("__eq__")
    assert func_ir
    eq_sig = func_ir.decl.sig
    strict_typing = builder.options.strict_dunders_typing
    with builder.enter_method(cls, "__ne__", eq_sig.ret_type):
        rhs_type = eq_sig.args[0].type if strict_typing else object_rprimitive
        rhs_arg = builder.add_argument("rhs", rhs_type)
        eqval = builder.add(MethodCall(builder.self(), "__eq__", [rhs_arg], line))

        can_return_not_implemented = is_subtype(not_implemented_op.type, eq_sig.ret_type)
        return_bool = is_subtype(eq_sig.ret_type, bool_rprimitive)

        if not strict_typing or can_return_not_implemented:
            # If __eq__ returns NotImplemented, then __ne__ should also
            not_implemented_block, regular_block = BasicBlock(), BasicBlock()
            not_implemented = builder.add(
                LoadAddress(not_implemented_op.type, not_implemented_op.src, line)
            )
            builder.add(
                Branch(
                    builder.translate_is_op(eqval, not_implemented, "is", line),
                    not_implemented_block,
                    regular_block,
                    Branch.BOOL,
                )
            )
            builder.activate_block(regular_block)
            rettype = bool_rprimitive if return_bool and strict_typing else object_rprimitive
            retval = builder.coerce(builder.unary_op(eqval, "not", line), rettype, line)
            builder.add(Return(retval))
            builder.activate_block(not_implemented_block)
            builder.add(Return(not_implemented))
        else:
            rettype = bool_rprimitive if return_bool and strict_typing else object_rprimitive
            retval = builder.coerce(builder.unary_op(eqval, "not", line), rettype, line)
            builder.add(Return(retval))


def load_non_ext_class(
    builder: IRBuilder, ir: ClassIR, non_ext: NonExtClassInfo, line: int
) -> Value:
    cls_name = builder.load_str(ir.name)

    add_dunders_to_non_ext_dict(builder, non_ext, line)

    class_type_obj = builder.py_call(
        non_ext.metaclass, [cls_name, non_ext.bases, non_ext.dict], line
    )
    return class_type_obj


def load_decorated_class(builder: IRBuilder, cdef: ClassDef, type_obj: Value) -> Value:
    """Apply class decorators to create a decorated (non-extension) class object.

    Given a decorated ClassDef and a register containing a
    non-extension representation of the ClassDef created via the type
    constructor, applies the corresponding decorator functions on that
    decorated ClassDef and returns a register containing the decorated
    ClassDef.
    """
    decorators = cdef.decorators
    dec_class = type_obj
    for d in reversed(decorators):
        decorator = d.accept(builder.visitor)
        assert isinstance(decorator, Value), decorator
        dec_class = builder.py_call(decorator, [dec_class], dec_class.line)
    return dec_class


def cache_class_attrs(
    builder: IRBuilder, attrs_to_cache: list[tuple[Lvalue, RType]], cdef: ClassDef
) -> None:
    """Add class attributes to be cached to the global cache."""
    typ = builder.load_native_type_object(cdef.info.fullname)
    for lval, rtype in attrs_to_cache:
        assert isinstance(lval, NameExpr), lval
        rval = builder.py_get_attr(typ, lval.name, cdef.line)
        builder.init_final_static(lval, rval, cdef.name, type_override=rtype)


def create_mypyc_attrs_tuple(builder: IRBuilder, ir: ClassIR, line: int) -> Value:
    attrs = [name for ancestor in ir.mro for name in ancestor.attributes]
    if ir.inherits_python:
        attrs.append("__dict__")
    items = [builder.load_str(attr) for attr in attrs]
    return builder.new_tuple(items, line)


def add_dunders_to_non_ext_dict(
    builder: IRBuilder, non_ext: NonExtClassInfo, line: int, add_annotations: bool = True
) -> None:
    if add_annotations:
        # Add __annotations__ to the class dict.
        builder.add_to_non_ext_dict(non_ext, "__annotations__", non_ext.anns, line)

    # We add a __doc__ attribute so if the non-extension class is decorated with the
    # dataclass decorator, dataclass will not try to look for __text_signature__.
    # https://github.com/python/cpython/blob/3.7/Lib/dataclasses.py#L957
    filler_doc_str = "mypyc filler docstring"
    builder.add_to_non_ext_dict(non_ext, "__doc__", builder.load_str(filler_doc_str), line)
    builder.add_to_non_ext_dict(non_ext, "__module__", builder.load_str(builder.module_name), line)
