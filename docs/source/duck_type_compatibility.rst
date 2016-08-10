Duck type compatibility
-----------------------

In Python, certain types are compatible even though they aren't subclasses of
each other. For example, ``int`` objects are valid whenever ``float`` objects
are expected. Mypy supports this idiom via *duck type compatibility*. As of
now, this is only supported for a small set of built-in types:

* ``int`` is duck type compatible with ``float`` and ``complex``.
* ``float`` is duck type compatible with ``complex``.
* In Python 2, ``str`` is duck type compatible with ``unicode``.

.. note::

   Mypy support for Python 2 is still work in progress.

For example, mypy considers an ``int`` object to be valid whenever a
``float`` object is expected.  Thus code like this is nice and clean
and also behaves as expected:

.. code-block:: python

   def degrees_to_radians(x: float) -> float:
       return math.pi * degrees / 180

   n = 90  # Inferred type 'int'
   print(degrees_to_radians(n))   # Okay!

.. note::

   Note that in Python 2 a ``str`` object with non-ASCII characters is
   often *not valid* when a unicode string is expected. The mypy type
   system does not consider a string with non-ASCII values as a
   separate type so some programs with this kind of error will
   silently pass type checking. In Python 3 ``str`` and ``bytes`` are
   separate, unrelated types and this kind of error is easy to
   detect. This a good reason for preferring Python 3 over Python 2!

   See :ref:`text-and-anystr` for details on how to enforce that a
   value must be a unicode string in a cross-compatible way.
