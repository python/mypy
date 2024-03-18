// Generic native class attribute getters and setters

#include <Python.h>
#include "CPy.h"

PyObject *CPyAttr_UndefinedError(PyObject *self, CPyAttr_Context *context) {
    assert(!context->always_defined && "attribute should be initialized!");
    PyErr_Format(PyExc_AttributeError,
        "attribute '%s' of '%s' undefined", context->attr_name, Py_TYPE(self)->tp_name);
    return NULL;
}

int CPyAttr_UndeletableError(PyObject *self, CPyAttr_Context *context) {
    PyErr_Format(PyExc_AttributeError,
        "'%s' object attribute '%s' cannot be deleted", Py_TYPE(self)->tp_name, context->attr_name);
    return -1;
}

static void set_definedness_in_bitmap(PyObject *self, CPyAttr_Context *context, bool defined) {
    uint32_t *bitmap = (uint32_t *)((char *)self + context->bitmap.offset);
    if (defined) {
        *bitmap |= context->bitmap.mask;
    } else {
        *bitmap &= ~context->bitmap.mask;
    }
}

static inline bool is_undefined_via_bitmap(PyObject *self, CPyAttr_Context *context) {
    return !(*(uint32_t *)((char *)self + context->bitmap.offset) & context->bitmap.mask);
}

PyObject *CPyAttr_GetterPyObject(PyObject *self, CPyAttr_Context *context) {
    PyObject *value = *(PyObject **)((char *)self + context->offset);
    if (unlikely(value == NULL)) {
        return CPyAttr_UndefinedError(self, context);
    }
    return Py_NewRef(value);
}

PyObject *CPyAttr_GetterTagged(PyObject *self, CPyAttr_Context *context) {
    CPyTagged value = *(CPyTagged *)((char *)self + context->offset);
    if (unlikely(value == CPY_INT_TAG)) {
        return CPyAttr_UndefinedError(self, context);
    }
    return CPyTagged_AsObject(value);
}

PyObject *CPyAttr_GetterBool(PyObject *self, CPyAttr_Context *context) {
    char value = *((char *)self + context->offset);
    if (unlikely(value == 2)) {
        return CPyAttr_UndefinedError(self, context);
    }
    return Py_NewRef(value ? Py_True : Py_False);
}

PyObject *CPyAttr_GetterFloat(PyObject *self, CPyAttr_Context *context) {
    double value = *(double *)((char *)self + context->offset);
    if (unlikely(value == CPY_FLOAT_ERROR
            && !context->always_defined
            && is_undefined_via_bitmap(self, context))) {
        return CPyAttr_UndefinedError(self, context);
    }
    return PyFloat_FromDouble(value);
}

int CPyAttr_SetterPyObject(PyObject *self, PyObject *value, CPyAttr_Context *context) {
    if (value == NULL && !context->deletable) {
        return CPyAttr_UndeletableError(self, context);
    }

    PyObject **attr = (PyObject **)((char *)self + context->offset);
    if (value != NULL) {
        Py_XSETREF(*attr, Py_NewRef(value));
    } else {
        Py_CLEAR(*attr);
    }
    return 0;
}

#define _CPyAttr_BUILTIN_SETTER(name, typechecker, typename)                                    \
    int CPyAttr_Setter##name(PyObject *self, PyObject *value, CPyAttr_Context *context) {       \
        if (unlikely(value == NULL && !context->deletable)) {                                   \
            return CPyAttr_UndeletableError(self, context);                                     \
        }                                                                                       \
                                                                                                \
        PyObject **attr = (PyObject **)((char *)self + context->offset);                        \
        if (value != NULL) {                                                                    \
            if (unlikely(!typechecker(value) && !(value == Py_None && context->allow_none))) {  \
                if (context->allow_none) {                                                      \
                    CPy_TypeError(typename " or None", value);                                  \
                } else {                                                                        \
                    CPy_TypeError(typename, value);                                             \
                }                                                                               \
                return -1;                                                                      \
            }                                                                                   \
            Py_XSETREF(*attr, Py_NewRef(value));                                                \
        } else {                                                                                \
            Py_CLEAR(*attr);                                                                    \
        }                                                                                       \
        return 0;                                                                               \
    }

_CPyAttr_BUILTIN_SETTER(Unicode, PyUnicode_Check, "str")
_CPyAttr_BUILTIN_SETTER(LongOrNone, PyLong_Check, "int")
_CPyAttr_BUILTIN_SETTER(BoolOrNone, PyBool_Check, "bool")
_CPyAttr_BUILTIN_SETTER(FloatOrNone, PyFloat_Check, "float")
_CPyAttr_BUILTIN_SETTER(Tuple, PyTuple_Check, "tuple")
_CPyAttr_BUILTIN_SETTER(List, PyList_Check, "list")
_CPyAttr_BUILTIN_SETTER(Dict, PyDict_Check, "dict")
_CPyAttr_BUILTIN_SETTER(Set, PySet_Check, "set")

int CPyAttr_SetterTagged(PyObject *self, PyObject *value, CPyAttr_Context *context) {
    if (value == NULL && !context->deletable) {
        return CPyAttr_UndeletableError(self, context);
    }

    CPyTagged *attr = (CPyTagged *)((char *)self + context->offset);
    if (value != NULL) {
        if (unlikely(!PyLong_Check(value))) {
            CPy_TypeError("int", value);
            return -1;
        }
        if (*attr != CPY_INT_TAG) {
            CPyTagged_DECREF(*attr);
        }
        *attr = CPyTagged_FromObject(value);
    } else {
        if (*attr != CPY_INT_TAG) {
            CPyTagged_DECREF(*attr);
        }
        *attr = CPY_INT_TAG;
    }
    return 0;
}

int CPyAttr_SetterBool(PyObject *self, PyObject *value, CPyAttr_Context *context) {
    if (value == NULL && !context->deletable) {
        return CPyAttr_UndeletableError(self, context);
    }

    char *attr = (char *)self + context->offset;
    if (value != NULL) {
        if (unlikely(!PyBool_Check(value))) {
            CPy_TypeError("bool", value);
            return -1;
        }
        *attr = value == Py_True;
    } else {
        *attr = 2;
    }
    return 0;
}

int CPyAttr_SetterFloat(PyObject *self, PyObject *value, CPyAttr_Context *context) {
    if (value == NULL && !context->deletable) {
        return CPyAttr_UndeletableError(self, context);
    }

    double *attr = (double *)((char *)self + context->offset);
    if (value != NULL) {
        if (unlikely(!PyFloat_Check(value))) {
            CPy_TypeError("float", value);
            return -1;
        }
        double tmp = PyFloat_AsDouble(value);
        if (unlikely(tmp == -1.0 && PyErr_Occurred())) {
            return -1;
        }
        *attr = tmp;
        if (tmp == CPY_FLOAT_ERROR) {
            set_definedness_in_bitmap(self, context, true);
        }
    } else {
        *attr = CPY_FLOAT_ERROR;
        set_definedness_in_bitmap(self, context, false);
    }
    return 0;
}
