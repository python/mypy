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

.. note::

   The support for structural subtyping is still experimental. Some features
   might be not yet implemented, mypy could pass unsafe code or reject
   working code.

There are two main type systems with respect to subtyping: nominal subtyping
and structural subtyping. The *nominal* subtyping is based on class hierarchy,
so that if class ``D`` inherits from class ``C``, then it is a subtype
of ``C``. This type system is primarily used in mypy since it allows
to produce clear and concise error messages, and since Python provides native
``isinstance()`` checks based on class hierarchy. The *structural* subtyping
however has its own advantages. In this system class ``D`` is a subtype
of class ``C`` if the former has all attributes of the latter with
compatible types. For example:

.. code-block:: python

   from typing import Sized

   def my_len(obj: Sized) -> int:
       ...

   class MyCollection:
       ...
       def __len__(self) -> int:
           return 42

   my_len(MyCollection())  # OK, since 'MyCollection' is a subtype of 'Sized'

This type system is a static equivalent of duck typing, well known by Python
programmers. Mypy provides an opt-in support for structural subtyping via
protocol classes described in this section.
See `PEP 544 <https://www.python.org/dev/peps/pep-0544/>`_ for
specification of protocols and structural subtyping in Python.

User defined protocols
**********************

To define a protocol class, one must inherit the special
``typing_extensions.Protocol`` class:

.. code-block:: python

   from typing import Iterable
   from typing_extensions import Protocol

   class SupportsClose(Protocol):
       def close(self) -> None:
          ...

   class Resource:  # Note, this class does not have 'SupportsClose' base.
       # some methods
       def close(self) -> None:
          self.resource.release()

   def close_all(things: Iterable[SupportsClose]) -> None:
       for thing in things:
           thing.close()

   close_all([Resource(), open('some/file')])  # This passes type check

.. note::

   The ``Protocol`` base class is currently provided in ``typing_extensions``
   package. Stub files are however allowed to use
   ``from typing import Protocol``. When structural subtyping is mature and
   `PEP 544 <https://www.python.org/dev/peps/pep-0544/>`_ is accepted,
   ``Protocol`` will be included in the ``typing`` module.

Defining subprotocols
*********************

Subprotocols are also supported. Existing protocols can be extended
and merged using multiple inheritance. For example:

.. code-block:: python

   # continuing from previous example

   class SizedLabeledResource(SupportsClose, Sized, Protocol):
       label: str

   class AdvancedResource(Resource):
       def __init__(self, label: str) -> None:
           self.label = label
       def __len__(self) -> int:
           ...

   resource = None  # type: SizedLabeledResource

   # some code

   resource = AdvancedResource('handle with care')  # OK

Note that inheriting from existing protocols does not automatically turn
a subclass into a protocol, it just creates a usual (non-protocol) ABC that
implements given protocols. The ``typing_extensions.Protocol`` base must always
be explicitly present:

.. code-block:: python

   class NewProtocol(Sized):  # This is NOT a protocol
       new_attr: int

   class Concrete:
      new_attr = None  # type: int
      def __len__(self) -> int:
          ...
   # Below is an error, since nominal subtyping is used by default
   x = Concrete()  # type: NewProtocol  # Error!

.. note::

   The `PEP 526 <https://www.python.org/dev/peps/pep-0526/>`_ variable
   annotations can be used to declare protocol attributes. However, protocols
   are also supported on Python 2.7 and Python 3.3+ with the help of type
   comments and properties, see
   `backwards compatibility in PEP 544 <https://www.python.org/dev/peps/pep-0544/#backwards-compatibility>`_.

Recursive protocols
*******************

Protocols can be recursive and mutually recursive. This could be useful for
declaring abstract recursive collections such as trees and linked lists:

.. code-block:: python

   from typing import TypeVar, Optional
   from typing_extensions import Protocol

   class TreeLike(Protocol):
       value: int
       @property
       def left(self) -> Optional['TreeLike']: ...
       @property
       def right(self) -> Optional['TreeLike']: ...

   class SimpleTree:
       def __init__(self, value: int) -> None:
           self.value = value
           self.left = self.right = None

   root = SimpleTree(0)  # type: TreeLike  # OK

Predefined protocols in ``typing`` module
*****************************************

Most ABCs in ``typing`` module are protocol classes describing
common Python protocols such as ``Iterator``, ``Awaitable``, ``Mapping``, etc.
(see `Python Docs <https://docs.python.org/3/library/typing.html>`_
for an exhaustive list)
For example, the following class will be considered a subtype of
``typing.Sized`` and ``typing.Iterable[int]``:

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

Using ``isinstance()`` with protocols
*************************************

To use a protocol class with ``isinstance()``, one needs to decorate it with
a special ``typing.runtime`` decorator. It will add support for basic runtime
structural checks:

.. code-block:: python

   from typing_extensions import Protocol, runtime

   @runtime
   class Portable(Protocol):
       handles: int

   class Mug:
       def __init__(self) -> None:
           self.handles = 1

   mug = Mug()
   if isinstance(mug, Portable):
      use(mug.handles)  # Works statically and at runtime.

.. note::
   ``isinstance()`` is with protocols not completely safe at runtime.
   For example, signatures of methods are not checked. The runtime
   implementation only checks the presence of all protocol members
   in object's MRO.

