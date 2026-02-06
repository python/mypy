#ifndef BYTESWRITER_EXTRA_OPS_H
#define BYTESWRITER_EXTRA_OPS_H

#ifdef MYPYC_EXPERIMENTAL

#include <stdint.h>
#include <Python.h>

#include "strings/librt_strings.h"
#include "strings/librt_strings_common.h"

// BytesWriter: Length and capacity

static inline CPyTagged
CPyBytesWriter_Len(PyObject *obj) {
    return (CPyTagged)((BytesWriterObject *)obj)->len << 1;
}

static inline bool
CPyBytesWriter_EnsureSize(BytesWriterObject *data, Py_ssize_t n) {
    if (likely(data->capacity - data->len >= n)) {
        return true;
    } else {
        return LibRTStrings_ByteWriter_grow_buffer_internal(data, n);
    }
}

// BytesWriter: Basic write operations

static inline char
CPyBytesWriter_Append(PyObject *obj, uint8_t value) {
    BytesWriterObject *self = (BytesWriterObject *)obj;
    // Store length in a local variable to enable additional optimizations
    Py_ssize_t len = self->len;
    if (!CPyBytesWriter_EnsureSize(self, 1))
        return CPY_NONE_ERROR;
    self->buf[len] = value;
    self->len = len + 1;
    return CPY_NONE;
}

char CPyBytesWriter_Write(PyObject *obj, PyObject *value);

// BytesWriter: Indexing operations

// If index is negative, convert to non-negative index (no range checking)
static inline int64_t CPyBytesWriter_AdjustIndex(PyObject *obj, int64_t index) {
    if (index < 0) {
        return index + ((BytesWriterObject *)obj)->len;
    }
    return index;
}

static inline bool CPyBytesWriter_RangeCheck(PyObject *obj, int64_t index) {
    return index >= 0 && index < ((BytesWriterObject *)obj)->len;
}

static inline uint8_t CPyBytesWriter_GetItem(PyObject *obj, int64_t index) {
    return (((BytesWriterObject *)obj)->buf)[index];
}

static inline void CPyBytesWriter_SetItem(PyObject *obj, int64_t index, uint8_t x) {
    (((BytesWriterObject *)obj)->buf)[index] = x;
}

// BytesWriter: Write integer operations (little-endian)

static inline char
CPyBytesWriter_WriteI16LE(PyObject *obj, int16_t value) {
    BytesWriterObject *self = (BytesWriterObject *)obj;
    if (!CPyBytesWriter_EnsureSize(self, 2))
        return CPY_NONE_ERROR;
    BytesWriter_WriteI16LEUnsafe(self, value);
    return CPY_NONE;
}

static inline char
CPyBytesWriter_WriteI32LE(PyObject *obj, int32_t value) {
    BytesWriterObject *self = (BytesWriterObject *)obj;
    if (!CPyBytesWriter_EnsureSize(self, 4))
        return CPY_NONE_ERROR;
    BytesWriter_WriteI32LEUnsafe(self, value);
    return CPY_NONE;
}

static inline char
CPyBytesWriter_WriteI64LE(PyObject *obj, int64_t value) {
    BytesWriterObject *self = (BytesWriterObject *)obj;
    if (!CPyBytesWriter_EnsureSize(self, 8))
        return CPY_NONE_ERROR;
    BytesWriter_WriteI64LEUnsafe(self, value);
    return CPY_NONE;
}

// Bytes: Read integer operations (little-endian)

// Helper function for bytes read error handling (negative index or out of range)
void CPyBytes_ReadError(int64_t index, Py_ssize_t size);

static inline int16_t
CPyBytes_ReadI16LE(PyObject *bytes_obj, int64_t index) {
    // bytes_obj type is enforced by mypyc
    Py_ssize_t size = PyBytes_GET_SIZE(bytes_obj);
    if (unlikely(index < 0 || index > size - 2)) {
        CPyBytes_ReadError(index, size);
        return CPY_LL_INT_ERROR;
    }
    const unsigned char *data = (const unsigned char *)PyBytes_AS_STRING(bytes_obj);
    return CPyBytes_ReadI16LEUnsafe(data + index);
}

static inline int32_t
CPyBytes_ReadI32LE(PyObject *bytes_obj, int64_t index) {
    // bytes_obj type is enforced by mypyc
    Py_ssize_t size = PyBytes_GET_SIZE(bytes_obj);
    if (unlikely(index < 0 || index > size - 4)) {
        CPyBytes_ReadError(index, size);
        return CPY_LL_INT_ERROR;
    }
    const unsigned char *data = (const unsigned char *)PyBytes_AS_STRING(bytes_obj);
    return CPyBytes_ReadI32LEUnsafe(data + index);
}

static inline int64_t
CPyBytes_ReadI64LE(PyObject *bytes_obj, int64_t index) {
    // bytes_obj type is enforced by mypyc
    Py_ssize_t size = PyBytes_GET_SIZE(bytes_obj);
    if (unlikely(index < 0 || index > size - 8)) {
        CPyBytes_ReadError(index, size);
        return CPY_LL_INT_ERROR;
    }
    const unsigned char *data = (const unsigned char *)PyBytes_AS_STRING(bytes_obj);
    return CPyBytes_ReadI64LEUnsafe(data + index);
}

#endif // MYPYC_EXPERIMENTAL

#endif
