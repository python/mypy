#ifndef LIBRT_STRINGS_H
#define LIBRT_STRINGS_H

#include <Python.h>
#include <stdbool.h>
#include <stdint.h>
#include "CPy.h"
#include "librt_strings_common.h"

// ABI version -- only an exact match is compatible. This will only be changed in
// very exceptional cases (likely never) due to strict backward compatibility
// requirements.
#define LIBRT_STRINGS_ABI_VERSION 1

// API version -- more recent versions must maintain backward compatibility, i.e.
// we can add new features but not remove or change existing features (unless
// ABI version is changed, but see the comment above).
#define LIBRT_STRINGS_API_VERSION 4

// Number of functions in the capsule API. If you add a new function, also increase
// LIBRT_STRINGS_API_VERSION.
#define LIBRT_STRINGS_API_LEN 14

typedef struct {
    PyObject_HEAD
    char *buf;  // Beginning of the buffer
    char kind;  // Bytes per code point (1, 2 or 4)
    Py_ssize_t len;  // Current length (number of code points written)
    Py_ssize_t capacity;  // Total capacity of the buffer (number of code points)
    char data[WRITER_EMBEDDED_BUF_LEN];  // Default buffer
} StringWriterObject;

// Codepoint classification helpers. Inputs are signed i32 for compatibility
// with mypyc's int32_rprimitive; negative values are non-codepoints and
// return false. Defined `static inline` so they compile statically into
// both the librt.strings module and any mypyc-compiled extension that
// includes this header, avoiding the capsule indirection that would dwarf
// the work of a single Py_UNICODE_IS* macro call.

static inline bool LibRTStrings_IsSpace(int32_t c) {
    return c >= 0 && Py_UNICODE_ISSPACE((Py_UCS4)c);
}

static inline bool LibRTStrings_IsDigit(int32_t c) {
    return c >= 0 && Py_UNICODE_ISDIGIT((Py_UCS4)c);
}

static inline bool LibRTStrings_IsAlnum(int32_t c) {
    return c >= 0 && Py_UNICODE_ISALNUM((Py_UCS4)c);
}

static inline bool LibRTStrings_IsAlpha(int32_t c) {
    return c >= 0 && Py_UNICODE_ISALPHA((Py_UCS4)c);
}

// True if c could start a valid identifier (XID_Start, per PEP 3131).
// ASCII fast path covers `[A-Za-z_]`; non-ASCII delegates to CPython's
// PyUnicode_IsIdentifier on a 1-character string. Aborts via
// CPyError_OutOfMemory on allocation failure to keep this ERR_NEVER.
static inline bool LibRTStrings_IsIdentifier(int32_t c) {
    if (c < 0) return false;
    if (c < 128) {
        return (c >= 'a' && c <= 'z')
            || (c >= 'A' && c <= 'Z')
            || c == '_';
    }
    PyObject *s = PyUnicode_FromOrdinal((int)c);
    if (s == NULL) {
        CPyError_OutOfMemory();
    }
    int r = PyUnicode_IsIdentifier(s);
    Py_DECREF(s);
    return r == 1;
}

#endif  // LIBRT_STRINGS_H
