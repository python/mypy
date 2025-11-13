#ifndef LIBRT_BASE64_H
#define LIBRT_BASE64_H

#ifndef MYPYC_EXPERIMENTAL

static int
import_librt_base64(void)
{
    // All librt.base64 features are experimental for now, so don't set up the API here
    return 0;
}

#else  // MYPYC_EXPERIMENTAL

#define LIBRT_BASE64_ABI_VERSION 0
#define LIBRT_BASE64_API_VERSION 0
#define LIBRT_BASE64_API_LEN 3

static void *LibRTBase64_API[LIBRT_BASE64_API_LEN];

#define LibRTBase64_ABIVersion (*(int (*)(void)) LibRTBase64_API[0])
#define LibRTBase64_APIVersion (*(int (*)(void)) LibRTBase64_API[1])
#define LibRTBase64_b64encode_internal (*(PyObject* (*)(PyObject *source)) LibRTBase64_API[2])

static int
import_librt_base64(void)
{
    PyObject *mod = PyImport_ImportModule("librt.base64");
    if (mod == NULL)
        return -1;
    Py_DECREF(mod);  // we import just for the side effect of making the below work.
    void *capsule = PyCapsule_Import("librt.base64._C_API", 0);
    if (capsule == NULL)
        return -1;
    memcpy(LibRTBase64_API, capsule, sizeof(LibRTBase64_API));
    if (LibRTBase64_ABIVersion() != LIBRT_BASE64_ABI_VERSION) {
        char err[128];
        snprintf(err, sizeof(err), "ABI version conflict for librt.base64, expected %d, found %d",
            LIBRT_BASE64_ABI_VERSION,
            LibRTBase64_ABIVersion()
        );
        PyErr_SetString(PyExc_ValueError, err);
        return -1;
    }
    if (LibRTBase64_APIVersion() < LIBRT_BASE64_API_VERSION) {
        char err[128];
        snprintf(err, sizeof(err),
                 "API version conflict for librt.base64, expected %d or newer, found %d (hint: upgrade librt)",
            LIBRT_BASE64_API_VERSION,
            LibRTBase64_APIVersion()
        );
        PyErr_SetString(PyExc_ValueError, err);
        return -1;
    }
    return 0;
}

#endif  // MYPYC_EXPERIMENTAL

#endif  // LIBRT_BASE64_H
