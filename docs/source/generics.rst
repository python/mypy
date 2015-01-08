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

   from typing import typevar, Generic

   T = typevar('T')

   class Stack(Generic[T]):
       def __init__(self) -> None:
           self.items = List[T]()  # Create an empty list with items of type T

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

   stack = Stack[int]()   # Construct an empty Stack[int] instance
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
operator. If you worry about the overhead introduced by the type
indexing operation when constructing instances, you can usually
rewrite such code using a ``# type:`` annotation, which has no runtime
impact:

.. code-block:: python

   x = List[int]()
   x = [] # type: List[int]   # Like the above but faster.

The savings are rarely significant, but it could make a difference in
a performance-critical loop or function. Function annotations, on the
other hand, are only evaluated during the defintion of the function,
not during every call. Constructing type objects in function
signatures rarely has any noticeable performance impact.

.. _generic-functions:

Generic functions
*****************

Generic type variables can also be used to define generic functions:

.. code-block:: python

   from typing import typevar, Sequence

   T = typevar('T')      # Declare type variable

   def first(seq: Sequence[T]) -> T:   # Generic function
       return seq[0]

As with generic classes, the type variable can be replaced with any
type. That means first can we used with any sequence type, and the
return type is derived from the sequence item type. For example:

.. code-block:: python

   # Assume first defined as above.

   s = first('foo')      # s has type str.
   n = first([1, 2, 3])  # n has type int.

Note also that a single definition of a type variable (such as ``T``
above) can be used in multiple generic functions or classes. In this
example we use the same type variable in two generic functions:

.. code-block:: python

   from typing typevar, Sequence

   T = typevar('T')      # Declare type variable

   def first(seq: Sequence[T]) -> T:
       return seq[0]

   def last(seq: Sequence[T]) -> T:
       return seq[-1]

You can also define generic methods — just use a type variable in the
method signature that is different from class type variables.

Type variables with value restriction
*************************************

By default, a type variable can be replaced with any type. However, sometimes
it's useful to have a type variable that can only have some specific types
as its value. A typical example is a type variable that can only have values
``str`` and ``bytes``:

.. code-block:: python

   from typing import typevar

   AnyStr = typevar('AnyStr', values=(str, bytes))

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

The original, valid definition of ``concat`` is more or less
equivalent to this overloaded function, but it's much shorter,
cleaner and more efficient:

.. code-block:: python

   @overload
   def overload_concat(x: str, y: str) -> str:
       return x + y

   @overload
   def overload_concat(x: bytes, y: bytes) -> bytes:
       return x + y

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

You can also use a ``typevar`` with ``values`` when defining a generic
class. For example, mypy uses the type ``typing.Pattern[AnyStr]`` for the
return value of ``re.compile``, since regular expressions can be based
on a string or a bytes pattern.
