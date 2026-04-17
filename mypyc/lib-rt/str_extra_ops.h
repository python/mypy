#ifndef MYPYC_STR_EXTRA_OPS_H
#define MYPYC_STR_EXTRA_OPS_H

#include <Python.h>
#include <stdint.h>
#include "CPy.h"

// Optimized str indexing for ord(s[i])

// If index is negative, convert to non-negative index (no range checking)
static inline int64_t CPyStr_AdjustIndex(PyObject *obj, int64_t index) {
    if (index < 0) {
        return index + PyUnicode_GET_LENGTH(obj);
    }
    return index;
}

// Check if index is in valid range [0, len)
static inline bool CPyStr_RangeCheck(PyObject *obj, int64_t index) {
    return index >= 0 && index < PyUnicode_GET_LENGTH(obj);
}

// Get character at index as int (ord value) - no bounds checking, returns as CPyTagged
static inline CPyTagged CPyStr_GetItemUnsafeAsInt(PyObject *obj, int64_t index) {
    int kind = PyUnicode_KIND(obj);
    return PyUnicode_READ(kind, PyUnicode_DATA(obj), index) << 1;
}

// Bounds-checked codepoint read returning int32. Error sentinel -113 on
// out-of-range / non-short index. Used by char_str_index_fold to avoid the
// 1-char PyObject alloc when the result is immediately unboxed to char.
static inline int32_t CPyStr_GetCharAt(PyObject *s, CPyTagged index_tagged) {
    Py_ssize_t i;
    if (likely(CPyTagged_CheckShort(index_tagged))) {
        i = CPyTagged_ShortAsSsize_t(index_tagged);
    } else {
        PyObject *c = CPyStr_GetItem(s, index_tagged);
        if (c == NULL) return -113;
        int32_t cp = (int32_t)PyUnicode_READ_CHAR(c, 0);
        Py_DECREF(c);
        return cp;
    }
    Py_ssize_t n = PyUnicode_GET_LENGTH(s);
    if (i < 0) i += n;
    if (i < 0 || i >= n) {
        PyErr_SetString(PyExc_IndexError, "string index out of range");
        return -113;
    }
    return (int32_t)PyUnicode_READ(PyUnicode_KIND(s), PyUnicode_DATA(s), i);
}

// char-codepoint classification. Negative c (empty sentinel / invalid)
// returns false. Py_UNICODE_IS* have their own ASCII fast paths.

static inline bool CPyChar_IsSpace(int32_t c) {
    return c >= 0 && Py_UNICODE_ISSPACE((Py_UCS4)c);
}

static inline bool CPyChar_IsDigit(int32_t c) {
    return c >= 0 && Py_UNICODE_ISDIGIT((Py_UCS4)c);
}

static inline bool CPyChar_IsAlnum(int32_t c) {
    return c >= 0 && Py_UNICODE_ISALNUM((Py_UCS4)c);
}

static inline bool CPyChar_IsAlpha(int32_t c) {
    return c >= 0 && Py_UNICODE_ISALPHA((Py_UCS4)c);
}

// .isidentifier(): ASCII fast path matches XID_Start; non-ASCII delegates
// to CPython for correct XID_Start handling.
static inline bool CPyChar_IsIdentifier(int32_t c) {
    if (c < 0) return false;
    if (c < 128) return Py_ISALPHA((unsigned char)c) || c == (int32_t)'_';
    PyObject *s = PyUnicode_FromOrdinal((int)c);
    if (s == NULL) { PyErr_Clear(); return false; }
    int r = PyUnicode_IsIdentifier(s);
    Py_DECREF(s);
    return r == 1;
}

// Delegated Unicode case conversion for non-ASCII letters. Returns c
// unchanged when the str method produces multi-char (e.g. ß -> SS) or
// non-alpha ASCII. -113 + exception on OOM / CPython error.
static inline int32_t CPyChar_ChangeCase(int32_t c, const char *method) {
    if (c < 128) return c;
    PyObject *s = PyUnicode_FromOrdinal((int)c);
    if (s == NULL) return -113;
    PyObject *u = PyObject_CallMethod(s, method, NULL);
    Py_DECREF(s);
    if (u == NULL) return -113;
    int32_t result = c;
    if (PyUnicode_GET_LENGTH(u) == 1) {
        result = (int32_t)PyUnicode_READ_CHAR(u, 0);
    }
    Py_DECREF(u);
    return result;
}

// .upper() / .lower(): ASCII-letter fast path; everything else goes
// through CPyChar_ChangeCase.
static inline int32_t CPyChar_Upper(int32_t c) {
    if (c >= (int32_t)'a' && c <= (int32_t)'z') return c - 32;
    return CPyChar_ChangeCase(c, "upper");
}

static inline int32_t CPyChar_Lower(int32_t c) {
    if (c >= (int32_t)'A' && c <= (int32_t)'Z') return c + 32;
    return CPyChar_ChangeCase(c, "lower");
}

#endif
