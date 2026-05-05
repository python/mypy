librt.vecs
==========

The ``librt.vecs`` module is part of the ``librt`` package on PyPI, and it includes
a low-level growable array type ``vec`` and helper functions.

Classes
-------

.. class:: vec(items: Iterable[T] = ..., *, capacity: i64 = ...)

   A generic growable array type. The type parameter ``T`` determines the
   element type.

   TODO

   .. method:: __len__() -> i64

      TODO

   .. method:: __getitem__(i: i64) -> T
               __getitem__(i: slice) -> vec[T]

      TODO

   .. method:: __setitem__(i: i64, o: T) -> None

      TODO

   .. method:: __contains__(o: object) -> bool

      TODO

   .. method:: __iter__() -> Iterator[T]

      TODO

   .. method:: __buffer__(flags: int) -> memoryview

      TODO

Functions
---------

.. function:: append(v: vec[T], o: T) -> vec[T]

   TODO

.. function:: remove(v: vec[T], o: T) -> vec[T]

   TODO

.. function:: pop(v: vec[T], i: i64 = -1) -> tuple[vec[T], T]

   TODO

.. function:: extend(v: vec[T], o: Iterable[T]) -> vec[T]

   TODO
