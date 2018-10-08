// Collects code that was copied in from cpython, for a couple of different reasons:
//  * We wanted to modify it to produce a more efficient version for our uses
//  * We needed to call it and it was static :(

#ifndef CPY_PYTHONSUPPORT_H
#define CPY_PYTHONSUPPORT_H

#include <stdbool.h>
#include <Python.h>
#include <frameobject.h>
#include <assert.h>
#include "mypyc_util.h"

#ifdef __cplusplus
extern "C" {
#endif
#if 0
} // why isn't emacs smart enough to not indent this
#endif

/////////////////////////////////////////
// Adapted from bltinmodule.c in Python 3.7.0
#if PY_MAJOR_VERSION >= 3 && PY_MINOR_VERSION >= 7
_Py_IDENTIFIER(__mro_entries__);
static PyObject*
update_bases(PyObject *bases)
{
    Py_ssize_t i, j;
    PyObject *base, *meth, *new_base, *result, *new_bases = NULL;
    PyObject *stack[1] = {bases};
    assert(PyTuple_Check(bases));

    Py_ssize_t nargs = PyTuple_GET_SIZE(bases);
    for (i = 0; i < nargs; i++) {
        base = PyTuple_GET_ITEM(bases, i);
        if (PyType_Check(base)) {
            if (new_bases) {
                /* If we already have made a replacement, then we append every normal base,
                   otherwise just skip it. */
                if (PyList_Append(new_bases, base) < 0) {
                    goto error;
                }
            }
            continue;
        }
        if (_PyObject_LookupAttrId(base, &PyId___mro_entries__, &meth) < 0) {
            goto error;
        }
        if (!meth) {
            if (new_bases) {
                if (PyList_Append(new_bases, base) < 0) {
                    goto error;
                }
            }
            continue;
        }
        new_base = _PyObject_FastCall(meth, stack, 1);
        Py_DECREF(meth);
        if (!new_base) {
            goto error;
        }
        if (!PyTuple_Check(new_base)) {
            PyErr_SetString(PyExc_TypeError,
                            "__mro_entries__ must return a tuple");
            Py_DECREF(new_base);
            goto error;
        }
        if (!new_bases) {
            /* If this is a first successful replacement, create new_bases list and
               copy previously encountered bases. */
            if (!(new_bases = PyList_New(i))) {
                goto error;
            }
            for (j = 0; j < i; j++) {
                base = PyTuple_GET_ITEM(bases, j);
                PyList_SET_ITEM(new_bases, j, base);
                Py_INCREF(base);
            }
        }
        j = PyList_GET_SIZE(new_bases);
        if (PyList_SetSlice(new_bases, j, j, new_base) < 0) {
            goto error;
        }
        Py_DECREF(new_base);
    }
    if (!new_bases) {
        return bases;
    }
    result = PyList_AsTuple(new_bases);
    Py_DECREF(new_bases);
    return result;

error:
    Py_XDECREF(new_bases);
    return NULL;
}
#else
static PyObject*
update_bases(PyObject *bases)
{
    return bases;
}
#endif

// From Python 3.7's typeobject.c
#if PY_MAJOR_VERSION >= 3 && PY_MINOR_VERSION >= 6
_Py_IDENTIFIER(__init_subclass__);
static int
init_subclass(PyTypeObject *type, PyObject *kwds)
{
    PyObject *super, *func, *result;
    PyObject *args[2] = {(PyObject *)type, (PyObject *)type};

    super = _PyObject_FastCall((PyObject *)&PySuper_Type, args, 2);
    if (super == NULL) {
        return -1;
    }

    func = _PyObject_GetAttrId(super, &PyId___init_subclass__);
    Py_DECREF(super);
    if (func == NULL) {
        return -1;
    }

    result = _PyObject_FastCallDict(func, NULL, 0, kwds);
    Py_DECREF(func);
    if (result == NULL) {
        return -1;
    }

    Py_DECREF(result);
    return 0;
}

#else
static int
init_subclass(PyTypeObject *type, PyObject *kwds)
{
    return 0;
}
#endif

// Adapted from longobject.c in Python 3.7.0

/* This function adapted from PyLong_AsLongLongAndOverflow, but with
 * some safety checks removed and specialized to only work for objects
 * that are already longs.
 * About half of the win this provides, though, just comes from being
 * able to inline the function, which in addition to saving function call
 * overhead allows the out-parameter overflow flag to be collapsed into
 * control flow.
 * Additionally, we check against the possible range of CPyTagged, not of
 * long long. */
static inline long long
CPyLong_AsLongLongAndOverflow(PyObject *vv, int *overflow)
{
    /* This version by Tim Peters */
    PyLongObject *v = (PyLongObject *)vv;
    unsigned long long x, prev;
    long long res;
    Py_ssize_t i;
    int sign;

    *overflow = 0;

    res = -1;
    i = Py_SIZE(v);

    if (likely(i == 1)) {
        res = v->ob_digit[0];
    } else if (likely(i == 0)) {
        res = 0;
    } else if (i == -1) {
        res = -(sdigit)v->ob_digit[0];
    } else {
        sign = 1;
        x = 0;
        if (i < 0) {
            sign = -1;
            i = -(i);
        }
        while (--i >= 0) {
            prev = x;
            x = (x << PyLong_SHIFT) + v->ob_digit[i];
            if ((x >> PyLong_SHIFT) != prev) {
                *overflow = sign;
                goto exit;
            }
        }
        /* Haven't lost any bits, but casting to long requires extra
         * care (see comment above).
         */
        if (x <= (unsigned long long)CPY_TAGGED_MAX) {
            res = (long long)x * sign;
        }
        else if (sign < 0 && x == CPY_TAGGED_ABS_MIN) {
            res = CPY_TAGGED_MIN;
        }
        else {
            *overflow = sign;
            /* res is already set to -1 */
        }
    }
  exit:
    return res;
}

#ifdef __cplusplus
}
#endif

#endif
