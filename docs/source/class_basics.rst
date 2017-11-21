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

   Structural subtyping is experimental. Some things may not
   work as expected. Mypy may pass unsafe code or it can reject
   valid code.

Mypy supports two ways of deciding whether two classes are compatible
as types: nominal subtyping and structural subtyping. *Nominal*
subtyping is strictly based on the class hierarchy. If class ``D``
inherits class ``C``, it's also a subtype of ``C``. This form of
subtyping is used by default in mypy, since it's easy to understand
and produces clear and concise error messages, and since it matches
how the native ``isinstance()`` check works -- based on class
hierarchy. *Structural* subtyping can also be useful. Class ``D`` is
a structural subtype of class ``C`` if the former has all attributes
and methods of the latter, and with compatible types.

Structural subtyping can be seen as a static equivalent of duck
typing, which is well known to Python programmers. Mypy provides an
opt-in support for structural subtyping via protocol classes described
below.  See `PEP 544 <https://www.python.org/dev/peps/pep-0544/>`_ for
the detailed specification of protocols and structural subtyping in
Python.

Simple user-defined protocols
*****************************

You can define a protocol class by inheriting the special
``typing_extensions.Protocol`` class:

.. code-block:: python

   from typing import Iterable
   from typing_extensions import Protocol

   class SupportsClose(Protocol):
       def close(self) -> None:
          ...  # Explicit '...'

   class Resource:  # No SupportsClose base class!
       # ... some methods ...

       def close(self) -> None:
          self.resource.release()

   def close_all(items: Iterable[SupportsClose]) -> None:
       for item in items:
           item.close()

   close_all([Resource(), open('some/file')])  # Okay!

``Resource`` is a subtype of the ``SupportClose`` protocol since it defines
a compatible ``close`` method. Regular file objects returned by ``open()`` are
similarly compatible with the protocol, as they support ``close()``.

.. note::

   The ``Protocol`` base class is currently provided in the ``typing_extensions``
   package. Once structural subtyping is mature and
   `PEP 544 <https://www.python.org/dev/peps/pep-0544/>`_ has been accepted,
   ``Protocol`` will be included in the ``typing`` module. Several library
   types such as ``typing.Sized`` and ``typing.Iterable`` will also be changed
   into protocols. They are currently treated as regular ABCs by mypy.

Defining subprotocols
*********************

You can also define subprotocols. Existing protocols can be extended
and merged using multiple inheritance. Example:

.. code-block:: python

   # ... continuing from the previous example

   class SupportsRead(Protocol):
       def read(self, amount: int) -> bytes: ...

   class TaggedReadableResource(SupportsClose, SupportsRead, Protocol):
       label: str

   class AdvancedResource(Resource):
       def __init__(self, label: str) -> None:
           self.label = label

       def read(self, amount: int) -> bytes:
           # some implementation
           ...

   resource: TaggedReadableResource
   resource = AdvancedResource('handle with care')  # OK

Note that inheriting from an existing protocol does not automatically
turn the subclass into a protocol -- it just creates a regular
(non-protocol) ABC that implements the given protocol (or
protocols). The ``typing_extensions.Protocol`` base class must always
be explicitly present if you are defining a protocol:

.. code-block:: python

   class NewProtocol(SupportsClose):  # This is NOT a protocol
       new_attr: int

   class Concrete:
      new_attr: int = 0

      def close(self) -> None:
          ...

   # Error: nominal subtyping used by default
   x: NewProtocol = Concrete()  # Error!

.. note::

   You can use Python 3.6 variable annotations (`PEP 526
   <https://www.python.org/dev/peps/pep-0526/>`_)
   to declare protocol attributes.  On Python 2.7 and earlier Python 3
   versions you can use type comments and properties.

Recursive protocols
*******************

Protocols can be recursive (self-referential) and mutually
recursive. This is useful for declaring abstract recursive collections
such as trees and linked lists:

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
           self.left: Optional['SimpleTree'] = None
           self.right: Optional['SimpleTree'] = None

   root = SimpleTree(0)  # type: TreeLike  # OK

Using ``isinstance()`` with protocols
*************************************

You can use a protocol class with ``isinstance()`` if you decorate it
with the ``typing_extensions.runtime`` class decorator. The decorator
adds support for basic runtime structural checks:

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
      use(mug.handles)  # Works statically and at runtime

.. note::
   ``isinstance()`` with protocols is not completely safe at runtime.
   For example, signatures of methods are not checked. The runtime
   implementation only checks that all protocol members are defined.
