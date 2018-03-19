"""Plugin for supporting the attrs library (http://www.attrs.org)"""
from collections import OrderedDict
from typing import Optional, Dict, List, cast, Tuple, Iterable

import mypy.plugin  # To avoid circular imports.
from mypy.exprtotype import expr_to_unanalyzed_type, TypeTranslationError
from mypy.fixup import lookup_qualified_stnode
from mypy.nodes import (
    Context, Argument, Var, ARG_OPT, ARG_POS, TypeInfo, AssignmentStmt,
    TupleExpr, ListExpr, NameExpr, CallExpr, RefExpr, FuncBase,
    is_class_var, TempNode, Decorator, MemberExpr, Expression, FuncDef, Block,
    PassStmt, SymbolTableNode, MDEF, JsonDict
)
from mypy.types import (
    Type, AnyType, TypeOfAny, CallableType, NoneTyp, TypeVarDef, TypeVarType,
    Overloaded, Instance, UnionType
)
from mypy.typevars import fill_typevars


# The names of the different functions that create classes or arguments.
attr_class_makers = {
    'attr.s',
    'attr.attrs',
    'attr.attributes',
}
attr_dataclass_makers = {
    'attr.dataclass',
}
attr_attrib_makers = {
    'attr.ib',
    'attr.attrib',
    'attr.attr',
}


class Attribute:
    """The value of an attr.ib() call."""

    def __init__(self, name: str, info: TypeInfo,
                 has_default: bool, init: bool, converter_name: Optional[str],
                 context: Context) -> None:
        self.name = name
        self.info = info
        self.has_default = has_default
        self.init = init
        self.converter_name = converter_name
        self.context = context

    def argument(self, ctx: 'mypy.plugin.ClassDefContext') -> Argument:
        """Return this attribute as an argument to __init__."""
        assert self.init
        init_type = self.info[self.name].type

        if self.converter_name:
            # When a converter is set the init_type is overriden by the first argument
            # of the converter method.
            converter = lookup_qualified_stnode(ctx.api.modules, self.converter_name, True)
            if not converter:
                # The converter may be a local variable. Check there too.
                converter = ctx.api.lookup_qualified(self.converter_name, self.info, True)

            # Get the type of the converter.
            converter_type = None
            if converter and isinstance(converter.node, TypeInfo):
                from mypy.checkmember import type_object_type  # To avoid import cycle.
                converter_type = type_object_type(converter.node, ctx.api.builtin_type)
            elif converter and converter.type:
                converter_type = converter.type

            if isinstance(converter_type, CallableType) and converter_type.arg_types:
                init_type = ctx.api.anal_type(converter_type.arg_types[0])
            elif isinstance(converter_type, Overloaded):
                types: List[Type] = []
                for item in converter_type.items():
                    # Walk the overloads looking for methods that can accept one argument.
                    num_arg_types = len(item.arg_types)
                    if not num_arg_types:
                        continue
                    if num_arg_types > 1 and any(kind == ARG_POS for kind in item.arg_kinds[1:]):
                        continue
                    types.append(item.arg_types[0])
                # Make a union of all the valid types.
                args = UnionType.make_simplified_union(types)
                init_type = ctx.api.anal_type(args)
            else:
                ctx.api.fail("Cannot determine type of converter", self.context)
                init_type = AnyType(TypeOfAny.from_error)
        elif self.converter_name == '':
            # This means we had a converter but it's not of a type we can infer.
            # Error was shown in _get_converter_name
            init_type = AnyType(TypeOfAny.from_error)

        if init_type is None:
            if ctx.api.options.disallow_untyped_defs:
                # This is a compromise.  If you don't have a type here then the
                # __init__ will be untyped. But since the __init__ is added it's
                # pointing at the decorator. So instead we also show the error in the
                # assignment, which is where you would fix the issue.
                node = self.info[self.name].node
                assert node is not None
                ctx.api.msg.need_annotation_for_var(node, self.context)

            # Convert type not set to Any.
            init_type = AnyType(TypeOfAny.unannotated)

        # Attrs removes leading underscores when creating the __init__ arguments.
        return Argument(Var(self.name.lstrip("_"), init_type), init_type,
                        None,
                        ARG_OPT if self.has_default else ARG_POS)

    def serialize(self) -> JsonDict:
        """Serialize this object so it can be saved and restored."""
        return {
            'name': self.name,
            'has_default': self.has_default,
            'init': self.init,
            'converter_name': self.converter_name,
            'context_line': self.context.line,
            'context_column': self.context.column,
        }

    @classmethod
    def deserialize(cls, info: TypeInfo, data: JsonDict) -> 'Attribute':
        """Return the Attribute that was serialized."""
        return Attribute(
            data['name'],
            info,
            data['has_default'],
            data['init'],
            data['converter_name'],
            Context(line=data['context_line'], column=data['context_column'])
        )


def attr_class_maker_callback(ctx: 'mypy.plugin.ClassDefContext',
                              auto_attribs_default: bool = False) -> None:
    """Add necessary dunder methods to classes decorated with attr.s.

    attrs is a package that lets you define classes without writing dull boilerplate code.

    At a quick glance, the decorator searches the class body for assignments of `attr.ib`s (or
    annotated variables if auto_attribs=True), then depending on how the decorator is called,
    it will add an __init__ or all the __cmp__ methods.  For frozen=True it will turn the attrs
    into properties.

    See http://www.attrs.org/en/stable/how-does-it-work.html for information on how attrs works.
    """
    info = ctx.cls.info

    init = _get_decorator_bool_argument(ctx, 'init', True)
    frozen = _get_frozen(ctx)
    cmp = _get_decorator_bool_argument(ctx, 'cmp', True)
    auto_attribs = _get_decorator_bool_argument(ctx, 'auto_attribs', auto_attribs_default)

    if ctx.api.options.python_version[0] < 3:
        if auto_attribs:
            ctx.api.fail("auto_attribs is not supported in Python 2", ctx.reason)
            return
        if not info.defn.base_type_exprs:
            # Note: This will not catch subclassing old-style classes.
            ctx.api.fail("attrs only works with new-style classes", info.defn)
            return

    attributes = _analyze_class(ctx, auto_attribs)

    # Save the attributes so that subclasses can reuse them.
    ctx.cls.info.metadata['attrs'] = {
        'attributes': [attr.serialize() for attr in attributes],
        'frozen': frozen,
    }

    adder = MethodAdder(info, ctx.api.named_type('__builtins__.function'))
    if init:
        _add_init(ctx, attributes, adder)
    if cmp:
        _add_cmp(ctx, adder)
    if frozen:
        _make_frozen(ctx, attributes)


def _get_frozen(ctx: 'mypy.plugin.ClassDefContext') -> bool:
    """Return whether this class is frozen."""
    if _get_decorator_bool_argument(ctx, 'frozen', False):
        return True
    # Subclasses of frozen classes are frozen so check that.
    for super_info in ctx.cls.info.mro[1:-1]:
        if 'attrs' in super_info.metadata and super_info.metadata['attrs']['frozen']:
            return True
    return False


def _analyze_class(ctx: 'mypy.plugin.ClassDefContext', auto_attribs: bool) -> List[Attribute]:
    """Analyze the class body of an attr maker, its parents, and return the Attributes found."""
    own_attrs = OrderedDict()  # type: OrderedDict[str, Attribute]
    # Walk the body looking for assignments and decorators.
    for stmt in ctx.cls.defs.body:
        if isinstance(stmt, AssignmentStmt):
            for attr in _attributes_from_assignment(ctx, stmt, auto_attribs):
                # When attrs are defined twice in the same body we want to use the 2nd definition
                # in the 2nd location. So remove it from the OrderedDict.
                # Unless it's auto_attribs in which case we want the 2nd definition in the
                # 1st location.
                if not auto_attribs and attr.name in own_attrs:
                    del own_attrs[attr.name]
                own_attrs[attr.name] = attr
        elif isinstance(stmt, Decorator):
            _cleanup_decorator(stmt, own_attrs)

    for attribute in own_attrs.values():
        # Even though these look like class level assignments we want them to look like
        # instance level assignments.
        if attribute.name in ctx.cls.info.names:
            node = ctx.cls.info.names[attribute.name].node
            assert isinstance(node, Var)
            node.is_initialized_in_class = False

    # Traverse the MRO and collect attributes from the parents.
    taken_attr_names = set(own_attrs)
    super_attrs = []
    for super_info in ctx.cls.info.mro[1:-1]:
        if 'attrs' in super_info.metadata:
            for data in super_info.metadata['attrs']['attributes']:
                # Only add an attribute if it hasn't been defined before.  This
                # allows for overwriting attribute definitions by subclassing.
                if data['name'] not in taken_attr_names:
                    a = Attribute.deserialize(super_info, data)
                    super_attrs.append(a)
                    taken_attr_names.add(a.name)
    attributes = super_attrs + list(own_attrs.values())

    # Check the init args for correct default-ness.  Note: This has to be done after all the
    # attributes for all classes have been read, because subclasses can override parents.
    last_default = False
    for attribute in attributes:
        if attribute.init and not attribute.has_default and last_default:
            ctx.api.fail(
                "Non-default attributes not allowed after default attributes.",
                attribute.context)
        last_default = attribute.has_default

    return attributes


def _attributes_from_assignment(ctx: 'mypy.plugin.ClassDefContext',
                                stmt: AssignmentStmt, auto_attribs: bool) -> Iterable[Attribute]:
    """Return Attribute objects that are created by this assignment.

    The assignments can look like this:
        x = attr.ib()
        x = y = attr.ib()
        x, y = attr.ib(), attr.ib()
    or if auto_attribs is enabled also like this:
        x: type
        x: type = default_value
    """
    for lvalue in stmt.lvalues:
        lvalues, rvalues = _parse_assignments(lvalue, stmt)

        if len(lvalues) != len(rvalues):
            # This means we have some assignment that isn't 1 to 1.
            # It can't be an attrib.
            continue

        for lhs, rvalue in zip(lvalues, rvalues):
            # Check if the right hand side is a call to an attribute maker.
            if (isinstance(rvalue, CallExpr)
                    and isinstance(rvalue.callee, RefExpr)
                    and rvalue.callee.fullname in attr_attrib_makers):
                attr = _attribute_from_attrib_maker(ctx, auto_attribs, lhs, rvalue, stmt)
                if attr:
                    yield attr
            elif auto_attribs and stmt.type and stmt.new_syntax and not is_class_var(lhs):
                yield _attribute_from_auto_attrib(ctx, lhs, rvalue, stmt)


def _cleanup_decorator(stmt: Decorator, attr_map: Dict[str, Attribute]) -> None:
    """Handle decorators in class bodies.

    `x.default` will set a default value on x
    `x.validator` and `x.default` will get removed to avoid throwing a type error.
    """
    remove_me = []
    for func_decorator in stmt.decorators:
        if (isinstance(func_decorator, MemberExpr)
                and isinstance(func_decorator.expr, NameExpr)
                and func_decorator.expr.name in attr_map):

            if func_decorator.name == 'default':
                attr_map[func_decorator.expr.name].has_default = True

            if func_decorator.name in ('default', 'validator'):
                # These are decorators on the attrib object that only exist during
                # class creation time.  In order to not trigger a type error later we
                # just remove them.  This might leave us with a Decorator with no
                # decorators (Emperor's new clothes?)
                # TODO: It would be nice to type-check these rather than remove them.
                #       default should be Callable[[], T]
                #       validator should be Callable[[Any, 'Attribute', T], Any]
                #       where T is the type of the attribute.
                remove_me.append(func_decorator)
    for dec in remove_me:
        stmt.decorators.remove(dec)


def _attribute_from_auto_attrib(ctx: 'mypy.plugin.ClassDefContext',
                                lhs: NameExpr,
                                rvalue: Expression,
                                stmt: AssignmentStmt) -> Attribute:
    """Return an Attribute for a new type assignment."""
    # `x: int` (without equal sign) assigns rvalue to TempNode(AnyType())
    has_rhs = not isinstance(rvalue, TempNode)
    return Attribute(lhs.name, ctx.cls.info, has_rhs, True, None, stmt)


def _attribute_from_attrib_maker(ctx: 'mypy.plugin.ClassDefContext',
                                 auto_attribs: bool,
                                 lhs: NameExpr,
                                 rvalue: CallExpr,
                                 stmt: AssignmentStmt) -> Optional[Attribute]:
    """Return an Attribute from the assignment or None if you can't make one."""
    if auto_attribs and not stmt.new_syntax:
        # auto_attribs requires an annotation on *every* attr.ib.
        assert lhs.node is not None
        ctx.api.msg.need_annotation_for_var(lhs.node, stmt)
        return None

    if len(stmt.lvalues) > 1:
        ctx.api.fail("Too many names for one attribute", stmt)
        return None

    # This is the type that belongs in the __init__ method for this attrib.
    init_type = stmt.type

    # Read all the arguments from the call.
    init = _get_bool_argument(ctx, rvalue, 'init', True)
    # TODO: Check for attr.NOTHING
    attr_has_default = bool(_get_argument(rvalue, 'default'))

    # If the type isn't set through annotation but is passed through `type=` use that.
    type_arg = _get_argument(rvalue, 'type')
    if type_arg and not init_type:
        try:
            un_type = expr_to_unanalyzed_type(type_arg)
        except TypeTranslationError:
            ctx.api.fail('Invalid argument to type', type_arg)
        else:
            init_type = ctx.api.anal_type(un_type)
            if init_type and isinstance(lhs.node, Var) and not lhs.node.type:
                # If there is no annotation, add one.
                lhs.node.type = init_type
                lhs.is_inferred_def = False

    # Note: convert is deprecated but works the same as converter.
    converter = _get_argument(rvalue, 'converter')
    convert = _get_argument(rvalue, 'convert')
    if convert and converter:
        ctx.api.fail("Can't pass both `convert` and `converter`.", rvalue)
    elif convert:
        ctx.api.fail("convert is deprecated, use converter", rvalue)
        converter = convert
    converter_name = _get_converter_name(ctx, converter)

    return Attribute(lhs.name, ctx.cls.info, attr_has_default, init, converter_name, stmt)


def _get_converter_name(ctx: 'mypy.plugin.ClassDefContext',
                        converter: Optional[Expression]) -> Optional[str]:
    """Return the full name of the converter if it exists and is a simple function."""
    # TODO: Support complex converters, e.g. lambdas, calls, etc.
    if converter:
        if isinstance(converter, RefExpr) and converter.node:
            if (isinstance(converter.node, FuncBase)
                    and converter.node.type
                    and isinstance(converter.node.type, CallableType)
                    and converter.node.type.arg_types):
                return converter.node.fullname()
            elif isinstance(converter.node, TypeInfo):
                return converter.node.fullname()

        # Signal that we have an unsupported converter.
        ctx.api.fail(
            "Unsupported converter, only named functions and types are currently supported",
            converter
        )
        return ''
    return None


def _parse_assignments(
        lvalue: Expression,
        stmt: AssignmentStmt) -> Tuple[List[NameExpr], List[Expression]]:
    """Convert a possibly complex assignment expression into lists of lvalues and rvalues."""
    lvalues = []  # type: List[NameExpr]
    rvalues = []  # type: List[Expression]
    if isinstance(lvalue, (TupleExpr, ListExpr)):
        if all(isinstance(item, NameExpr) for item in lvalue.items):
            lvalues = cast(List[NameExpr], lvalue.items)
        if isinstance(stmt.rvalue, (TupleExpr, ListExpr)):
            rvalues = stmt.rvalue.items
    elif isinstance(lvalue, NameExpr):
        lvalues = [lvalue]
        rvalues = [stmt.rvalue]
    return lvalues, rvalues


def _add_cmp(ctx: 'mypy.plugin.ClassDefContext', adder: 'MethodAdder') -> None:
    """Generate all the cmp methods for this class."""
    # For __ne__ and __eq__ the type is:
    #     def __ne__(self, other: object) -> bool
    bool_type = ctx.api.named_type('__builtins__.bool')
    object_type = ctx.api.named_type('__builtins__.object')
    args = [Argument(Var('other', object_type), object_type, None, ARG_POS)]
    for method in ['__ne__', '__eq__']:
        adder.add_method(method, args, bool_type)
    # For the rest we use:
    #    AT = TypeVar('AT')
    #    def __lt__(self: AT, other: AT) -> bool
    # This way comparisons with subclasses will work correctly.
    tvd = TypeVarDef('AT', 'AT', 1, [], object_type)
    tvd_type = TypeVarType(tvd)
    args = [Argument(Var('other', tvd_type), tvd_type, None, ARG_POS)]
    for method in ['__lt__', '__le__', '__gt__', '__ge__']:
        adder.add_method(method, args, bool_type, self_type=tvd_type, tvd=tvd)


def _make_frozen(ctx: 'mypy.plugin.ClassDefContext', attributes: List[Attribute]) -> None:
    """Turn all the attributes into properties to simulate frozen classes."""
    for attribute in attributes:
        if attribute.name in ctx.cls.info.names:
            # This variable belongs to this class so we can modify it.
            node = ctx.cls.info.names[attribute.name].node
            assert isinstance(node, Var)
            node.is_property = True
        else:
            # This variable belongs to a super class so create new Var so we
            # can modify it.
            var = Var(attribute.name, ctx.cls.info[attribute.name].type)
            var.info = ctx.cls.info
            var._fullname = '%s.%s' % (ctx.cls.info.fullname(), var.name())
            ctx.cls.info.names[var.name()] = SymbolTableNode(MDEF, var)
            var.is_property = True


def _add_init(ctx: 'mypy.plugin.ClassDefContext', attributes: List[Attribute],
              adder: 'MethodAdder') -> None:
    """Generate an __init__ method for the attributes and add it to the class."""
    adder.add_method(
        '__init__',
        [attribute.argument(ctx) for attribute in attributes if attribute.init],
        NoneTyp()
    )
    for stmt in ctx.cls.defs.body:
        # The type of classmethods will be wrong because it's based on the parent's __init__.
        # Set it correctly.
        if isinstance(stmt, Decorator) and stmt.func.is_class:
            func_type = stmt.func.type
            if isinstance(func_type, CallableType):
                func_type.arg_types[0] = ctx.api.class_type(ctx.cls.info)


def _get_decorator_bool_argument(
        ctx: 'mypy.plugin.ClassDefContext',
        name: str,
        default: bool) -> bool:
    """Return the bool argument for the decorator.

    This handles both @attr.s(...) and @attr.s
    """
    if isinstance(ctx.reason, CallExpr):
        return _get_bool_argument(ctx, ctx.reason, name, default)
    else:
        return default


def _get_bool_argument(ctx: 'mypy.plugin.ClassDefContext', expr: CallExpr,
                       name: str, default: bool) -> bool:
    """Return the boolean value for an argument to a call or the default if it's not found."""
    attr_value = _get_argument(expr, name)
    if attr_value:
        ret = ctx.api.parse_bool(attr_value)
        if ret is None:
            ctx.api.fail('"{}" argument must be True or False.'.format(name), expr)
            return default
        return ret
    return default


def _get_argument(call: CallExpr, name: str) -> Optional[Expression]:
    """Return the expression for the specific argument."""
    # To do this we use the CallableType of the callee to find the FormalArgument,
    # then walk the actual CallExpr looking for the appropriate argument.
    #
    # Note: I'm not hard-coding the index so that in the future we can support other
    # attrib and class makers.
    callee_type = None
    if (isinstance(call.callee, RefExpr)
            and isinstance(call.callee.node, (Var, FuncBase))
            and call.callee.node.type):
        callee_node_type = call.callee.node.type
        if isinstance(callee_node_type, Overloaded):
            # We take the last overload.
            callee_type = callee_node_type.items()[-1]
        elif isinstance(callee_node_type, CallableType):
            callee_type = callee_node_type

    if not callee_type:
        return None

    argument = callee_type.argument_by_name(name)
    if not argument:
        return None
    assert argument.name

    for i, (attr_name, attr_value) in enumerate(zip(call.arg_names, call.args)):
        if argument.pos is not None and not attr_name and i == argument.pos:
            return attr_value
        if attr_name == argument.name:
            return attr_value
    return None


class MethodAdder:
    """Helper to add methods to a TypeInfo.

    info: The TypeInfo on which we will add methods.
    function_type: The type of __builtins__.function that will be used as the
                   fallback for all methods added.
    """

    # TODO: Combine this with the code build_namedtuple_typeinfo to support both.

    def __init__(self, info: TypeInfo, function_type: Instance) -> None:
        self.info = info
        self.self_type = fill_typevars(info)
        self.function_type = function_type

    def add_method(self,
                   method_name: str, args: List[Argument], ret_type: Type,
                   self_type: Optional[Type] = None,
                   tvd: Optional[TypeVarDef] = None) -> None:
        """Add a method: def <method_name>(self, <args>) -> <ret_type>): ... to info.

        self_type: The type to use for the self argument or None to use the inferred self type.
        tvd: If the method is generic these should be the type variables.
        """
        from mypy.semanal import set_callable_name
        self_type = self_type if self_type is not None else self.self_type
        args = [Argument(Var('self'), self_type, None, ARG_POS)] + args
        arg_types = [arg.type_annotation for arg in args]
        arg_names = [arg.variable.name() for arg in args]
        arg_kinds = [arg.kind for arg in args]
        assert None not in arg_types
        signature = CallableType(cast(List[Type], arg_types), arg_kinds, arg_names,
                                 ret_type, self.function_type)
        if tvd:
            signature.variables = [tvd]
        func = FuncDef(method_name, args, Block([PassStmt()]))
        func.info = self.info
        func.type = set_callable_name(signature, func)
        func._fullname = self.info.fullname() + '.' + method_name
        func.line = self.info.line
        self.info.names[method_name] = SymbolTableNode(MDEF, func)
        # Add the created methods to the body so that they can get further semantic analysis.
        # e.g. Forward Reference Resolution.
        self.info.defn.defs.body.append(func)
