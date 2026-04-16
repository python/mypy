#include "librt_strings_api.h"

#ifndef MYPYC_EXPERIMENTAL

int
import_librt_strings(void)
{
    // All librt.strings features are experimental for now, so don't set up the API here
    return 0;
}

#else  // MYPYC_EXPERIMENTAL

void *LibRTStrings_API[LIBRT_STRINGS_API_LEN] = {0};

int
import_librt_strings(void)
{
    PyObject *mod = PyImport_ImportModule("librt.strings");
    if (mod == NULL)
        return -1;
    Py_DECREF(mod);  // we import just for the side effect of making the below work.
    void *capsule = PyCapsule_Import("librt.strings._C_API", 0);
    if (capsule == NULL)
        return -1;
    memcpy(LibRTStrings_API, capsule, sizeof(LibRTStrings_API));
    if (LibRTStrings_ABIVersion() != LIBRT_STRINGS_ABI_VERSION) {
        char err[128];
        snprintf(err, sizeof(err), "ABI version conflict for librt.strings, expected %d, found %d",
            LIBRT_STRINGS_ABI_VERSION,
            LibRTStrings_ABIVersion()
        );
        PyErr_SetString(PyExc_ValueError, err);
        return -1;
    }
    if (LibRTStrings_APIVersion() < LIBRT_STRINGS_API_VERSION) {
        char err[128];
        snprintf(err, sizeof(err),
                 "API version conflict for librt.strings, expected %d or newer, found %d (hint: upgrade librt)",
            LIBRT_STRINGS_API_VERSION,
            LibRTStrings_APIVersion()
        );
        PyErr_SetString(PyExc_ValueError, err);
        return -1;
    }
    return 0;
}

#endif // MYPYC_EXPERIMENTAL
