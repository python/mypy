.. _librt-strings:

librt.strings
=============

The ``librt.strings`` module is part of the ``librt`` package on PyPI, and it includes
string and bytes utilities.

Classes
-------

BytesWriter
^^^^^^^^^^^

.. class:: BytesWriter

   TODO

   .. method:: append(x: int, /) -> None

      TODO

   .. method:: write(b: bytes | bytearray, /) -> None

      TODO

   .. method:: getvalue() -> bytes

      TODO

   .. method:: truncate(size: i64, /) -> None

      TODO

   .. describe:: len(writer)

      TODO

   .. describe:: writer[i]

      TODO

   .. describe:: writer[i] = x

      TODO

StringWriter
^^^^^^^^^^^^

.. class:: StringWriter

   TODO

   .. method:: append(x: int, /) -> None

      TODO

   .. method:: write(s: str, /) -> None

      TODO

   .. method:: getvalue() -> str

      TODO

   .. describe:: len(writer)

      TODO

   .. describe:: writer[i]

      TODO

Functions
---------

.. function:: write_i16_le(b: BytesWriter, n: i16, /) -> None

   TODO

.. function:: write_i16_be(b: BytesWriter, n: i16, /) -> None

   TODO

.. function:: read_i16_le(b: bytes, index: i64, /) -> i16

   TODO

.. function:: read_i16_be(b: bytes, index: i64, /) -> i16

   TODO

.. function:: write_i32_le(b: BytesWriter, n: i32, /) -> None

   TODO

.. function:: write_i32_be(b: BytesWriter, n: i32, /) -> None

   TODO

.. function:: read_i32_le(b: bytes, index: i64, /) -> i32

   TODO

.. function:: read_i32_be(b: bytes, index: i64, /) -> i32

   TODO

.. function:: write_i64_le(b: BytesWriter, n: i64, /) -> None

   TODO

.. function:: write_i64_be(b: BytesWriter, n: i64, /) -> None

   TODO

.. function:: read_i64_le(b: bytes, index: i64, /) -> i64

   TODO

.. function:: read_i64_be(b: bytes, index: i64, /) -> i64

   TODO

.. function:: write_f32_le(b: BytesWriter, n: float, /) -> None

   TODO

.. function:: write_f32_be(b: BytesWriter, n: float, /) -> None

   TODO

.. function:: read_f32_le(b: bytes, index: i64, /) -> float

   TODO

.. function:: read_f32_be(b: bytes, index: i64, /) -> float

   TODO

.. function:: write_f64_le(b: BytesWriter, n: float, /) -> None

   TODO

.. function:: write_f64_be(b: BytesWriter, n: float, /) -> None

   TODO

.. function:: read_f64_le(b: bytes, index: i64, /) -> float

   TODO

.. function:: read_f64_be(b: bytes, index: i64, /) -> float

   TODO
