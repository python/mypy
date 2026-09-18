#include "pythoncapi_compat.h"

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "librt_threading.h"
#include "mypyc_util.h"

#if !defined(_WIN32)
#include <unistd.h>
#include <errno.h>
#endif

#if CPY_3_14_FEATURES

// Python 3.14+ (all platforms, with or without the GIL): Use PyMutex (1-byte
// atomic lock with parking lot). PyMutex gives better interruptibility than the
// pthread fallback, and its fast release path is competitive with sem_t.
// PyMutex_LockFast, _PyMutex_LockTimed, and _PY_LOCK_DETACH are internal
// CPython APIs that might change across minor releases.
#define LOCK_BACKEND_PYMUTEX
#ifndef Py_BUILD_CORE
#define Py_BUILD_CORE
#endif
#include "internal/pycore_lock.h"

#elif defined(_WIN32)

// Python <3.14 on Windows: Use Slim Reader/Writer Lock
#define LOCK_BACKEND_SRWLOCK
#include <windows.h>

#else

// Python <3.14 on POSIX.
//
// Prefer a POSIX unnamed semaphore when the platform supports it well and the
// GIL is enabled, and fall back to a pthread mutex + condition variable
// otherwise. We use the same test CPython uses to pick its semaphore-based lock
// (see Python/thread_pthread.h): an unnamed semaphore is only usable when
// sem_init() actually works AND a timed wait is available. Notably this is true
// on Linux but false on macOS (whose sem_init() is a non-functional stub), so
// macOS uses the mutex+condvar fallback. Free-threaded builds also use the
// mutex+condvar fallback because the semaphore backend's `locked` bookkeeping
// relies on GIL serialization.
#if !defined(Py_GIL_DISABLED) && \
    defined(_POSIX_SEMAPHORES) && (_POSIX_SEMAPHORES + 0) != -1 && \
    (defined(HAVE_SEM_TIMEDWAIT) || defined(HAVE_SEM_CLOCKWAIT))
#define LOCK_BACKEND_SEM
#include <semaphore.h>
#else
#define LOCK_BACKEND_PTHREAD
#include <pthread.h>
#endif

#endif

//
// Lock
//
// A fast mutex lock for use from mypyc-compiled code.
//
// On Python 3.14+ (all platforms), this uses CPython's PyMutex, a 1-byte atomic
// lock backed by a parking lot for contended waits. PyMutex automatically
// releases the GIL when blocking.
//
// On Python 3.13 and earlier with Windows, this uses an SRWLOCK (Slim
// Reader/Writer Lock) plus a CONDITION_VARIABLE guarding a `locked` flag. The SRWLOCK only
// protects the flag and is never held across the user's critical section, so
// release() may be called from a thread other than the acquirer (matching
// threading.Lock semantics). This mirrors CPython's Windows lock (NRMUTEX in
// Python/thread_nt.h) and is the Windows twin of the POSIX pthread+condvar
// backend below.
//
// On Python 3.13 and earlier with POSIX systems, there are two backends, both
// of which allow release() from a thread other than the one that acquired the
// lock (matching threading.Lock semantics):
//
//  - Where unnamed POSIX semaphores work well (e.g. Linux) and the GIL is
//    enabled, this uses a sem_t initialized to 1: acquire is sem_wait, release
//    is sem_post. Semaphores have no ownership concept, so cross-thread release
//    is directly well-defined.
//
//  - Otherwise (e.g. macOS, whose sem_init() is a non-functional stub, and
//    free-threaded builds), this uses a pthread mutex + condition variable
//    guarding a `locked` flag. The mutex only protects the flag and is never
//    held across the user's critical section, so the OS mutex is always
//    unlocked on the same thread that locked it.
//

// ---------- Platform-specific lock state ----------

#if defined(LOCK_BACKEND_PYMUTEX)

typedef struct {
    PyObject_HEAD
    PyMutex mutex;
} LockObject;

#elif defined(LOCK_BACKEND_SRWLOCK)

typedef struct {
    PyObject_HEAD
    // The SRWLOCK below does NOT represent the Python lock; like the pthread
    // fallback's `mut`, it only guards `locked` and the condition variable,
    // and is held just long enough to inspect/flip the flag -- never across
    // the user's critical section. That is what allows release() from a
    // thread other than the acquirer: SRWLOCK's same-thread-release rule is
    // never violated, and clearing `locked` is just a guarded store. This
    // mirrors CPython's Windows lock (NRMUTEX in Python/thread_nt.h).
    SRWLOCK srw;
    CONDITION_VARIABLE lock_released;
    int locked;  // 0=unlocked, 1=locked; protected by `srw`
} LockObject;

#elif defined(LOCK_BACKEND_SEM)

typedef struct {
    PyObject_HEAD
    sem_t sem;          // counting semaphore, initialized to 1
    // Tracks the locked state for locked() and release-unlocked detection.
    // The semaphore itself is the source of truth for mutual exclusion; this
    // flag is advisory bookkeeping. It is set after a successful acquire and
    // cleared before sem_post in release.
    //
    // This backend is only selected when the GIL is enabled, so this flag is a
    // plain int relying on the GIL for serialization: it is only ever touched
    // with the GIL held (the blocking sem_wait drops the GIL, but the flag
    // store happens after the GIL is reacquired). This mirrors the old
    // PyThread_type_lock wrapper bookkeeping used by CPython 3.12 and earlier,
    // where _thread lock kept a plain `char locked` for sanity checks and
    // locked().
    int locked;
} LockObject;

#else  // pthread mutex + condvar fallback

typedef struct {
    PyObject_HEAD
    // The pthread mutex below does NOT represent the Python lock; it only
    // guards the `locked` flag and the condition variable. The Python lock
    // state is `locked` itself. This indirection (matching CPython's POSIX
    // lock) is what allows release() from a thread other than the acquirer:
    // `mut` is always locked and unlocked within a single call on a single
    // thread, so pthread's same-thread-unlock rule is never violated.
    pthread_mutex_t mut;
    pthread_cond_t lock_released;
    // Always accessed while holding `mut` (including the locked() reader),
    // so a plain int is sufficient -- the mutex provides the ordering.
    // Matches CPython's pthread_lock.locked (a plain char).
    int locked;  // 0=unlocked, 1=locked; protected by `mut`
} LockObject;

#endif

// ---------- Platform-specific init/acquire/release ----------

static inline int
Lock_init_internal(LockObject *self)
{
#if defined(LOCK_BACKEND_PYMUTEX)
    self->mutex = (PyMutex){0};
#elif defined(LOCK_BACKEND_SRWLOCK)
    InitializeSRWLock(&self->srw);
    InitializeConditionVariable(&self->lock_released);
    self->locked = 0;
#elif defined(LOCK_BACKEND_SEM)
    if (sem_init(&self->sem, 0, 1) != 0) {
        PyErr_SetFromErrno(PyExc_OSError);
        return -1;
    }
    self->locked = 0;
#else
    int status = pthread_mutex_init(&self->mut, NULL);
    if (status != 0) {
        errno = status;
        PyErr_SetFromErrno(PyExc_OSError);
        return -1;
    }

    status = pthread_cond_init(&self->lock_released, NULL);
    if (status != 0) {
        pthread_mutex_destroy(&self->mut);
        errno = status;
        PyErr_SetFromErrno(PyExc_OSError);
        return -1;
    }

    self->locked = 0;
#endif
    return 0;
}

// Try to acquire the lock. Returns 1 (true) on success, 0 (false) if
// non-blocking and the lock is held, or -1 if interrupted by an error-raising
// signal handler.
static int
Lock_acquire_impl(LockObject *self, int blocking)
{
#if defined(LOCK_BACKEND_PYMUTEX)
    if (!blocking) {
        PyLockStatus r = _PyMutex_LockTimed(&self->mutex, 0, _Py_LOCK_DONT_DETACH);
        return r == PY_LOCK_ACQUIRED;
    }
    if (PyMutex_LockFast(&self->mutex)) {
        return 1;
    }
    PyLockStatus r = _PyMutex_LockTimed(&self->mutex, -1,
                                        _PY_LOCK_DETACH | _PY_LOCK_HANDLE_SIGNALS);
    if (r == PY_LOCK_INTR) {
        return -1;
    }
    return 1;

#elif defined(LOCK_BACKEND_SRWLOCK)
    // `srw` only guards `locked` and the condition variable; it is held just
    // long enough to inspect/flip the flag, never across the user's critical
    // section. This is what lets a different thread call release().
    //
    // Fast path: grab the lock without releasing the GIL if it is free. This is
    // also the whole story in the non-blocking case.
    AcquireSRWLockExclusive(&self->srw);
    if (!self->locked) {
        self->locked = 1;
        ReleaseSRWLockExclusive(&self->srw);
        return 1;
    }
    ReleaseSRWLockExclusive(&self->srw);
    if (!blocking) {
        return 0;
    }

    // Slow path: wait for the lock to be released, with the GIL dropped so
    // other Python threads can run (and release the lock).
    // SleepConditionVariableSRW atomically releases the SRWLOCK while sleeping
    // and reacquires it on wake, exactly like pthread_cond_wait.
    Py_BEGIN_ALLOW_THREADS
    AcquireSRWLockExclusive(&self->srw);
    while (self->locked) {
        SleepConditionVariableSRW(&self->lock_released, &self->srw, INFINITE, 0);
    }
    self->locked = 1;
    ReleaseSRWLockExclusive(&self->srw);
    Py_END_ALLOW_THREADS
    return 1;

#elif defined(LOCK_BACKEND_SEM)
    // A semaphore has no ownership: any thread may sem_post a token that
    // another thread consumed via sem_wait, so cross-thread release is
    // directly well-defined. `locked` is advisory bookkeeping for locked()
    // and for guarding against releasing an unheld lock.
    //
    // Fast path: try a non-blocking acquire first to avoid GIL release/reacquire
    // overhead in the common uncontended case. This is also the whole story in
    // the non-blocking case.
    {
        int status;
        do {
            status = sem_trywait(&self->sem);
        } while (status == -1 && errno == EINTR);
        if (status == 0) {
            self->locked = 1;
            return 1;
        }
    }
    if (!blocking) {
        return 0;  // EAGAIN: already held
    }

    // Slow path: block with the GIL dropped so other Python threads can run
    // (and release the lock). If a signal interrupts sem_wait(), run pending
    // Python signal handlers with the GIL held; retry unless a handler raises.
    for (;;) {
        int status;
        int err = 0;

        Py_BEGIN_ALLOW_THREADS
        status = sem_wait(&self->sem);
        if (status == -1) {
            err = errno;
        }
        Py_END_ALLOW_THREADS

        if (status == 0) {
            self->locked = 1;
            return 1;
        }

        if (err != EINTR) {
            PyErr_SetFromErrno(PyExc_OSError);
            return -1;
        }

        if (Py_MakePendingCalls() < 0) {
            return -1;
        }
    }

#else  // pthread mutex + condvar fallback
    // `mut` only guards `locked` and the condition variable; it is held just
    // long enough to inspect/flip the flag, never across the user's critical
    // section. This is what lets a different thread call release().
    //
    // Fast path: grab the lock without releasing the GIL if it is free. This is
    // also the whole story in the non-blocking case.
    pthread_mutex_lock(&self->mut);
    if (!self->locked) {
        self->locked = 1;
        pthread_mutex_unlock(&self->mut);
        return 1;
    }
    pthread_mutex_unlock(&self->mut);
    if (!blocking) {
        return 0;
    }

    // Slow path: wait for the lock to be released, with the GIL dropped so
    // other Python threads can run (and release the lock). If we wake but do
    // not get the lock, give pending Python signal handlers a chance to run,
    // matching CPython's pthread fallback.
    for (;;) {
        int acquired = 0;
        int interrupted = 0;
        int status;

        Py_BEGIN_ALLOW_THREADS
        status = pthread_mutex_lock(&self->mut);
        if (status == 0) {
            while (self->locked) {
                status = pthread_cond_wait(&self->lock_released, &self->mut);
                if (status != 0) {
                    break;
                }
                if (self->locked) {
                    interrupted = 1;
                    break;
                }
            }
            if (status == 0 && !interrupted) {
                self->locked = 1;
                acquired = 1;
            }
            int unlock_status = pthread_mutex_unlock(&self->mut);
            if (status == 0) {
                status = unlock_status;
            }
        }
        Py_END_ALLOW_THREADS

        if (status != 0) {
            errno = status;
            PyErr_SetFromErrno(PyExc_OSError);
            return -1;
        }
        if (acquired) {
            return 1;
        }
        if (interrupted && Py_MakePendingCalls() < 0) {
            return -1;
        }
    }
#endif
}

// Release the lock. Returns 0 on success, -1 if the lock was not held.
static int
Lock_release_impl(LockObject *self)
{
#if defined(LOCK_BACKEND_PYMUTEX)
    // threading.Lock is unowned, so release() may be called from a different
    // thread than acquire(). CPython's atomic _PyMutex_TryUnlock() is not part
    // of the public API and is not exported by all CPython builds. This fast
    // partial-replacement path deliberately avoids a second guard mutex:
    // ordinary release() of an unlocked lock raises RuntimeError, but racy
    // erroneous release() calls are undefined behavior and may make
    // PyMutex_Unlock() abort.
    if (!PyMutex_IsLocked(&self->mutex)) {
        return -1;
    }
    PyMutex_Unlock(&self->mutex);
    return 0;

#elif defined(LOCK_BACKEND_SRWLOCK)
    AcquireSRWLockExclusive(&self->srw);
    if (!self->locked) {
        ReleaseSRWLockExclusive(&self->srw);
        return -1;
    }
    self->locked = 0;
    // Wake one waiter (if any). Signalling under `srw` is fine and avoids a
    // lost-wakeup race.
    WakeConditionVariable(&self->lock_released);
    ReleaseSRWLockExclusive(&self->srw);
    return 0;

#elif defined(LOCK_BACKEND_SEM)
    // Check-then-clear the flag, then post. This backend is only selected when
    // the GIL is enabled, so the check and clear are serialized without an
    // atomic.
    if (!self->locked) {
        return -1;
    }
    self->locked = 0;
    sem_post(&self->sem);
    return 0;

#else  // pthread mutex + condvar fallback
    pthread_mutex_lock(&self->mut);
    if (!self->locked) {
        pthread_mutex_unlock(&self->mut);
        return -1;
    }
    self->locked = 0;
    // Wake one waiter (if any). Signalling under `mut` is fine and avoids a
    // lost-wakeup race.
    pthread_cond_signal(&self->lock_released);
    pthread_mutex_unlock(&self->mut);
    return 0;
#endif
}

static inline int
Lock_is_locked(LockObject *self)
{
#if defined(LOCK_BACKEND_PYMUTEX)
    return PyMutex_IsLocked(&self->mutex);
#elif defined(LOCK_BACKEND_SRWLOCK)
    // locked() is not expected to be on a perf-critical path, so take the
    // SRWLOCK (shared) for a clean read of the guarded flag rather than
    // relying on an atomic/volatile field.
    AcquireSRWLockShared(&self->srw);
    int result = self->locked;
    ReleaseSRWLockShared(&self->srw);
    return result;
#elif defined(LOCK_BACKEND_SEM)
    // The flag is GIL-serialized (see the struct comment); locked() is a
    // plain read, matching the old CPython _thread lock bookkeeping described
    // above.
    return self->locked != 0;
#else  // pthread mutex + condvar fallback
    // `locked` is only ever accessed under `mut`; take it for a clean read.
    // locked() is not expected to be on a perf-critical path.
    pthread_mutex_lock(&self->mut);
    int result = self->locked;
    pthread_mutex_unlock(&self->mut);
    return result;
#endif
}

// ---------- Python type methods (shared across platforms) ----------

static PyTypeObject LockType;

static PyObject *
Lock_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    if (type != &LockType) {
        PyErr_SetString(PyExc_TypeError, "Lock cannot be subclassed");
        return NULL;
    }

    LockObject *self = (LockObject *)type->tp_alloc(type, 0);
    if (self != NULL && Lock_init_internal(self) < 0) {
        type->tp_free((PyObject *)self);
        return NULL;
    }
    return (PyObject *)self;
}

static int
Lock_init(LockObject *self, PyObject *args, PyObject *kwds)
{
    if (!PyArg_ParseTuple(args, "")) {
        return -1;
    }

    if (kwds != NULL && PyDict_Size(kwds) > 0) {
        PyErr_SetString(PyExc_TypeError,
                        "Lock() takes no keyword arguments");
        return -1;
    }

    return 0;
}

static void
Lock_dealloc(LockObject *self)
{
#if defined(LOCK_BACKEND_SEM)
    sem_destroy(&self->sem);
#elif defined(LOCK_BACKEND_PTHREAD)
    // `mut` is only ever held transiently within a single call, so it is
    // always unlocked here even if the Python lock is still "locked".
    // Some pthread implementations require the cond to be destroyed first.
    pthread_cond_destroy(&self->lock_released);
    pthread_mutex_destroy(&self->mut);
#endif
    Py_TYPE(self)->tp_free((PyObject *)self);
}

static PyObject *
Lock_acquire(LockObject *self, PyObject *const *args, Py_ssize_t nargs,
             PyObject *kwnames)
{
    int blocking = 1;

    Py_ssize_t nkw = kwnames ? PyTuple_GET_SIZE(kwnames) : 0;
    if (nargs + nkw > 1) {
        PyErr_SetString(PyExc_TypeError, "acquire() takes at most 1 argument");
        return NULL;
    }

    if (nargs == 1) {
        blocking = PyObject_IsTrue(args[0]);
        if (blocking < 0)
            return NULL;
    } else if (nkw == 1) {
        PyObject *key = PyTuple_GET_ITEM(kwnames, 0);
        if (PyUnicode_CompareWithASCIIString(key, "blocking") != 0) {
            PyErr_Format(PyExc_TypeError,
                         "acquire() got an unexpected keyword argument '%U'",
                         key);
            return NULL;
        }
        blocking = PyObject_IsTrue(args[0]);
        if (blocking < 0)
            return NULL;
    }

    int result = Lock_acquire_impl(self, blocking);
    if (result < 0) {
        return NULL;
    }
    return PyBool_FromLong(result);
}

static PyObject *
Lock_release(LockObject *self, PyObject *Py_UNUSED(ignored))
{
    if (Lock_release_impl(self) < 0) {
        PyErr_SetString(PyExc_RuntimeError, "cannot release an unlocked lock");
        return NULL;
    }
    Py_RETURN_NONE;
}

static PyObject *
Lock_locked(LockObject *self, PyObject *Py_UNUSED(ignored))
{
    return PyBool_FromLong(Lock_is_locked(self));
}

static PyObject *
Lock_enter(LockObject *self, PyObject *Py_UNUSED(ignored))
{
    int result = Lock_acquire_impl(self, 1);
    if (result < 0)
        return NULL;
    return PyBool_FromLong(result);
}

static PyObject *
Lock_exit(LockObject *self, PyObject *const *args, Py_ssize_t nargs)
{
    return Lock_release(self, NULL);
}

static PyMethodDef Lock_methods[] = {
    {"acquire", (PyCFunction)(void(*)(void))Lock_acquire, METH_FASTCALL | METH_KEYWORDS,
     PyDoc_STR("Acquire the lock, blocking or non-blocking.\n"
               "Returns True if the lock was acquired, False otherwise.")},
    {"release", (PyCFunction)Lock_release, METH_NOARGS,
     PyDoc_STR("Release the lock.")},
    {"locked", (PyCFunction)Lock_locked, METH_NOARGS,
     PyDoc_STR("Return True if the lock is currently held.")},
    {"__enter__", (PyCFunction)Lock_enter, METH_NOARGS,
     PyDoc_STR("Acquire the lock.")},
    {"__exit__", (PyCFunction)Lock_exit, METH_FASTCALL,
     PyDoc_STR("Release the lock.")},
    {NULL}
};

static PyTypeObject LockType = {
    .ob_base = PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "Lock",
    .tp_doc = PyDoc_STR("A fast mutual exclusion lock"),
    .tp_basicsize = sizeof(LockObject),
    .tp_itemsize = 0,
    .tp_flags = Py_TPFLAGS_DEFAULT,
    .tp_new = Lock_new,
    .tp_init = (initproc)Lock_init,
    .tp_dealloc = (destructor)Lock_dealloc,
    .tp_methods = Lock_methods,
};

static PyTypeObject *
Lock_type_internal(void) {
    return &LockType;
}

// Create a new Lock object (for use from compiled code)
static PyObject *
Lock_new_internal(void) {
    LockObject *self = (LockObject *)LockType.tp_alloc(&LockType, 0);
    if (self != NULL && Lock_init_internal(self) < 0) {
        LockType.tp_free((PyObject *)self);
        return NULL;
    }
    return (PyObject *)self;
}

// Acquire the lock (blocking), for use from compiled code.
// Returns true on success, sets error and returns 2 (ERR_MAGIC) on failure.
static char
Lock_acquire_internal(PyObject *self) {
    int result = Lock_acquire_impl((LockObject *)self, 1);
    if (result < 0) {
        return 2;
    }
    return (char)result;
}

// Acquire the lock with explicit blocking arg, for use from compiled code.
// Returns true if acquired, false otherwise. Sets error and returns 2
// (ERR_MAGIC) on failure.
static char
Lock_acquire_blocking_internal(PyObject *self, char blocking) {
    int result = Lock_acquire_impl((LockObject *)self, blocking);
    if (result < 0) {
        return 2;
    }
    return (char)result;
}

// Release the lock, for use from compiled code.
// Returns 0 (None) on success, sets error and returns 2 (ERR_MAGIC) on failure.
static char
Lock_release_internal(PyObject *self) {
    if (Lock_release_impl((LockObject *)self) < 0) {
        PyErr_SetString(PyExc_RuntimeError, "cannot release an unlocked lock");
        return 2;
    }
    return 0;
}

// Check if the lock is held, for use from compiled code.
static char
Lock_locked_internal(PyObject *self) {
    return (char)Lock_is_locked((LockObject *)self);
}

static PyMethodDef librt_threading_module_methods[] = {
    {NULL, NULL, 0, NULL}
};

static int
threading_abi_version(void) {
    return LIBRT_THREADING_ABI_VERSION;
}

static int
threading_api_version(void) {
    return LIBRT_THREADING_API_VERSION;
}

static int
librt_threading_module_exec(PyObject *m)
{
    if (PyType_Ready(&LockType) < 0) {
        return -1;
    }
    if (PyModule_AddObjectRef(m, "Lock", (PyObject *)&LockType) < 0) {
        return -1;
    }

    // Export mypyc internal C API via capsule
    static void *threading_api[LIBRT_THREADING_API_LEN] = {
        (void *)threading_abi_version,
        (void *)threading_api_version,
        (void *)Lock_type_internal,
        (void *)Lock_new_internal,
        (void *)Lock_acquire_internal,
        (void *)Lock_release_internal,
        (void *)Lock_locked_internal,
        (void *)Lock_acquire_blocking_internal,
    };
    PyObject *c_api_object = PyCapsule_New((void *)threading_api, "librt.threading._C_API", NULL);
    if (PyModule_Add(m, "_C_API", c_api_object) < 0) {
        return -1;
    }
    return 0;
}

static PyModuleDef_Slot librt_threading_module_slots[] = {
    {Py_mod_exec, librt_threading_module_exec},
#ifdef Py_MOD_GIL_NOT_USED
    {Py_mod_gil, Py_MOD_GIL_NOT_USED},
#endif
    {0, NULL}
};

static PyModuleDef librt_threading_module = {
    .m_base = PyModuleDef_HEAD_INIT,
    .m_name = "threading",
    .m_doc = "Fast threading primitives optimized for mypyc",
    .m_size = 0,
    .m_methods = librt_threading_module_methods,
    .m_slots = librt_threading_module_slots,
};

PyMODINIT_FUNC
PyInit_threading(void)
{
    return PyModuleDef_Init(&librt_threading_module);
}
