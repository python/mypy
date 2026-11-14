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

// Move the first n items of a tuple being built into a new tuple of the given size.
// Steals the reference to the original tuple.
static PyObject *CPyTuple_MoveItems(PyObject *tuple, Py_ssize_t n, Py_ssize_t size) {
    PyObject *result = PyTuple_New(size);
    if (result == NULL) {
        Py_DECREF(tuple);
        return NULL;
    }
    for (Py_ssize_t i = 0; i < n; i++) {
        PyTuple_SET_ITEM(result, i, PyTuple_GET_ITEM(tuple, i));
        PyTuple_SET_ITEM(tuple, i, NULL);
    }
    Py_DECREF(tuple);
    return result;
}

// Set an item of a tuple that is being built using CPySequenceTuple_SetItemUnsafe, and
// grow the tuple if the index is out of range. Items before the index must have been
// set, and items at or after it must not have been set (so the index is at most the
// size of the tuple). Steals the tuple and the value,
// and returns the resulting tuple, which may be a new object.
PyObject *CPySequenceTuple_SetItemGrow(PyObject *tuple, Py_ssize_t index, PyObject *value) {
    Py_ssize_t size = PyTuple_GET_SIZE(tuple);
    if (index >= size) {
        Py_ssize_t new_size = size < 4 ? 8 : size * 2;
        if (new_size <= index) {
            new_size = index + 1;
        }
        tuple = CPyTuple_MoveItems(tuple, size, new_size);
        if (tuple == NULL) {
            Py_DECREF(value);
            return NULL;
        }
    }
    PyTuple_SET_ITEM(tuple, index, value);
    return tuple;
}

// Set the size of a tuple that is being built using CPySequenceTuple_SetItemUnsafe or
// CPySequenceTuple_SetItemGrow. Items before the size must have been set, and items at
// or after it must not have been set. Steals the tuple and returns the resulting tuple,
// which may be a new object.
PyObject *CPySequenceTuple_SetSize(PyObject *tuple, Py_ssize_t size) {
    if (size == PyTuple_GET_SIZE(tuple)) {
        return tuple;
    }
    return CPyTuple_MoveItems(tuple, size, size);
}
