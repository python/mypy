#ifndef VEC_H_INCL
#define VEC_H_INCL

#define PY_SSIZE_T_CLEAN
#include <Python.h>

// Magic (native) integer return value on exception. Caller must also
// use PyErr_Occurred() since this overlaps with valid integer values.
#define MYPYC_INT_ERROR -113

// Item type constants; must be even but not multiples of 4 (2 + 4 * n)
#define VEC_ITEM_TYPE_I64 2
#define VEC_ITEM_TYPE_FLOAT 18

inline size_t Vec_IsMagicItemType(size_t item_type) {
    return item_type & 2;
}


// Buffer objects


// vecbuf[i64]
typedef struct _VecI64BufObject {
    PyObject_VAR_HEAD
    int64_t items[1];
} VecI64BufObject;

// vecbuf[float]
typedef struct _VecFloatBufObject {
    PyObject_VAR_HEAD
    double items[1];
} VecFloatBufObject;

// Simple generic vecbuf: vecbuf[t] when t is a type object
typedef struct _VecTBufObject {
    PyObject_VAR_HEAD
    // Tagged pointer to PyTypeObject *. The lowest bit is 1 for optional item type.
    size_t item_type;
    PyObject *items[1];
} VecTBufObject;

typedef struct _VecNestedBufItem {
    Py_ssize_t len;
    PyObject *buf;
} VecNestedBufItem;

// Nested vec type: vec[vec[...]], vec[vec[...] | None], etc.
typedef struct _VecNestedBufObject {
    PyObject_VAR_HEAD
    // Tagged pointer to PyTypeObject *. Lowest bit is set for optional item type.
    // The second lowest bit is set for a packed item type (VEC_ITEM_TYPE_*).
    size_t item_type;
    // Number of nested vec types (of any kind, at least 1)
    size_t depth;
    VecNestedBufItem items[1];
} VecNestedBufObject;


// Unboxed vec objects


typedef struct _VecI64 {
    Py_ssize_t len;
    VecI64BufObject *buf;
} VecI64;

typedef struct _VecFloat {
    Py_ssize_t len;
    VecFloatBufObject *buf;
} VecFloat;

typedef struct _VecT {
    Py_ssize_t len;
    VecTBufObject *buf;
} VecT;

typedef struct _VecNested {
    Py_ssize_t len;
    VecNestedBufObject *buf;
} VecNested;


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

// Boxed vec[float]
typedef struct _VecFloatObject {
    PyObject_HEAD
    VecFloat vec;
} VecFloatObject;

// Simple boxed generic vecbuf: vecbuf[t] when t is a type object
typedef struct _VecTObject {
    PyObject_HEAD
    VecT vec;
} VecTObject;

// Extended generic vec type: vec[t | None], vec[vec[...]], etc.
typedef struct _VecNestedObject {
    PyObject_HEAD
    VecNested vec;
} VecNestedObject;


#ifndef MYPYC_DECLARED_tuple_T2V88
#define MYPYC_DECLARED_tuple_T2V88
typedef struct tuple_T2V88 {
    VecI64 f0;
    int64_t f1;
} tuple_T2V88;
static tuple_T2V88 tuple_undefined_T2V88 = { { -1, NULL } , 0 };
#endif

#ifndef MYPYC_DECLARED_tuple_T2VFF
#define MYPYC_DECLARED_tuple_T2VFF
typedef struct tuple_T2VFF {
    VecFloat f0;
    double f1;
} tuple_T2VFF;
static tuple_T2VFF tuple_undefined_T2VFF = { { -1, NULL } , 0.0 };
#endif

typedef tuple_T2V88 VecI64PopResult;
typedef tuple_T2VFF VecFloatPopResult;

// vec[i64] operations + type objects (stored in a capsule)
typedef struct _VecI64Features {
    PyTypeObject *boxed_type;
    PyTypeObject *buf_type;
    VecI64 (*alloc)(Py_ssize_t, Py_ssize_t);
    PyObject *(*box)(VecI64);
    VecI64 (*unbox)(PyObject *);
    VecI64 (*convert_from_nested)(VecNestedBufItem);
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

// vec[float] operations + type objects (stored in a capsule)
typedef struct _VecFloatFeatures {
    PyTypeObject *boxed_type;
    PyTypeObject *buf_type;
    VecFloat (*alloc)(Py_ssize_t, Py_ssize_t);
    PyObject *(*box)(VecFloat);
    VecFloat (*unbox)(PyObject *);
    VecFloat (*convert_from_nested)(VecNestedBufItem);
    VecFloat (*append)(VecFloat, double);
    VecFloatPopResult (*pop)(VecFloat, Py_ssize_t);
    VecFloat (*remove)(VecFloat, double);
    // TODO: Py_ssize_t
    VecFloat (*slice)(VecFloat, int64_t, int64_t);
    // PyObject *(*extend)(PyObject *, PyObject *);
    // PyObject *(*concat)(PyObject *, PyObject *);
    // bool (*contains)(PyObject *, double);
    // iter?
} VecFloatFeatures;

#ifndef MYPYC_DECLARED_tuple_T2VOO
#define MYPYC_DECLARED_tuple_T2VOO
typedef struct tuple_T2VOO {
    VecT f0;
    PyObject *f1;
} tuple_T2VOO;
static tuple_T2VOO tuple_undefined_T2VOO = { { -1, NULL } , NULL };
#endif

typedef tuple_T2VOO VecTPopResult;

// vec[T] operations + type objects (stored in a capsule)
//
// T is a class type or class type | None
typedef struct _VecTFeatures {
    PyTypeObject *boxed_type;
    PyTypeObject *buf_type;
    VecT (*alloc)(Py_ssize_t, Py_ssize_t, size_t);
    PyObject *(*box)(VecT, size_t);
    VecT (*unbox)(PyObject *, size_t);
    VecT (*convert_from_nested)(VecNestedBufItem);
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


#ifndef MYPYC_DECLARED_tuple_T2VvVi
#define MYPYC_DECLARED_tuple_T2VvVi
typedef struct tuple_T2VvVi {
    VecNested f0;
    VecNestedBufItem f1;
} tuple_T2VvVi;
static tuple_T2VvVi tuple_undefined_T2VvVi = { { -1, NULL } , { -1, NULL } };
#endif

typedef tuple_T2VvVi VecNestedPopResult;

// Nested vec operations + type objects (stored in a capsule)
typedef struct _VecNestedFeatures {
    PyTypeObject *boxed_type;
    PyTypeObject *buf_type;
    VecNested (*alloc)(Py_ssize_t, Py_ssize_t, size_t, size_t depth);
    PyObject *(*box)(VecNested);
    VecNested (*unbox)(PyObject *, size_t, size_t depth);
    VecNested (*convert_from_nested)(VecNestedBufItem);
    VecNested (*append)(VecNested, VecNestedBufItem);
    VecNestedPopResult (*pop)(VecNested, Py_ssize_t);
    VecNested (*remove)(VecNested, VecNestedBufItem);
    // TODO: Py_ssize_t
    VecNested (*slice)(VecNested, int64_t, int64_t);
    // PyObject *(*extend)(PyObject *, PyObject *);
    // PyObject *(*concat)(PyObject *, PyObject *);
    // bool (*contains)(PyObject *, PyObject *);
    // iter?
} VecNestedFeatures;

typedef struct {
    VecTFeatures *t;
    VecNestedFeatures *nested;
    VecI64Features *i64;
    VecFloatFeatures *float_;
} VecCapsule;

#define BUF_SIZE(b) ((b)->ob_base.ob_size)
#define ITEM_TYPE(t) ((PyTypeObject *)((t) & ~1))
#define BUF_ITEM_TYPE(b) ITEM_TYPE((b)->item_type)
#define VEC_CAP(v) ((v).buf->ob_base.ob_size)
#define VEC_IS_ERROR(v) ((v).len < 0)
#define VEC_DECREF(v) Py_XDECREF((v).buf)
#define VEC_INCREF(v) Py_XINCREF((v).buf)

inline VecI64 VecI64_Error() {
    VecI64 v = { .len = -1 };
    return v;
}

inline VecFloat VecFloat_Error() {
    VecFloat v = { .len = -1 };
    return v;
}

inline VecT VecT_Error() {
    VecT v = { .len = -1 };
    return v;
}

inline VecNested VecVec_Error() {
    VecNested v = { .len = -1 };
    return v;
}

// Type objects

extern PyTypeObject VecI64BufType;
extern PyTypeObject VecFloatBufType;
extern PyTypeObject VecTBufType;
extern PyTypeObject VecNestedBufType;

extern PyTypeObject VecI64Type;
extern PyTypeObject VecFloatType;
extern PyTypeObject VecTType;
extern PyTypeObject VecNestedType;

extern PyTypeObject *I64TypeObj;

extern VecI64Features I64Features;
extern VecFloatFeatures FloatFeatures;
extern VecTFeatures TFeatures;
extern VecNestedFeatures TExtFeatures;

// vec[i64] operations

static inline int VecI64_Check(PyObject *o) {
    return o->ob_type == &VecI64Type;
}

PyObject *VecI64_Box(VecI64);
VecI64 VecI64_Append(VecI64, int64_t x);
VecI64 VecI64_Remove(VecI64, int64_t x);
VecI64PopResult VecI64_Pop(VecI64 v, Py_ssize_t index);

// vec[float] operations

static inline int VecFloat_Check(PyObject *o) {
    return o->ob_type == &VecFloatType;
}

PyObject *VecFloat_Box(VecFloat);
VecFloat VecFloat_Append(VecFloat, double x);
VecFloat VecFloat_Remove(VecFloat, double x);
VecFloatPopResult VecFloat_Pop(VecFloat v, Py_ssize_t index);

// vec[t] operations

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

VecT VecT_New(Py_ssize_t size, Py_ssize_t cap, size_t item_type);
PyObject *VecT_FromIterable(size_t item_type, PyObject *iterable);
PyObject *VecT_Box(VecT vec, size_t item_type);
VecT VecT_Append(VecT vec, PyObject *x, size_t item_type);
VecT VecT_Remove(VecT vec, PyObject *x);
VecTPopResult VecT_Pop(VecT v, Py_ssize_t index);

// Nested vec operations

static inline int VecVec_Check(PyObject *o) {
    return o->ob_type == &VecNestedType;
}

VecNested VecVec_New(Py_ssize_t size, Py_ssize_t cap, size_t item_type, size_t depth);
PyObject *VecVec_FromIterable(size_t item_type, size_t depth, PyObject *iterable);
PyObject *VecVec_Box(VecNested);
VecNested VecVec_Append(VecNested vec, VecNestedBufItem x);
VecNested VecVec_Remove(VecNested vec, VecNestedBufItem x);
VecNestedPopResult VecVec_Pop(VecNested v, Py_ssize_t index);

// Return 0 on success, -1 on error. Store unboxed item in *unboxed if successful.
// Return a *borrowed* reference.
static inline int VecVec_UnboxItem(VecNested v, PyObject *item, VecNestedBufItem *unboxed) {
    size_t depth = v.buf->depth;
    if (depth == 1) {
        if (item->ob_type == &VecTType) {
            VecNestedObject *o = (VecNestedObject *)item;
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
        } else if (item->ob_type == &VecFloatType && v.buf->item_type == VEC_ITEM_TYPE_FLOAT) {
            VecFloatObject *o = (VecFloatObject *)item;
            unboxed->len = o->vec.len;
            unboxed->buf = (PyObject *)o->vec.buf;
            return 0;
        }
    } else if (item->ob_type == &VecNestedType) {
        VecNestedObject *o = (VecNestedObject *)item;
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

static inline PyObject *VecVec_BoxItem(VecNested v, VecNestedBufItem item) {
    if (item.len < 0)
        Py_RETURN_NONE;
    Py_XINCREF(item.buf);
    if (v.buf->depth > 1) {
        // Item is a nested vec
        VecNested v = { .len = item.len, .buf = (VecNestedBufObject *)item.buf };
        return VecVec_Box(v);
    } else {
        // Item is a non-nested vec
        size_t item_type = v.buf->item_type;
        if (item_type == VEC_ITEM_TYPE_I64) {
            // vec[i64]
            VecI64 v = { .len = item.len, .buf = (VecI64BufObject *)item.buf };
            return VecI64_Box(v);
        } else if (item_type == VEC_ITEM_TYPE_FLOAT) {
            // vec[float]
            VecFloat v = { .len = item.len, .buf = (VecFloatBufObject *)item.buf };
            return VecFloat_Box(v);
        } else {
            // Generic vec[t]
            VecT v = { .len = item.len, .buf = (VecTBufObject *)item.buf };
            return VecT_Box(v, item_type);
        }
    }
}

// Misc helpers

static inline int Vec_CheckFloatError(PyObject *o) {
    if (PyFloat_Check(o)) {
        PyErr_SetString(PyExc_TypeError, "integer argument expected, got float");
        return 1;
    }
    return 0;
}

PyObject *Vec_TypeToStr(size_t item_type, size_t depth);
PyObject *Vec_GenericRepr(PyObject *vec, size_t item_type, size_t depth, int verbose);
PyObject *Vec_GenericRichcompare(Py_ssize_t *len, PyObject **items,
                                  Py_ssize_t *other_len, PyObject **other_items,
                                  int op);
int Vec_GenericRemove(Py_ssize_t *len, PyObject **items, PyObject *item);
PyObject *Vec_GenericPopWrapper(Py_ssize_t *len, PyObject **items, PyObject *args);
PyObject *Vec_GenericPop(Py_ssize_t *len, PyObject **items, Py_ssize_t index);

#endif
