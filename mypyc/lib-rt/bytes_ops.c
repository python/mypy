// Bytes primitive operations
//
// These are registered in mypyc.primitives.bytes_ops.

#include <Python.h>
#include "CPy.h"

PyObject *CPyBytes_FromInt(CPyTagged n) {
    if (CPyTagged_CheckShort(n)) {
        Py_ssize_t i, len = CPyTagged_AsSsize_t(n);
        // If `str' is NULL then PyBytes_FromStringAndSize() will allocate
        // `size+1' bytes (setting the last byte to the null terminating
        // character) and you can fill in the data yourself.
        PyBytesObject *ret = (PyBytesObject *)PyBytes_FromStringAndSize(NULL, len);
        for (i = 0; i < len; i++)
            ret->ob_sval[i] = '\x00';
        return (PyObject *)ret;
    } else {
        return NULL;
    }
}