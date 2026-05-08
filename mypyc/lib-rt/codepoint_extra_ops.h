#ifndef MYPYC_CODEPOINT_EXTRA_OPS_H
#define MYPYC_CODEPOINT_EXTRA_OPS_H

#include <Python.h>
#include <stdbool.h>
#include <stdint.h>

// Codepoint helpers for librt.strings.
// Inputs are signed int32_t for compatibility with mypyc's i32 type.
// Negative values are treated as non-codepoints and return false.

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

// Slow path for non-ASCII isidentifier; defined out-of-line in
// codepoint_extra_ops.c because it allocates and calls into CPython.
bool LibRTStrings_IsIdentifier_slow(int32_t c);

// True if c could start a valid identifier (matches XID_Start
// semantics, which is what str.isidentifier reports for a 1-character
// string). The ASCII fast path covers `[A-Za-z_]` inline; non-ASCII
// delegates to PyUnicode_IsIdentifier for correct PEP 3131 handling.
// Returns false on OOM in the slow path (the function stays ERR_NEVER).
static inline bool LibRTStrings_IsIdentifier(int32_t c) {
    if (c < 0) return false;
    if (c < 128) {
        return (c >= 'a' && c <= 'z')
            || (c >= 'A' && c <= 'Z')
            || c == '_';
    }
    return LibRTStrings_IsIdentifier_slow(c);
}

#endif  // MYPYC_CODEPOINT_EXTRA_OPS_H
