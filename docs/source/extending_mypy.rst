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
of the two formats: full path to the plugin file, or a module name (if the plugin
is installed using ``pip install`` in the same virtual environment
where mypy is running). The two formats can be mixed, for example:

.. code-block:: ini

    [mypy]
    plugins = /one/plugin.py, other.plugin

Mypy will try to import the plugins and will look for an entry point function
named ``plugin``. If the plugin entry point function has a different name, it
can be specified after colon:

.. code-block:: ini

    [mypy]
    plugins = custom_plugin:custom_entry_point

In following sections we describe basics of the plugin system with
some examples. For more technical details please read docstrings
in ``mypy/plugin.py``. Also you can find good examples in the bundled
plugins located in ``mypy/plugins``.

Large scale overview
********************

Every entry point function should accept a single string argument
that is a full mypy version and return a subclass of ``mypy.plugins.Plugin``.
At several steps during semantic analysis and type checking mypy calls special
``get_xxx`` methods listed :ref:`below <plugin-hooks>` on user plugins.
The first plugin that returns non-None object will be used to customize the
corresponding aspect of analyzing/checking the current abstract syntax tree node.

The callback returned by the ``get_xxx`` method will be given a detailed
current context and an API to create new nodes, new types, emit error messages
etc., and the result will be used for further processing. Such two-step plugin
choice procedure exists to allow effectively coordinate multiple plugins.

Plugin developers should ensure that their plugins work well in incremental and
daemon modes. In particular, plugins should not hold global state, and should
always add semantic dependencies for generated nodes.

.. _plugin_hooks:

Current list of plugin hooks
****************************

**get_type_analyze_hook()** customizes behaviour of the type analyzer.
For example, PEP 484 doesn't support definig variadic generic types:

.. code-block:: python

    from lib import Vector

    a: Vector[int, int]
    b: Vector[int, int, int]

When analyzing this code, mypy will call ``get_type_analyze_hook("lib.Vector")``,
so the plugin can return some valid type for each variable.

**get_function_hook()** is used to adjust the return type of a function call.
This is a good choice if the return type of some function depends on *values*
of some arguments. This hook will be also called for instantiation of classes.
For example:

.. code-block:: python

   from orm import Property

   p = Property()  # a plugin can infer orm.Property[orm.Null]

**get_method_hook()** is the same as ``get_function_hook()`` but for methods
instead of module level functions.

**get_method_signature_hook()** is used to adjust the signature of a method.
This includes special Python methods. For example in this code:

.. code-block:: python

   from lib import MagicCollection

   var: MagicCollection
   x = var[0]

mypy will call ``get_method_signature_hook("lib.MagicCollection.__getitem__")``.

**get_attribute_hook** can be used to give more precise type of an instance
attribute. Note however, that this method is only called for variables that
already exist in the class symbol table. If you want to add some generated
variables/methods to the symbol table you can use one of the three hooks
below.

**get_class_decorator_hook()** can bu used to update class definition for
given class decorators. For example, you can add some attributes to the class
to match runtime behaviour:

.. code-block:: python

   from lib import customize

   @customize
   class UserDefined:
       pass

   var = UserDefined
   var.customized  # mypy can understand this using a plugin

**get_metaclass_hook()** is similar to above, but for metaclasses.

**get_base_class_hook()** is similar to above, but for base classes.

**get_dynamic_class_hook()** can be used to allow dynamic class definitions
in mypy. This plugin hook is called for every assignment to a simple name
where right hand side is a function call:

.. code-block:: python

   from lib import dynamic_class

   X = dynamic_class('X', [])

For such definition, mypy will call ``get_dynamic_class_hook("lib.dynamic_class")``.
The plugin should create the corresponding ``mypy.nodes.TypeInfo`` object, and
place it into a relevant symbol table.

**get_customize_class_mro_hook()** can be used to modify class MRO (for example
insert some entries there) before the class body is analyzed.
