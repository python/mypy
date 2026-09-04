#include "CPy.h"

struct CPyModuleLockAPI {
    PyObject *get_module_lock;
    PyObject *deadlock_error;
};

CPyModuleLockAPI *CPyModuleLockAPI_Alloc(void) {
    CPyModuleLockAPI *api = PyMem_Calloc(1, sizeof(CPyModuleLockAPI));
    if (api == NULL) {
        PyErr_NoMemory();
        return NULL;
    }

    PyObject *bootstrap = PyImport_ImportModule("importlib._bootstrap");
    if (bootstrap == NULL) {
        PyMem_Free(api);
        return NULL;
    }
    api->get_module_lock = PyObject_GetAttrString(bootstrap, "_get_module_lock");
    api->deadlock_error = PyObject_GetAttrString(bootstrap, "_DeadlockError");
    Py_DECREF(bootstrap);
    if (api->get_module_lock == NULL || api->deadlock_error == NULL) {
        CPyModuleLockAPI_Free(api);
        return NULL;
    }
    return api;
}

void CPyModuleLockAPI_Free(CPyModuleLockAPI *api) {
    if (api == NULL) {
        return;
    }
    Py_XDECREF(api->get_module_lock);
    Py_XDECREF(api->deadlock_error);
    PyMem_Free(api);
}

int CPyImport_AcquireLock(CPyModuleLockAPI *api, PyObject *module_name,
                          PyObject **acquired_lock) {
    *acquired_lock = NULL;
    if (api == NULL) {
        return CPY_LOCK_ACQUIRED;
    }

    PyObject *module_lock = PyObject_CallOneArg(api->get_module_lock, module_name);
    if (module_lock == NULL) {
        return CPY_LOCK_ERROR;
    }
    PyObject *result = PyObject_CallMethod(module_lock, "acquire", NULL);
    if (result == NULL) {
        if (PyErr_ExceptionMatches(api->deadlock_error)) {
            PyErr_Clear();
            Py_DECREF(module_lock);
            return CPY_LOCK_DEADLOCK;
        }
        Py_DECREF(module_lock);
        return CPY_LOCK_ERROR;
    }
    Py_DECREF(result);
    *acquired_lock = module_lock;
    return CPY_LOCK_ACQUIRED;
}

int CPyImport_ReleaseLock(PyObject *module_lock) {
    if (module_lock == NULL) {
        return 0;
    }

    PyObject *result = PyObject_CallMethod(module_lock, "release", NULL);
    Py_DECREF(module_lock);
    if (result == NULL) {
        return -1;
    }
    Py_DECREF(result);
    return 0;
}

// CPython exposes pyatomic.h through Python.h starting in 3.13. Older supported
// versions are GIL-only, so plain accesses provide the same serialization there.
bool CPyImport_IsInitialized(const CPyImportState *state) {
#if PY_VERSION_HEX >= 0x030D0000
    return _Py_atomic_load_int32(&state->initialized) != 0;
#else
    return state->initialized != 0;
#endif
}

bool CPyImport_IsInitializedForModule(const CPyImportState *state, PyObject *module,
                                      CPyModule **module_cache) {
    // Read initialized before re-reading the cache. If a retry completed after
    // the caller's first cache load, this load rejects its stale pointer.
    return CPyImport_IsInitialized(state)
        && CPyImport_GetModuleCache(module_cache) == module;
}

void CPyImport_SetInitialized(CPyImportState *state, bool initialized) {
#if PY_VERSION_HEX >= 0x030D0000
    _Py_atomic_store_int32(&state->initialized, initialized);
#else
    state->initialized = initialized;
#endif
}

static void CPyImport_DecRefOld(PyObject *previous) {
    if (previous == NULL) {
        return;
    }
#ifdef Py_GIL_DISABLED
    // Atomic loads return borrowed references, so defer releasing the old
    // reference until concurrent readers have passed a quiescent point.
    CPy_DecRefAttrOld(previous);
#else
    Py_DECREF(previous);
#endif
}

PyObject *CPyImport_GetModuleCache(CPyModule **cache) {
#if PY_VERSION_HEX >= 0x030D0000
    return (PyObject *)_Py_atomic_load_ptr_acquire(cache);
#else
    return (PyObject *)*cache;
#endif
}

static bool CPyImport_IsModuleInitializing(PyObject *module) {
    PyObject *spec = PyObject_GetAttrString(module, "__spec__");
    if (spec == NULL) {
        PyErr_Clear();
        return false;
    }
    PyObject *initializing = PyObject_GetAttrString(spec, "_initializing");
    Py_DECREF(spec);
    if (initializing == NULL) {
        PyErr_Clear();
        return false;
    }
    bool result = Py_IsTrue(initializing);
    Py_DECREF(initializing);
    return result;
}

PyObject *CPyImport_GetModuleCacheForImport(CPyModule **cache, PyObject *module_name) {
    PyObject *cached = CPyImport_GetModuleCache(cache);
    if (cached == Py_None) {
        return Py_None;
    }

    // Generic imports may cache a partial module so compiled references after
    // the import can use the value returned by CPython to break an import-lock
    // deadlock. Such a module must not take the fast path on a later import.
    // Comparing with sys.modules also rejects a partial module left behind in
    // this cache after its initialization failed.
    PyObject *current = PyImport_GetModule(module_name);
    if (current == NULL) {
        return PyErr_Occurred() ? NULL : Py_None;
    }
    bool valid = current == cached && !CPyImport_IsModuleInitializing(current);
    Py_DECREF(current);
    return valid ? cached : Py_None;
}

void CPyImport_SetModuleCache(CPyModule **cache, PyObject *module) {
    Py_INCREF(module);
#if PY_VERSION_HEX >= 0x030D0000
    CPyModule *expected = (CPyModule *)Py_None;
    if (!_Py_atomic_compare_exchange_ptr(cache, &expected, module)) {
        Py_DECREF(module);
    }
#else
    if (*cache == (CPyModule *)Py_None) {
        *cache = (CPyModule *)module;
    } else {
        Py_DECREF(module);
    }
#endif
}

void CPyImport_ReplaceModuleCache(CPyModule **cache, PyObject *module) {
    Py_INCREF(module);
    CPyModule *previous;
#if PY_VERSION_HEX >= 0x030D0000
    previous = (CPyModule *)_Py_atomic_exchange_ptr(cache, module);
#else
    previous = *cache;
    *cache = (CPyModule *)module;
#endif
    if (previous == NULL || previous == (CPyModule *)Py_None) {
        return;
    }
    CPyImport_DecRefOld((PyObject *)previous);
}
