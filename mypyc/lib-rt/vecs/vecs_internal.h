#ifndef VECS_INTERNAL_H_INCL
#define VECS_INTERNAL_H_INCL

// Internal header for mypyc/lib-rt/vecs implementation

#include <Python.h>

// The base vec type
extern PyTypeObject VecType;

// Return 0 if a buffer object of 'type' with 'size' items can be allocated without
// overflow. Otherwise set MemoryError and return -1. This must be checked before
// calling PyObject_NewVar or PyObject_GC_NewVar, since they don't check for overflow.
static inline int Vec_CheckBufSize(PyTypeObject *type, Py_ssize_t size) {
    if (size > (PY_SSIZE_T_MAX - type->tp_basicsize) / type->tp_itemsize) {
        PyErr_NoMemory();
        return -1;
    }
    return 0;
}

#endif  // VECS_INTERNAL_H_INCL
