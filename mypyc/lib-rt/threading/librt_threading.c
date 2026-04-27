#include "pythoncapi_compat.h"

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "librt_threading.h"
#include "mypyc_util.h"

#if CPY_3_14_FEATURES

// Python 3.14+: Use PyMutex (1-byte atomic lock with parking lot)
#ifndef Py_BUILD_CORE
#define Py_BUILD_CORE
#endif
#include "internal/pycore_lock.h"

#elif defined(_WIN32)

// Python <3.14 on Windows: Use Slim Reader/Writer Lock
#define LOCK_BACKEND_SRWLOCK
#include <windows.h>

#else

// Python <3.14 on POSIX: Use pthread mutex
#define LOCK_BACKEND_PTHREAD
#include <pthread.h>
#include <stdatomic.h>

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
// On older Python with Windows, this uses SRWLOCK (Slim Reader/Writer Lock),
// a lightweight kernel primitive. A separate volatile flag tracks the locked state.
//
// On older Python with POSIX systems (macOS, Linux, etc.), this uses pthread_mutex
// with a separate atomic flag for locked() and release-unlocked-lock detection.
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
    SRWLOCK lock;
    volatile long locked;  // 0=unlocked, 1=locked (for locked() and error checking)
} LockObject;

#else  // POSIX fallback

typedef struct {
    PyObject_HEAD
    pthread_mutex_t mutex;
    _Atomic int locked;  // 0=unlocked, 1=locked (for locked() and error checking)
} LockObject;

#endif

// ---------- Platform-specific init/acquire/release ----------

static inline void
Lock_init_internal(LockObject *self)
{
#if CPY_3_14_FEATURES
    self->mutex = (PyMutex){0};
#elif defined(LOCK_BACKEND_SRWLOCK)
    InitializeSRWLock(&self->lock);
    self->locked = 0;
#else
    pthread_mutex_init(&self->mutex, NULL);
    atomic_store_explicit(&self->locked, 0, memory_order_relaxed);
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
    if (!blocking) {
        if (TryAcquireSRWLockExclusive(&self->lock)) {
            InterlockedExchange(&self->locked, 1);
            return 1;
        }
        return 0;
    }

    // Fast path: try non-blocking acquire first to avoid GIL release/reacquire
    // overhead in the common uncontended case.
    if (TryAcquireSRWLockExclusive(&self->lock)) {
        InterlockedExchange(&self->locked, 1);
        return 1;
    }

    Py_BEGIN_ALLOW_THREADS
    AcquireSRWLockExclusive(&self->lock);
    Py_END_ALLOW_THREADS
    InterlockedExchange(&self->locked, 1);
    return 1;

#else  // POSIX fallback
    if (!blocking) {
        if (pthread_mutex_trylock(&self->mutex) == 0) {
            atomic_store_explicit(&self->locked, 1, memory_order_relaxed);
            return 1;
        }
        return 0;
    }

    // Fast path: try non-blocking acquire first to avoid GIL release/reacquire
    // overhead in the common uncontended case.
    if (pthread_mutex_trylock(&self->mutex) == 0) {
        atomic_store_explicit(&self->locked, 1, memory_order_relaxed);
        return 1;
    }

    Py_BEGIN_ALLOW_THREADS
    pthread_mutex_lock(&self->mutex);
    Py_END_ALLOW_THREADS
    atomic_store_explicit(&self->locked, 1, memory_order_relaxed);
    return 1;
#endif
}

// Release the lock. Returns 0 on success, -1 if the lock was not held.
static int
Lock_release_impl(LockObject *self)
{
#if CPY_3_14_FEATURES
    if (!PyMutex_IsLocked(&self->mutex)) {
        return -1;
    }
    PyMutex_Unlock(&self->mutex);
    return 0;

#elif defined(LOCK_BACKEND_SRWLOCK)
    if (!InterlockedExchange(&self->locked, 0)) {
        return -1;
    }
    ReleaseSRWLockExclusive(&self->lock);
    return 0;

#else  // POSIX fallback
    if (!atomic_exchange_explicit(&self->locked, 0, memory_order_relaxed)) {
        return -1;
    }
    pthread_mutex_unlock(&self->mutex);
    return 0;
#endif
}

static inline int
Lock_is_locked(LockObject *self)
{
#if CPY_3_14_FEATURES
    return PyMutex_IsLocked(&self->mutex);
#elif defined(LOCK_BACKEND_SRWLOCK)
    return InterlockedCompareExchange(&self->locked, 0, 0) != 0;
#else
    return atomic_load_explicit(&self->locked, memory_order_relaxed) != 0;
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
#ifdef LOCK_BACKEND_PTHREAD
    pthread_mutex_destroy(&self->mutex);
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
