#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdlib.h>
#include <time.h>

//
// Random
//

typedef struct {
    PyObject_HEAD
    unsigned int seed;
} RandomObject;

static PyTypeObject RandomType;

static PyObject*
Random_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    if (type != &RandomType) {
        PyErr_SetString(PyExc_TypeError, "Random cannot be subclassed");
        return NULL;
    }

    RandomObject *self = (RandomObject *)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->seed = (unsigned int)time(NULL);
    }
    return (PyObject *)self;
}

static int
Random_init(RandomObject *self, PyObject *args, PyObject *kwds)
{
    if (!PyArg_ParseTuple(args, "")) {
        return -1;
    }

    if (kwds != NULL && PyDict_Size(kwds) > 0) {
        PyErr_SetString(PyExc_TypeError,
                        "Random() takes no keyword arguments");
        return -1;
    }

    return 0;
}

// Simple linear congruential generator
static inline unsigned int
next_random(RandomObject *self) {
    self->seed = self->seed * 1103515245 + 12345;
    return self->seed;
}

static PyObject*
Random_randint(RandomObject *self, PyObject *const *args, Py_ssize_t nargs) {
    if (nargs != 2) {
        PyErr_Format(PyExc_TypeError,
                     "randint() takes exactly 2 arguments (%zd given)", nargs);
        return NULL;
    }

    long long a = PyLong_AsLongLong(args[0]);
    if (a == -1 && PyErr_Occurred())
        return NULL;

    long long b = PyLong_AsLongLong(args[1]);
    if (b == -1 && PyErr_Occurred())
        return NULL;

    if (a > b) {
        PyErr_SetString(PyExc_ValueError,
                        "empty range for randint()");
        return NULL;
    }

    unsigned long long range = (unsigned long long)(b - a) + 1;
    unsigned int r = next_random(self);
    long long result = a + (long long)(r % range);
    return PyLong_FromLongLong(result);
}

static PyMethodDef Random_methods[] = {
    {"randint", (PyCFunction) Random_randint, METH_FASTCALL,
     PyDoc_STR("Return random integer in range [a, b], including both end points.")
    },
    {NULL}  /* Sentinel */
};

static PyTypeObject RandomType = {
    .ob_base = PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "Random",
    .tp_doc = PyDoc_STR("Fast random number generator"),
    .tp_basicsize = sizeof(RandomObject),
    .tp_itemsize = 0,
    .tp_flags = Py_TPFLAGS_DEFAULT,
    .tp_new = Random_new,
    .tp_init = (initproc) Random_init,
    .tp_methods = Random_methods,
};

// Module definition

static PyMethodDef librt_random_module_methods[] = {
    {NULL, NULL, 0, NULL}
};

static int
librt_random_module_exec(PyObject *m)
{
    if (PyType_Ready(&RandomType) < 0) {
        return -1;
    }
    if (PyModule_AddObjectRef(m, "Random", (PyObject *) &RandomType) < 0) {
        return -1;
    }
    return 0;
}

static PyModuleDef_Slot librt_random_module_slots[] = {
    {Py_mod_exec, librt_random_module_exec},
#ifdef Py_MOD_GIL_NOT_USED
    {Py_mod_gil, Py_MOD_GIL_NOT_USED},
#endif
    {0, NULL}
};

static PyModuleDef librt_random_module = {
    .m_base = PyModuleDef_HEAD_INIT,
    .m_name = "random",
    .m_doc = "Fast random number generation",
    .m_size = 0,
    .m_methods = librt_random_module_methods,
    .m_slots = librt_random_module_slots,
};

PyMODINIT_FUNC
PyInit_random(void)
{
    return PyModuleDef_Init(&librt_random_module);
}
