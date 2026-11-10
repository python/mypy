#ifndef VECS_INTERNAL_H_INCL
#define VECS_INTERNAL_H_INCL

// Internal header for mypyc/lib-rt/vecs implementation

#include <Python.h>

// The base vec type
extern PyTypeObject VecType;

// Maximum number of items in a buffer object with the given struct type and item size.
// Allocating more would overflow the allocation size, so this must be checked before
// calling PyObject_NewVar or PyObject_GC_NewVar, since they don't check for overflow.
// This is a compile-time constant, so the division is free.
#define VEC_MAX_BUF_ITEMS(buf_struct, item_size) \
    ((PY_SSIZE_T_MAX - (Py_ssize_t)sizeof(buf_struct)) / (Py_ssize_t)(item_size))

#endif  // VECS_INTERNAL_H_INCL
