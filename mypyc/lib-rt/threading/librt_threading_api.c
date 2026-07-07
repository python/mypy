#include "librt_threading_api.h"

void *LibRTThreading_API[LIBRT_THREADING_API_LEN] = {0};

int
import_librt_threading(void)
{
    PyObject *mod = PyImport_ImportModule("librt.threading");
    if (mod == NULL)
        return -1;
    Py_DECREF(mod);  // we import just for the side effect of making the below work.
    void **capsule = (void **)PyCapsule_Import("librt.threading._C_API", 0);
    if (capsule == NULL)
        return -1;

    // Only after version validation succeeds can we safely copy the full table.
    int (*abi_version)(void) = (int (*)(void))capsule[0];
    int (*api_version)(void) = (int (*)(void))capsule[1];
    if (abi_version() != LIBRT_THREADING_ABI_VERSION) {
        char err[128];
        snprintf(err, sizeof(err), "ABI version conflict for librt.threading, expected %d, found %d",
            LIBRT_THREADING_ABI_VERSION,
            abi_version()
        );
        PyErr_SetString(PyExc_ValueError, err);
        return -1;
    }
    if (api_version() < LIBRT_THREADING_API_VERSION) {
        char err[128];
        snprintf(err, sizeof(err),
                 "API version conflict for librt.threading, expected %d or newer, found %d (hint: upgrade librt)",
            LIBRT_THREADING_API_VERSION,
            api_version()
        );
        PyErr_SetString(PyExc_ValueError, err);
        return -1;
    }
    // Provider API version is >= our expected version, which (by the API
    // compatibility contract) means it has at least LIBRT_THREADING_API_LEN
    // entries, so this copy is safe.
    memcpy(LibRTThreading_API, capsule, sizeof(LibRTThreading_API));
    return 0;
}
