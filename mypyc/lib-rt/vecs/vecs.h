#ifndef VEC_H_INCL
#define VEC_H_INCL

#define PY_SSIZE_T_CLEAN
#include <Python.h>

typedef struct {
    PyObject_VAR_HEAD
    Py_ssize_t len;
    long long items[1];
} VecObject;

// vec[i64] operations + type object (stored in a capsule)
typedef struct {
    PyTypeObject *type;
    PyObject *(*alloc)(Py_ssize_t);
    VecObject *(*append)(VecObject *, int64_t);
    // VecObject *(*extend)(VecObject *, PyObject *);
    // VecObject *(*slice)(VecObject *, int64_t, int64_t);
    // VecObject *(*concat)(VecObject *, VecObject *);
    // bool (*contains)(VecObject *, int64_t);
    // int64_t (*pop)(VecObject *);
    // iter?
} VecI64Features;

typedef struct {
    VecI64Features *i64;
} VecCapsule;

#endif
