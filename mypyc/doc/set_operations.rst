Native set operations
======================

These ``set`` operations have fast, optimized implementations. Other
set operations use generic implementations that are often slower.

Construction
------------

* ``{item0, ..., itemN}``
* ``set()``
* ``set(x: Iterable)``

Operators
---------

* ``item in s``

Methods
-------

* ``s.add(item: object)``
* ``s.remove(item: object)``
* ``s.discard(item: object)``
* ``s.update(x: Iterable)``
* ``s.clear()``
* ``s.pop()``

Functions
---------

* ``len(s: set)``
