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

// Compare two exact tuples for equality. Return 1 if equal, 0 if not equal, -1 on error.
static int _CPyTuple_Equal(PyObject *left, PyObject *right) {
    if (left == right) {
        // All items are identical, so they compare equal
        return 1;
    }
    Py_ssize_t left_size = PyTuple_GET_SIZE(left);
    Py_ssize_t right_size = PyTuple_GET_SIZE(right);
    // Like CPython, compare items even if the lengths differ, since item
    // comparisons can have side effects or raise exceptions
    Py_ssize_t i;
    for (i = 0; i < left_size && i < right_size; i++) {
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
    return left_size == right_size;
}

// Compare two tuples using == or != (op is Py_EQ or Py_NE). Return 1 if the result is
// true, 0 if it's false, and -1 on error.
int CPyTuple_Compare(PyObject *left, PyObject *right, int op) {
    if (likely(PyTuple_CheckExact(left) && PyTuple_CheckExact(right))) {
        int result = _CPyTuple_Equal(left, right);
        if (result < 0) {
            return -1;
        }
        return op == Py_EQ ? result : !result;
    }
    // Subclasses may override __eq__ and __ne__
    PyObject *res = PyObject_RichCompare(left, right, op);
    if (res == NULL) {
        return -1;
    }
    int result = PyObject_IsTrue(res);
    Py_DECREF(res);
    return result;
}
