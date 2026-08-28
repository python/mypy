#include "bytearray_extra_ops.h"

PyObject *CPyByteArray_New(void) {
    return PyByteArray_FromStringAndSize(NULL, 0);
}

PyObject *CPyByteArray_FromBytesSlice(PyObject *obj, CPyTagged start, CPyTagged end) {
    if (PyBytes_CheckExact(obj) && CPyTagged_CheckShort(start) && CPyTagged_CheckShort(end)) {
        Py_ssize_t startn = CPyTagged_ShortAsSsize_t(start);
        Py_ssize_t endn = CPyTagged_ShortAsSsize_t(end);
        if (0 <= startn && startn <= endn && endn <= PyBytes_GET_SIZE(obj)) {
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
