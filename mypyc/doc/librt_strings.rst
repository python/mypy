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

There are no functions for reading or writing individual bytes. ``BytesWriter.append`` can
be used to insert a byte value, and ``b[n]`` can be used to read a byte value. Both
are fast operations in compiled code.

This example writes two binary values and reads them afterwards::

    def example() -> None:
        b = BytesWriter()
        write_i32_le(b, 123)
        write_f64_le(b, 4.5)
        data = b.getvalue()

        x = read_i32_le(data, 0)
        y = read_f64_le(data, 4)
        ...

.. function:: write_i16_le(b: BytesWriter, n: i16, /) -> None

   Append a 16-bit integer as a little-endian binary value.

.. function:: write_i16_be(b: BytesWriter, n: i16, /) -> None

   Append a 16-bit integer as a big-endian binary value.

.. function:: read_i16_le(b: bytes, index: i64, /) -> i16

   Read a 16-bit integer value starting at the given index as a little-endian binary value
   (2 bytes).

.. function:: read_i16_be(b: bytes, index: i64, /) -> i16

   Read a 16-bit integer value starting at the given index as a big-endian binary value
   (2 bytes).

.. function:: write_i32_le(b: BytesWriter, n: i32, /) -> None

   Append a 32-bit integer as a little-endian binary value.

.. function:: write_i32_be(b: BytesWriter, n: i32, /) -> None

   Append a 32-bit integer as a big-endian binary value.

.. function:: read_i32_le(b: bytes, index: i64, /) -> i32

   Read a 32-bit integer value starting at the given index as a little-endian binary value
   (4 bytes).

.. function:: read_i32_be(b: bytes, index: i64, /) -> i32

   Read a 32-bit integer value starting at the given index as a big-endian binary value
   (4 bytes).

.. function:: write_i64_le(b: BytesWriter, n: i64, /) -> None

   Append a 64-bit integer as a little-endian binary value.

.. function:: write_i64_be(b: BytesWriter, n: i64, /) -> None

   Append a 64-bit integer as a big-endian binary value.

.. function:: read_i64_le(b: bytes, index: i64, /) -> i64

   Read a 64-bit integer value starting at the given index as a little-endian binary value
   (8 bytes).

.. function:: read_i64_be(b: bytes, index: i64, /) -> i64

   Read a 64-bit integer value starting at the given index as a big-endian binary value
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
