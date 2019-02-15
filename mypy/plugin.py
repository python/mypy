"""Plugin system for extending mypy.

At large scale the plugin system works as following:
* Plugins are collected from the corresponding config option
  (either a paths to Python files, or installed Python modules)
  and imported using importlib
* Every module should get an entry point function (called 'plugin' by default,
  but may be overridden in the config file), that should accept a single string
  argument that is a full mypy version (includes git commit hash for dev versions)
  and return a subclass of mypy.plugins.Plugin
* All plugin class constructors should match the signature of mypy.plugin.Plugin
  (i.e. should accept an mypy.options.Options object), and *must* call super().__init__
* At several steps during semantic analysis and type checking mypy calls special `get_xxx`
  methods on user plugins with a single string argument that is a full name of a relevant
  node (see mypy.plugin.Plugin method docstrings for details)
* The plugins are called in the order they are passed in the config option. Every plugin must
  decide whether to act on a given full name. The first plugin that returns non-None object
  will be used
* The above decision should be made using the limited common API specified by
  mypy.plugin.CommonPluginApi
* The callback returned by the plugin will be called with a larger context that includes
  relevant current state (e.g. a default return type, or a default attribute type) and
  a wider relevant API provider (e.g. SemanticAnalyzerPluginInterface or
  CheckerPluginInterface)
* The result of this is used for further processing. See various `XxxContext` named tuples
  for details about which information is given to each hook.

Plugin developers should ensure that their plugins work well in incremental and
daemon modes. In particular, plugins should not hold global state, and should always call
add_plugin_dependency() in plugin hooks called during semantic analysis, see the method
docstring for more details.

There is no dedicated cache storage for plugins, but plugins can store per-TypeInfo data
in a special .metadata attribute that is serialized to cache between incremental runs.
To avoid collisions between plugins they are encouraged to store their state
under a dedicated key coinciding with plugin name in the metadata dictionary.
Every value stored there must be JSON-serializable.
"""

import types

from abc import abstractmethod
from typing import Any, Callable, List, Tuple, Optional, NamedTuple, TypeVar, Dict
from mypy_extensions import trait

from mypy.nodes import (
    Expression, Context, ClassDef, SymbolTableNode, MypyFile, CallExpr
)
from mypy.tvar_scope import TypeVarScope
from mypy.types import Type, Instance, CallableType, TypeList, UnboundType
from mypy.messages import MessageBuilder
from mypy.options import Options
from mypy.lookup import lookup_fully_qualified
import mypy.interpreted_plugin


@trait
class TypeAnalyzerPluginInterface:
    """Interface for accessing semantic analyzer functionality in plugins.

    Methods docstrings contain only basic info. Look for corresponding implementation
    docstrings in typeanal.py for more details.
    """

    # An options object. Note: these are the cloned options for the current file.
    # This might be different from Plugin.options (that contains default/global options)
    # if there are per-file options in the config. This applies to all other interfaces
    # in this file.
    options = None  # type: Options

    @abstractmethod
    def fail(self, msg: str, ctx: Context) -> None:
        """Emmit an error message at given location."""
        raise NotImplementedError

    @abstractmethod
    def named_type(self, name: str, args: List[Type]) -> Instance:
        """Construct an instance of a builtin type with given name."""
        raise NotImplementedError

    @abstractmethod
    def analyze_type(self, typ: Type) -> Type:
        """Ananlyze an unbound type using the default mypy logic."""
        raise NotImplementedError

    @abstractmethod
    def analyze_callable_args(self, arglist: TypeList) -> Optional[Tuple[List[Type],
                                                                         List[int],
                                                                         List[Optional[str]]]]:
        """Find types, kinds, and names of arguments from extended callable syntax."""
        raise NotImplementedError


# A context for a hook that semantically analyzes an unbound type.
AnalyzeTypeContext = NamedTuple(
    'AnalyzeTypeContext', [
        ('type', UnboundType),  # Type to analyze
        ('context', Context),   # Relevant location context (e.g. for error messages)
        ('api', TypeAnalyzerPluginInterface)])


@trait
class CommonPluginApi:
    """
    A common plugin API (shared between semantic analysis and type checking phases)
    that all plugin hooks get independently of the context.
    """

    # Global mypy options.
    # Per-file options can be only accessed on various
    # XxxPluginInterface classes.
    options = None  # type: Options

    @abstractmethod
    def lookup_fully_qualified(self, fullname: str) -> Optional[SymbolTableNode]:
        """Lookup a symbol by its full name (including module).

        This lookup function available for all plugins. Return None if a name
        is not found. This function doesn't support lookup from current scope.
        Use SemanticAnalyzerPluginInterface.lookup_qualified() for this."""
        raise NotImplementedError


@trait
class CheckerPluginInterface:
    """Interface for accessing type checker functionality in plugins.

    Methods docstrings contain only basic info. Look for corresponding implementation
    docstrings in checker.py for more details.
    """

    msg = None  # type: MessageBuilder
    options = None  # type: Options

    @abstractmethod
    def fail(self, msg: str, ctx: Context) -> None:
        """Emit an error message at given location."""
        raise NotImplementedError

    @abstractmethod
    def named_generic_type(self, name: str, args: List[Type]) -> Instance:
        """Construct an instance of a builtin type with given type arguments."""
        raise NotImplementedError


@trait
class SemanticAnalyzerPluginInterface:
    """Interface for accessing semantic analyzer functionality in plugins.

    Methods docstrings contain only basic info. Look for corresponding implementation
    docstrings in semanal.py for more details.

    # TODO: clean-up lookup functions.
    """

    modules = None  # type: Dict[str, MypyFile]
    # Options for current file.
    options = None  # type: Options
    cur_mod_id = None  # type: str
    msg = None  # type: MessageBuilder

    @abstractmethod
    def named_type(self, qualified_name: str, args: Optional[List[Type]] = None) -> Instance:
        """Construct an instance of a builtin type with given type arguments."""
        raise NotImplementedError

    @abstractmethod
    def parse_bool(self, expr: Expression) -> Optional[bool]:
        """Parse True/False literals."""
        raise NotImplementedError

    @abstractmethod
    def fail(self, msg: str, ctx: Context, serious: bool = False, *,
             blocker: bool = False) -> None:
        """Emmit an error message at given location."""
        raise NotImplementedError

    @abstractmethod
    def anal_type(self, t: Type, *,
                  tvar_scope: Optional[TypeVarScope] = None,
                  allow_tuple_literal: bool = False,
                  allow_unbound_tvars: bool = False,
                  report_invalid_types: bool = True,
                  third_pass: bool = False) -> Optional[Type]:
        """Analyze an unbound type.

        Return None if the some part of the type is not ready yet (only
        happens with the new semantic analyzer). In this case the current
        target being analyzed will be deferred and analyzed again.
        """
        raise NotImplementedError

    @abstractmethod
    def class_type(self, self_type: Type) -> Type:
        """Generate type of first argument of class methods from type of self."""
        raise NotImplementedError

    @abstractmethod
    def builtin_type(self, fully_qualified_name: str) -> Instance:
        """Deprecated: use named_type instead."""
        raise NotImplementedError

    @abstractmethod
    def lookup_fully_qualified(self, name: str) -> SymbolTableNode:
        """Lookup a symbol by its fully qualified name.

        Raise an error if not found.
        """
        raise NotImplementedError

    @abstractmethod
    def lookup_fully_qualified_or_none(self, name: str) -> Optional[SymbolTableNode]:
        """Lookup a symbol by its fully qualified name.

        Return None if not found.
        """
        raise NotImplementedError

    @abstractmethod
    def lookup_qualified(self, name: str, ctx: Context,
                         suppress_errors: bool = False) -> Optional[SymbolTableNode]:
        """Lookup symbol using a name in current scope.

        This follows Python local->non-local->global->builtins rules.
        """
        raise NotImplementedError

    @abstractmethod
    def add_plugin_dependency(self, trigger: str, target: Optional[str] = None) -> None:
        """Specify semantic dependencies for generated methods/variables.

        If the symbol with full name given by trigger is found to be stale by mypy,
        then the body of node with full name given by target will be re-checked.
        By default, this is the node that is currently analyzed.

        For example, the dataclass plugin adds a generated __init__ method with
        a signature that depends on types of attributes in ancestor classes. If any
        attribute in an ancestor class gets stale (modified), we need to reprocess
        the subclasses (and thus regenerate __init__ methods).

        This is used by fine-grained incremental mode (mypy daemon). See mypy/server/deps.py
        for more details.
        """
        raise NotImplementedError

    @abstractmethod
    def add_symbol_table_node(self, name: str, stnode: SymbolTableNode) -> Any:
        """Add node to global symbol table (or to nearest class if there is one)."""
        raise NotImplementedError

    @abstractmethod
    def qualified_name(self, n: str) -> str:
        """Make qualified name using current module and enclosing class (if any)."""
        raise NotImplementedError


# A context for a function hook that infers the return type of a function with
# a special signature.
#
# A no-op callback would just return the inferred return type, but a useful
# callback at least sometimes can infer a more precise type.
FunctionContext = NamedTuple(
    'FunctionContext', [
        ('arg_types', List[List[Type]]),   # List of actual caller types for each formal argument
        ('arg_kinds', List[List[int]]),    # Ditto for argument kinds, see nodes.ARG_* constants
        # Names of formal parameters from the callee definition,
        # these will be sufficient in most cases.
        ('callee_arg_names', List[Optional[str]]),
        # Names of actual arguments in the call expression. For example,
        # in a situation like this:
        #     def func(**kwargs) -> None:
        #         pass
        #     func(kw1=1, kw2=2)
        # callee_arg_names will be ['kwargs'] and arg_names will be [['kw1', 'kw2']].
        ('arg_names', List[List[Optional[str]]]),
        ('default_return_type', Type),     # Return type inferred from signature
        ('args', List[List[Expression]]),  # Actual expressions for each formal argument
        ('context', Context),              # Relevant location context (e.g. for error messages)
        ('api', CheckerPluginInterface)])

# A context for a method signature hook that infers a better signature for a
# method.  Note that argument types aren't available yet.  If you need them,
# you have to use a method hook instead.
MethodSigContext = NamedTuple(
    'MethodSigContext', [
        ('type', Type),                       # Base object type for method call
        ('args', List[List[Expression]]),     # Actual expressions for each formal argument
        ('default_signature', CallableType),  # Original signature of the method
        ('context', Context),                 # Relevant location context (e.g. for error messages)
        ('api', CheckerPluginInterface)])

# A context for a method hook that infers the return type of a method with a
# special signature.
#
# This is very similar to FunctionContext (only differences are documented).
MethodContext = NamedTuple(
    'MethodContext', [
        ('type', Type),                    # Base object type for method call
        ('arg_types', List[List[Type]]),   # List of actual caller types for each formal argument
        # see FunctionContext for details about names and kinds
        ('arg_kinds', List[List[int]]),
        ('callee_arg_names', List[Optional[str]]),
        ('arg_names', List[List[Optional[str]]]),
        ('default_return_type', Type),     # Return type inferred by mypy
        ('args', List[List[Expression]]),  # Lists of actual expressions for every formal argument
        ('context', Context),
        ('api', CheckerPluginInterface)])

# A context for an attribute type hook that infers the type of an attribute.
AttributeContext = NamedTuple(
    'AttributeContext', [
        ('type', Type),               # Type of object with attribute
        ('default_attr_type', Type),  # Original attribute type
        ('context', Context),         # Relevant location context (e.g. for error messages)
        ('api', CheckerPluginInterface)])

# A context for a class hook that modifies the class definition.
ClassDefContext = NamedTuple(
    'ClassDefContext', [
        ('cls', ClassDef),       # The class definition
        ('reason', Expression),  # The expression being applied (decorator, metaclass, base class)
        ('api', SemanticAnalyzerPluginInterface)
    ])

# A context for dynamic class definitions like
# Base = declarative_base()
DynamicClassDefContext = NamedTuple(
    'DynamicClassDefContext', [
        ('call', CallExpr),      # The r.h.s. of dynamic class definition
        ('name', str),           # The name this class is being assigned to
        ('api', SemanticAnalyzerPluginInterface)
    ])


class Plugin(CommonPluginApi):
    """Base class of all type checker plugins.

    This defines a no-op plugin.  Subclasses can override some methods to
    provide some actual functionality.

    All get_ methods are treated as pure functions (you should assume that
    results might be cached). A plugin should return None from a get_ method
    to give way to other plugins.

    Look at the comments of various *Context objects for additional information on
    various hooks.
    """

    def __init__(self, options: Options) -> None:
        self.options = options
        self.python_version = options.python_version
        # This can't be set in __init__ because it is executed too soon in build.py.
        # Therefore, build.py *must* set it later before graph processing starts
        # by calling set_modules().
        self._modules = None  # type: Optional[Dict[str, MypyFile]]

    def set_modules(self, modules: Dict[str, MypyFile]) -> None:
        self._modules = modules

    def lookup_fully_qualified(self, fullname: str) -> Optional[SymbolTableNode]:
        assert self._modules is not None
        return lookup_fully_qualified(fullname, self._modules)

    def get_type_analyze_hook(self, fullname: str
                              ) -> Optional[Callable[[AnalyzeTypeContext], Type]]:
        """Customize behaviour of the type analyzer for given full names.

        This method is called during the semantic analysis pass whenever mypy sees an
        unbound type. For example, while analysing this code:

            from lib import Special, Other

            var: Special
            def func(x: Other[int]) -> None:
                ...

        this method will be called with 'lib.Special', and then with 'lib.Other'.
        The callback returned by plugin must return an analyzed type,
        i.e. an instance of `mypy.types.Type`.
        """
        return None

    def get_function_hook(self, fullname: str
                          ) -> Optional[Callable[[FunctionContext], Type]]:
        """Adjust the return type of a function call.

        This method is called after type checking a call. Plugin may adjust the return
        type inferred by mypy, and/or emmit some error messages. Note, this hook is also
        called for class instantiation calls, so that in this example:

            from lib import Class, do_stuff

            do_stuff(42)
            Class()

        This method will be called with 'lib.do_stuff' and then with 'lib.Class'.
        """
        return None

    def get_method_signature_hook(self, fullname: str
                                  ) -> Optional[Callable[[MethodSigContext], CallableType]]:
        """Adjust the signature of a method.

        This method is called before type checking a method call. Plugin
        may infer a better type for the method. The hook is also called for special
        Python dunder methods except __init__ and __new__ (use get_function_hook to customize
        class instantiation). This function is called with the method full name using
        the class where it was _defined_. For example, in this code:

            from lib import Special

            class Base:
                def method(self, arg: Any) -> Any:
                    ...
            class Derived(Base):
                ...

            var: Derived
            var.method(42)

            x: Special
            y = x[0]

        this method is called with '__main__.Base.method', and then with
        'lib.Special.__getitem__'.
        """
        return None

    def get_method_hook(self, fullname: str
                        ) -> Optional[Callable[[MethodContext], Type]]:
        """Adjust return type of a method call.

        This is the same as get_function_hook(), but is called with the
        method full name (again, using the class where the method is defined).
        """
        return None

    def get_attribute_hook(self, fullname: str
                           ) -> Optional[Callable[[AttributeContext], Type]]:
        """Adjust type of a class attribute.

        This method is called with attribute full name using the class where the attribute was
        defined (or Var.info.fullname() for generated attributes).

        For classes without __getattr__ or __getattribute__, this hook is only called for
        names of fields/properties (but not methods) that exist in the instance MRO.

        For classes that implement __getattr__ or __getattribute__, this hook is called
        for all fields/properties, including nonexistent ones (but still not methods).

        For example:

            class Base:
                x: Any
                def __getattr__(self, attr: str) -> Any: ...

            class Derived(Base):
                ...

            var: Derived
            var.x
            var.y

        get_attribute_hook is called with '__main__.Base.x' and '__main__.Base.y'.
        However, if we had not implemented __getattr__ on Base, you would only get
        the callback for 'var.x'; 'var.y' would produce an error without calling the hook.
        """
        return None

    def get_class_decorator_hook(self, fullname: str
                                 ) -> Optional[Callable[[ClassDefContext], None]]:
        """Update class definition for given class decorators.

        The plugin can modify a TypeInfo _in place_ (for example add some generated
        methods to the symbol table). This hook is called after the class body was
        semantically analyzed.

        The hook is called with full names of all class decorators, for example
        """
        return None

    def get_metaclass_hook(self, fullname: str
                           ) -> Optional[Callable[[ClassDefContext], None]]:
        """Update class definition for given declared metaclasses.

        Same as get_class_decorator_hook() but for metaclasses. Note:
        this hook will be only called for explicit metaclasses, not for
        inherited ones.

        TODO: probably it should also be called on inherited metaclasses.
        """
        return None

    def get_base_class_hook(self, fullname: str
                            ) -> Optional[Callable[[ClassDefContext], None]]:
        """Update class definition for given base classes.

        Same as get_class_decorator_hook() but for base classes. Base classes
        don't need to refer to TypeInfos, if a base class refers to a variable with
        Any type, this hook will still be called.
        """
        return None

    def get_customize_class_mro_hook(self, fullname: str
                                     ) -> Optional[Callable[[ClassDefContext], None]]:
        """Customize MRO for given classes.

        The plugin can modify the class MRO _in place_. This method is called
        with the class full name before its body was semantically analyzed.
        """
        return None

    def get_dynamic_class_hook(self, fullname: str
                               ) -> Optional[Callable[[DynamicClassDefContext], None]]:
        """Semantically analyze a dynamic class definition.

        This plugin hook allows to semantically analyze dynamic class definitions like:

            from lib import dynamic_class

            X = dynamic_class('X', [])

        For such definition, this hook will be called with 'lib.dynamic_class'.
        The plugin should create the corresponding TypeInfo, and place it into a relevant
        symbol table, e.g. using ctx.api.add_symbol_table_node().
        """
        return None


T = TypeVar('T')


class WrapperPlugin(Plugin):
    """A plugin that wraps an interpreted plugin.

    This is a ugly workaround the limitation that mypyc-compiled
    classes can't be subclassed by interpreted ones, so instead we
    create a new class for interpreted clients to inherit from and
    dispatch to it from here.

    Eventually mypyc ought to do something like this automatically.
    """

    def __init__(self, plugin: mypy.interpreted_plugin.InterpretedPlugin) -> None:
        super().__init__(plugin.options)
        self.plugin = plugin

    def set_modules(self, modules: Dict[str, MypyFile]) -> None:
        self.plugin.set_modules(modules)

    def lookup_fully_qualified(self, fullname: str) -> Optional[SymbolTableNode]:
        return self.plugin.lookup_fully_qualified(fullname)

    def get_type_analyze_hook(self, fullname: str
                              ) -> Optional[Callable[[AnalyzeTypeContext], Type]]:
        return self.plugin.get_type_analyze_hook(fullname)

    def get_function_hook(self, fullname: str
                          ) -> Optional[Callable[[FunctionContext], Type]]:
        return self.plugin.get_function_hook(fullname)

    def get_method_signature_hook(self, fullname: str
                                  ) -> Optional[Callable[[MethodSigContext], CallableType]]:
        return self.plugin.get_method_signature_hook(fullname)

    def get_method_hook(self, fullname: str
                        ) -> Optional[Callable[[MethodContext], Type]]:
        return self.plugin.get_method_hook(fullname)

    def get_attribute_hook(self, fullname: str
                           ) -> Optional[Callable[[AttributeContext], Type]]:
        return self.plugin.get_attribute_hook(fullname)

    def get_class_decorator_hook(self, fullname: str
                                 ) -> Optional[Callable[[ClassDefContext], None]]:
        return self.plugin.get_class_decorator_hook(fullname)

    def get_metaclass_hook(self, fullname: str
                           ) -> Optional[Callable[[ClassDefContext], None]]:
        return self.plugin.get_metaclass_hook(fullname)

    def get_base_class_hook(self, fullname: str
                            ) -> Optional[Callable[[ClassDefContext], None]]:
        return self.plugin.get_base_class_hook(fullname)

    def get_customize_class_mro_hook(self, fullname: str
                                     ) -> Optional[Callable[[ClassDefContext], None]]:
        return self.plugin.get_customize_class_mro_hook(fullname)

    def get_dynamic_class_hook(self, fullname: str
                               ) -> Optional[Callable[[DynamicClassDefContext], None]]:
        return self.plugin.get_dynamic_class_hook(fullname)


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

    def set_modules(self, modules: Dict[str, MypyFile]) -> None:
        for plugin in self._plugins:
            plugin.set_modules(modules)

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

    def get_customize_class_mro_hook(self, fullname: str
                                     ) -> Optional[Callable[[ClassDefContext], None]]:
        return self._find_hook(lambda plugin: plugin.get_customize_class_mro_hook(fullname))

    def get_dynamic_class_hook(self, fullname: str
                               ) -> Optional[Callable[[DynamicClassDefContext], None]]:
        return self._find_hook(lambda plugin: plugin.get_dynamic_class_hook(fullname))

    def _find_hook(self, lookup: Callable[[Plugin], T]) -> Optional[T]:
        for plugin in self._plugins:
            hook = lookup(plugin)
            if hook:
                return hook
        return None


def _dummy() -> None:
    """Only used to test whether we are running in compiled mode."""


# This is an incredibly frumious hack. If this module is compiled by mypyc,
# set the module 'Plugin' attribute to point to InterpretedPlugin. This means
# that anything interpreted that imports Plugin will get InterpretedPlugin
# while anything compiled alongside this module will get the real Plugin.
if isinstance(_dummy, types.BuiltinFunctionType):
    plugin_types = (Plugin, mypy.interpreted_plugin.InterpretedPlugin)  # type: Tuple[type, ...]
    globals()['Plugin'] = mypy.interpreted_plugin.InterpretedPlugin
else:
    plugin_types = (Plugin,)
