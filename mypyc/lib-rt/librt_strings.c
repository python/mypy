#include "pythoncapi_compat.h"

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdint.h>
#include "CPy.h"
#include "librt_strings.h"

#define CPY_BOOL_ERROR 2

//
// BytesWriter
//

#define _WRITE(data, type, v) \
    do { \
       *(type *)(((BytesWriterObject *)data)->buf + ((BytesWriterObject *)data)->len) = v; \
       ((BytesWriterObject *)data)->len += sizeof(type); \
    } while (0)

#ifdef MYPYC_EXPERIMENTAL

static PyTypeObject BytesWriterType;

static bool
_grow_buffer(BytesWriterObject *data, Py_ssize_t n) {
    Py_ssize_t target = data->len + n;
    Py_ssize_t size = data->capacity;
    do {
        size *= 2;
    } while (target >= size);
    if (data->buf == data->data) {
        // Move from embedded buffer to heap-allocated buffer
        data->buf = PyMem_Malloc(size);
        if (data->buf != NULL) {
            memcpy(data->buf, data->data, WRITER_EMBEDDED_BUF_LEN);
        }
    } else {
        data->buf = PyMem_Realloc(data->buf, size);
    }
    if (unlikely(data->buf == NULL)) {
        PyErr_NoMemory();
        return false;
    }
    data->capacity = size;
    return true;
}

static inline bool
ensure_bytes_writer_size(BytesWriterObject *data, Py_ssize_t n) {
    if (likely(data->capacity - data->len >= n)) {
        return true;
    } else {
        return _grow_buffer(data, n);
    }
}

static inline void
BytesWriter_init_internal(BytesWriterObject *self) {
    self->buf = self->data;
    self->len = 0;
    self->capacity = WRITER_EMBEDDED_BUF_LEN;
}

static PyObject*
BytesWriter_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    if (type != &BytesWriterType) {
        PyErr_SetString(PyExc_TypeError, "BytesWriter cannot be subclassed");
        return NULL;
    }

    BytesWriterObject *self = (BytesWriterObject *)type->tp_alloc(type, 0);
    if (self != NULL) {
        BytesWriter_init_internal(self);
    }
    return (PyObject *)self;
}

static PyObject *
BytesWriter_internal(void) {
    BytesWriterObject *self = (BytesWriterObject *)BytesWriterType.tp_alloc(&BytesWriterType, 0);
    if (self == NULL)
        return NULL;
    BytesWriter_init_internal(self);
    return (PyObject *)self;
}

static int
BytesWriter_init(BytesWriterObject *self, PyObject *args, PyObject *kwds)
{
    if (!PyArg_ParseTuple(args, "")) {
        return -1;
    }

    if (kwds != NULL && PyDict_Size(kwds) > 0) {
        PyErr_SetString(PyExc_TypeError,
                        "BytesWriter() takes no keyword arguments");
        return -1;
    }

    BytesWriter_init_internal(self);
    return 0;
}

static void
BytesWriter_dealloc(BytesWriterObject *self)
{
    if (self->buf != self->data) {
        PyMem_Free(self->buf);
        self->buf = NULL;
    }
    Py_TYPE(self)->tp_free((PyObject *)self);
}

static PyObject*
BytesWriter_getvalue_internal(PyObject *self)
{
    BytesWriterObject *obj = (BytesWriterObject *)self;
    return PyBytes_FromStringAndSize(obj->buf, obj->len);
}

static PyObject*
BytesWriter_repr(BytesWriterObject *self)
{
    PyObject *value = BytesWriter_getvalue_internal((PyObject *)self);
    if (value == NULL) {
        return NULL;
    }
    PyObject *value_repr = PyObject_Repr(value);
    Py_DECREF(value);
    if (value_repr == NULL) {
        return NULL;
    }
    PyObject *result = PyUnicode_FromFormat("BytesWriter(%U)", value_repr);
    Py_DECREF(value_repr);
    return result;
}

static PyObject*
BytesWriter_getvalue(BytesWriterObject *self, PyObject *Py_UNUSED(ignored))
{
    return PyBytes_FromStringAndSize(self->buf, self->len);
}

static Py_ssize_t
BytesWriter_length(BytesWriterObject *self)
{
    return self->len;
}

static PyObject*
BytesWriter_item(BytesWriterObject *self, Py_ssize_t index)
{
    Py_ssize_t length = self->len;

    // Check bounds
    if (index < 0 || index >= length) {
        PyErr_SetString(PyExc_IndexError, "BytesWriter index out of range");
        return NULL;
    }

    // Return the byte at the given index as a Python int
    return PyLong_FromLong((unsigned char)self->buf[index]);
}

static int
BytesWriter_ass_item(BytesWriterObject *self, Py_ssize_t index, PyObject *value)
{
    Py_ssize_t length = self->len;

    // Check bounds
    if (index < 0 || index >= length) {
        PyErr_SetString(PyExc_IndexError, "BytesWriter index out of range");
        return -1;
    }

    // Check that value is not NULL (deletion not supported)
    if (value == NULL) {
        PyErr_SetString(PyExc_TypeError, "BytesWriter does not support item deletion");
        return -1;
    }

    // Convert value to uint8
    uint8_t byte_value = CPyLong_AsUInt8(value);
    if (unlikely(byte_value == CPY_LL_UINT_ERROR && PyErr_Occurred())) {
        CPy_TypeError("u8", value);
        return -1;
    }

    // Assign the byte
    self->buf[index] = (char)byte_value;
    return 0;
}

static PySequenceMethods BytesWriter_as_sequence = {
    .sq_length = (lenfunc)BytesWriter_length,
    .sq_item = (ssizeargfunc)BytesWriter_item,
    .sq_ass_item = (ssizeobjargproc)BytesWriter_ass_item,
};

static PyObject* BytesWriter_append(PyObject *self, PyObject *const *args, size_t nargs, PyObject *kwnames);
static PyObject* BytesWriter_write(PyObject *self, PyObject *const *args, size_t nargs, PyObject *kwnames);
static PyObject* BytesWriter_truncate(PyObject *self, PyObject *const *args, size_t nargs);

static PyMethodDef BytesWriter_methods[] = {
    {"append", (PyCFunction) BytesWriter_append, METH_FASTCALL | METH_KEYWORDS,
     PyDoc_STR("Append a single byte to the buffer")
    },
    {"write", (PyCFunction) BytesWriter_write, METH_FASTCALL | METH_KEYWORDS,
     PyDoc_STR("Append bytes to the buffer")
    },
    {"getvalue", (PyCFunction) BytesWriter_getvalue, METH_NOARGS,
     "Return the buffer content as bytes object"
    },
    {"truncate", (PyCFunction) BytesWriter_truncate, METH_FASTCALL,
     PyDoc_STR("Truncate the buffer to the specified size")
    },
    {NULL}  /* Sentinel */
};

static PyTypeObject BytesWriterType = {
    .ob_base = PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "BytesWriter",
    .tp_doc = PyDoc_STR("Memory buffer for building bytes objects from parts"),
    .tp_basicsize = sizeof(BytesWriterObject),
    .tp_itemsize = 0,
    .tp_flags = Py_TPFLAGS_DEFAULT,
    .tp_new = BytesWriter_new,
    .tp_init = (initproc) BytesWriter_init,
    .tp_dealloc = (destructor) BytesWriter_dealloc,
    .tp_methods = BytesWriter_methods,
    .tp_as_sequence = &BytesWriter_as_sequence,
    .tp_repr = (reprfunc)BytesWriter_repr,
};

static inline bool
check_bytes_writer(PyObject *data) {
    if (unlikely(Py_TYPE(data) != &BytesWriterType)) {
        PyErr_Format(
            PyExc_TypeError, "data must be a BytesWriter object, got %s", Py_TYPE(data)->tp_name
        );
        return false;
    }
    return true;
}

static char
BytesWriter_write_internal(BytesWriterObject *self, PyObject *value) {
    const char *data;
    Py_ssize_t size;
    if (likely(PyBytes_Check(value))) {
        data = PyBytes_AS_STRING(value);
        size = PyBytes_GET_SIZE(value);
    } else {
        data = PyByteArray_AS_STRING(value);
        size = PyByteArray_GET_SIZE(value);
    }
    // Write bytes content.
    if (!ensure_bytes_writer_size(self, size))
        return CPY_NONE_ERROR;
    memcpy(self->buf + self->len, data, size);
    self->len += size;
    return CPY_NONE;
}

static PyObject*
BytesWriter_write(PyObject *self, PyObject *const *args, size_t nargs, PyObject *kwnames) {
    static const char * const kwlist[] = {"value", 0};
    static CPyArg_Parser parser = {"O:write", kwlist, 0};
    PyObject *value;
    if (unlikely(!CPyArg_ParseStackAndKeywordsSimple(args, nargs, kwnames, &parser, &value))) {
        return NULL;
    }
    if (!check_bytes_writer(self)) {
        return NULL;
    }
    if (unlikely(!PyBytes_Check(value) && !PyByteArray_Check(value))) {
        PyErr_SetString(PyExc_TypeError, "value must be a bytes or bytearray object");
        return NULL;
    }
    if (unlikely(BytesWriter_write_internal((BytesWriterObject *)self, value) == CPY_NONE_ERROR)) {
        return NULL;
    }
    Py_INCREF(Py_None);
    return Py_None;
}

static inline char
BytesWriter_append_internal(BytesWriterObject *self, uint8_t value) {
    if (!ensure_bytes_writer_size(self, 1))
        return CPY_NONE_ERROR;
    _WRITE(self, uint8_t, value);
    return CPY_NONE;
}

static PyObject*
BytesWriter_append(PyObject *self, PyObject *const *args, size_t nargs, PyObject *kwnames) {
    static const char * const kwlist[] = {"value", 0};
    static CPyArg_Parser parser = {"O:append", kwlist, 0};
    PyObject *value;
    if (unlikely(!CPyArg_ParseStackAndKeywordsSimple(args, nargs, kwnames, &parser, &value))) {
        return NULL;
    }
    if (!check_bytes_writer(self)) {
        return NULL;
    }
    uint8_t unboxed = CPyLong_AsUInt8(value);
    if (unlikely(unboxed == CPY_LL_UINT_ERROR && PyErr_Occurred())) {
        CPy_TypeError("u8", value);
        return NULL;
    }
    if (unlikely(BytesWriter_append_internal((BytesWriterObject *)self, unboxed) == CPY_NONE_ERROR)) {
        return NULL;
    }
    Py_INCREF(Py_None);
    return Py_None;
}

static char
BytesWriter_truncate_internal(PyObject *self, int64_t size) {
    BytesWriterObject *writer = (BytesWriterObject *)self;
    Py_ssize_t current_size = writer->len;

    // Validate size is non-negative
    if (size < 0) {
        PyErr_SetString(PyExc_ValueError, "size must be non-negative");
        return CPY_NONE_ERROR;
    }

    // Validate size doesn't exceed current size
    if (size > current_size) {
        PyErr_SetString(PyExc_ValueError, "size cannot be larger than current buffer size");
        return CPY_NONE_ERROR;
    }

    writer->len = size;
    return CPY_NONE;
}

static PyObject*
BytesWriter_truncate(PyObject *self, PyObject *const *args, size_t nargs) {
    if (unlikely(nargs != 1)) {
        PyErr_Format(PyExc_TypeError,
                     "truncate() takes exactly 1 argument (%zu given)", nargs);
        return NULL;
    }
    if (!check_bytes_writer(self)) {
        return NULL;
    }

    PyObject *size_obj = args[0];
    int overflow;
    long long size = PyLong_AsLongLongAndOverflow(size_obj, &overflow);

    if (size == -1 && PyErr_Occurred()) {
        return NULL;
    }
    if (overflow != 0) {
        PyErr_SetString(PyExc_ValueError, "integer out of range");
        return NULL;
    }

    if (unlikely(BytesWriter_truncate_internal(self, size) == CPY_NONE_ERROR)) {
        return NULL;
    }
    Py_INCREF(Py_None);
    return Py_None;
}

static PyTypeObject *
BytesWriter_type_internal(void) {
    return &BytesWriterType;  // Return borrowed reference
};

static CPyTagged
BytesWriter_len_internal(PyObject *self) {
    BytesWriterObject *writer = (BytesWriterObject *)self;
    return writer->len << 1;
}

#endif

static PyMethodDef librt_strings_module_methods[] = {
    {NULL, NULL, 0, NULL}
};

#ifdef MYPYC_EXPERIMENTAL

static int
strings_abi_version(void) {
    return LIBRT_STRINGS_ABI_VERSION;
}

static int
strings_api_version(void) {
    return LIBRT_STRINGS_API_VERSION;
}

#endif

static int
librt_strings_module_exec(PyObject *m)
{
#ifdef MYPYC_EXPERIMENTAL
    if (PyType_Ready(&BytesWriterType) < 0) {
        return -1;
    }
    if (PyModule_AddObjectRef(m, "BytesWriter", (PyObject *) &BytesWriterType) < 0) {
        return -1;
    }

    // Export mypy internal C API, be careful with the order!
    static void *librt_strings_api[LIBRT_STRINGS_API_LEN] = {
        (void *)strings_abi_version,
        (void *)strings_api_version,
        (void *)BytesWriter_internal,
        (void *)BytesWriter_getvalue_internal,
        (void *)BytesWriter_append_internal,
        (void *)_grow_buffer,
        (void *)BytesWriter_type_internal,
        (void *)BytesWriter_truncate_internal,
    };
    PyObject *c_api_object = PyCapsule_New((void *)librt_strings_api, "librt.strings._C_API", NULL);
    if (PyModule_Add(m, "_C_API", c_api_object) < 0) {
        return -1;
    }
#endif
    return 0;
}

static PyModuleDef_Slot librt_strings_module_slots[] = {
    {Py_mod_exec, librt_strings_module_exec},
#ifdef Py_MOD_GIL_NOT_USED
    {Py_mod_gil, Py_MOD_GIL_NOT_USED},
#endif
    {0, NULL}
};

static PyModuleDef librt_strings_module = {
    .m_base = PyModuleDef_HEAD_INIT,
    .m_name = "strings",
    .m_doc = "Utilities for working with str and bytes objects",
    .m_size = 0,
    .m_methods = librt_strings_module_methods,
    .m_slots = librt_strings_module_slots,
};

PyMODINIT_FUNC
PyInit_strings(void)
{
    intern_strings();
    return PyModuleDef_Init(&librt_strings_module);
}
