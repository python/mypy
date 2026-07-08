.. _librt-threading:

librt.threading
===============

The ``librt.threading`` module is part of the ``librt`` package on PyPI, and it includes
threading primitives.

Classes
-------

Lock
^^^^

.. class:: Lock

   A fast mutual exclusion lock. This can be used as a faster replacement for
   :py:class:`threading.Lock` in compiled code.

   Like :py:class:`threading.Lock`, a ``Lock`` is *unowned*: it may be released by a thread
   other than the one that acquired it, and it doesn't support reentrant (recursive) locking.
   A newly created lock is unlocked.

   ``Lock`` can be used as a context manager. The lock is acquired (blocking) on entry and
   released on exit, including when the body raises an exception::

       def example(lock: Lock) -> None:
           with lock:
               ...  # Critical section; the lock is held here.

   ``Lock`` cannot be subclassed. ``Lock`` cannot be used with :py:class:`threading.Condition`.

   .. method:: acquire(blocking: bool = True) -> bool

      Acquire the lock.

      When *blocking* is true (the default), block (if needed) until the lock is available,
      acquire it, and return ``True``. When *blocking* is false, acquire the lock only if it
      can be done without blocking: return ``True`` if the lock could be acquired, or
      ``False`` otherwise (it was already locked by some thread).

      Unlike :py:meth:`threading.Lock.acquire`, there is no *timeout* argument.

   .. method:: release() -> None

      Release the lock, allowing another thread (if any) that is blocked on :meth:`acquire`
      to proceed. Since the lock is unowned, it may be released from a thread other than the
      one that acquired it.

      Raise :py:exc:`RuntimeError` if the lock is not currently held.

   .. method:: locked() -> bool

      Return ``True`` if the lock is currently held (by any thread).
