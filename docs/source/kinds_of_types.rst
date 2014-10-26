Kinds of types
==============

User-defined types
******************

Each class is also a type. Any instance of a subclass is also compatible with all superclasses. All values are compatible with the object type (and also the Any type).

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

A value with the Any type is dynamically typed. Any operations are permitted on the value, and the operations are checked at runtime, similar to normal Python code. If you do not define a function return value or argument types, these default to Any. Also, a function without an explicit return type is dynamically typed. The body of a dynamically typed function is not checked statically.

Any is compatible with every other type, and vice versa. No implicit type check is inserted when assigning a value of type Any to a variable with a more precise type:

.. code-block:: python

   a, s = Undefined(Any), Undefined(str)
   a = 2      # OK
   s = a      # OK

Declared (and inferred) types are erased at runtime (they are basically treated as comments), and thus the above code does not generate a runtime error.

Tuple types
***********

The type Tuple[t, ...] represents a tuple with the item types t, ...:

.. code-block:: python

   def f(t: Tuple[int, str]) -> None:
       t = 1, 'foo'    # OK
       t = 'foo', 1    # Type check error

Class name forward references
*****************************

Python does not allow references to a class object before the class is defined. Thus this code is does not work as expected:

.. code-block:: python

   def f(x: A) -> None: # Error: Name A not defined
       ....

   class A:
       ...

In cases like these you can enter the type as a string literal — this is a *forward reference*:

.. code-block:: python

   def f(x: 'A') -> None:  # OK
       ...

   class A:
       ...

Of course, instead of using a string literal type, you could move the function definition after the class definition. This is not always desirable or even possible, though.

Any type can be entered as a string literal, and youn can combine string-literal types with non-string-literal types freely:

.. code-block:: python

   a = Undefined(List['A'])  # OK
   n = Undefined('int')      # OK, though not useful

   class A: pass

String literal types are never needed in # type comments.

Callable types and lambdas
**************************

You can pass around function objects and bound methods in statically typed code. The type of a function that accepts arguments A1, ..., An and returns Rt is Function[[A1, ..., An], Rt]. Example:

.. code-block:: python

   def twice(i: int, next: Function[[int], int]) -> int:
       return next(next(i))

   def add(i: int) -> int:
       return i + 1

   print(twice(3, add))   # 5

Lambdas are also supported. The lambda argument and return value types cannot be given explicitly; they are always inferred based on context using bidirectional type inference:

.. code-block:: python

   l = map(lambda x: x + 1, [1, 2, 3])   # infer x as int and l as List[int]

If you want to give the argument or return value types explicitly, use an ordinary, perhaps nested function definition.
