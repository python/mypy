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

// On free-threaded builds, the item array of a bytearray may be resized or freed
// concurrently, so it must only be accessed in a critical section. On other builds,
// the critical section macros don't do anything.

CPyTagged CPyByteArray_GetItem(PyObject *obj, CPyTagged index) {
    if (likely(PyByteArray_CheckExact(obj) && CPyTagged_CheckShort(index))) {
        Py_ssize_t n = CPyTagged_ShortAsSsize_t(index);
        CPyTagged result = CPY_INT_TAG;
        Py_BEGIN_CRITICAL_SECTION(obj);
        Py_ssize_t size = PyByteArray_GET_SIZE(obj);
        if (n < 0) {
            n += size;
        }
        if (n < 0 || n >= size) {
            PyErr_SetString(PyExc_IndexError, "bytearray index out of range");
        } else {
            result = (CPyTagged)(unsigned char)PyByteArray_AS_STRING(obj)[n] << 1;
        }
        Py_END_CRITICAL_SECTION();
        return result;
    }

    // Generic path for subclasses and large indexes
    PyObject *index_obj = CPyTagged_AsObject(index);
    if (index_obj == NULL) {
        return CPY_INT_TAG;
    }
    PyObject *item = PyObject_GetItem(obj, index_obj);
    Py_DECREF(index_obj);
    if (item == NULL) {
        return CPY_INT_TAG;
    }
    if (unlikely(!PyLong_Check(item))) {
        CPy_TypeError("int", item);
        Py_DECREF(item);
        return CPY_INT_TAG;
    }
    return CPyTagged_StealFromObject(item);
}

bool CPyByteArray_SetItem(PyObject *obj, CPyTagged index, CPyTagged value) {
    if (likely(PyByteArray_CheckExact(obj) && CPyTagged_CheckShort(index))) {
        Py_ssize_t n = CPyTagged_ShortAsSsize_t(index);
        // Like CPython, check the value before the index
        Py_ssize_t v = CPyTagged_CheckShort(value) ? CPyTagged_ShortAsSsize_t(value) : -1;
        if (v < 0 || v > 255) {
            PyErr_SetString(PyExc_ValueError, "byte must be in range(0, 256)");
            return false;
        }
        bool ok = false;
        Py_BEGIN_CRITICAL_SECTION(obj);
        Py_ssize_t size = PyByteArray_GET_SIZE(obj);
        if (n < 0) {
            n += size;
        }
        if (n < 0 || n >= size) {
            PyErr_SetString(PyExc_IndexError, "bytearray index out of range");
        } else {
            PyByteArray_AS_STRING(obj)[n] = (char)v;
            ok = true;
        }
        Py_END_CRITICAL_SECTION();
        return ok;
    }

    // Generic path for subclasses and large indexes
    PyObject *index_obj = CPyTagged_AsObject(index);
    if (index_obj == NULL) {
        return false;
    }
    PyObject *value_obj = CPyTagged_AsObject(value);
    if (value_obj == NULL) {
        Py_DECREF(index_obj);
        return false;
    }
    int res = PyObject_SetItem(obj, index_obj, value_obj);
    Py_DECREF(index_obj);
    Py_DECREF(value_obj);
    return res >= 0;
}

PyObject *CPyByteArray_GetSlice(PyObject *obj, CPyTagged start, CPyTagged end) {
    if (likely(PyByteArray_CheckExact(obj)
               && CPyTagged_CheckShort(start) && CPyTagged_CheckShort(end))) {
        Py_ssize_t startn = CPyTagged_ShortAsSsize_t(start);
        Py_ssize_t endn = CPyTagged_ShortAsSsize_t(end);
        PyObject *result;
        Py_BEGIN_CRITICAL_SECTION(obj);
        Py_ssize_t size = PyByteArray_GET_SIZE(obj);
        if (startn < 0) {
            startn += size;
            if (startn < 0) {
                startn = 0;
            }
        } else if (startn > size) {
            startn = size;
        }
        if (endn < 0) {
            endn += size;
            if (endn < 0) {
                endn = 0;
            }
        } else if (endn > size) {
            endn = size;
        }
        Py_ssize_t len = endn > startn ? endn - startn : 0;
        result = PyByteArray_FromStringAndSize(PyByteArray_AS_STRING(obj) + startn, len);
        Py_END_CRITICAL_SECTION();
        return result;
    }

    // Generic path for subclasses and large indexes
    PyObject *result = CPyObject_GetSlice(obj, start, end);
    if (result != NULL && unlikely(!PyByteArray_Check(result))) {
        // A subclass may override __getitem__ to return anything
        CPy_TypeError("bytearray", result);
        Py_DECREF(result);
        return NULL;
    }
    return result;
}
