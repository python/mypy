Duck type compatibility
-----------------------

In Python, certain types are compatible even though they aren't subclasses of
each other. For example, ``int`` objects are valid whenever ``float`` objects
are expected. Mypy supports this idiom via *duck type compatibility*. This is
supported for a small set of built-in types:

* ``int`` is duck type compatible with ``float`` and ``complex``.
* ``float`` is duck type compatible with ``complex``.
* In Python 2, ``str`` is duck type compatible with ``unicode``.

For example, mypy considers an ``int`` object to be valid whenever a
``float`` object is expected.  Thus code like this is nice and clean
and also behaves as expected:

.. code-block:: python

   import math

   def degrees_to_radians(degrees: float) -> float:
       return math.pi * degrees / 180

   n = 90  # Inferred type 'int'
   print(degrees_to_radians(n))  # Okay!

You can also often use :ref:`protocol-types` to achieve a similar effect in
a more principled and extensible fashion. Protocols don't apply to
cases like ``int`` being compatible with ``float``, since ``float`` is not
a protocol class but a regular, concrete class, and many standard library
functions expect concrete instances of ``float`` (or ``int``).

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
