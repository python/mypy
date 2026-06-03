#include "pythoncapi_compat.h"

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "librt_threading.h"
#include "mypyc_util.h"

#if CPY_3_14_FEATURES

// Python 3.14+: Use PyMutex (1-byte atomic lock with parking lot).
// PyMutex_LockFast, _PyMutex_LockTimed, and _PY_LOCK_DETACH are internal
// CPython APIs that might change across minor releases.
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
// Prefer a POSIX unnamed semaphore when the platform supports it well, and
// fall back to a pthread mutex + condition variable otherwise. We use the
// same test CPython uses to pick its semaphore-based lock (see
// Python/thread_pthread.h): an unnamed semaphore is only usable when
// sem_init() actually works AND a timed wait is available. Notably this is
// true on Linux but false on macOS (whose sem_init() is a non-functional
// stub), so macOS uses the mutex+condvar fallback.
#include <unistd.h>
#if defined(_POSIX_SEMAPHORES) && (_POSIX_SEMAPHORES + 0) != -1 && \
    (defined(HAVE_SEM_TIMEDWAIT) || defined(HAVE_SEM_CLOCKWAIT))
#define LOCK_BACKEND_SEM
#include <semaphore.h>
#include <errno.h>
#include <stdatomic.h>
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
// On Python 3.14+, this uses CPython's PyMutex, a 1-byte atomic lock
// backed by a parking lot for contended waits. PyMutex automatically
// releases the GIL when blocking.
//
// On older Python with Windows, this uses an SRWLOCK (Slim Reader/Writer
// Lock) plus a CONDITION_VARIABLE guarding a `locked` flag. The SRWLOCK only
// protects the flag and is never held across the user's critical section, so
// release() may be called from a thread other than the acquirer (matching
// threading.Lock semantics). This mirrors CPython's Windows lock (NRMUTEX in
// Python/thread_nt.h) and is the Windows twin of the POSIX pthread+condvar
// backend below.
//
// On older Python with POSIX systems, there are two backends, both of which
// allow release() from a thread other than the one that acquired the lock
// (matching threading.Lock semantics):
//
//  - Where unnamed POSIX semaphores work well (e.g. Linux), this uses a
//    sem_t initialized to 1: acquire is sem_wait, release is sem_post.
//    Semaphores have no ownership concept, so cross-thread release is
//    directly well-defined.
//
//  - Otherwise (e.g. macOS, whose sem_init() is a non-functional stub), this
//    uses a pthread mutex + condition variable guarding a `locked` flag. The
//    mutex only protects the flag and is never held across the user's
//    critical section, so the OS mutex is always unlocked on the same thread
//    that locked it.
//

#ifdef MYPYC_EXPERIMENTAL

// ---------- Platform-specific lock state ----------

#if CPY_3_14_FEATURES

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
    _Atomic int locked;
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

static inline void
Lock_init_internal(LockObject *self)
{
#if CPY_3_14_FEATURES
    self->mutex = (PyMutex){0};
#elif defined(LOCK_BACKEND_SRWLOCK)
    InitializeSRWLock(&self->srw);
    InitializeConditionVariable(&self->lock_released);
    self->locked = 0;
#elif defined(LOCK_BACKEND_SEM)
    sem_init(&self->sem, 0, 1);
    atomic_store_explicit(&self->locked, 0, memory_order_relaxed);
#else
    pthread_mutex_init(&self->mut, NULL);
    pthread_cond_init(&self->lock_released, NULL);
    self->locked = 0;
#endif
}

// Try to acquire the lock. Returns 1 (true) on success, 0 (false) if
// non-blocking and the lock is held.
static int
Lock_acquire_impl(LockObject *self, int blocking)
{
#if CPY_3_14_FEATURES
    if (!blocking) {
        return PyMutex_LockFast(&self->mutex);
    }
    if (PyMutex_LockFast(&self->mutex)) {
        return 1;
    }
    _PyMutex_LockTimed(&self->mutex, -1, _PY_LOCK_DETACH);
    return 1;

#elif defined(LOCK_BACKEND_SRWLOCK)
    // `srw` only guards `locked` and the condition variable; it is held just
    // long enough to inspect/flip the flag, never across the user's critical
    // section. This is what lets a different thread call release().
    if (!blocking) {
        AcquireSRWLockExclusive(&self->srw);
        if (!self->locked) {
            self->locked = 1;
            ReleaseSRWLockExclusive(&self->srw);
            return 1;
        }
        ReleaseSRWLockExclusive(&self->srw);
        return 0;
    }

    // Fast path: grab the lock without releasing the GIL if it is free.
    AcquireSRWLockExclusive(&self->srw);
    if (!self->locked) {
        self->locked = 1;
        ReleaseSRWLockExclusive(&self->srw);
        return 1;
    }
    ReleaseSRWLockExclusive(&self->srw);

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
    if (!blocking) {
        int status;
        do {
            status = sem_trywait(&self->sem);
        } while (status == -1 && errno == EINTR);
        if (status == 0) {
            atomic_store_explicit(&self->locked, 1, memory_order_relaxed);
            return 1;
        }
        return 0;  // EAGAIN: already held
    }

    // Fast path: try non-blocking acquire first to avoid GIL release/reacquire
    // overhead in the common uncontended case.
    {
        int status;
        do {
            status = sem_trywait(&self->sem);
        } while (status == -1 && errno == EINTR);
        if (status == 0) {
            atomic_store_explicit(&self->locked, 1, memory_order_relaxed);
            return 1;
        }
    }

    // Slow path: block with the GIL dropped so other Python threads can run
    // (and release the lock). Retry on EINTR (signal).
    Py_BEGIN_ALLOW_THREADS
    {
        int status;
        do {
            status = sem_wait(&self->sem);
        } while (status == -1 && errno == EINTR);
    }
    Py_END_ALLOW_THREADS
    atomic_store_explicit(&self->locked, 1, memory_order_relaxed);
    return 1;

#else  // pthread mutex + condvar fallback
    // `mut` only guards `locked` and the condition variable; it is held just
    // long enough to inspect/flip the flag, never across the user's critical
    // section. This is what lets a different thread call release().
    if (!blocking) {
        pthread_mutex_lock(&self->mut);
        if (!self->locked) {
            self->locked = 1;
            pthread_mutex_unlock(&self->mut);
            return 1;
        }
        pthread_mutex_unlock(&self->mut);
        return 0;
    }

    // Fast path: grab the lock without releasing the GIL if it is free.
    pthread_mutex_lock(&self->mut);
    if (!self->locked) {
        self->locked = 1;
        pthread_mutex_unlock(&self->mut);
        return 1;
    }
    pthread_mutex_unlock(&self->mut);

    // Slow path: wait for the lock to be released, with the GIL dropped so
    // other Python threads can run (and release the lock).
    Py_BEGIN_ALLOW_THREADS
    pthread_mutex_lock(&self->mut);
    while (self->locked) {
        pthread_cond_wait(&self->lock_released, &self->mut);
    }
    self->locked = 1;
    pthread_mutex_unlock(&self->mut);
    Py_END_ALLOW_THREADS
    return 1;
#endif
}

// Release the lock. Returns 0 on success, -1 if the lock was not held.
static int
Lock_release_impl(LockObject *self)
{
#if CPY_3_14_FEATURES
    // Note: check-then-unlock is not atomic, but this matches CPython's
    // threading.Lock semantics. Only the owning thread should call release().
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
    // Atomically clear the flag; only the caller that observes the previous
    // value as 1 actually owns the release and posts the semaphore. This
    // prevents a double release from over-incrementing the semaphore.
    if (!atomic_exchange_explicit(&self->locked, 0, memory_order_relaxed)) {
        return -1;
    }
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
#if CPY_3_14_FEATURES
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
    // The semaphore backend touches `locked` locklessly (no mutex), so the
    // flag is genuinely atomic and read without locking here.
    return atomic_load_explicit(&self->locked, memory_order_relaxed) != 0;
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

    Lock_init_internal(self);
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
    return PyBool_FromLong(result);
}

static PyObject *
Lock_release(LockObject *self, PyObject *Py_UNUSED(ignored))
{
    if (Lock_release_impl(self) < 0) {
        PyErr_SetString(PyExc_RuntimeError, "release unlocked lock");
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
    if (self != NULL) {
        Lock_init_internal(self);
    }
    return (PyObject *)self;
}

// Acquire the lock (blocking), for use from compiled code.
// Returns true on success.
static char
Lock_acquire_internal(PyObject *self) {
    int result = Lock_acquire_impl((LockObject *)self, 1);
    return (char)result;
}

// Acquire the lock with explicit blocking arg, for use from compiled code.
// Returns true if acquired, false otherwise.
static char
Lock_acquire_blocking_internal(PyObject *self, char blocking) {
    int result = Lock_acquire_impl((LockObject *)self, blocking);
    return (char)result;
}

// Release the lock, for use from compiled code.
// Returns 0 (None) on success, sets error and returns 2 (ERR_MAGIC) on failure.
static char
Lock_release_internal(PyObject *self) {
    if (Lock_release_impl((LockObject *)self) < 0) {
        PyErr_SetString(PyExc_RuntimeError, "release unlocked lock");
        return 2;
    }
    return 0;
}

// Check if the lock is held, for use from compiled code.
static char
Lock_locked_internal(PyObject *self) {
    return (char)Lock_is_locked((LockObject *)self);
}

#endif  // MYPYC_EXPERIMENTAL

static PyMethodDef librt_threading_module_methods[] = {
    {NULL, NULL, 0, NULL}
};

#ifdef MYPYC_EXPERIMENTAL

static int
threading_abi_version(void) {
    return LIBRT_THREADING_ABI_VERSION;
}

static int
threading_api_version(void) {
    return LIBRT_THREADING_API_VERSION;
}

#endif

static int
librt_threading_module_exec(PyObject *m)
{
#ifdef MYPYC_EXPERIMENTAL
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
#endif  // MYPYC_EXPERIMENTAL
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
