#ifndef VEC_H_INCL
#define VEC_H_INCL

#define PY_SSIZE_T_CLEAN
#include <Python.h>

// Arbitrary vec object (only shared bits)
typedef struct _VecObject {
    PyObject_VAR_HEAD
    Py_ssize_t len;
} VecObject;

// vec[i64]
typedef struct _VecI64Object {
    PyObject_VAR_HEAD
    Py_ssize_t len;
    int64_t items[1];
} VecI64Object;

// Simple generic vec: vec[t] when t is a type object
typedef struct _VecTObject {
    PyObject_VAR_HEAD
    Py_ssize_t len;
    PyTypeObject *item_type;
    PyObject *items[1];
} VecTObject;

// Extended generic vec type: vec[t | None], vec[vec[...]], etc.
typedef struct _VecTExtObject {
    PyObject_VAR_HEAD
    Py_ssize_t len;
    PyTypeObject *item_type;
    int32_t depth;  // Number of nested VecTExt or VecT types
    int32_t optionals;  // Flags for optional types on each nesting level
    PyObject *items[1];
} VecTExtObject;

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
    // VecTFeatures *t;
    // VecTExtFeatures *t_ext;
} VecCapsule;

#define VEC_SIZE(v) ((v)->ob_base.ob_size)

// Type objects

extern PyTypeObject VecI64Type;
extern PyTypeObject VecTType;
extern PyTypeObject VecTExtType;
extern VecI64Features I64Features;
extern PyTypeObject *I64TypeObj;

// vec[i64] operations

static inline int VecI64_Check(PyObject *o) {
    return o->ob_type == &VecI64Type;
}

PyObject *Vec_I64_Append(PyObject *obj, int64_t x);

// vec[t] operations (simple)

static inline int VecT_Check(PyObject *o) {
    return o->ob_type == &VecTType;
}

static inline int VecT_ItemCheck(VecTObject *v, PyObject *item) {
    if (PyObject_TypeCheck(item, v->item_type))
        return 1;
    else {
        // TODO: better error message
        PyErr_SetString(PyExc_TypeError, "invalid item type");
        return 0;
    }
}

VecTObject *Vec_T_New(Py_ssize_t size, PyTypeObject *item_type);
VecTObject *Vec_T_FromIterable(PyTypeObject *item_type, PyObject *iterable);
PyObject *Vec_T_Append(PyObject *obj, PyObject *x);

// vec[t] operations (extended)

static inline int VecTExt_Check(PyObject *o) {
    return o->ob_type == &VecTExtType;
}

static inline int VecTExt_ItemCheck(VecTExtObject *v, PyObject *it) {
    if (v->depth == 0 && PyObject_TypeCheck(it, v->item_type)) {
        return 1;
    } else if (it == Py_None && (v->optionals & 1)) {
        return 1;
    } else if (v->depth == 1 && it->ob_type == &VecTType
               && ((VecTExtObject *)it)->item_type == v->item_type) {
        return 1;
    } else if (it->ob_type == &VecTExtType
               && ((VecTExtObject *)it)->depth == v->depth - 1
               && ((VecTExtObject *)it)->item_type == v->item_type
               && ((VecTExtObject *)it)->optionals == (v->optionals >> 1)) {
        return 1;
    } else {
        // TODO: better error message
        PyErr_SetString(PyExc_TypeError, "invalid item type");
        return 0;
    }
}

VecTExtObject *Vec_T_Ext_New(Py_ssize_t size, PyTypeObject *item_type, int32_t optionals,
                             int32_t depth);
VecTExtObject *Vec_T_Ext_FromIterable(PyTypeObject *item_type, int32_t optionals, int32_t depth,
                                      PyObject *iterable);
PyObject *Vec_T_Ext_Append(PyObject *obj, PyObject *x);
// Misc helpers

static inline int check_float_error(PyObject *o) {
    if (PyFloat_Check(o)) {
        PyErr_SetString(PyExc_TypeError, "integer argument expected, got float");
        return 1;
    }
    return 0;
}

PyObject *vec_type_to_str(PyTypeObject *item_type, int32_t depth, int32_t optionals);
PyObject *vec_repr(PyObject *vec, PyTypeObject *item_type, int32_t depth, int32_t optionals,
                   int verbose);
PyObject *vec_generic_richcompare(Py_ssize_t *len, PyObject **items,
                                  Py_ssize_t *other_len, PyObject **other_items,
                                  int op);
PyObject *vec_generic_remove(Py_ssize_t *len, PyObject **items, PyObject *item);
PyObject *vec_generic_pop(Py_ssize_t *len, PyObject **items, PyObject *args);

#endif
