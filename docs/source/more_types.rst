More types
==========

This section introduces a few additional kinds of types, including ``NoReturn``,
``NewType``, ``TypedDict``, and types for async code. All of these are only
situationally useful, so feel free to skip this section and come back when you
have a need for some of them.

Here's a quick summary of what's covered here:

* ``NoReturn`` lets you tell mypy that a function never returns normally.

* ``NewType`` lets you define a variant of a type that is treated as a
  separate type by mypy but is identical to the original type at runtime.
  For example, you can have ``UserId`` as a variant of ``int`` that is
  just an ``int`` at runtime.

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

Mypy will ensure that functions annotated as returning ``NoReturn``
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
pip to use ``NoReturn`` in your code. Python 3 command line:

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

    get_by_user_id(user_id: UserId):
        ...

However, this approach introduces some runtime overhead. To avoid this, the typing
module provides a helper function ``NewType`` that creates simple unique types with
almost zero runtime overhead. Mypy will treat the statement
``Derived = NewType('Derived', Base)`` as being roughly equivalent to the following
definition:

.. code-block:: python

    class Derived(Base):
        def __init__(self, _x: Base) -> None:
            ...

However, at runtime, ``NewType('Derived', Base)`` will return a dummy function that
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

``NewType`` accepts exactly two arguments. The first argument must be a string literal
containing the name of the new type and must equal the name of the variable to which the new
type is assigned. The second argument must be a properly subclassable class, i.e.,
not a type construct like ``Union``, etc.

The function returned by ``NewType`` accepts only one argument; this is equivalent to
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

You cannot use ``isinstance()`` or ``issubclass()`` on the object returned by
``NewType()``, because function objects don't support these operations. You cannot
create subclasses of these objects either.

.. note::

    Unlike type aliases, ``NewType`` will create an entirely new and
    unique type when used. The intended purpose of ``NewType`` is to help you
    detect cases where you accidentally mixed together the old base type and the
    new derived type.

    For example, the following will successfully typecheck when using type
    aliases:

    .. code-block:: python

        UserId = int

        def name_by_id(user_id: UserId) -> str:
            ...

        name_by_id(3)  # ints and UserId are synonymous

    But a similar example using ``NewType`` will not typecheck:

    .. code-block:: python

        from typing import NewType

        UserId = NewType('UserId', int)

        def name_by_id(user_id: UserId) -> str:
            ...

        name_by_id(3)  # int is not the same as UserId

.. _async-and-await:

Typing async/await
******************

Mypy supports the ability to type coroutines that use the ``async/await``
syntax introduced in Python 3.5. For more information regarding coroutines and
this new syntax, see `PEP 492 <https://www.python.org/dev/peps/pep-0492/>`_.

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
value of type ``typing.Coroutine[Any, Any, T]``, which is a subtype of
``Awaitable[T]``:

.. code-block:: python

   my_coroutine = countdown_1("Millennium Falcon", 5)
   reveal_type(my_coroutine)  # has type 'Coroutine[Any, Any, str]'

.. note::

    :ref:`reveal_type() <reveal-type>` displays the inferred static type of
    an expression.

If you want to use coroutines in Python 3.4, which does not support
the ``async def`` syntax, you can instead use the ``@asyncio.coroutine``
decorator to convert a generator into a coroutine.

Note that we set the ``YieldType`` of the generator to be ``Any`` in the
following example. This is because the exact yield type is an implementation
detail of the coroutine runner (e.g. the ``asyncio`` event loop) and your
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

As before, the result of calling a generator decorated with ``@asyncio.coroutine``
will be a value of type ``Awaitable[T]``.

.. note::

   At runtime, you are allowed to add the ``@asyncio.coroutine`` decorator to
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

You may also choose to create a subclass of ``Awaitable`` instead:

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

To create an iterable coroutine, subclass ``AsyncIterator``:

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

.. note::

   TypedDict is an officially supported feature, but it is still experimental.


Python programs often use dictionaries with string keys to represent objects.
Here is a typical example:

.. code-block:: python

   movie = {'name': 'Blade Runner', 'year': 1982}

Only a fixed set of string keys is expected (``'name'`` and
``'year'`` above), and each key has an independent value type (``str``
for ``'name'`` and ``int`` for ``'year'`` above). We've previously
seen the ``Dict[K, V]`` type, which lets you declare uniform
dictionary types, where every value has the same type, and arbitrary keys
are supported. This is clearly not a good fit for
``movie`` above. Instead, you can use a ``TypedDict`` to give a precise
type for objects like ``movie``, where the type of each
dictionary value depends on the key:

.. code-block:: python

   from mypy_extensions import TypedDict

   Movie = TypedDict('Movie', {'name': str, 'year': int})

   movie = {'name': 'Blade Runner', 'year': 1982}  # type: Movie

``Movie`` is a TypedDict type with two items: ``'name'`` (with type ``str``)
and ``'year'`` (with type ``int``). Note that we used an explicit type
annotation for the ``movie`` variable. This type annotation is
important -- without it, mypy will try to infer a regular, uniform
``Dict`` type for ``movie``, which is not what we want here.

.. note::

   If you pass a TypedDict object as an argument to a function, no
   type annotation is usually necessary since mypy can infer the
   desired type based on the declared argument type. Also, if an
   assignment target has been previously defined, and it has a
   TypedDict type, mypy will treat the assigned value as a TypedDict,
   not ``Dict``.

Now mypy will recognize these as valid:

.. code-block:: python

   name = movie['name']  # Okay; type of name is str
   year = movie['year']  # Okay; type of year is int

Mypy will detect an invalid key as an error:

.. code-block:: python

   director = movie['director']  # Error: 'director' is not a valid key

Mypy will also reject a runtime-computed expression as a key, as
it can't verify that it's a valid key. You can only use string
literals as TypedDict keys.

The ``TypedDict`` type object can also act as a constructor. It
returns a normal ``dict`` object at runtime -- a ``TypedDict`` does
not define a new runtime type:

.. code-block:: python

   toy_story = Movie(name='Toy Story', year=1995)

This is equivalent to just constructing a dictionary directly using
``{ ... }`` or ``dict(key=value, ...)``. The constructor form is
sometimes convenient, since it can be used without a type annotation,
and it also makes the type of the object explicit.

Like all types, TypedDicts can be used as components to build
arbitrarily complex types. For example, you can define nested
TypedDicts and containers with TypedDict items.
Unlike most other types, mypy uses structural compatibility checking
(or structural subtyping) with TypedDicts. A TypedDict object with
extra items is compatible with a narrower TypedDict, assuming item
types are compatible (*totality* also affects
subtyping, as discussed below).

.. note::

   You need to install ``mypy_extensions`` using pip to use ``TypedDict``:

   .. code-block:: text

       python3 -m pip install --upgrade mypy-extensions

   Or, if you are using Python 2:

   .. code-block:: text

       pip install --upgrade mypy-extensions

Totality
--------

By default mypy ensures that a TypedDict object has all the specified
keys. This will be flagged as an error:

.. code-block:: python

   # Error: 'year' missing
   toy_story = {'name': 'Toy Story'}  # type: Movie

Sometimes you want to allow keys to be left out when creating a
TypedDict object. You can provide the ``total=False`` argument to
``TypedDict(...)`` to achieve this:

.. code-block:: python

   GuiOptions = TypedDict(
       'GuiOptions', {'language': str, 'color': str}, total=False)
   options = {}  # type: GuiOptions  # Okay
   options['language'] = 'en'

You may need to use ``get()`` to access items of a partial (non-total)
TypedDict, since indexing using ``[]`` could fail at runtime.
However, mypy still lets use ``[]`` with a partial TypedDict -- you
just need to be careful with it, as it could result in a ``KeyError``.
Requiring ``get()`` everywhere would be too cumbersome. (Note that you
are free to use ``get()`` with total TypedDicts as well.)

Keys that aren't required are shown with a ``?`` in error messages:

.. code-block:: python

   # Revealed type is 'TypedDict('GuiOptions', {'language'?: builtins.str,
   #                                            'color'?: builtins.str})'
   reveal_type(options)

Totality also affects structural compatibility. You can't use a partial
TypedDict when a total one is expected. Also, a total TypedDict is not
valid when a partial one is expected.

Class-based syntax
------------------

An alternative, class-based syntax to define a TypedDict is supported
in Python 3.6 and later:

.. code-block:: python

   from mypy_extensions import TypedDict

   class Movie(TypedDict):
       name: str
       year: int

The above definition is equivalent to the original ``Movie``
definition. It doesn't actually define a real class. This syntax also
supports a form of inheritance -- subclasses can define additional
items. However, this is primarily a notational shortcut. Since mypy
uses structural compatibility with TypedDicts, inheritance is not
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

In addition to allowing reuse across TypedDict types, inheritance also allows
you to mix required and non-required (using ``total=False``) items
in a single TypedDict. Example:

.. code-block:: python

   class MovieBase(TypedDict):
       name: str
       year: int

   class Movie(MovieBase, total=False):
       based_on: str

Now ``Movie`` has required keys ``name`` and ``year``, while ``based_on``
can be left out when constructing an object. A TypedDict with a mix of required
and non-required keys, such as ``Movie`` above, will only be compatible with
another TypedDict if all required keys in the other TypedDict are required keys in the
first TypedDict, and all non-required keys of the other TypedDict are also non-required keys
in the first TypedDict.
