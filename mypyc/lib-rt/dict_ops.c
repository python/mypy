// Dict primitive operations
//
// These are registered in mypyc.primitives.dict_ops.

#include <Python.h>
#include "CPy.h"

// Dict subclasses like defaultdict override things in interesting
// ways, so we don't want to just directly use the dict methods. Not
// sure if it is actually worth doing all this stuff, but it saves
// some indirections.
PyObject *CPyDict_GetItem(PyObject *dict, PyObject *key) {
    if (PyDict_CheckExact(dict)) {
        PyObject *res = PyDict_GetItemWithError(dict, key);
        if (!res) {
            if (!PyErr_Occurred()) {
                PyErr_SetObject(PyExc_KeyError, key);
            }
        } else {
            Py_INCREF(res);
        }
        return res;
    } else {
        return PyObject_GetItem(dict, key);
    }
}

PyObject *CPyDict_Build(Py_ssize_t size, ...) {
    Py_ssize_t i;

    PyObject *res = _PyDict_NewPresized(size);
    if (res == NULL) {
        return NULL;
    }

    va_list args;
    va_start(args, size);

    for (i = 0; i < size; i++) {
        PyObject *key = va_arg(args, PyObject *);
        PyObject *value = va_arg(args, PyObject *);
        if (PyDict_SetItem(res, key, value)) {
            Py_DECREF(res);
            return NULL;
        }
    }

    va_end(args);
    return res;
}

PyObject *CPyDict_Get(PyObject *dict, PyObject *key, PyObject *fallback) {
    // We are dodgily assuming that get on a subclass doesn't have
    // different behavior.
    PyObject *res = PyDict_GetItemWithError(dict, key);
    if (!res) {
        if (PyErr_Occurred()) {
            return NULL;
        }
        res = fallback;
    }
    Py_INCREF(res);
    return res;
}

int CPyDict_SetItem(PyObject *dict, PyObject *key, PyObject *value) {
    if (PyDict_CheckExact(dict)) {
        return PyDict_SetItem(dict, key, value);
    } else {
        return PyObject_SetItem(dict, key, value);
    }
}

static int CPyDict_UpdateGeneral(PyObject *dict, PyObject *stuff) {
    _Py_IDENTIFIER(update);
    PyObject *res = _PyObject_CallMethodIdObjArgs(dict, &PyId_update, stuff, NULL);
    return CPy_ObjectToStatus(res);
}

int CPyDict_UpdateInDisplay(PyObject *dict, PyObject *stuff) {
    // from https://github.com/python/cpython/blob/55d035113dfb1bd90495c8571758f504ae8d4802/Python/ceval.c#L2710
    int ret = PyDict_Update(dict, stuff);
    if (ret < 0) {
        if (PyErr_ExceptionMatches(PyExc_AttributeError)) {
            PyErr_Format(PyExc_TypeError,
                    "'%.200s' object is not a mapping",
                    stuff->ob_type->tp_name);
        }
    }
    return ret;
}

int CPyDict_Update(PyObject *dict, PyObject *stuff) {
    if (PyDict_CheckExact(dict)) {
        return PyDict_Update(dict, stuff);
    } else {
        return CPyDict_UpdateGeneral(dict, stuff);
    }
}

int CPyDict_UpdateFromAny(PyObject *dict, PyObject *stuff) {
    if (PyDict_CheckExact(dict)) {
        // Argh this sucks
        _Py_IDENTIFIER(keys);
        if (PyDict_Check(stuff) || _PyObject_HasAttrId(stuff, &PyId_keys)) {
            return PyDict_Update(dict, stuff);
        } else {
            return PyDict_MergeFromSeq2(dict, stuff, 1);
        }
    } else {
        return CPyDict_UpdateGeneral(dict, stuff);
    }
}

PyObject *CPyDict_FromAny(PyObject *obj) {
    if (PyDict_Check(obj)) {
        return PyDict_Copy(obj);
    } else {
        int res;
        PyObject *dict = PyDict_New();
        if (!dict) {
            return NULL;
        }
        _Py_IDENTIFIER(keys);
        if (_PyObject_HasAttrId(obj, &PyId_keys)) {
            res = PyDict_Update(dict, obj);
        } else {
            res = PyDict_MergeFromSeq2(dict, obj, 1);
        }
        if (res < 0) {
            Py_DECREF(dict);
            return NULL;
        }
        return dict;
    }
}
