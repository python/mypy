Planned features
================

This section introduces some language features that are still work in progress.

None
----

Currently, None is a valid value for each type, similar to null or NULL in many languages. However, it is likely that this decision will be reversed, and types do not include None default. The Optional type modifier can be used to define a type variant that includes None, such as Optional(int):

.. code-block:: python

   def f() -> Optional[int]:
       return None # OK

   def g() -> int:
       ...
       return None # Error: None not compatible with int

Also, most operations would not be supported on None values:

.. code-block:: python

   def f(x: Optional[int]) -> int:
       return x + 1  # Error: Cannot add None and int

Instead, an explicit None check would be required. This would benefit from more powerful type inference:

.. code-block:: python

   def f(x: Optional[int]) -> int:
       if x is None:
           return 0
       else:
           # The inferred type of x is just int here.
           return x + 1

We would infer the type of x to be int in the else block due to the check against None in the if condition.

.. _union-types:

Union types
-----------

Python functions often accept values of two or more different types. You can use overloading to model this in statically typed code, but union types can make code like this easier to write.

Use the Union[...] type constructor to construct a union type. For example, the type Union[int, str] is compatible with both integers and strings. You can use an isinstance check to narrow down the type to a specific type:

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

More general type inference
---------------------------

It may be useful to support type inference also for variables defined in multiple locations in an if/else statement, even if the initializer types are different:

.. code-block:: python

   if x:
       y = None     # First definition of y
   else:
       y = 'a'      # Second definition of y

In the above example, both of the assignments would be used in type inference, and the type of y would be str. However, it is not obvious whether this would be generally desirable in more complex cases.
