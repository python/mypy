// Float primitive operations
//
// These are registered in mypyc.primitives.float_ops.

#include <Python.h>
#include "CPy.h"


static double CPy_DomainError() {
    PyErr_SetString(PyExc_ValueError, "math domain error");
    return CPY_FLOAT_ERROR;
}

double CPyFloat_FromTagged(CPyTagged x) {
    if (CPyTagged_CheckShort(x)) {
        return CPyTagged_ShortAsSsize_t(x);
    }
    double result = PyFloat_AsDouble(CPyTagged_LongAsObject(x));
    if (unlikely(result == -1.0) && PyErr_Occurred()) {
        return CPY_FLOAT_ERROR;
    }
    return result;
}

double CPyFloat_Abs(double x) {
    return x >= 0.0 ? x : -x;
}

double CPyFloat_Sin(double x) {
    double v = sin(x);
    if (unlikely(isnan(v)) && !isnan(x)) {
        return CPy_DomainError();
    }
    return v;
}

double CPyFloat_Cos(double x) {
    double v = cos(x);
    if (unlikely(isnan(v)) && !isnan(x)) {
        return CPy_DomainError();
    }
    return v;
}

double CPyFloat_Sqrt(double x) {
    if (x < 0.0) {
        return CPy_DomainError();
    }
    return sqrt(x);
}

bool CPyFloat_IsInf(double x) {
    return isinf(x) != 0;
}

bool CPyFloat_IsNaN(double x) {
    return isnan(x) != 0;
}
