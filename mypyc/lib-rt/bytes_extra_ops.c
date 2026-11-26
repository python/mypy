#include "bytes_extra_ops.h"

PyObject *CPyBytes_Translate(PyObject *bytes, PyObject *table) {
    // Fast path: exact bytes object with exact bytes table
    if (PyBytes_CheckExact(bytes) && PyBytes_CheckExact(table)) {
        Py_ssize_t table_len = PyBytes_GET_SIZE(table);
        if (table_len != 256) {
            PyErr_SetString(PyExc_ValueError,
                           "translation table must be 256 characters long");
            return NULL;
        }

        Py_ssize_t len = PyBytes_GET_SIZE(bytes);
        const char *input = PyBytes_AS_STRING(bytes);
        const char *trans_table = PyBytes_AS_STRING(table);

        PyObject *result = PyBytes_FromStringAndSize(NULL, len);
        if (result == NULL) {
            return NULL;
        }

        char *output = PyBytes_AS_STRING(result);
        bool changed = false;

        // Without a loop unrolling hint performance can be worse than CPython
        CPY_UNROLL_LOOP(4)
        for (Py_ssize_t i = len; --i >= 0;) {
            char c = *input++;
            if ((*output++ = trans_table[(unsigned char)c]) != c)
                changed = true;
        }

        // If nothing changed, discard result and return the original object
        if (!changed) {
            Py_DECREF(result);
            Py_INCREF(bytes);
            return bytes;
        }

        return result;
    }

    // Fallback to Python method call for non-exact types or non-standard tables
    return CPyBytes_CheckResult(
        PyObject_CallMethodOneArg(bytes, mypyc_interned_str.translate, table));
}

// Needles up to this length are searched for directly. Longer needles use the
// generic implementation, which has better worst-case behavior.
#define CPY_BYTES_CONTAINS_MAX_DIRECT 32

#if CPY_3_11_FEATURES
// Exported by CPython (used by the mmap module) but only declared in an internal header.
// Uses the same search as bytes.find, and the haystack doesn't need to be a bytes object.
PyAPI_FUNC(Py_ssize_t) _PyBytes_Find(const char *haystack, Py_ssize_t len_haystack,
                                     const char *needle, Py_ssize_t len_needle,
                                     Py_ssize_t offset);
#endif

// Continue a bytes containment search after a false hit, with p pointing to the
// next position to check. See CPyBytes_Contains for the meaning of the arguments.
// Not inlined, so that the common fast path in CPyBytes_Contains stays small.
static CPy_NOINLINE int bytes_contains_after_false_hit(PyObject *self, PyObject *sub_obj,
                                                       const char *p, const char *end,
                                                       const char *sub, Py_ssize_t sub_len) {
    // Position at the last density check
    const char *mark = p;
    unsigned false_hits = 1;
    while ((p = memchr(p, sub[0], end - p)) != NULL) {
        if (memcmp(p + 1, sub + 1, sub_len - 1) == 0) {
            return 1;
        }
        p++;
        // If the first needle byte is frequent, memchr makes little progress per
        // call. Use the CPython search implementation, which has better worst-case
        // behavior, if the last 16 false hits were within 128 bytes.
        if ((++false_hits & 15) == 0) {
            if (p - mark < 128) {
#if CPY_3_11_FEATURES
                return _PyBytes_Find(p, end - p + sub_len - 1, sub, sub_len, 0) >= 0;
#else
                return PySequence_Contains(self, sub_obj);
#endif
            }
            mark = p;
        }
    }
    return 0;
}

int CPyBytes_ContainsInt(PyObject *self, CPyTagged value) {
    if (likely(PyBytes_CheckExact(self))) {
        if (likely(CPyTagged_CheckShort(value))) {
            Py_ssize_t byte = CPyTagged_ShortAsSsize_t(value);
            if (likely(byte >= 0 && byte < 256)) {
                return memchr(PyBytes_AS_STRING(self), (int)byte, PyBytes_GET_SIZE(self)) != NULL;
            }
        }
        PyErr_SetString(PyExc_ValueError, "byte must be in range(0, 256)");
        return -1;
    }
    PyObject *item = CPyTagged_AsObject(value);
    int result = PySequence_Contains(self, item);
    Py_DECREF(item);
    return result;
}

int CPyBytes_Contains(PyObject *self, PyObject *sub) {
    if (likely(PyBytes_CheckExact(self) && PyBytes_CheckExact(sub))) {
        Py_ssize_t len = PyBytes_GET_SIZE(self);
        Py_ssize_t sub_len = PyBytes_GET_SIZE(sub);
        if (sub_len == 0) {
            return 1;
        }
        if (sub_len > len) {
            return 0;
        }
        if (sub_len <= CPY_BYTES_CONTAINS_MAX_DIRECT) {
            const char *buf = PyBytes_AS_STRING(self);
            const char *sub_buf = PyBytes_AS_STRING(sub);
            // One past the last position where a match can start
            const char *end = buf + (len - sub_len + 1);
            const char *p = memchr(buf, sub_buf[0], end - buf);
            if (p == NULL) {
                return 0;
            }
            if (memcmp(p + 1, sub_buf + 1, sub_len - 1) == 0) {
                return 1;
            }
            return bytes_contains_after_false_hit(self, sub, p + 1, end, sub_buf, sub_len);
        }
    }
    return PySequence_Contains(self, sub);
}
