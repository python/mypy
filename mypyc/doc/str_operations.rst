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
* ``repr(x: int)``
* ``repr(x: object)``

Operators
---------

* Concatenation (``s1 + s2``)
* Indexing (``s[n]``)
* Slicing (``s[n:m]``, ``s[n:]``, ``s[:m]``)
* Comparisons (``==``, ``!=``)
* Augmented assignment (``s1 += s2``)
* Containment (``s1 in s2``)

.. _str-methods:

Methods
-------

* ``s.encode()``
* ``s.encode(encoding: str)``
* ``s.encode(encoding: str, errors: str)``
* ``s1.endswith(s2: str)``
* ``s1.endswith(t: tuple[str, ...])``
* ``s1.find(s2: str)``
* ``s1.find(s2: str, start: int)``
* ``s1.find(s2: str, start: int, end: int)``
* ``s.join(x: Iterable)``
* ``s.lstrip()``
* ``s.lstrip(chars: str)``
* ``s.partition(sep: str)``
* ``s.removeprefix(prefix: str)``
* ``s.removesuffix(suffix: str)``
* ``s.replace(old: str, new: str)``
* ``s.replace(old: str, new: str, count: int)``
* ``s1.rfind(s2: str)``
* ``s1.rfind(s2: str, start: int)``
* ``s1.rfind(s2: str, start: int, end: int)``
* ``s.rpartition(sep: str)``
* ``s.rsplit()``
* ``s.rsplit(sep: str)``
* ``s.rsplit(sep: str, maxsplit: int)``
* ``s.rstrip()``
* ``s.rstrip(chars: str)``
* ``s.split()``
* ``s.split(sep: str)``
* ``s.split(sep: str, maxsplit: int)``
* ``s.splitlines()``
* ``s.splitlines(keepends: bool)``
* ``s1.startswith(s2: str)``
* ``s1.startswith(t: tuple[str, ...])``
* ``s.strip()``
* ``s.strip(chars: str)``

.. note::

    :ref:`bytes.decode() <bytes-methods>` is also optimized.

Formatting
----------

A subset of these common string formatting expressions are optimized:

* F-strings
* ``"...".format(...)``
* ``"..." % (...)``

Functions
---------

* ``len(s: str)``
* ``ord(s: str)``
