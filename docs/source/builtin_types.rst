Built-in types
==============

This chapter introduces some commonly used built-in types. We will
cover many other kinds of types later.

Simple types
............

Here are examples of some common built-in types:

====================== ===============================
Type                   Description
====================== ===============================
``int``                integer
``float``              floating point number
``bool``               boolean value (subclass of ``int``)
``str``                text, sequence of unicode codepoints
``bytes``              8-bit string, sequence of byte values
``object``             an arbitrary object (``object`` is the common base class)
====================== ===============================

All built-in classes can be used as types.

Any type
........

If you can't find a good type for some value, you can always fall back
to ``Any``:

====================== ===============================
Type                   Description
====================== ===============================
``Any``                dynamically typed value with an arbitrary type
====================== ===============================

The type ``Any`` is defined in the :py:mod:`typing` module.
See :ref:`dynamic-typing` for more details.

Generic types
.............

In Python 3.9 and later, built-in collection type objects support
indexing:

====================== ===============================
Type                   Description
====================== ===============================
``list[str]``          list of ``str`` objects
``tuple[int, int]``    tuple of two ``int`` objects (``tuple[()]`` is the empty tuple)
``tuple[int, ...]``    tuple of an arbitrary number of ``int`` objects
``dict[str, int]``     dictionary from ``str`` keys to ``int`` values
``Iterable[int]``      iterable object containing ints
``Sequence[bool]``     sequence of booleans (read-only)
``Mapping[str, int]``  mapping from ``str`` keys to ``int`` values (read-only)
``type[C]``            type object of ``C`` (``C`` is a class/type variable/union of types)
====================== ===============================

The type ``dict`` is a *generic* class, signified by type arguments within
``[...]``. For example, ``dict[int, str]`` is a dictionary from integers to
strings and ``dict[Any, Any]`` is a dictionary of dynamically typed
(arbitrary) values and keys. ``list`` is another generic class.

``Iterable``, ``Sequence``, and ``Mapping`` are generic types that correspond to
Python protocols. For example, a ``str`` object or a ``list[str]`` object is
valid when ``Iterable[str]`` or ``Sequence[str]`` is expected.
You can import them from :py:mod:`collections.abc` instead of importing from
:py:mod:`typing` in Python 3.9.

See :ref:`generic-builtins` for more details, including how you can
use these in annotations also in Python 3.7 and 3.8.

These legacy types defined in :py:mod:`typing` are needed if you need to support
Python 3.8 and earlier:

====================== ===============================
Type                   Description
====================== ===============================
``List[str]``          list of ``str`` objects
``Tuple[int, int]``    tuple of two ``int`` objects (``Tuple[()]`` is the empty tuple)
``Tuple[int, ...]``    tuple of an arbitrary number of ``int`` objects
``Dict[str, int]``     dictionary from ``str`` keys to ``int`` values
``Iterable[int]``      iterable object containing ints
``Sequence[bool]``     sequence of booleans (read-only)
``Mapping[str, int]``  mapping from ``str`` keys to ``int`` values (read-only)
``Type[C]``            type object of ``C`` (``C`` is a class/type variable/union of types)
====================== ===============================

``List`` is an alias for the built-in type ``list`` that supports
indexing (and similarly for ``dict``/``Dict`` and
``tuple``/``Tuple``).

Note that even though ``Iterable``, ``Sequence`` and ``Mapping`` look
similar to abstract base classes defined in :py:mod:`collections.abc`
(formerly ``collections``), they are not identical, since the latter
don't support indexing prior to Python 3.9.
