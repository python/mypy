#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "vecs.h"


static PyObject *i64_type_obj;


// vec type proxy
//
// Used for the result of generic vec[t] that must preserve knowledge of 't'.
// These aren't really types.

// this can only instantiated
typedef struct {
    PyObject_HEAD
    PyObject *item_type;
} VecProxy;

static PyObject *vec_proxy_call(PyObject *self, PyObject *args, PyObject *kw)
{
    static char *kwlist[] = {NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kw, ":vec", kwlist)) {
        return NULL;
    }
    return (PyObject *)Vec_T_New(0, ((VecProxy *)self)->item_type);
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

PyObject *VecProxy_repr(PyObject *self) {
    // TODO: error handling, refcounting, etc.
    PyObject *l = Py_BuildValue("[]");
    PyObject *prefix = Py_BuildValue("s", "<class_proxy 'vec[");
    PyObject *suffix = Py_BuildValue("s", "]'>");
    PyObject *sep = Py_BuildValue("s", "");
    PyList_Append(l, prefix);
    PyList_Append(l, PyObject_GetAttrString(((VecProxy *)self)->item_type, "__name__"));
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


// Untyped vec
//
// This cannot be instantiated, only used for isinstance and indexing: vec[T].

typedef struct {
    PyObject_HEAD
} VecGeneric;

static PyObject *vec_class_getitem(PyObject *type, PyObject *item)
{
    if (item == i64_type_obj) {
        Py_INCREF(&VecI64Type);
        return (PyObject *)&VecI64Type;
    } else {
        // TODO: Check validity
        VecProxy *p;
        p = PyObject_GC_New(VecProxy, &VecProxyType);
        if (p == NULL)
            return NULL;
        Py_INCREF(item);
        p->item_type = item;
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


// Module-level functions

static PyObject *vecs_append(PyObject *self, PyObject *args)
{
    PyObject *vec;
    PyObject *item;

    if (!PyArg_ParseTuple(args, "OO", &vec, &item))
        return NULL;

    // TODO: Type check obj

    if (VecI64_Check(vec)) {
        // TODO: Check exact
        int64_t x = PyLong_AsLong(item);
        if (x == -1 && PyErr_Occurred()) {
            return NULL;
        }
        Py_INCREF(vec);
        return Vec_I64_Append(vec, x);
    } else if (VecT_Check(vec)) {
        VecTObject *v = (VecTObject *)vec;
        int r = PyObject_IsInstance(item, v->item_type);
        if (r > 0) {
            Py_INCREF(vec);
            return Vec_T_Append(vec, item);
        } else if (r == -1) {
            return NULL;
        } else {
            // TODO: exception
            return NULL;
        }
    } else {
        // TODO: exception
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
    &I64Features
};

PyMODINIT_FUNC
PyInit_vecs(void)
{
    PyObject *ext = PyImport_ImportModule("mypy_extensions");
    if (ext == NULL) {
        return NULL;
    }

    i64_type_obj = PyObject_GetAttrString(ext, "i64");
    if (i64_type_obj == NULL) {
        return NULL;
    }

    if (PyType_Ready(&VecGenericType) < 0)
        return NULL;
    if (PyType_Ready(&VecProxyType) < 0)
        return NULL;
    if (PyType_Ready(&VecTType) < 0)
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
