.. _librt-time:

librt.time
==========

The ``librt.time`` module is part of the ``librt`` package on PyPI, and it includes
time-related utilities.

Functions
---------

.. function:: time() -> float

   Return the time in seconds since the
   `epoch <https://docs.python.org/3/library/time.html#epoch>`_ as a floating-point number.
   This is a replacement for the standard library
   `time.time() <https://docs.python.org/3/library/time.html#time.time>`_
   function that is faster in compiled code. Unlike the standard library function,
   uses of this function can't be monkey patched in compiled code -- calls use *early binding*.
