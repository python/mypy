// Bytes primitive operations
//
// These are registered in mypyc.primitives.bytes_ops.

#include <Python.h>
#include "CPy.h"

CPyTagged CPyBytes_GetItem(PyObject *o, CPyTagged index) {
    if (CPyTagged_CheckShort(index)) {
        Py_ssize_t n = CPyTagged_ShortAsSsize_t(index);
        Py_ssize_t size = ((PyVarObject *)o)->ob_size;
        if (n < 0)
            n += size;
        if (n < 0 || n >= size) {
            PyErr_SetString(PyExc_IndexError, "index out of range");
            return CPY_INT_TAG;
        }
        unsigned char num = PyBytes_Check(o) ? ((PyBytesObject *)o)->ob_sval[n]
                                             : ((PyByteArrayObject *)o)->ob_bytes[n];
        return num << 1;
    } else {
        PyErr_SetString(PyExc_OverflowError, CPYTHON_LARGE_INT_ERRMSG);
        return CPY_INT_TAG;
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

static inline Py_ssize_t Clamp(Py_ssize_t a, Py_ssize_t b, Py_ssize_t c) {
    return a < b ? b : (a >= c ? c : a);
}

PyObject *CPyBytes_GetSlice(PyObject *obj, CPyTagged start, CPyTagged end) {
    if ((PyBytes_Check(obj) || PyByteArray_Check(obj))
            && CPyTagged_CheckShort(start) && CPyTagged_CheckShort(end)) {
        Py_ssize_t startn = CPyTagged_ShortAsSsize_t(start);
        Py_ssize_t endn = CPyTagged_ShortAsSsize_t(end);
        Py_ssize_t len = ((PyVarObject *)obj)->ob_size;
        if (startn < 0) {
            startn += len;
        }
        if (endn < 0) {
            endn += len;
        }
        startn = Clamp(startn, 0, len);
        endn = Clamp(endn, 0, len);
        Py_ssize_t slice_len = endn - startn;
        if (PyBytes_Check(obj)) {
            return PyBytes_FromStringAndSize(PyBytes_AS_STRING(obj) + startn, slice_len);
        } else {
            return PyByteArray_FromStringAndSize(PyByteArray_AS_STRING(obj) + startn, slice_len);
        }
    }
    return CPyObject_GetSlice(obj, start, end);
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
