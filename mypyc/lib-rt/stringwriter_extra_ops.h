#ifndef STRINGWRITER_EXTRA_OPS_H
#define STRINGWRITER_EXTRA_OPS_H

#ifdef MYPYC_EXPERIMENTAL

#include <stdint.h>
#include <Python.h>

#include "librt_strings.h"

static inline CPyTagged
CPyStringWriter_Len(PyObject *obj) {
    return (CPyTagged)((StringWriterObject *)obj)->len << 1;
}

static inline char
CPyStringWriter_Append(PyObject *obj, int32_t value) {
    StringWriterObject *self = (StringWriterObject *)obj;
    char kind = self->kind;

    // Fast path for kind 1 (ASCII/Latin-1) with common characters
    if (kind == 1 && (uint32_t)value < 256) {
        Py_ssize_t len = self->len;
        Py_ssize_t capacity = self->capacity;
        if (likely(capacity - len >= 1)) {
            self->buf[len] = (char)value;
            self->len = len + 1;
            return CPY_NONE;
        }
    }

    // Slow path handles capacity growth and kind switching
    return LibRTStrings_string_append_slow_path(self, value);
}

// If index is negative, convert to non-negative index (no range checking)
static inline int64_t CPyStringWriter_AdjustIndex(PyObject *obj, int64_t index) {
    if (index < 0) {
        return index + ((StringWriterObject *)obj)->len;
    }
    return index;
}

static inline bool CPyStringWriter_RangeCheck(PyObject *obj, int64_t index) {
    return index >= 0 && index < ((StringWriterObject *)obj)->len;
}

static inline int32_t CPyStringWriter_GetItem(PyObject *obj, int64_t index) {
    StringWriterObject *self = (StringWriterObject *)obj;
    char kind = self->kind;
    char *buf = self->buf;

    if (kind == 1) {
        return (uint8_t)buf[index];
    } else if (kind == 2) {
        uint16_t val;
        memcpy(&val, buf + index * 2, 2);
        return (int32_t)val;
    } else {
        uint32_t val;
        memcpy(&val, buf + index * 4, 4);
        return (int32_t)val;
    }
}

#endif // MYPYC_EXPERIMENTAL

#endif
