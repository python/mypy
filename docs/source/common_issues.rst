.. _common_issues:

Dealing with common issues
==========================

Statically typed function bodies are often identical to normal Python
code, but sometimes you need to do things slightly differently. This
section has examples of cases when you need to update your code
to use static typing, and ideas for working
around issues if the type checker gets confused about your code.

.. _silencing_checker:

Spurious errors and locally silencing the checker
-------------------------------------------------

You can use a ``# type: ignore`` comment to silence the type checker
on a particular line. For example, let's say our code is using
the C extension module ``frobnicate``, and there's no stub available.
Mypy will complain about this, as it has no information about the
module:

.. code-block:: python

    import frobnicate  # Error: No module "frobnicate"
    frobnicate.start()

You can add a ``# type: ignore`` comment to tell mypy to ignore this
error:

.. code-block:: python

    import frobnicate  # type: ignore
    frobnicate.start()  # Okay!

The second line is now fine, since the ignore comment causes the name
``frobnicate`` to get an implicit ``Any`` type.

Types of empty collections
--------------------------

You need to specify the type when you assign an empty list or
dict to a new variable, as mentioned earlier:

.. code-block:: python

   a = []  # type: List[int]

Without the annotation the type checker has no way of figuring out the
precise type of ``a``.

You can use a simple empty list literal in a dynamically typed function (as the
type of ``a`` would be implicitly ``Any`` and need not be inferred), or if type
of the variable has been declared or inferred before:

.. code-block:: python

   a = []  # Okay if type of a known

Sometimes you can avoid the explicit list item type by using a list
comprehension. Here a type annotation is needed:

.. code-block:: python

   l = []  # type: List[int]
   for i in range(n):
       l.append(i * i)

.. note::

   A future mypy version may be able to deal with cases such as the
   above without type annotations.

No type annotation needed if using a list comprehension:

.. code-block:: python

   l = [i * i for i in range(n)]

However, in more complex cases the explicit type annotation can
improve the clarity of your code, whereas a complex list comprehension
can make your code difficult to understand.

Redefinitions with incompatible types
-------------------------------------

Each name within a function only has a single 'declared' type. You can
reuse for loop indices etc., but if you want to use a variable with
multiple types within a single function, you may need to declare it
with the ``Any`` type.

.. code-block:: python

   def f() -> None:
       n = 1
       ...
       n = 'x'        # Type error: n has type int

.. note::

   This is another limitation that could be lifted in a future mypy
   version.

Note that you can redefine a variable with a more *precise* or a more
concrete type. For example, you can redefine a sequence (which does
not support ``sort()``) as a list and sort it in-place:

.. code-block:: python

    def f(x: Sequence[int]) -> None:
        # Type of x is Sequence[int] here; we don't know the concrete type.
        x = list(x)
        # Type of x is List[int] here.
        x.sort()  # Okay!

Declaring a supertype as variable type
--------------------------------------

Sometimes the inferred type is a subtype (subclass) of the desired
type. The type inference uses the first assignment to infer the type
of a name (assume here that ``Shape`` is the base class of both
``Circle`` and ``Triangle``):

.. code-block:: python

   shape = Circle()    # Infer shape to be Circle
   ...
   shape = Triangle()  # Type error: Triangle is not a Circle

You can just give an explicit type for the variable in cases such the
above example:

.. code-block:: python

   shape = Circle() # type: Shape   # The variable s can be any Shape,
                                    # not just Circle
   ...
   shape = Triangle()               # OK

Complex isinstance tests
------------------------

If you use ``isinstance()`` tests or other kinds of runtime type
tests, you may have to add casts (this is similar to ``instanceof`` tests
in Java):

.. code-block:: python

   def f(o: object, x: int) -> None:
       if isinstance(o, int) and x > 1:
           n = cast(int, o)
           g(n + 1)    # o + 1 would be an error
           ...

.. note::

    Note that the ``object`` type used in the above example is similar
    to ``Object`` in Java: it only supports operations defined for *all*
    objects, such as equality and ``isinstance()``. The type ``Any``,
    in contrast, supports all operations, even if they may fail at
    runtime. The cast above would have been unnecessary if the type of
    ``o`` was ``Any``.

Mypy can't infer the type of ``o`` after the ``isinstance()`` check
because of the ``and`` operator (this limitation will likely be lifted
in the future).  We can write the above code without a cast by using a
nested if statement:

.. code-block:: python

   def f(o: object, x: int) -> None:
       if isinstance(o, int):  # Mypy understands a lone isinstance check
           if x > 1:
               g(o + 1)        # Okay; type of o is inferred as int here
           ...

Some consider casual use of ``isinstance()`` tests a sign of bad
programming style. Often a method override or a ``hasattr`` check
is a cleaner way of implementing functionality that depends on the
runtime types of values. However, use whatever techniques that work
for you. Sometimes ``isinstance`` tests *are* the cleanest way of
implementing a piece of functionality.

Type inference in mypy is designed to work well in common cases, to be
predictable and to let the type checker give useful error
messages. More powerful type inference strategies often have complex
and difficult-to-predict failure modes and could result in very
confusing error messages. The tradeoff is that you as a programmer
sometimes have to give the type checker a little help.
