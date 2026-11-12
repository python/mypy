.. _bytearray-ops:

Native bytearray operations
============================

These ``bytearray`` operations have fast, optimized implementations. Other
bytearray operations use generic implementations that are often slower.

Construction
------------

* ``bytearray()``
* ``bytearray(x)``

Operators
---------

* Indexing (``b[n]``)
* Slicing (``b[n:m]``, ``b[n:]``, ``b[:m]``)

Statements
----------

Set item by integer index:

* ``b[n] = x``

Functions
---------

* ``len(b: bytearray)``
