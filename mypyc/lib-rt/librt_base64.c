#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "librt_base64.h"
#include "libbase64.h"
#include "pythoncapi_compat.h"

#ifdef MYPYC_EXPERIMENTAL

#define BASE64_MAXBIN ((PY_SSIZE_T_MAX - 3) / 2)

#define STACK_BUFFER_SIZE 1024

static PyObject *
b64encode_internal(PyObject *obj) {
    unsigned char *ascii_data;
    char *bin_data;
    int leftbits = 0;
    unsigned char this_ch;
    unsigned int leftchar = 0;
    Py_ssize_t bin_len, out_len;
    PyBytesWriter *writer;
    int newline = 0; // TODO

    if (!PyBytes_Check(obj)) {
        PyErr_SetString(PyExc_TypeError, "base64() expects a bytes object");
        return NULL;
    }

    bin_data = PyBytes_AS_STRING(obj);
    bin_len = PyBytes_GET_SIZE(obj);
    assert(bin_len >= 0);

    if (bin_len > BASE64_MAXBIN) {
        PyErr_SetString(PyExc_ValueError, "Too much data for base64 line");
        return NULL;
    }

    Py_ssize_t buflen = 4 * bin_len / 3 + 4;
    char *buf;
    char stack_buf[STACK_BUFFER_SIZE];
    if (buflen <= STACK_BUFFER_SIZE) {
        buf = stack_buf;
    } else {
        buf = PyMem_Malloc(buflen);
        if (buf == NULL) {
            return PyErr_NoMemory();
        }
    }
    size_t actual_len;
    base64_encode(bin_data, bin_len, buf, &actual_len, 0);
    PyObject *res = PyBytes_FromStringAndSize(buf, actual_len);
    if (buflen > STACK_BUFFER_SIZE)
        PyMem_Free(buf);
    return res;
}

static PyObject*
b64encode(PyObject *self, PyObject *const *args, size_t nargs) {
    if (nargs != 1) {
        PyErr_SetString(PyExc_TypeError, "b64encode() takes exactly one argument");
        return 0;
    }
    return b64encode_internal(args[0]);
}

#endif

static PyMethodDef librt_base64_module_methods[] = {
#ifdef MYPYC_EXPERIMENTAL
    {"b64encode", (PyCFunction)b64encode, METH_FASTCALL, PyDoc_STR("Encode bytes-like object using Base64.")},
#endif
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
#ifdef MYPYC_EXPERIMENTAL
    // Export mypy internal C API, be careful with the order!
    static void *base64_api[LIBRT_BASE64_API_LEN] = {
        (void *)base64_abi_version,
        (void *)base64_api_version,
        (void *)b64encode_internal,
    };
    PyObject *c_api_object = PyCapsule_New((void *)base64_api, "librt.base64._C_API", NULL);
    if (PyModule_Add(m, "_C_API", c_api_object) < 0) {
        return -1;
    }
#endif
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
