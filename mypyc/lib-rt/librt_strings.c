#include "pythoncapi_compat.h"

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdint.h>
#include "CPy.h"
#define LIBRT_INTERNAL_MODULE
#include "librt_internal.h"

#define START_SIZE 512

#define CPY_BOOL_ERROR 2
#define CPY_NONE_ERROR 2
#define CPY_NONE 1

#define _CHECK_WRITE_BUFFER(data, err) if (unlikely(_check_write_buffer(data) == CPY_NONE_ERROR)) \
                                           return err;
#define _CHECK_WRITE(data, need)        if (unlikely(_check_size((WriteBufferObject *)data, need) == CPY_NONE_ERROR)) \
                                           return CPY_NONE_ERROR;

#define _WRITE(data, type, v) \
    do { \
       *(type *)(((WriteBufferObject *)data)->ptr) = v; \
       ((WriteBufferObject *)data)->ptr += sizeof(type); \
    } while (0)

//
// WriteBuffer
//

typedef struct {
    PyObject_HEAD
    char *buf;  // Beginning of the buffer
    char *ptr;  // Current write location in the buffer
    char *end;  // End of the buffer
} WriteBufferObject;

static PyTypeObject WriteBufferType;

static PyObject*
WriteBuffer_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    if (type != &WriteBufferType) {
        PyErr_SetString(PyExc_TypeError, "WriteBuffer cannot be subclassed");
        return NULL;
    }

    WriteBufferObject *self = (WriteBufferObject *)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->buf = NULL;
        self->ptr = NULL;
        self->end = NULL;
    }
    return (PyObject *)self;
}

static int
WriteBuffer_init_internal(WriteBufferObject *self) {
    Py_ssize_t size = START_SIZE;
    self->buf = PyMem_Malloc(size + 1);
    if (self->buf == NULL) {
        PyErr_NoMemory();
        return -1;
    }
    self->ptr = self->buf;
    self->end = self->buf + size;
    return 0;
}

static PyObject*
WriteBuffer_internal(void) {
    WriteBufferObject *self = (WriteBufferObject *)WriteBufferType.tp_alloc(&WriteBufferType, 0);
    if (self == NULL)
        return NULL;
    self->buf = NULL;
    self->ptr = NULL;
    self->end = NULL;
    if (WriteBuffer_init_internal(self) == -1) {
        Py_DECREF(self);
        return NULL;
    }
    return (PyObject *)self;
}

static int
WriteBuffer_init(WriteBufferObject *self, PyObject *args, PyObject *kwds)
{
    if (!PyArg_ParseTuple(args, "")) {
        return -1;
    }

    if (kwds != NULL && PyDict_Size(kwds) > 0) {
        PyErr_SetString(PyExc_TypeError,
                        "WriteBuffer() takes no keyword arguments");
        return -1;
    }

    return WriteBuffer_init_internal(self);
}

static void
WriteBuffer_dealloc(WriteBufferObject *self)
{
    PyMem_Free(self->buf);
    self->buf = NULL;
    Py_TYPE(self)->tp_free((PyObject *)self);
}

static PyObject*
WriteBuffer_getvalue_internal(PyObject *self)
{
    WriteBufferObject *obj = (WriteBufferObject *)self;
    return PyBytes_FromStringAndSize(obj->buf, obj->ptr - obj->buf);
}

static PyObject*
WriteBuffer_getvalue(WriteBufferObject *self, PyObject *Py_UNUSED(ignored))
{
    return PyBytes_FromStringAndSize(self->buf, self->ptr - self->buf);
}

static PyMethodDef WriteBuffer_methods[] = {
    {"getvalue", (PyCFunction) WriteBuffer_getvalue, METH_NOARGS,
     "Return the buffer content as bytes object"
    },
    {NULL}  /* Sentinel */
};

static PyTypeObject WriteBufferType = {
    .ob_base = PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "WriteBuffer",
    .tp_doc = PyDoc_STR("Mypy cache buffer objects"),
    .tp_basicsize = sizeof(WriteBufferObject),
    .tp_itemsize = 0,
    .tp_flags = Py_TPFLAGS_DEFAULT,
    .tp_new = WriteBuffer_new,
    .tp_init = (initproc) WriteBuffer_init,
    .tp_dealloc = (destructor) WriteBuffer_dealloc,
    .tp_methods = WriteBuffer_methods,
};

static inline char
_check_write_buffer(PyObject *data) {
    if (unlikely(Py_TYPE(data) != &WriteBufferType)) {
        PyErr_Format(
            PyExc_TypeError, "data must be a WriteBuffer object, got %s", Py_TYPE(data)->tp_name
        );
        return CPY_NONE_ERROR;
    }
    return CPY_NONE;
}

static inline char
_check_size(WriteBufferObject *data, Py_ssize_t need) {
    if (data->end - data->ptr >= need)
        return CPY_NONE;
    Py_ssize_t index = data->ptr - data->buf;
    Py_ssize_t target = index + need;
    Py_ssize_t size = data->end - data->buf;
    do {
        size *= 2;
    } while (target >= size);
    data->buf = PyMem_Realloc(data->buf, size);
    if (unlikely(data->buf == NULL)) {
        PyErr_NoMemory();
        return CPY_NONE_ERROR;
    }
    data->ptr = data->buf + index;
    data->end = data->buf + size;
    return CPY_NONE;
}

static inline char
_check_read(ReadBufferObject *data, Py_ssize_t need) {
    if (unlikely((data->end - data->ptr) < need)) {
        PyErr_SetString(PyExc_ValueError, "reading past the buffer end");
        return CPY_NONE_ERROR;
    }
    return CPY_NONE;
}

static char
write_bytes_internal(PyObject *data, PyObject *value) {
    const char *chunk = PyBytes_AsString(value);
    if (unlikely(chunk == NULL))
        return CPY_NONE_ERROR;
    Py_ssize_t size = PyBytes_GET_SIZE(value);

    // Write length.
    if (likely(size >= MIN_FOUR_BYTES_INT && size <= MAX_FOUR_BYTES_INT)) {
        if (_write_short_int(data, size) == CPY_NONE_ERROR)
            return CPY_NONE_ERROR;
    } else {
        PyErr_SetString(PyExc_ValueError, "bytes too long to serialize");
        return CPY_NONE_ERROR;
    }
    // Write bytes content.
    _CHECK_WRITE(data, size)
    char *ptr = ((WriteBufferObject *)data)->ptr;
    memcpy(ptr, chunk, size);
    ((WriteBufferObject *)data)->ptr += size;
    return CPY_NONE;
}

static PyObject*
write_bytes(PyObject *self, PyObject *const *args, size_t nargs, PyObject *kwnames) {
    static const char * const kwlist[] = {"data", "value", 0};
    static CPyArg_Parser parser = {"OO:write_bytes", kwlist, 0};
    PyObject *data;
    PyObject *value;
    if (unlikely(!CPyArg_ParseStackAndKeywordsSimple(args, nargs, kwnames, &parser, &data, &value))) {
        return NULL;
    }
    _CHECK_WRITE_BUFFER(data, NULL)
    if (unlikely(!PyBytes_Check(value))) {
        PyErr_SetString(PyExc_TypeError, "value must be a bytes object");
        return NULL;
    }
    if (unlikely(write_bytes_internal(data, value) == CPY_NONE_ERROR)) {
        return NULL;
    }
    Py_INCREF(Py_None);
    return Py_None;
}

static char
write_tag_internal(PyObject *data, uint8_t value) {
    _CHECK_WRITE(data, 1)
    _WRITE(data, uint8_t, value);
    return CPY_NONE;
}

static PyObject*
write_tag(PyObject *self, PyObject *const *args, size_t nargs, PyObject *kwnames) {
    static const char * const kwlist[] = {"data", "value", 0};
    static CPyArg_Parser parser = {"OO:write_tag", kwlist, 0};
    PyObject *data;
    PyObject *value;
    if (unlikely(!CPyArg_ParseStackAndKeywordsSimple(args, nargs, kwnames, &parser, &data, &value))) {
        return NULL;
    }
    _CHECK_WRITE_BUFFER(data, NULL)
    uint8_t unboxed = CPyLong_AsUInt8(value);
    if (unlikely(unboxed == CPY_LL_UINT_ERROR && PyErr_Occurred())) {
        CPy_TypeError("u8", value);
        return NULL;
    }
    if (unlikely(write_tag_internal(data, unboxed) == CPY_NONE_ERROR)) {
        return NULL;
    }
    Py_INCREF(Py_None);
    return Py_None;
}

static PyTypeObject *
WriteBuffer_type_internal(void) {
    return &WriteBufferType;  // Return borrowed reference
};

static PyMethodDef librt_internal_module_methods[] = {
    {"write_bool", (PyCFunction)write_bool, METH_FASTCALL | METH_KEYWORDS, PyDoc_STR("write a bool")},
    {"read_bool", (PyCFunction)read_bool, METH_FASTCALL | METH_KEYWORDS, PyDoc_STR("read a bool")},
    {"write_str", (PyCFunction)write_str, METH_FASTCALL | METH_KEYWORDS, PyDoc_STR("write a string")},
    {"read_str", (PyCFunction)read_str, METH_FASTCALL | METH_KEYWORDS, PyDoc_STR("read a string")},
    {"write_bytes", (PyCFunction)write_bytes, METH_FASTCALL | METH_KEYWORDS, PyDoc_STR("write bytes")},
    {"read_bytes", (PyCFunction)read_bytes, METH_FASTCALL | METH_KEYWORDS, PyDoc_STR("read bytes")},
    {"write_float", (PyCFunction)write_float, METH_FASTCALL | METH_KEYWORDS, PyDoc_STR("write a float")},
    {"read_float", (PyCFunction)read_float, METH_FASTCALL | METH_KEYWORDS, PyDoc_STR("read a float")},
    {"write_int", (PyCFunction)write_int, METH_FASTCALL | METH_KEYWORDS, PyDoc_STR("write an int")},
    {"read_int", (PyCFunction)read_int, METH_FASTCALL | METH_KEYWORDS, PyDoc_STR("read an int")},
    {"write_tag", (PyCFunction)write_tag, METH_FASTCALL | METH_KEYWORDS, PyDoc_STR("write a short int")},
    {"read_tag", (PyCFunction)read_tag, METH_FASTCALL | METH_KEYWORDS, PyDoc_STR("read a short int")},
    {"cache_version", (PyCFunction)cache_version, METH_NOARGS, PyDoc_STR("cache format version")},
    {NULL, NULL, 0, NULL}
};

static int
NativeInternal_ABI_Version(void) {
    return LIBRT_INTERNAL_ABI_VERSION;
}

static int
NativeInternal_API_Version(void) {
    return LIBRT_INTERNAL_API_VERSION;
}

static int
librt_internal_module_exec(PyObject *m)
{
    if (PyType_Ready(&WriteBufferType) < 0) {
        return -1;
    }
    if (PyModule_AddObjectRef(m, "WriteBuffer", (PyObject *) &WriteBufferType) < 0) {
        return -1;
    }

    // Export mypy internal C API, be careful with the order!
    static void *NativeInternal_API[LIBRT_INTERNAL_API_LEN] = {
        (void *)NativeInternal_ABI_Version,
        (void *)NativeInternal_API_Version,
        (void *)WriteBuffer_internal,
        (void *)WriteBuffer_getvalue_internal,
        (void *)write_tag_internal,
        (void *)write_bytes_internal,
        (void *)WriteBuffer_type_internal,
    };
    PyObject *c_api_object = PyCapsule_New((void *)NativeInternal_API, "librt.internal._C_API", NULL);
    if (PyModule_Add(m, "_C_API", c_api_object) < 0) {
        return -1;
    }
    return 0;
}

static PyModuleDef_Slot librt_internal_module_slots[] = {
    {Py_mod_exec, librt_internal_module_exec},
#ifdef Py_MOD_GIL_NOT_USED
    {Py_mod_gil, Py_MOD_GIL_NOT_USED},
#endif
    {0, NULL}
};

static PyModuleDef librt_internal_module = {
    .m_base = PyModuleDef_HEAD_INIT,
    .m_name = "internal",
    .m_doc = "Mypy cache serialization utils",
    .m_size = 0,
    .m_methods = librt_internal_module_methods,
    .m_slots = librt_internal_module_slots,
};

PyMODINIT_FUNC
PyInit_internal(void)
{
    return PyModuleDef_Init(&librt_internal_module);
}
