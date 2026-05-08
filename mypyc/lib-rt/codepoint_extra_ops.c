#include "codepoint_extra_ops.h"

// Out-of-line bodies for codepoint helpers that are too large to inline.
// The classification helpers and the ASCII fast paths for case conversion
// stay inline in codepoint_extra_ops.h; this file holds the slow paths
// that round-trip through PyUnicode_FromOrdinal and CPython's Unicode
// machinery.

bool LibRTStrings_IsIdentifier_slow(int32_t c) {
    PyObject *s = PyUnicode_FromOrdinal((int)c);
    if (s == NULL) {
        // OOM. Swallow and return false to keep the function ERR_NEVER;
        // callers expect a defined answer, not a propagated exception.
        PyErr_Clear();
        return false;
    }
    int r = PyUnicode_IsIdentifier(s);
    Py_DECREF(s);
    return r == 1;
}
