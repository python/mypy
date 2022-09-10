// Float primitive operations
//
// These are registered in mypyc.primitives.float_ops.

#include <Python.h>
#include "CPy.h"


double CPyFloat_Abs(double x) {
    return x >= 0.0 ? x : -x;
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

double CPyFloat_Sqrt(double x) {
    if (x < 0.0) {
        PyErr_SetString(PyExc_ValueError, "math domain error");
        return CPY_FLOAT_ERROR;
    }
    return sqrt(x);
}
