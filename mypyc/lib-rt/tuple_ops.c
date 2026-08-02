// Tuple primitive operations
//
// These are registered in mypyc.primitives.tuple_ops.

#include <Python.h>
#include "CPy.h"

PyObject *CPySequenceTuple_GetSlice(PyObject *obj, CPyTagged start, CPyTagged end) {
    if (likely(PyTuple_CheckExact(obj)
               && CPyTagged_CheckShort(start) && CPyTagged_CheckShort(end))) {
        Py_ssize_t startn = CPyTagged_ShortAsSsize_t(start);
        Py_ssize_t endn = CPyTagged_ShortAsSsize_t(end);
        if (startn < 0) {
            startn += PyTuple_GET_SIZE(obj);
        }
        if (endn < 0) {
            endn += PyTuple_GET_SIZE(obj);
        }
        return PyTuple_GetSlice(obj, startn, endn);
    }
    return CPyObject_GetSlice(obj, start, end);
}
