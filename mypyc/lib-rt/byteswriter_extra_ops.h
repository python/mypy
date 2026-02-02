#ifndef BYTESWRITER_EXTRA_OPS_H
#define BYTESWRITER_EXTRA_OPS_H

#ifdef MYPYC_EXPERIMENTAL

#include <stdint.h>
#include <Python.h>

#include "strings/librt_strings.h"

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

#endif // MYPYC_EXPERIMENTAL

#endif
