Dealing with common issues
==========================

Statically typed function bodies are often identical to normal Python code, but sometimes you need to do things slightly differently. This section introduces some of the most common cases which require different conventions in statically typed code.

First, you need to specify the type when creating an empty list or dict and when you assign to a new variable, as mentioned earlier:

.. code-block:: python

   a = List[int]()   # Explicit type required in statically typed code
   a = []            # Fine in a dynamically typed function, or if type
                     # of a has been declared or inferred before

Sometimes you can avoid the explicit list item type by using a list comprehension. Here a type annotation is needed:

.. code-block:: python

   l = List[int]()
   for i in range(n):
       l.append(i * i)

.. note::

   A future mypy version may be able to deal with cases such as the above without type annotations.

No type annotation needed if using a list comprehension:

.. code-block:: python

   l = [i * i for i in range(n)]

However, in more complex cases the explicit type annotation can improve the clarity of your code, whereas a complex list comprehension can make your code difficult to understand.

Second, each name within a function only has a single type. You can reuse for loop indices etc., but if you want to use a variable with multiple types within a single function, you may need to declare it with the Any type.

.. code-block:: python

   def f() -> None:
       n = 1
       ...
       n = x        # Type error: n has type int

.. note::

   This is another limitation that could be lifted in a future mypy version.

Third, sometimes the inferred type is a subtype of the desired type. The type inference uses the first assignment to infer the type of a name:

.. code-block:: python

   # Assume Shape is the base class of both Circle and Triangle.
   shape = Circle()    # Infer shape to be Circle
   ...
   shape = Triangle()  # Type error: Triangle is not a Circle

You can just give an explicit type for the variable in cases such the above example:

.. code-block:: python

   shape = Circle() # type: Shape   # The variable s can be any Shape,
                                    # not just Circle
   ...
   shape = Triangle()               # OK

Fourth, if you use isinstance tests or other kinds of runtime type tests, you may have to add casts (this is similar to instanceof tests in Java):

.. code-block:: python

   def f(o: object) -> None:
       if isinstance(o, int):
           n = cast(int, o)
           n += 1    # o += 1 would be an error
           ...

Note that the object type used in the above example is similar to Object in Java: it only supports operations defined for all objects, such as equality and isinstance(). The type Any, in contrast, supports all operations, even if they may fail at runtime. The cast above would have been unnecessary if the type of o was Any.

Some consider casual use of isinstance tests a sign of bad programming style. Often a method override or an overloaded function is a cleaner way of implementing functionality that depends on the runtime types of values. However, use whatever techniques that work for you. Sometimes isinstance tests *are* the cleanest way of implementing a piece of functionality.

Type inference in mypy is designed to work well in common cases, to be predictable and to let the type checker give useful error messages. More powerful type inference strategies often have complex and difficult-to-prefict failure modes and could result in very confusing error messages.
