#include "librt_time_api.h"

#ifndef MYPYC_EXPERIMENTAL

int
import_librt_time(void)
{
    // All librt.time features are experimental for now, so don't set up the API here
    return 0;
}

#else  // MYPYC_EXPERIMENTAL

void *LibRTTime_API[LIBRT_TIME_API_LEN] = {0};

int
import_librt_time(void)
{
    PyObject *mod = PyImport_ImportModule("librt.time");
    if (mod == NULL)
        return -1;
    Py_DECREF(mod);  // we import just for the side effect of making the below work.
    void *capsule = PyCapsule_Import("librt.time._C_API", 0);
    if (capsule == NULL)
        return -1;
    memcpy(LibRTTime_API, capsule, sizeof(LibRTTime_API));
    if (LibRTTime_ABIVersion() != LIBRT_TIME_ABI_VERSION) {
        char err[128];
        snprintf(err, sizeof(err), "ABI version conflict for librt.time, expected %d, found %d",
            LIBRT_TIME_ABI_VERSION,
            LibRTTime_ABIVersion()
        );
        PyErr_SetString(PyExc_ValueError, err);
        return -1;
    }
    if (LibRTTime_APIVersion() < LIBRT_TIME_API_VERSION) {
        char err[128];
        snprintf(err, sizeof(err),
                 "API version conflict for librt.time, expected %d or newer, found %d (hint: upgrade librt)",
            LIBRT_TIME_API_VERSION,
            LibRTTime_APIVersion()
        );
        PyErr_SetString(PyExc_ValueError, err);
        return -1;
    }
    return 0;
}

#endif // MYPYC_EXPERIMENTAL
