// Tuple primitive operations
//
// These are registered in mypyc.primitives.tuple_ops.

#include <Python.h>
#include "CPy.h"

PyObject *CPySequenceTuple_GetItem_(PyObject *tuple, CPyTagged index) {
    if (CPyTagged_CheckShort(index)) {
        Py_ssize_t n = CPyTagged_ShortAsSsize_t(index);
        Py_ssize_t size = PyTuple_GET_SIZE(tuple);
        if (n < 0) {
            n += size;
        }
        if (n < 0 || n >= size) {
            PyErr_SetString(PyExc_IndexError, "tuple index out of range");
            return NULL;
        }
        PyObject *result = PyTuple_GET_ITEM(tuple, n);
        Py_INCREF(result);
        return result;
    } else {
        PyErr_SetString(PyExc_OverflowError, CPYTHON_LARGE_INT_ERRMSG);
        return NULL;
    }
}

PyObject *CPySequenceTuple_GetSlice(PyObject *obj, CPyTagged start, CPyTagged end) {
    if (likely(PyTuple_CheckExact(obj)
               && CPyTagged_CheckShort(start) && CPyTagged_CheckShort(end))) {
        Py_ssize_t startn = CPyTagged_ShortAsSsize_t(start);
        Py_ssize_t endn = CPyTagged_ShortAsSsize_t(end);
        if (startn < 0) {
            startn += PyTuple_GET_SIZE(obj);
        }
        if (endn < 0) {
            endn += PyTuple_GET_SIZE(obj);
        }
        return PyTuple_GetSlice(obj, startn, endn);
    }
    return CPyObject_GetSlice(obj, start, end);
}

// Compare two tuples for equality. Return 1 if equal, 0 if not equal, -1 on error.
int CPyTuple_Equal(PyObject *left, PyObject *right) {
    if (likely(PyTuple_CheckExact(left) && PyTuple_CheckExact(right))) {
        if (left == right) {
            // All items are identical, so they compare equal
            return 1;
        }
        Py_ssize_t size = PyTuple_GET_SIZE(left);
        if (size != PyTuple_GET_SIZE(right)) {
            return 0;
        }
        Py_ssize_t i;
        for (i = 0; i < size; i++) {
            PyObject *left_item = PyTuple_GET_ITEM(left, i);
            PyObject *right_item = PyTuple_GET_ITEM(right, i);
            if (left_item == right_item) {
                continue;
            }
            int cmp = PyObject_RichCompareBool(left_item, right_item, Py_EQ);
            if (cmp <= 0) {
                return cmp;
            }
        }
        return 1;
    }
    // Subclasses may override __eq__
    PyObject *res = PyObject_RichCompare(left, right, Py_EQ);
    if (res == NULL) {
        return -1;
    }
    int result = PyObject_IsTrue(res);
    Py_DECREF(res);
    return result;
}
