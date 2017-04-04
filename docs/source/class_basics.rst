Class basics
============

Instance and class attributes
*****************************

Mypy type checker detects if you are trying to access a missing
attribute, which is a very common programming error. For this to work
correctly, instance and class attributes must be defined or
initialized within the class. Mypy infers the types of attributes:

.. code-block:: python

   class A:
       def __init__(self, x: int) -> None:
           self.x = x     # Attribute x of type int

   a = A(1)
   a.x = 2       # OK
   a.y = 3       # Error: A has no attribute y

This is a bit like each class having an implicitly defined
``__slots__`` attribute. This is only enforced during type
checking and not when your program is running.

You can declare types of variables in the class body explicitly using
a type comment:

.. code-block:: python

   class A:
       x = None  # type: List[int]  # Declare attribute x of type List[int]

   a = A()
   a.x = [1]     # OK

As in Python, a variable defined in the class body can used as a class
or an instance variable.

Similarly, you can give explicit types to instance variables defined
in a method:

.. code-block:: python

   class A:
       def __init__(self) -> None:
           self.x = []  # type: List[int]

       def f(self) -> None:
           self.y = 0  # type: Any

You can only define an instance variable within a method if you assign
to it explicitly using ``self``:

.. code-block:: python

   class A:
       def __init__(self) -> None:
           self.y = 1   # Define y
           a = self
           a.x = 1      # Error: x not defined

Overriding statically typed methods
***********************************

When overriding a statically typed method, mypy checks that the
override has a compatible signature:

.. code-block:: python

   class A:
       def f(self, x: int) -> None:
           ...

   class B(A):
       def f(self, x: str) -> None:   # Error: type of x incompatible
           ...

   class C(A):
       def f(self, x: int, y: int) -> None:  # Error: too many arguments
           ...

   class D(A):
       def f(self, x: int) -> None:   # OK
           ...

.. note::

   You can also vary return types **covariantly** in overriding. For
   example, you could override the return type ``object`` with a subtype
   such as ``int``.

You can also override a statically typed method with a dynamically
typed one. This allows dynamically typed code to override methods
defined in library classes without worrying about their type
signatures.

There is no runtime enforcement that the method override returns a
value that is compatible with the original return type, since
annotations have no effect at runtime:

.. code-block:: python

   class A:
       def inc(self, x: int) -> int:
           return x + 1

   class B(A):
       def inc(self, x):       # Override, dynamically typed
           return 'hello'

   b = B()
   print(b.inc(1))   # hello
   a = b # type: A
   print(a.inc(1))   # hello

Abstract base classes and multiple inheritance
**********************************************

Mypy uses Python abstract base classes for protocol types. There are
several built-in abstract base classes types (for example,
``Sequence``, ``Iterable`` and ``Iterator``). You can define abstract
base classes using the ``abc.ABCMeta`` metaclass and the
``abc.abstractmethod`` function decorator.

.. code-block:: python

   from abc import ABCMeta, abstractmethod
   import typing

   class A(metaclass=ABCMeta):
       @abstractmethod
       def foo(self, x: int) -> None: pass

       @abstractmethod
       def bar(self) -> str: pass

   class B(A):
       def foo(self, x: int) -> None: ...
       def bar(self) -> str:
           return 'x'

   a = A() # Error: A is abstract
   b = B() # OK

Unlike most Python code, abstract base classes are likely to play a
significant role in many complex mypy programs.

A class can inherit any number of classes, both abstract and
concrete. As with normal overrides, a dynamically typed method can
implement a statically typed abstract method defined in an abstract
base class.

.. _protocol-types:

Protocols and structural subtyping
**********************************

Mypy provides support for structural subtyping and protocol classes.
To define a protocol class, one must inherit the special ``typing.Protocol``
class:

.. code-block:: python

   from typing import Protocol

   class SupportsClose(Protocol):
       def close(self) -> None:
          ...

   class UnrelatedClass:
       # some methods
       def close(self) -> None:
          self.resource.release()

   def close_all(things: Sequence[SupportsClose]) -> None:
       for thing in things:
           thing.close()

   close_all([UnrelatedClass(), open('some/file')])  # This passes type check

Subprotocols are also supported. Inheriting from an existing protocol does
not automatically turn a subclass into a protocol, it just creates a usual
ABC. The ``typing.Protocol`` base must always be explicitly present.
Generic and recursive protocols are also supported:

.. code-block:: python

   from typing import Protocol, TypeVar

   T = TypeVar('T')
   class Linked(Protocol[T]):
       val: T
       next: 'Linked[T]'

   class L:
       val: int
       next: 'L'

   def last(seq: Linked[T]) -> T:
       ...

   result = last(L())  # The inferred type of 'result' is 'int'

See :ref:`generic-classes` for more details on generic classes.
The standard ABCs in ``typing`` module are protocols, so that the following
class will be considered a subtype of ``typing.Sized`` and
``typing.Iterable[int]``:

.. code-block:: python

   from typing import Iterator, Iterable

   class Bucket:
       ...
       def __len__(self) -> int:
           return 22
       def __iter__(self) -> Iterator[int]:
           yield 22

   def collect(items: Iterable[int]) -> int: ...
   result: int = collect(Bucket())  # Passes type check

To use a protocol class with ``isinstance()``, one needs to decorate it with
a special ``typing.runtime`` decorator. It will add support for basic runtime
structural checks:

.. code-block:: python

   from typing import Protocol, runtime

   @runtime
   class Portable(Protocol):
       handles: int

   class Mug:
       def __init__(self) -> None:
           self.handles = 1

   mug = Mug()
   if isinstance(mug, Portable):
      use(mug.handles)  # Works statically and at runtime.

See `PEP 544 <https://www.python.org/dev/peps/pep-0544/>`_ for
specification of structural subtyping in Python.

.. note::

   The support for structural subtyping is still experimental. Some features
   might be not yet implemented, mypy could pass unsafe code or reject
   working code.
