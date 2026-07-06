.. _librt-base64:

librt.base64
============

The ``librt.base64`` module is part of the ``librt`` package on PyPI, and it includes
base64 encoding and decoding functions that use SIMD (Single Instruction, Multiple Data)
for high efficiency. It is a wrapper around
`Alfred Klomp's base64 library <https://github.com/aklomp/base64>`_.

These functions are mostly compatible with the corresponding functions in the
Python standard library ``base64`` module but are significantly faster,
especially in code compiled with mypyc. For larger inputs, these are much
faster than the standard library alternatives even when used from interpreted code.

.. note::

    The decode functions don't behave identically when data is malformed.
    Only commonly used functionality is provided. The supported arguments may be
    restricted compared to the stdlib functions: the optional ``altchars`` and
    ``validate`` arguments are not supported.

Functions
---------

.. function:: b64encode(s: bytes) -> bytes

   Encode a bytes object using Base64 and return the encoded bytes.

   This is equivalent to ``base64.b64encode(s)`` in the standard library.

.. function:: b64decode(s: bytes | str) -> bytes

   Decode a Base64 encoded bytes object or ASCII string and return
   the decoded bytes.

   Non-base64-alphabet characters are ignored. This is compatible
   with the default behavior of standard library ``base64.b64decode``.

   Raise ``ValueError`` if the padding is incorrect. The standard
   library raises ``binascii.Error`` (a subclass of ``ValueError``)
   instead.

.. function:: urlsafe_b64encode(s: bytes) -> bytes

   Encode a bytes object using the URL and filesystem safe Base64
   alphabet (using ``-`` instead of ``+`` and ``_`` instead of ``/``),
   and return the encoded bytes.

   This is equivalent to ``base64.urlsafe_b64encode(s)`` in the
   standard library.

.. function:: urlsafe_b64decode(s: bytes | str) -> bytes

   Decode a bytes object or ASCII string using the URL and filesystem
   safe Base64 alphabet (using ``-`` instead of ``+`` and ``_`` instead
   of ``/``), and return the decoded bytes.

   This is an alternative to ``base64.urlsafe_b64decode(s)`` in the
   standard library.

   Raise ``ValueError`` if the padding is incorrect. The standard
   library raises ``binascii.Error`` (a subclass of ``ValueError``)
   instead.
