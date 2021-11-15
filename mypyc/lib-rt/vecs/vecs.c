#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "vecs.h"

static PyObject *vecs_append(PyObject *self, PyObject *args)
{
    PyObject *obj;
    int64_t x;

    if (!PyArg_ParseTuple(args, "OL", &obj, &x))
        return NULL;

    // TODO: Type check obj

    Py_INCREF(obj);
    return Vec_I64_Append(obj, x);
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
    PyObject *m;
    if (PyType_Ready(&VecI64Type) < 0)
        return NULL;

    m = PyModule_Create(&vecsmodule);
    if (m == NULL)
        return NULL;

    Py_INCREF(&VecI64Type);
    if (PyModule_AddObject(m, "vec", (PyObject *) &VecI64Type) < 0) {
        Py_DECREF(&VecI64Type);
        Py_DECREF(m);
        return NULL;
    }

    PyObject *c_api = PyCapsule_New(&Capsule, "vecs._C_API", NULL);
    if (c_api == NULL)
        return NULL;

    if (PyModule_AddObject(m, "_C_API", c_api) < 0) {
        Py_XDECREF(c_api);
        Py_DECREF(&VecI64Type);
        Py_DECREF(m);
        return NULL;
    }

    return m;
}
