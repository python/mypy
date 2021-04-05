#define PY_SSIZE_T_CLEAN
#include <Python.h>

typedef struct {
    PyObject_HEAD
    /* Type-specific fields go here. */
} VecObject;

static PyTypeObject VecType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "vecs.vec",
    .tp_doc = "vec doc",
    .tp_basicsize = sizeof(VecObject),
    .tp_itemsize = 0,
    .tp_flags = Py_TPFLAGS_DEFAULT,
    .tp_new = PyType_GenericNew,
};

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
