// Tuple primitive operations
//
// These are registered in mypyc.primitives.tuple_ops.

#include <Python.h>
#include "CPy.h"

PyObject *CPySequenceTuple_GetItem(PyObject *tuple, CPyTagged index) {
    if (CPyTagged_CheckShort(index)) {
        Py_ssize_t n = CPyTagged_ShortAsSsize_t(index);
        Py_ssize_t size = PyTuple_GET_SIZE(tuple);
        if (n >= 0) {
            if (n >= size) {
                PyErr_SetString(PyExc_IndexError, "tuple index out of range");
                return NULL;
            }
        } else {
            n += size;
            if (n < 0) {
                PyErr_SetString(PyExc_IndexError, "tuple index out of range");
                return NULL;
            }
        }
        PyObject *result = PyTuple_GET_ITEM(tuple, n);
        Py_INCREF(result);
        return result;
    } else {
        PyErr_SetString(PyExc_IndexError, "tuple index out of range");
        return NULL;
    }
}
