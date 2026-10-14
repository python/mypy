#ifndef LIBRT_INTERNAL_H
#define LIBRT_INTERNAL_H

#include <Python.h>
#include <stdbool.h>

// ABI version -- only an exact match is compatible. This will only be changed in
// very exceptional cases (likely never) due to strict backward compatibility
// requirements.
#define LIBRT_INTERNAL_ABI_VERSION 2

// API version -- more recent versions must maintain backward compatibility, i.e.
// we can add new features but not remove or change existing features (unless
// ABI version is changed, but see the comment above).
#define LIBRT_INTERNAL_API_VERSION 1

// Number of functions in the capsule API. If you add a new function, also increase
// LIBRT_INTERNAL_API_VERSION.
#define LIBRT_INTERNAL_API_LEN 21

#ifdef LIBRT_INTERNAL_MODULE

LIBRT_API_LINKAGE PyObject *NativeInternal_ReadBuffer_internal(PyObject *source);
LIBRT_API_LINKAGE PyObject *NativeInternal_WriteBuffer_internal(void);
LIBRT_API_LINKAGE PyObject *NativeInternal_WriteBuffer_getvalue_internal(PyObject *self);
LIBRT_API_LINKAGE PyObject *NativeInternal_ReadBuffer_internal(PyObject *source);
static PyObject *ReadBuffer_internal_empty(void);
LIBRT_API_LINKAGE char NativeInternal_write_bool_internal(PyObject *data, char value);
LIBRT_API_LINKAGE char NativeInternal_read_bool_internal(PyObject *data);
LIBRT_API_LINKAGE char NativeInternal_write_str_internal(PyObject *data, PyObject *value);
LIBRT_API_LINKAGE PyObject *NativeInternal_read_str_internal(PyObject *data);
LIBRT_API_LINKAGE char NativeInternal_write_float_internal(PyObject *data, double value);
LIBRT_API_LINKAGE double NativeInternal_read_float_internal(PyObject *data);
LIBRT_API_LINKAGE char NativeInternal_write_int_internal(PyObject *data, CPyTagged value);
LIBRT_API_LINKAGE CPyTagged NativeInternal_read_int_internal(PyObject *data);
LIBRT_API_LINKAGE char NativeInternal_write_tag_internal(PyObject *data, uint8_t value);
LIBRT_API_LINKAGE uint8_t NativeInternal_read_tag_internal(PyObject *data);
LIBRT_API_LINKAGE int NativeInternal_ABI_Version(void);
LIBRT_API_LINKAGE char NativeInternal_write_bytes_internal(PyObject *data, PyObject *value);
LIBRT_API_LINKAGE PyObject *NativeInternal_read_bytes_internal(PyObject *data);
LIBRT_API_LINKAGE uint8_t NativeInternal_cache_version_internal(void);
LIBRT_API_LINKAGE PyTypeObject *NativeInternal_ReadBuffer_type_internal(void);
LIBRT_API_LINKAGE PyTypeObject *NativeInternal_WriteBuffer_type_internal(void);
LIBRT_API_LINKAGE int NativeInternal_API_Version(void);
LIBRT_API_LINKAGE PyObject *NativeInternal_extract_symbol_internal(PyObject *data);

#endif

#ifdef MYPYC_STATIC_LINKING
// With static linking, the API is used directly (see librt_internal_api.h)
#include <stdbool.h>
#include <stdint.h>
#include "CPy.h"
extern PyTypeObject NativeInternal_ReadBufferType;
extern PyTypeObject NativeInternal_WriteBufferType;
PyObject *NativeInternal_ReadBuffer_internal(PyObject *source);
PyObject *NativeInternal_WriteBuffer_internal(void);
PyObject *NativeInternal_WriteBuffer_getvalue_internal(PyObject *self);
char NativeInternal_write_bool_internal(PyObject *data, char value);
char NativeInternal_read_bool_internal(PyObject *data);
char NativeInternal_write_str_internal(PyObject *data, PyObject *value);
PyObject *NativeInternal_read_str_internal(PyObject *data);
char NativeInternal_write_float_internal(PyObject *data, double value);
double NativeInternal_read_float_internal(PyObject *data);
char NativeInternal_write_int_internal(PyObject *data, CPyTagged value);
CPyTagged NativeInternal_read_int_internal(PyObject *data);
char NativeInternal_write_tag_internal(PyObject *data, uint8_t value);
uint8_t NativeInternal_read_tag_internal(PyObject *data);
int NativeInternal_ABI_Version(void);
char NativeInternal_write_bytes_internal(PyObject *data, PyObject *value);
PyObject *NativeInternal_read_bytes_internal(PyObject *data);
uint8_t NativeInternal_cache_version_internal(void);
PyTypeObject *NativeInternal_ReadBuffer_type_internal(void);
PyTypeObject *NativeInternal_WriteBuffer_type_internal(void);
int NativeInternal_API_Version(void);
PyObject *NativeInternal_extract_symbol_internal(PyObject *data);
#endif

#endif  // LIBRT_INTERNAL_H
