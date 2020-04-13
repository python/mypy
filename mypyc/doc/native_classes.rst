Native classes
==============

Classes in compiled modules are *native classes* by default (some
exceptions are discussed below). Native classes are compiled to C
extension classes, which have some important differences from normal
Python classes. Native classes are similar to built-in types such as
``int``, ``str``, and ``list``.

Immutable namespaces
--------------------

The type object namespace of native classes is mostly immutable (class
variables can be assigned to)::

    class Cls:
        def method1(self) -> None:
            print("method1")

        def method2(self) -> None:
            print("method2")

    Cls.method1 = Cls.method2  # Error!
    Cls.new_method = Cls.method2  # Error!

Only attributes defined within class definition can be assigned to
(similar to ``__slots__``)::

    class Cls:
        x: int

        def __init__(self, y: int) -> None:
            self.x = 0
            self.y = y

        def method(self) -> None:
            self.z = "x"

    o = Cls()
    print(o.x, o.y)  # OK
    o.z = "y"  # OK
    o.extra = 3  # Error: no attribute "extra"

Inheritance
-----------

Only single inheritance is supported (except for traits). Most
non-native classes can't be used as base classes.

By default, a non-native class can't inherit a native class, and you
can't inherit from a native class outside the compilation unit that
defines the class. You can enable these through
``mypy_extensions.mypyc_attr``::

    from mypy_extensions import mypyc_attr

    @mypyc_attr(allow_interpreted_subclasses=True)
    class Base:
        ...

If you override a method outside the original compilation unit or in a
non-native subclass, calling the method will be slower, since it won't
use the native calling convention.

You need to install ``mypy-extensions`` to use ``@mypyc_attr``:

.. code-block:: text

    pip install --upgrade mypy-extensions

Class variables
---------------

Class variables much be explicitly declared using ``attr: ClassVar``
or ``attr: ClassVar[<type>]``. You can't assign to a class variable
through an instance. Example::

    from typing import ClassVar

    class Cls:
        cv: ClassVar = 0

    Cls.cv = 2  # OK
    o = Cls()
    print(o.cv)  # OK (2)
    o.cv = 3  # Error!

Generic native classes
----------------------

Native classes can be generic. Type variables are *erased* at runtime,
and instances don't keep track of type variable values.

Generated code thus can't check the values type variables when performing
runtime type checks, and these are delayed to when reading a value with
a type variable type::

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
behavior is too dynamic. You can use these metaclasses:

* ``abc.ABCMeta``
* ``typing.GenericMeta`` (used by ``typing.Generic``)

.. note::

   If a class definition uses an unsupported metaclass, *mypyc
   compiles the class into a regular Python class*.

Class decorators
----------------

Similar to metaclasses, most class decorators aren't supported with
native classes, as they are usually too dynamic. These class
decorators have special support:

* ``mypy_extensions.trait`` (for defining trait types)
* ``mypy_extensions.mypyc_attr`` (see below)
* ``dataclasses.dataclass``

Dataclasses have partial native support, and they aren't as efficient
as pure native classes.

.. note::

   If a class definition uses an unsupported class decorator, *mypyc
   compiles the class into a regular Python class*.

Other properties
----------------

Instances of native classes don't usually have a ``__dict__`` attribute.
