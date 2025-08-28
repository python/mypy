#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdint.h>
#include "CPy.h"
#define NATIVE_INTERNAL_MODULE
#include "native_internal.h"

#define START_SIZE 512
#define MAX_SHORT_INT_TAGGED (255 << 1)

typedef struct {
    PyObject_HEAD
    Py_ssize_t pos;
    Py_ssize_t end;
    Py_ssize_t size;
    char *buf;
    PyObject *source;
} BufferObject;

static PyTypeObject BufferType;

static PyObject*
Buffer_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    if (type != &BufferType) {
        PyErr_SetString(PyExc_TypeError, "Buffer should not be subclassed");
        return NULL;
    }

    BufferObject *self = (BufferObject *)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->pos = 0;
        self->end = 0;
        self->size = 0;
        self->buf = NULL;
    }
    return (PyObject *) self;
}


static int
Buffer_init_internal(BufferObject *self, PyObject *source) {
    if (source) {
        if (!PyBytes_Check(source)) {
            PyErr_SetString(PyExc_TypeError, "source must be a bytes object");
            return -1;
        }
        self->size = PyBytes_GET_SIZE(source);
        self->end = self->size;
        // This returns a pointer to internal bytes data, so make our own copy.
        char *buf = PyBytes_AsString(source);
        self->buf = PyMem_Malloc(self->size);
        memcpy(self->buf, buf, self->size);
    } else {
        self->buf = PyMem_Malloc(START_SIZE);
        self->size = START_SIZE;
    }
    return 0;
}

static PyObject*
Buffer_internal(PyObject *source) {
    BufferObject *self = (BufferObject *)BufferType.tp_alloc(&BufferType, 0);
    if (self == NULL)
        return NULL;
    self->pos = 0;
    self->end = 0;
    self->size = 0;
    self->buf = NULL;
    if (Buffer_init_internal(self, source) == -1) {
        Py_DECREF(self);
        return NULL;
    }
    return (PyObject *)self;
}

static PyObject*
Buffer_internal_empty(void) {
    return Buffer_internal(NULL);
}

static int
Buffer_init(BufferObject *self, PyObject *args, PyObject *kwds)
{
    static char *kwlist[] = {"source", NULL};
    PyObject *source = NULL;

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "|O", kwlist, &source))
        return -1;

    return Buffer_init_internal(self, source);
}

static void
Buffer_dealloc(BufferObject *self)
{
    PyMem_Free(self->buf);
    Py_TYPE(self)->tp_free((PyObject *)self);
}

static PyObject*
Buffer_getvalue_internal(PyObject *self)
{
    return PyBytes_FromStringAndSize(((BufferObject *)self)->buf, ((BufferObject *)self)->end);
}

static PyObject*
Buffer_getvalue(BufferObject *self, PyObject *Py_UNUSED(ignored))
{
    return PyBytes_FromStringAndSize(self->buf, self->end);
}

static PyMethodDef Buffer_methods[] = {
    {"getvalue", (PyCFunction) Buffer_getvalue, METH_NOARGS,
     "Return the buffer content as bytes object"
    },
    {NULL}  /* Sentinel */
};

static PyTypeObject BufferType = {
    .ob_base = PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "Buffer",
    .tp_doc = PyDoc_STR("Mypy cache buffer objects"),
    .tp_basicsize = sizeof(BufferObject),
    .tp_itemsize = 0,
    .tp_flags = Py_TPFLAGS_DEFAULT,
    .tp_new = Buffer_new,
    .tp_init = (initproc) Buffer_init,
    .tp_dealloc = (destructor) Buffer_dealloc,
    .tp_methods = Buffer_methods,
};

static inline char
_check_buffer(PyObject *data) {
    if (Py_TYPE(data) != &BufferType) {
        PyErr_Format(
            PyExc_TypeError, "data must be a Buffer object, got %s", Py_TYPE(data)->tp_name
        );
        return 2;
    }
    return 1;
}

static inline char
_check_size(BufferObject *data, Py_ssize_t need) {
    Py_ssize_t target = data->pos + need;
    if (target <= data->size)
        return 1;
    do
        data->size *= 2;
    while (target >= data->size);
    data->buf = PyMem_Realloc(data->buf, data->size);
    if (!data->buf) {
        PyErr_NoMemory();
        return 2;
    }
    return 1;
}

static inline char
_check_read(BufferObject *data, Py_ssize_t need) {
    if (data->pos + need > data->end) {
        PyErr_SetString(PyExc_ValueError, "reading past the buffer end");
        return 2;
    }
    return 1;
}

static char
read_bool_internal(PyObject *data) {
    if (_check_buffer(data) == 2)
        return 2;

    if (_check_read((BufferObject *)data, 1) == 2)
        return 2;
    char *buf = ((BufferObject *)data)->buf;
    char res = buf[((BufferObject *)data)->pos];
    ((BufferObject *)data)->pos += 1;
    return res;
}

static PyObject*
read_bool(PyObject *self, PyObject *args, PyObject *kwds) {
    static char *kwlist[] = {"data", NULL};
    PyObject *data = NULL;
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "O", kwlist, &data))
        return NULL;
    char res = read_bool_internal(data);
    if (res == 2)
        return NULL;
    PyObject *retval = res ? Py_True : Py_False;
    Py_INCREF(retval);
    return retval;
}

static char
write_bool_internal(PyObject *data, char value) {
    if (_check_buffer(data) == 2)
        return 2;

    if (_check_size((BufferObject *)data, 1) == 2)
        return 2;
    char *buf = ((BufferObject *)data)->buf;
    buf[((BufferObject *)data)->pos] = value;
    ((BufferObject *)data)->pos += 1;
    ((BufferObject *)data)->end += 1;
    return 1;
}

static PyObject*
write_bool(PyObject *self, PyObject *args, PyObject *kwds) {
    static char *kwlist[] = {"data", "value", NULL};
    PyObject *data = NULL;
    PyObject *value = NULL;
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "OO", kwlist, &data, &value))
        return NULL;
    if (!PyBool_Check(value)) {
        PyErr_SetString(PyExc_TypeError, "value must be a bool");
        return NULL;
    }
    if (write_bool_internal(data, value == Py_True) == 2) {
        return NULL;
    }
    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject*
read_str_internal(PyObject *data) {
    if (_check_buffer(data) == 2)
        return NULL;

    if (_check_read((BufferObject *)data, sizeof(Py_ssize_t)) == 2)
        return NULL;
    char *buf = ((BufferObject *)data)->buf;
    // Read string length.
    Py_ssize_t size = *(Py_ssize_t *)(buf + ((BufferObject *)data)->pos);
    ((BufferObject *)data)->pos += sizeof(Py_ssize_t);
    if (_check_read((BufferObject *)data, size) == 2)
        return NULL;
    // Read string content.
    PyObject *res = PyUnicode_FromStringAndSize(
        buf + ((BufferObject *)data)->pos, (Py_ssize_t)size
    );
    if (!res)
        return NULL;
    ((BufferObject *)data)->pos += size;
    return res;
}

static PyObject*
read_str(PyObject *self, PyObject *args, PyObject *kwds) {
    static char *kwlist[] = {"data", NULL};
    PyObject *data = NULL;
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "O", kwlist, &data))
        return NULL;
    return read_str_internal(data);
}

static char
write_str_internal(PyObject *data, PyObject *value) {
    if (_check_buffer(data) == 2)
        return 2;

    Py_ssize_t size;
    const char *chunk = PyUnicode_AsUTF8AndSize(value, &size);
    if (!chunk)
        return 2;
    Py_ssize_t need = size + sizeof(Py_ssize_t);
    if (_check_size((BufferObject *)data, need) == 2)
        return 2;

    char *buf = ((BufferObject *)data)->buf;
    // Write string length.
    *(Py_ssize_t *)(buf + ((BufferObject *)data)->pos) = size;
    ((BufferObject *)data)->pos += sizeof(Py_ssize_t);
    // Write string content.
    memcpy(buf + ((BufferObject *)data)->pos, chunk, size);
    ((BufferObject *)data)->pos += size;
    ((BufferObject *)data)->end += need;
    return 1;
}

static PyObject*
write_str(PyObject *self, PyObject *args, PyObject *kwds) {
    static char *kwlist[] = {"data", "value", NULL};
    PyObject *data = NULL;
    PyObject *value = NULL;
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "OO", kwlist, &data, &value))
        return NULL;
    if (!PyUnicode_Check(value)) {
        PyErr_SetString(PyExc_TypeError, "value must be a str");
        return NULL;
    }
    if (write_str_internal(data, value) == 2) {
        return NULL;
    }
    Py_INCREF(Py_None);
    return Py_None;
}

static double
read_float_internal(PyObject *data) {
    if (_check_buffer(data) == 2)
        return CPY_FLOAT_ERROR;

    if (_check_read((BufferObject *)data, sizeof(double)) == 2)
        return CPY_FLOAT_ERROR;
    char *buf = ((BufferObject *)data)->buf;
    double res = *(double *)(buf + ((BufferObject *)data)->pos);
    ((BufferObject *)data)->pos += sizeof(double);
    return res;
}

static PyObject*
read_float(PyObject *self, PyObject *args, PyObject *kwds) {
    static char *kwlist[] = {"data", NULL};
    PyObject *data = NULL;
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "O", kwlist, &data))
        return NULL;
    double retval = read_float_internal(data);
    if (retval == CPY_FLOAT_ERROR && PyErr_Occurred()) {
        return NULL;
    }
    return PyFloat_FromDouble(retval);
}

static char
write_float_internal(PyObject *data, double value) {
    if (_check_buffer(data) == 2)
        return 2;

    if (_check_size((BufferObject *)data, sizeof(double)) == 2)
        return 2;
    char *buf = ((BufferObject *)data)->buf;
    *(double *)(buf + ((BufferObject *)data)->pos) = value;
    ((BufferObject *)data)->pos += sizeof(double);
    ((BufferObject *)data)->end += sizeof(double);
    return 1;
}

static PyObject*
write_float(PyObject *self, PyObject *args, PyObject *kwds) {
    static char *kwlist[] = {"data", "value", NULL};
    PyObject *data = NULL;
    PyObject *value = NULL;
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "OO", kwlist, &data, &value))
        return NULL;
    if (!PyFloat_Check(value)) {
        PyErr_SetString(PyExc_TypeError, "value must be a float");
        return NULL;
    }
    if (write_float_internal(data, PyFloat_AsDouble(value)) == 2) {
        return NULL;
    }
    Py_INCREF(Py_None);
    return Py_None;
}

static CPyTagged
read_int_internal(PyObject *data) {
    if (_check_buffer(data) == 2)
        return CPY_INT_TAG;

    if (_check_read((BufferObject *)data, sizeof(CPyTagged)) == 2)
        return CPY_INT_TAG;
    char *buf = ((BufferObject *)data)->buf;

    CPyTagged ret = *(CPyTagged *)(buf + ((BufferObject *)data)->pos);
    ((BufferObject *)data)->pos += sizeof(CPyTagged);
    if ((ret & CPY_INT_TAG) == 0)
        return ret;
    // People who have literal ints not fitting in size_t should be punished :-)
    PyObject *str_ret = read_str_internal(data);
    if (str_ret == NULL)
        return CPY_INT_TAG;
    PyObject* ret_long = PyLong_FromUnicodeObject(str_ret, 10);
    Py_DECREF(str_ret);
    return ((CPyTagged)ret_long) | CPY_INT_TAG;
}

static PyObject*
read_int(PyObject *self, PyObject *args, PyObject *kwds) {
    static char *kwlist[] = {"data", NULL};
    PyObject *data = NULL;
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "O", kwlist, &data))
        return NULL;
    CPyTagged retval = read_int_internal(data);
    if (retval == CPY_INT_TAG) {
        return NULL;
    }
    return CPyTagged_StealAsObject(retval);
}

static char
write_int_internal(PyObject *data, CPyTagged value) {
    if (_check_buffer(data) == 2)
        return 2;

    if (_check_size((BufferObject *)data, sizeof(CPyTagged)) == 2)
        return 2;
    char *buf = ((BufferObject *)data)->buf;
    if ((value & CPY_INT_TAG) == 0) {
        *(CPyTagged *)(buf + ((BufferObject *)data)->pos) = value;
    } else {
        *(CPyTagged *)(buf + ((BufferObject *)data)->pos) = CPY_INT_TAG;
    }
    ((BufferObject *)data)->pos += sizeof(CPyTagged);
    ((BufferObject *)data)->end += sizeof(CPyTagged);
    if ((value & CPY_INT_TAG) != 0) {
        PyObject *str_value = PyObject_Str(CPyTagged_LongAsObject(value));
        if (str_value == NULL)
            return 2;
        char res = write_str_internal(data, str_value);
        Py_DECREF(str_value);
        if (res == 2)
            return 2;
    }
    return 1;
}

static PyObject*
write_int(PyObject *self, PyObject *args, PyObject *kwds) {
    static char *kwlist[] = {"data", "value", NULL};
    PyObject *data = NULL;
    PyObject *value = NULL;
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "OO", kwlist, &data, &value))
        return NULL;
    if (!PyLong_Check(value)) {
        PyErr_SetString(PyExc_TypeError, "value must be an int");
        return NULL;
    }
    CPyTagged tagged_value = CPyTagged_BorrowFromObject(value);
    if (write_int_internal(data, tagged_value) == 2) {
        return NULL;
    }
    Py_INCREF(Py_None);
    return Py_None;
}

static uint8_t
read_tag_internal(PyObject *data) {
    if (_check_buffer(data) == 2)
        return CPY_LL_UINT_ERROR;

    if (_check_read((BufferObject *)data, 1) == 2)
        return CPY_LL_UINT_ERROR;
    char *buf = ((BufferObject *)data)->buf;

    uint8_t ret = *(uint8_t *)(buf + ((BufferObject *)data)->pos);
    ((BufferObject *)data)->pos += 1;
    return ret;
}

static PyObject*
read_tag(PyObject *self, PyObject *args, PyObject *kwds) {
    static char *kwlist[] = {"data", NULL};
    PyObject *data = NULL;
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "O", kwlist, &data))
        return NULL;
    uint8_t retval = read_tag_internal(data);
    if (retval == CPY_LL_UINT_ERROR && PyErr_Occurred()) {
        return NULL;
    }
    return PyLong_FromLong(retval);
}

static char
write_tag_internal(PyObject *data, uint8_t value) {
    if (_check_buffer(data) == 2)
        return 2;

    if (_check_size((BufferObject *)data, 1) == 2)
        return 2;
    uint8_t *buf = (uint8_t *)((BufferObject *)data)->buf;
    *(buf + ((BufferObject *)data)->pos) = value;
    ((BufferObject *)data)->pos += 1;
    ((BufferObject *)data)->end += 1;
    return 1;
}

static PyObject*
write_tag(PyObject *self, PyObject *args, PyObject *kwds) {
    static char *kwlist[] = {"data", "value", NULL};
    PyObject *data = NULL;
    PyObject *value = NULL;
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "OO", kwlist, &data, &value))
        return NULL;
    uint8_t unboxed = CPyLong_AsUInt8(value);
    if (unboxed == CPY_LL_UINT_ERROR && PyErr_Occurred()) {
        CPy_TypeError("u8", value);
        return NULL;
    }
    if (write_tag_internal(data, unboxed) == 2) {
        return NULL;
    }
    Py_INCREF(Py_None);
    return Py_None;
}

static PyMethodDef native_internal_module_methods[] = {
    // TODO: switch public wrappers to METH_FASTCALL.
    {"write_bool", (PyCFunction)write_bool, METH_VARARGS | METH_KEYWORDS, PyDoc_STR("write a bool")},
    {"read_bool", (PyCFunction)read_bool, METH_VARARGS | METH_KEYWORDS, PyDoc_STR("read a bool")},
    {"write_str", (PyCFunction)write_str, METH_VARARGS | METH_KEYWORDS, PyDoc_STR("write a string")},
    {"read_str", (PyCFunction)read_str, METH_VARARGS | METH_KEYWORDS, PyDoc_STR("read a string")},
    {"write_float", (PyCFunction)write_float, METH_VARARGS | METH_KEYWORDS, PyDoc_STR("write a float")},
    {"read_float", (PyCFunction)read_float, METH_VARARGS | METH_KEYWORDS, PyDoc_STR("read a float")},
    {"write_int", (PyCFunction)write_int, METH_VARARGS | METH_KEYWORDS, PyDoc_STR("write an int")},
    {"read_int", (PyCFunction)read_int, METH_VARARGS | METH_KEYWORDS, PyDoc_STR("read an int")},
    {"write_tag", (PyCFunction)write_tag, METH_VARARGS | METH_KEYWORDS, PyDoc_STR("write a short int")},
    {"read_tag", (PyCFunction)read_tag, METH_VARARGS | METH_KEYWORDS, PyDoc_STR("read a short int")},
    {NULL, NULL, 0, NULL}
};

static int
NativeInternal_ABI_Version(void) {
    return NATIVE_INTERNAL_ABI_VERSION;
}

static int
native_internal_module_exec(PyObject *m)
{
    if (PyType_Ready(&BufferType) < 0) {
        return -1;
    }
    if (PyModule_AddObjectRef(m, "Buffer", (PyObject *) &BufferType) < 0) {
        return -1;
    }

    // Export mypy internal C API, be careful with the order!
    static void *NativeInternal_API[14] = {
        (void *)Buffer_internal,
        (void *)Buffer_internal_empty,
        (void *)Buffer_getvalue_internal,
        (void *)write_bool_internal,
        (void *)read_bool_internal,
        (void *)write_str_internal,
        (void *)read_str_internal,
        (void *)write_float_internal,
        (void *)read_float_internal,
        (void *)write_int_internal,
        (void *)read_int_internal,
        (void *)write_tag_internal,
        (void *)read_tag_internal,
        (void *)NativeInternal_ABI_Version,
    };
    PyObject *c_api_object = PyCapsule_New((void *)NativeInternal_API, "native_internal._C_API", NULL);
    if (PyModule_Add(m, "_C_API", c_api_object) < 0) {
        return -1;
    }
    return 0;
}

static PyModuleDef_Slot native_internal_module_slots[] = {
    {Py_mod_exec, native_internal_module_exec},
#ifdef Py_MOD_GIL_NOT_USED
    {Py_mod_gil, Py_MOD_GIL_NOT_USED},
#endif
    {0, NULL}
};

static PyModuleDef native_internal_module = {
    .m_base = PyModuleDef_HEAD_INIT,
    .m_name = "native_internal",
    .m_doc = "Mypy cache serialization utils",
    .m_size = 0,
    .m_methods = native_internal_module_methods,
    .m_slots = native_internal_module_slots,
};

PyMODINIT_FUNC
PyInit_native_internal(void)
{
    return PyModuleDef_Init(&native_internal_module);
}
