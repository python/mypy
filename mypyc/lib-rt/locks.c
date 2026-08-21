#include "CPy.h"

#ifdef _WIN32
#include <windows.h>
#endif

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

bool CPyImport_IsInitialized(const CPyImportState *state) {
#ifdef _WIN32
    return InterlockedCompareExchange(
        (volatile LONG *)&state->initialized, 0, 0) != 0;
#else
    return __atomic_load_n(&state->initialized, __ATOMIC_ACQUIRE) != 0;
#endif
}

void CPyImport_SetInitialized(CPyImportState *state, bool initialized) {
#ifdef _WIN32
    InterlockedExchange((volatile LONG *)&state->initialized, initialized);
#else
    __atomic_store_n(&state->initialized, initialized, __ATOMIC_RELEASE);
#endif
}
