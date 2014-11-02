Duck type compatibility
-----------------------

In Python, certain types are compatible even though they aren't subclasses of
each other. For example, ``int`` objects are valid whenever ``float`` objects
are expected. Mypy supports this idiom via *duck type compatibility*. You can
specify a type to be a valid substitute for another type using the ``ducktype``
class decorator:

.. code-block:: python

    from typing import ducktype

    @ducktype(str)
    class MyString:
        def __init__(self, ...): ...
        ...

Now mypy considers a ``MyString`` instance to be valid whenever a
``str`` object is expected, independent of whether ``MyString``
actually is a perfect substitute for strings. You can think of this as
a class-level cast as opposed to a value-level cast. This is a powerful
feature but you can easily abuse it and make it easy to write programs
that pass type checking but will crash and burn when run!

The most common case where ``ducktype`` is useful is for certain
well-known standard library classes:

* ``int`` is duck type compatible with ``float``
* ``float`` is duck type compatible with ``complex``.

Thus code like this is nice and clean and also behaves as expected:

.. code-block:: python

   def degrees_to_radians(x: float) -> float:
       return math.pi * degrees / 180

   n = 90  # Inferred type 'int'
   print(degrees_to_radians(n))   # Okay!

Also, in Python 2 ``str`` would be duck type compatible with ``unicode``.

.. note::

   Note that in Python 2 a ``str`` object with non-ASCII characters is
   often *not valid* when a unicode string is expected. The mypy type
   system does not consider a string with non-ASCII values as a
   separate type so some programs with this kind of error will
   silently pass type checking. In Python 3 ``str`` and ``bytes`` are
   separate, unrelated types and this kind of error is easy to
   detect. This a good reason for preferring Python 3 over Python 2!

.. note::

   Mypy support for Python 2 is still work in progress.
