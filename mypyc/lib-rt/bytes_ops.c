// Bytes primitive operations
//
// These are registered in mypyc.primitives.bytes_ops.

#include <Python.h>
#include "CPy.h"

// Returns -1 on error, 0 on inequality, 1 on equality.
// 
// Falls back to PyObject_RichCompareBool.
int CPyBytes_Compare(PyObject *left, PyObject *right) {
    if (PyBytes_CheckExact(left) && PyBytes_CheckExact(right)) {
        if (left == right) {
            return 1;
        }

        // Adapted from cpython internal implementation of bytes_compare.
        Py_ssize_t len = Py_SIZE(left);
        if (Py_SIZE(right) != len) {
            return 0;
        }
        PyBytesObject *left_b = (PyBytesObject *)left;
        PyBytesObject *right_b = (PyBytesObject *)right;
        if (left_b->ob_sval[0] != right_b->ob_sval[0]) {
            return 0;
        }

        return memcmp(left_b->ob_sval, right_b->ob_sval, len) == 0;
    }
    return PyObject_RichCompareBool(left, right, Py_EQ);
}
