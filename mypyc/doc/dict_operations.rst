Native dict operations
======================

These ``dict`` operations have fast, optimized implementations. Other
dictionary operations use generic implementations that are often slower.

Construction
------------

* ``{key: value,  ...}``
* ``dict(d: dict)``
* ``dict(x: Iterable)``

Operators
---------

* ``d[key]``
* ``d[key] = value``
* ``value in d``

Methods
-------

* ``d.get(key: object)``
* ``d.get(key: object, default: object)``
* ``d1.update(d2: dict)``
* ``d.update(x: Iterable)``

Functions
---------

* ``len(d: dict)``
