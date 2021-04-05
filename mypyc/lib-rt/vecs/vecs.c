#define PY_SSIZE_T_CLEAN
#include <Python.h>

static PyObject *vec_new(PyTypeObject *self, PyObject *args, PyObject *kw);

typedef struct {
    PyObject_VAR_HEAD
    Py_ssize_t capacity;
    long long item[1];
} VecObject;

static PyTypeObject VecType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "vecs.vec",
    .tp_doc = "vec doc",
    .tp_basicsize = sizeof(VecObject) - sizeof(long long),
    .tp_itemsize = sizeof(long long),
    .tp_flags = Py_TPFLAGS_DEFAULT,
    .tp_new = vec_new,
    .tp_free = PyObject_Del,
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
        v->item[i] = 0;
    }
    v->capacity = size;
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

static PyObject *
vecs_append(PyObject *self, PyObject *args)
{
    PyObject *obj;
    long long x;

    if (!PyArg_ParseTuple(args, "OL", &obj, &x))
        return NULL;
    Py_INCREF(obj);
    return obj;
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

    return m;
}
