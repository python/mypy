#ifndef VEC_H_INCL
#define VEC_H_INCL

#define PY_SSIZE_T_CLEAN
#include <Python.h>

// Magic (native) integer return value on exception. Caller must also
// use PyErr_Occurred() since this overlaps with valid integer values.
#define MYPYC_INT_ERROR -113

// Item type constants; must be even but not multiples of 4 (2 + 4 * n)
#define VEC_ITEM_TYPE_I64 2

inline size_t vec_is_magic_item_type(size_t item_type) {
    return item_type & 2;
}


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
    // Tagged pointer to PyTypeObject *. Lowest bit is set for optional item type.
    // The second lowest bit is set for a packed item type (VEC_ITEM_TYPE_*).
    size_t item_type;
    // Number of nested vec types (of any kind, at least 1)
    size_t depth;
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


#ifndef MYPYC_DECLARED_tuple_T2V88
#define MYPYC_DECLARED_tuple_T2V88
typedef struct tuple_T2V88 {
    VecI64 f0;
    int64_t f1;
} tuple_T2V88;
static tuple_T2V88 tuple_undefined_T2V88 = { { -1, NULL } , 0 };
#endif

typedef tuple_T2V88 VecI64PopResult;

// vec[i64] operations + type objects (stored in a capsule)
typedef struct _VecI64Features {
    PyTypeObject *boxed_type;
    PyTypeObject *buf_type;
    VecI64 (*alloc)(Py_ssize_t, Py_ssize_t);
    PyObject *(*box)(VecI64);
    VecI64 (*unbox)(PyObject *);
    VecI64 (*append)(VecI64, int64_t);
    VecI64PopResult (*pop)(VecI64, Py_ssize_t);
    VecI64 (*remove)(VecI64, int64_t);
    // TODO: Py_ssize_t
    VecI64 (*slice)(VecI64, int64_t, int64_t);
    // PyObject *(*extend)(PyObject *, PyObject *);
    // PyObject *(*concat)(PyObject *, PyObject *);
    // bool (*contains)(PyObject *, int64_t);
    // iter?
} VecI64Features;

#ifndef MYPYC_DECLARED_tuple_T2VOO
#define MYPYC_DECLARED_tuple_T2VOO
typedef struct tuple_T2VOO {
    VecT f0;
    PyObject *f1;
} tuple_T2VOO;
static tuple_T2VOO tuple_undefined_T2VOO = { { -1, NULL } , NULL };
#endif

typedef tuple_T2VOO VecTPopResult;

// vec[T] operations + type object (stored in a capsule)
//
// T is a class type
typedef struct _VecTFeatures {
    PyTypeObject *boxed_type;
    PyTypeObject *buf_type;
    VecT (*alloc)(Py_ssize_t, Py_ssize_t, size_t);
    PyObject *(*box)(VecT, size_t);
    VecT (*unbox)(PyObject *, size_t);
    VecT (*append)(VecT, PyObject *, size_t);
    VecTPopResult (*pop)(VecT, Py_ssize_t);
    VecT (*remove)(VecT, PyObject *);
    // TODO: Py_ssize_t
    VecT (*slice)(VecT, int64_t, int64_t);
    // PyObject *(*extend)(PyObject *, PyObject *);
    // PyObject *(*concat)(PyObject *, PyObject *);
    // bool (*contains)(PyObject *, PyObject *);
    // iter?
} VecTFeatures;

typedef struct {
    VecTExt vec;
    VecbufTExtItem item;
} VecTExtPopResult;

// vec[T] operations for complex item types + type object (stored in a capsule)
//
// T can be T | None or vec[T] (or a combination of these)
typedef struct _VecTExtFeatures {
    PyTypeObject *boxed_type;
    PyTypeObject *buf_type;
    VecTExt (*alloc)(Py_ssize_t, Py_ssize_t, size_t, size_t depth);
    PyObject *(*box)(VecTExt);
    VecTExt (*unbox)(PyObject *, size_t, size_t depth);
    VecTExt (*append)(VecTExt, VecbufTExtItem);
    VecTExtPopResult (*pop)(VecTExt, Py_ssize_t);
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
#define ITEM_TYPE(t) ((PyTypeObject *)((t) & ~1))
#define BUF_ITEM_TYPE(b) ITEM_TYPE((b)->item_type)
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
VecI64 Vec_I64_Remove(VecI64, int64_t x);
VecI64PopResult Vec_I64_Pop(VecI64 v, Py_ssize_t index);

// vec[t] operations (simple)

static inline int VecT_Check(PyObject *o) {
    return o->ob_type == &VecTType;
}

static inline int VecT_ItemCheck(VecT v, PyObject *item, size_t item_type) {
    if (PyObject_TypeCheck(item, ITEM_TYPE(item_type))) {
        return 1;
    } else if ((item_type & 1) && item == Py_None) {
        return 1;
    } else {
        // TODO: better error message
        PyErr_SetString(PyExc_TypeError, "invalid item type");
        return 0;
    }
}

VecT Vec_T_New(Py_ssize_t size, Py_ssize_t cap, size_t item_type);
PyObject *Vec_T_FromIterable(size_t item_type, PyObject *iterable);
PyObject *Vec_T_Box(VecT vec, size_t item_type);
VecT Vec_T_Append(VecT vec, PyObject *x, size_t item_type);
VecT Vec_T_Remove(VecT vec, PyObject *x);
VecTPopResult Vec_T_Pop(VecT v, Py_ssize_t index);

// vec[t] operations (extended)

static inline int VecTExt_Check(PyObject *o) {
    return o->ob_type == &VecTExtType;
}

static inline int VecTExt_ItemCheck(VecTExt v, PyObject *it) {
    // TODO: vec[i64] item type
    if (it == Py_None && (v.buf->item_type & 1)) {
        return 1;
    } else if (v.buf->depth == 1 && it->ob_type == &VecTType
               && ((VecTExtObject *)it)->vec.buf->item_type == v.buf->item_type) {
        return 1;
    } else if (it->ob_type == &VecTExtType
               && ((VecTExtObject *)it)->vec.buf->depth == v.buf->depth - 1
               && ((VecTExtObject *)it)->vec.buf->item_type == v.buf->item_type) {
        return 1;
    } else {
        // TODO: better error message
        PyErr_SetString(PyExc_TypeError, "invalid item type");
        return 0;
    }
}

VecTExt Vec_T_Ext_New(Py_ssize_t size, Py_ssize_t cap, size_t item_type, size_t depth);
PyObject *Vec_T_Ext_FromIterable(size_t item_type, size_t depth, PyObject *iterable);
PyObject *Vec_T_Ext_Box(VecTExt);
VecTExt Vec_T_Ext_Append(VecTExt vec, VecbufTExtItem x);
VecTExt Vec_T_Ext_Remove(VecTExt vec, VecbufTExtItem x);
VecTExtPopResult Vec_T_Ext_Pop(VecTExt v, Py_ssize_t index);

// Return 0 on success, -1 on error. Store unboxed item in *unboxed if successful.
// Return a *borrowed* reference.
static inline int Vec_T_Ext_UnboxItem(VecTExt v, PyObject *item, VecbufTExtItem *unboxed) {
    size_t depth = v.buf->depth;
    if (depth == 1) {
        // TODO: vec[i64]
        if (item->ob_type == &VecTType) {
            VecTExtObject *o = (VecTExtObject *)item;
            if (o->vec.buf->item_type == v.buf->item_type) {
                unboxed->len = o->vec.len;
                unboxed->buf = (PyObject *)o->vec.buf;
                return 0;
            }
        } else if (item->ob_type == &VecI64Type && v.buf->item_type == VEC_ITEM_TYPE_I64) {
            VecI64Object *o = (VecI64Object *)item;
            unboxed->len = o->vec.len;
            unboxed->buf = (PyObject *)o->vec.buf;
            return 0;
        }
    } else if (item->ob_type == &VecTExtType) {
        VecTExtObject *o = (VecTExtObject *)item;
        if (o->vec.buf->depth == v.buf->depth - 1
            && o->vec.buf->item_type == v.buf->item_type) {
            unboxed->len = o->vec.len;
            unboxed->buf = (PyObject *)o->vec.buf;
            return 0;
        }
    }
    // TODO: better error message
    PyErr_SetString(PyExc_TypeError, "invalid item type");
    return -1;
}

static inline PyObject *Vec_T_Ext_BoxItem(VecTExt v, VecbufTExtItem item) {
    if (item.len < 0)
        Py_RETURN_NONE;
    Py_XINCREF(item.buf);
    if (v.buf->depth > 1) {
        // Item is a nested vec
        VecTExt v = { .len = item.len, .buf = (VecbufTExtObject *)item.buf };
        return Vec_T_Ext_Box(v);
    } else {
        // Item is a non-nested vec
        size_t item_type = v.buf->item_type;
        if (item_type == VEC_ITEM_TYPE_I64) {
            // vec[i64]
            VecI64 v = { .len = item.len, .buf = (VecbufI64Object *)item.buf };
            return Vec_I64_Box(v);
        } else {
            // Generic vec[t]
            VecT v = { .len = item.len, .buf = (VecbufTObject *)item.buf };
            return Vec_T_Box(v, item_type);
        }
    }
}

// Misc helpers

static inline int check_float_error(PyObject *o) {
    if (PyFloat_Check(o)) {
        PyErr_SetString(PyExc_TypeError, "integer argument expected, got float");
        return 1;
    }
    return 0;
}

PyObject *vec_type_to_str(size_t item_type, size_t depth);
PyObject *vec_repr(PyObject *vec, size_t item_type, size_t depth, int verbose);
PyObject *vec_generic_richcompare(Py_ssize_t *len, PyObject **items,
                                  Py_ssize_t *other_len, PyObject **other_items,
                                  int op);
int vec_generic_remove(Py_ssize_t *len, PyObject **items, PyObject *item);
PyObject *vec_generic_pop_wrapper(Py_ssize_t *len, PyObject **items, PyObject *args);
PyObject *vec_generic_pop(Py_ssize_t *len, PyObject **items, Py_ssize_t index);

#endif
