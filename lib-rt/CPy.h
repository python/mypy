#ifndef CPY_CPY_H
#define CPY_CPY_H

#include <stdbool.h>
#include <Python.h>
#include <frameobject.h>

#ifdef __cplusplus
extern "C" {
#endif

// Naming conventions:
//
// Tagged: tagged int
// Long: tagged long int (pointer)
// Short: tagged short int (unboxed)
// LongLong: C long long (64 bit)
// Int: C int
// Object: CPython object (PyObject *)

typedef unsigned long long CPyTagged;
typedef long long CPySignedInt;
typedef PyObject CPyModule;

#define CPY_INT_TAG 1

typedef void (*CPyVTableItem)(void);

static void CPyDebug_Print(const char *msg) {
    printf("%s\n", msg);
    fflush(stdout);
}

// Get attribute value using vtable (may return an undefined value)
#define CPY_GET_ATTR(obj, vtable_index, object_type, attr_type) \
    ((attr_type (*)(object_type *))((object_type *)obj)->vtable[vtable_index])((object_type *)obj)

// Set attribute value using vtable
#define CPY_SET_ATTR(obj, vtable_index, value, object_type, attr_type) \
    ((bool (*)(object_type *, attr_type))((object_type *)obj)->vtable[vtable_index])( \
        (object_type *)obj, value)

static void CPyError_OutOfMemory(void) {
    fprintf(stderr, "fatal: out of memory\n");
    fflush(stderr);
    abort();
}

inline int CPyTagged_CheckLong(CPyTagged x) {
    return x & CPY_INT_TAG;
}

inline int CPyTagged_CheckShort(CPyTagged x) {
    return !CPyTagged_CheckLong(x);
}

inline CPyTagged CPyTagged_ShortFromInt(int x) {
    return x << 1;
}

inline CPyTagged CPyTagged_ShortFromLongLong(long long x) {
    return x << 1;
}

inline long long CPyTagged_ShortAsLongLong(CPyTagged x) {
    // NOTE: Assume that we sign extend.
    return (CPySignedInt)x >> 1;
}

inline PyObject *CPyTagged_LongAsObject(CPyTagged x) {
    // NOTE: Assume target is not a short int.
    return (PyObject *)(x & ~CPY_INT_TAG);
}

static CPyTagged CPyTagged_FromObject(PyObject *object) {
    int overflow;
    // TODO: This may call __int__ and raise exceptions.
    PY_LONG_LONG value = PyLong_AsLongLongAndOverflow(object, &overflow);
    // We use a Python object if the value shifted left by 1 is too
    // large for long long.  The latter check is micro-optimized where
    // the common case where long long is small enough.
    if (overflow != 0 || (((unsigned long long)value >= (1LL << 62)) &&
                          (value >= 0 || value < -(1LL << 62)))) {
        Py_INCREF(object);
        return ((CPyTagged)object) | CPY_INT_TAG;
    } else {
        return value << 1;
    }
}

static CPyTagged CPyTagged_StealFromObject(PyObject *object) {
    int overflow;
    // TODO: This may call __int__ and raise exceptions.
    PY_LONG_LONG value = PyLong_AsLongLongAndOverflow(object, &overflow);
    // We use a Python object if the value shifted left by 1 is too
    // large for long long.  The latter check is micro-optimized where
    // the common case where long long is small enough.
    if (overflow != 0 || (((unsigned long long)value >= (1LL << 62)) &&
                          (value >= 0 || value < -(1LL << 62)))) {
        return ((CPyTagged)object) | CPY_INT_TAG;
    } else {
        Py_DECREF(object);
        return value << 1;
    }
}

static CPyTagged CPyTagged_BorrowFromObject(PyObject *object) {
    int overflow;
    // TODO: This may call __int__ and raise exceptions.
    PY_LONG_LONG value = PyLong_AsLongLongAndOverflow(object, &overflow);
    // We use a Python object if the value shifted left by 1 is too
    // large for long long.  The latter check is micro-optimized where
    // the common case where long long is small enough.
    if (overflow != 0 || (((unsigned long long)value >= (1LL << 62)) &&
                          (value >= 0 || value < -(1LL << 62)))) {
        return ((CPyTagged)object) | CPY_INT_TAG;
    } else {
        return value << 1;
    }
}

static PyObject *CPyTagged_AsObject(CPyTagged x) {
    PyObject *value;
    if (CPyTagged_CheckLong(x)) {
        value = CPyTagged_LongAsObject(x);
        Py_INCREF(value);
    } else {
        value = PyLong_FromLongLong(CPyTagged_ShortAsLongLong(x));
        if (value == NULL) {
            CPyError_OutOfMemory();
        }
    }
    return value;
}

static PyObject *CPyTagged_StealAsObject(CPyTagged x) {
    PyObject *value;
    if (CPyTagged_CheckLong(x)) {
        value = CPyTagged_LongAsObject(x);
    } else {
        value = PyLong_FromLongLong(CPyTagged_ShortAsLongLong(x));
        if (value == NULL) {
            CPyError_OutOfMemory();
        }
    }
    return value;
}

static long long CPyTagged_AsLongLong(CPyTagged x) {
    if (CPyTagged_CheckShort(x)) {
        return CPyTagged_ShortAsLongLong(x);
    } else {
        long long result = PyLong_AsLongLong(CPyTagged_LongAsObject(x));
        if (PyErr_Occurred()) {
            return -1;
        }
        return result;
    }
}

inline void CPyTagged_IncRef(CPyTagged x) {
    if (CPyTagged_CheckLong(x)) {
        Py_INCREF(CPyTagged_LongAsObject(x));
    }
}

inline void CPyTagged_DecRef(CPyTagged x) {
    if (CPyTagged_CheckLong(x)) {
        Py_DECREF(CPyTagged_LongAsObject(x));
    }
}

inline bool CPyTagged_IsAddOverflow(CPyTagged sum, CPyTagged left, CPyTagged right) {
    // This check was copied from some of my old code I believe that it works :-)
    return (long long)(sum ^ left) < 0 && (long long)(sum ^ right) < 0;
}

static CPyTagged CPyTagged_Add(CPyTagged left, CPyTagged right) {
    // TODO: Use clang/gcc extension __builtin_saddll_overflow instead.
    if (CPyTagged_CheckShort(left) && CPyTagged_CheckShort(right)) {
        CPyTagged sum = left + right;
        if (!CPyTagged_IsAddOverflow(sum, left, right)) {
            return sum;
        }
    }
    PyObject *left_obj = CPyTagged_AsObject(left);
    PyObject *right_obj = CPyTagged_AsObject(right);
    PyObject *result = PyNumber_Add(left_obj, right_obj);
    if (result == NULL) {
        CPyError_OutOfMemory();
    }
    Py_DECREF(left_obj);
    Py_DECREF(right_obj);
    return CPyTagged_StealFromObject(result);
}

inline bool CPyTagged_IsSubtractOverflow(CPyTagged diff, CPyTagged left, CPyTagged right) {
    // This check was copied from some of my old code I believe that it works :-)
    return (long long)(diff ^ left) < 0 && (long long)(diff ^ right) >= 0;
}

static CPyTagged CPyTagged_Subtract(CPyTagged left, CPyTagged right) {
    // TODO: Use clang/gcc extension __builtin_saddll_overflow instead.
    if (CPyTagged_CheckShort(left) && CPyTagged_CheckShort(right)) {
        CPyTagged diff = left - right;
        if (!CPyTagged_IsSubtractOverflow(diff, left, right)) {
            return diff;
        }
    }
    PyObject *left_obj = CPyTagged_AsObject(left);
    PyObject *right_obj = CPyTagged_AsObject(right);
    PyObject *result = PyNumber_Subtract(left_obj, right_obj);
    if (result == NULL) {
        CPyError_OutOfMemory();
    }
    Py_DECREF(left_obj);
    Py_DECREF(right_obj);
    return CPyTagged_StealFromObject(result);
}

inline bool CPyTagged_IsMultiplyOverflow(CPyTagged left, CPyTagged right) {
    // This is conservative -- return false only in a small number of all non-overflow cases
    return left >= (1U << 31) || right >= (1U << 31);
}

static CPyTagged CPyTagged_Multiply(CPyTagged left, CPyTagged right) {
    // TODO: Consider using some clang/gcc extension
    if (CPyTagged_CheckShort(left) && CPyTagged_CheckShort(right)) {
        if (!CPyTagged_IsMultiplyOverflow(left, right)) {
            return left * CPyTagged_ShortAsLongLong(right);
        }
    }
    PyObject *left_obj = CPyTagged_AsObject(left);
    PyObject *right_obj = CPyTagged_AsObject(right);
    PyObject *result = PyNumber_Multiply(left_obj, right_obj);
    if (result == NULL) {
        CPyError_OutOfMemory();
    }
    Py_DECREF(left_obj);
    Py_DECREF(right_obj);
    return CPyTagged_StealFromObject(result);
}

inline bool CPyTagged_MaybeFloorDivideOverflow(CPyTagged left, CPyTagged right) {
    return right == -0x8000000000000000ULL || left == -0x8000000000000000ULL;
}

static CPyTagged CPyTagged_FloorDivide(CPyTagged left, CPyTagged right) {
    if (CPyTagged_CheckShort(left) && CPyTagged_CheckShort(right)
        && !CPyTagged_MaybeFloorDivideOverflow(left, right)) {
        if (right == 0)
            abort();
        CPySignedInt result = ((CPySignedInt)left / CPyTagged_ShortAsLongLong(right)) & ~1;
        if (((CPySignedInt)left < 0) != (((CPySignedInt)right) < 0)) {
            if (result / 2 * right != left) {
                // Round down
                result -= 2;
            }
        }
        return result;
    }
    PyObject *left_obj = CPyTagged_AsObject(left);
    PyObject *right_obj = CPyTagged_AsObject(right);
    PyObject *result = PyNumber_FloorDivide(left_obj, right_obj);
    if (result == NULL) {
        CPyError_OutOfMemory();
    }
    Py_DECREF(left_obj);
    Py_DECREF(right_obj);
    return CPyTagged_StealFromObject(result);
}

inline bool CPyTagged_MaybeRemainderOverflow(CPyTagged left, CPyTagged right) {
    return right == -0x8000000000000000ULL || left == -0x8000000000000000ULL;
}

static CPyTagged CPyTagged_Remainder(CPyTagged left, CPyTagged right) {
    if (CPyTagged_CheckShort(left) && CPyTagged_CheckShort(right)
        && !CPyTagged_MaybeRemainderOverflow(left, right)) {
        CPySignedInt result = (CPySignedInt)left % (CPySignedInt)right;
        if (((CPySignedInt)right < 0) != ((CPySignedInt)left < 0) && result != 0) {
            result += right;
        }
        return result;
    }
    PyObject *left_obj = CPyTagged_AsObject(left);
    PyObject *right_obj = CPyTagged_AsObject(right);
    PyObject *result = PyNumber_Remainder(left_obj, right_obj);
    if (result == NULL) {
        CPyError_OutOfMemory();
    }
    Py_DECREF(left_obj);
    Py_DECREF(right_obj);
    return CPyTagged_StealFromObject(result);
}

static bool CPyTagged_IsEq_(CPyTagged left, CPyTagged right) {
    if (CPyTagged_CheckShort(right)) {
        return false;
    } else {
        int result = PyObject_RichCompareBool(CPyTagged_LongAsObject(left),
                                              CPyTagged_LongAsObject(right), Py_EQ);
        if (result == -1) {
            CPyError_OutOfMemory();
        }
        return result;
    }
}

static inline bool CPyTagged_IsEq(CPyTagged left, CPyTagged right) {
    if (CPyTagged_CheckShort(left)) {
        return left == right;
    } else {
        return CPyTagged_IsEq_(left, right);
    }
}

static inline bool CPyTagged_IsNe(CPyTagged left, CPyTagged right) {
    if (CPyTagged_CheckShort(left)) {
        return left != right;
    } else {
        return !CPyTagged_IsEq_(left, right);
    }
}

static bool CPyTagged_IsLt_(CPyTagged left, CPyTagged right) {
    PyObject *left_obj = CPyTagged_AsObject(left);
    PyObject *right_obj = CPyTagged_AsObject(right);
    int result = PyObject_RichCompareBool(left_obj, right_obj, Py_LT);
    Py_DECREF(left_obj);
    Py_DECREF(right_obj);
    if (result == -1) {
        CPyError_OutOfMemory();
    }
    return result;
}

static inline bool CPyTagged_IsLt(CPyTagged left, CPyTagged right) {
    if (CPyTagged_CheckShort(left) && CPyTagged_CheckShort(right)) {
        return (CPySignedInt)left < (CPySignedInt)right;
    } else {
        return CPyTagged_IsLt_(left, right);
    }
}

static inline bool CPyTagged_IsGe(CPyTagged left, CPyTagged right) {
    if (CPyTagged_CheckShort(left) && CPyTagged_CheckShort(right)) {
        return (CPySignedInt)left >= (CPySignedInt)right;
    } else {
        return !CPyTagged_IsLt_(left, right);
    }
}

static inline bool CPyTagged_IsGt(CPyTagged left, CPyTagged right) {
    if (CPyTagged_CheckShort(left) && CPyTagged_CheckShort(right)) {
        return (CPySignedInt)left > (CPySignedInt)right;
    } else {
        return CPyTagged_IsLt_(right, left);
    }
}

static inline bool CPyTagged_IsLe(CPyTagged left, CPyTagged right) {
    if (CPyTagged_CheckShort(left) && CPyTagged_CheckShort(right)) {
        return (CPySignedInt)left <= (CPySignedInt)right;
    } else {
        return !CPyTagged_IsLt_(right, left);
    }
}

static PyObject *CPyList_GetItem(PyObject *list, CPyTagged index) {
    if (CPyTagged_CheckShort(index)) {
        long long n = CPyTagged_ShortAsLongLong(index);
        Py_ssize_t size = PyList_GET_SIZE(list);
        if (n >= 0) {
            if (n >= size) {
                PyErr_SetString(PyExc_IndexError, "list index out of range");
                return NULL;
            }
        } else {
            n += size;
            if (n < 0) {
                PyErr_SetString(PyExc_IndexError, "list index out of range");
                return NULL;
            }
        }
        PyObject *result = PyList_GET_ITEM(list, n);
        Py_INCREF(result);
        return result;
    } else {
        PyErr_SetString(PyExc_IndexError, "list index out of range");
        return NULL;
    }
}

static bool CPyList_SetItem(PyObject *list, CPyTagged index, PyObject *value) {
    if (CPyTagged_CheckShort(index)) {
        long long n = CPyTagged_ShortAsLongLong(index);
        Py_ssize_t size = PyList_GET_SIZE(list);
        if (n >= 0) {
            if (n >= size) {
                PyErr_SetString(PyExc_IndexError, "list assignment index out of range");
                return false;
            }
        } else {
            n += size;
            if (n < 0) {
                PyErr_SetString(PyExc_IndexError, "list assignment index out of range");
                return false;
            }
        }
        Py_INCREF(value); // TODO: Move this outside the function to allow optimizing it away
        PyList_SET_ITEM(list, n, value);
        return true;
    } else {
        PyErr_SetString(PyExc_IndexError, "list assignment index out of range");
        return false;
    }
}

static PyObject *CPySequenceTuple_GetItem(PyObject *tuple, CPyTagged index) {
    if (CPyTagged_CheckShort(index)) {
        long long n = CPyTagged_ShortAsLongLong(index);
        Py_ssize_t size = PyTuple_GET_SIZE(tuple);
        if (n >= 0) {
            if (n >= size) {
                PyErr_SetString(PyExc_IndexError, "tuple index out of range");
                return NULL;
            }
        } else {
            n += size;
            if (n < 0) {
                PyErr_SetString(PyExc_IndexError, "tuple index out of range");
                return NULL;
            }
        }
        PyObject *result = PyTuple_GET_ITEM(tuple, n);
        Py_INCREF(result);
        return result;
    } else {
        PyErr_SetString(PyExc_IndexError, "tuple index out of range");
        return NULL;
    }
}

static inline PyObject *CPyObject_GetAttrString(PyObject *obj, const char *attr_name) {
    PyObject *result = PyObject_GetAttrString(obj, attr_name);
    if (result == NULL) {
        abort();
    }
    return result;
}

static PyCodeObject *CPy_CreateCodeObject(const char *filename, const char *funcname, int line) {
    PyObject *filename_obj = PyUnicode_FromString(filename);
    PyObject *funcname_obj = PyUnicode_FromString(funcname);
    PyObject *empty_bytes = PyBytes_FromStringAndSize("", 0);
    PyObject *empty_tuple = PyTuple_New(0);
    PyCodeObject *code_obj = NULL;
    if (filename_obj == NULL || funcname_obj == NULL || empty_bytes == NULL
        || empty_tuple == NULL) {
        goto Error;
    }
    code_obj = PyCode_New(0, 0, 0, 0, 0,
                          empty_bytes,
                          empty_tuple,
                          empty_tuple,
                          empty_tuple,
                          empty_tuple,
                          empty_tuple,
                          filename_obj,
                          funcname_obj,
                          line,
                          empty_bytes);
  Error:
    Py_XDECREF(empty_bytes);
    Py_XDECREF(empty_tuple);
    Py_XDECREF(filename_obj);
    Py_XDECREF(funcname_obj);
    return code_obj;
}

static void CPy_AddTraceback(const char *filename, const char *funcname, int line,
                             PyObject *globals) {
    PyCodeObject *code_obj = CPy_CreateCodeObject(filename, funcname, line);
    if (code_obj == NULL) {
        return;
    }
    PyThreadState *thread_state = PyThreadState_GET();
    PyFrameObject *frame_obj = PyFrame_New(thread_state, code_obj, globals, 0);
    if (frame_obj == NULL) {
        Py_DECREF(code_obj);
        return;
    }
    frame_obj->f_lineno = line;
    PyTraceBack_Here(frame_obj);
    Py_DECREF(code_obj);
    Py_DECREF(frame_obj);
}

#ifdef __cplusplus
}
#endif

#endif // CPY_CPY_H
