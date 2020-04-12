Miscellaneous native operations
===============================

We document various generic operations that have custom
implementations here. Operations specific to various primitive types
are described later. Type-specific operations are often faster than
the generic operations described here.

If a function or method has no native implementation, mypyc will fall
back to a generic implementation that works always but is not as fast.

Functions
---------

* ``isinstance(obj, type: type)``
* ``isinstance(obj, type: tuple)``
* ``type(obj)``
* ``len(obj)``
* ``id(obj)``
* ``iter(obj)``
* ``next(iter: Iterator)``
* ``hash(obj)``
* ``getattr(obj, attr)``
* ``getattr(obj, attr, default)``
* ``setattr(obj, attr, value)``
* ``hasattr(obj, attr)``
* ``delattr(obj, name)``
* ``slice(start, stop, step)``
* ``globals()``

Statements
----------

These variants of statements have custom implementations:

* ``for ... in seq:`` (for loop over a sequence)
* ``for ... in enumerate(...):``
* ``for ... in zip(...):``
