Dynamically typed code
======================

As mentioned earlier, bodies of functions that don't have have an
explicit return type are dynamically typed (operations are checked at
runtime). Code outside functions is statically typed by default, and
types of variables are inferred. This does usually the right thing,
but you can also make any variable dynamically typed by defining it
explicitly with the type ``Any``:

.. code-block:: python

   from typing import Any

   s = 1                 # Statically typed (type int)
   d = 1  # type: Any    # Dynamically typed (type Any)
   s = 'x'               # Type check error
   d = 'x'               # OK

Operations on Any values
------------------------

You can do anything using a value with type ``Any``, and type checker
does not complain:

.. code-block:: python

    def f(x: Any) -> int:
        # All of these are valid!
        x.foobar(1, y=2)
        print(x[3] + 'f')
        if x:
            x.z = x(2)
        open(x).read()
        return x

Values derived from an ``Any`` value also have the value ``Any``
implicitly. For example, if you get the attribute of an ``Any``
value or call a ``Any`` value the result is ``Any``:

.. code-block:: python

    def f(x: Any) -> None:
        y = x.foo()  # y has type Any
        y.bar()      # Okay as well!

Any vs. object
--------------

The type ``object`` is another type that can have an instance of arbitrary
type as a value. Unlike ``Any``, ``object`` is an ordinary static type (it
is similar to ``Object`` in Java), and only operations valid for *all*
types are accepted for ``object`` values. These are all valid:

.. code-block:: python

    def f(o: object) -> None:
        if o:
            print(o)
        print(isinstance(o, int))
        o = 2
        o = 'foo'

These are, however, flagged as errors, since not all objects support these
operations:

.. code-block:: python

    def f(o: object) -> None:
        o.foo()       # Error!
        o + 2         # Error!
        open(o)       # Error!
        n = Undefined(int)
        n = o         # Error!

You can use ``cast()`` (see chapter :ref:`casts`) to go from a general
type such as ``object`` to a more specific type (subtype) such as
``int``.  ``cast()`` is not needed with dynamically typed values
(values with type ``Any``).
