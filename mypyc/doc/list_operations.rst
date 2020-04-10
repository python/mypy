Native list operations
======================

Various ``list`` operations have fast, optimized implementations.

Construction
------------

* ``[item0, ..., itemN]``
* ``list(x: Iterable)``
* ``[expr for item in lst]`` (list comprehension)
* ``[expr1 for item in lst if expr2]`` (list comprehension with filter)

Operators
---------

Indexing:

* ``lst[n]`` (integer index)
* ``lst[n] = x`` (integer index)

Multiplication:

* ``lst * n``, ``n * lst`` (multiply by integer)

Statements
----------

* ``for item in lst:`` (for loop over a list)

Methods
-------

* ``lst.append(item: object)``
* ``lst.extend(x: Iterable)``
* ``lst.pop()``
* ``lst.count(item: object)``

Functions
---------

* ``len(lst: list)``
