// Float primitive operations
//
// These are registered in mypyc.primitives.float_ops.

#include <Python.h>
#include "CPy.h"


static double CPy_DomainError() {
    PyErr_SetString(PyExc_ValueError, "math domain error");
    return CPY_FLOAT_ERROR;
}

static double CPy_MathRangeError() {
    PyErr_SetString(PyExc_OverflowError, "math range error");
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

double CPyFloat_Tan(double x) {
    if (unlikely(isinf(x))) {
        return CPy_DomainError();
    }
    return tan(x);
}

double CPyFloat_Sqrt(double x) {
    if (x < 0.0) {
        return CPy_DomainError();
    }
    return sqrt(x);
}

double CPyFloat_Exp(double x) {
    double v = exp(x);
    if (unlikely(v == INFINITY) && x != INFINITY) {
        return CPy_MathRangeError();
    }
    return v;
}

double CPyFloat_Log(double x) {
    if (x <= 0.0) {
        return CPy_DomainError();
    }
    return log(x);
}

CPyTagged CPyFloat_Floor(double x) {
    double v = floor(x);
    return CPyTagged_FromFloat(v);
}

CPyTagged CPyFloat_Ceil(double x) {
    double v = ceil(x);
    return CPyTagged_FromFloat(v);
}

bool CPyFloat_IsInf(double x) {
    return isinf(x) != 0;
}

bool CPyFloat_IsNaN(double x) {
    return isnan(x) != 0;
}

// From CPython 3.10.0, Objects/floatobject.c
static void
_float_div_mod(double vx, double wx, double *floordiv, double *mod)
{
    double div;
    *mod = fmod(vx, wx);
    /* fmod is typically exact, so vx-mod is *mathematically* an
       exact multiple of wx.  But this is fp arithmetic, and fp
       vx - mod is an approximation; the result is that div may
       not be an exact integral value after the division, although
       it will always be very close to one.
    */
    div = (vx - *mod) / wx;
    if (*mod) {
        /* ensure the remainder has the same sign as the denominator */
        if ((wx < 0) != (*mod < 0)) {
            *mod += wx;
            div -= 1.0;
        }
    }
    else {
        /* the remainder is zero, and in the presence of signed zeroes
           fmod returns different results across platforms; ensure
           it has the same sign as the denominator. */
        *mod = copysign(0.0, wx);
    }
    /* snap quotient to nearest integral value */
    if (div) {
        *floordiv = floor(div);
        if (div - *floordiv > 0.5) {
            *floordiv += 1.0;
        }
    }
    else {
        /* div is zero - get the same sign as the true quotient */
        *floordiv = copysign(0.0, vx / wx); /* zero w/ sign of vx/wx */
    }
}

double CPyFloat_FloorDivide(double x, double y) {
    double mod, floordiv;
    if (y == 0) {
        PyErr_SetString(PyExc_ZeroDivisionError, "float floor division by zero");
        return CPY_FLOAT_ERROR;
    }
    _float_div_mod(x, y, &floordiv, &mod);
    return floordiv;
}
