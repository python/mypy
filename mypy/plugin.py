from typing import Callable, Dict, List, Tuple, Type as Class, Optional, NamedTuple

from types import ModuleType
from mypy.nodes import Expression, StrExpr, IntExpr, UnaryExpr, Context
from mypy.types import (
    Type, Instance, CallableType, TypedDictType, UnionType, NoneTyp, FunctionLike, TypeVarType,
    AnyType
)
MYPY = False
if MYPY:
    from mypy.messages import MessageBuilder


def _safeimport(path: str) -> Optional[ModuleType]:
    try:
        module = __import__(path)
    except ImportError as err:
        if err.name == path:  # type: ignore  # ImportError stubs need to be updated
            # No such module in the path.
            return None
        else:
            raise
    for part in path.split('.')[1:]:
        try:
            module = getattr(module, part)
        except AttributeError:
            return None
    return module


def locate(path: str) -> Optional[object]:
    """Locate an object by string identifier, importing as necessary.

    The two identifiers supported are:

    dotted path:
        package.module.object.child

    file path followed by dotted object path]
        /path/to/module.py:object.child
    """
    if ':' in path:
        raise RuntimeError
        # not supported in python 3.3
        # file_path, obj_path = path.split(':', 1)
        # mod_name = os.path.splitext(os.path.basename(file_path))[0]
        # spec = importlib.util.spec_from_file_location(mod_name, file_path)
        # module = importlib.util.module_from_spec(spec)
        # spec.loader.exec_module(module)
        # parts = obj_path.split('.')
    else:
        parts = [part for part in path.split('.') if part]
        module, n = None, 0
        while n < len(parts):
            nextmodule = _safeimport('.'.join(parts[:n + 1]))
            if nextmodule:
                module, n = nextmodule, n + 1
            else:
                break
        parts = parts[n:]

    if not module:
        return None

    obj = module
    for part in parts:
        try:
            obj = getattr(obj, part)
        except AttributeError:
            return None
    return obj


# Create an Instance given full name of class and type arguments.
NamedInstanceCallback = Callable[[str, List[Type]], Type]

PluginRegistry = NamedTuple('PluginRegistry', [('name', str),
                                               ('location', str),
                                               ('options', Dict[str, str])])

# Some objects and callbacks that plugins can use to get information from the
# type checker or to report errors.
PluginContext = NamedTuple('PluginContext', [('named_instance', NamedInstanceCallback),
                                             ('msg', 'MessageBuilder'),
                                             ('context', Context)])


# A callback that infers the return type of a function with a special signature.
#
# A no-op callback would just return the inferred return type, but a useful callback
# at least sometimes can infer a more precise type.
FunctionHook = Callable[
    [
        List[List[Type]],        # List of types caller provides for each formal argument
        List[List[Expression]],  # Actual argument expressions for each formal argument
        Type,                    # Return type for call inferred using the regular signature
        NamedInstanceCallback    # Callable for constructing a named instance type
    ],
    Type  # Return type inferred by the callback
]

# A callback that may infer a better signature for a method.  Note that argument types aren't
# available yet.  If you need them, you have to use a MethodHook instead.
MethodSignatureHook = Callable[
    [
        Type,                    # Base object type
        List[List[Expression]],  # Actual argument expressions for each formal argument
        CallableType,            # Original signature of the method
        NamedInstanceCallback    # Callable for constructing a named instance type
    ],
    CallableType  # Potentially more precise signature inferred for the method
]

# A callback that infers the return type of a method with a special signature.
#
# This is pretty similar to FunctionHook.
MethodHook = Callable[
    [
        Type,                    # Base object type
        List[List[Type]],        # List of types caller provides for each formal argument
        List[List[Expression]],  # Actual argument expressions for each formal argument
        Type,                    # Return type for call inferred using the regular signature
        PluginContext            # Access to type checking context
    ],
    Type  # Return type inferred by the callback
]


class Plugin:
    """Base class of type checker plugins.

    This defines a no-op plugin.  Subclasses can override some methods to
    provide some actual functionality.

    All get_ methods are treated as pure functions (you should assume that
    results might be cached).
    """

    # TODO: Way of chaining multiple plugins

    def __init__(self, python_version: Tuple[int, int]) -> None:
        self.python_version = python_version

    def get_function_hook(self, fullname: str) -> Optional[FunctionHook]:
        return None

    def get_method_signature_hook(self, fullname: str) -> Optional[MethodSignatureHook]:
        return None

    def get_method_hook(self, fullname: str) -> Optional[MethodHook]:
        return None

    # TODO: metaclass / class decorator hook


class DefaultPlugin(Plugin):
    """Type checker plugin that is enabled by default."""

    def get_function_hook(self, fullname: str) -> Optional[FunctionHook]:
        if fullname == 'contextlib.contextmanager':
            return contextmanager_callback
        elif fullname == 'builtins.open' and self.python_version[0] == 3:
            return open_callback
        return None

    def get_method_signature_hook(self, fullname: str) -> Optional[MethodSignatureHook]:
        if fullname == 'typing.Mapping.get':
            return typed_dict_get_signature_callback
        return None

    def get_method_hook(self, fullname: str) -> Optional[MethodHook]:
        if fullname == 'typing.Mapping.get':
            return typed_dict_get_callback
        elif fullname == 'builtins.int.__pow__':
            return int_pow_callback
        return None


class PluginManager(Plugin):
    def __init__(self, python_version: Tuple[int, int],
                 plugins: List[Class[Plugin]]) -> None:
        super().__init__(python_version)
        # TODO: handle exceptions to provide more feedback
        self.plugins = [p(python_version) for p in plugins]
        self._function_hooks = {}  # type: Dict[str, Optional[FunctionHook]]
        self._method_signature_hooks = {}  # type: Dict[str, Optional[MethodSignatureHook]]
        self._method_hooks = {}  # type: Dict[str, Optional[MethodHook]]

    def get_function_hook(self, fullname: str) -> Optional[FunctionHook]:
        hook = self._function_hooks.get(fullname)
        if hook is None:
            for plugin in self.plugins:
                hook = plugin.get_function_hook(fullname)
                if hook is not None:
                    break
            self._function_hooks[fullname] = hook
        return hook

    def get_method_signature_hook(self, fullname: str) -> Optional[MethodSignatureHook]:
        hook = self._method_signature_hooks.get(fullname)
        if hook is None:
            for plugin in self.plugins:
                hook = plugin.get_method_signature_hook(fullname)
                if hook is not None:
                    break
            self._method_signature_hooks[fullname] = hook
        return hook

    def get_method_hook(self, fullname: str) -> Optional[MethodHook]:
        hook = self._method_hooks.get(fullname)
        if hook is None:
            for plugin in self.plugins:
                hook = plugin.get_method_hook(fullname)
                if hook is not None:
                    break
            self._method_hooks[fullname] = hook
        return hook


def open_callback(
        arg_types: List[List[Type]],
        args: List[List[Expression]],
        inferred_return_type: Type,
        named_generic_type: Callable[[str, List[Type]], Type]) -> Type:
    """Infer a better return type for 'open'.

    Infer TextIO or BinaryIO as the return value if the mode argument is not
    given or is a literal.
    """
    mode = None
    if not arg_types or len(arg_types[1]) != 1:
        mode = 'r'
    elif isinstance(args[1][0], StrExpr):
        mode = args[1][0].value
    if mode is not None:
        assert isinstance(inferred_return_type, Instance)
        if 'b' in mode:
            return named_generic_type('typing.BinaryIO', [])
        else:
            return named_generic_type('typing.TextIO', [])
    return inferred_return_type


def contextmanager_callback(
        arg_types: List[List[Type]],
        args: List[List[Expression]],
        inferred_return_type: Type,
        named_generic_type: Callable[[str, List[Type]], Type]) -> Type:
    """Infer a better return type for 'contextlib.contextmanager'."""
    # Be defensive, just in case.
    if arg_types and len(arg_types[0]) == 1:
        arg_type = arg_types[0][0]
        if isinstance(arg_type, CallableType) and isinstance(inferred_return_type, CallableType):
            # The stub signature doesn't preserve information about arguments so
            # add them back here.
            return inferred_return_type.copy_modified(
                arg_types=arg_type.arg_types,
                arg_kinds=arg_type.arg_kinds,
                arg_names=arg_type.arg_names)
    return inferred_return_type


def typed_dict_get_signature_callback(
        object_type: Type,
        args: List[List[Expression]],
        signature: CallableType,
        named_generic_type: Callable[[str, List[Type]], Type]) -> CallableType:
    """Try to infer a better signature type for TypedDict.get.

    This is used to get better type context for the second argument that
    depends on a TypedDict value type.
    """
    if (isinstance(object_type, TypedDictType)
            and len(args) == 2
            and len(args[0]) == 1
            and isinstance(args[0][0], StrExpr)
            and len(signature.arg_types) == 2
            and len(signature.variables) == 1):
        key = args[0][0].value
        value_type = object_type.items.get(key)
        if value_type:
            # Tweak the signature to include the value type as context. It's
            # only needed for type inference since there's a union with a type
            # variable that accepts everything.
            tv = TypeVarType(signature.variables[0])
            return signature.copy_modified(
                arg_types=[signature.arg_types[0],
                           UnionType.make_simplified_union([value_type, tv])])
    return signature


def typed_dict_get_callback(
        object_type: Type,
        arg_types: List[List[Type]],
        args: List[List[Expression]],
        inferred_return_type: Type,
        context: PluginContext) -> Type:
    """Infer a precise return type for TypedDict.get with literal first argument."""
    if (isinstance(object_type, TypedDictType)
            and len(arg_types) >= 1
            and len(arg_types[0]) == 1):
        if isinstance(args[0][0], StrExpr):
            key = args[0][0].value
            value_type = object_type.items.get(key)
            if value_type:
                if len(arg_types) == 1:
                    return UnionType.make_simplified_union([value_type, NoneTyp()])
                elif len(arg_types) == 2 and len(arg_types[1]) == 1:
                    return UnionType.make_simplified_union([value_type, arg_types[1][0]])
            else:
                context.msg.typeddict_item_name_not_found(object_type, key, context.context)
                return AnyType()
    return inferred_return_type


def int_pow_callback(
        object_type: Type,
        arg_types: List[List[Type]],
        args: List[List[Expression]],
        inferred_return_type: Type,
        context: PluginContext) -> Type:
    """Infer a more precise return type for int.__pow__."""
    if (len(arg_types) == 1
            and len(arg_types[0]) == 1):
        arg = args[0][0]
        if isinstance(arg, IntExpr):
            exponent = arg.value
        elif isinstance(arg, UnaryExpr) and arg.op == '-' and isinstance(arg.expr, IntExpr):
            exponent = -arg.expr.value
        else:
            # Right operand not an int literal or a negated literal -- give up.
            return inferred_return_type
        if exponent >= 0:
            return context.named_instance('builtins.int', [])
        else:
            return context.named_instance('builtins.float', [])
    return inferred_return_type
