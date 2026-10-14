#ifndef LIBRT_INTERNAL_API_H
#define LIBRT_INTERNAL_API_H

#include "librt_internal.h"

#ifdef MYPYC_STATIC_LINKING
// librt is statically linked, so the API functions (declared in librt_internal.h) are
// called directly, and type objects are referred to directly
#define NativeInternal_ReadBuffer_type_internal() (&NativeInternal_ReadBufferType)
#define NativeInternal_WriteBuffer_type_internal() (&NativeInternal_WriteBufferType)
#else
extern void *NativeInternal_API[LIBRT_INTERNAL_API_LEN];

#define NativeInternal_ReadBuffer_internal (*(PyObject* (*)(PyObject *source)) NativeInternal_API[0])
#define NativeInternal_WriteBuffer_internal (*(PyObject* (*)(void)) NativeInternal_API[1])
#define NativeInternal_WriteBuffer_getvalue_internal (*(PyObject* (*)(PyObject *source)) NativeInternal_API[2])
#define NativeInternal_write_bool_internal (*(char (*)(PyObject *source, char value)) NativeInternal_API[3])
#define NativeInternal_read_bool_internal (*(char (*)(PyObject *source)) NativeInternal_API[4])
#define NativeInternal_write_str_internal (*(char (*)(PyObject *source, PyObject *value)) NativeInternal_API[5])
#define NativeInternal_read_str_internal (*(PyObject* (*)(PyObject *source)) NativeInternal_API[6])
#define NativeInternal_write_float_internal (*(char (*)(PyObject *source, double value)) NativeInternal_API[7])
#define NativeInternal_read_float_internal (*(double (*)(PyObject *source)) NativeInternal_API[8])
#define NativeInternal_write_int_internal (*(char (*)(PyObject *source, CPyTagged value)) NativeInternal_API[9])
#define NativeInternal_read_int_internal (*(CPyTagged (*)(PyObject *source)) NativeInternal_API[10])
#define NativeInternal_write_tag_internal (*(char (*)(PyObject *source, uint8_t value)) NativeInternal_API[11])
#define NativeInternal_read_tag_internal (*(uint8_t (*)(PyObject *source)) NativeInternal_API[12])
#define NativeInternal_ABI_Version (*(int (*)(void)) NativeInternal_API[13])
#define NativeInternal_write_bytes_internal (*(char (*)(PyObject *source, PyObject *value)) NativeInternal_API[14])
#define NativeInternal_read_bytes_internal (*(PyObject* (*)(PyObject *source)) NativeInternal_API[15])
#define NativeInternal_cache_version_internal (*(uint8_t (*)(void)) NativeInternal_API[16])
#define NativeInternal_ReadBuffer_type_internal (*(PyTypeObject* (*)(void)) NativeInternal_API[17])
#define NativeInternal_WriteBuffer_type_internal (*(PyTypeObject* (*)(void)) NativeInternal_API[18])
#define NativeInternal_API_Version (*(int (*)(void)) NativeInternal_API[19])
#define NativeInternal_extract_symbol_internal (*(PyObject* (*)(PyObject *source)) NativeInternal_API[20])
#endif

int
import_librt_internal(void);

static inline bool CPyReadBuffer_Check(PyObject *obj) {
    return Py_TYPE(obj) == NativeInternal_ReadBuffer_type_internal();
}

static inline bool CPyWriteBuffer_Check(PyObject *obj) {
    return Py_TYPE(obj) == NativeInternal_WriteBuffer_type_internal();
}

#endif  // LIBRT_INTERNAL_API_H
