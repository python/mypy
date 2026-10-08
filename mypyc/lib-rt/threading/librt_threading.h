#ifndef LIBRT_THREADING_H
#define LIBRT_THREADING_H

#include <Python.h>

#define LIBRT_THREADING_ABI_VERSION 1
#define LIBRT_THREADING_API_VERSION 1
#define LIBRT_THREADING_API_LEN 8

#ifdef MYPYC_STATIC_LINKING
// With static linking, the API is used directly (see librt_threading_api.h)
#include <stdbool.h>
#include <stdint.h>
extern PyTypeObject LibRTThreading_LockType;
int LibRTThreading_ABIVersion(void);
int LibRTThreading_APIVersion(void);
PyTypeObject *LibRTThreading_Lock_type_internal(void);
PyObject *LibRTThreading_Lock_new_internal(void);
char LibRTThreading_Lock_acquire_internal(PyObject *self);
char LibRTThreading_Lock_release_internal(PyObject *self);
char LibRTThreading_Lock_locked_internal(PyObject *self);
char LibRTThreading_Lock_acquire_blocking_internal(PyObject *self, char blocking);
#endif

#endif  // LIBRT_THREADING_H
