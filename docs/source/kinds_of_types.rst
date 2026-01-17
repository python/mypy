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

This should not be confused with the
:py:class:`object` type, which represents the set of all values.
Unlike ``object``, ``Any`` introduces type unsafety — see
:ref:`any-vs-object` for more.

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

The type ``tuple[T1, ..., Tn]`` represents a tuple with the item types ``T1``, ..., ``Tn``:

.. code-block:: python

   # Use `typing.Tuple` in Python 3.8 and earlier
   def f(t: tuple[int, str]) -> None:
       t = 1, 'foo'    # OK
       t = 'foo', 1    # Type check error

A tuple type of this kind has exactly a specific number of items (2 in
the above example). Tuples can also be used as immutable,
varying-length sequences. You can use the type ``tuple[T, ...]`` (with
a literal ``...`` -- it's part of the syntax) for this
purpose. Example:

.. code-block:: python

    def print_squared(t: tuple[int, ...]) -> None:
        for n in t:
            print(n, n ** 2)

    print_squared(())           # OK
    print_squared((1, 3, 5))    # OK
    print_squared([1, 2])       # Error: only a tuple is valid

.. note::

   Usually it's a better idea to use ``Sequence[T]`` instead of ``tuple[T, ...]``, as
   :py:class:`~collections.abc.Sequence` is also compatible with lists and other non-tuple sequences.

.. note::

   ``tuple[...]`` is valid as a base class in Python 3.6 and later, and
   always in stub files. In earlier Python versions you can sometimes work around this
   limitation by using a named tuple as a base class (see section :ref:`named-tuples`).

.. _callable-types:

Callable types (and lambdas)
****************************

You can pass around function objects and bound methods in statically
typed code. The type of a function that accepts arguments ``A1``, ..., ``An``
and returns ``Rt`` is ``Callable[[A1, ..., An], Rt]``. Example:

.. code-block:: python

   from collections.abc import Callable

   def twice(i: int, next: Callable[[int], int]) -> int:
       return next(next(i))

   def add(i: int) -> int:
       return i + 1

   print(twice(3, add))   # 5

.. note::

    Import :py:data:`Callable[...] <typing.Callable>` from ``typing`` instead
    of ``collections.abc`` if you use Python 3.8 or earlier.

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

   from collections.abc import Callable

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

   l = map(lambda x: x + 1, [1, 2, 3])   # Infer x as int and l as list[int]

If you want to give the argument or return value types explicitly, use
an ordinary, perhaps nested function definition.

Callables can also be used against type objects, matching their
``__init__`` or ``__new__`` signature:

.. code-block:: python

    from collections.abc import Callable

    class C:
        def __init__(self, app: str) -> None:
            pass

    CallableType = Callable[[str], C]

    def class_or_callable(arg: CallableType) -> None:
        inst = arg("my_app")
        reveal_type(inst)  # Revealed type is "C"

This is useful if you want ``arg`` to be either a ``Callable`` returning an
instance of ``C`` or the type of ``C`` itself. This also works with
:ref:`callback protocols <callback_protocols>`.


.. _union-types:
.. _alternative_union_syntax:

Union types
***********

Python functions often accept values of two or more different
types. You can use :ref:`overloading <function-overloading>` to
represent this, but union types are often more convenient.

Use ``T1 | ... | Tn`` to construct a union
type. For example, if an argument has type ``int | str``, both
integers and strings are valid argument values.

You can use an :py:func:`isinstance` check to narrow down a union type to a
more specific type:

.. code-block:: python

   def f(x: int | str) -> None:
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

Python 3.9 and older only partially support this syntax. Instead, you can
use the legacy ``Union[T1, ..., Tn]`` type constructor. Example:

.. code-block:: python

   from typing import Union

   def f(x: Union[int, str]) -> None:
       ...

It is also possible to use the new syntax with versions of Python where it
isn't supported by the runtime with some limitations, if you use
``from __future__ import annotations`` (see :ref:`runtime_troubles`):

.. code-block:: python

   from __future__ import annotations

   def f(x: int | str) -> None:   # OK on Python 3.7 and later
       ...

.. _no-strict-optional:
.. _strict_optional:

Optional types and the None type
********************************

You can use ``T | None`` to define a type variant that allows ``None`` values,
such as ``int | None``. This is called an *optional type*:

.. code-block:: python

   def strlen(s: str) -> int | None:
       if not s:
           return None  # OK
       return len(s)

   def strlen_invalid(s: str) -> int:
       if not s:
           return None  # Error: None not compatible with int
       return len(s)

To support Python 3.9 and earlier, you can use the :py:data:`~typing.Optional`
type modifier instead, such as ``Optional[int]`` (``Optional[X]`` is
the preferred shorthand for ``Union[X, None]``):

.. code-block:: python

   from typing import Optional

   def strlen(s: str) -> Optional[int]:
       ...

Most operations will not be allowed on unguarded ``None`` or *optional* values
(values with an optional type):

.. code-block:: python

   def my_inc(x: int | None) -> int:
       return x + 1  # Error: Cannot add None and int

Instead, an explicit ``None`` check is required. Mypy has
powerful type inference that lets you use regular Python
idioms to guard against ``None`` values. For example, mypy
recognizes ``is None`` checks:

.. code-block:: python

   def my_inc(x: int | None) -> int:
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

   def concat(x: str | None, y: str | None) -> str | None:
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
       path: str | None = None

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
This is why you need to annotate an attribute in cases like the class
``Resource`` above:

.. code-block:: python

    class Resource:
        path: str | None = None
        ...

This also works for attributes defined within methods:

.. code-block:: python

    class Counter:
        def __init__(self) -> None:
            self.count: int | None = None

Often it's easier to not use any initial value for an attribute.
This way you don't need to use an optional type and can avoid ``assert ... is not None``
checks. No initial value is needed if you annotate an attribute in the class body:

.. code-block:: python

   class Container:
       items: list[str]  # No initial value

Mypy generally uses the first assignment to a variable to
infer the type of the variable. However, if you assign both a ``None``
value and a non-``None`` value in the same scope, mypy can usually do
the right thing without an annotation:

.. code-block:: python

   def f(i: int) -> None:
       n = None  # Inferred type 'int | None' because of the assignment below
       if i > 0:
            n = i
       ...

Sometimes you may get the error "Cannot determine type of <something>". In this
case you should add an explicit ``... | None`` annotation.

.. note::

   ``None`` is a type with only one value, ``None``. ``None`` is also used
   as the return type for functions that don't return a value, i.e. functions
   that implicitly return ``None``.

.. note::

   The Python interpreter internally uses the name ``NoneType`` for
   the type of ``None``, but ``None`` is always used in type
   annotations. The latter is shorter and reads better. (``NoneType``
   is available as :py:data:`types.NoneType` on Python 3.10+, but is
   not exposed at all on earlier versions of Python.)

.. note::

    The type ``Optional[T]`` *does not* mean a function parameter with a default value.
    It simply means that ``None`` is a valid argument value. This is
    a common confusion because ``None`` is a common default value for parameters,
    and parameters with default values are sometimes called *optional* parameters
    (or arguments).

.. _type-aliases:

Type aliases
************

In certain situations, type names may end up being long and painful to type,
especially if they are used frequently:

.. code-block:: python

   def f() -> list[dict[tuple[int, str], set[int]]] | tuple[str, list[str]]:
       ...

When cases like this arise, you can define a type alias by simply
assigning the type to a variable (this is an *implicit type alias*):

.. code-block:: python

   AliasType = list[dict[tuple[int, str], set[int]]] | tuple[str, list[str]]

   # Now we can use AliasType in place of the full name:

   def f() -> AliasType:
       ...

.. note::

    A type alias does not create a new type. It's just a shorthand notation for
    another type -- it's equivalent to the target type except for
    :ref:`generic aliases <generic-type-aliases>`.

Python 3.12 introduced the ``type`` statement for defining *explicit type aliases*.
Explicit type aliases are unambiguous and can also improve readability by
making the intent clear:

.. code-block:: python

   type AliasType = list[dict[tuple[int, str], set[int]]] | tuple[str, list[str]]

   # Now we can use AliasType in place of the full name:

   def f() -> AliasType:
       ...

There can be confusion about exactly when an assignment defines an implicit type alias --
for example, when the alias contains forward references, invalid types, or violates some other
restrictions on type alias declarations.  Because the
distinction between an unannotated variable and a type alias is implicit,
ambiguous or incorrect type alias declarations default to defining
a normal variable instead of a type alias.

Aliases defined using the ``type`` statement have these properties, which
distinguish them from implicit type aliases:

* The definition may contain forward references without having to use string
  literal escaping, since it is evaluated lazily.
* The alias can be used in type annotations, type arguments, and casts, but
  it can't be used in contexts which require a class object. For example, it's
  not valid as a base class and it can't be used to construct instances.

There is also use an older syntax for defining explicit type aliases, which was
introduced in Python 3.10 (:pep:`613`):

.. code-block:: python

   from typing import TypeAlias  # "from typing_extensions" in Python 3.9 and earlier

   AliasType: TypeAlias = list[dict[tuple[int, str], set[int]]] | tuple[str, list[str]]

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

.. note::

  You can use the raw ``NamedTuple`` "pseudo-class" in type annotations
  if any ``NamedTuple`` object is valid.

  For example, it can be useful for deserialization:

  .. code-block:: python

    def deserialize_named_tuple(arg: NamedTuple) -> Dict[str, Any]:
        return arg._asdict()

    Point = namedtuple('Point', ['x', 'y'])
    Person = NamedTuple('Person', [('name', str), ('age', int)])

    deserialize_named_tuple(Point(x=1, y=2))  # ok
    deserialize_named_tuple(Person(name='Nikita', age=18))  # ok

    # Error: Argument 1 to "deserialize_named_tuple" has incompatible type
    # "Tuple[int, int]"; expected "NamedTuple"
    deserialize_named_tuple((1, 2))

  Note that this behavior is highly experimental, non-standard,
  and may not be supported by other type checkers and IDEs.

.. _type-of-class:

The type of class objects
*************************

(Freely after :pep:`PEP 484: The type of class objects
<484#the-type-of-class-objects>`.)

Sometimes you want to talk about class objects that inherit from a
given class.  This can be spelled as ``type[C]`` (or, on Python 3.8 and lower,
:py:class:`typing.Type[C] <typing.Type>`) where ``C`` is a
class.  In other words, when ``C`` is the name of a class, using ``C``
to annotate an argument declares that the argument is an instance of
``C`` (or of a subclass of ``C``), but using ``type[C]`` as an
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

How would we annotate this function?  Without the ability to parameterize ``type``, the best we
could do would be:

.. code-block:: python

   def new_user(user_class: type) -> User:
       # Same  implementation as before

This seems reasonable, except that in the following example, mypy
doesn't see that the ``buyer`` variable has type ``ProUser``:

.. code-block:: python

   buyer = new_user(ProUser)
   buyer.pay()  # Rejected, not a method on User

However, using the ``type[C]`` syntax and a type variable with an upper bound (see
:ref:`type-variable-upper-bound`) we can do better (Python 3.12 syntax):

.. code-block:: python

   def new_user[U: User](user_class: type[U]) -> U:
       # Same implementation as before

Here is the example using the legacy syntax (Python 3.11 and earlier):

.. code-block:: python

   U = TypeVar('U', bound=User)

   def new_user(user_class: type[U]) -> U:
       # Same implementation as before

Now mypy will infer the correct type of the result when we call
``new_user()`` with a specific subclass of ``User``:

.. code-block:: python

   beginner = new_user(BasicUser)  # Inferred type is BasicUser
   beginner.upgrade()  # OK

.. note::

   The value corresponding to ``type[C]`` must be an actual class
   object that's a subtype of ``C``.  Its constructor must be
   compatible with the constructor of ``C``.  If ``C`` is a type
   variable, its upper bound must be a class object.

For more details about ``type[]`` and :py:class:`typing.Type[] <typing.Type>`, see :pep:`PEP 484: The type of
class objects <484#the-type-of-class-objects>`.

.. _generators:

Generators
**********

A basic generator that only yields values can be succinctly annotated as having a return
type of either :py:class:`Iterator[YieldType] <typing.Iterator>` or :py:class:`Iterable[YieldType] <typing.Iterable>`. For example:

.. code-block:: python

   def squares(n: int) -> Iterator[int]:
       for i in range(n):
           yield i * i

A good rule of thumb is to annotate functions with the most specific return
type possible. However, you should also take care to avoid leaking implementation
details into a function's public API. In keeping with these two principles, prefer
:py:class:`Iterator[YieldType] <typing.Iterator>` over
:py:class:`Iterable[YieldType] <typing.Iterable>` as the return-type annotation for a
generator function, as it lets mypy know that users are able to call :py:func:`next` on
the object returned by the function. Nonetheless, bear in mind that ``Iterable`` may
sometimes be the better option, if you consider it an implementation detail that
``next()`` can be called on the object returned by your function.

If you want your generator to accept values via the :py:meth:`~generator.send` method or return
a value, on the other hand, you should use the
:py:class:`Generator[YieldType, SendType, ReturnType] <typing.Generator>` generic type instead of
either ``Iterator`` or ``Iterable``. For example:

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

This is slightly different from using ``Iterator[int]`` or ``Iterable[int]``,
since generators have :py:meth:`~generator.close`, :py:meth:`~generator.send`, and :py:meth:`~generator.throw` methods that
generic iterators and iterables don't. If you plan to call these methods on the returned
generator, use the :py:class:`~typing.Generator` type instead of :py:class:`~typing.Iterator` or :py:class:`~typing.Iterable`.
