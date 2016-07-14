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

A type alias does not create a new type. It's just a shorthand notation
for another type -- it's equivalent to the target type. Type aliases
can be imported from modules like any names.

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
