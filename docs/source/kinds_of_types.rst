Kinds of types
==============

We've mostly restricted ourselves to built-in types until now. This
section introduces several additional kinds of types. You are likely
to need at least some of them to type check any non-trivial programs.

Class types
***********

Every class is also a valid type. Any instance of a subclass is also
compatible with all superclasses -- it follows that every value is compatible
with the :py:class:`object` type (and incidentally also the ``Any`` type, discussed
below). Mypy analyzes the bodies of classes to determine which methods and
attributes are available in instances. This example uses subclassing:

.. code-block:: python

   class A:
       def f(self) -> int:  # Type of self inferred (A)
           return 2

   class B(A):
       def f(self) -> int:
            return 3
       def g(self) -> int:
           return 4

   def foo(a: A) -> None:
       print(a.f())  # 3
       a.g()         # Error: "A" has no attribute "g"

   foo(B())  # OK (B is a subclass of A)

The Any type
************

A value with the ``Any`` type is dynamically typed. Mypy doesn't know
anything about the possible runtime types of such value. Any
operations are permitted on the value, and the operations are only checked
at runtime. You can use ``Any`` as an "escape hatch" when you can't use
a more precise type for some reason.

``Any`` is compatible with every other type, and vice versa. You can freely
assign a value of type ``Any`` to a variable with a more precise type:

.. code-block:: python

   a: Any = None
   s: str = ''
   a = 2     # OK (assign "int" to "Any")
   s = a     # OK (assign "Any" to "str")

Declared (and inferred) types are ignored (or *erased*) at runtime. They are
basically treated as comments, and thus the above code does not
generate a runtime error, even though ``s`` gets an ``int`` value when
the program is run, while the declared type of ``s`` is actually
``str``! You need to be careful with ``Any`` types, since they let you
lie to mypy, and this could easily hide bugs.

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

The ``Any`` type is discussed in more detail in section :ref:`dynamic-typing`.

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
   :py:class:`~typing.Sequence` is also compatible with lists and other non-tuple sequences.

.. note::

   ``Tuple[...]`` is valid as a base class in Python 3.6 and later, and
   always in stub files. In earlier Python versions you can sometimes work around this
   limitation by using a named tuple as a base class (see section :ref:`named-tuples`).

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

In situations where more precise or complex types of callbacks are
necessary one can use flexible :ref:`callback protocols <callback_protocols>`.
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
types. You can use :ref:`overloading <function-overloading>` to
represent this, but union types are often more convenient.

Use the ``Union[T1, ..., Tn]`` type constructor to construct a union
type. For example, if an argument has type ``Union[int, str]``, both
integers and strings are valid argument values.

You can use an :py:func:`isinstance` check to narrow down a union type to a
more specific type:

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

.. note::

    Operations are valid for union types only if they are valid for *every*
    union item. This is why it's often necessary to use an :py:func:`isinstance`
    check to first narrow down a union type to a non-union type. This also
    means that it's recommended to avoid union types as function return types,
    since the caller may have to use :py:func:`isinstance` before doing anything
    interesting with the value.

.. _strict_optional:

Optional types and the None type
********************************

You can use the :py:data:`~typing.Optional` type modifier to define a type variant
that allows ``None``, such as ``Optional[int]`` (``Optional[X]`` is
the preferred shorthand for ``Union[X, None]``):

.. code-block:: python

   from typing import Optional

   def strlen(s: str) -> Optional[int]:
       if not s:
           return None  # OK
       return len(s)

   def strlen_invalid(s: str) -> int:
       if not s:
           return None  # Error: None not compatible with int
       return len(s)

Most operations will not be allowed on unguarded ``None`` or :py:data:`~typing.Optional`
values:

.. code-block:: python

   def my_inc(x: Optional[int]) -> int:
       return x + 1  # Error: Cannot add None and int

Instead, an explicit ``None`` check is required. Mypy has
powerful type inference that lets you use regular Python
idioms to guard against ``None`` values. For example, mypy
recognizes ``is None`` checks:

.. code-block:: python

   def my_inc(x: Optional[int]) -> int:
       if x is None:
           return 0
       else:
           # The inferred type of x is just int here.
           return x + 1

Mypy will infer the type of ``x`` to be ``int`` in the else block due to the
check against ``None`` in the if condition.

Other supported checks for guarding against a ``None`` value include
``if x is not None``, ``if x`` and ``if not x``. Additionally, mypy understands
``None`` checks within logical expressions:

.. code-block:: python

   def concat(x: Optional[str], y: Optional[str]) -> Optional[str]:
       if x is not None and y is not None:
           # Both x and y are not None here
           return x + y
       else:
           return None

Sometimes mypy doesn't realize that a value is never ``None``. This notably
happens when a class instance can exist in a partially defined state,
where some attribute is initialized to ``None`` during object
construction, but a method assumes that the attribute is no longer ``None``. Mypy
will complain about the possible ``None`` value. You can use
``assert x is not None`` to work around this in the method:

.. code-block:: python

   class Resource:
       path: Optional[str] = None

       def initialize(self, path: str) -> None:
           self.path = path

       def read(self) -> str:
           # We require that the object has been initialized.
           assert self.path is not None
           with open(self.path) as f:  # OK
              return f.read()

   r = Resource()
   r.initialize('/foo/bar')
   r.read()

When initializing a variable as ``None``, ``None`` is usually an
empty place-holder value, and the actual value has a different type.
This is why you need to annotate an attribute in a cases like the class
``Resource`` above:

.. code-block:: python

    class Resource:
        path: Optional[str] = None
        ...

This also works for attributes defined within methods:

.. code-block:: python

    class Counter:
        def __init__(self) -> None:
            self.count: Optional[int] = None

As a special case, you can use a non-optional type when initializing an
attribute to ``None`` inside a class body *and* using a type comment,
since when using a type comment, an initializer is syntactically required,
and ``None`` is used as a dummy, placeholder initializer:

.. code-block:: python

   from typing import List

   class Container:
       items = None  # type: List[str]  # OK (only with type comment)

This is not a problem when using variable annotations, since no initializer
is needed:

.. code-block:: python

   from typing import List

   class Container:
       items: List[str]  # No initializer

Mypy generally uses the first assignment to a variable to
infer the type of the variable. However, if you assign both a ``None``
value and a non-``None`` value in the same scope, mypy can usually do
the right thing without an annotation:

.. code-block:: python

   def f(i: int) -> None:
       n = None  # Inferred type Optional[int] because of the assignment below
       if i > 0:
            n = i
       ...

Sometimes you may get the error "Cannot determine type of <something>". In this
case you should add an explicit ``Optional[...]`` annotation (or type comment).

.. note::

   ``None`` is a type with only one value, ``None``. ``None`` is also used
   as the return type for functions that don't return a value, i.e. functions
   that implicitly return ``None``.

.. note::

   The Python interpreter internally uses the name ``NoneType`` for
   the type of ``None``, but ``None`` is always used in type
   annotations. The latter is shorter and reads better. (Besides,
   ``NoneType`` is not even defined in the standard library.)

.. note::

    ``Optional[...]`` *does not* mean a function argument with a default value.
    However, if the default value of an argument is ``None``, you can use
    an optional type for the argument, but it's not enforced by default.
    You can use the :option:`--no-implicit-optional <mypy --no-implicit-optional>` command-line option to stop
    treating arguments with a ``None`` default value as having an implicit
    ``Optional[...]`` type. It's possible that this will become the default
    behavior in the future.

.. _no_strict_optional:

Disabling strict optional checking
**********************************

Mypy also has an option to treat ``None`` as a valid value for every
type (in case you know Java, it's useful to think of it as similar to
the Java ``null``). In this mode ``None`` is also valid for primitive
types such as ``int`` and ``float``, and :py:data:`~typing.Optional` types are
not required.

The mode is enabled through the :option:`--no-strict-optional <mypy --no-strict-optional>` command-line
option. In mypy versions before 0.600 this was the default mode. You
can enable this option explicitly for backward compatibility with
earlier mypy versions, in case you don't want to introduce optional
types to your codebase yet.

It will cause mypy to silently accept some buggy code, such as
this example -- it's not recommended if you can avoid it:

.. code-block:: python

   def inc(x: int) -> int:
       return x + 1

   x = inc(None)  # No error reported by mypy if strict optional mode disabled!

However, making code "optional clean" can take some work! You can also use
:ref:`the mypy configuration file <config-file>` to migrate your code
to strict optional checking one file at a time, since there exists
the :ref:`per-module flag <config-file-none-and-optional-handling>`
``strict_optional`` to control strict optional mode.

Often it's still useful to document whether a variable can be
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

You can still use :py:data:`Optional[t] <typing.Optional>` to document that ``None`` is a
valid argument type, even if strict ``None`` checking is not
enabled:

.. code-block:: python

    from typing import Optional

    def greeting(name: Optional[str]) -> str:
        if name:
            return 'Hello, {}'.format(name)
        else:
            return 'Hello, stranger'

Mypy treats this as semantically equivalent to the previous example
if strict optional checking is disabled, since ``None`` is implicitly
valid for any type, but it's much more
useful for a programmer who is reading the code. This also makes
it easier to migrate to strict ``None`` checking in the future.

Class name forward references
*****************************

Python does not allow references to a class object before the class is
defined. Thus this code does not work as expected:

.. code-block:: python

   def f(x: A) -> None:  # Error: Name A not defined
       ...

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

.. note::

    A type alias does not create a new type. It's just a shorthand notation for
    another type -- it's equivalent to the target type except for
    :ref:`generic aliases <generic-type-aliases>`.

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

If you use :py:func:`namedtuple <collections.namedtuple>` to define your named tuple, all the items
are assumed to have ``Any`` types. That is, mypy doesn't know anything
about item types. You can use :py:class:`~typing.NamedTuple` to also define
item types:

.. code-block:: python

    from typing import NamedTuple

    Point = NamedTuple('Point', [('x', int),
                                 ('y', int)])
    p = Point(x=1, y='x')  # Argument has incompatible type "str"; expected "int"

Python 3.6 introduced an alternative, class-based syntax for named tuples with types:

.. code-block:: python

    from typing import NamedTuple

    class Point(NamedTuple):
        x: int
        y: int

    p = Point(x=1, y='x')  # Argument has incompatible type "str"; expected "int"

.. _type-of-class:

The type of class objects
*************************

(Freely after :pep:`PEP 484: The type of class objects
<484#the-type-of-class-objects>`.)

Sometimes you want to talk about class objects that inherit from a
given class.  This can be spelled as :py:class:`Type[C] <typing.Type>` where ``C`` is a
class.  In other words, when ``C`` is the name of a class, using ``C``
to annotate an argument declares that the argument is an instance of
``C`` (or of a subclass of ``C``), but using :py:class:`Type[C] <typing.Type>` as an
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

How would we annotate this function?  Without :py:class:`~typing.Type` the best we
could do would be:

.. code-block:: python

   def new_user(user_class: type) -> User:
       # Same  implementation as before

This seems reasonable, except that in the following example, mypy
doesn't see that the ``buyer`` variable has type ``ProUser``:

.. code-block:: python

   buyer = new_user(ProUser)
   buyer.pay()  # Rejected, not a method on User

However, using :py:class:`~typing.Type` and a type variable with an upper bound (see
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

   The value corresponding to :py:class:`Type[C] <typing.Type>` must be an actual class
   object that's a subtype of ``C``.  Its constructor must be
   compatible with the constructor of ``C``.  If ``C`` is a type
   variable, its upper bound must be a class object.

For more details about ``Type[]`` see :pep:`PEP 484: The type of
class objects <484#the-type-of-class-objects>`.

.. _text-and-anystr:

Text and AnyStr
***************

Sometimes you may want to write a function which will accept only unicode
strings. This can be challenging to do in a codebase intended to run in
both Python 2 and Python 3 since ``str`` means something different in both
versions and ``unicode`` is not a keyword in Python 3.

To help solve this issue, use :py:class:`~typing.Text` which is aliased to
``unicode`` in Python 2 and to ``str`` in Python 3. This allows you to
indicate that a function should accept only unicode strings in a
cross-compatible way:

.. code-block:: python

   from typing import Text

   def unicode_only(s: Text) -> Text:
       return s + u'\u2713'

In other cases, you may want to write a function that will work with any
kind of string but will not let you mix two different string types. To do
so use :py:data:`~typing.AnyStr`:

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
type of either :py:class:`Iterator[YieldType] <typing.Iterator>` or :py:class:`Iterable[YieldType] <typing.Iterable>`. For example:

.. code-block:: python

   def squares(n: int) -> Iterator[int]:
       for i in range(n):
           yield i * i

If you want your generator to accept values via the :py:meth:`~generator.send` method or return
a value, you should use the
:py:class:`Generator[YieldType, SendType, ReturnType] <typing.Generator>` generic type instead. For example:

.. code-block:: python

   def echo_round() -> Generator[int, float, str]:
       sent = yield 0
       while sent >= 0:
           sent = yield round(sent)
       return 'Done'

Note that unlike many other generics in the typing module, the ``SendType`` of
:py:class:`~typing.Generator` behaves contravariantly, not covariantly or invariantly.

If you do not plan on receiving or returning values, then set the ``SendType``
or ``ReturnType`` to ``None``, as appropriate. For example, we could have
annotated the first example as the following:

.. code-block:: python

   def squares(n: int) -> Generator[int, None, None]:
       for i in range(n):
           yield i * i

This is slightly different from using ``Iterable[int]`` or ``Iterator[int]``,
since generators have :py:meth:`~generator.close`, :py:meth:`~generator.send`, and :py:meth:`~generator.throw` methods that
generic iterables don't. If you will call these methods on the returned
generator, use the :py:class:`~typing.Generator` type instead of :py:class:`~typing.Iterable` or :py:class:`~typing.Iterator`.
