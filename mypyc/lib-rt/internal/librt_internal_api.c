#include "librt_internal_api.h"

void *NativeInternal_API[LIBRT_INTERNAL_API_LEN] = {0};

int
import_librt_internal(void)
{
    PyObject *mod = PyImport_ImportModule("librt.internal");
    if (mod == NULL)
        return -1;
    Py_DECREF(mod);  // we import just for the side effect of making the below work.
    void *capsule = PyCapsule_Import("librt.internal._C_API", 0);
    if (capsule == NULL)
        return -1;
    memcpy(NativeInternal_API, capsule, sizeof(NativeInternal_API));
    if (NativeInternal_ABI_Version() != LIBRT_INTERNAL_ABI_VERSION) {
        char err[128];
        snprintf(err, sizeof(err), "ABI version conflict for librt.internal, expected %d, found %d",
            LIBRT_INTERNAL_ABI_VERSION,
            NativeInternal_ABI_Version()
        );
        PyErr_SetString(PyExc_ValueError, err);
        return -1;
    }
    if (NativeInternal_API_Version() < LIBRT_INTERNAL_API_VERSION) {
        char err[128];
        snprintf(err, sizeof(err),
                 "API version conflict for librt.internal, expected %d or newer, found %d (hint: upgrade librt)",
            LIBRT_INTERNAL_API_VERSION,
            NativeInternal_API_Version()
        );
        PyErr_SetString(PyExc_ValueError, err);
        return -1;
    }
    return 0;
}
