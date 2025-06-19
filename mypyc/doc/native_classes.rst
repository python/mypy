.. _native-classes:

Native classes
==============

Classes in compiled modules are *native classes* by default (some
exceptions are discussed below). Native classes are compiled to C
extension classes, which have some important differences from normal
Python classes. Native classes are similar in many ways to built-in
types, such as ``int``, ``str``, and ``list``.

Immutable namespaces
--------------------

The type object namespace of native classes is mostly immutable (but
class variables can be assigned to)::

    class Cls:
        def method1(self) -> None:
            print("method1")

        def method2(self) -> None:
            print("method2")

    Cls.method1 = Cls.method2  # Error
    Cls.new_method = Cls.method2  # Error

Only attributes defined within a class definition (or in a base class)
can be assigned to (similar to using ``__slots__``)::

    class Cls:
        x: int

        def __init__(self, y: int) -> None:
            self.x = 0
            self.y = y

        def method(self) -> None:
            self.z = "x"

    o = Cls(0)
    print(o.x, o.y)  # OK
    o.z = "y"  # OK
    o.extra = 3  # Error: no attribute "extra"

.. _inheritance:

Inheritance
-----------

Only single inheritance is supported from native classes (except for
:ref:`traits <trait-types>`). Most non-native extension classes can't
be used as base classes, but regular Python classes can be used as
base classes unless they use unsupported metaclasses (see below for
more about this).

These non-native extension classes can be used as base classes of native
classes:

* ``object``
* ``dict`` (and ``dict[k, v]``)
* ``BaseException``
* ``Exception``
* ``ValueError``
* ``IndexError``
* ``LookupError``
* ``UserWarning``

By default, a non-native class can't inherit a native class, and you
can't inherit from a native class outside the compilation unit that
defines the class. You can enable these through
``mypy_extensions.mypyc_attr``::

    from mypy_extensions import mypyc_attr

    @mypyc_attr(allow_interpreted_subclasses=True)
    class Cls:
        ...

Allowing interpreted subclasses has only minor impact on performance
of instances of the native class.  Accessing methods and attributes of
a *non-native* subclass (or a subclass defined in another compilation
unit) will be slower, since it needs to use the normal Python
attribute access mechanism.

You need to install ``mypy-extensions`` to use ``@mypyc_attr``:

.. code-block:: text

    pip install --upgrade mypy-extensions

Additionally, mypyc recognizes these base classes as special, and
understands how they alter the behavior of classes (including native
classes) that subclass them:

* ``typing.NamedTuple``
* ``typing.Generic``
* ``typing.Protocol``
* ``enum.Enum``

Class variables
---------------

Class variables must be explicitly declared using ``attr: ClassVar``
or ``attr: ClassVar[<type>]``. You can't assign to a class variable
through an instance. Example::

    from typing import ClassVar

    class Cls:
        cv: ClassVar = 0

    Cls.cv = 2  # OK
    o = Cls()
    print(o.cv)  # OK (2)
    o.cv = 3  # Error!

.. tip::

    Constant class variables can be declared using ``typing.Final`` or
    ``typing.Final[<type>]``.

Generic native classes
----------------------

Native classes can be generic. Type variables are *erased* at runtime,
and instances don't keep track of type variable values.

Compiled code thus can't check the values of type variables when
performing runtime type checks. These checks are delayed to when
reading a value with a type variable type::

    from typing import TypeVar, Generic, cast

    T = TypeVar('T')

    class Box(Generic[T]):
        def __init__(self, item: T) -> None:
            self.item = item

    x = Box(1)  # Box[int]
    y = cast(Box[str], x)  # OK (type variable value not checked)
    y.item  # Runtime error: item is "int", but "str" expected

Metaclasses
-----------

Most metaclasses aren't supported with native classes, since their
behavior is too dynamic. You can use these metaclasses, however:

* ``abc.ABCMeta``
* ``typing.GenericMeta`` (used by ``typing.Generic``)

.. note::

   If a class definition uses an unsupported metaclass, *mypyc
   compiles the class into a regular Python class* (non-native
   class).

Class decorators
----------------

Similar to metaclasses, most class decorators aren't supported with
native classes, as they are usually too dynamic. These class
decorators can be used with native classes, however:

* ``mypy_extensions.trait`` (for defining :ref:`trait types <trait-types>`)
* ``mypy_extensions.mypyc_attr`` (see :ref:`above <inheritance>`)
* ``dataclasses.dataclass``
* ``@attr.s(auto_attribs=True)``

Dataclasses and attrs classes have partial native support, and they aren't as
efficient as pure native classes.

.. note::

   If a class definition uses an unsupported class decorator, *mypyc
   compiles the class into a regular Python class* (non-native class).

Defining non-native classes
---------------------------

You can use the ``@mypy_extensions.mypyc_attr(...)`` class decorator
with an argument ``native_class=False`` to explicitly define normal
Python classes (non-native classes)::

    from mypy_extensions import mypyc_attr

    @mypyc_attr(native_class=False)
    class NonNative:
        def __init__(self) -> None:
            self.attr = 1

    setattr(NonNative, "extra", 1)  # Ok

This only has an effect in classes compiled using mypyc. Non-native
classes are significantly less efficient than native classes, but they
are sometimes necessary to work around the limitations of native classes.

Non-native classes can use arbitrary metaclasses and class decorators,
and they support flexible multiple inheritance.  Mypyc will still
generate a compile-time error if you try to assign to a method, or an
attribute that is not defined in a class body, since these are static
type errors detected by mypy::

    o = NonNative()
    o.extra = "x"  # Static type error: "extra" not defined

However, these operations still work at runtime, including in modules
that are not compiled using mypyc. You can also use ``setattr`` and
``getattr`` for dynamic access of arbitrary attributes. Expressions
with an ``Any`` type are also not type checked statically, allowing
access to arbitrary attributes::

    a: Any = o
    a.extra = "x"  # Ok

    setattr(o, "extra", "y")  # Also ok

Implicit non-native classes
---------------------------

If a compiled class uses an unsupported metaclass or an unsupported
class decorator, it will implicitly be a non-native class, as
discussed above. You can still use ``@mypyc_attr(native_class=False)``
to explicitly mark it as a non-native class.

Explicit native classes
-----------------------

You can use ``@mypyc_attr(native_class=True)`` to explicitly declare a
class as a native class. It will be a compile-time error if mypyc
can't compile the class as a native class. You can use this to avoid
accidentally defining implicit non-native classes.

Deleting attributes
-------------------

By default, attributes defined in native classes can't be deleted. You
can explicitly allow certain attributes to be deleted by using
``__deletable__``::

   class Cls:
       x: int = 0
       y: int = 0
       other: int = 0

       __deletable__ = ['x', 'y']  # 'x' and 'y' can be deleted

   o = Cls()
   del o.x  # OK
   del o.y  # OK
   del o.other  # Error

You must initialize the ``__deletable__`` attribute in the class body,
using a list or a tuple expression with only string literal items that
refer to attributes. These are not valid::

   a = ['x', 'y']

   class Cls:
       x: int
       y: int

       __deletable__ = a  # Error: cannot use variable 'a'

   __deletable__ = ('a',)  # Error: not in a class body

Other properties
----------------

Instances of native classes don't usually have a ``__dict__`` attribute.
