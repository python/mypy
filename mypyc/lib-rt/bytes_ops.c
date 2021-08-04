// Bytes primitive operations
//
// These are registered in mypyc.primitives.bytes_ops.

#include <Python.h>
#include "CPy.h"

PyObject *CPyBytes_Concat(PyObject *a, PyObject *b) {
    if (PyByteArray_Check(a) && PyByteArray_Check(b)) {
        return PyByteArray_Concat(a, b);
    } else {
        PyBytes_Concat(&a, b);
        return a;
    }
}
