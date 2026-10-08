#include "bytearray_extra_ops.h"

PyObject *CPyByteArray_New(void) {
    return PyByteArray_FromStringAndSize(NULL, 0);
}

PyObject *CPyByteArray_FromBytesSlice(PyObject *obj, CPyTagged start, CPyTagged end) {
    if (PyBytes_CheckExact(obj)
            && (start == CPY_INT_TAG || CPyTagged_CheckShort(start))
            && (end == CPY_INT_TAG || CPyTagged_CheckShort(end))) {
        Py_ssize_t size = PyBytes_GET_SIZE(obj);
        Py_ssize_t startn = start == CPY_INT_TAG ? 0 : CPyTagged_ShortAsSsize_t(start);
        Py_ssize_t endn = end == CPY_INT_TAG ? size : CPyTagged_ShortAsSsize_t(end);
        if (startn < 0) {
            startn += size;
        }
        if (endn < 0) {
            endn += size;
        }
        if (0 <= startn && startn <= endn && endn <= size) {
            return PyByteArray_FromStringAndSize(PyBytes_AS_STRING(obj) + startn, endn - startn);
        }
    }

    // Preserve general slice semantics, including bytes subclass overrides.
    PyObject *slice = CPyObject_GetSlice(obj, start, end);
    if (slice == NULL) {
        return NULL;
    }
    PyObject *result = PyByteArray_FromObject(slice);
    Py_DECREF(slice);
    return result;
}
