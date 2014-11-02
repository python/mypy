Built-in types
==============

These are examples of some of the most common built-in types:

=================== ===============================
Type                Description
=================== ===============================
``int``             integer of arbitrary size
``float``           floating point number
``bool``            boolean value
``str``             unicode string
``bytes``           8-bit string
``object``          an arbitrary object (``object`` is the common base class)
``List[str]``       list of ``str`` objects
``Dict[str, int]``  dictionary from ``str`` keys to ``int`` values
``Iterable[int]``   iterable object containing ints
``Sequence[bool]``  sequence of booleans
``Any``             dynamically typed value with an arbitrary type
=================== ===============================

The type ``Any`` and type constructors ``List``, ``Dict``,
``Iterable`` and ``Sequence`` are defined in the ``typing`` module.

The type ``Dict`` is a *generic* class, signified by type arguments within
``[...]``. For example, ``Dict[int, str]`` is a dictionary from integers to
strings and and ``Dict[Any, Any]`` is a dictionary of dynamically typed
(arbitrary) values and keys. ``List`` is another generic class. ``Dict`` and
``List`` are aliases for the built-ins ``dict`` and ``list``, respectively.

``Iterable`` and ``Sequence`` are generic abstract base classes that
correspond to Python protocols. For example, a ``str`` object or a
``List[str]`` object is valid
when ``Iterable[str]`` or ``Sequence[str]`` is expected. Note that even though
they are similar to abstract base classes defined in ``abc.collections``
(formerly ``collections``), they are not identical, since the built-in
collection type objects do not support indexing.
