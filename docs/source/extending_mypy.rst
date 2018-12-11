.. _extending-mypy:

Extending and integrating mypy
==============================

.. _integrating-mypy:

Integrating mypy into another Python application
************************************************

It is possible to integrate mypy into another Python 3 application by
importing ``mypy.api`` and calling the ``run`` function with a parameter of type ``List[str]``, containing
what normally would have been the command line arguments to mypy.

Function ``run`` returns a ``Tuple[str, str, int]``, namely
``(<normal_report>, <error_report>, <exit_status>)``, in which ``<normal_report>``
is what mypy normally writes to ``sys.stdout``, ``<error_report>`` is what mypy
normally writes to ``sys.stderr`` and ``exit_status`` is the exit status mypy normally
returns to the operating system.

A trivial example of using the api is the following

.. code-block:: python

    import sys
    from mypy import api

    result = api.run(sys.argv[1:])

    if result[0]:
        print('\nType checking report:\n')
        print(result[0])  # stdout

    if result[1]:
        print('\nError report:\n')
        print(result[1])  # stderr

    print ('\nExit status:', result[2])

Extending mypy using plugins
****************************

Python is a highly dynamic language and has extensive metaprogramming
capabilities. Many poppular libraries use these to create APIs that may
be more flexible and/or natural for humans, but are hard to express using
static types. Extending the PEP 484 type system to accommodate all existing
dynamic patterns is impractical and often just impossible.

Mypy supports a plugin system that lets you customize the way mypy type checks
code. This can be useful if you want to extend mypy so it can type check code
that uses a library that is difficult to express using just PEP 484 types, for
example.

The plugin system is focused on improving mypy's understanding
of *semantics* of third party frameworks, there is currently no way to define
new first class kinds of types.

.. note::

   The plugin system is experimental and prone to change. If you want to write
   a mypy plugin, we recommend you start by contacting the mypy core developers
   on `gitter <https://gitter.im/python/typing>`_. In particular, there are
   no guarantees about backwards compatibility. Backwards incompatible changes
   may be made without a deprecation period.

Configuring mypy to use plugins
*******************************

Plugins can be specified using a :ref:`config file <config-file>` using one
of the two formats: full path to the plugin file

.. code-block:: ini

    [mypy]
    plugins = /path/to/plugin.py

Large scale overview
********************

Plugins are collected from the corresponding config option
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

The above two-step plugin choice procedure exists to allow effectively coordinate
multiple plugins.

Plugin developers should ensure that their plugins work well in incremental and
daemon modes. In particular, plugins should not hold global state, and should always call
add_plugin_dependency() in plugin hooks called during semantic analysis.

There is no dedicated cache storage for plugins, but plugins can store per-TypeInfo data
in a special .metadata attribute that is serialized to cache between incremental runs.
To avoid collisions between plugins they are encouraged to store their state
under a dedicated key coinciding with plugin name in the metadata dictionary.
Every value stored there must be JSON-serializable.


Current list of plugin hooks
****************************

get_type_analyze_hook()
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

get_function_hook()
    """Adjust the return type of a function call.

    This method is called after type checking a call. Plugin may adjust the return
    type inferred by mypy, and/or emmit some error messages. Note, this hook is also
    called for class instantiation calls, so that in this example:

        from lib import Class, do_stuff

        do_stuff(42)
        Class()

    This method will be called with 'lib.do_stuff' and then with 'lib.Class'.

get_method_signature_hook()
    """Adjust the signature of a method.

    This method is called before type checking a method call. Plugin
    may infer a better type for the method. The hook is called for both special and
    user-defined methods. This function is called with the method full name using
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

def get_method_hook(self, fullname: str
                    ) -> Optional[Callable[[MethodContext], Type]]:
    """Adjust return type of a method call.

    This is the same as get_function_hook(), but is called with the
    method full name (again, using the class where the method is defined).

def get_attribute_hook(self, fullname: str
                       ) -> Optional[Callable[[AttributeContext], Type]]:
    """Adjust type of a class attribute.

    This method is called with attribute full name using the class where the attribute was
    defined (or Var.info.fullname() for generated attributes). Currently, this hook is only
    called for names that exist in the class MRO, for example in:

        class Base:
            x: Any
            def __getattr__(self, attr: str) -> Any: ...

        class Derived(Base):
            ...

        var: Derived
        var.x
        var.y

    this method is only called with '__main__.Base.x'.

def get_class_decorator_hook(self, fullname: str
                             ) -> Optional[Callable[[ClassDefContext], None]]:
    """Update class definition for given class decorators.

    The plugin can modify a TypeInfo _in place_ (for example add some generated
    methods to the symbol table). This hook is called after the class body was
    semantically analyzed.

    The hook is called with full names of all class decorators, for example

def get_metaclass_hook(self, fullname: str
                       ) -> Optional[Callable[[ClassDefContext], None]]:
    """Update class definition for given declared metaclasses.

    Same as get_class_decorator_hook() but for metaclasses. Note:
    this hook will be only called for explicit metaclasses, not for
    inherited ones.

def get_base_class_hook(self, fullname: str
                        ) -> Optional[Callable[[ClassDefContext], None]]:
    """Update class definition for given base classes.

    Same as get_class_decorator_hook() but for base classes. Base classes
    don't need to refer to TypeInfo's, if a base class refers to a variable with
    Any type, this hook will still be called.

def get_customize_class_mro_hook(self, fullname: str
                                 ) -> Optional[Callable[[ClassDefContext], None]]:
    """Customize MRO for given classes.

    The plugin can modify the class MRO _in place_. This method is called
    with the class full name before its body was semantically analyzed.

def get_dynamic_class_hook(self, fullname: str
                           ) -> Optional[Callable[[DynamicClassDefContext], None]]:
    """Semantically analyze a dynamic class definition.

    This plugin hook allows to semantically analyze dynamic class definitions like:

        from lib import dynamic_class

        X = dynamic_class('X', [])

    For such definition, this hook will be called with 'lib.dynamic_class'.
    The plugin should create the corresponding TypeInfo, and place it into a relevant
    symbol table, e.g. using ctx.api.add_symbol_table_node().

