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

A value with the ``Any`` type is dynamically typed. Any operations are
permitted on the value, and the operations are checked at runtime,
similar to normal Python code. If you do not define a function return
value or argument types, these default to ``Any``. Also, a function
without an explicit return type is dynamically typed. The body of a
dynamically typed function is not checked statically.

``Any`` is compatible with every other type, and vice versa. No
implicit type check is inserted when assigning a value of type ``Any``
to a variable with a more precise type:

.. code-block:: python

   a, s = Undefined(Any), Undefined(str)
   a = 2      # OK
   s = a      # OK

Declared (and inferred) types are erased at runtime (they are
basically treated as comments), and thus the above code does not
generate a runtime error.

Tuple types
***********

The type ``Tuple[T1, ..., Tn]`` represents a tuple with the item types ``T1``, |...|, ``Tn``:

.. code-block:: python

   def f(t: Tuple[int, str]) -> None:
       t = 1, 'foo'    # OK
       t = 'foo', 1    # Type check error

Callable types (and lambdas)
****************************

You can pass around function objects and bound methods in statically
typed code. The type of a function that accepts arguments ``A1``, |...|, ``An``
and returns ``Rt`` is ``Callable[[A1, ..., An], Rt]``. Example:

.. code-block:: python

   def twice(i: int, next: Callable[[int], int]) -> int:
       return next(next(i))

   def add(i: int) -> int:
       return i + 1

   print(twice(3, add))   # 5

Lambdas are also supported. The lambda argument and return value types
cannot be given explicitly; they are always inferred based on context
using bidirectional type inference:

.. code-block:: python

   l = map(lambda x: x + 1, [1, 2, 3])   # infer x as int and l as List[int]

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

Class name forward references
*****************************

Python does not allow references to a class object before the class is
defined. Thus this code is does not work as expected:

.. code-block:: python

   def f(x: A) -> None: # Error: Name A not defined
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

Any type can be entered as a string literal, and youn can combine
string-literal types with non-string-literal types freely:

.. code-block:: python

   a = Undefined(List['A'])  # OK
   n = Undefined('int')      # OK, though not useful

   class A: pass

String literal types are never needed in ``# type:`` comments.

Type aliases
************

In certain situations, type names may end up being long and painful to type:

.. code-block:: python
   
   def f() -> Union[List[Dict[Tuple[int, str], Set[int]]], Tuple[str, List[str]]]:
      ...

When cases like this arise, you can define a type alias by simply assigning the type to a variable:

.. code-block:: python
   
   MagicType = Union[List[Dict[Tuple[int, str], Set[int]]], Tuple[str, List[str]]]
   # now we can use MagicType in place of the full name
   def f() -> MagicType():
      ...

Of course, you can also instantinate type aliases:

.. code-block:: python
   
   t = MagicType(('abc', []))
