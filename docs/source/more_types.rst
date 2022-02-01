More types
==========

This section introduces a few additional kinds of types, including :py:data:`~typing.NoReturn`,
:py:func:`NewType <typing.NewType>`, ``TypedDict``, and types for async code. It also discusses
how to give functions more precise types using overloads. All of these are only
situationally useful, so feel free to skip this section and come back when you
have a need for some of them.

Here's a quick summary of what's covered here:

* :py:data:`~typing.NoReturn` lets you tell mypy that a function never returns normally.

* :py:func:`NewType <typing.NewType>` lets you define a variant of a type that is treated as a
  separate type by mypy but is identical to the original type at runtime.
  For example, you can have ``UserId`` as a variant of ``int`` that is
  just an ``int`` at runtime.

* :py:func:`@overload <typing.overload>` lets you define a function that can accept multiple distinct
  signatures. This is useful if you need to encode a relationship between the
  arguments and the return type that would be difficult to express normally.

* ``TypedDict`` lets you give precise types for dictionaries that represent
  objects with a fixed schema, such as ``{'id': 1, 'items': ['x']}``.

* Async types let you type check programs using ``async`` and ``await``.

.. _noreturn:

The NoReturn type
*****************

Mypy provides support for functions that never return. For
example, a function that unconditionally raises an exception:

.. code-block:: python

   from typing import NoReturn

   def stop() -> NoReturn:
       raise Exception('no way')

Mypy will ensure that functions annotated as returning :py:data:`~typing.NoReturn`
truly never return, either implicitly or explicitly. Mypy will also
recognize that the code after calls to such functions is unreachable
and will behave accordingly:

.. code-block:: python

   def f(x: int) -> int:
       if x == 0:
           return x
       stop()
       return 'whatever works'  # No error in an unreachable block

In earlier Python versions you need to install ``typing_extensions`` using
pip to use :py:data:`~typing.NoReturn` in your code. Python 3 command line:

.. code-block:: text

    python3 -m pip install --upgrade typing-extensions

This works for Python 2:

.. code-block:: text

    pip install --upgrade typing-extensions

.. _newtypes:

NewTypes
********

There are situations where you may want to avoid programming errors by
creating simple derived classes that are only used to distinguish
certain values from base class instances. Example:

.. code-block:: python

    class UserId(int):
        pass

    def get_by_user_id(user_id: UserId):
        ...

However, this approach introduces some runtime overhead. To avoid this, the typing
module provides a helper object :py:func:`NewType <typing.NewType>` that creates simple unique types with
almost zero runtime overhead. Mypy will treat the statement
``Derived = NewType('Derived', Base)`` as being roughly equivalent to the following
definition:

.. code-block:: python

    class Derived(Base):
        def __init__(self, _x: Base) -> None:
            ...

However, at runtime, ``NewType('Derived', Base)`` will return a dummy callable that
simply returns its argument:

.. code-block:: python

    def Derived(_x):
        return _x

Mypy will require explicit casts from ``int`` where ``UserId`` is expected, while
implicitly casting from ``UserId`` where ``int`` is expected. Examples:

.. code-block:: python

    from typing import NewType

    UserId = NewType('UserId', int)

    def name_by_id(user_id: UserId) -> str:
        ...

    UserId('user')          # Fails type check

    name_by_id(42)          # Fails type check
    name_by_id(UserId(42))  # OK

    num = UserId(5) + 1     # type: int

:py:func:`NewType <typing.NewType>` accepts exactly two arguments. The first argument must be a string literal
containing the name of the new type and must equal the name of the variable to which the new
type is assigned. The second argument must be a properly subclassable class, i.e.,
not a type construct like :py:data:`~typing.Union`, etc.

The callable returned by :py:func:`NewType <typing.NewType>` accepts only one argument; this is equivalent to
supporting only one constructor accepting an instance of the base class (see above).
Example:

.. code-block:: python

    from typing import NewType

    class PacketId:
        def __init__(self, major: int, minor: int) -> None:
            self._major = major
            self._minor = minor

    TcpPacketId = NewType('TcpPacketId', PacketId)

    packet = PacketId(100, 100)
    tcp_packet = TcpPacketId(packet)  # OK

    tcp_packet = TcpPacketId(127, 0)  # Fails in type checker and at runtime

You cannot use :py:func:`isinstance` or :py:func:`issubclass` on the object returned by
:py:func:`~typing.NewType`, nor can you subclass an object returned by :py:func:`~typing.NewType`.

.. note::

    Unlike type aliases, :py:func:`NewType <typing.NewType>` will create an entirely new and
    unique type when used. The intended purpose of :py:func:`NewType <typing.NewType>` is to help you
    detect cases where you accidentally mixed together the old base type and the
    new derived type.

    For example, the following will successfully typecheck when using type
    aliases:

    .. code-block:: python

        UserId = int

        def name_by_id(user_id: UserId) -> str:
            ...

        name_by_id(3)  # ints and UserId are synonymous

    But a similar example using :py:func:`NewType <typing.NewType>` will not typecheck:

    .. code-block:: python

        from typing import NewType

        UserId = NewType('UserId', int)

        def name_by_id(user_id: UserId) -> str:
            ...

        name_by_id(3)  # int is not the same as UserId

.. _function-overloading:

Function overloading
********************

Sometimes the arguments and types in a function depend on each other
in ways that can't be captured with a :py:data:`~typing.Union`. For example, suppose
we want to write a function that can accept x-y coordinates. If we pass
in just a single x-y coordinate, we return a ``ClickEvent`` object. However,
if we pass in two x-y coordinates, we return a ``DragEvent`` object.

Our first attempt at writing this function might look like this:

.. code-block:: python

    from typing import Union, Optional

    def mouse_event(x1: int,
                    y1: int,
                    x2: Optional[int] = None,
                    y2: Optional[int] = None) -> Union[ClickEvent, DragEvent]:
        if x2 is None and y2 is None:
            return ClickEvent(x1, y1)
        elif x2 is not None and y2 is not None:
            return DragEvent(x1, y1, x2, y2)
        else:
            raise TypeError("Bad arguments")

While this function signature works, it's too loose: it implies ``mouse_event``
could return either object regardless of the number of arguments
we pass in. It also does not prohibit a caller from passing in the wrong
number of ints: mypy would treat calls like ``mouse_event(1, 2, 20)`` as being
valid, for example.

We can do better by using :pep:`overloading <484#function-method-overloading>`
which lets us give the same function multiple type annotations (signatures)
to more accurately describe the function's behavior:

.. code-block:: python

    from typing import Union, overload

    # Overload *variants* for 'mouse_event'.
    # These variants give extra information to the type checker.
    # They are ignored at runtime.

    @overload
    def mouse_event(x1: int, y1: int) -> ClickEvent: ...
    @overload
    def mouse_event(x1: int, y1: int, x2: int, y2: int) -> DragEvent: ...

    # The actual *implementation* of 'mouse_event'.
    # The implementation contains the actual runtime logic.
    #
    # It may or may not have type hints. If it does, mypy
    # will check the body of the implementation against the
    # type hints.
    #
    # Mypy will also check and make sure the signature is
    # consistent with the provided variants.

    def mouse_event(x1: int,
                    y1: int,
                    x2: Optional[int] = None,
                    y2: Optional[int] = None) -> Union[ClickEvent, DragEvent]:
        if x2 is None and y2 is None:
            return ClickEvent(x1, y1)
        elif x2 is not None and y2 is not None:
            return DragEvent(x1, y1, x2, y2)
        else:
            raise TypeError("Bad arguments")

This allows mypy to understand calls to ``mouse_event`` much more precisely.
For example, mypy will understand that ``mouse_event(5, 25)`` will
always have a return type of ``ClickEvent`` and will report errors for
calls like ``mouse_event(5, 25, 2)``.

As another example, suppose we want to write a custom container class that
implements the :py:meth:`__getitem__ <object.__getitem__>` method (``[]`` bracket indexing). If this
method receives an integer we return a single item. If it receives a
``slice``, we return a :py:class:`~typing.Sequence` of items.

We can precisely encode this relationship between the argument and the
return type by using overloads like so:

.. code-block:: python

    from typing import Sequence, TypeVar, Union, overload

    T = TypeVar('T')

    class MyList(Sequence[T]):
        @overload
        def __getitem__(self, index: int) -> T: ...

        @overload
        def __getitem__(self, index: slice) -> Sequence[T]: ...

        def __getitem__(self, index: Union[int, slice]) -> Union[T, Sequence[T]]:
            if isinstance(index, int):
                # Return a T here
            elif isinstance(index, slice):
                # Return a sequence of Ts here
            else:
                raise TypeError(...)

.. note::

   If you just need to constrain a type variable to certain types or
   subtypes, you can use a :ref:`value restriction
   <type-variable-value-restriction>`.

The default values of a function's arguments don't affect its signature -- only
the absence or presence of a default value does. So in order to reduce
redundancy, it's possible to replace default values in overload definitions with
``...`` as a placeholder:

.. code-block:: python

    from typing import overload

    class M: ...

    @overload
    def get_model(model_or_pk: M, flag: bool = ...) -> M: ...
    @overload
    def get_model(model_or_pk: int, flag: bool = ...) -> M | None: ...

    def get_model(model_or_pk: int | M, flag: bool = True) -> M | None:
        ...


Runtime behavior
----------------

An overloaded function must consist of two or more overload *variants*
followed by an *implementation*. The variants and the implementations
must be adjacent in the code: think of them as one indivisible unit.

The variant bodies must all be empty; only the implementation is allowed
to contain code. This is because at runtime, the variants are completely
ignored: they're overridden by the final implementation function.

This means that an overloaded function is still an ordinary Python
function! There is no automatic dispatch handling and you must manually
handle the different types in the implementation (e.g. by using
``if`` statements and :py:func:`isinstance <isinstance>` checks).

If you are adding an overload within a stub file, the implementation
function should be omitted: stubs do not contain runtime logic.

.. note::

   While we can leave the variant body empty using the ``pass`` keyword,
   the more common convention is to instead use the ellipsis (``...``) literal.

Type checking calls to overloads
--------------------------------

When you call an overloaded function, mypy will infer the correct return
type by picking the best matching variant, after taking into consideration
both the argument types and arity. However, a call is never type
checked against the implementation. This is why mypy will report calls
like ``mouse_event(5, 25, 3)`` as being invalid even though it matches the
implementation signature.

If there are multiple equally good matching variants, mypy will select
the variant that was defined first. For example, consider the following
program:

.. code-block:: python

    # For Python 3.8 and below you must use `typing.List` instead of `list`. e.g.
    # from typing import List
    from typing import overload

    @overload
    def summarize(data: list[int]) -> float: ...

    @overload
    def summarize(data: list[str]) -> str: ...

    def summarize(data):
        if not data:
            return 0.0
        elif isinstance(data[0], int):
            # Do int specific code
        else:
            # Do str-specific code

    # What is the type of 'output'? float or str?
    output = summarize([])

The ``summarize([])`` call matches both variants: an empty list could
be either a ``list[int]`` or a ``list[str]``. In this case, mypy
will break the tie by picking the first matching variant: ``output``
will have an inferred type of ``float``. The implementor is responsible
for making sure ``summarize`` breaks ties in the same way at runtime.

However, there are two exceptions to the "pick the first match" rule.
First, if multiple variants match due to an argument being of type
``Any``, mypy will make the inferred type also be ``Any``:

.. code-block:: python

    dynamic_var: Any = some_dynamic_function()

    # output2 is of type 'Any'
    output2 = summarize(dynamic_var)

Second, if multiple variants match due to one or more of the arguments
being a union, mypy will make the inferred type be the union of the
matching variant returns:

.. code-block:: python

    some_list: Union[list[int], list[str]]

    # output3 is of type 'Union[float, str]'
    output3 = summarize(some_list)

.. note::

   Due to the "pick the first match" rule, changing the order of your
   overload variants can change how mypy type checks your program.

   To minimize potential issues, we recommend that you:

   1. Make sure your overload variants are listed in the same order as
      the runtime checks (e.g. :py:func:`isinstance <isinstance>` checks) in your implementation.
   2. Order your variants and runtime checks from most to least specific.
      (See the following section for an example).

Type checking the variants
--------------------------

Mypy will perform several checks on your overload variant definitions
to ensure they behave as expected. First, mypy will check and make sure
that no overload variant is shadowing a subsequent one. For example,
consider the following function which adds together two ``Expression``
objects, and contains a special-case to handle receiving two ``Literal``
types:

.. code-block:: python

    from typing import overload, Union

    class Expression:
        # ...snip...

    class Literal(Expression):
        # ...snip...

    # Warning -- the first overload variant shadows the second!

    @overload
    def add(left: Expression, right: Expression) -> Expression: ...

    @overload
    def add(left: Literal, right: Literal) -> Literal: ...

    def add(left: Expression, right: Expression) -> Expression:
        # ...snip...

While this code snippet is technically type-safe, it does contain an
anti-pattern: the second variant will never be selected! If we try calling
``add(Literal(3), Literal(4))``, mypy will always pick the first variant
and evaluate the function call to be of type ``Expression``, not ``Literal``.
This is because ``Literal`` is a subtype of ``Expression``, which means
the "pick the first match" rule will always halt after considering the
first overload.

Because having an overload variant that can never be matched is almost
certainly a mistake, mypy will report an error. To fix the error, we can
either 1) delete the second overload or 2) swap the order of the overloads:

.. code-block:: python

    # Everything is ok now -- the variants are correctly ordered
    # from most to least specific.

    @overload
    def add(left: Literal, right: Literal) -> Literal: ...

    @overload
    def add(left: Expression, right: Expression) -> Expression: ...

    def add(left: Expression, right: Expression) -> Expression:
        # ...snip...

Mypy will also type check the different variants and flag any overloads
that have inherently unsafely overlapping variants. For example, consider
the following unsafe overload definition:

.. code-block:: python

    from typing import overload, Union

    @overload
    def unsafe_func(x: int) -> int: ...

    @overload
    def unsafe_func(x: object) -> str: ...

    def unsafe_func(x: object) -> Union[int, str]:
        if isinstance(x, int):
            return 42
        else:
            return "some string"

On the surface, this function definition appears to be fine. However, it will
result in a discrepancy between the inferred type and the actual runtime type
when we try using it like so:

.. code-block:: python

    some_obj: object = 42
    unsafe_func(some_obj) + " danger danger"  # Type checks, yet crashes at runtime!

Since ``some_obj`` is of type :py:class:`object`, mypy will decide that ``unsafe_func``
must return something of type ``str`` and concludes the above will type check.
But in reality, ``unsafe_func`` will return an int, causing the code to crash
at runtime!

To prevent these kinds of issues, mypy will detect and prohibit inherently unsafely
overlapping overloads on a best-effort basis. Two variants are considered unsafely
overlapping when both of the following are true:

1. All of the arguments of the first variant are compatible with the second.
2. The return type of the first variant is *not* compatible with (e.g. is not a
   subtype of) the second.

So in this example, the ``int`` argument in the first variant is a subtype of
the ``object`` argument in the second, yet the ``int`` return type is not a subtype of
``str``. Both conditions are true, so mypy will correctly flag ``unsafe_func`` as
being unsafe.

However, mypy will not detect *all* unsafe uses of overloads. For example,
suppose we modify the above snippet so it calls ``summarize`` instead of
``unsafe_func``:

.. code-block:: python

    some_list: list[str] = []
    summarize(some_list) + "danger danger"  # Type safe, yet crashes at runtime!

We run into a similar issue here. This program type checks if we look just at the
annotations on the overloads. But since ``summarize(...)`` is designed to be biased
towards returning a float when it receives an empty list, this program will actually
crash during runtime.

The reason mypy does not flag definitions like ``summarize`` as being potentially
unsafe is because if it did, it would be extremely difficult to write a safe
overload. For example, suppose we define an overload with two variants that accept
types ``A`` and ``B`` respectively. Even if those two types were completely unrelated,
the user could still potentially trigger a runtime error similar to the ones above by
passing in a value of some third type ``C`` that inherits from both ``A`` and ``B``.

Thankfully, these types of situations are relatively rare. What this does mean,
however, is that you should exercise caution when designing or using an overloaded
function that can potentially receive values that are an instance of two seemingly
unrelated types.


Type checking the implementation
--------------------------------

The body of an implementation is type-checked against the
type hints provided on the implementation. For example, in the
``MyList`` example up above, the code in the body is checked with
argument list ``index: Union[int, slice]`` and a return type of
``Union[T, Sequence[T]]``. If there are no annotations on the
implementation, then the body is not type checked. If you want to
force mypy to check the body anyways, use the :option:`--check-untyped-defs <mypy --check-untyped-defs>`
flag (:ref:`more details here <untyped-definitions-and-calls>`).

The variants must also also be compatible with the implementation
type hints. In the ``MyList`` example, mypy will check that the
parameter type ``int`` and the return type ``T`` are compatible with
``Union[int, slice]`` and ``Union[T, Sequence]`` for the
first variant. For the second variant it verifies the parameter
type ``slice`` and the return type ``Sequence[T]`` are compatible
with ``Union[int, slice]`` and ``Union[T, Sequence]``.

.. note::

   The overload semantics documented above are new as of mypy 0.620.

   Previously, mypy used to perform type erasure on all overload variants. For
   example, the ``summarize`` example from the previous section used to be
   illegal because ``list[str]`` and ``list[int]`` both erased to just ``list[Any]``.
   This restriction was removed in mypy 0.620.

   Mypy also previously used to select the best matching variant using a different
   algorithm. If this algorithm failed to find a match, it would default to returning
   ``Any``. The new algorithm uses the "pick the first match" rule and will fall back
   to returning ``Any`` only if the input arguments also contain ``Any``.


.. _advanced_self:

Advanced uses of self-types
***************************

Normally, mypy doesn't require annotations for the first arguments of instance and
class methods. However, they may be needed to have more precise static typing
for certain programming patterns.

Restricted methods in generic classes
-------------------------------------

In generic classes some methods may be allowed to be called only
for certain values of type arguments:

.. code-block:: python

   T = TypeVar('T')

   class Tag(Generic[T]):
       item: T
       def uppercase_item(self: Tag[str]) -> str:
           return self.item.upper()

   def label(ti: Tag[int], ts: Tag[str]) -> None:
       ti.uppercase_item()  # E: Invalid self argument "Tag[int]" to attribute function
                            # "uppercase_item" with type "Callable[[Tag[str]], str]"
       ts.uppercase_item()  # This is OK

This pattern also allows matching on nested types in situations where the type
argument is itself generic:

.. code-block:: python

  T = TypeVar('T', covariant=True)
  S = TypeVar('S')

   class Storage(Generic[T]):
       def __init__(self, content: T) -> None:
           self.content = content
       def first_chunk(self: Storage[Sequence[S]]) -> S:
           return self.content[0]

   page: Storage[list[str]]
   page.first_chunk()  # OK, type is "str"

   Storage(0).first_chunk()  # Error: Invalid self argument "Storage[int]" to attribute function
                             # "first_chunk" with type "Callable[[Storage[Sequence[S]]], S]"

Finally, one can use overloads on self-type to express precise types of
some tricky methods:

.. code-block:: python

   T = TypeVar('T')

   class Tag(Generic[T]):
       @overload
       def export(self: Tag[str]) -> str: ...
       @overload
       def export(self, converter: Callable[[T], str]) -> str: ...

       def export(self, converter=None):
           if isinstance(self.item, str):
               return self.item
           return converter(self.item)

In particular, an :py:meth:`~object.__init__` method overloaded on self-type
may be useful to annotate generic class constructors where type arguments
depend on constructor parameters in a non-trivial way, see e.g. :py:class:`~subprocess.Popen`.

Mixin classes
-------------

Using host class protocol as a self-type in mixin methods allows
more code re-usability for static typing of mixin classes. For example,
one can define a protocol that defines common functionality for
host classes instead of adding required abstract methods to every mixin:

.. code-block:: python

   class Lockable(Protocol):
       @property
       def lock(self) -> Lock: ...

   class AtomicCloseMixin:
       def atomic_close(self: Lockable) -> int:
           with self.lock:
               # perform actions

   class AtomicOpenMixin:
       def atomic_open(self: Lockable) -> int:
           with self.lock:
               # perform actions

   class File(AtomicCloseMixin, AtomicOpenMixin):
       def __init__(self) -> None:
           self.lock = Lock()

   class Bad(AtomicCloseMixin):
       pass

   f = File()
   b: Bad
   f.atomic_close()  # OK
   b.atomic_close()  # Error: Invalid self type for "atomic_close"

Note that the explicit self-type is *required* to be a protocol whenever it
is not a supertype of the current class. In this case mypy will check the validity
of the self-type only at the call site.

Precise typing of alternative constructors
------------------------------------------

Some classes may define alternative constructors. If these
classes are generic, self-type allows giving them precise signatures:

.. code-block:: python

   T = TypeVar('T')

   class Base(Generic[T]):
       Q = TypeVar('Q', bound='Base[T]')

       def __init__(self, item: T) -> None:
           self.item = item

       @classmethod
       def make_pair(cls: Type[Q], item: T) -> tuple[Q, Q]:
           return cls(item), cls(item)

   class Sub(Base[T]):
       ...

   pair = Sub.make_pair('yes')  # Type is "tuple[Sub[str], Sub[str]]"
   bad = Sub[int].make_pair('no')  # Error: Argument 1 to "make_pair" of "Base"
                                   # has incompatible type "str"; expected "int"

.. _async-and-await:

Typing async/await
******************

Mypy supports the ability to type coroutines that use the ``async/await``
syntax introduced in Python 3.5. For more information regarding coroutines and
this new syntax, see :pep:`492`.

Functions defined using ``async def`` are typed just like normal functions.
The return type annotation should be the same as the type of the value you
expect to get back when ``await``-ing the coroutine.

.. code-block:: python

   import asyncio

   async def format_string(tag: str, count: int) -> str:
       return 'T-minus {} ({})'.format(count, tag)

   async def countdown_1(tag: str, count: int) -> str:
       while count > 0:
           my_str = await format_string(tag, count)  # has type 'str'
           print(my_str)
           await asyncio.sleep(0.1)
           count -= 1
       return "Blastoff!"

   loop = asyncio.get_event_loop()
   loop.run_until_complete(countdown_1("Millennium Falcon", 5))
   loop.close()

The result of calling an ``async def`` function *without awaiting* will be a
value of type :py:class:`Coroutine[Any, Any, T] <typing.Coroutine>`, which is a subtype of
:py:class:`Awaitable[T] <typing.Awaitable>`:

.. code-block:: python

   my_coroutine = countdown_1("Millennium Falcon", 5)
   reveal_type(my_coroutine)  # has type 'Coroutine[Any, Any, str]'

.. note::

    :ref:`reveal_type() <reveal-type>` displays the inferred static type of
    an expression.

If you want to use coroutines in Python 3.4, which does not support
the ``async def`` syntax, you can instead use the :py:func:`@asyncio.coroutine <asyncio.coroutine>`
decorator to convert a generator into a coroutine.

Note that we set the ``YieldType`` of the generator to be ``Any`` in the
following example. This is because the exact yield type is an implementation
detail of the coroutine runner (e.g. the :py:mod:`asyncio` event loop) and your
coroutine shouldn't have to know or care about what precisely that type is.

.. code-block:: python

   from typing import Any, Generator
   import asyncio

   @asyncio.coroutine
   def countdown_2(tag: str, count: int) -> Generator[Any, None, str]:
       while count > 0:
           print('T-minus {} ({})'.format(count, tag))
           yield from asyncio.sleep(0.1)
           count -= 1
       return "Blastoff!"

   loop = asyncio.get_event_loop()
   loop.run_until_complete(countdown_2("USS Enterprise", 5))
   loop.close()

As before, the result of calling a generator decorated with :py:func:`@asyncio.coroutine <asyncio.coroutine>`
will be a value of type :py:class:`Awaitable[T] <typing.Awaitable>`.

.. note::

   At runtime, you are allowed to add the :py:func:`@asyncio.coroutine <asyncio.coroutine>` decorator to
   both functions and generators. This is useful when you want to mark a
   work-in-progress function as a coroutine, but have not yet added ``yield`` or
   ``yield from`` statements:

   .. code-block:: python

      import asyncio

      @asyncio.coroutine
      def serialize(obj: object) -> str:
          # todo: add yield/yield from to turn this into a generator
          return "placeholder"

   However, mypy currently does not support converting functions into
   coroutines. Support for this feature will be added in a future version, but
   for now, you can manually force the function to be a generator by doing
   something like this:

   .. code-block:: python

      from typing import Generator
      import asyncio

      @asyncio.coroutine
      def serialize(obj: object) -> Generator[None, None, str]:
          # todo: add yield/yield from to turn this into a generator
          if False:
              yield
          return "placeholder"

You may also choose to create a subclass of :py:class:`~typing.Awaitable` instead:

.. code-block:: python

   from typing import Any, Awaitable, Generator
   import asyncio

   class MyAwaitable(Awaitable[str]):
       def __init__(self, tag: str, count: int) -> None:
           self.tag = tag
           self.count = count

       def __await__(self) -> Generator[Any, None, str]:
           for i in range(n, 0, -1):
               print('T-minus {} ({})'.format(i, tag))
               yield from asyncio.sleep(0.1)
           return "Blastoff!"

   def countdown_3(tag: str, count: int) -> Awaitable[str]:
       return MyAwaitable(tag, count)

   loop = asyncio.get_event_loop()
   loop.run_until_complete(countdown_3("Heart of Gold", 5))
   loop.close()

To create an iterable coroutine, subclass :py:class:`~typing.AsyncIterator`:

.. code-block:: python

   from typing import Optional, AsyncIterator
   import asyncio

   class arange(AsyncIterator[int]):
       def __init__(self, start: int, stop: int, step: int) -> None:
           self.start = start
           self.stop = stop
           self.step = step
           self.count = start - step

       def __aiter__(self) -> AsyncIterator[int]:
           return self

       async def __anext__(self) -> int:
           self.count += self.step
           if self.count == self.stop:
               raise StopAsyncIteration
           else:
               return self.count

   async def countdown_4(tag: str, n: int) -> str:
       async for i in arange(n, 0, -1):
           print('T-minus {} ({})'.format(i, tag))
           await asyncio.sleep(0.1)
       return "Blastoff!"

   loop = asyncio.get_event_loop()
   loop.run_until_complete(countdown_4("Serenity", 5))
   loop.close()

For a more concrete example, the mypy repo has a toy webcrawler that
demonstrates how to work with coroutines. One version
`uses async/await <https://github.com/python/mypy/blob/master/test-data/samples/crawl2.py>`_
and one
`uses yield from <https://github.com/python/mypy/blob/master/test-data/samples/crawl.py>`_.

.. _typeddict:

TypedDict
*********

Python programs often use dictionaries with string keys to represent objects.
Here is a typical example:

.. code-block:: python

   movie = {'name': 'Blade Runner', 'year': 1982}

Only a fixed set of string keys is expected (``'name'`` and
``'year'`` above), and each key has an independent value type (``str``
for ``'name'`` and ``int`` for ``'year'`` above). We've previously
seen the ``dict[K, V]`` type, which lets you declare uniform
dictionary types, where every value has the same type, and arbitrary keys
are supported. This is clearly not a good fit for
``movie`` above. Instead, you can use a ``TypedDict`` to give a precise
type for objects like ``movie``, where the type of each
dictionary value depends on the key:

.. code-block:: python

   from typing_extensions import TypedDict

   Movie = TypedDict('Movie', {'name': str, 'year': int})

   movie = {'name': 'Blade Runner', 'year': 1982}  # type: Movie

``Movie`` is a ``TypedDict`` type with two items: ``'name'`` (with type ``str``)
and ``'year'`` (with type ``int``). Note that we used an explicit type
annotation for the ``movie`` variable. This type annotation is
important -- without it, mypy will try to infer a regular, uniform
:py:class:`dict` type for ``movie``, which is not what we want here.

.. note::

   If you pass a ``TypedDict`` object as an argument to a function, no
   type annotation is usually necessary since mypy can infer the
   desired type based on the declared argument type. Also, if an
   assignment target has been previously defined, and it has a
   ``TypedDict`` type, mypy will treat the assigned value as a ``TypedDict``,
   not :py:class:`dict`.

Now mypy will recognize these as valid:

.. code-block:: python

   name = movie['name']  # Okay; type of name is str
   year = movie['year']  # Okay; type of year is int

Mypy will detect an invalid key as an error:

.. code-block:: python

   director = movie['director']  # Error: 'director' is not a valid key

Mypy will also reject a runtime-computed expression as a key, as
it can't verify that it's a valid key. You can only use string
literals as ``TypedDict`` keys.

The ``TypedDict`` type object can also act as a constructor. It
returns a normal :py:class:`dict` object at runtime -- a ``TypedDict`` does
not define a new runtime type:

.. code-block:: python

   toy_story = Movie(name='Toy Story', year=1995)

This is equivalent to just constructing a dictionary directly using
``{ ... }`` or ``dict(key=value, ...)``. The constructor form is
sometimes convenient, since it can be used without a type annotation,
and it also makes the type of the object explicit.

Like all types, ``TypedDict``\s can be used as components to build
arbitrarily complex types. For example, you can define nested
``TypedDict``\s and containers with ``TypedDict`` items.
Unlike most other types, mypy uses structural compatibility checking
(or structural subtyping) with ``TypedDict``\s. A ``TypedDict`` object with
extra items is compatible with (a subtype of) a narrower
``TypedDict``, assuming item types are compatible (*totality* also affects
subtyping, as discussed below).

A ``TypedDict`` object is not a subtype of the regular ``dict[...]``
type (and vice versa), since :py:class:`dict` allows arbitrary keys to be
added and removed, unlike ``TypedDict``. However, any ``TypedDict`` object is
a subtype of (that is, compatible with) ``Mapping[str, object]``, since
:py:class:`~typing.Mapping` only provides read-only access to the dictionary items:

.. code-block:: python

   def print_typed_dict(obj: Mapping[str, object]) -> None:
       for key, value in obj.items():
           print('{}: {}'.format(key, value))

   print_typed_dict(Movie(name='Toy Story', year=1995))  # OK

.. note::

   Unless you are on Python 3.8 or newer (where ``TypedDict`` is available in
   standard library :py:mod:`typing` module) you need to install ``typing_extensions``
   using pip to use ``TypedDict``:

   .. code-block:: text

      python3 -m pip install --upgrade typing-extensions

   Or, if you are using Python 2:

   .. code-block:: text

      pip install --upgrade typing-extensions

Totality
--------

By default mypy ensures that a ``TypedDict`` object has all the specified
keys. This will be flagged as an error:

.. code-block:: python

   # Error: 'year' missing
   toy_story = {'name': 'Toy Story'}  # type: Movie

Sometimes you want to allow keys to be left out when creating a
``TypedDict`` object. You can provide the ``total=False`` argument to
``TypedDict(...)`` to achieve this:

.. code-block:: python

   GuiOptions = TypedDict(
       'GuiOptions', {'language': str, 'color': str}, total=False)
   options = {}  # type: GuiOptions  # Okay
   options['language'] = 'en'

You may need to use :py:meth:`~dict.get` to access items of a partial (non-total)
``TypedDict``, since indexing using ``[]`` could fail at runtime. By default
mypy will issue an error for this case; it is possible to disable this check
by adding "typeddict-item-access" to the :confval:`disable_error_code` config option.

Keys that aren't required are shown with a ``?`` in error messages:

.. code-block:: python

   # Revealed type is "TypedDict('GuiOptions', {'language'?: builtins.str,
   #                                            'color'?: builtins.str})"
   reveal_type(options)

Totality also affects structural compatibility. You can't use a partial
``TypedDict`` when a total one is expected. Also, a total ``TypedDict`` is not
valid when a partial one is expected.

Supported operations
--------------------

``TypedDict`` objects support a subset of dictionary operations and methods.
You must use string literals as keys when calling most of the methods,
as otherwise mypy won't be able to check that the key is valid. List
of supported operations:

* Anything included in :py:class:`~typing.Mapping`:

  * ``d[key]``
  * ``key in d``
  * ``len(d)``
  * ``for key in d`` (iteration)
  * :py:meth:`d.get(key[, default]) <dict.get>`
  * :py:meth:`d.keys() <dict.keys>`
  * :py:meth:`d.values() <dict.values>`
  * :py:meth:`d.items() <dict.items>`

* :py:meth:`d.copy() <dict.copy>`
* :py:meth:`d.setdefault(key, default) <dict.setdefault>`
* :py:meth:`d1.update(d2) <dict.update>`
* :py:meth:`d.pop(key[, default]) <dict.pop>` (partial ``TypedDict``\s only)
* ``del d[key]`` (partial ``TypedDict``\s only)

In Python 2 code, these methods are also supported:

* ``has_key(key)``
* ``viewitems()``
* ``viewkeys()``
* ``viewvalues()``

.. note::

   :py:meth:`~dict.clear` and :py:meth:`~dict.popitem` are not supported since they are unsafe
   -- they could delete required ``TypedDict`` items that are not visible to
   mypy because of structural subtyping.

Class-based syntax
------------------

An alternative, class-based syntax to define a ``TypedDict`` is supported
in Python 3.6 and later:

.. code-block:: python

   from typing_extensions import TypedDict

   class Movie(TypedDict):
       name: str
       year: int

The above definition is equivalent to the original ``Movie``
definition. It doesn't actually define a real class. This syntax also
supports a form of inheritance -- subclasses can define additional
items. However, this is primarily a notational shortcut. Since mypy
uses structural compatibility with ``TypedDict``\s, inheritance is not
required for compatibility. Here is an example of inheritance:

.. code-block:: python

   class Movie(TypedDict):
       name: str
       year: int

   class BookBasedMovie(Movie):
       based_on: str

Now ``BookBasedMovie`` has keys ``name``, ``year`` and ``based_on``.

Mixing required and non-required items
--------------------------------------

When a ``TypedDict`` has a mix of items that are required and not required,
the ``NotRequired`` type annotation can be used to specify this for each field:

.. code-block:: python

   class Movie(TypedDict):
       name: str
       year: int
       based_on: NotRequired[str]

Now ``Movie`` has required keys ``name`` and ``year``, while ``based_on``
can be left out when constructing an object. A ``TypedDict`` with a mix of required
and non-required keys, such as ``Movie`` above, will only be compatible with
another ``TypedDict`` if all required keys in the other ``TypedDict`` are required keys in the
first ``TypedDict``, and all non-required keys of the other ``TypedDict`` are also non-required keys
in the first ``TypedDict``.

Unions of TypedDicts
--------------------

Since TypedDicts are really just regular dicts at runtime, it is not possible to
use ``isinstance`` checks to distinguish between different variants of a Union of
TypedDict in the same way you can with regular objects.

Instead, you can use the :ref:`tagged union pattern <tagged_unions>`. The referenced
section of the docs has a full description with an example, but in short, you will
need to give each TypedDict the same key where each value has a unique
:ref:`Literal type <literal_types>`. Then, check that key to distinguish
between your TypedDicts.
