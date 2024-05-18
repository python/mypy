.. _protocol-types:

Protocols and structural subtyping
==================================

The Python type system supports two ways of deciding whether two objects are
compatible as types: nominal subtyping and structural subtyping.

*Nominal* subtyping is strictly based on the class hierarchy. If class ``Dog``
inherits class ``Animal``, it's a subtype of ``Animal``. Instances of ``Dog``
can be used when ``Animal`` instances are expected. This form of subtyping
is what Python's type system predominantly uses: it's easy to
understand and produces clear and concise error messages, and matches how the
native :py:func:`isinstance <isinstance>` check works -- based on class
hierarchy.

*Structural* subtyping is based on the operations that can be performed with an
object. Class ``Dog`` is a structural subtype of class ``Animal`` if the former
has all attributes and methods of the latter, and with compatible types.

Structural subtyping can be seen as a static equivalent of duck typing, which is
well known to Python programmers. See :pep:`544` for the detailed specification
of protocols and structural subtyping in Python.

.. _predefined_protocols:

Predefined protocols
********************

The :py:mod:`typing` module defines various protocol classes that correspond
to common Python protocols, such as :py:class:`Iterable[T] <typing.Iterable>`. If a class
defines a suitable :py:meth:`__iter__ <object.__iter__>` method, mypy understands that it
implements the iterable protocol and is compatible with :py:class:`Iterable[T] <typing.Iterable>`.
For example, ``IntList`` below is iterable, over ``int`` values:

.. code-block:: python

   from typing import Iterator, Iterable, Optional

   class IntList:
       def __init__(self, value: int, next: Optional['IntList']) -> None:
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

:ref:`predefined_protocols_reference` lists all protocols defined in
:py:mod:`typing` and the signatures of the corresponding methods you need to define
to implement each protocol.

Simple user-defined protocols
*****************************

You can define your own protocol class by inheriting the special ``Protocol``
class:

.. code-block:: python

   from typing import Iterable, Protocol

   class SupportsClose(Protocol):
       # Empty method body (explicit '...')
       def close(self) -> None: ...

   class Resource:  # No SupportsClose base class!

       def close(self) -> None:
          self.resource.release()

       # ... other methods ...

   def close_all(items: Iterable[SupportsClose]) -> None:
       for item in items:
           item.close()

   close_all([Resource(), open('some/file')])  # OK

``Resource`` is a subtype of the ``SupportsClose`` protocol since it defines
a compatible ``close`` method. Regular file objects returned by :py:func:`open` are
similarly compatible with the protocol, as they support ``close()``.

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
protocols). The ``Protocol`` base class must always be explicitly
present if you are defining a protocol:

.. code-block:: python

   class NotAProtocol(SupportsClose):  # This is NOT a protocol
       new_attr: int

   class Concrete:
      new_attr: int = 0

      def close(self) -> None:
          ...

   # Error: nominal subtyping used by default
   x: NotAProtocol = Concrete()  # Error!

You can also include default implementations of methods in
protocols. If you explicitly subclass these protocols you can inherit
these default implementations.

Explicitly including a protocol as a
base class is also a way of documenting that your class implements a
particular protocol, and it forces mypy to verify that your class
implementation is actually compatible with the protocol. In particular,
omitting a value for an attribute or a method body will make it implicitly
abstract:

.. code-block:: python

   class SomeProto(Protocol):
       attr: int  # Note, no right hand side
       def method(self) -> str: ...  # Literally just ... here

   class ExplicitSubclass(SomeProto):
       pass

   ExplicitSubclass()  # error: Cannot instantiate abstract class 'ExplicitSubclass'
                       # with abstract attributes 'attr' and 'method'

Similarly, explicitly assigning to a protocol instance can be a way to ask the
type checker to verify that your class implements a protocol:

.. code-block:: python

   _proto: SomeProto = cast(ExplicitSubclass, None)

Invariance of protocol attributes
*********************************

A common issue with protocols is that protocol attributes are invariant.
For example:

.. code-block:: python

   class Box(Protocol):
         content: object

   class IntBox:
         content: int

   def takes_box(box: Box) -> None: ...

   takes_box(IntBox())  # error: Argument 1 to "takes_box" has incompatible type "IntBox"; expected "Box"
                        # note:  Following member(s) of "IntBox" have conflicts:
                        # note:      content: expected "object", got "int"

This is because ``Box`` defines ``content`` as a mutable attribute.
Here's why this is problematic:

.. code-block:: python

   def takes_box_evil(box: Box) -> None:
       box.content = "asdf"  # This is bad, since box.content is supposed to be an object

   my_int_box = IntBox()
   takes_box_evil(my_int_box)
   my_int_box.content + 1  # Oops, TypeError!

This can be fixed by declaring ``content`` to be read-only in the ``Box``
protocol using ``@property``:

.. code-block:: python

   class Box(Protocol):
       @property
       def content(self) -> object: ...

   class IntBox:
       content: int

   def takes_box(box: Box) -> None: ...

   takes_box(IntBox(42))  # OK

Recursive protocols
*******************

Protocols can be recursive (self-referential) and mutually
recursive. This is useful for declaring abstract recursive collections
such as trees and linked lists:

.. code-block:: python

   from typing import TypeVar, Optional, Protocol

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

   root: TreeLike = SimpleTree(0)  # OK

Using isinstance() with protocols
*********************************

You can use a protocol class with :py:func:`isinstance` if you decorate it
with the ``@runtime_checkable`` class decorator. The decorator adds
rudimentary support for runtime structural checks:

.. code-block:: python

   from typing import Protocol, runtime_checkable

   @runtime_checkable
   class Portable(Protocol):
       handles: int

   class Mug:
       def __init__(self) -> None:
           self.handles = 1

   def use(handles: int) -> None: ...

   mug = Mug()
   if isinstance(mug, Portable):  # Works at runtime!
      use(mug.handles)

:py:func:`isinstance` also works with the :ref:`predefined protocols <predefined_protocols>`
in :py:mod:`typing` such as :py:class:`~typing.Iterable`.

.. warning::
   :py:func:`isinstance` with protocols is not completely safe at runtime.
   For example, signatures of methods are not checked. The runtime
   implementation only checks that all protocol members exist,
   not that they have the correct type. :py:func:`issubclass` with protocols
   will only check for the existence of methods.

.. note::
   :py:func:`isinstance` with protocols can also be surprisingly slow.
   In many cases, you're better served by using :py:func:`hasattr` to
   check for the presence of attributes.

.. _callback_protocols:

Callback protocols
******************

Protocols can be used to define flexible callback types that are hard
(or even impossible) to express using the :py:data:`Callable[...] <typing.Callable>` syntax, such as variadic,
overloaded, and complex generic callbacks. They are defined with a special :py:meth:`__call__ <object.__call__>`
member:

.. code-block:: python

   from typing import Optional, Iterable, Protocol

   class Combiner(Protocol):
       def __call__(self, *vals: bytes, maxlen: Optional[int] = None) -> list[bytes]: ...

   def batch_proc(data: Iterable[bytes], cb_results: Combiner) -> bytes:
       for item in data:
           ...

   def good_cb(*vals: bytes, maxlen: Optional[int] = None) -> list[bytes]:
       ...
   def bad_cb(*vals: bytes, maxitems: Optional[int]) -> list[bytes]:
       ...

   batch_proc([], good_cb)  # OK
   batch_proc([], bad_cb)   # Error! Argument 2 has incompatible type because of
                            # different name and kind in the callback

Callback protocols and :py:data:`~typing.Callable` types can be used mostly interchangeably.
Argument names in :py:meth:`__call__ <object.__call__>` methods must be identical, unless
a double underscore prefix is used. For example:

.. code-block:: python

   from typing import Callable, Protocol, TypeVar

   T = TypeVar('T')

   class Copy(Protocol):
       def __call__(self, __origin: T) -> T: ...

   copy_a: Callable[[T], T]
   copy_b: Copy

   copy_a = copy_b  # OK
   copy_b = copy_a  # Also OK

.. _predefined_protocols_reference:

Predefined protocol reference
*****************************

Iteration protocols
...................

The iteration protocols are useful in many contexts. For example, they allow
iteration of objects in for loops.

Iterable[T]
-----------

The :ref:`example above <predefined_protocols>` has a simple implementation of an
:py:meth:`__iter__ <object.__iter__>` method.

.. code-block:: python

   def __iter__(self) -> Iterator[T]

See also :py:class:`~typing.Iterable`.

Iterator[T]
-----------

.. code-block:: python

   def __next__(self) -> T
   def __iter__(self) -> Iterator[T]

See also :py:class:`~typing.Iterator`.

Collection protocols
....................

Many of these are implemented by built-in container types such as
:py:class:`list` and :py:class:`dict`, and these are also useful for user-defined
collection objects.

Sized
-----

This is a type for objects that support :py:func:`len(x) <len>`.

.. code-block:: python

   def __len__(self) -> int

See also :py:class:`~typing.Sized`.

Container[T]
------------

This is a type for objects that support the ``in`` operator.

.. code-block:: python

   def __contains__(self, x: object) -> bool

See also :py:class:`~typing.Container`.

Collection[T]
-------------

.. code-block:: python

   def __len__(self) -> int
   def __iter__(self) -> Iterator[T]
   def __contains__(self, x: object) -> bool

See also :py:class:`~typing.Collection`.

One-off protocols
.................

These protocols are typically only useful with a single standard
library function or class.

Reversible[T]
-------------

This is a type for objects that support :py:func:`reversed(x) <reversed>`.

.. code-block:: python

   def __reversed__(self) -> Iterator[T]

See also :py:class:`~typing.Reversible`.

SupportsAbs[T]
--------------

This is a type for objects that support :py:func:`abs(x) <abs>`. ``T`` is the type of
value returned by :py:func:`abs(x) <abs>`.

.. code-block:: python

   def __abs__(self) -> T

See also :py:class:`~typing.SupportsAbs`.

SupportsBytes
-------------

This is a type for objects that support :py:class:`bytes(x) <bytes>`.

.. code-block:: python

   def __bytes__(self) -> bytes

See also :py:class:`~typing.SupportsBytes`.

.. _supports-int-etc:

SupportsComplex
---------------

This is a type for objects that support :py:class:`complex(x) <complex>`. Note that no arithmetic operations
are supported.

.. code-block:: python

   def __complex__(self) -> complex

See also :py:class:`~typing.SupportsComplex`.

SupportsFloat
-------------

This is a type for objects that support :py:class:`float(x) <float>`. Note that no arithmetic operations
are supported.

.. code-block:: python

   def __float__(self) -> float

See also :py:class:`~typing.SupportsFloat`.

SupportsInt
-----------

This is a type for objects that support :py:class:`int(x) <int>`. Note that no arithmetic operations
are supported.

.. code-block:: python

   def __int__(self) -> int

See also :py:class:`~typing.SupportsInt`.

SupportsRound[T]
----------------

This is a type for objects that support :py:func:`round(x) <round>`.

.. code-block:: python

   def __round__(self) -> T

See also :py:class:`~typing.SupportsRound`.

Async protocols
...............

These protocols can be useful in async code. See :ref:`async-and-await`
for more information.

Awaitable[T]
------------

.. code-block:: python

   def __await__(self) -> Generator[Any, None, T]

See also :py:class:`~typing.Awaitable`.

AsyncIterable[T]
----------------

.. code-block:: python

   def __aiter__(self) -> AsyncIterator[T]

See also :py:class:`~typing.AsyncIterable`.

AsyncIterator[T]
----------------

.. code-block:: python

   def __anext__(self) -> Awaitable[T]
   def __aiter__(self) -> AsyncIterator[T]

See also :py:class:`~typing.AsyncIterator`.

Context manager protocols
.........................

There are two protocols for context managers -- one for regular context
managers and one for async ones. These allow defining objects that can
be used in ``with`` and ``async with`` statements.

ContextManager[T]
-----------------

.. code-block:: python

   def __enter__(self) -> T
   def __exit__(self,
                exc_type: Optional[Type[BaseException]],
                exc_value: Optional[BaseException],
                traceback: Optional[TracebackType]) -> Optional[bool]

See also :py:class:`~typing.ContextManager`.

AsyncContextManager[T]
----------------------

.. code-block:: python

   def __aenter__(self) -> Awaitable[T]
   def __aexit__(self,
                 exc_type: Optional[Type[BaseException]],
                 exc_value: Optional[BaseException],
                 traceback: Optional[TracebackType]) -> Awaitable[Optional[bool]]

See also :py:class:`~typing.AsyncContextManager`.
