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

Mypy supports Python abstract base classes (ABCs). Abstract classes
have at least one abstract method or property that must be implemented
by a subclass. You can define abstract base classes using the
``abc.ABCMeta`` metaclass, and the ``abc.abstractmethod`` and
``abc.abstractproperty`` function decorators. Example:

.. code-block:: python

   from abc import ABCMeta, abstractmethod

   class A(metaclass=ABCMeta):
       @abstractmethod
       def foo(self, x: int) -> None: pass

       @abstractmethod
       def bar(self) -> str: pass

   class B(A):
       def foo(self, x: int) -> None: ...
       def bar(self) -> str:
           return 'x'

   a = A()  # Error: A is abstract
   b = B()  # OK

Note that mypy performs checking for unimplemented abstract methods
even if you omit the ``ABCMeta`` metaclass. This can be useful if the
metaclass would cause runtime metaclass conflicts.

A class can inherit any number of classes, both abstract and
concrete. As with normal overrides, a dynamically typed method can
implement a statically typed method defined in any base class,
including an abstract method defined in an abstract base class.

You can implement an abstract property using either a normal
property or an instance variable.

.. _protocol-types:

Protocols and structural subtyping
**********************************

Mypy supports two ways of deciding whether two classes are compatible
as types: nominal subtyping and structural subtyping. *Nominal*
subtyping is strictly based on the class hierarchy. If class ``D``
inherits class ``C``, it's also a subtype of ``C``, and instances of
``D`` can be used when ``C`` instances are expected. This form of
subtyping is used by default in mypy, since it's easy to understand
and produces clear and concise error messages, and since it matches
how the native ``isinstance()`` check works -- based on class
hierarchy. *Structural* subtyping can also be useful. Class ``D`` is
a structural subtype of class ``C`` if the former has all attributes
and methods of the latter, and with compatible types.

Structural subtyping can be seen as a static equivalent of duck
typing, which is well known to Python programmers. Mypy provides
support for structural subtyping via protocol classes described
below.  See `PEP 544 <https://www.python.org/dev/peps/pep-0544/>`_ for
the detailed specification of protocols and structural subtyping in
Python.

.. _predefined_protocols:

Predefined protocols
********************

The ``typing`` module defines various protocol classes that correspond
to common Python protocols, such as ``Iterable[T]``.  If a class
defines a suitable ``__iter__`` method, mypy understands that it
implements the iterable protocol and is compatible with ``Iterable[T]``.
For example, ``IntList`` below is iterable, over ``int`` values:

.. code-block:: python

   from typing import Iterator, Iterable, Optional

   class IntList:
       def __init__(self, value: int, next: Optional[IntList]) -> None:
           self.value = value
           self.next = next

       def __iter__(self) -> Iterator[int]:
           current = self
           while current:
               yield current.value
               current = current.next

   def print_numbered(items: Iterable[int]) -> None:
       for n, x in enumerate(items):
           print(n + 1, x)

   x = IntList(3, IntList(5, None))
   print_numbered(x)  # OK
   print_numbered([4, 5])  # Also OK

The subsections below introduce all built-in protocols defined in
``typing`` and the signatures of the corresponding methods you need to define
to implement each protocol (the signatures can be left out, as always, but mypy
won't type check unannotated methods).

Iteration protocols
...................

The iteration protocols are useful in many contexts. For example, they allow
iteration of objects in for loops.

``Iterable[T]``
---------------

The :ref:`example above <predefined_protocols>` has a simple implementation of an
``__iter__`` method.

.. code-block:: python

   def __iter__(self) -> Iterator[T]

``Iterator[T]``
---------------

.. code-block:: python

   def __next__(self) -> T
   def __iter__(self) -> Iterator[T]

Collection protocols
....................

Many of these are implemented by built-in container types such as
``list`` and ``dict``, and these are also useful for user-defined
collection objects.

``Sized``
---------

This is a type for objects that support ``len(x)``.

.. code-block:: python

   def __len__(self) -> int

``Container[T]``
----------------

This is a type for objects that support the ``in`` operator.

.. code-block:: python

   def __contains__(self, x: object) -> bool

``Collection[T]``
-----------------

.. code-block:: python

   def __len__(self) -> int
   def __iter__(self) -> Iterator[T]
   def __contains__(self, x: object) -> bool

One-off protocols
.................

These protocols are typically only useful with a single standard
library function or class.

``Reversible[T]``
-----------------

This is a type for objects that support ``reversed(x)``.

.. code-block:: python

   def __reversed__(self) -> Iterator[T]

``SupportsAbs[T]``
------------------

This is a type for objects that support ``abs(x)``. ``T`` is the type of
value returned by ``abs(x)``.

.. code-block:: python

   def __abs__(self) -> T

``SupportsBytes``
-----------------

This is a type for objects that support ``bytes(x)``.

.. code-block:: python

   def __bytes__(self) -> bytes

.. _supports-int-etc:

``SupportsComplex``
-------------------

This is a type for objects that support ``complex(x)``. Note that no arithmetic operations
are supported.

.. code-block:: python

   def __complex__(self) -> complex

``SupportsFloat``
-----------------

This is a type for objects that support ``float(x)``. Note that no arithmetic operations
are supported.

.. code-block:: python

   def __float__(self) -> float

``SupportsInt``
---------------

This is a type for objects that support ``int(x)``.  Note that no arithmetic operations
are supported.

.. code-block:: python

   def __int__(self) -> int

``SupportsRound[T]``
--------------------

This is a type for objects that support ``round(x)``.

.. code-block:: python

   def __round__(self) -> T

Async protocols
...............

These protocols can be useful in async code.

``Awaitable[T]``
----------------

.. code-block:: python

   def __await__(self) -> Generator[Any, None, T]

``AsyncIterable[T]``
--------------------

.. code-block:: python

   def __aiter__(self) -> AsyncIterator[T]

``AsyncIterator[T]``
--------------------

.. code-block:: python

   def __anext__(self) -> Awaitable[T]
   def __aiter__(self) -> AsyncIterator[T]

Context manager protocols
.........................

There are two protocols for context managers -- one for regular context
managers and one for async ones. These allow defining objects that can
be used in ``with`` and ``async with`` statements.

``ContextManager[T]``
---------------------

.. code-block:: python

   def __enter__(self) -> T
   def __exit__(self,
                exc_type: Optional[Type[BaseException]],
                exc_value: Optional[BaseException],
                traceback: Optional[TracebackType]) -> Optional[bool]

``AsyncContextManager[T]``
--------------------------

.. code-block:: python

   def __aenter__(self) -> Awaitable[T]
   def __aexit__(self,
                 exc_type: Optional[Type[BaseException]],
                 exc_value: Optional[BaseException],
                 traceback: Optional[TracebackType]) -> Awaitable[Optional[bool]]

Simple user-defined protocols
*****************************

You can define your own protocol class by inheriting the special
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
   ``Protocol`` will be included in the ``typing`` module.

Defining subprotocols and subclassing protocols
***********************************************

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
(non-protocol) class or ABC that implements the given protocol (or
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

You can also include default implementations of methods in
protocols. If you explicitly subclass these protocols you can inherit
these default implementations. Explicitly including a protocol as a
base class is also a way of documenting that your class implements a
particular protocol, and it forces mypy to verify that your class
implementation is actually compatible with the protocol.

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

``isinstance()`` also works with the :ref:`predefined protocols <predefined_protocols>`
in ``typing`` such as ``Iterable``.

.. note::
   ``isinstance()`` with protocols is not completely safe at runtime.
   For example, signatures of methods are not checked. The runtime
   implementation only checks that all protocol members are defined.


.. _metaclasses:

Metaclasses
***********

A `metaclass <https://docs.python.org/3/reference/datamodel.html#metaclasses>`_
is a class that describes the construction and behavior of other classes,
similarly to how classes describe the construction and behavior of objects.
The default metaclass is ``type``, but it's possible to use other metaclasses.
Metaclasses allows one to create "a different kind of class", such as Enums,
NamedTuples and singletons.

Mypy has some special understanding of ``ABCMeta`` and ``EnumMeta``.

Defining a metaclass
********************

.. code-block:: python

    class M(type):

    class A(metaclass=M):
        pass

In Python 2, the syntax for defining a metaclass different:

.. code-block:: python

    class A(object):
        __metaclass__ = M

Mypy also supports using the `six <https://pythonhosted.org/six/#six.with_metaclass>`_
library to define metaclass in a portable way:

.. code-block:: python

    import six

    class A(six.with_metaclass(M)):
        pass

    @six.add_metaclass(M)
    class C(object):
        pass

Metaclass usage example
***********************

Mypy supports the lookup of attributes in the metaclass:

.. code-block:: python

    from typing import Type, TypeVar, ClassVar
    T = TypeVar('T')

    class M(type):
        count: ClassVar[int] = 0

        def make(cls: Type[T]) -> T:
            M.count += 1
            return cls()

    class A(metaclass=M):
        pass

    a: A = A.make()  # make() is looked up at M; the result is an object of type A
    print(A.count)

    class B(A):
        pass

    b: B = B.make()  # metaclasses are inherited
    print(B.count + " objects were created")  # Error: Unsupported operand types for + ("int" and "str")

Gotchas and limitations of metaclass support
********************************************

Note that metaclasses pose some requirement on the inheritance structure,
so it's better not to combine metaclasses and class hierarchies:

.. code-block:: python

    class M1(type): pass
    class M2(type): pass

    class A1(metaclass=M1): pass
    class A2(metaclass=M2): pass

    class B1(A1, metaclass=M2): pass  # Mypy Error: Inconsistent metaclass structure for 'B1'
    # At runtime the above definition raises an exception
    # TypeError: metaclass conflict: the metaclass of a derived class must be a (non-strict) subclass of the metaclasses of all its bases

    # Same runtime error as in B1, but mypy does not catch it yet
    class B12(A1, A2): pass

* Mypy does not understand dynamically-computed metaclasses,
  such as ``class A(metaclass=f()): ...``
* Mypy does not and cannot understand arbitrary metaclass code.
* Mypy only recognizes classes are subclasses of `type` as potential metaclasses.
