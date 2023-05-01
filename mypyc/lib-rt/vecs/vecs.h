#ifndef VEC_H_INCL
#define VEC_H_INCL

#define PY_SSIZE_T_CLEAN
#include <Python.h>

// Magic (native) integer return value on exception. Caller must also
// use PyErr_Occurred() since this overlaps with valid integer values.
#define MYPYC_INT_ERROR -113


// Buffer objects


// vecbuf[i64]
typedef struct _VecbufI64Object {
    PyObject_VAR_HEAD
    int64_t items[1];
} VecbufI64Object;

// Simple generic vecbuf: vecbuf[t] when t is a type object
typedef struct _VecbufTObject {
    PyObject_VAR_HEAD
    // Tagged pointer to PyTypeObject *. The lowest bit is 1 for optional item type.
    size_t item_type;
    PyObject *items[1];
} VecbufTObject;

typedef struct _VecbufTExtItem {
    Py_ssize_t len;
    PyObject *buf;
} VecbufTExtItem;

// Nested vec type: vec[vec[...]], vec[vec[...] | None], etc.
typedef struct _VecbufTExtObject {
    PyObject_VAR_HEAD
    // Tagged pointer to PyTypeObject *. The lowest bit is 1 for optional item type.
    size_t item_type;
    int32_t depth;  // Number of nested VecTExt or VecT types
    int32_t optionals;  // Flags for optional types on each nesting level
    VecbufTExtItem items[1];
} VecbufTExtObject;


// Unboxed vec objects


typedef struct _VecI64 {
    Py_ssize_t len;
    VecbufI64Object *buf;
} VecI64;

typedef struct _VecT {
    Py_ssize_t len;
    VecbufTObject *buf;
} VecT;

typedef struct _VecTExt {
    Py_ssize_t len;
    VecbufTExtObject *buf;
} VecTExt;


// Boxed vec objects


// Arbitrary boxed vec object (only shared bits)
typedef struct _VecObject {
    PyObject_HEAD
    Py_ssize_t len;
} VecObject;

// Boxed vec[i64]
typedef struct _VecI64Object {
    PyObject_HEAD
    VecI64 vec;
} VecI64Object;

// Simple boxed generic vecbuf: vecbuf[t] when t is a type object
typedef struct _VecTObject {
    PyObject_HEAD
    VecT vec;
} VecTObject;

// Extended generic vec type: vec[t | None], vec[vec[...]], etc.
typedef struct _VecTExtObject {
    PyObject_HEAD
    VecTExt vec;
} VecTExtObject;


// vec[i64] operations + type objects (stored in a capsule)
typedef struct _VecI64Features {
    PyTypeObject *boxed_type;
    PyTypeObject *buf_type;
    VecI64 (*alloc)(Py_ssize_t);
    PyObject *(*box)(VecI64);
    VecI64 (*unbox)(PyObject *);
    VecI64 (*append)(VecI64, int64_t);
    VecI64 (*pop)(VecI64, Py_ssize_t, int64_t *result);
    VecI64 (*remove)(VecI64, int64_t);
    // TODO: Py_ssize_t
    VecI64 (*slice)(VecI64, int64_t, int64_t);
    // PyObject *(*extend)(PyObject *, PyObject *);
    // PyObject *(*concat)(PyObject *, PyObject *);
    // bool (*contains)(PyObject *, int64_t);
    // iter?
} VecI64Features;

// vec[T] operations + type object (stored in a capsule)
//
// T is a class type
typedef struct _VecTFeatures {
    PyTypeObject *boxed_type;
    PyTypeObject *buf_type;
    VecT (*alloc)(Py_ssize_t, size_t);
    PyObject *(*box)(VecT);
    VecT (*unbox)(size_t);
    VecT (*append)(VecT, PyObject *);
    VecT (*pop)(VecT, Py_ssize_t, PyObject **result);
    VecT (*remove)(VecT, PyObject *);
    // TODO: Py_ssize_t
    VecT (*slice)(VecT, int64_t, int64_t);
    // PyObject *(*extend)(PyObject *, PyObject *);
    // PyObject *(*concat)(PyObject *, PyObject *);
    // bool (*contains)(PyObject *, PyObject *);
    // iter?
} VecTFeatures;

// vec[T] operations for complex item types + type object (stored in a capsule)
//
// T can be T | None or vec[T] (or a combination of these)
typedef struct _VecTExtFeatures {
    PyTypeObject *boxed_type;
    PyTypeObject *buf_type;
    VecTExt (*alloc)(Py_ssize_t, size_t, int optionals, int depth);
    PyObject *(*box)(VecTExt);
    VecTExt (*unbox)(size_t, int optionals, int depth);
    VecTExt (*append)(VecTExt, VecbufTExtItem);
    VecTExt (*pop)(VecTExt, Py_ssize_t, VecbufTExtItem *result);
    VecTExt (*remove)(VecTExt, VecbufTExtItem);
    // TODO: Py_ssize_t
    VecTExt (*slice)(VecTExt, int64_t, int64_t);
    // PyObject *(*extend)(PyObject *, PyObject *);
    // PyObject *(*concat)(PyObject *, PyObject *);
    // bool (*contains)(PyObject *, PyObject *);
    // iter?
} VecTExtFeatures;

typedef struct {
    VecI64Features *i64;
    VecTFeatures *t;
    VecTExtFeatures *t_ext;
} VecCapsule;

#define BUF_SIZE(b) ((b)->ob_base.ob_size)
#define BUF_ITEM_TYPE(b) ((PyTypeObject *)((b)->item_type & ~1))
#define VEC_CAP(v) ((v).buf->ob_base.ob_size)
#define VEC_IS_ERROR(v) ((v).len < 0)
#define VEC_DECREF(v) Py_XDECREF((v).buf)
#define VEC_INCREF(v) Py_XINCREF((v).buf)

inline VecI64 Vec_I64_Error() {
    VecI64 v = { .len = -1 };
    return v;
}

inline VecT Vec_T_Error() {
    VecT v = { .len = -1 };
    return v;
}

inline VecTExt Vec_T_Ext_Error() {
    VecTExt v = { .len = -1 };
    return v;
}

// Type objects

extern PyTypeObject VecbufI64Type;
extern PyTypeObject VecbufTType;
extern PyTypeObject VecbufTExtType;

extern PyTypeObject VecI64Type;
extern PyTypeObject VecTType;
extern PyTypeObject VecTExtType;

extern VecI64Features I64Features;
extern PyTypeObject *I64TypeObj;
extern VecTFeatures TFeatures;
extern VecTExtFeatures TExtFeatures;

// vec[i64] operations

static inline int VecI64_Check(PyObject *o) {
    return o->ob_type == &VecI64Type;
}

PyObject *Vec_I64_Box(VecI64);
VecI64 Vec_I64_Append(VecI64, int64_t x);

// vec[t] operations (simple)

static inline int VecT_Check(PyObject *o) {
    return o->ob_type == &VecTType;
}

static inline int VecT_ItemCheck(VecT v, PyObject *item) {
    if (PyObject_TypeCheck(item, BUF_ITEM_TYPE(v.buf))) {
        return 1;
    } else if ((v.buf->item_type & 1) && item == Py_None) {
        return 1;
    } else {
        // TODO: better error message
        PyErr_SetString(PyExc_TypeError, "invalid item type");
        return 0;
    }
}

VecT Vec_T_New(Py_ssize_t size, size_t item_type);
PyObject *Vec_T_FromIterable(size_t item_type, PyObject *iterable);
PyObject *Vec_T_Box(VecT);
VecT Vec_T_Append(VecT vec, PyObject *x);

// vec[t] operations (extended)

static inline int VecTExt_Check(PyObject *o) {
    return o->ob_type == &VecTExtType;
}

static inline int VecTExt_ItemCheck(VecTExt v, PyObject *it) {
    // TODO: vec[i64] item type
    if (it == Py_None && (v.buf->optionals & 1)) {
        return 1;
    } else if (v.buf->depth == 1 && it->ob_type == &VecTType
               && ((VecTExtObject *)it)->vec.buf->item_type == v.buf->item_type) {
        return 1;
    } else if (it->ob_type == &VecTExtType
               && ((VecTExtObject *)it)->vec.buf->depth == v.buf->depth - 1
               && ((VecTExtObject *)it)->vec.buf->item_type == v.buf->item_type
               && ((VecTExtObject *)it)->vec.buf->optionals == (v.buf->optionals >> 1)) {
        return 1;
    } else {
        // TODO: better error message
        PyErr_SetString(PyExc_TypeError, "invalid item type");
        return 0;
    }
}

VecTExt Vec_T_Ext_New(Py_ssize_t size, size_t item_type, int32_t optionals, int32_t depth);
PyObject *Vec_T_Ext_FromIterable(size_t item_type, int32_t optionals, int32_t depth,
                                 PyObject *iterable);
PyObject *Vec_T_Ext_Box(VecTExt);
VecTExt Vec_T_Ext_Append(VecTExt vec, VecbufTExtItem x);

// Return 0 on success, -1 on error. Store unboxed item in *unboxed if successful.
// Return a new reference.
static inline int Vec_T_Ext_UnboxItem(VecTExt v, PyObject *item, VecbufTExtItem *unboxed) {
    int optionals = v.buf->optionals;
    if (item == Py_None && (optionals & 1)) {
        unboxed->len = -1;
        unboxed->buf = NULL;
        return 0;
    }
    int depth = v.buf->depth;
    if (depth == 1) {
        // TODO: vec[i64]
        if (item->ob_type == &VecTType) {
            VecTExtObject *o = (VecTExtObject *)item;
            if (o->vec.buf->item_type == v.buf->item_type) {
                unboxed->len = o->vec.len;
                unboxed->buf = (PyObject *)o->vec.buf;
                Py_INCREF(unboxed->buf);
                return 0;
            }
        } else if (item->ob_type == &VecI64Type && v.buf->item_type == (size_t)I64TypeObj) {
            VecI64Object *o = (VecI64Object *)item;
            unboxed->len = o->vec.len;
            unboxed->buf = (PyObject *)o->vec.buf;
            Py_INCREF(unboxed->buf);
            return 0;
        }
    } else if (item->ob_type == &VecTExtType) {
        VecTExtObject *o = (VecTExtObject *)item;
        if (o->vec.buf->depth == v.buf->depth - 1
            && o->vec.buf->item_type == v.buf->item_type
            && o->vec.buf->optionals == (optionals >> 1)) {
            unboxed->len = o->vec.len;
            unboxed->buf = (PyObject *)o->vec.buf;
            Py_INCREF(unboxed->buf);
            return 0;
        }
    }
    // TODO: better error message
    PyErr_SetString(PyExc_TypeError, "invalid item type");
    return -1;
}

// Misc helpers

static inline int check_float_error(PyObject *o) {
    if (PyFloat_Check(o)) {
        PyErr_SetString(PyExc_TypeError, "integer argument expected, got float");
        return 1;
    }
    return 0;
}

PyObject *vec_type_to_str(size_t item_type, int32_t depth, int32_t optionals);
PyObject *vec_repr(PyObject *vec, size_t item_type, int32_t depth, int32_t optionals,
                   int verbose);
PyObject *vec_generic_richcompare(Py_ssize_t *len, PyObject **items,
                                  Py_ssize_t *other_len, PyObject **other_items,
                                  int op);
int vec_generic_remove(Py_ssize_t *len, PyObject **items, PyObject *item);
PyObject *vec_generic_pop_wrapper(Py_ssize_t *len, PyObject **items, PyObject *args);
PyObject *vec_generic_pop(Py_ssize_t *len, PyObject **items, Py_ssize_t index);

#endif
