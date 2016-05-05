Generics
========

Defining generic classes
************************

The built-in collection classes are generic classes. Generic types
have one or more type parameters, which can be arbitrary types. For
example, ``Dict[int, str]`` has the type parameters ``int`` and
``str``, and ``List[int]`` has a type parameter ``int``.

Programs can also define new generic classes. Here is a very simple
generic class that represents a stack:

.. code-block:: python

   from typing import TypeVar, Generic

   T = TypeVar('T')

   class Stack(Generic[T]):
       def __init__(self) -> None:
           # Create an empty list with items of type T
           self.items = []  # type: List[T]

       def push(self, item: T) -> None:
           self.items.append(item)

       def pop(self) -> T:
           return self.items.pop()

       def empty(self) -> bool:
           return not self.items

The ``Stack`` class can be used to represent a stack of any type:
``Stack[int]``, ``Stack[Tuple[int, str]]``, etc.

Using ``Stack`` is similar to built-in container types:

.. code-block:: python

   # Construct an empty Stack[int] instance
   stack = Stack()  # type: Stack[int]
   stack.push(2)
   stack.pop()
   stack.push('x')        # Type error

Type inference works for user-defined generic types as well:

.. code-block:: python

   def process(stack: Stack[int]) -> None: ...

   process(Stack())   # Argument has inferred type Stack[int]

Generic class internals
***********************

You may wonder what happens at runtime when you index
``Stack``. Actually, indexing ``Stack`` just returns ``Stack``:

>>> print(Stack)
<class '__main__.Stack'>
>>> print(Stack[int])
<class '__main__.Stack'>

Note that built-in types ``list``, ``dict`` and so on do not support
indexing in Python. This is why we have the aliases ``List``, ``Dict``
and so on in the ``typing`` module. Indexing these aliases just gives
you the target class in Python, similar to ``Stack``:

>>> from typing import List
>>> List[int]
<class 'list'>

The above examples illustrate that type variables are erased at
runtime. Generic ``Stack`` or ``list`` instances are just ordinary
Python objects, and they have no extra runtime overhead or magic due
to being generic, other than a metaclass that overloads the indexing
operator.

.. _generic-functions:

Generic functions
*****************

Generic type variables can also be used to define generic functions:

.. code-block:: python

   from typing import TypeVar, Sequence

   T = TypeVar('T')      # Declare type variable

   def first(seq: Sequence[T]) -> T:   # Generic function
       return seq[0]

As with generic classes, the type variable can be replaced with any
type. That means ``first`` can be used with any sequence type, and the
return type is derived from the sequence item type. For example:

.. code-block:: python

   # Assume first defined as above.

   s = first('foo')      # s has type str.
   n = first([1, 2, 3])  # n has type int.

Note also that a single definition of a type variable (such as ``T``
above) can be used in multiple generic functions or classes. In this
example we use the same type variable in two generic functions:

.. code-block:: python

   from typing TypeVar, Sequence

   T = TypeVar('T')      # Declare type variable

   def first(seq: Sequence[T]) -> T:
       return seq[0]

   def last(seq: Sequence[T]) -> T:
       return seq[-1]

You can also define generic methods — just use a type variable in the
method signature that is different from class type variables.

.. _type-variable-value-restriction:

Type variables with value restriction
*************************************

By default, a type variable can be replaced with any type. However, sometimes
it's useful to have a type variable that can only have some specific types
as its value. A typical example is a type variable that can only have values
``str`` and ``bytes``:

.. code-block:: python

   from typing import TypeVar

   AnyStr = TypeVar('AnyStr', str, bytes)

This is actually such a common type variable that ``AnyStr`` is
defined in ``typing`` and we don't need to define it ourselves.

We can use ``AnyStr`` to define a function that can concatenate
two strings or bytes objects, but it can't be called with other
argument types:

.. code-block:: python

   from typing import AnyStr

   def concat(x: AnyStr, y: AnyStr) -> AnyStr:
       return x + y

   concat('a', 'b')    # Okay
   concat(b'a', b'b')  # Okay
   concat(1, 2)        # Error!

Note that this is different from a union type, since combinations
of ``str`` and ``bytes`` are not accepted:

.. code-block:: python

   concat('string', b'bytes')   # Error!

In this case, this is exactly what we want, since it's not possible
to concatenate a string and a bytes object! The type checker
will reject this function:

.. code-block:: python

   def union_concat(x: Union[str, bytes], y: Union[str, bytes]) -> Union[str, bytes]:
       return x + y  # Error: can't concatenate str and bytes

Another interesting special case is calling ``concat()`` with a
subtype of ``str``:

.. code-block:: python

    class S(str): pass

    ss = concat(S('foo'), S('bar')))

You may expect that the type of ``ss`` is ``S``, but the type is
actually ``str``: a subtype gets promoted to one of the valid values
for the type variable, which in this case is ``str``. This is thus
subtly different from *bounded quantification* in languages such as
Java, where the return type would be ``S``. The way mypy implements
this is correct for ``concat``, since ``concat`` actually returns a
``str`` instance in the above example:

.. code-block:: python

    >>> print(type(ss))
    <class 'str'>

You can also use a ``TypeVar`` with a restricted set of possible
values when defining a generic class. For example, mypy uses the type
``typing.Pattern[AnyStr]`` for the return value of ``re.compile``,
since regular expressions can be based on a string or a bytes pattern.

.. _type-variable-upper-bound:

Type variables with upper bounds
********************************

A type variable can also be restricted to having values that are
subtypes of a specific type. This type is called the upper bound of
the type variable, and is specified with the ``bound=...`` keyword
argument to ``TypeVar``.

.. code-block:: python

   from typing import TypeVar, SupportsAbs

   T = TypeVar('T', bound=SupportsAbs[float])

In the definition of a generic function that uses such a type variable
``T``, the type represented by ``T`` is assumed to be a subtype of
its upper bound, so the function can use methods of the upper bound on
values of type ``T``.

.. code-block:: python

   def largest_in_absolute_value(*xs: T) -> T:
       return max(xs, key=abs)  # Okay, because T is a subtype of SupportsAbs[float].

In a call to such a function, the type ``T`` must be replaced by a
type that is a subtype of its upper bound. Continuing the example
above,

.. code-block:: python

   largest_in_absolute_value(-3.5, 2)   # Okay, has type float.
   largest_in_absolute_value(5+6j, 7)   # Okay, has type complex.
   largest_in_absolute_value('a', 'b')  # Error: 'str' is not a subtype of SupportsAbs[float].

Type parameters of generic classes may also have upper bounds, which
restrict the valid values for the type parameter in the same way.

A type variable may not have both a value restriction (see
:ref:`type-variable-value-restriction`) and an upper bound.

One common application of type variable upper bounds is in declaring
the types of decorators that do not change the type of the function
they decorate:

.. code-block:: python

   from typing import TypeVar, Callable, Any

   AnyCallable = TypeVar('AnyCallable', bound=Callable[..., Any])

   def my_decorator(f: AnyCallable) -> AnyCallable: ...

   @my_decorator
   def my_function(x: int, y: str) -> bool:
       ...

The decorated ``my_function`` still has type ``Callable[[int, str],
bool]``. Due to the bound on ``AnyCallable``, an application of the
decorator to a non-function like ``my_decorator(1)`` will be rejected.
