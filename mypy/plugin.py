"""Plugin system for extending mypy."""

from collections import OrderedDict
from abc import abstractmethod
from functools import partial
from typing import Callable, List, Tuple, Optional, NamedTuple, TypeVar, cast, Any

from mypy import messages
from mypy.exprtotype import expr_to_unanalyzed_type, TypeTranslationError
from mypy.nodes import (
    Expression, StrExpr, IntExpr, UnaryExpr, Context, DictExpr, ClassDef, Argument, Var,
    FuncDef, Block, SymbolTableNode, MDEF, CallExpr, RefExpr, AssignmentStmt, TempNode, ARG_POS,
    ARG_OPT, EllipsisExpr, NameExpr, Node, Decorator, MemberExpr)
from mypy.tvar_scope import TypeVarScope
from mypy.types import (
    Type, Instance, CallableType, TypedDictType, UnionType, NoneTyp, TypeVarType,
    AnyType, TypeList, UnboundType, TypeOfAny
)
from mypy.messages import MessageBuilder
from mypy.options import Options


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
    def accept(self, node: Node) -> None:
        raise NotImplementedError

    @abstractmethod
    def anal_type(self, t: Type, *,
                  tvar_scope: Optional[TypeVarScope] = None,
                  allow_tuple_literal: bool = False,
                  aliasing: bool = False,
                  third_pass: bool = False) -> Type:
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
            return partial(attr_class_maker_callback, attr_class_makers[fullname])
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


# Arguments to the attr functions (attr.s and attr.ib) with their defaults in their correct order.
# These are needed to find the actual value from the CallExpr.
attrs_arguments = OrderedDict([
    ('maybe_cls', None), ('these', None), ('repr_ns', None), ('repr', True), ('cmp', True),
    ('hash', None), ('init', True), ('slots', False), ('frozen', False), ('str', False),
    ('auto_attribs', False)
])
attrib_arguments = OrderedDict([
    ('default', None), ('validator', None), ('repr', True), ('cmp', True), ('hash', None),
    ('init', True), ('convert', None), ('metadata', {}), ('type', None)
])

# The names of the different functions that create classes or arguments.
# The right hand side is an OrderedDict of the arguments to the call.
attr_class_makers = {
    'attr.s': attrs_arguments,
    'attr.attrs': attrs_arguments,
    'attr.attributes': attrs_arguments,
    'attr.dataclass': OrderedDict(attrs_arguments, auto_attribs=True),
}
attr_attrib_makers = {
    'attr.ib': attrib_arguments,
    'attr.attrib': attrib_arguments,
    'attr.attr': attrib_arguments,
}


def attr_class_maker_callback(attrs_arguments: 'OrderedDict[str, Any]',
                              ctx: ClassDefContext) -> None:
    """Add necessary dunder methods to classes decorated with attr.s.

    Currently supports init=True, cmp=True and frozen=True.
    """
    # attrs is a package that lets you define classes without writing dull boilerplate code.
    #
    # At a quick glance, the decorator searches the class body for assignments of `attr.ib`s (or
    # annotated variables if auto_attribs=True), then depending on how the decorator is called,
    # it will add an __init__ or all the __cmp__ methods.  For frozen=True it will turn the attrs
    # into properties.
    #
    # See http://www.attrs.org/en/stable/how-does-it-work.html for information on how attrs works.

    def called_function(expr: Expression) -> Optional[str]:
        """Return the full name of the function being called by the expr, or None."""
        if isinstance(expr, CallExpr) and isinstance(expr.callee, RefExpr):
            return expr.callee.fullname
        return None

    def get_argument(call: CallExpr, arg_name: str,
                     func_args: 'OrderedDict[str, Any]') -> Optional[Expression]:
        """Return the expression for the specific argument."""
        arg_num = list(func_args).index(arg_name)
        assert arg_num >= 0, "Function doesn't have arg {}".format(arg_name)
        for i, (attr_name, attr_value) in enumerate(zip(call.arg_names, call.args)):
            if not attr_name and i == arg_num:
                return attr_value
            if attr_name == arg_name:
                return attr_value
        return None

    def get_bool_argument(expr: Expression, arg_name: str,
                          func_args: 'OrderedDict[str, Any]') -> bool:
        """Return the value of an argument name in the give Expression.

        If it's a CallExpr and the argument is one of the args then return it.
        Otherwise return the default value for the argument.
        """
        default = func_args[arg_name]
        assert isinstance(default, bool), "Default value for {} isn't boolean".format(arg_name)

        if isinstance(expr, CallExpr):
            attr_value = get_argument(expr, arg_name, func_args)
            if attr_value:
                ret = ctx.api.parse_bool(attr_value)
                if ret is None:
                    ctx.api.fail('"{}" argument must be True or False.'.format(arg_name), expr)
                    return default
                return ret
        return default

    def is_class_var(expr: NameExpr) -> bool:
        """Return whether the expression is ClassVar[...]"""
        if isinstance(expr.node, Var):
            return expr.node.is_classvar
        return False

    decorator = ctx.reason

    # Walk the class body (including the MRO) looking for the attributes.

    class Attribute:
        """An attribute that belongs to this class."""

        def __init__(self, name: str, type: Type,
                     has_default: bool, init: bool, context: Context) -> None:
            # I really wanted to use attrs for this.  :)
            self.name = name
            self.type = type
            self.has_default = has_default
            self.init = init
            self.context = context

        def argument(self) -> Argument:
            """Return this attribute as an argument to __init__."""
            # Attrs removes leading underscores when creating the __init__ arguments.
            return Argument(Var(self.name.strip("_"), self.type), self.type,
                            EllipsisExpr() if self.has_default else None,
                            ARG_OPT if self.has_default else ARG_POS)

    attributes = OrderedDict()  # type: OrderedDict[str, Attribute]

    def add_attribute(attr_name: str, attr_type: Optional[Type], default: bool, init: bool,
                      context: Context) -> None:
        if not attr_type:
            if ctx.api.options.disallow_untyped_defs:
                # This is a compromise.  If you don't have a type here then the __init__ will
                # be untyped. But since the __init__ method doesn't have a line number it's
                # difficult to point to the correct line number.  So instead we just show the
                # error in the assignment, which is where you would fix the issue.
                ctx.api.fail(messages.NEED_ANNOTATION_FOR_VAR, context)
            attr_type = AnyType(TypeOfAny.unannotated)

        if attr_name in attributes:
            # When a subclass overrides an attrib it gets pushed to the end.
            del attributes[attr_name]
        attributes[attr_name] = Attribute(attr_name, attr_type, default, init, context)

    # auto_attribs means we generate attributes from annotated variables.
    auto_attribs = get_bool_argument(decorator, "auto_attribs", attrs_arguments)

    # Walk the mro in reverse looking for those yummy attributes.
    for info in reversed(ctx.cls.info.mro):
        for stmt in info.defn.defs.body:
            if isinstance(stmt, AssignmentStmt) and isinstance(stmt.lvalues[0], NameExpr):
                lhs = stmt.lvalues[0]
                name = lhs.name
                typ = stmt.type

                func_name = called_function(stmt.rvalue)

                if func_name in attr_attrib_makers:
                    assert isinstance(stmt.rvalue, CallExpr)
                    func_arguments = attr_attrib_makers[func_name]

                    # Look for default=<something> in the call.  Note: This fails if someone
                    # passes the _NOTHING sentinel object into attrs.
                    attr_has_default = bool(get_argument(stmt.rvalue, "default",
                                                         func_arguments))

                    # If the type isn't set through annotation but it is passed through type=
                    # use that.
                    type_arg = get_argument(stmt.rvalue, "type", func_arguments)
                    if type_arg and not typ:
                        try:
                            un_type = expr_to_unanalyzed_type(type_arg)
                        except TypeTranslationError:
                            ctx.api.fail('Invalid argument to type', type_arg)
                        else:
                            typ = ctx.api.anal_type(un_type)

                    add_attribute(name, typ, attr_has_default,
                                  get_bool_argument(stmt.rvalue, "init", func_arguments),
                                  stmt)
                else:
                    if auto_attribs and typ and stmt.new_syntax and not is_class_var(lhs):
                        # `x: int` (without equal sign) assigns rvalue to TempNode(AnyType())
                        has_rhs = not isinstance(stmt.rvalue, TempNode)
                        add_attribute(name, typ, has_rhs, True, stmt)
            elif isinstance(stmt, Decorator):
                # Look for attr specific decorators.  ('x.default' and 'x.validator')
                remove_me = []
                for func_decorator in stmt.decorators:
                    if (isinstance(func_decorator, MemberExpr)
                            and isinstance(func_decorator.expr, NameExpr)
                            and func_decorator.expr.name in attributes):
                        if func_decorator.name == 'default':
                            # This decorator lets you set a default after the fact.
                            attributes[func_decorator.expr.name].has_default = True

                        if func_decorator.name in ('default', 'validator'):
                            # These are decorators on the attrib object that only exist during
                            # class creation time.  In order to not trigger a type error later we
                            # just remove them.  This might leave us with a Decorator with no
                            # decorators (Emperor's new clothes?)
                            remove_me.append(func_decorator)

                for dec in remove_me:
                    stmt.decorators.remove(dec)

    function_type = ctx.api.named_type('__builtins__.function')

    def add_method(method_name: str, args: List[Argument], ret_type: Type) -> None:
        """Create a method: def <method_name>(self, <args>) -> <ret_type>): ..."""
        args = [Argument(Var('self'), AnyType(TypeOfAny.unannotated), None, ARG_POS)] + args
        arg_types = [arg.type_annotation for arg in args]
        arg_names = [arg.variable.name() for arg in args]
        arg_kinds = [arg.kind for arg in args]
        assert None not in arg_types
        signature = CallableType(cast(List[Type], arg_types), arg_kinds, arg_names,
                                 ret_type, function_type)
        func = FuncDef(method_name, args, Block([]), signature)
        # The accept will resolve all unbound variables, etc.
        ctx.api.accept(func)
        ctx.cls.info.names[method_name] = SymbolTableNode(MDEF, func)

    if get_bool_argument(decorator, "init", attrs_arguments):
        # Generate the __init__ method.

        # Check the init args for correct default-ness.  Note: This has to be done after all the
        # attributes for all classes have been read, because subclasses can override parents.
        last_default = False
        for name, attribute in attributes.items():
            if not attribute.has_default and last_default:
                ctx.api.fail(
                    "Non-default attributes not allowed after default attributes.",
                    attribute.context)
            last_default = attribute.has_default

        add_method('__init__',
                   [attribute.argument() for attribute in attributes.values()
                    if attribute.init],
                   NoneTyp())

    if get_bool_argument(decorator, "frozen", attrs_arguments):
        # If the class is frozen then all the attributes need to be turned into properties.
        for name in attributes:
            node = ctx.cls.info.names[name].node
            assert isinstance(node, Var)
            node.is_initialized_in_class = False
            node.is_property = True

    if get_bool_argument(decorator, "cmp", attrs_arguments):
        # Generate cmp methods that look like this:
        #   def __ne__(self, other: '<class name>') -> bool: ...
        # We use fullname to handle nested classes, splitting to remove the module name.
        other_type = UnboundType(ctx.cls.info.fullname().split(".", 1)[1])
        bool_type = ctx.api.named_type('__builtins__.bool')
        args = [Argument(Var('other', other_type), other_type, None, ARG_POS)]
        for method in ['__ne__', '__eq__', '__lt__', '__le__', '__gt__', '__ge__']:
            add_method(method, args, bool_type)
