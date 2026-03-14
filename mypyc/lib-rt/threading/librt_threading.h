#ifndef LIBRT_THREADING_H
#define LIBRT_THREADING_H

#ifndef MYPYC_EXPERIMENTAL

static int
import_librt_threading(void)
{
    // All librt.threading features are experimental for now, so don't set up the API here
    return 0;
}

#else  // MYPYC_EXPERIMENTAL

#include <Python.h>

#define LIBRT_THREADING_ABI_VERSION 1
#define LIBRT_THREADING_API_VERSION 1
#define LIBRT_THREADING_API_LEN 3

static void *LibRTThreading_API[LIBRT_THREADING_API_LEN];

#define LibRTThreading_ABIVersion (*(int (*)(void)) LibRTThreading_API[0])
#define LibRTThreading_APIVersion (*(int (*)(void)) LibRTThreading_API[1])
#define LibRTThreading_Lock_type_internal (*(PyTypeObject* (*)(void)) LibRTThreading_API[2])

static int
import_librt_threading(void)
{
    PyObject *mod = PyImport_ImportModule("librt.threading");
    if (mod == NULL)
        return -1;
    Py_DECREF(mod);  // we import just for the side effect of making the below work.
    void *capsule = PyCapsule_Import("librt.threading._C_API", 0);
    if (capsule == NULL)
        return -1;
    memcpy(LibRTThreading_API, capsule, sizeof(LibRTThreading_API));
    if (LibRTThreading_ABIVersion() != LIBRT_THREADING_ABI_VERSION) {
        char err[128];
        snprintf(err, sizeof(err), "ABI version conflict for librt.threading, expected %d, found %d",
            LIBRT_THREADING_ABI_VERSION,
            LibRTThreading_ABIVersion()
        );
        PyErr_SetString(PyExc_ValueError, err);
        return -1;
    }
    if (LibRTThreading_APIVersion() < LIBRT_THREADING_API_VERSION) {
        char err[128];
        snprintf(err, sizeof(err),
                 "API version conflict for librt.threading, expected %d or newer, found %d (hint: upgrade librt)",
            LIBRT_THREADING_API_VERSION,
            LibRTThreading_APIVersion()
        );
        PyErr_SetString(PyExc_ValueError, err);
        return -1;
    }
    return 0;
}

#endif  // MYPYC_EXPERIMENTAL

#endif  // LIBRT_THREADING_H
