#include "librt_vecs_api.h"

#ifndef MYPYC_EXPERIMENTAL

int
import_librt_vecs(void)
{
    // All librt.vecs features are experimental for now, so don't set up the API here
    return 0;
}

#else

VecCapsule *VecApi = NULL;
VecI64API VecI64Api = {0};
VecI32API VecI32Api = {0};
VecI16API VecI16Api = {0};
VecU8API VecU8Api = {0};
VecFloatAPI VecFloatApi = {0};
VecBoolAPI VecBoolApi = {0};
VecTAPI VecTApi = {0};
VecNestedAPI VecNestedApi = {0};

int
import_librt_vecs(void)
{
    PyObject *mod = PyImport_ImportModule("librt.vecs");
    if (mod == NULL)
        return -1;
    Py_DECREF(mod);  // we import just for the side effect of making the below work.
    VecApi = PyCapsule_Import("librt.vecs._C_API", 0);
    if (!VecApi)
        return -1;
    VecI64Api = *VecApi->i64;
    VecI32Api = *VecApi->i32;
    VecI16Api = *VecApi->i16;
    VecU8Api = *VecApi->u8;
    VecFloatApi = *VecApi->float_;
    VecBoolApi = *VecApi->bool_;
    VecTApi = *VecApi->t;
    VecNestedApi = *VecApi->nested;
    return 0;
}

#endif // MYPYC_EXPERIMENTAL
