Kinds of types
==============

User-defined types
******************

Each class is also a type. Any instance of a subclass is also
compatible with all superclasses. All values are compatible with the
``object`` type (and also the ``Any`` type).

.. code-block:: python

   class A:
       def f(self) -> int:        # Type of self inferred (A)
           return 2

   class B(A):
       def f(self) -> int:
            return 3
       def g(self) -> int:
           return 4

   a = B() # type: A  # OK (explicit type for a; override type inference)
   print(a.f())       # 3
   a.g()              # Type check error: A has no method g

The Any type
************

A value with the ``Any`` type is dynamically typed. Mypy doesn't know
anything about the possible runtime types of such value. Any
operations are permitted on the value, and the operations are checked
at runtime, similar to normal Python code without type annotations.

``Any`` is compatible with every other type, and vice versa. No
implicit type check is inserted when assigning a value of type ``Any``
to a variable with a more precise type:

.. code-block:: python

   a = None  # type: Any
   s = ''    # type: str
   a = 2     # OK
   s = a     # OK

Declared (and inferred) types are *erased* at runtime. They are
basically treated as comments, and thus the above code does not
generate a runtime error, even though ``s`` gets an ``int`` value when
the program is run. Note that the declared type of ``s`` is actually
``str``!

If you do not define a function return value or argument types, these
default to ``Any``:

.. code-block:: python

   def show_heading(s) -> None:
       print('=== ' + s + ' ===')  # No static type checking, as s has type Any

   show_heading(1)  # OK (runtime error only; mypy won't generate an error)

You should give a statically typed function an explicit ``None``
return type even if it doesn't return a value, as this lets mypy catch
additional type errors:

.. code-block:: python

   def wait(t: float):  # Implicit Any return value
       print('Waiting...')
       time.sleep(t)

   if wait(2) > 1:   # Mypy doesn't catch this error!
       ...

If we had used an explicit ``None`` return type, mypy would have caught
the error:

.. code-block:: python

   def wait(t: float) -> None:
       print('Waiting...')
       time.sleep(t)

   if wait(2) > 1:   # Error: can't compare None and int
       ...

The ``Any`` type is discussed in more detail in section :ref:`dynamic_typing`.

.. note::

  A function without any types in the signature is dynamically
  typed. The body of a dynamically typed function is not checked
  statically, and local variables have implicit ``Any`` types.
  This makes it easier to migrate legacy Python code to mypy, as
  mypy won't complain about dynamically typed functions.

.. _tuple-types:

Tuple types
***********

The type ``Tuple[T1, ..., Tn]`` represents a tuple with the item types ``T1``, ..., ``Tn``:

.. code-block:: python

   def f(t: Tuple[int, str]) -> None:
       t = 1, 'foo'    # OK
       t = 'foo', 1    # Type check error

A tuple type of this kind has exactly a specific number of items (2 in
the above example). Tuples can also be used as immutable,
varying-length sequences. You can use the type ``Tuple[T, ...]`` (with
a literal ``...`` -- it's part of the syntax) for this
purpose. Example:

.. code-block:: python

    def print_squared(t: Tuple[int, ...]) -> None:
        for n in t:
            print(n, n ** 2)

    print_squared(())           # OK
    print_squared((1, 3, 5))    # OK
    print_squared([1, 2])       # Error: only a tuple is valid

.. note::

   Usually it's a better idea to use ``Sequence[T]`` instead of ``Tuple[T, ...]``, as
   ``Sequence`` is also compatible with lists and other non-tuple sequences.

.. note::

   ``Tuple[...]`` is not valid as a base class outside stub files. This is a
   limitation of the ``typing`` module. One way to work around
   this is to use a named tuple as a base class (see section :ref:`named-tuples`).

.. _callable-types:

Callable types (and lambdas)
****************************

You can pass around function objects and bound methods in statically
typed code. The type of a function that accepts arguments ``A1``, ..., ``An``
and returns ``Rt`` is ``Callable[[A1, ..., An], Rt]``. Example:

.. code-block:: python

   from typing import Callable

   def twice(i: int, next: Callable[[int], int]) -> int:
       return next(next(i))

   def add(i: int) -> int:
       return i + 1

   print(twice(3, add))   # 5

You can only have positional arguments, and only ones without default
values, in callable types. These cover the vast majority of uses of
callable types, but sometimes this isn't quite enough. Mypy recognizes
a special form ``Callable[..., T]`` (with a literal ``...``) which can
be used in less typical cases. It is compatible with arbitrary
callable objects that return a type compatible with ``T``, independent
of the number, types or kinds of arguments. Mypy lets you call such
callable values with arbitrary arguments, without any checking -- in
this respect they are treated similar to a ``(*args: Any, **kwargs:
Any)`` function signature. Example:

.. code-block:: python

   from typing import Callable

    def arbitrary_call(f: Callable[..., int]) -> int:
        return f('x') + f(y=2)  # OK

    arbitrary_call(ord)   # No static error, but fails at runtime
    arbitrary_call(open)  # Error: does not return an int
    arbitrary_call(1)     # Error: 'int' is not callable

Lambdas are also supported. The lambda argument and return value types
cannot be given explicitly; they are always inferred based on context
using bidirectional type inference:

.. code-block:: python

   l = map(lambda x: x + 1, [1, 2, 3])   # Infer x as int and l as List[int]

If you want to give the argument or return value types explicitly, use
an ordinary, perhaps nested function definition.

.. _extended_callable:

Extended Callable types
***********************

As an experimental mypy extension, you can specify ``Callable`` types
that support keyword arguments, optional arguments, and more.  Where
you specify the arguments of a Callable, you can choose to supply just
the type of a nameless positional argument, or an "argument specifier"
representing a more complicated form of argument.  This allows one to
more closely emulate the full range of possibilities given by the
``def`` statement in Python.

As an example, here's a complicated function definition and the
corresponding ``Callable``:

.. code-block:: python

   from typing import Callable
   from mypy_extensions import (Arg, DefaultArg, NamedArg,
                                DefaultNamedArg, VarArg, KwArg)

   def func(__a: int,  # This convention is for nameless arguments
            b: int,
            c: int = 0,
            *args: int,
            d: int,
            e: int = 0,
            **kwargs: int) -> int:
       ...

   F = Callable[[int,  # Or Arg(int)
                 Arg(int, 'b'),
                 DefaultArg(int, 'c'),
                 VarArg(int),
                 NamedArg(int, 'd'),
                 DefaultNamedArg(int, 'e'),
                 KwArg(int)],
                int]

   f: F = func

Argument specifiers are special function calls that can specify the
following aspects of an argument:

- its type (the only thing that the basic format supports)

- its name (if it has one)

- whether it may be omitted

- whether it may or must be passed using a keyword

- whether it is a ``*args`` argument (representing the remaining
  positional arguments)

- whether it is a ``**kwargs`` argument (representing the remaining
  keyword arguments)

The following functions are available in ``mypy_extensions`` for this
purpose:

.. code-block:: python

   def Arg(type=Any, name=None):
       # A normal, mandatory, positional argument.
       # If the name is specified it may be passed as a keyword.

   def DefaultArg(type=Any, name=None):
       # An optional positional argument (i.e. with a default value).
       # If the name is specified it may be passed as a keyword.

   def NamedArg(type=Any, name=None):
       # A mandatory keyword-only argument.

   def DefaultNamedArg(type=Any, name=None):
       # An optional keyword-only argument (i.e. with a default value).

   def VarArg(type=Any):
       # A *args-style variadic positional argument.
       # A single VarArg() specifier represents all remaining
       # positional arguments.

   def KwArg(type=Any):
       # A **kwargs-style variadic keyword argument.
       # A single KwArg() specifier represents all remaining
       # keyword arguments.

In all cases, the ``type`` argument defaults to ``Any``, and if the
``name`` argument is omitted the argument has no name (the name is
required for ``NamedArg`` and ``DefaultNamedArg``).  A basic
``Callable`` such as

.. code-block:: python

   MyFunc = Callable[[int, str, int], float]

is equivalent to the following:

.. code-block:: python

   MyFunc = Callable[[Arg(int), Arg(str), Arg(int)], float]

A ``Callable`` with unspecified argument types, such as

.. code-block:: python

   MyOtherFunc = Callable[..., int]

is (roughly) equivalent to

.. code-block:: python

   MyOtherFunc = Callable[[VarArg(), KwArg()], int]

.. note::

   This feature is experimental.  Details of the implementation may
   change and there may be unknown limitations. **IMPORTANT:**
   Each of the functions above currently just returns its ``type``
   argument, so the information contained in the argument specifiers
   is not available at runtime.  This limitation is necessary for
   backwards compatibility with the existing ``typing.py`` module as
   present in the Python 3.5+ standard library and distributed via
   PyPI.

.. _union-types:

Union types
***********

Python functions often accept values of two or more different
types. You can use overloading to model this in statically typed code,
but union types can make code like this easier to write.

Use the ``Union[T1, ..., Tn]`` type constructor to construct a union
type. For example, the type ``Union[int, str]`` is compatible with
both integers and strings. You can use an ``isinstance()`` check to
narrow down the type to a specific type:

.. code-block:: python

   from typing import Union

   def f(x: Union[int, str]) -> None:
       x + 1     # Error: str + int is not valid
       if isinstance(x, int):
           # Here type of x is int.
           x + 1      # OK
       else:
           # Here type of x is str.
           x + 'a'    # OK

   f(1)    # OK
   f('x')  # OK
   f(1.1)  # Error

.. _optional:

The type of None and optional types
***********************************

Mypy treats the type of ``None`` as special. ``None`` is a valid value
for every type, which resembles ``null`` in Java. Unlike Java, mypy
doesn't treat primitives types
specially: ``None`` is also valid for primitive types such as ``int``
and ``float``.

.. note::

   See :ref:`strict_optional` for an experimental mode which allows
   mypy to check ``None`` values precisely.

When initializing a variable as ``None``, ``None`` is usually an
empty place-holder value, and the actual value has a different type.
This is why you need to annotate an attribute in a case like this:

.. code-block:: python

    class A:
        def __init__(self) -> None:
            self.count = None  # type: int

Mypy will complain if you omit the type annotation, as it wouldn't be
able to infer a non-trivial type for the ``count`` attribute
otherwise.

Mypy generally uses the first assignment to a variable to
infer the type of the variable. However, if you assign both a ``None``
value and a non-``None`` value in the same scope, mypy can often do
the right thing:

.. code-block:: python

   def f(i: int) -> None:
       n = None  # Inferred type int because of the assignment below
       if i > 0:
            n = i
       ...

Often it's useful to know whether a variable can be
``None``. For example, this function accepts a ``None`` argument,
but it's not obvious from its signature:

.. code-block:: python

    def greeting(name: str) -> str:
        if name:
            return 'Hello, {}'.format(name)
        else:
            return 'Hello, stranger'

    print(greeting('Python'))  # Okay!
    print(greeting(None))      # Also okay!

Mypy lets you use ``Optional[t]`` to document that ``None`` is a
valid argument type:

.. code-block:: python

    from typing import Optional

    def greeting(name: Optional[str]) -> str:
        if name:
            return 'Hello, {}'.format(name)
        else:
            return 'Hello, stranger'

Mypy treats this as semantically equivalent to the previous example,
since ``None`` is implicitly valid for any type, but it's much more
useful for a programmer who is reading the code. You can equivalently
use ``Union[str, None]``, but ``Optional`` is shorter and more
idiomatic.

.. note::

    ``None`` is also used as the return type for functions that don't
    return a value, i.e. that implicitly return ``None``. Mypy doesn't
    use ``NoneType`` for this, since it would
    look awkward, even though that is the real name of the type of ``None``
    (try ``type(None)`` in the interactive interpreter to see for yourself).

.. _strict_optional:

Experimental strict optional type and None checking
***************************************************

Currently, ``None`` is a valid value for each type, similar to
``null`` or ``NULL`` in many languages. However, you can use the
experimental ``--strict-optional`` command line option to tell mypy
that types should not include ``None``
by default. The ``Optional`` type modifier is then used to define
a type variant that includes ``None``, such as ``Optional[int]``:

.. code-block:: python

   from typing import Optional

   def f() -> Optional[int]:
       return None  # OK

   def g() -> int:
       ...
       return None  # Error: None not compatible with int

Also, most operations will not be allowed on unguarded ``None``
or ``Optional`` values:

.. code-block:: python

   def f(x: Optional[int]) -> int:
       return x + 1  # Error: Cannot add None and int

Instead, an explicit ``None`` check is required. Mypy has
powerful type inference that lets you use regular Python
idioms to guard against ``None`` values. For example, mypy
recognizes ``is None`` checks:

.. code-block:: python

   def f(x: Optional[int]) -> int:
       if x is None:
           return 0
       else:
           # The inferred type of x is just int here.
           return x + 1

Mypy will infer the type of ``x`` to be ``int`` in the else block due to the
check against ``None`` in the if condition.

.. note::

    ``--strict-optional`` is experimental and still has known issues.

.. _noreturn:

The NoReturn type
*****************

Mypy provides support for functions that never return. For
example, a function that unconditionally raises an exception:

.. code-block:: python

   from mypy_extensions import NoReturn

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

Install ``mypy_extensions`` using pip to use ``NoReturn`` in your code.
Python 3 command line:

.. code-block:: text

    python3 -m pip install --upgrade mypy-extensions

This works for Python 2:

.. code-block:: text

    pip install --upgrade mypy-extensions


Class name forward references
*****************************

Python does not allow references to a class object before the class is
defined. Thus this code does not work as expected:

.. code-block:: python

   def f(x: A) -> None:  # Error: Name A not defined
       ....

   class A:
       ...

In cases like these you can enter the type as a string literal — this
is a *forward reference*:

.. code-block:: python

   def f(x: 'A') -> None:  # OK
       ...

   class A:
       ...

Of course, instead of using a string literal type, you could move the
function definition after the class definition. This is not always
desirable or even possible, though.

Any type can be entered as a string literal, and you can combine
string-literal types with non-string-literal types freely:

.. code-block:: python

   def f(a: List['A']) -> None: ...  # OK
   def g(n: 'int') -> None: ...      # OK, though not useful

   class A: pass

String literal types are never needed in ``# type:`` comments.

String literal types must be defined (or imported) later *in the same
module*.  They cannot be used to leave cross-module references
unresolved.  (For dealing with import cycles, see
:ref:`import-cycles`.)

.. _type-aliases:

Type aliases
************

In certain situations, type names may end up being long and painful to type:

.. code-block:: python

   def f() -> Union[List[Dict[Tuple[int, str], Set[int]]], Tuple[str, List[str]]]:
       ...

When cases like this arise, you can define a type alias by simply
assigning the type to a variable:

.. code-block:: python

   AliasType = Union[List[Dict[Tuple[int, str], Set[int]]], Tuple[str, List[str]]]

   # Now we can use AliasType in place of the full name:

   def f() -> AliasType:
       ...

Type aliases can be generic, in this case they could be used in two variants:
Subscripted aliases are equivalent to original types with substituted type variables,
number of type arguments must match the number of free type variables
in generic type alias. Unsubscripted aliases are treated as original types with free
variables replaced with ``Any``. Examples (following `PEP 484
<https://www.python.org/dev/peps/pep-0484/#type-aliases>`_):

.. code-block:: python

    from typing import TypeVar, Iterable, Tuple, Union, Callable
    S = TypeVar('S')
    TInt = Tuple[int, S]
    UInt = Union[S, int]
    CBack = Callable[..., S]

    def response(query: str) -> UInt[str]:  # Same as Union[str, int]
        ...
    def activate(cb: CBack[S]) -> S:        # Same as Callable[..., S]
        ...
    table_entry: TInt  # Same as Tuple[int, Any]

    T = TypeVar('T', int, float, complex)
    Vec = Iterable[Tuple[T, T]]

    def inproduct(v: Vec[T]) -> T:
        return sum(x*y for x, y in v)

    def dilate(v: Vec[T], scale: T) -> Vec[T]:
        return ((x * scale, y * scale) for x, y in v)

    v1: Vec[int] = []      # Same as Iterable[Tuple[int, int]]
    v2: Vec = []           # Same as Iterable[Tuple[Any, Any]]
    v3: Vec[int, int] = [] # Error: Invalid alias, too many type arguments!

Type aliases can be imported from modules like any names. Aliases can target another
aliases (although building complex chains of aliases is not recommended, this
impedes code readability, thus defeating the purpose of using aliases).
Following previous examples:

.. code-block:: python

    from typing import TypeVar, Generic, Optional
    from first_example import AliasType
    from second_example import Vec

    def fun() -> AliasType:
        ...

    T = TypeVar('T')
    class NewVec(Generic[T], Vec[T]):
        ...
    for i, j in NewVec[int]():
        ...

    OIntVec = Optional[Vec[int]]

.. note::

    A type alias does not create a new type. It's just a shorthand notation for
    another type -- it's equivalent to the target type. For generic type aliases
    this means that variance of type variables used for alias definition does not
    apply to aliases. A parameterized generic alias is treated simply as an original
    type with the corresponding type variables substituted.

.. _newtypes:

NewTypes
********

(Freely after `PEP 484
<https://www.python.org/dev/peps/pep-0484/#newtype-helper-function>`_.)

There are also situations where a programmer might want to avoid logical errors by
creating simple classes. For example:

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

Both ``isinstance`` and ``issubclass``, as well as subclassing will fail for
``NewType('Derived', Base)`` since function objects don't support these operations.

.. note::

    Note that unlike type aliases, ``NewType`` will create an entirely new and
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

.. _named-tuples:

Named tuples
************

Mypy recognizes named tuples and can type check code that defines or
uses them.  In this example, we can detect code trying to access a
missing attribute:

.. code-block:: python

    Point = namedtuple('Point', ['x', 'y'])
    p = Point(x=1, y=2)
    print(p.z)  # Error: Point has no attribute 'z'

If you use ``namedtuple`` to define your named tuple, all the items
are assumed to have ``Any`` types. That is, mypy doesn't know anything
about item types. You can use ``typing.NamedTuple`` to also define
item types:

.. code-block:: python

    from typing import NamedTuple

    Point = NamedTuple('Point', [('x', int),
                                 ('y', int)])
    p = Point(x=1, y='x')  # Argument has incompatible type "str"; expected "int"

Python 3.6 will have an alternative, class-based syntax for named tuples with types.
Mypy supports it already:

.. code-block:: python

    from typing import NamedTuple

    class Point(NamedTuple):
        x: int
        y: int

    p = Point(x=1, y='x')  # Argument has incompatible type "str"; expected "int"

.. _type-of-class:

The type of class objects
*************************

(Freely after `PEP 484
<https://www.python.org/dev/peps/pep-0484/#the-type-of-class-objects>`_.)

Sometimes you want to talk about class objects that inherit from a
given class.  This can be spelled as ``Type[C]`` where ``C`` is a
class.  In other words, when ``C`` is the name of a class, using ``C``
to annotate an argument declares that the argument is an instance of
``C`` (or of a subclass of ``C``), but using ``Type[C]`` as an
argument annotation declares that the argument is a class object
deriving from ``C`` (or ``C`` itself).

For example, assume the following classes:

.. code-block:: python

   class User:
       # Defines fields like name, email

   class BasicUser(User):
       def upgrade(self):
           """Upgrade to Pro"""

   class ProUser(User):
       def pay(self):
           """Pay bill"""

Note that ``ProUser`` doesn't inherit from ``BasicUser``.

Here's a function that creates an instance of one of these classes if
you pass it the right class object:

.. code-block:: python

   def new_user(user_class):
       user = user_class()
       # (Here we could write the user object to a database)
       return user

How would we annotate this function?  Without ``Type[]`` the best we
could do would be:

.. code-block:: python

   def new_user(user_class: type) -> User:
       # Same  implementation as before

This seems reasonable, except that in the following example, mypy
doesn't see that the ``buyer`` variable has type ``ProUser``:

.. code-block:: python

   buyer = new_user(ProUser)
   buyer.pay()  # Rejected, not a method on User

However, using ``Type[]`` and a type variable with an upper bound (see
:ref:`type-variable-upper-bound`) we can do better:

.. code-block:: python

   U = TypeVar('U', bound=User)

   def new_user(user_class: Type[U]) -> U:
       # Same  implementation as before

Now mypy will infer the correct type of the result when we call
``new_user()`` with a specific subclass of ``User``:

.. code-block:: python

   beginner = new_user(BasicUser)  # Inferred type is BasicUser
   beginner.upgrade()  # OK

.. note::

   The value corresponding to ``Type[C]`` must be an actual class
   object that's a subtype of ``C``.  Its constructor must be
   compatible with the constructor of ``C``.  If ``C`` is a type
   variable, its upper bound must be a class object.

For more details about ``Type[]`` see `PEP 484
<https://www.python.org/dev/peps/pep-0484/#the-type-of-class-objects>`_.

.. _text-and-anystr:

Text and AnyStr
***************

Sometimes you may want to write a function which will accept only unicode
strings. This can be challenging to do in a codebase intended to run in
both Python 2 and Python 3 since ``str`` means something different in both
versions and ``unicode`` is not a keyword in Python 3.

To help solve this issue, use ``typing.Text`` which is aliased to
``unicode`` in Python 2 and to ``str`` in Python 3. This allows you to
indicate that a function should accept only unicode strings in a
cross-compatible way:

.. code-block:: python

   from typing import Text

   def unicode_only(s: Text) -> Text:
       return s + u'\u2713'

In other cases, you may want to write a function that will work with any
kind of string but will not let you mix two different string types. To do
so use ``typing.AnyStr``:

.. code-block:: python

   from typing import AnyStr

   def concat(x: AnyStr, y: AnyStr) -> AnyStr:
       return x + y

   concat('a', 'b')     # Okay
   concat(b'a', b'b')   # Okay
   concat('a', b'b')    # Error: cannot mix bytes and unicode

For more details, see :ref:`type-variable-value-restriction`.

.. note::

   How ``bytes``, ``str``, and ``unicode`` are handled between Python 2 and
   Python 3 may change in future versions of mypy.

.. _generators:

Generators
**********

A basic generator that only yields values can be annotated as having a return
type of either ``Iterator[YieldType]`` or ``Iterable[YieldType]``. For example:

.. code-block:: python

   def squares(n: int) -> Iterator[int]:
       for i in range(n):
           yield i * i

If you want your generator to accept values via the ``send`` method or return
a value, you should use the
``Generator[YieldType, SendType, ReturnType]`` generic type instead. For example:

.. code-block:: python

   def echo_round() -> Generator[int, float, str]:
       sent = yield 0
       while sent >= 0:
           sent = yield round(sent)
       return 'Done'

Note that unlike many other generics in the typing module, the ``SendType`` of
``Generator`` behaves contravariantly, not covariantly or invariantly.

If you do not plan on receiving or returning values, then set the ``SendType``
or ``ReturnType`` to ``None``, as appropriate. For example, we could have
annotated the first example as the following:

.. code-block:: python

   def squares(n: int) -> Generator[int, None, None]:
       for i in range(n):
           yield i * i

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
value of type ``Awaitable[T]``:

.. code-block:: python

   my_coroutine = countdown_1("Millennium Falcon", 5)
   reveal_type(my_coroutine)  # has type 'Awaitable[str]'

.. note::

    :ref:`reveal_type() <reveal-type>` displays the inferred static type of
    an expression.

If you want to use coroutines in older versions of Python that do not support
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
TypedDict when a total one is expected. Also, a total typed dict is not
valid when a partial one is expected.

Class-based syntax
------------------

Python 3.6 supports an alternative, class-based syntax to define a
TypedDict. This means that your code must be checked as if it were
Python 3.6 (using the ``--python-version`` flag on the command line,
for example). Simply running mypy on Python 3.6 is insufficient.

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
