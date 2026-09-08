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

void CPyImport_SetInitialized(CPyImportState *state, bool initialized) {
#if PY_VERSION_HEX >= 0x030D0000
    _Py_atomic_store_int32(&state->initialized, initialized);
#else
    state->initialized = initialized;
#endif
}

bool CPyImport_IsExecuted(const CPyImportState *state) {
#if PY_VERSION_HEX >= 0x030D0000
    return _Py_atomic_load_int32(&state->executed) != 0;
#else
    return state->executed != 0;
#endif
}

void CPyImport_SetExecuted(CPyImportState *state) {
#if PY_VERSION_HEX >= 0x030D0000
    _Py_atomic_store_int32(&state->executed, true);
#else
    state->executed = true;
#endif
}

static PyObject *CPyImport_DecodeModuleCache(CPyModuleCache cached) {
    return (PyObject *)(cached & ~CPY_MODULE_CACHE_UNVERIFIED);
}

static CPyModuleCache CPyImport_EncodeModuleCache(PyObject *module, bool unverified) {
    CPyModuleCache cached = (CPyModuleCache)module;
    assert((cached & CPY_MODULE_CACHE_UNVERIFIED) == 0);
    return cached | (unverified ? CPY_MODULE_CACHE_UNVERIFIED : 0);
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

bool CPyImport_IsModuleInitializing(PyObject *module) {
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

PyObject *CPyImport_GetModuleCacheForImport(CPyModuleCache *cache, PyObject *module_name) {
    for (;;) {
        CPyModuleCache cached_value = CPyImport_LoadModuleCache(cache);
        PyObject *cached = CPyImport_DecodeModuleCache(cached_value);
        if (cached == Py_None) {
            return Py_None;
        }

        // An untagged module has already been verified. This is the steady-state
        // fast path and avoids consulting sys.modules or the module spec again.
        if ((cached_value & CPY_MODULE_CACHE_UNVERIFIED) == 0) {
            return cached;
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
        if (!valid) {
            return Py_None;
        }

        // Clearing the tag changes only the cache metadata and does not transfer
        // a reference. Retry if another thread replaced the cache: generated code
        // reloads the cache after this check, so only the value whose tag we
        // successfully cleared may take the fast path.
#if PY_VERSION_HEX >= 0x030D0000
        CPyModuleCache expected = cached_value;
        if (_Py_atomic_compare_exchange_uintptr(cache, &expected, (CPyModuleCache)cached)) {
            return cached;
        }
#else
        if (*cache == cached_value) {
            *cache = (CPyModuleCache)cached;
            return cached;
        }
#endif
    }
}

static void CPyImport_ReplaceModuleCacheValue(CPyModuleCache *cache, PyObject *module,
                                              bool unverified) {
    CPyModuleCache desired = CPyImport_EncodeModuleCache(module, unverified);
#if PY_VERSION_HEX >= 0x030D0000
    for (;;) {
        CPyModuleCache previous = CPyImport_LoadModuleCache(cache);
        if (previous == desired) {
            return;
        }
        CPyModuleCache expected = previous;
        PyObject *previous_module = CPyImport_DecodeModuleCache(previous);
        if (previous_module == module) {
            // Verification is monotonic for a particular module object. A
            // thread that observed it while it was still initializing must not
            // re-tag it after another thread has verified completion.
            if ((previous & CPY_MODULE_CACHE_UNVERIFIED) == 0) {
                return;
            }
            // Only the tag is changing, so the cache retains its existing
            // reference to module.
            if (_Py_atomic_compare_exchange_uintptr(cache, &expected, desired)) {
                return;
            }
        } else {
            Py_INCREF(module);
            if (_Py_atomic_compare_exchange_uintptr(cache, &expected, desired)) {
                if (previous_module != NULL && previous_module != Py_None) {
                    CPyImport_DecRefOld(previous_module);
                }
                return;
            }
            Py_DECREF(module);
        }
    }
#else
    CPyModuleCache previous = *cache;
    PyObject *previous_module = CPyImport_DecodeModuleCache(previous);
    if (previous_module == module) {
        if ((previous & CPY_MODULE_CACHE_UNVERIFIED) != 0) {
            *cache = desired;
        }
        return;
    }
    Py_INCREF(module);
    *cache = desired;
    if (previous_module == NULL || previous_module == Py_None) {
        return;
    }
    CPyImport_DecRefOld(previous_module);
#endif
}

void CPyImport_ReplaceModuleCache(CPyModuleCache *cache, PyObject *module) {
    CPyImport_ReplaceModuleCacheValue(cache, module, false);
}

void CPyImport_ReplaceModuleCacheUnverified(CPyModuleCache *cache, PyObject *module) {
    CPyImport_ReplaceModuleCacheValue(cache, module, true);
}

void CPyImport_ReplaceModuleCacheForImport(CPyModuleCache *cache, PyObject *module) {
    if (CPyImport_LoadModuleCache(cache) == (CPyModuleCache)module) {
        return;
    }

    CPyImport_ReplaceModuleCacheValue(cache, module, CPyImport_IsModuleInitializing(module));
}
