// Exception related primitive operations
//
// These are registered in mypyc.primitives.exc_ops.

#include <Python.h>
#include "CPy.h"

void CPy_Raise(PyObject *exc) {
    if (PyObject_IsInstance(exc, (PyObject *)&PyType_Type)) {
        PyObject *obj = PyObject_CallFunctionObjArgs(exc, NULL);
        if (!obj)
            return;
        PyErr_SetObject(exc, obj);
        Py_DECREF(obj);
    } else {
        PyErr_SetObject((PyObject *)Py_TYPE(exc), exc);
    }
}

void CPy_Reraise(void) {
    PyObject *p_type, *p_value, *p_traceback;
    PyErr_GetExcInfo(&p_type, &p_value, &p_traceback);
    PyErr_Restore(p_type, p_value, p_traceback);
}

void CPyErr_SetObjectAndTraceback(PyObject *type, PyObject *value, PyObject *traceback) {
    // Set the value and traceback of an error. Because calling
    // PyErr_Restore takes away a reference to each object passed in
    // as an argument, we manually increase the reference count of
    // each argument before calling it.
    Py_INCREF(type);
    Py_INCREF(value);
    Py_INCREF(traceback);
    PyErr_Restore(type, value, traceback);
}

tuple_T3OOO CPy_CatchError(void) {
    // We need to return the existing sys.exc_info() information, so
    // that it can be restored when we finish handling the error we
    // are catching now. Grab that triple and convert NULL values to
    // the ExcDummy object in order to simplify refcount handling in
    // generated code.
    tuple_T3OOO ret;
    PyErr_GetExcInfo(&ret.f0, &ret.f1, &ret.f2);
    _CPy_ToDummy(&ret.f0);
    _CPy_ToDummy(&ret.f1);
    _CPy_ToDummy(&ret.f2);

    if (!PyErr_Occurred()) {
        PyErr_SetString(PyExc_RuntimeError, "CPy_CatchError called with no error!");
    }

    // Retrieve the error info and normalize it so that it looks like
    // what python code needs it to be.
    PyObject *type, *value, *traceback;
    PyErr_Fetch(&type, &value, &traceback);
    // Could we avoid always normalizing?
    PyErr_NormalizeException(&type, &value, &traceback);
    if (traceback != NULL) {
        PyException_SetTraceback(value, traceback);
    }
    // Indicate that we are now handling this exception by stashing it
    // in sys.exc_info().  mypyc routines that need access to the
    // exception will read it out of there.
    PyErr_SetExcInfo(type, value, traceback);
    // Clear the error indicator, since the exception isn't
    // propagating anymore.
    PyErr_Clear();

    return ret;
}

void CPy_RestoreExcInfo(tuple_T3OOO info) {
    PyErr_SetExcInfo(_CPy_FromDummy(info.f0), _CPy_FromDummy(info.f1), _CPy_FromDummy(info.f2));
}

bool CPy_ExceptionMatches(PyObject *type) {
    return PyErr_GivenExceptionMatches(CPy_ExcState()->exc_type, type);
}

PyObject *CPy_GetExcValue(void) {
    PyObject *exc = CPy_ExcState()->exc_value;
    Py_INCREF(exc);
    return exc;
}

void _CPy_GetExcInfo(PyObject **p_type, PyObject **p_value, PyObject **p_traceback) {
    PyErr_GetExcInfo(p_type, p_value, p_traceback);
    _CPy_ToNone(p_type);
    _CPy_ToNone(p_value);
    _CPy_ToNone(p_traceback);
}

tuple_T3OOO CPy_GetExcInfo(void) {
    tuple_T3OOO ret;
    _CPy_GetExcInfo(&ret.f0, &ret.f1, &ret.f2);
    return ret;
}
