#ifndef VEC_H_INCL
#define VEC_H_INCL

// Header for the implementation of librt.vecs, which defines the 'vec' type.
// Refer to librt_vecs.c for more detailed information.

#ifndef MYPYC_EXPERIMENTAL

static int
import_librt_vecs(void)
{
    // All librt.vecs features are experimental for now, so don't set up the API here
    return 0;
}

#else  // MYPYC_EXPERIMENTAL

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdint.h>

// Magic (native) integer return value on exception. Caller must also
// use PyErr_Occurred() since this overlaps with valid integer values.
#define MYPYC_INT_ERROR -113

// Item type constants for supported packed/specialized item types; must be
// even but not a multiple of 4 (2 + 4 * n). Each of these has a corresponding
// distinct implementation C extension class. For example, vec[i64] has a
// different runtime type than vec[i32]. All other item types use generic
// implementations.
#define VEC_ITEM_TYPE_I64 2
#define VEC_ITEM_TYPE_I32 6
#define VEC_ITEM_TYPE_I16 10
#define VEC_ITEM_TYPE_U8  14
#define VEC_ITEM_TYPE_FLOAT 18
#define VEC_ITEM_TYPE_BOOL 22

static inline size_t Vec_IsMagicItemType(size_t item_type) {
    return item_type & 2;
}


// Buffer objects


// vecbuf[i64]
typedef struct _VecI64BufObject {
    PyObject_VAR_HEAD
    int64_t items[1];
} VecI64BufObject;

// vecbuf[i32]
typedef struct _VecI32BufObject {
    PyObject_VAR_HEAD
    int32_t items[1];
} VecI32BufObject;

// vecbuf[i16]
typedef struct _VecI16BufObject {
    PyObject_VAR_HEAD
    int16_t items[1];
} VecI16BufObject;

// vecbuf[u8]
typedef struct _VecU8BufObject {
    PyObject_VAR_HEAD
    uint8_t items[1];
} VecU8BufObject;

// vecbuf[float]
typedef struct _VecFloatBufObject {
    PyObject_VAR_HEAD
    double items[1];
} VecFloatBufObject;

// vecbuf[bool]
typedef struct _VecBoolBufObject {
    PyObject_VAR_HEAD
    char items[1];
} VecBoolBufObject;

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

typedef struct _VecI32 {
    Py_ssize_t len;
    VecI32BufObject *buf;
} VecI32;

typedef struct _VecI16 {
    Py_ssize_t len;
    VecI16BufObject *buf;
} VecI16;

typedef struct _VecU8 {
    Py_ssize_t len;
    VecU8BufObject *buf;
} VecU8;

typedef struct _VecFloat {
    Py_ssize_t len;
    VecFloatBufObject *buf;
} VecFloat;

typedef struct _VecBool {
    Py_ssize_t len;
    VecBoolBufObject *buf;
} VecBool;

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

// Boxed vec[i32]
typedef struct _VecI32Object {
    PyObject_HEAD
    VecI32 vec;
} VecI32Object;

// Boxed vec[i16]
typedef struct _VecI16Object {
    PyObject_HEAD
    VecI16 vec;
} VecI16Object;

// Boxed vec[u8]
typedef struct _VecU8Object {
    PyObject_HEAD
    VecU8 vec;
} VecU8Object;

// Boxed vec[float]
typedef struct _VecFloatObject {
    PyObject_HEAD
    VecFloat vec;
} VecFloatObject;

// Boxed vec[bool]
typedef struct _VecBoolObject {
    PyObject_HEAD
    VecBool vec;
} VecBoolObject;

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

#ifndef MYPYC_DECLARED_tuple_T2V44
#define MYPYC_DECLARED_tuple_T2V44
typedef struct tuple_T2V44 {
    VecI32 f0;
    int32_t f1;
} tuple_T2V44;
static tuple_T2V44 tuple_undefined_T2V44 = { { -1, NULL } , 0 };
#endif

#ifndef MYPYC_DECLARED_tuple_T2V22
#define MYPYC_DECLARED_tuple_T2V22
typedef struct tuple_T2V22 {
    VecI16 f0;
    int16_t f1;
} tuple_T2V22;
static tuple_T2V22 tuple_undefined_T2V22 = { { -1, NULL } , 0 };
#endif

#ifndef MYPYC_DECLARED_tuple_T2VU1U1
#define MYPYC_DECLARED_tuple_T2VU1U1
typedef struct tuple_T2VU1U1 {
    VecU8 f0;
    uint8_t f1;
} tuple_T2VU1U1;
static tuple_T2VU1U1 tuple_undefined_T2VU1U1 = { { -1, NULL } , 0 };
#endif

#ifndef MYPYC_DECLARED_tuple_T2VFF
#define MYPYC_DECLARED_tuple_T2VFF
typedef struct tuple_T2VFF {
    VecFloat f0;
    double f1;
} tuple_T2VFF;
static tuple_T2VFF tuple_undefined_T2VFF = { { -1, NULL } , 0.0 };
#endif

#ifndef MYPYC_DECLARED_tuple_T2VCC
#define MYPYC_DECLARED_tuple_T2VCC
typedef struct tuple_T2VCC {
    VecBool f0;
    char f1;
} tuple_T2VCC;
static tuple_T2VCC tuple_undefined_T2VCC = { { -1, NULL } , 0 };
#endif

typedef tuple_T2V88 VecI64PopResult;
typedef tuple_T2V44 VecI32PopResult;
typedef tuple_T2V22 VecI16PopResult;
typedef tuple_T2VU1U1 VecU8PopResult;
typedef tuple_T2VFF VecFloatPopResult;
typedef tuple_T2VCC VecBoolPopResult;

// vec[i64] operations + type objects (stored in a capsule)
typedef struct _VecI64API {
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
} VecI64API;

// vec[i32] operations + type objects (stored in a capsule)
typedef struct _VecI32API {
    PyTypeObject *boxed_type;
    PyTypeObject *buf_type;
    VecI32 (*alloc)(Py_ssize_t, Py_ssize_t);
    PyObject *(*box)(VecI32);
    VecI32 (*unbox)(PyObject *);
    VecI32 (*convert_from_nested)(VecNestedBufItem);
    VecI32 (*append)(VecI32, int32_t);
    VecI32PopResult (*pop)(VecI32, Py_ssize_t);
    VecI32 (*remove)(VecI32, int32_t);
    // TODO: Py_ssize_t
    VecI32 (*slice)(VecI32, int64_t, int64_t);
    // PyObject *(*extend)(PyObject *, PyObject *);
    // PyObject *(*concat)(PyObject *, PyObject *);
    // bool (*contains)(PyObject *, int32_t);
    // iter?
} VecI32API;

// vec[i16] operations + type objects (stored in a capsule)
typedef struct _VecI16API {
    PyTypeObject *boxed_type;
    PyTypeObject *buf_type;
    VecI16 (*alloc)(Py_ssize_t, Py_ssize_t);
    PyObject *(*box)(VecI16);
    VecI16 (*unbox)(PyObject *);
    VecI16 (*convert_from_nested)(VecNestedBufItem);
    VecI16 (*append)(VecI16, int16_t);
    VecI16PopResult (*pop)(VecI16, Py_ssize_t);
    VecI16 (*remove)(VecI16, int16_t);
    // TODO: Py_ssize_t
    VecI16 (*slice)(VecI16, int64_t, int64_t);
    // PyObject *(*extend)(PyObject *, PyObject *);
    // PyObject *(*concat)(PyObject *, PyObject *);
    // bool (*contains)(PyObject *, int16_t);
    // iter?
} VecI16API;

// vec[u8] operations + type objects (stored in a capsule)
typedef struct _VecU8API {
    PyTypeObject *boxed_type;
    PyTypeObject *buf_type;
    VecU8 (*alloc)(Py_ssize_t, Py_ssize_t);
    PyObject *(*box)(VecU8);
    VecU8 (*unbox)(PyObject *);
    VecU8 (*convert_from_nested)(VecNestedBufItem);
    VecU8 (*append)(VecU8, uint8_t);
    VecU8PopResult (*pop)(VecU8, Py_ssize_t);
    VecU8 (*remove)(VecU8, uint8_t);
    // TODO: Py_ssize_t
    VecU8 (*slice)(VecU8, int64_t, int64_t);
    // PyObject *(*extend)(PyObject *, PyObject *);
    // PyObject *(*concat)(PyObject *, PyObject *);
    // bool (*contains)(PyObject *, uint8_t);
    // iter?
} VecU8API;

// vec[float] operations + type objects (stored in a capsule)
typedef struct _VecFloatAPI {
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
} VecFloatAPI;

// vec[bool] operations + type objects (stored in a capsule)
typedef struct _VecBoolAPI {
    PyTypeObject *boxed_type;
    PyTypeObject *buf_type;
    VecBool (*alloc)(Py_ssize_t, Py_ssize_t);
    PyObject *(*box)(VecBool);
    VecBool (*unbox)(PyObject *);
    VecBool (*convert_from_nested)(VecNestedBufItem);
    VecBool (*append)(VecBool, char);
    VecBoolPopResult (*pop)(VecBool, Py_ssize_t);
    VecBool (*remove)(VecBool, char);
    // TODO: Py_ssize_t
    VecBool (*slice)(VecBool, int64_t, int64_t);
    // PyObject *(*extend)(PyObject *, PyObject *);
    // PyObject *(*concat)(PyObject *, PyObject *);
    // bool (*contains)(PyObject *, char);
    // iter?
} VecBoolAPI;

typedef struct {
    VecI64API *i64;
    VecI32API *i32;
    VecI16API *i16;
    VecU8API *u8;
    VecFloatAPI *float_;
    VecBoolAPI *bool_;
} VecCapsule;

#define VEC_BUF_SIZE(b) ((b)->ob_base.ob_size)
#define VEC_ITEM_TYPE(t) ((PyTypeObject *)((t) & ~1))
#define VEC_BUF_ITEM_TYPE(b) VEC_ITEM_TYPE((b)->item_type)
#define VEC_CAP(v) ((v).buf->ob_base.ob_size)
#define VEC_IS_ERROR(v) ((v).len < 0)
#define VEC_DECREF(v) Py_XDECREF((v).buf)
#define VEC_INCREF(v) Py_XINCREF((v).buf)

// Type objects

// Buffer type objects that store vec items
extern PyTypeObject VecI64BufType;
extern PyTypeObject VecI32BufType;
extern PyTypeObject VecI16BufType;
extern PyTypeObject VecU8BufType;
extern PyTypeObject VecFloatBufType;
extern PyTypeObject VecBoolBufType;

// Wrapper type objects for boxed vec values
extern PyTypeObject VecI64Type;
extern PyTypeObject VecI32Type;
extern PyTypeObject VecI16Type;
extern PyTypeObject VecU8Type;
extern PyTypeObject VecFloatType;
extern PyTypeObject VecBoolType;

// Type objects corresponding to the 'i64', 'i32', 'i16, and 'u8' types
extern PyTypeObject *LibRTVecs_I64TypeObj;
extern PyTypeObject *LibRTVecs_I32TypeObj;
extern PyTypeObject *LibRTVecs_I16TypeObj;
extern PyTypeObject *LibRTVecs_U8TypeObj;

extern VecI64API Vec_I64API;
extern VecI32API Vec_I32API;
extern VecI16API Vec_I16API;
extern VecU8API Vec_U8API;
extern VecFloatAPI Vec_FloatAPI;
extern VecBoolAPI Vec_BoolAPI;

static inline int Vec_CheckFloatError(PyObject *o) {
    if (PyFloat_Check(o)) {
        PyErr_SetString(PyExc_TypeError, "integer argument expected, got float");
        return 1;
    }
    return 0;
}

// vec[i64] operations

static inline int VecI64_Check(PyObject *o) {
    return o->ob_type == &VecI64Type;
}

static inline PyObject *VecI64_BoxItem(int64_t x) {
    return PyLong_FromLongLong(x);
}

static inline int64_t VecI64_UnboxItem(PyObject *o) {
    if (Vec_CheckFloatError(o))
        return -1;
    return PyLong_AsLongLong(o);
}

static inline int VecI64_IsUnboxError(int64_t x) {
    return x == -1 && PyErr_Occurred();
}

PyObject *VecI64_Box(VecI64);
VecI64 VecI64_Append(VecI64, int64_t x);
VecI64 VecI64_Remove(VecI64, int64_t x);
VecI64PopResult VecI64_Pop(VecI64 v, Py_ssize_t index);

// vec[i32] operations

static inline int VecI32_Check(PyObject *o) {
    return o->ob_type == &VecI32Type;
}

static inline PyObject *VecI32_BoxItem(int32_t x) {
    return PyLong_FromLongLong(x);
}

static inline int32_t VecI32_UnboxItem(PyObject *o) {
    if (Vec_CheckFloatError(o))
        return -1;
    long x = PyLong_AsLong(o);
    if (x > INT32_MAX || x < INT32_MIN) {
        PyErr_SetString(PyExc_OverflowError, "Python int too large to convert to i32");
        return -1;
    }
    return x;
}

static inline int VecI32_IsUnboxError(int32_t x) {
    return x == -1 && PyErr_Occurred();
}

PyObject *VecI32_Box(VecI32);
VecI32 VecI32_Append(VecI32, int32_t x);
VecI32 VecI32_Remove(VecI32, int32_t x);
VecI32PopResult VecI32_Pop(VecI32 v, Py_ssize_t index);

// vec[i16] operations

static inline int VecI16_Check(PyObject *o) {
    return o->ob_type == &VecI16Type;
}

static inline PyObject *VecI16_BoxItem(int16_t x) {
    return PyLong_FromLongLong(x);
}

static inline int16_t VecI16_UnboxItem(PyObject *o) {
    if (Vec_CheckFloatError(o))
        return -1;
    long x = PyLong_AsLong(o);
    if (x >= 32768 || x < -32768) {
        PyErr_SetString(PyExc_OverflowError, "Python int too large to convert to i16");
        return -1;
    }
    return x;
}

static inline int VecI16_IsUnboxError(int16_t x) {
    return x == -1 && PyErr_Occurred();
}

PyObject *VecI16_Box(VecI16);
VecI16 VecI16_Append(VecI16, int16_t x);
VecI16 VecI16_Remove(VecI16, int16_t x);
VecI16PopResult VecI16_Pop(VecI16 v, Py_ssize_t index);

// vec[u8] operations

static inline int VecU8_Check(PyObject *o) {
    return o->ob_type == &VecU8Type;
}

static inline PyObject *VecU8_BoxItem(uint8_t x) {
    return PyLong_FromUnsignedLong(x);
}

static inline uint8_t VecU8_UnboxItem(PyObject *o) {
    if (Vec_CheckFloatError(o))
        return -1;
    unsigned long x = PyLong_AsUnsignedLong(o);
    if (x <= 255)
        return x;
    else if (x == (unsigned long)-1)
        return 239;
    else {
        PyErr_SetString(PyExc_OverflowError, "Python int too large to convert to u8");
        return 239;
    }
}

static inline int VecU8_IsUnboxError(uint8_t x) {
    return x == 239 && PyErr_Occurred();
}

PyObject *VecU8_Box(VecU8);
VecU8 VecU8_Append(VecU8, uint8_t x);
VecU8 VecU8_Remove(VecU8, uint8_t x);
VecU8PopResult VecU8_Pop(VecU8 v, Py_ssize_t index);

// vec[float] operations

static inline int VecFloat_Check(PyObject *o) {
    return o->ob_type == &VecFloatType;
}

static inline PyObject *VecFloat_BoxItem(double x) {
    return PyFloat_FromDouble(x);
}

static inline double VecFloat_UnboxItem(PyObject *o) {
    return PyFloat_AsDouble(o);
}

static inline int VecFloat_IsUnboxError(double x) {
    return x == -1.0 && PyErr_Occurred();
}

PyObject *VecFloat_Box(VecFloat);
VecFloat VecFloat_Append(VecFloat, double x);
VecFloat VecFloat_Remove(VecFloat, double x);
VecFloatPopResult VecFloat_Pop(VecFloat v, Py_ssize_t index);

// vec[bool] operations

static inline int VecBool_Check(PyObject *o) {
    return o->ob_type == &VecBoolType;
}

static inline PyObject *VecBool_BoxItem(char x) {
    if (x == 1) {
        Py_INCREF(Py_True);
        return Py_True;
    } else {
        Py_INCREF(Py_False);
        return Py_False;
    }
}

static inline char VecBool_UnboxItem(PyObject *o) {
    if (o == Py_False) {
        return 0;
    } else if (o == Py_True) {
        return 1;
    } else {
        PyErr_SetString(PyExc_TypeError, "bool value expected");
        return 2;
    }
}

static inline int VecBool_IsUnboxError(char x) {
    return x == 2;
}

PyObject *VecBool_Box(VecBool);
VecBool VecBool_Append(VecBool, char x);
VecBool VecBool_Remove(VecBool, char x);
VecBoolPopResult VecBool_Pop(VecBool v, Py_ssize_t index);

// Misc helpers

PyObject *Vec_TypeToStr(size_t item_type, size_t depth);
PyObject *Vec_GenericRepr(PyObject *vec, size_t item_type, size_t depth, int verbose);
PyObject *Vec_GenericRichcompare(Py_ssize_t *len, PyObject **items,
                                  Py_ssize_t *other_len, PyObject **other_items,
                                  int op);
int Vec_GenericRemove(Py_ssize_t *len, PyObject **items, PyObject *item);
PyObject *Vec_GenericPopWrapper(Py_ssize_t *len, PyObject **items, PyObject *args);
PyObject *Vec_GenericPop(Py_ssize_t *len, PyObject **items, Py_ssize_t index);

#endif  // MYPYC_EXPERIMENTAL

#endif  // VEC_H_INCL
