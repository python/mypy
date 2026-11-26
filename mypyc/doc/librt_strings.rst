.. _librt-strings:

librt.strings
=============

The ``librt.strings`` module is part of the ``librt`` package on PyPI, and it includes
low-level string and bytes utilities.

Classes
-------

Thread safety
^^^^^^^^^^^^^

``BytesWriter`` and ``StringWriter`` objects are unsafe to access from another
thread if they are concurrently modified (on free-threaded Python builds). They are optimized
for maximal performance, and they aren't fully synchronized. Read-only access from multiple
threads is safe, as always.

BytesWriter
^^^^^^^^^^^

.. class:: BytesWriter

   This class can be used to efficiently construct a bytes object from individual byte values
   and from bytes or bytearray objects. It also provides some operations for accessing
   and modifying items, but it doesn't support the full sequence interface.

   This can be used as a faster replacement for :py:class:`io.BytesIO` or :py:class:`bytearray` in
   compiled code. This is also usually faster than constructing a list of bytes objects and using
   the :meth:`bytes.join` method to concatenate them.

   .. method:: append(x: int, /) -> None

      Append a byte to contents.

   .. method:: write(b: bytes | bytearray, /) -> None

      Append a bytes or bytearray object to contents.

   .. method:: getvalue() -> bytes

      Return the contents as a bytes object.

   .. method:: truncate(size: i64, /) -> None

      Truncate the length of the contents to the given size.

   .. describe:: len(writer) → i64

      Return the length of the contents.

   .. describe:: writer[i] → u8

      Return the byte at a specific index. The index can be negative.

   .. describe:: writer[i] = x

      Set a byte at a specific index. The index can be negative.

.. _librt-string-writer:

StringWriter
^^^^^^^^^^^^

.. class:: StringWriter

   This class can be used to efficiently construct a string object from individual Unicode code
   point integer values and from string objects. It also provides some operations for accessing
   items, but it doesn't support the full sequence interface.

   ``StringWriter`` can be used as a faster replacement for :py:class:`io.StringIO` in
   compiled code. This is also usually faster than constructing a list of str objects and using
   the :meth:`str.join` method to concatenate them.

   If you construct a string from individual characters or code points, using integer values
   can be much faster than using 1-length strings. You can rely on expressions like ``ord("x")``
   being treated as compile-time integer constants in compiled code. Also ``ord(s[i])`` is
   guaranteed to be a very quick operation in compiled code, if ``s`` has type :py:class:`str`.

   .. method:: append(x: int, /) -> None

      Append a Unicode code point (often representing a character) to the contents.

   .. method:: write(s: str, /) -> None

      Append a string to contents.

   .. method:: getvalue() -> str

      Return the contents as a string.

   .. describe:: len(writer) → i64

      Return the length of the contents (number of code points).

   .. describe:: writer[i] → i32

      Return the Unicode code point at a specific index as an integer. The index can be negative.

Functions
---------

Reading and writing binary data
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The ``write_*`` and ``read_*`` functions allow interpreting bytes as packed binary
data. They can be used as (much) more efficient but lower-level alternatives to the
stdlib :mod:`struct` module in compiled code.

Individual unsigned byte values can be read using ``b[n]`` and written using
``BytesWriter.append``. Both are fast operations in compiled code. Use ``write_i8`` and
``read_i8`` to write and read a byte as a signed value.

The ``read_*`` functions raise ``ValueError`` if the index is negative, and ``IndexError``
if the value doesn't fit within the data starting at the index. Unlike ``b[n]``, they don't
support negative indices that count from the end.

This example writes two binary values and reads them afterwards::

    def example() -> None:
        b = BytesWriter()
        write_i32_le(b, 123)
        write_f64_le(b, 4.5)
        data = b.getvalue()

        x = read_i32_le(data, 0)
        y = read_f64_le(data, 4)
        ...

This table shows the :mod:`struct` format codes that correspond to these functions (``<``
is little-endian and ``>`` is big-endian):

.. list-table::
   :header-rows: 1

   * - Format
     - Type
     - Write function
     - Read function
   * - ``b``
     - ``i8``
     - :func:`write_i8`
     - :func:`read_i8`
   * - ``B``
     - ``u8``
     - :meth:`BytesWriter.append`
     - ``b[n]``
   * - ``<h``
     - ``i16``
     - :func:`write_i16_le`
     - :func:`read_i16_le`
   * - ``>h``
     - ``i16``
     - :func:`write_i16_be`
     - :func:`read_i16_be`
   * - ``<i``
     - ``i32``
     - :func:`write_i32_le`
     - :func:`read_i32_le`
   * - ``>i``
     - ``i32``
     - :func:`write_i32_be`
     - :func:`read_i32_be`
   * - ``<q``
     - ``i64``
     - :func:`write_i64_le`
     - :func:`read_i64_le`
   * - ``>q``
     - ``i64``
     - :func:`write_i64_be`
     - :func:`read_i64_be`
   * - ``<H``
     - ``u16``
     - :func:`write_u16_le`
     - :func:`read_u16_le`
   * - ``>H``
     - ``u16``
     - :func:`write_u16_be`
     - :func:`read_u16_be`
   * - ``<I``
     - ``u32``
     - :func:`write_u32_le`
     - :func:`read_u32_le`
   * - ``>I``
     - ``u32``
     - :func:`write_u32_be`
     - :func:`read_u32_be`
   * - ``<Q``
     - ``u64``
     - :func:`write_u64_le`
     - :func:`read_u64_le`
   * - ``>Q``
     - ``u64``
     - :func:`write_u64_be`
     - :func:`read_u64_be`
   * - ``<f``
     - ``float``
     - :func:`write_f32_le`
     - :func:`read_f32_le`
   * - ``>f``
     - ``float``
     - :func:`write_f32_be`
     - :func:`read_f32_be`
   * - ``<d``
     - ``float``
     - :func:`write_f64_le`
     - :func:`read_f64_le`
   * - ``>d``
     - ``float``
     - :func:`write_f64_be`
     - :func:`read_f64_be`

.. function:: write_i8(b: BytesWriter, n: i8, /) -> None

   Append an 8-bit signed integer as a binary value (1 byte).

.. function:: read_i8(b: bytes, index: i64, /) -> i8

   Read an 8-bit signed integer value at the given index (1 byte).

.. function:: write_i16_le(b: BytesWriter, n: i16, /) -> None

   Append a 16-bit signed integer as a little-endian binary value.

.. function:: write_i16_be(b: BytesWriter, n: i16, /) -> None

   Append a 16-bit signed integer as a big-endian binary value.

.. function:: read_i16_le(b: bytes, index: i64, /) -> i16

   Read a 16-bit signed integer value starting at the given index as a little-endian binary value
   (2 bytes).

.. function:: read_i16_be(b: bytes, index: i64, /) -> i16

   Read a 16-bit signed integer value starting at the given index as a big-endian binary value
   (2 bytes).

.. function:: write_i32_le(b: BytesWriter, n: i32, /) -> None

   Append a 32-bit signed integer as a little-endian binary value.

.. function:: write_i32_be(b: BytesWriter, n: i32, /) -> None

   Append a 32-bit signed integer as a big-endian binary value.

.. function:: read_i32_le(b: bytes, index: i64, /) -> i32

   Read a 32-bit signed integer value starting at the given index as a little-endian binary value
   (4 bytes).

.. function:: read_i32_be(b: bytes, index: i64, /) -> i32

   Read a 32-bit signed integer value starting at the given index as a big-endian binary value
   (4 bytes).

.. function:: write_i64_le(b: BytesWriter, n: i64, /) -> None

   Append a 64-bit signed integer as a little-endian binary value.

.. function:: write_i64_be(b: BytesWriter, n: i64, /) -> None

   Append a 64-bit signed integer as a big-endian binary value.

.. function:: read_i64_le(b: bytes, index: i64, /) -> i64

   Read a 64-bit signed integer value starting at the given index as a little-endian binary value
   (8 bytes).

.. function:: read_i64_be(b: bytes, index: i64, /) -> i64

   Read a 64-bit signed integer value starting at the given index as a big-endian binary value
   (8 bytes).

.. function:: write_u16_le(b: BytesWriter, n: u16, /) -> None

   Append a 16-bit unsigned integer as a little-endian binary value.

.. function:: write_u16_be(b: BytesWriter, n: u16, /) -> None

   Append a 16-bit unsigned integer as a big-endian binary value.

.. function:: read_u16_le(b: bytes, index: i64, /) -> u16

   Read a 16-bit unsigned integer value starting at the given index as a little-endian binary value
   (2 bytes).

.. function:: read_u16_be(b: bytes, index: i64, /) -> u16

   Read a 16-bit unsigned integer value starting at the given index as a big-endian binary value
   (2 bytes).

.. function:: write_u32_le(b: BytesWriter, n: u32, /) -> None

   Append a 32-bit unsigned integer as a little-endian binary value.

.. function:: write_u32_be(b: BytesWriter, n: u32, /) -> None

   Append a 32-bit unsigned integer as a big-endian binary value.

.. function:: read_u32_le(b: bytes, index: i64, /) -> u32

   Read a 32-bit unsigned integer value starting at the given index as a little-endian binary value
   (4 bytes).

.. function:: read_u32_be(b: bytes, index: i64, /) -> u32

   Read a 32-bit unsigned integer value starting at the given index as a big-endian binary value
   (4 bytes).

.. function:: write_u64_le(b: BytesWriter, n: u64, /) -> None

   Append a 64-bit unsigned integer as a little-endian binary value.

.. function:: write_u64_be(b: BytesWriter, n: u64, /) -> None

   Append a 64-bit unsigned integer as a big-endian binary value.

.. function:: read_u64_le(b: bytes, index: i64, /) -> u64

   Read a 64-bit unsigned integer value starting at the given index as a little-endian binary value
   (8 bytes).

.. function:: read_u64_be(b: bytes, index: i64, /) -> u64

   Read a 64-bit unsigned integer value starting at the given index as a big-endian binary value
   (8 bytes).

.. function:: write_f32_le(b: BytesWriter, n: float, /) -> None

   Append a 32-bit floating-point value as a little-endian binary value.

.. function:: write_f32_be(b: BytesWriter, n: float, /) -> None

   Append a 32-bit floating-point value as a big-endian binary value.

.. function:: read_f32_le(b: bytes, index: i64, /) -> float

   Read a 32-bit floating-point value starting at the given index as a little-endian binary value
   (4 bytes).

.. function:: read_f32_be(b: bytes, index: i64, /) -> float

   Read a 32-bit floating-point value starting at the given index as a big-endian binary value
   (4 bytes).

.. function:: write_f64_le(b: BytesWriter, n: float, /) -> None

   Append a 64-bit floating-point value as a little-endian binary value.

.. function:: write_f64_be(b: BytesWriter, n: float, /) -> None

   Append a 64-bit floating-point value as a big-endian binary value.

.. function:: read_f64_le(b: bytes, index: i64, /) -> float

   Read a 64-bit floating-point value starting at the given index as a little-endian binary value
   (8 bytes).

.. function:: read_f64_be(b: bytes, index: i64, /) -> float

   Read a 64-bit floating-point value starting at the given index as a big-endian binary value
   (8 bytes).

Code point classification
^^^^^^^^^^^^^^^^^^^^^^^^^

These functions classify a single Unicode code point, passed as an ``i32`` integer. They are
faster alternatives to calling the corresponding :py:class:`str` methods on a one-character
string in compiled code. A code point is often obtained via ``ord(s[i])``, which is a
fast operation in compiled code when ``s`` has type :py:class:`str`.

Each function agrees with the matching :py:class:`str` method applied to the one-character
string ``chr(c)``. Out-of-range inputs (negative values, or values past the maximum Unicode
code point ``0x10FFFF``) return ``False``.

.. function:: isspace(c: i32, /) -> bool

   Return whether the code point is whitespace. Equivalent to ``chr(c).isspace()``.

.. function:: isalpha(c: i32, /) -> bool

   Return whether the code point is alphabetic. Equivalent to ``chr(c).isalpha()``.

.. function:: isdigit(c: i32, /) -> bool

   Return whether the code point is a digit. Equivalent to ``chr(c).isdigit()``.

.. function:: isalnum(c: i32, /) -> bool

   Return whether the code point is alphanumeric. Equivalent to ``chr(c).isalnum()``.

.. function:: isidentifier(c: i32, /) -> bool

   Return whether the code point is valid as the first character of a Python identifier.
   Equivalent to ``chr(c).isidentifier()``.

Code point case conversion
^^^^^^^^^^^^^^^^^^^^^^^^^^

These functions convert the case of a single Unicode code point, passed as an ``i32`` integer,
and return the converted code point as an ``i32``. They are faster alternatives to
:py:meth:`str.upper` / :py:meth:`str.lower` on a one-character string in compiled code.

For the rare code points whose Unicode uppercase or lowercase form has multiple code points
(e.g. U+00DF ``ß`` has the upper case form ``"SS"``, and U+FB01 ``ﬁ`` maps to ``"FI"``), the
input is returned unchanged, so the signature can stay ``i32 -> i32``. Use :py:meth:`str.upper`
/ :py:meth:`str.lower` when full Unicode case conversion matters, or implement the logic to
handle the special cases explicitly. Out-of-range inputs (negative values, or values past the
maximum Unicode code point ``0x10FFFF``) are returned unchanged.

.. function:: toupper(c: i32, /) -> i32

   Return the uppercase of the code point, or the input unchanged if the uppercase does not
   consist of exactly one code point.

.. function:: tolower(c: i32, /) -> i32

   Return the lowercase of the code point, or the input unchanged if the lowercase does not
   consist of exactly one code point.
