#ifndef LIBRT_RANDOM_H
#define LIBRT_RANDOM_H

#ifndef MYPYC_EXPERIMENTAL

static int
import_librt_random(void)
{
    // All librt.random features are experimental for now, so don't set up the API here
    return 0;
}

#else  // MYPYC_EXPERIMENTAL

#include <Python.h>

#define LIBRT_RANDOM_ABI_VERSION 1
#define LIBRT_RANDOM_API_VERSION 9
#define LIBRT_RANDOM_API_LEN 17

static void *LibRTRandom_API[LIBRT_RANDOM_API_LEN];

#define LibRTRandom_ABIVersion (*(int (*)(void)) LibRTRandom_API[0])
#define LibRTRandom_APIVersion (*(int (*)(void)) LibRTRandom_API[1])
#define LibRTRandom_Random_internal (*(PyObject* (*)(void)) LibRTRandom_API[2])
#define LibRTRandom_Random_from_seed_internal (*(PyObject* (*)(int64_t)) LibRTRandom_API[3])
#define LibRTRandom_Random_type_internal (*(PyTypeObject* (*)(void)) LibRTRandom_API[4])
#define LibRTRandom_Random_randbits62_internal (*(int64_t (*)(PyObject*)) LibRTRandom_API[5])
#define LibRTRandom_Random_random_internal (*(double (*)(PyObject*)) LibRTRandom_API[6])
#define LibRTRandom_Random_randbits31_internal (*(int32_t (*)(PyObject*)) LibRTRandom_API[7])
#define LibRTRandom_Random_randint_internal (*(int64_t (*)(PyObject*, int64_t, int64_t)) LibRTRandom_API[8])
#define LibRTRandom_Random_randrange1_internal (*(int64_t (*)(PyObject*, int64_t)) LibRTRandom_API[9])
#define LibRTRandom_Random_randrange2_internal (*(int64_t (*)(PyObject*, int64_t, int64_t)) LibRTRandom_API[10])
#define LibRTRandom_module_random_internal (*(double (*)(void)) LibRTRandom_API[11])
#define LibRTRandom_module_randint_internal (*(int64_t (*)(int64_t, int64_t)) LibRTRandom_API[12])
#define LibRTRandom_module_randrange1_internal (*(int64_t (*)(int64_t)) LibRTRandom_API[13])
#define LibRTRandom_module_randrange2_internal (*(int64_t (*)(int64_t, int64_t)) LibRTRandom_API[14])
#define LibRTRandom_module_randbits31_internal (*(int32_t (*)(void)) LibRTRandom_API[15])
#define LibRTRandom_module_randbits62_internal (*(int64_t (*)(void)) LibRTRandom_API[16])

static int
import_librt_random(void)
{
    PyObject *mod = PyImport_ImportModule("librt.random");
    if (mod == NULL)
        return -1;
    Py_DECREF(mod);  // we import just for the side effect of making the below work.
    void *capsule = PyCapsule_Import("librt.random._C_API", 0);
    if (capsule == NULL)
        return -1;
    memcpy(LibRTRandom_API, capsule, sizeof(LibRTRandom_API));
    if (LibRTRandom_ABIVersion() != LIBRT_RANDOM_ABI_VERSION) {
        char err[128];
        snprintf(err, sizeof(err), "ABI version conflict for librt.random, expected %d, found %d",
            LIBRT_RANDOM_ABI_VERSION,
            LibRTRandom_ABIVersion()
        );
        PyErr_SetString(PyExc_ValueError, err);
        return -1;
    }
    if (LibRTRandom_APIVersion() < LIBRT_RANDOM_API_VERSION) {
        char err[128];
        snprintf(err, sizeof(err),
                 "API version conflict for librt.random, expected %d or newer, found %d (hint: upgrade librt)",
            LIBRT_RANDOM_API_VERSION,
            LibRTRandom_APIVersion()
        );
        PyErr_SetString(PyExc_ValueError, err);
        return -1;
    }
    return 0;
}

static inline bool CPyRandom_Check(PyObject *obj) {
    return Py_TYPE(obj) == LibRTRandom_Random_type_internal();
}

#endif  // MYPYC_EXPERIMENTAL

#endif  // LIBRT_RANDOM_H
