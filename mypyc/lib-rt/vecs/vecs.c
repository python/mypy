#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "vecs.h"


PyTypeObject *I64TypeObj;


// vec type proxy
//
// Used for the result of generic vec[t] that must preserve knowledge of 't'.
// These aren't really types. This only supports constructing instances.
typedef struct {
    PyObject_HEAD
    PyTypeObject *item_type;
    int32_t depth;  // Number of nested VecTExt or VecT types
    int32_t optionals;  // Flags for optional types on each nesting level
} VecProxy;

static PyObject *vec_proxy_call(PyObject *self, PyObject *args, PyObject *kw)
{
    static char *kwlist[] = {"", NULL};
    PyObject *init = NULL;
    if (!PyArg_ParseTupleAndKeywords(args, kw, "|O:vec", kwlist, &init)) {
        return NULL;
    }
    VecProxy *p = (VecProxy *)self;
    if (p->optionals == 0 && p->depth == 0) {
        if (init == NULL) {
            return (PyObject *)Vec_T_New(0, (PyObject *)p->item_type);
        } else {
            return (PyObject *)Vec_T_FromIterable((PyTypeObject *)p->item_type, init);
        }
    } else {
        if (init == NULL) {
            return (PyObject *)Vec_T_Ext_New(0, (PyObject *)p->item_type, p->optionals,
                                             p->depth);
        } else {
            return (PyObject *)Vec_T_Ext_FromIterable((PyTypeObject *)p->item_type, p->optionals,
                                                      p->depth, init);
        }
    }
}

static int
VecProxy_traverse(VecProxy *self, visitproc visit, void *arg)
{
    Py_VISIT(self->item_type);
    return 0;
}

static void
VecProxy_dealloc(VecProxy *self)
{
    Py_CLEAR(self->item_type);
    PyObject_GC_Del(self);
}

PyObject *vec_type_to_str(PyTypeObject *item_type, int32_t depth, int32_t optionals) {
    PyObject *item;
    if (depth == 0)
        item = PyObject_GetAttrString((PyObject *)item_type, "__name__");
    else
        item = vec_type_to_str(item_type, depth - 1, optionals >> 1);

    if (optionals & 1) {
        item = PyUnicode_FromFormat("%U | None", item);
    }
    return PyUnicode_FromFormat("vec[%U]", item);
}

PyObject *VecProxy_repr(PyObject *self) {
    // TODO: error handling, refcounting, etc.
    PyObject *l = Py_BuildValue("[]");
    PyObject *prefix = Py_BuildValue("s", "<class_proxy '");
    PyObject *suffix = Py_BuildValue("s", "'>");
    PyObject *sep = Py_BuildValue("s", "");
    PyList_Append(l, prefix);
    VecProxy *v = (VecProxy *)self;
    PyList_Append(l, vec_type_to_str(v->item_type, v->depth, v->optionals));
    PyList_Append(l, suffix);
    return PyUnicode_Join(sep, l);
}

PyTypeObject VecProxyType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "vec_proxy",
    .tp_basicsize = sizeof(VecProxy),
    .tp_itemsize = 0,
    .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC,
    .tp_call = vec_proxy_call,
    .tp_traverse = (traverseproc)VecProxy_traverse,
    .tp_dealloc = (destructor)VecProxy_dealloc,
    .tp_repr = (reprfunc)VecProxy_repr,
};


// The 'vec' type
//
// This cannot be instantiated, and it's only used for isinstance and indexing: vec[T].

typedef struct {
    PyObject_HEAD
} VecGeneric;

static PyObject *extract_optional_item(PyObject *item) {
    PyObject *args = PyObject_GetAttrString(item, "__args__");
    if (args == NULL) {
        PyErr_Clear();
        return NULL;
    }
    if (!PyTuple_CheckExact(args))
        goto error;
    if (PyTuple_GET_SIZE(args) != 2)
        goto error;
    PyObject *item0 = PyTuple_GET_ITEM(args, 0);
    PyObject *item1 = PyTuple_GET_ITEM(args, 1);
    if (item0 == (PyObject *)Py_None->ob_type) {
        Py_DECREF(args);
        return item1;
    } else if (item1 == (PyObject *)Py_None->ob_type) {
        Py_DECREF(args);
        return item0;
    }
  error:
    Py_DECREF(args);
    return NULL;
}

static PyObject *vec_class_getitem(PyObject *type, PyObject *item)
{
    if (item == (PyObject *)I64TypeObj) {
        Py_INCREF(&VecI64Type);
        return (PyObject *)&VecI64Type;
    } else {
        int32_t optionals = 0;
        int32_t depth = 0;
        if (!PyObject_TypeCheck(item, &PyType_Type)) {
            PyObject *it = extract_optional_item(item);
            if (it != NULL) {
                optionals = 1;
                item = it;
            }
            if (item->ob_type == &VecProxyType) {
                VecProxy *p = (VecProxy *)item;
                item = (PyObject *)p->item_type;
                depth = p->depth + 1;
                optionals |= p->optionals << 1;
            } else if (!PyObject_TypeCheck(item, &PyType_Type)) {
                PyErr_SetString(PyExc_TypeError, "type object expected in vec[...]");
                return NULL;
            }
        }
        if (item == (PyObject *)&PyLong_Type
            || item == (PyObject *)&PyFloat_Type
            || item == (PyObject *)&PyBool_Type) {
            PyErr_SetString(PyExc_ValueError, "unsupported type in vec[...]");
            return NULL;
        }
        VecProxy *p;
        p = PyObject_GC_New(VecProxy, &VecProxyType);
        if (p == NULL)
            return NULL;
        Py_INCREF(item);
        p->item_type = (PyTypeObject *)item;
        p->depth = depth;
        p->optionals = optionals;
        PyObject_GC_Track(p);
        return (PyObject *)p;
    }
}

static PyMethodDef vec_methods[] = {
    {"__class_getitem__", vec_class_getitem, METH_O|METH_CLASS, NULL},
    {NULL, NULL, 0, NULL},  /* Sentinel */
};

PyTypeObject VecGenericType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "vec",
    .tp_basicsize = sizeof(VecGeneric),
    .tp_itemsize = 0,
    .tp_flags = Py_TPFLAGS_DEFAULT,
    .tp_methods = vec_methods,
};

PyObject *vec_repr(PyObject *vec, PyTypeObject *item_type, int32_t depth, int32_t optionals,
                   int verbose) {
    PyObject *l = Py_BuildValue("[]");
    PyObject *prefix;
    PyObject *mid;
    PyObject *suffix;
    PyObject *sep = Py_BuildValue("s", "");
    PyObject *comma = Py_BuildValue("s", ", ");
    if (verbose) {
        prefix = vec_type_to_str(item_type, depth, optionals);
        mid = Py_BuildValue("s", "([");
        suffix = Py_BuildValue("s", "])");
    } else {
        prefix = Py_BuildValue("s", "");
        mid = Py_BuildValue("s", "[");
        suffix = Py_BuildValue("s", "]");
    }
    PyList_Append(l, prefix);
    PyList_Append(l, mid);

    Py_ssize_t len = PyObject_Length(vec);

    for (Py_ssize_t i = 0; i < len; i++) {
        PyObject *it = PySequence_GetItem(vec, i);
        PyObject *r;
        if (depth == 0) {
            r = PyObject_Repr(it);
        } else {
            r = vec_repr(it, item_type, depth - 1, optionals >> 1, 0);
        }
        if (r == NULL)
            return NULL;
        PyList_Append(l, r);
        if (i + 1 < len)
            PyList_Append(l, comma);
    }

    PyList_Append(l, suffix);

    return PyUnicode_Join(sep, l);
}

// Generic comparison implementation for vecs with PyObject * items.
PyObject *vec_generic_richcompare(Py_ssize_t *len, PyObject **items,
                                  Py_ssize_t *other_len, PyObject **other_items,
                                  int op) {
    int cmp = 1;
    PyObject *res;
    if (op == Py_EQ || op == Py_NE) {
        if (*len != *other_len) {
            cmp = 0;
        } else {
            for (Py_ssize_t i = 0; i < *len && i < *other_len; i++) {
                int itemcmp = PyObject_RichCompareBool(items[i], other_items[i], Py_EQ);
                if (itemcmp < 0)
                    return NULL;
                if (!itemcmp) {
                    cmp = 0;
                    break;
                }
            }
        }
        if (op == Py_NE)
            cmp = cmp ^ 1;
        res = cmp ? Py_True : Py_False;
    } else
        res = Py_NotImplemented;
    Py_INCREF(res);
    return res;
}

int vec_generic_remove(Py_ssize_t *len, PyObject **items, PyObject *item) {
    for (Py_ssize_t i = 0; i < *len; i++) {
        int match = 0;
        if (items[i] == item)
            match = 1;
        else {
            int itemcmp = PyObject_RichCompareBool(items[i], item, Py_EQ);
            if (itemcmp < 0)
                return 0;
            match = itemcmp;
        }
        if (match) {
            Py_CLEAR(items[i]);
            for (; i < *len - 1; i++) {
                items[i] = items[i + 1];
            }
            (*len)--;
            return 1;
        }
    }
    PyErr_SetString(PyExc_ValueError, "vec.remove(x): x not in vec");
    return 0;
}

PyObject *vec_generic_pop(Py_ssize_t *len, PyObject **items, Py_ssize_t index) {
    if (index < 0)
        index += *len;

    if (index < 0 || index >= *len) {
        PyErr_SetString(PyExc_IndexError, "index out of range");
        return NULL;
    }

    PyObject *item = items[index];
    for (Py_ssize_t i = index; i < *len - 1; i++)
        items[i] = items[i + 1];

    (*len)--;
    return item;
}

PyObject *vec_generic_pop_wrapper(Py_ssize_t *len, PyObject **items, PyObject *args) {
    Py_ssize_t index = -1;
    if (!PyArg_ParseTuple(args, "|n:pop", &index))
        return NULL;

    return vec_generic_pop(len, items, index);
}

// Module-level functions

static PyObject *vecs_append(PyObject *self, PyObject *args)
{
    PyObject *vec;
    PyObject *item;

    if (!PyArg_ParseTuple(args, "OO", &vec, &item))
        return NULL;

    if (VecI64_Check(vec)) {
        if (check_float_error(item))
            return NULL;
        int64_t x = PyLong_AsLong(item);
        if (x == -1 && PyErr_Occurred()) {
            return NULL;
        }
        Py_INCREF(vec);
        return Vec_I64_Append(vec, x);
    } else if (VecT_Check(vec)) {
        VecTObject *v = (VecTObject *)vec;
        if (!VecT_ItemCheck(v, item))
            return NULL;
        Py_INCREF(vec);
        return Vec_T_Append(vec, item);
    } else if (VecTExt_Check(vec)) {
        VecTExtObject *v = (VecTExtObject *)vec;
        if (!VecTExt_ItemCheck(v, item))
            return NULL;
        Py_INCREF(vec);
        return Vec_T_Ext_Append(vec, item);
    } else {
        PyErr_SetString(PyExc_TypeError, "vec argument expected");
        return NULL;
    }
}

static PyMethodDef VecsMethods[] = {
    {"append",  vecs_append, METH_VARARGS, "Append a value to a vec"},
    {NULL, NULL, 0, NULL}        /* Sentinel */
};

static PyModuleDef vecsmodule = {
    PyModuleDef_HEAD_INIT,
    .m_name = "vecs",
    .m_doc = "vecs doc",
    .m_size = -1,
    .m_methods = VecsMethods,
};

static VecCapsule Capsule = {
    &I64Features,
    &TFeatures,
    &TExtFeatures,
};

PyMODINIT_FUNC
PyInit_vecs(void)
{
    PyObject *ext = PyImport_ImportModule("mypy_extensions");
    if (ext == NULL) {
        return NULL;
    }

    I64TypeObj = (PyTypeObject *)PyObject_GetAttrString(ext, "i64");
    // TODO: Check that it's a type object!
    if (I64TypeObj == NULL) {
        return NULL;
    }

    if (PyType_Ready(&VecGenericType) < 0)
        return NULL;
    if (PyType_Ready(&VecProxyType) < 0)
        return NULL;
    if (PyType_Ready(&VecTType) < 0)
        return NULL;
    if (PyType_Ready(&VecTExtType) < 0)
        return NULL;
    if (PyType_Ready(&VecI64Type) < 0)
        return NULL;

    PyObject *m = PyModule_Create(&vecsmodule);
    if (m == NULL)
        return NULL;

    Py_INCREF(&VecGenericType);
    if (PyModule_AddObject(m, "vec", (PyObject *)&VecGenericType) < 0) {
        Py_DECREF(&VecGenericType);
        Py_DECREF(m);
        return NULL;
    }

    PyObject *c_api = PyCapsule_New(&Capsule, "vecs._C_API", NULL);
    if (c_api == NULL)
        return NULL;

    if (PyModule_AddObject(m, "_C_API", c_api) < 0) {
        Py_XDECREF(c_api);
        Py_DECREF(&VecGenericType);
        Py_DECREF(m);
        return NULL;
    }

    Py_DECREF(ext);

    return m;
}
