#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "vecs.h"

static PyObject *vec_i64_new(PyTypeObject *self, PyObject *args, PyObject *kw);

PyObject *vec_i64_repr(PyObject *self) {
    // TODO: Type check, refcounting, error handling
    VecI64Object *o = (VecI64Object *)self;
    PyObject *prefix = Py_BuildValue("s", "vec(i64, [");
    PyObject *suffix = Py_BuildValue("s", "])");
    PyObject *l = Py_BuildValue("[]");
    PyObject *sep = Py_BuildValue("s", "");
    PyObject *comma = Py_BuildValue("s", ", ");
    PyList_Append(l, prefix);
    for (int i = 0; i < o->len; i++) {
        char s[100];
        sprintf(s, "%lld", (long long)o->items[i]);
        PyObject *x = Py_BuildValue("s", s);
        PyList_Append(l, x);
        if (i + 1 < o->len)
            PyList_Append(l, comma);
    }
    PyList_Append(l, suffix);
    return PyUnicode_Join(sep, l);
}

PyObject *vec_i64_get_item(PyObject *o, Py_ssize_t i) {
    // TODO: Type check o
    VecI64Object *v = (VecI64Object *)o;
    if ((size_t)i < (size_t)v->len) {
        return PyLong_FromLongLong(v->items[i]);
    } else {
        PyErr_SetString(PyExc_IndexError, "index out of range");
        return NULL;
    }
}

int vec_i64_ass_item(PyObject *self, Py_ssize_t i, PyObject *o) {
    // TODO: Type check o
    VecI64Object *v = (VecI64Object *)self;
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
    return ((VecI64Object *)o)->len;
}

static PyMappingMethods VecI64Mapping = {
    .mp_length = vec_length,
};

static PySequenceMethods VecI64Sequence = {
    .sq_item = vec_i64_get_item,
    .sq_ass_item = vec_i64_ass_item,
};

PyTypeObject VecI64Type = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "vec[i64]",
    .tp_doc = "vec doc",
    .tp_basicsize = sizeof(VecI64Object) - sizeof(int64_t),
    .tp_itemsize = sizeof(int64_t),
    .tp_flags = Py_TPFLAGS_DEFAULT,
    .tp_new = vec_i64_new,
    .tp_free = PyObject_Del,
    .tp_repr = (reprfunc)vec_i64_repr,
    .tp_as_sequence = &VecI64Sequence,
    .tp_as_mapping = &VecI64Mapping,
};

static VecI64Object *vec_i64_alloc(Py_ssize_t size)
{
    VecI64Object *v;
    /* TODO: Check for overflow */
    v = PyObject_NewVar(VecI64Object, &VecI64Type, size);
    if (v == NULL)
        return NULL;
    return v;
}

PyObject *Vec_I64_New(Py_ssize_t size)
{
    VecI64Object *v;
    v = vec_i64_alloc(size);
    if (v == NULL)
        return NULL;
    for (Py_ssize_t i = 0; i < size; i++) {
        v->items[i] = 0;
    }
    v->len = size;
    return (PyObject *)v;
}

PyObject *vec_i64_new(PyTypeObject *self, PyObject *args, PyObject *kw) {
    static char *kwlist[] = {NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kw, ":vec", kwlist)) {
        return NULL;
    }
    return Vec_I64_New(0);
}

PyObject *Vec_I64_Append(PyObject *obj, int64_t x) {
    VecI64Object *vec = (VecI64Object *)obj;
    Py_ssize_t cap = VEC_SIZE(vec);
    Py_ssize_t len = vec->len;
    if (len < cap) {
        vec->items[len] = x;
        vec->len = len + 1;
        return (PyObject *)vec;
    } else {
        Py_ssize_t new_size = 2 * cap + 1;
        VecI64Object *new = vec_i64_alloc(new_size);
        if (new == NULL)
            return NULL;
        memcpy(new->items, vec->items, sizeof(int64_t) * len);
        new->items[len] = x;
        new->len = len + 1;
        Py_DECREF(vec);
        return (PyObject *)new;
    }
}

VecI64Features I64Features = {
    &VecI64Type,
    Vec_I64_New,
    Vec_I64_Append,
};
