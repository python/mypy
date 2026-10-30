// Generic primitive operations
//
// These are registered in mypyc.primitives.generic_ops.

#include <Python.h>
#include "CPy.h"

CPyTagged CPyObject_Hash(PyObject *o) {
    Py_hash_t h = PyObject_Hash(o);
    if (h == -1) {
        return CPY_INT_TAG;
    } else {
        // This is tragically annoying. The range of hash values in
        // 64-bit python covers 64-bits, and our short integers only
        // cover 63. This means that half the time we are boxing the
        // result for basically no good reason. To add insult to
        // injury it is probably about to be immediately unboxed by a
        // tp_hash wrapper.
        return CPyTagged_FromSsize_t(h);
    }
}

PyObject *CPyObject_GetAttr3(PyObject *v, PyObject *name, PyObject *defl)
{
    PyObject *result = PyObject_GetAttr(v, name);
    if (!result && PyErr_ExceptionMatches(PyExc_AttributeError)) {
        PyErr_Clear();
        Py_INCREF(defl);
        result = defl;
    }
    return result;
}

PyObject *CPyIter_Next(PyObject *iter)
{
    return (*Py_TYPE(iter)->tp_iternext)(iter);
}

PyObject *CPyNumber_Power(PyObject *base, PyObject *index)
{
    return PyNumber_Power(base, index, Py_None);
}

PyObject *CPyNumber_InPlacePower(PyObject *base, PyObject *index)
{
    return PyNumber_InPlacePower(base, index, Py_None);
}

PyObject *CPyObject_GetSlice(PyObject *obj, CPyTagged start, CPyTagged end) {
    PyObject *start_obj = start == CPY_INT_TAG ? Py_NewRef(Py_None) : CPyTagged_AsObject(start);
    PyObject *end_obj = end == CPY_INT_TAG ? Py_NewRef(Py_None) : CPyTagged_AsObject(end);
    if (unlikely(start_obj == NULL || end_obj == NULL)) {
        Py_XDECREF(start_obj);
        Py_XDECREF(end_obj);
        return NULL;
    }
    PyObject *slice = PySlice_New(start_obj, end_obj, NULL);
    Py_DECREF(start_obj);
    Py_DECREF(end_obj);
    if (unlikely(slice == NULL)) {
        return NULL;
    }
    PyObject *result = PyObject_GetItem(obj, slice);
    Py_DECREF(slice);
    return result;
}

typedef PyObject *(*SetupFunction)(PyObject *);

PyObject *CPy_SetupObject(PyObject *type) {
    PyTypeObject *tp = (PyTypeObject *)type;
    PyMethodDef *def = NULL;
    for(; tp; tp = tp->tp_base) {
        def = tp->tp_methods;
        if (!def || !def->ml_name) {
            continue;
        }

        if (!strcmp(def->ml_name, "__internal_mypyc_setup")) {
            return ((SetupFunction)(void(*)(void))def->ml_meth)(type);
        }
    }

    PyErr_SetString(PyExc_RuntimeError, "Internal mypyc error: Unable to find object setup function");
    return NULL;
}

typedef PyObject *(*CPyFastcallWrapper)(PyObject *, PyObject *const *, size_t, PyObject *);

// Call the wrapper function of a native function that uses the vectorcall convention,
// with the positional arguments in a tuple and the keyword arguments in a dict (or NULL).
// If takes_self is set, the first positional argument is passed to the wrapper as self.
PyObject *CPy_CallFastcallWrapper(void *wrapper_ptr, int takes_self, PyObject *args,
                                  PyObject *kwargs) {
    CPyFastcallWrapper wrapper = (CPyFastcallWrapper)wrapper_ptr;
    PyObject *const *items = &PyTuple_GET_ITEM(args, 0);
    Py_ssize_t nargs = PyTuple_GET_SIZE(args);
    PyObject *self = NULL;
    if (takes_self) {
        if (nargs == 0) {
            PyErr_SetString(PyExc_TypeError, "missing the self argument");
            return NULL;
        }
        self = items[0];
        items++;
        nargs--;
    }
    if (kwargs == NULL || PyDict_GET_SIZE(kwargs) == 0) {
        return wrapper(self, items, (size_t)nargs, NULL);
    }

    // The values of the keyword arguments go after the positional arguments, and their
    // names in a tuple.
    Py_ssize_t nkwargs = PyDict_GET_SIZE(kwargs);
    PyObject **stack = PyMem_Malloc((nargs + nkwargs) * sizeof(PyObject *));
    if (stack == NULL) {
        return PyErr_NoMemory();
    }
    PyObject *kwnames = PyTuple_New(nkwargs);
    if (kwnames == NULL) {
        PyMem_Free(stack);
        return NULL;
    }
    memcpy(stack, items, nargs * sizeof(PyObject *));
    Py_ssize_t pos = 0;
    Py_ssize_t i = 0;
    PyObject *key, *value;
    while (PyDict_Next(kwargs, &pos, &key, &value)) {
        if (!PyUnicode_Check(key)) {
            PyErr_SetString(PyExc_TypeError, "keywords must be strings");
            Py_DECREF(kwnames);
            PyMem_Free(stack);
            return NULL;
        }
        Py_INCREF(key);
        PyTuple_SET_ITEM(kwnames, i, key);
        stack[nargs + i] = value;
        i++;
    }
    PyObject *result = wrapper(self, stack, (size_t)nargs, kwnames);
    Py_DECREF(kwnames);
    PyMem_Free(stack);
    return result;
}

// Call the wrapper function of __init__ or __new__ of a native class, with the positional
// arguments in a tuple and the keyword arguments in a dict (or NULL). These wrappers take
// the first argument (self or cls) separately.
PyObject *CPy_CallLegacyWrapper(void *wrapper_ptr, PyObject *args, PyObject *kwargs) {
    PyCFunctionWithKeywords wrapper = (PyCFunctionWithKeywords)wrapper_ptr;
    Py_ssize_t nargs = PyTuple_GET_SIZE(args);
    if (nargs == 0) {
        PyErr_SetString(PyExc_TypeError, "missing the self argument");
        return NULL;
    }
    PyObject *rest = PyTuple_GetSlice(args, 1, nargs);
    if (rest == NULL) {
        return NULL;
    }
    PyObject *result = wrapper(PyTuple_GET_ITEM(args, 0), rest, kwargs);
    Py_DECREF(rest);
    return result;
}
