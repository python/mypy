librt.vecs
==========

The ``librt.vecs`` module is part of the ``librt`` package on PyPI, and it includes
a low-level, uniform growable array type ``vec`` and helper functions. A vec can be
a more efficient alternative to ``array.array`` or ``list`` in some uses cases.`

A vec instance perform runtime type checking of item types. This allows using
an optimized memory representation based on item type.

A vec instance must always we created using ``vec[<t>](...)``, where ``<t>`` is a non-generic
supported item type, so that the item type is known at runtime.

Since vec performs runtime type checking, only simple uniform types are supported. Summary
of supported item types:

* Value item types (``i64``, ``i32``, ``i16``, ``u8``, ``float`` and ``bool``) are stored
  as efficient packed arrays. No other value item types are supported.

  * ``int`` is not a valid item type, since it has an arbitrary precision, and vec is an efficiency
    focused type. Use one of the fixed-length integer types instead.

* Class item types (e.g. ``str`` or ``MyNativeClass``) are stored as normal object references.
* Optional class item types (e.g. ``str | None``) are supported for convenience, but arbitrary
  union types are not supported as item types.
* Nested vecs are support, e.g. ``vec[vec[i64]]``.

Here are some examples of valid vec types:

.. list-table::
   :header-rows: 1

   * - Type
     - Item representation
   * - ``vec[i32]``
     - Packed 32-bit integers
   * - ``vec[float]``
     - Packed 64-bit floats
   * - ``vec[str]``
     - Object references
   * - ``vec[vec[u8]]``
     - Object references (nested vecs)

Classes
-------

.. class:: vec(items: Iterable[T] = ..., *, capacity: i64 = ...)

   A generic growable array type. The type parameter ``T`` determines the
   element type.

   .. describe:: len(v) → i64

      Return the length of ``v```.

   .. describe:: v[i] → T

      ``vec`` supports indexing.

   .. describe:: v[i:j] → vec[T]

      ``vec`` supports slicing. This constructs a new ``vec`` object.

   .. describe:: v[i] = o

      ``vec`` supports indexed assignment.

   .. describe:: o in v → bool

      ``vec`` supports the ``in`` operator.

   .. describe:: for o in v

      ``vec`` supports iteration.

   .. describe:: memoryview(v)

      ``vec`` implements the buffer protocol (TODO for given item types).

Functions
---------

.. function:: append(v: vec[T], o: T) -> vec[T]

   Return ``v`` with item ``o`` appended to it.

.. function:: extend(v: vec[T], it: Iterable[T]) -> vec[T]

   Return ``v`` with all items from iterable ``o`` appended to it.

.. function:: remove(v: vec[T], o: T) -> vec[T]

   Return ``v`` with the first instance of item ``o`` removed from it.

.. function:: pop(v: vec[T], i: i64 = -1) -> tuple[vec[T], T]

   Return tuple with first being ``v`` with an item at index ``i`` removed,
   and second being the removed item.
