"""Plugin system for extending mypy."""

from collections import OrderedDict
from abc import abstractmethod
from functools import partial
from typing import Callable, List, Tuple, Optional, NamedTuple, TypeVar, cast, Dict

from mypy import messages
from mypy.exprtotype import expr_to_unanalyzed_type, TypeTranslationError
from mypy.nodes import (
    Expression, StrExpr, IntExpr, UnaryExpr, Context, DictExpr, ClassDef,
    Argument, Var,
    FuncDef, Block, SymbolTableNode, MDEF, CallExpr, RefExpr, AssignmentStmt,
    TempNode,
    ARG_OPT, ARG_POS, NameExpr, Decorator, MemberExpr, TypeInfo, PassStmt,
    FuncBase,
    TupleExpr, ListExpr, is_class_var)
from mypy.tvar_scope import TypeVarScope
from mypy.types import (
    Type, Instance, CallableType, TypedDictType, UnionType, NoneTyp, TypeVarType,
    AnyType, TypeList, UnboundType, TypeOfAny, TypeVarDef, Overloaded
)
from mypy.messages import MessageBuilder
from mypy.options import Options
from mypy.typevars import fill_typevars


class TypeAnalyzerPluginInterface:
    """Interface for accessing semantic analyzer functionality in plugins."""

    @abstractmethod
    def fail(self, msg: str, ctx: Context) -> None:
        raise NotImplementedError

    @abstractmethod
    def named_type(self, name: str, args: List[Type]) -> Instance:
        raise NotImplementedError

    @abstractmethod
    def analyze_type(self, typ: Type) -> Type:
        raise NotImplementedError

    @abstractmethod
    def analyze_callable_args(self, arglist: TypeList) -> Optional[Tuple[List[Type],
                                                                         List[int],
                                                                         List[Optional[str]]]]:
        raise NotImplementedError


# A context for a hook that semantically analyzes an unbound type.
AnalyzeTypeContext = NamedTuple(
    'AnalyzeTypeContext', [
        ('type', UnboundType),  # Type to analyze
        ('context', Context),
        ('api', TypeAnalyzerPluginInterface)])


class CheckerPluginInterface:
    """Interface for accessing type checker functionality in plugins."""

    msg = None  # type: MessageBuilder

    @abstractmethod
    def named_generic_type(self, name: str, args: List[Type]) -> Instance:
        raise NotImplementedError


class SemanticAnalyzerPluginInterface:
    """Interface for accessing semantic analyzer functionality in plugins."""

    options = None  # type: Options

    @abstractmethod
    def named_type(self, qualified_name: str, args: Optional[List[Type]] = None) -> Instance:
        raise NotImplementedError

    @abstractmethod
    def parse_bool(self, expr: Expression) -> Optional[bool]:
        raise NotImplementedError

    @abstractmethod
    def fail(self, msg: str, ctx: Context, serious: bool = False, *,
             blocker: bool = False) -> None:
        raise NotImplementedError

    @abstractmethod
    def anal_type(self, t: Type, *,
                  tvar_scope: Optional[TypeVarScope] = None,
                  allow_tuple_literal: bool = False,
                  aliasing: bool = False,
                  third_pass: bool = False) -> Type:
        raise NotImplementedError

    @abstractmethod
    def class_type(self, info: TypeInfo) -> Type:
        raise NotImplementedError


# A context for a function hook that infers the return type of a function with
# a special signature.
#
# A no-op callback would just return the inferred return type, but a useful
# callback at least sometimes can infer a more precise type.
FunctionContext = NamedTuple(
    'FunctionContext', [
        ('arg_types', List[List[Type]]),   # List of actual caller types for each formal argument
        ('default_return_type', Type),     # Return type inferred from signature
        ('args', List[List[Expression]]),  # Actual expressions for each formal argument
        ('context', Context),
        ('api', CheckerPluginInterface)])

# A context for a method signature hook that infers a better signature for a
# method.  Note that argument types aren't available yet.  If you need them,
# you have to use a method hook instead.
MethodSigContext = NamedTuple(
    'MethodSigContext', [
        ('type', Type),                       # Base object type for method call
        ('args', List[List[Expression]]),     # Actual expressions for each formal argument
        ('default_signature', CallableType),  # Original signature of the method
        ('context', Context),
        ('api', CheckerPluginInterface)])

# A context for a method hook that infers the return type of a method with a
# special signature.
#
# This is very similar to FunctionContext (only differences are documented).
MethodContext = NamedTuple(
    'MethodContext', [
        ('type', Type),                    # Base object type for method call
        ('arg_types', List[List[Type]]),
        ('default_return_type', Type),
        ('args', List[List[Expression]]),
        ('context', Context),
        ('api', CheckerPluginInterface)])

# A context for an attribute type hook that infers the type of an attribute.
AttributeContext = NamedTuple(
    'AttributeContext', [
        ('type', Type),                # Type of object with attribute
        ('default_attr_type', Type),  # Original attribute type
        ('context', Context),
        ('api', CheckerPluginInterface)])

# A context for a class hook that modifies the class definition.
ClassDefContext = NamedTuple(
    'ClassDecoratorContext', [
        ('cls', ClassDef),       # The class definition
        ('reason', Expression),  # The expression being applied (decorator, metaclass, base class)
        ('api', SemanticAnalyzerPluginInterface)
    ])


class Plugin:
    """Base class of all type checker plugins.

    This defines a no-op plugin.  Subclasses can override some methods to
    provide some actual functionality.

    All get_ methods are treated as pure functions (you should assume that
    results might be cached).

    Look at the comments of various *Context objects for descriptions of
    various hooks.
    """

    def __init__(self, options: Options) -> None:
        self.options = options
        self.python_version = options.python_version

    def get_type_analyze_hook(self, fullname: str
                              ) -> Optional[Callable[[AnalyzeTypeContext], Type]]:
        return None

    def get_function_hook(self, fullname: str
                          ) -> Optional[Callable[[FunctionContext], Type]]:
        return None

    def get_method_signature_hook(self, fullname: str
                                  ) -> Optional[Callable[[MethodSigContext], CallableType]]:
        return None

    def get_method_hook(self, fullname: str
                        ) -> Optional[Callable[[MethodContext], Type]]:
        return None

    def get_attribute_hook(self, fullname: str
                           ) -> Optional[Callable[[AttributeContext], Type]]:
        return None

    def get_class_decorator_hook(self, fullname: str
                                 ) -> Optional[Callable[[ClassDefContext], None]]:
        return None

    def get_metaclass_hook(self, fullname: str
                           ) -> Optional[Callable[[ClassDefContext], None]]:
        return None

    def get_base_class_hook(self, fullname: str
                            ) -> Optional[Callable[[ClassDefContext], None]]:
        return None


T = TypeVar('T')


class ChainedPlugin(Plugin):
    """A plugin that represents a sequence of chained plugins.

    Each lookup method returns the hook for the first plugin that
    reports a match.

    This class should not be subclassed -- use Plugin as the base class
    for all plugins.
    """

    # TODO: Support caching of lookup results (through a LRU cache, for example).

    def __init__(self, options: Options, plugins: List[Plugin]) -> None:
        """Initialize chained plugin.

        Assume that the child plugins aren't mutated (results may be cached).
        """
        super().__init__(options)
        self._plugins = plugins

    def get_type_analyze_hook(self, fullname: str
                              ) -> Optional[Callable[[AnalyzeTypeContext], Type]]:
        return self._find_hook(lambda plugin: plugin.get_type_analyze_hook(fullname))

    def get_function_hook(self, fullname: str
                          ) -> Optional[Callable[[FunctionContext], Type]]:
        return self._find_hook(lambda plugin: plugin.get_function_hook(fullname))

    def get_method_signature_hook(self, fullname: str
                                  ) -> Optional[Callable[[MethodSigContext], CallableType]]:
        return self._find_hook(lambda plugin: plugin.get_method_signature_hook(fullname))

    def get_method_hook(self, fullname: str
                        ) -> Optional[Callable[[MethodContext], Type]]:
        return self._find_hook(lambda plugin: plugin.get_method_hook(fullname))

    def get_attribute_hook(self, fullname: str
                           ) -> Optional[Callable[[AttributeContext], Type]]:
        return self._find_hook(lambda plugin: plugin.get_attribute_hook(fullname))

    def get_class_decorator_hook(self, fullname: str
                                 ) -> Optional[Callable[[ClassDefContext], None]]:
        return self._find_hook(lambda plugin: plugin.get_class_decorator_hook(fullname))

    def get_metaclass_hook(self, fullname: str
                           ) -> Optional[Callable[[ClassDefContext], None]]:
        return self._find_hook(lambda plugin: plugin.get_metaclass_hook(fullname))

    def get_base_class_hook(self, fullname: str
                            ) -> Optional[Callable[[ClassDefContext], None]]:
        return self._find_hook(lambda plugin: plugin.get_base_class_hook(fullname))

    def _find_hook(self, lookup: Callable[[Plugin], T]) -> Optional[T]:
        for plugin in self._plugins:
            hook = lookup(plugin)
            if hook:
                return hook
        return None


class DefaultPlugin(Plugin):
    """Type checker plugin that is enabled by default."""

    def __init__(self, options: Options) -> None:
        super().__init__(options)
        self._attr_classes = {}  # type: Dict[TypeInfo, List[Attribute]]

    def get_function_hook(self, fullname: str
                          ) -> Optional[Callable[[FunctionContext], Type]]:
        if fullname == 'contextlib.contextmanager':
            return contextmanager_callback
        elif fullname == 'builtins.open' and self.python_version[0] == 3:
            return open_callback
        return None

    def get_method_signature_hook(self, fullname: str
                                  ) -> Optional[Callable[[MethodSigContext], CallableType]]:
        if fullname == 'typing.Mapping.get':
            return typed_dict_get_signature_callback
        return None

    def get_method_hook(self, fullname: str
                        ) -> Optional[Callable[[MethodContext], Type]]:
        if fullname == 'typing.Mapping.get':
            return typed_dict_get_callback
        elif fullname == 'builtins.int.__pow__':
            return int_pow_callback
        return None

    def get_class_decorator_hook(self, fullname: str
                                 ) -> Optional[Callable[[ClassDefContext], None]]:
        if fullname in attr_class_makers:
            return partial(
                attr_class_maker_callback,
                self._attr_classes
            )
        elif fullname in attr_dataclass_makers:
            return partial(
                attr_class_maker_callback,
                self._attr_classes,
                auto_attribs_default=True
            )
        return None


def open_callback(ctx: FunctionContext) -> Type:
    """Infer a better return type for 'open'.

    Infer TextIO or BinaryIO as the return value if the mode argument is not
    given or is a literal.
    """
    mode = None
    if not ctx.arg_types or len(ctx.arg_types[1]) != 1:
        mode = 'r'
    elif isinstance(ctx.args[1][0], StrExpr):
        mode = ctx.args[1][0].value
    if mode is not None:
        assert isinstance(ctx.default_return_type, Instance)
        if 'b' in mode:
            return ctx.api.named_generic_type('typing.BinaryIO', [])
        else:
            return ctx.api.named_generic_type('typing.TextIO', [])
    return ctx.default_return_type


def contextmanager_callback(ctx: FunctionContext) -> Type:
    """Infer a better return type for 'contextlib.contextmanager'."""
    # Be defensive, just in case.
    if ctx.arg_types and len(ctx.arg_types[0]) == 1:
        arg_type = ctx.arg_types[0][0]
        if (isinstance(arg_type, CallableType)
                and isinstance(ctx.default_return_type, CallableType)):
            # The stub signature doesn't preserve information about arguments so
            # add them back here.
            return ctx.default_return_type.copy_modified(
                arg_types=arg_type.arg_types,
                arg_kinds=arg_type.arg_kinds,
                arg_names=arg_type.arg_names,
                variables=arg_type.variables,
                is_ellipsis_args=arg_type.is_ellipsis_args)
    return ctx.default_return_type


def typed_dict_get_signature_callback(ctx: MethodSigContext) -> CallableType:
    """Try to infer a better signature type for TypedDict.get.

    This is used to get better type context for the second argument that
    depends on a TypedDict value type.
    """
    signature = ctx.default_signature
    if (isinstance(ctx.type, TypedDictType)
            and len(ctx.args) == 2
            and len(ctx.args[0]) == 1
            and isinstance(ctx.args[0][0], StrExpr)
            and len(signature.arg_types) == 2
            and len(signature.variables) == 1
            and len(ctx.args[1]) == 1):
        key = ctx.args[0][0].value
        value_type = ctx.type.items.get(key)
        ret_type = signature.ret_type
        if value_type:
            default_arg = ctx.args[1][0]
            if (isinstance(value_type, TypedDictType)
                    and isinstance(default_arg, DictExpr)
                    and len(default_arg.items) == 0):
                # Caller has empty dict {} as default for typed dict.
                value_type = value_type.copy_modified(required_keys=set())
            # Tweak the signature to include the value type as context. It's
            # only needed for type inference since there's a union with a type
            # variable that accepts everything.
            tv = TypeVarType(signature.variables[0])
            return signature.copy_modified(
                arg_types=[signature.arg_types[0],
                           UnionType.make_simplified_union([value_type, tv])],
                ret_type=ret_type)
    return signature


def typed_dict_get_callback(ctx: MethodContext) -> Type:
    """Infer a precise return type for TypedDict.get with literal first argument."""
    if (isinstance(ctx.type, TypedDictType)
            and len(ctx.arg_types) >= 1
            and len(ctx.arg_types[0]) == 1):
        if isinstance(ctx.args[0][0], StrExpr):
            key = ctx.args[0][0].value
            value_type = ctx.type.items.get(key)
            if value_type:
                if len(ctx.arg_types) == 1:
                    return UnionType.make_simplified_union([value_type, NoneTyp()])
                elif (len(ctx.arg_types) == 2 and len(ctx.arg_types[1]) == 1
                      and len(ctx.args[1]) == 1):
                    default_arg = ctx.args[1][0]
                    if (isinstance(default_arg, DictExpr) and len(default_arg.items) == 0
                            and isinstance(value_type, TypedDictType)):
                        # Special case '{}' as the default for a typed dict type.
                        return value_type.copy_modified(required_keys=set())
                    else:
                        return UnionType.make_simplified_union([value_type, ctx.arg_types[1][0]])
            else:
                ctx.api.msg.typeddict_key_not_found(ctx.type, key, ctx.context)
                return AnyType(TypeOfAny.from_error)
    return ctx.default_return_type


def int_pow_callback(ctx: MethodContext) -> Type:
    """Infer a more precise return type for int.__pow__."""
    if (len(ctx.arg_types) == 1
            and len(ctx.arg_types[0]) == 1):
        arg = ctx.args[0][0]
        if isinstance(arg, IntExpr):
            exponent = arg.value
        elif isinstance(arg, UnaryExpr) and arg.op == '-' and isinstance(arg.expr, IntExpr):
            exponent = -arg.expr.value
        else:
            # Right operand not an int literal or a negated literal -- give up.
            return ctx.default_return_type
        if exponent >= 0:
            return ctx.api.named_generic_type('builtins.int', [])
        else:
            return ctx.api.named_generic_type('builtins.float', [])
    return ctx.default_return_type


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

    def __init__(self, name: str, type: Optional[Type],
                 has_default: bool, init: bool,
                 context: Context) -> None:
        self.name = name
        self.type = type
        self.has_default = has_default
        self.init = init
        self.context = context

    def argument(self) -> Argument:
        """Return this attribute as an argument to __init__."""
        # Convert type not set to Any.
        _type = self.type or AnyType(TypeOfAny.unannotated)
        # Attrs removes leading underscores when creating the __init__ arguments.
        return Argument(Var(self.name.lstrip("_"), _type), _type,
                        None,
                        ARG_OPT if self.has_default else ARG_POS)


def attr_class_maker_callback(
        attr_classes: Dict[TypeInfo, List[Attribute]],
        ctx: ClassDefContext,
        auto_attribs_default: bool = False
) -> None:
    """Add necessary dunder methods to classes decorated with attr.s.

    attrs is a package that lets you define classes without writing dull boilerplate code.

    At a quick glance, the decorator searches the class body for assignments of `attr.ib`s (or
    annotated variables if auto_attribs=True), then depending on how the decorator is called,
    it will add an __init__ or all the __cmp__ methods.  For frozen=True it will turn the attrs
    into properties.

    See http://www.attrs.org/en/stable/how-does-it-work.html for information on how attrs works.
    """
    info = ctx.cls.info

    # auto_attribs means we also generate Attributes from annotated variables.
    auto_attribs = _attrs_get_decorator_bool_argument(ctx, 'auto_attribs', auto_attribs_default)

    if ctx.api.options.python_version[0] < 3:
        if auto_attribs:
            ctx.api.fail("auto_attribs is not supported in Python 2", ctx.reason)
            return
        if not info.defn.base_type_exprs:
            # Note: This does not catch subclassing old-style classes.
            ctx.api.fail("attrs only works with new-style classes", info.defn)
            return

    # First, walk the body looking for attribute definitions.
    # They will look like this:
    #     x = attr.ib()
    #     x = y = attr.ib()
    #     x, y = attr.ib(), attr.ib()
    # or if auto_attribs is enabled also like this:
    #     x: type
    #     x: type = default_value
    own_attrs = OrderedDict()  # type: OrderedDict[str, Attribute]
    for stmt in ctx.cls.defs.body:
        if isinstance(stmt, AssignmentStmt):
            for lvalue in stmt.lvalues:
                # To handle all types of assignments we just convert everything
                # to a matching lists of lefts and rights.
                lhss = []  # type: List[NameExpr]
                rvalues = []  # type: List[Expression]
                if isinstance(lvalue, (TupleExpr, ListExpr)):
                    if all(isinstance(item, NameExpr) for item in lvalue.items):
                        lhss = cast(List[NameExpr], lvalue.items)
                    if isinstance(stmt.rvalue, (TupleExpr, ListExpr)):
                        rvalues = stmt.rvalue.items
                elif isinstance(lvalue, NameExpr):
                    lhss = [lvalue]
                    rvalues = [stmt.rvalue]

                if len(lhss) != len(rvalues):
                    # This means we have some assignment that isn't 1 to 1.
                    # It can't be an attrib.
                    continue

                for lhs, rvalue in zip(lhss, rvalues):
                    typ = stmt.type
                    name = lhs.name

                    # Check if the right hand side is a call to an attribute maker.
                    if (isinstance(rvalue, CallExpr)
                            and isinstance(rvalue.callee, RefExpr)
                            and rvalue.callee.fullname in attr_attrib_makers):
                        if auto_attribs and not stmt.new_syntax:
                            # auto_attribs requires annotation on every attr.ib.
                            ctx.api.fail(messages.NEED_ANNOTATION_FOR_VAR, stmt)
                            continue

                        if len(stmt.lvalues) > 1:
                            ctx.api.fail("Too many names for one attribute", stmt)
                            continue

                        # Look for default=<something> in the call.
                        # TODO: Check for attr.NOTHING
                        attr_has_default = bool(_attrs_get_argument(rvalue, 'default'))

                        # If the type isn't set through annotation but it is passed through type=
                        # use that.
                        type_arg = _attrs_get_argument(rvalue, 'type')
                        if type_arg and not typ:
                            try:
                                un_type = expr_to_unanalyzed_type(type_arg)
                            except TypeTranslationError:
                                ctx.api.fail('Invalid argument to type', type_arg)
                            else:
                                typ = ctx.api.anal_type(un_type)
                                if typ and isinstance(lhs.node, Var) and not lhs.node.type:
                                    # If there is no annotation, add one.
                                    lhs.node.type = typ
                                    lhs.is_inferred_def = False

                        # If the attrib has a converter function take the type of the first
                        # argument as the init type.
                        # Note: convert is deprecated but works the same as converter.
                        converter = _attrs_get_argument(rvalue, 'converter')
                        convert = _attrs_get_argument(rvalue, 'convert')
                        if convert and converter:
                            ctx.api.fail("Can't pass both `convert` and `converter`.", rvalue)
                        elif convert:
                            converter = convert
                        if (converter
                                and isinstance(converter, RefExpr)
                                and converter.node
                                and isinstance(converter.node, FuncBase)
                                and converter.node.type
                                and isinstance(converter.node.type, CallableType)
                                and converter.node.type.arg_types):
                            typ = converter.node.type.arg_types[0]

                        # Does this even have to go in init.
                        init = _attrs_get_bool_argument(ctx, rvalue, 'init', True)

                        # When attrs are defined twice in the same body we want to use
                        # the 2nd definition in the 2nd location. So remove it from the
                        # OrderedDict.  auto_attribs doesn't work that way.
                        if not auto_attribs and name in own_attrs:
                            del own_attrs[name]
                        own_attrs[name] = Attribute(name, typ, attr_has_default, init, stmt)
                    elif auto_attribs and typ and stmt.new_syntax and not is_class_var(lhs):
                        # `x: int` (without equal sign) assigns rvalue to TempNode(AnyType())
                        has_rhs = not isinstance(rvalue, TempNode)
                        own_attrs[name] = Attribute(name, typ, has_rhs, True, stmt)

        elif isinstance(stmt, Decorator):
            # Look for attr specific decorators.  ('x.default' and 'x.validator')
            remove_me = []
            for func_decorator in stmt.decorators:
                if (isinstance(func_decorator, MemberExpr)
                        and isinstance(func_decorator.expr, NameExpr)
                        and func_decorator.expr.name in own_attrs):

                    if func_decorator.name == 'default':
                        # This decorator lets you set a default after the fact.
                        own_attrs[func_decorator.expr.name].has_default = True

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

    taken_attr_names = set(own_attrs)
    super_attrs = []

    # Traverse the MRO and collect attributes from the parents.
    for super_info in info.mro[1:-1]:
        if super_info in attr_classes:
            for a in attr_classes[super_info]:
                # Only add an attribute if it hasn't been defined before.  This
                # allows for overwriting attribute definitions by subclassing.
                if a.name not in taken_attr_names:
                    super_attrs.append(a)
                    taken_attr_names.add(a.name)

    attributes = super_attrs + list(own_attrs.values())
    # Save the attributes so that subclasses can reuse them.
    # TODO: This doesn't work with incremental mode if the parent class is in a different file.
    attr_classes[info] = attributes

    if ctx.api.options.disallow_untyped_defs:
        for attribute in attributes:
            if attribute.type is None:
                # This is a compromise.  If you don't have a type here then the __init__ will
                # be untyped. But since the __init__ is added it's pointing at the decorator.
                # So instead we just show the error in the assignment, which is where you
                # would fix the issue.
                ctx.api.fail(messages.NEED_ANNOTATION_FOR_VAR, attribute.context)

    # Check the init args for correct default-ness.  Note: This has to be done after all the
    # attributes for all classes have been read, because subclasses can override parents.
    last_default = False
    for attribute in attributes:
        if not attribute.has_default and last_default:
            ctx.api.fail(
                "Non-default attributes not allowed after default attributes.",
                attribute.context)
        last_default = attribute.has_default

    adder = MethodAdder(info, ctx.api.named_type('__builtins__.function'))

    if _attrs_get_decorator_bool_argument(ctx, 'init', True):
        # Generate the __init__ method.
        adder.add_method(
            '__init__',
            [attribute.argument() for attribute in attributes if attribute.init],
            NoneTyp()
        )

        for stmt in ctx.cls.defs.body:
            # The type of classmethods will be wrong because it's based on the parent's __init__.
            # Set it correctly.
            if isinstance(stmt, Decorator) and stmt.func.is_class:
                func_type = stmt.func.type
                if isinstance(func_type, CallableType):
                    func_type.arg_types[0] = ctx.api.class_type(info)

    if _attrs_get_decorator_bool_argument(ctx, 'frozen', False):
        # If the class is frozen then all the attributes need to be turned into properties.
        for attribute in attributes:
            node = info.names[attribute.name].node
            assert isinstance(node, Var)
            node.is_initialized_in_class = False
            node.is_property = True

    if _attrs_get_decorator_bool_argument(ctx, 'cmp', True):
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
            adder.add_method(method, args, bool_type,
                             self_type=tvd_type, tvd=tvd)


def _attrs_get_decorator_bool_argument(ctx: ClassDefContext, name: str, default: bool) -> bool:
    """Return the bool argument for the decorator.

    This handles both @attr.s(...) and @attr.s
    """
    if isinstance(ctx.reason, CallExpr):
        return _attrs_get_bool_argument(ctx, ctx.reason, name, default)
    else:
        return default


def _attrs_get_bool_argument(ctx: ClassDefContext, expr: CallExpr,
                             name: str, default: bool) -> bool:
    """Return the boolean value for an argument to a call or the default if it's not found."""
    attr_value = _attrs_get_argument(expr, name)
    if attr_value:
        ret = ctx.api.parse_bool(attr_value)
        if ret is None:
            ctx.api.fail('"{}" argument must be True or False.'.format(name), expr)
            return default
        return ret
    return default


def _attrs_get_argument(call: CallExpr, name: str) -> Optional[Expression]:
    """Return the expression for the specific argument."""
    # To do this we find the CallableType of the callee and to find the FormalArgument.
    # Note: I'm not hard-coding the index so that in the future we can support other
    # attrib and class makers.
    callee_type = None
    if (isinstance(call.callee, RefExpr)
            and isinstance(call.callee.node, Var)
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

    # Now walk the actual call to pick off the correct argument.
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
