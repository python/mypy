#define PY_SSIZE_T_CLEAN
#include <Python.h>

#define START_SIZE 512

#define STR_LEN_TYPE unsigned int
#define MAX_STR_SIZE (1 << sizeof(STR_LEN_TYPE) * 8)

#define FLOAT_ERR -113.0

typedef struct {
    PyObject_HEAD
    Py_ssize_t pos;
    Py_ssize_t end;
    Py_ssize_t size;
    char *buf;
    PyObject *source;
} BufferObject;

static PyTypeObject BufferType;

static PyObject *
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

PyObject *
Buffer_internal(PyObject *source) {
    // Do some lazy initialization here.
    if (PyType_Ready(&BufferType) < 0) {
        return NULL;
    }
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

PyObject *
Buffer_internal_empty() {
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

PyObject *
Buffer_getvalue_internal(PyObject *self)
{
    return PyBytes_FromStringAndSize(((BufferObject *)self)->buf, ((BufferObject *)self)->end);
}

static PyObject *
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

static inline
char _check_buffer(PyObject *data) {
    if (Py_TYPE(data) != &BufferType) {
        PyErr_SetString(PyExc_TypeError, "data must be a Buffer object");
        return 2;
    }
    return 1;
}

static inline
char _check_size(BufferObject *data, Py_ssize_t need) {
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

static inline
char _check_read(BufferObject *data, Py_ssize_t need) {
    if (data->pos + need > data->end) {
        PyErr_SetString(PyExc_ValueError, "reading past the buffer end");
        return 2;
    }
    return 1;
}

char read_bool_internal(PyObject *data) {
    if (_check_buffer(data) == 2)
        return 2;

    if (_check_read((BufferObject *)data, 1) == 2)
        return 2;
    char *buf = ((BufferObject *)data)->buf;
    char res = buf[((BufferObject *)data)->pos];
    ((BufferObject *)data)->pos += 1;
    return res;
}

PyObject *read_bool(PyObject *self, PyObject *args, PyObject *kwds) {
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

char write_bool_internal(PyObject *data, char value) {
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

PyObject *write_bool(PyObject *self, PyObject *args, PyObject *kwds) {
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

PyObject *read_str_internal(PyObject *data) {
    if (_check_buffer(data) == 2)
        return NULL;

    STR_LEN_TYPE size;
    if (_check_read((BufferObject *)data, sizeof(size)) == 2)
        return NULL;
    char *buf = ((BufferObject *)data)->buf;
    // Read string length.
    size = *(STR_LEN_TYPE *)(buf + ((BufferObject *)data)->pos);
    ((BufferObject *)data)->pos += sizeof(size);
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

PyObject *read_str(PyObject *self, PyObject *args, PyObject *kwds) {
    static char *kwlist[] = {"data", NULL};
    PyObject *data = NULL;
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "O", kwlist, &data))
        return NULL;
    return read_str_internal(data);
}

char write_str_internal(PyObject *data, PyObject *value) {
    if (_check_buffer(data) == 2)
        return 2;

    Py_ssize_t size;
    const char *chunk = PyUnicode_AsUTF8AndSize(value, &size);
    if (!chunk)
        return 2;
    if (size > MAX_STR_SIZE) {
        PyErr_Format(
            PyExc_OverflowError,
            "cannot store string longer than %d bytes",
            MAX_STR_SIZE
        );
        return 2;
    }
    Py_ssize_t need = size + sizeof(STR_LEN_TYPE);
    if (_check_size((BufferObject *)data, need) == 2)
        return 2;

    char *buf = ((BufferObject *)data)->buf;
    // Write string length.
    *(STR_LEN_TYPE *)(buf + ((BufferObject *)data)->pos) = (STR_LEN_TYPE)size;
    ((BufferObject *)data)->pos += sizeof(STR_LEN_TYPE);
    // Write string content.
    memcpy(buf + ((BufferObject *)data)->pos, chunk, size);
    ((BufferObject *)data)->pos += size;
    ((BufferObject *)data)->end += need;
    return 1;
}

PyObject *write_str(PyObject *self, PyObject *args, PyObject *kwds) {
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

double read_float_internal(PyObject *data) {
    if (_check_buffer(data) == 2)
        return FLOAT_ERR;

    if (_check_read((BufferObject *)data, sizeof(double)) == 2)
        return FLOAT_ERR;
    char *buf = ((BufferObject *)data)->buf;
    double res = *(double *)(buf + ((BufferObject *)data)->pos);
    ((BufferObject *)data)->pos += sizeof(double);
    return res;
}

PyObject *read_float(PyObject *self, PyObject *args, PyObject *kwds) {
    static char *kwlist[] = {"data", NULL};
    PyObject *data = NULL;
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "O", kwlist, &data))
        return NULL;
    double retval = read_float_internal(data);
    if (retval == FLOAT_ERR && PyErr_Occurred()) {
        return NULL;
    }
    return PyFloat_FromDouble(retval);
}

char write_float_internal(PyObject *data, double value) {
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

PyObject *write_float(PyObject *self, PyObject *args, PyObject *kwds) {
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

static PyMethodDef native_buffer_module_methods[] = {
    {"write_bool", (PyCFunction)write_bool, METH_VARARGS | METH_KEYWORDS, PyDoc_STR("write a bool")},
    {"read_bool", (PyCFunction)read_bool, METH_VARARGS | METH_KEYWORDS, PyDoc_STR("read a bool")},
    {"write_str", (PyCFunction)write_str, METH_VARARGS | METH_KEYWORDS, PyDoc_STR("write a string")},
    {"read_str", (PyCFunction)read_str, METH_VARARGS | METH_KEYWORDS, PyDoc_STR("read a string")},
    {"write_float", (PyCFunction)write_float, METH_VARARGS | METH_KEYWORDS, PyDoc_STR("write a float")},
    {"read_float", (PyCFunction)read_float, METH_VARARGS | METH_KEYWORDS, PyDoc_STR("read a float")},
    {NULL, NULL, 0, NULL}
};

static int
native_buffer_module_exec(PyObject *m)
{
    if (PyType_Ready(&BufferType) < 0) {
        return -1;
    }
    if (PyModule_AddObjectRef(m, "Buffer", (PyObject *) &BufferType) < 0) {
        return -1;
    }
    return 0;
}

static PyModuleDef_Slot native_buffer_module_slots[] = {
    {Py_mod_exec, native_buffer_module_exec},
#ifdef Py_MOD_GIL_NOT_USED
    {Py_mod_gil, Py_MOD_GIL_NOT_USED},
#endif
    {0, NULL}
};

static PyModuleDef native_buffer_module = {
    .m_base = PyModuleDef_HEAD_INIT,
    .m_name = "native_buffer",
    .m_doc = "Mypy cache serialization utils",
    .m_size = 0,
    .m_methods = native_buffer_module_methods,
    .m_slots = native_buffer_module_slots,
};

PyMODINIT_FUNC
PyInit_native_buffer(void)
{
    return PyModuleDef_Init(&native_buffer_module);
}
