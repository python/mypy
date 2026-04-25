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

Built-in collection type objects support indexing:

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
:py:mod:`typing`.

See :ref:`generic-builtins` for more details.

These legacy types defined in :py:mod:`typing` are also supported:

====================== ===============================
Type                   Description
====================== ===============================
``List[str]``          list of ``str`` objects
``Tuple[int, int]``    tuple of two ``int`` objects (``Tuple[()]`` is the empty tuple)
``Tuple[int, ...]``    tuple of an arbitrary number of ``int`` objects
``Dict[str, int]``     dictionary from ``str`` keys to ``int`` values
``Type[C]``            type object of ``C`` (``C`` is a class/type variable/union of types)
====================== ===============================
