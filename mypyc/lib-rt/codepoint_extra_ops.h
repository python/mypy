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

#endif  // MYPYC_CODEPOINT_EXTRA_OPS_H
