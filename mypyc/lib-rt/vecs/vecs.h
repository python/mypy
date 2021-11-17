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
    // PyObject *(*concat)(PyObject *, PyObject *);
    // bool (*contains)(PyObject *, int64_t);
    // int64_t (*pop)(PyObject *);
    // bool (*remove)(PyObject *, int64_t);
    // iter?
} VecI64Features;

typedef struct _VecTObject {
    PyObject_VAR_HEAD
    Py_ssize_t len;
    PyObject *item_type;
    PyObject *items[1];
} VecTObject;

// vec[T] operations + type object (stored in a capsule)
//
// T can be a class type, T | None or vec[T] (or a combination of these)
typedef struct _VecTFeatures {
    PyTypeObject *type;
    PyObject *(*alloc)(Py_ssize_t);
    PyObject *(*append)(PyObject *, PyObject *);
    // PyObject *(*extend)(PyObject *, PyObject *);
    // PyObject *(*slice)(PyObject *, int64_t, int64_t);
    // PyObject *(*concat)(PyObject *, PyObject *);
    // bool (*contains)(PyObject *, PyObject *);
    // PyObject *(*pop)(PyObject *);
    // bool (*remove)(PyObject *, PyObject *);
    // iter?
} VecTFeatures;

typedef struct {
    VecI64Features *i64;
    // VecTFeatures *i64;
} VecCapsule;

#define VEC_SIZE(v) ((v)->ob_base.ob_size)

VecTObject *Vec_T_New(Py_ssize_t size, PyObject *item_type);
PyObject *Vec_T_Append(PyObject *obj, PyObject *x);

PyObject *Vec_I64_Append(PyObject *obj, int64_t x);

extern PyTypeObject VecI64Type;
extern PyTypeObject VecTType;
extern VecI64Features I64Features;

static inline int VecI64_Check(PyObject *o) {
    return o->ob_type == &VecI64Type;
}

static inline int VecT_Check(PyObject *o) {
    return o->ob_type == &VecTType;
}

static inline int check_float_error(PyObject *o) {
    if (PyFloat_Check(o)) {
        PyErr_SetString(PyExc_TypeError, "integer argument expected, got float");
        return 1;
    }
    return 0;
}

#endif
