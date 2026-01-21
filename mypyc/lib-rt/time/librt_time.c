#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <time.h>
#include "librt_time.h"
#include "pythoncapi_compat.h"
#include "mypyc_util.h"

#ifdef MYPYC_EXPERIMENTAL

// Internal function that returns a C double for mypyc primitives
static double
time_time_internal(void) {
    time_t t = time(NULL);
    if (unlikely(t == (time_t)-1)) {
        PyErr_SetString(PyExc_OSError, "time() failed");
        return CPY_FLOAT_ERROR;
    }
    return (double)t;
}

// Wrapper function for normal Python extension usage
static PyObject*
time_time(PyObject *self, PyObject *const *args, size_t nargs) {
    if (nargs != 0) {
        PyErr_SetString(PyExc_TypeError, "time() takes no arguments");
        return NULL;
    }

    double result = time_time_internal();
    if (result == CPY_FLOAT_ERROR) {
        return NULL;
    }
    return PyFloat_FromDouble(result);
}

#endif

static PyMethodDef librt_time_module_methods[] = {
#ifdef MYPYC_EXPERIMENTAL
    {"time", (PyCFunction)time_time, METH_FASTCALL,
     PyDoc_STR("Return the current time in seconds since the Unix epoch as a floating point number.")},
#endif
    {NULL, NULL, 0, NULL}
};

#ifdef MYPYC_EXPERIMENTAL

static int
time_abi_version(void) {
    return LIBRT_TIME_ABI_VERSION;
}

static int
time_api_version(void) {
    return LIBRT_TIME_API_VERSION;
}

#endif

static int
librt_time_module_exec(PyObject *m)
{
#ifdef MYPYC_EXPERIMENTAL
    // Export mypyc internal C API via capsule
    static void *time_api[LIBRT_TIME_API_LEN] = {
        (void *)time_abi_version,
        (void *)time_api_version,
        (void *)time_time_internal,
    };
    PyObject *c_api_object = PyCapsule_New((void *)time_api, "librt.time._C_API", NULL);
    if (PyModule_Add(m, "_C_API", c_api_object) < 0) {
        return -1;
    }
#endif
    return 0;
}

static PyModuleDef_Slot librt_time_module_slots[] = {
    {Py_mod_exec, librt_time_module_exec},
#ifdef Py_MOD_GIL_NOT_USED
    {Py_mod_gil, Py_MOD_GIL_NOT_USED},
#endif
    {0, NULL}
};

static PyModuleDef librt_time_module = {
    .m_base = PyModuleDef_HEAD_INIT,
    .m_name = "time",
    .m_doc = "Fast time() function optimized for mypyc",
    .m_size = 0,
    .m_methods = librt_time_module_methods,
    .m_slots = librt_time_module_slots,
};

PyMODINIT_FUNC
PyInit_time(void)
{
    return PyModuleDef_Init(&librt_time_module);
}
