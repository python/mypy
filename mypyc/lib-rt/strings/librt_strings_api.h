#ifndef LIBRT_STRINGS_API_H
#define LIBRT_STRINGS_API_H

int
import_librt_strings(void);

#include <Python.h>
#include <stdbool.h>
#include "librt_strings.h"

extern void *LibRTStrings_API[LIBRT_STRINGS_API_LEN];

#define LibRTStrings_ABIVersion (*(int (*)(void)) LibRTStrings_API[0])
#define LibRTStrings_APIVersion (*(int (*)(void)) LibRTStrings_API[1])
#define LibRTStrings_BytesWriter_internal (*(PyObject* (*)(void)) LibRTStrings_API[2])
#define LibRTStrings_BytesWriter_getvalue_internal (*(PyObject* (*)(PyObject *source)) LibRTStrings_API[3])
#define LibRTStrings_BytesWriter_append_internal (*(char (*)(PyObject *source, uint8_t value)) LibRTStrings_API[4])
#define LibRTStrings_ByteWriter_grow_buffer_internal (*(bool (*)(BytesWriterObject *obj, Py_ssize_t size)) LibRTStrings_API[5])
#define LibRTStrings_BytesWriter_type_internal (*(PyTypeObject* (*)(void)) LibRTStrings_API[6])
#define LibRTStrings_BytesWriter_truncate_internal (*(char (*)(PyObject *self, int64_t size)) LibRTStrings_API[7])
#define LibRTStrings_StringWriter_internal (*(PyObject* (*)(void)) LibRTStrings_API[8])
#define LibRTStrings_StringWriter_getvalue_internal (*(PyObject* (*)(PyObject *source)) LibRTStrings_API[9])
#define LibRTStrings_string_append_slow_path (*(char (*)(StringWriterObject *obj, int32_t value)) LibRTStrings_API[10])
#define LibRTStrings_StringWriter_type_internal (*(PyTypeObject* (*)(void)) LibRTStrings_API[11])
#define LibRTStrings_StringWriter_write_internal (*(char (*)(PyObject *source, PyObject *value)) LibRTStrings_API[12])
#define LibRTStrings_grow_string_buffer (*(bool (*)(StringWriterObject *obj, Py_ssize_t n)) LibRTStrings_API[13])
#define LibRTStrings_str_from_code_point_internal (*(PyObject* (*)(int32_t c)) LibRTStrings_API[14])


static inline bool CPyBytesWriter_Check(PyObject *obj) {
    return Py_TYPE(obj) == LibRTStrings_BytesWriter_type_internal();
}

static inline bool CPyStringWriter_Check(PyObject *obj) {
    return Py_TYPE(obj) == LibRTStrings_StringWriter_type_internal();
}

// Return a new reference to a single-character string for a code point, or NULL
// with an exception set. Strings for code points below
// LIBRT_STRINGS_CHAR_CACHE_END are cached.
static inline PyObject *LibRTStrings_StrFromCodePoint(Py_UCS4 c) {
    if (c < 256) {
        // CPython caches single-character Latin-1 strings
        return PyUnicode_FromOrdinal((int)c);
    }
    return LibRTStrings_str_from_code_point_internal((int32_t)c);
}

static inline PyObject *LibRTStrings_CachedChr(int64_t c) {
    if (unlikely(c < 0 || c > 0x10ffff)) {
        PyErr_SetString(PyExc_ValueError, LIBRT_STRINGS_CACHED_CHR_ERRMSG);
        return NULL;
    }
    return LibRTStrings_StrFromCodePoint((Py_UCS4)c);
}

static inline PyObject *LibRTStrings_CharAt(PyObject *s, int64_t i) {
    Py_ssize_t len = PyUnicode_GET_LENGTH(s);
    if (i < 0) {
        i += len;
    }
    if (unlikely(i < 0 || i >= len)) {
        PyErr_SetString(PyExc_IndexError, "string index out of range");
        return NULL;
    }
    return LibRTStrings_StrFromCodePoint(PyUnicode_READ_CHAR(s, (Py_ssize_t)i));
}

#endif  // LIBRT_STRINGS_API_H
