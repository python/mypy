.. _str-ops:

Native string operations
========================

These ``str`` operations have fast, optimized implementations. Other
string operations use generic implementations that are often slower.

Construction
------------

* String literal
* ``str(x: int)``
* ``str(x: object)``

Operators
---------

Concatenation:

* ``s1 + s2``

Indexing:

* ``s[n]`` (integer index)

Comparisons:

* ``s1 == s2``, ``s1 != s2``

Statements
----------

* ``s1 += s2``

Methods
-------

* ``s.join(x: Iterable)``
* ``s.split()``
* ``s.split(sep: str)``
* ``s.split(sep: str, maxsplit: int)``
