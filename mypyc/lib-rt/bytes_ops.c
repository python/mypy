// Bytes primitive operations
//
// These are registered in mypyc.primitives.bytes_ops.

#include <Python.h>
#include "CPy.h"

PyObject *CPyBytes_Concat(PyObject *a, PyObject *b) {
    if (PyBytes_Check(a) && PyBytes_Check(b)) {
        Py_ssize_t a_len = ((PyVarObject *)a)->ob_size;
        Py_ssize_t b_len = ((PyVarObject *)b)->ob_size;
        PyBytesObject *ret = (PyBytesObject *)PyBytes_FromStringAndSize(NULL, a_len + b_len);
        if (ret != NULL) {
            memcpy(ret->ob_sval, ((PyBytesObject *)a)->ob_sval, a_len);
            memcpy(ret->ob_sval + a_len, ((PyBytesObject *)b)->ob_sval, b_len);
        }
        return (PyObject *)ret;
    } else if (PyByteArray_Check(a)) {
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
        _Py_IDENTIFIER(join);
        return _PyObject_CallMethodIdOneArg(sep, &PyId_join, iter);
    }
}
