Generics
========

Defining generic classes
************************

The built-in collection classes are generic classes. Generic types have one or more type parameters, which can be arbitrary types. For example, Dict]int, str] has the type parameters int and str, and List[int] has a type parameter int.

Programs can also define new generic classes. Here is a very simple generic class that represents a stack:

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

The Stack class can be used to represent a stack of any type: Stack[int], Stack[Tuple[int, str]], etc.

Using Stack is similar to built-in container types:

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

You may wonder what happens at runtime when you index Stack. Actually, indexing Stack just returns Stack:

>>> print(Stack)
<class '__main__.Stack'>
>>> print(Stack[int])
<class '__main__.Stack'>

Note that built-in types list, dict and so on do not support indexing in Python. This is why we have the aliases List, Dict and so on in the typing module. Indexing these aliases just gives you the target class in Python, similar to Stack:

>>> from typing import List
>>> List[int]
<class 'list'>

The above examples illustrate that type variables are erased at runtime when running in a Python VM. Generic Stack or list instances are just ordinary Python objects, and they have no extra runtime overhead or magic due to being generic, other than a metaclass that overloads the indexing operator. If you worry about the overhead introduced by the type indexing operation when constructing instances, you can often rewrite such code using a # type annotation, which has no runtime impact:

.. code-block:: python

   x = List[int]()
   x = [] # type: List[int]   # Like the above but faster.

The savings are rarely significant, but it could make a difference in a performance-critical loop or function. Function annotations, on the other hand, are only evaluated during the defintion of the function, not during every call. Constructing type objects in function signatures rarely has any noticeable performance impact.

Generic functions
*****************

Generic type variables can also be used to define generic functions:

.. code-block:: python

   from typing import typevar, Sequence

   T = typevar('T')      # Declare type variable

   def first(seq: Sequence[T]) -> T:   # Generic function
       return seq[0]

As with generic classes, the type variable can be replaced with any type. That means first can we used with any sequence type, and the return type is derived from the sequence item type. For example:

.. code-block:: python

   # Assume first defined as above.

   s = first('foo')      # s has type str.
   n = first([1, 2, 3])  # n has type int.

Note also that a single definition of a type variable (such as T above) can be used in multiple generic functions or classes. In this example we use the same type variable in two generic functions:

.. code-block:: python

   from typing typevar, Sequence

   T = typevar('T')      # Declare type variable

   def first(seq: Sequence[T]) -> T:
       return seq[0]

   def last(seq: Sequence[T]) -> T:
       return seq[-1]

You can also define generic methods — just use a type variable in the method signature that is different from class type variables.
