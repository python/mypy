// Bytes primitive operations
//
// These are registered in mypyc.primitives.bytes_ops.

#include <Python.h>
#include "CPy.h"

CPyTagged CPyBytes_GetItem(PyObject *o, CPyTagged index) {
    if (CPyTagged_CheckShort(index)) {
        Py_ssize_t n = CPyTagged_ShortAsSsize_t(index);
        Py_ssize_t size = ((PyVarObject *)o)->ob_size;
        if ((n >= 0 && n >= size) || (n < 0 && n + size < 0)) {
            PyErr_SetString(PyExc_IndexError, "index out of range");
            return CPY_INT_TAG;
        }
        if (n < 0)
            n += size;
        int num = PyBytes_Check(o) ? ((PyBytesObject *)o)->ob_sval[n]
                                   : ((PyByteArrayObject *)o)->ob_bytes[n];
        if (num < 0)
            num += 256;
        return num << 1;
    } else {
        PyErr_SetString(PyExc_OverflowError, CPYTHON_LARGE_INT_ERRMSG);
        return CPY_INT_TAG;
    }
}

CPyTagged CPyBytes_GetItemShort(PyObject *o, CPyTagged index) {
    Py_ssize_t n = CPyTagged_ShortAsSsize_t(index);
    Py_ssize_t size = ((PyVarObject *)o)->ob_size;
    if ((n >= 0 && n >= size) || (n < 0 && n + size < 0)) {
        PyErr_SetString(PyExc_IndexError, "index out of range");
        return CPY_INT_TAG;
    }
    if (n < 0)
        n += size;
    int num = PyBytes_Check(o) ? ((PyBytesObject *)o)->ob_sval[n]
                               : ((PyByteArrayObject *)o)->ob_bytes[n];
    if (num < 0)
        num += 256;
    return num << 1;
}

bool CPyByteArray_SetItem(PyObject *o, CPyTagged index, CPyTagged num) {
    if (PyByteArray_Check(o)) {
        if (CPyTagged_CheckShort(index) && CPyTagged_CheckShort(num)) {
            Py_ssize_t n = CPyTagged_ShortAsSsize_t(index);
            Py_ssize_t size = ((PyVarObject *)o)->ob_size;
            if ((n >= 0 && n >= size) || (n < 0 && n + size < 0)) {
                PyErr_SetString(PyExc_IndexError, "index out of range");
                return false;
            }
            if (n < 0)
                n += size;
            Py_ssize_t num = CPyTagged_ShortAsSsize_t(index);
            if (num < 0 || n > 255) {
                PyErr_SetString(PyExc_ValueError, "byte must be in range(0, 256)");
                return false;
            }
            ((PyByteArrayObject *)o)->ob_bytes[n] = num;
            return true;
        } else {
            PyErr_SetString(PyExc_OverflowError, CPYTHON_LARGE_INT_ERRMSG);
            return false;
        }
    } else {
        PyErr_SetString(PyExc_TypeError, "'bytes' object does not support item assignment");
        return false;
    }
}

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
        return PyObject_CallMethod(sep, "join", "(O)", iter);
    }
}
