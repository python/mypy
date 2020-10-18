Built-in types
==============

These are examples of some of the most common built-in types:

====================== ===============================
Type                   Description
====================== ===============================
``int``                integer
``float``              floating point number
``bool``               boolean value (subclass of ``int``)
``str``                string (unicode)
``bytes``              8-bit string
``object``             an arbitrary object (``object`` is the common base class)
``List[str]``          list of ``str`` objects
``Tuple[int, int]``    tuple of two ``int`` objects (``Tuple[()]`` is the empty tuple)
``Tuple[int, ...]``    tuple of an arbitrary number of ``int`` objects
``Dict[str, int]``     dictionary from ``str`` keys to ``int`` values
``Iterable[int]``      iterable object containing ints
``Sequence[bool]``     sequence of booleans (read-only)
``Mapping[str, int]``  mapping from ``str`` keys to ``int`` values (read-only)
``Any``                dynamically typed value with an arbitrary type
====================== ===============================

The type ``Any`` and type constructors such as ``List``, ``Dict``,
``Iterable`` and ``Sequence`` are defined in the :py:mod:`typing` module.

The type ``Dict`` is a *generic* class, signified by type arguments within
``[...]``. For example, ``Dict[int, str]`` is a dictionary from integers to
strings and ``Dict[Any, Any]`` is a dictionary of dynamically typed
(arbitrary) values and keys. ``List`` is another generic class. ``Dict`` and
``List`` are aliases for the built-ins ``dict`` and ``list``, respectively.

``Iterable``, ``Sequence``, and ``Mapping`` are generic types that
correspond to Python protocols. For example, a ``str`` object or a
``List[str]`` object is valid
when ``Iterable[str]`` or ``Sequence[str]`` is expected. Note that even though
they are similar to abstract base classes defined in :py:mod:`collections.abc`
(formerly ``collections``), they are not identical, since the built-in
collection type objects do not support indexing.
