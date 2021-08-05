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

// Like _PyBytes_Join but fallback to dynamic call if 'sep' is not bytes
// (mostly commonly, for bytearrays)
PyObject *CPyBytes_Join(PyObject *sep, PyObject *iter) {
    if (PyBytes_CheckExact(sep)) {
        return _PyBytes_Join(sep, iter);
    } else {
        return PyObject_CallMethod(sep, "join", "(O)", iter);
    }
}
