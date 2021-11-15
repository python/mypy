#ifndef VEC_H_INCL
#define VEC_H_INCL

#define PY_SSIZE_T_CLEAN
#include <Python.h>

typedef struct _VecI64Object {
    PyObject_VAR_HEAD
    Py_ssize_t len;
    int64_t items[1];
} VecI64Object;

// vec[i64] operations + type object (stored in a capsule)
typedef struct _VecI64Features {
    PyTypeObject *type;
    PyObject *(*alloc)(Py_ssize_t);
    PyObject *(*append)(PyObject *, int64_t);
    // PyObject *(*extend)(PyObject *, PyObject *);
    // PyObject *(*slice)(PyObject *, int64_t, int64_t);
    // PyObject *(*concat)(PyObject *, VecObject *);
    // bool (*contains)(PyObject *, int64_t);
    // int64_t (*pop)(PyObject *);
    // bool (*remove)(PyObject *, int64_t);
    // iter?
} VecI64Features;

typedef struct {
    VecI64Features *i64;
} VecCapsule;

#endif
