.. _librt-random:

librt.random
============

The ``librt.random`` module is part of the ``librt`` package on PyPI, and it provides
pseudorandom number generation utilities. It can be used as a significantly faster
alternative to the stdlib :mod:`random` module in compiled code. It can also be faster
than stdlib ``random`` in interpreted code, depending on use case.

The module uses the `ChaCha8 <https://cr.yp.to/chacha.html>`__ algorithm with forward
secrecy. It is **not** suitable for cryptographic use, but it provides high-quality,
statistically uniform output.

Functions
---------

The module provides module-level functions that use thread-local state, so they are
safe to call concurrently from multiple threads without external locking, and they
scale well even if used from multiple threads:

.. function:: random() -> float

   Return a random floating-point number in the range [0.0, 1.0).

.. function:: randint(a: i64, b: i64) -> i64

   Return a random integer *n* such that *a* <= *n* <= *b*.

.. function:: randrange(stop: i64, /) -> i64
              randrange(start: i64, stop: i64, /) -> i64

   Return a random integer from the range. With one argument, the range is [0, *stop*).
   With two arguments, the range is [*start*, *stop*).

.. function:: seed(n: i64, /) -> None

   Seed the thread-local random number generator. This only affects module-level
   functions called from the current thread.

Random class
------------

.. class:: Random(seed: i64 | None = None)

   A pseudorandom number generator instance with its own independent state. Use this
   when you need reproducible sequences or want to avoid interference with the
   thread-local state used by the module-level functions.

   If *seed* is ``None``, the generator is seeded from OS entropy
   (via :func:`os.urandom`).

   It's not safe to use the same ``Random`` instance concurrently from multiple
   threads without synchronization on free-threaded Python builds.

   .. method:: random() -> float

      Return a random floating-point number in the range [0.0, 1.0).

   .. method:: randint(a: i64, b: i64) -> i64

      Return a random integer *n* such that *a* <= *n* <= *b*.

   .. method:: randrange(stop: i64, /) -> i64
               randrange(start: i64, stop: i64, /) -> i64

      Return a random integer from the range. With one argument, the range is [0, *stop*).
      With two arguments, the range is [*start*, *stop*).

   .. method:: seed(n: i64, /) -> None

      Reseed the generator.

Example
-------

Using module-level functions::

    from librt.random import randint, seed

    def roll_dice() -> i64:
        return randint(1, 6)

Using a ``Random`` instance for reproducible sequences::

    from librt.random import Random

    def generate_data() -> list[i64]:
        rng = Random(42)
        return [rng.randint(0, 100) for _ in range(10)]

Backward compatibility
----------------------

New versions of this module are not guaranteed to generate the same results when
using the same seed. A specific seed only produces predictable random numbers on a
specific version of ``librt``. In the future we might provide stronger guarantees.
