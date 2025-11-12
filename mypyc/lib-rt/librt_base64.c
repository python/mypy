#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "librt_base64.h"

static PyObject *
b64encode_internal(PyObject *obj) {
    return 0;
}

static PyObject*
b64encode(PyObject *self, PyObject *const *args, size_t nargs, PyObject *kwnames) {
    return 0;
}

static PyMethodDef librt_base64_module_methods[] = {
    {"b64encode", (PyCFunction)b64encode, METH_FASTCALL | METH_KEYWORDS, PyDoc_STR("Encode bytes-like object using Base64.")},
    {NULL, NULL, 0, NULL}
};

static int
base64_abi_version(void) {
    return 0;
}

static int
base64_api_version(void) {
    return 0;
}

static int
librt_base64_module_exec(PyObject *m)
{
    // Export mypy internal C API, be careful with the order!
    static void *base64_api[LIBRT_BASE64_API_LEN] = {
        (void *)base64_abi_version,
        (void *)base64_api_version,
        //(void *)b64encode_internal,
    };
    PyObject *c_api_object = PyCapsule_New((void *)base64_api, "librt.base64._C_API", NULL);
    if (PyModule_Add(m, "_C_API", c_api_object) < 0) {
        return -1;
    }
    return 0;
}

static PyModuleDef_Slot librt_base64_module_slots[] = {
    {Py_mod_exec, librt_base64_module_exec},
#ifdef Py_MOD_GIL_NOT_USED
    {Py_mod_gil, Py_MOD_GIL_NOT_USED},
#endif
    {0, NULL}
};

static PyModuleDef librt_base64_module = {
    .m_base = PyModuleDef_HEAD_INIT,
    .m_name = "base64",
    .m_doc = "base64 encoding and decoding optimized for mypyc",
    .m_size = 0,
    .m_methods = librt_base64_module_methods,
    .m_slots = librt_base64_module_slots,
};

PyMODINIT_FUNC
PyInit_base64(void)
{
    return PyModuleDef_Init(&librt_base64_module);
}
