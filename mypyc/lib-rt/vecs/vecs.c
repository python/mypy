#define PY_SSIZE_T_CLEAN
#include <Python.h>

static PyObject *
vecs_system(PyObject *self, PyObject *args)
{
    const char *command;
    int sts;

    if (!PyArg_ParseTuple(args, "s", &command))
        return NULL;
    sts = system(command);
    return PyLong_FromLong(sts);
}

static PyMethodDef VecsMethods[] = {
    {"system",  vecs_system, METH_VARARGS,
     "Execute a shell command."},
    {NULL, NULL, 0, NULL}        /* Sentinel */
};

static struct PyModuleDef vecsmodule = {
    PyModuleDef_HEAD_INIT,
    "vecs",   /* name of module */
    NULL, /* module documentation, may be NULL */
    -1,       /* size of per-interpreter state of the module,
                 or -1 if the module keeps state in global variables. */
    VecsMethods
};

PyMODINIT_FUNC
PyInit_vecs(void)
{
    return PyModule_Create(&vecsmodule);
}
