// Int primitive operations
//
// These are registered in mypyc.primitives.int_ops.

#include <Python.h>
#include "CPy.h"

CPyTagged CPyTagged_FromSsize_t(Py_ssize_t value) {
    // We use a Python object if the value shifted left by 1 is too
    // large for Py_ssize_t
    if (CPyTagged_TooBig(value)) {
        PyObject *object = PyLong_FromSsize_t(value);
        return ((CPyTagged)object) | CPY_INT_TAG;
    } else {
        return value << 1;
    }
}

CPyTagged CPyTagged_FromObject(PyObject *object) {
    int overflow;
    // The overflow check knows about CPyTagged's width
    Py_ssize_t value = CPyLong_AsSsize_tAndOverflow(object, &overflow);
    if (overflow != 0) {
        Py_INCREF(object);
        return ((CPyTagged)object) | CPY_INT_TAG;
    } else {
        return value << 1;
    }
}

CPyTagged CPyTagged_StealFromObject(PyObject *object) {
    int overflow;
    // The overflow check knows about CPyTagged's width
    Py_ssize_t value = CPyLong_AsSsize_tAndOverflow(object, &overflow);
    if (overflow != 0) {
        return ((CPyTagged)object) | CPY_INT_TAG;
    } else {
        Py_DECREF(object);
        return value << 1;
    }
}

CPyTagged CPyTagged_BorrowFromObject(PyObject *object) {
    int overflow;
    // The overflow check knows about CPyTagged's width
    Py_ssize_t value = CPyLong_AsSsize_tAndOverflow(object, &overflow);
    if (overflow != 0) {
        return ((CPyTagged)object) | CPY_INT_TAG;
    } else {
        return value << 1;
    }
}

PyObject *CPyTagged_AsObject(CPyTagged x) {
    PyObject *value;
    if (CPyTagged_CheckLong(x)) {
        value = CPyTagged_LongAsObject(x);
        Py_INCREF(value);
    } else {
        value = PyLong_FromSsize_t(CPyTagged_ShortAsSsize_t(x));
        if (value == NULL) {
            CPyError_OutOfMemory();
        }
    }
    return value;
}

PyObject *CPyTagged_StealAsObject(CPyTagged x) {
    PyObject *value;
    if (CPyTagged_CheckLong(x)) {
        value = CPyTagged_LongAsObject(x);
    } else {
        value = PyLong_FromSsize_t(CPyTagged_ShortAsSsize_t(x));
        if (value == NULL) {
            CPyError_OutOfMemory();
        }
    }
    return value;
}

Py_ssize_t CPyTagged_AsSsize_t(CPyTagged x) {
    if (CPyTagged_CheckShort(x)) {
        return CPyTagged_ShortAsSsize_t(x);
    } else {
        return PyLong_AsSsize_t(CPyTagged_LongAsObject(x));
    }
}

CPy_NOINLINE
void CPyTagged_IncRef(CPyTagged x) {
    if (CPyTagged_CheckLong(x)) {
        Py_INCREF(CPyTagged_LongAsObject(x));
    }
}

CPy_NOINLINE
void CPyTagged_DecRef(CPyTagged x) {
    if (CPyTagged_CheckLong(x)) {
        Py_DECREF(CPyTagged_LongAsObject(x));
    }
}

CPy_NOINLINE
void CPyTagged_XDecRef(CPyTagged x) {
    if (CPyTagged_CheckLong(x)) {
        Py_XDECREF(CPyTagged_LongAsObject(x));
    }
}

CPyTagged CPyTagged_Negate(CPyTagged num) {
    if (CPyTagged_CheckShort(num)
            && num != (CPyTagged) ((Py_ssize_t)1 << (CPY_INT_BITS - 1))) {
        // The only possibility of an overflow error happening when negating a short is if we
        // attempt to negate the most negative number.
        return -num;
    }
    PyObject *num_obj = CPyTagged_AsObject(num);
    PyObject *result = PyNumber_Negative(num_obj);
    if (result == NULL) {
        CPyError_OutOfMemory();
    }
    Py_DECREF(num_obj);
    return CPyTagged_StealFromObject(result);
}

CPyTagged CPyTagged_Add(CPyTagged left, CPyTagged right) {
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

CPyTagged CPyTagged_Subtract(CPyTagged left, CPyTagged right) {
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

CPyTagged CPyTagged_Multiply(CPyTagged left, CPyTagged right) {
    // TODO: Consider using some clang/gcc extension
    if (CPyTagged_CheckShort(left) && CPyTagged_CheckShort(right)) {
        if (!CPyTagged_IsMultiplyOverflow(left, right)) {
            return left * CPyTagged_ShortAsSsize_t(right);
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

CPyTagged CPyTagged_FloorDivide(CPyTagged left, CPyTagged right) {
    if (CPyTagged_CheckShort(left) && CPyTagged_CheckShort(right)
        && !CPyTagged_MaybeFloorDivideFault(left, right)) {
        Py_ssize_t result = ((Py_ssize_t)left / CPyTagged_ShortAsSsize_t(right)) & ~1;
        if (((Py_ssize_t)left < 0) != (((Py_ssize_t)right) < 0)) {
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
    Py_DECREF(left_obj);
    Py_DECREF(right_obj);
    // Handle exceptions honestly because it could be ZeroDivisionError
    if (result == NULL) {
        return CPY_INT_TAG;
    } else {
        return CPyTagged_StealFromObject(result);
    }
}

CPyTagged CPyTagged_Remainder(CPyTagged left, CPyTagged right) {
    if (CPyTagged_CheckShort(left) && CPyTagged_CheckShort(right)
        && !CPyTagged_MaybeRemainderFault(left, right)) {
        Py_ssize_t result = (Py_ssize_t)left % (Py_ssize_t)right;
        if (((Py_ssize_t)right < 0) != ((Py_ssize_t)left < 0) && result != 0) {
            result += right;
        }
        return result;
    }
    PyObject *left_obj = CPyTagged_AsObject(left);
    PyObject *right_obj = CPyTagged_AsObject(right);
    PyObject *result = PyNumber_Remainder(left_obj, right_obj);
    Py_DECREF(left_obj);
    Py_DECREF(right_obj);
    // Handle exceptions honestly because it could be ZeroDivisionError
    if (result == NULL) {
        return CPY_INT_TAG;
    } else {
        return CPyTagged_StealFromObject(result);
    }
}

bool CPyTagged_IsEq_(CPyTagged left, CPyTagged right) {
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

bool CPyTagged_IsLt_(CPyTagged left, CPyTagged right) {
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

PyObject *CPyLong_FromStrWithBase(PyObject *o, CPyTagged base) {
    Py_ssize_t base_size_t = CPyTagged_AsSsize_t(base);
    return PyLong_FromUnicodeObject(o, base_size_t);
}

PyObject *CPyLong_FromStr(PyObject *o) {
    CPyTagged base = CPyTagged_FromSsize_t(10);
    return CPyLong_FromStrWithBase(o, base);
}

PyObject *CPyLong_FromFloat(PyObject *o) {
    if (PyLong_Check(o)) {
        CPy_INCREF(o);
        return o;
    } else {
        return PyLong_FromDouble(PyFloat_AS_DOUBLE(o));
    }
}

PyObject *CPyBool_Str(bool b) {
    return PyObject_Str(b ? Py_True : Py_False);
}
