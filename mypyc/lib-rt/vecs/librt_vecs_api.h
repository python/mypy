#ifndef LIBRT_VECS_API_H
#define LIBRT_VECS_API_H

#include "librt_vecs.h"

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdint.h>

int
import_librt_vecs(void);

#ifdef MYPYC_STATIC_LINKING
// librt is statically linked. These have the same contents as the API structs in
// librt.vecs, but since they are constants, calls are direct (and can be inlined).
static const VecI64API VecI64Api = VEC_API_INIT(VecI64);
static const VecI32API VecI32Api = VEC_API_INIT(VecI32);
static const VecI16API VecI16Api = VEC_API_INIT(VecI16);
static const VecU8API VecU8Api = VEC_API_INIT(VecU8);
static const VecFloatAPI VecFloatApi = VEC_API_INIT(VecFloat);
static const VecBoolAPI VecBoolApi = VEC_API_INIT(VecBool);
static const VecTAPI VecTApi = VEC_API_INIT(VecT);
static const VecNestedAPI VecNestedApi = VEC_NESTED_API_INIT;
#else
// Global API pointers initialized by import_librt_vecs()
extern VecCapsule *VecApi;
extern VecI64API VecI64Api;
extern VecI32API VecI32Api;
extern VecI16API VecI16Api;
extern VecU8API VecU8Api;
extern VecFloatAPI VecFloatApi;
extern VecBoolAPI VecBoolApi;
extern VecTAPI VecTApi;
extern VecNestedAPI VecNestedApi;
#endif

#endif  // LIBRT_VECS_API_H
