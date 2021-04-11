#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "vecs.h"

#define VEC_SIZE(v) ((v)->ob_base.ob_size)

static PyObject *vec_new(PyTypeObject *self, PyObject *args, PyObject *kw);

PyObject *vec_repr(PyObject *self) {
    // TODO: Type check, refcounting, error handling
    VecObject *o = (VecObject *)self;
    PyObject *prefix = Py_BuildValue("s", "vec(i64, [");
    PyObject *suffix = Py_BuildValue("s", "])");
    PyObject *l = Py_BuildValue("[]");
    PyObject *sep = Py_BuildValue("s", "");
    PyObject *comma = Py_BuildValue("s", ", ");
    PyList_Append(l, prefix);
    for (int i = 0; i < o->len; i++) {
        char s[100];
        sprintf(s, "%lld", o->items[i]);
        PyObject *x = Py_BuildValue("s", s);
        PyList_Append(l, x);
        if (i + 1 < o->len)
            PyList_Append(l, comma);
    }
    PyList_Append(l, suffix);
    return PyUnicode_Join(sep, l);
}

PyObject *vec_get_item(PyObject *o, Py_ssize_t i) {
    // TODO: Type check o
    VecObject *v = (VecObject *)o;
    if ((size_t)i < (size_t)v->len) {
        return PyLong_FromLongLong(v->items[i]);
    } else {
        PyErr_SetString(PyExc_IndexError, "index out of range");
        return NULL;
    }
}

int vec_ass_item(PyObject *self, Py_ssize_t i, PyObject *o) {
    // TODO: Type check o
    VecObject *v = (VecObject *)self;
    if ((size_t)i < (size_t)v->len) {
        long long x = PyLong_AsLongLong(o);
        if (x == -1 && PyErr_Occurred())
            return -1;
        v->items[i] = x;
        return 0;
    } else {
        PyErr_SetString(PyExc_IndexError, "index out of range");
        return -1;
    }
}

Py_ssize_t vec_length(PyObject *o) {
    // TODO: Type check o
    return ((VecObject *)o)->len;
}

static PyMappingMethods VecMapping = {
    .mp_length = vec_length,
};

static PySequenceMethods VecSequence = {
    .sq_item = vec_get_item,
    .sq_ass_item = vec_ass_item,
};

static PyTypeObject VecType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "vecs.vec",
    .tp_doc = "vec doc",
    .tp_basicsize = sizeof(VecObject) - sizeof(long long),
    .tp_itemsize = sizeof(long long),
    .tp_flags = Py_TPFLAGS_DEFAULT,
    .tp_new = vec_new,
    .tp_free = PyObject_Del,
    .tp_repr = (reprfunc)vec_repr,
    .tp_as_sequence = &VecSequence,
    .tp_as_mapping = &VecMapping,
};

static VecObject *
vec_alloc(Py_ssize_t size)
{
    VecObject *v;
    /* TODO: Check for overflow */
    v = PyObject_NewVar(VecObject, &VecType, size);
    if (v == NULL)
        return NULL;
    return v;
}

PyObject *
Vec_New(Py_ssize_t size)
{
    VecObject *v;
    v = vec_alloc(size);
    if (v == NULL)
        return NULL;
    for (Py_ssize_t i = 0; i < size; i++) {
        v->items[i] = 0;
    }
    v->len = size;
    return (PyObject *)v;
}

PyObject *vec_new(PyTypeObject *self, PyObject *args, PyObject *kw) {
    static char *kwlist[] = {"", NULL};
    PyObject *t;
    if (!PyArg_ParseTupleAndKeywords(args, kw, "O:vec", kwlist, &t)) {
        return NULL;
    }
    return Vec_New(0);
}

VecObject *
Vec_Append(VecObject *vec, int64_t x) {
    Py_ssize_t cap = VEC_SIZE(vec);
    Py_ssize_t len = vec->len;
    if (len < cap) {
        vec->items[len] = x;
        vec->len = len + 1;
        Py_INCREF(vec);
        return vec;
    } else {
        Py_ssize_t new_size = 2 * cap + 1;
        VecObject *new = vec_alloc(new_size);
        if (new == NULL)
            return NULL;
        memcpy(new->items, vec->items, sizeof(long long) * len);
        new->items[len] = x;
        new->len = len + 1;
        return new;
    }
}

static PyObject *
vecs_append(PyObject *self, PyObject *args)
{
    PyObject *obj;
    long long x;

    if (!PyArg_ParseTuple(args, "OL", &obj, &x))
        return NULL;

    // TODO: Type check obj

    return (PyObject *)Vec_Append((VecObject *)obj, x);
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

static VecI64Features I64Features = {
    &VecType,
    Vec_New,
    Vec_Append,
};

static VecCapsule Capsule = {
    &I64Features
};

PyMODINIT_FUNC
PyInit_vecs(void)
{
    PyObject *m;
    if (PyType_Ready(&VecType) < 0)
        return NULL;

    m = PyModule_Create(&vecsmodule);
    if (m == NULL)
        return NULL;

    Py_INCREF(&VecType);
    if (PyModule_AddObject(m, "vec", (PyObject *) &VecType) < 0) {
        Py_DECREF(&VecType);
        Py_DECREF(m);
        return NULL;
    }

    if (PyCapsule_New(&Capsule, "vecs.capsule", NULL) == NULL)
        return NULL;

    return m;
}
