#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdint.h>
#include "CPy.h"
#define NATIVE_INTERNAL_MODULE
#include "native_internal.h"

#define START_SIZE 512
#define MAX_SHORT_INT_TAGGED (255 << 1)

#define MAX_SHORT_LEN 127
#define LONG_STR_TAG 1

#define MIN_SHORT_INT -10
#define MAX_SHORT_INT 117
#define MEDIUM_INT_TAG 1
#define LONG_INT_TAG 3

#define CPY_BOOL_ERROR 2
#define CPY_NONE_ERROR 2
#define CPY_NONE 1

#define _CHECK_BUFFER(data, err)      if (unlikely(_check_buffer(data) == CPY_NONE_ERROR)) \
                                          return err;
#define _CHECK_SIZE(data, need)       if (unlikely(_check_size((BufferObject *)data, need) == CPY_NONE_ERROR)) \
                                          return CPY_NONE_ERROR;
#define _CHECK_READ(data, size, err)  if (unlikely(_check_read((BufferObject *)data, size) == CPY_NONE_ERROR)) \
                                          return err;

#define _READ(data, type)  *(type *)(((BufferObject *)data)->buf + ((BufferObject *)data)->pos); \
                           ((BufferObject *)data)->pos += sizeof(type);

#define _WRITE(data, type, v)  *(type *)(((BufferObject *)data)->buf + ((BufferObject *)data)->pos) = v; \
                               ((BufferObject *)data)->pos += sizeof(type);

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
    if (unlikely(Py_TYPE(data) != &BufferType)) {
        PyErr_Format(
            PyExc_TypeError, "data must be a Buffer object, got %s", Py_TYPE(data)->tp_name
        );
        return CPY_NONE_ERROR;
    }
    return CPY_NONE;
}

static inline char
_check_size(BufferObject *data, Py_ssize_t need) {
    Py_ssize_t target = data->pos + need;
    if (target <= data->size)
        return CPY_NONE;
    do
        data->size *= 2;
    while (target >= data->size);
    data->buf = PyMem_Realloc(data->buf, data->size);
    if (unlikely(data->buf == NULL)) {
        PyErr_NoMemory();
        return CPY_NONE_ERROR;
    }
    return CPY_NONE;
}

static inline char
_check_read(BufferObject *data, Py_ssize_t need) {
    if (unlikely(data->pos + need > data->end)) {
        PyErr_SetString(PyExc_ValueError, "reading past the buffer end");
        return CPY_NONE_ERROR;
    }
    return CPY_NONE;
}

/*
bool format: single byte
    \x00 - False
    \x01 - True
*/

static char
read_bool_internal(PyObject *data) {
    _CHECK_BUFFER(data, CPY_BOOL_ERROR)
    _CHECK_READ(data, 1, CPY_BOOL_ERROR)
    char res = _READ(data, char)
    return res;
}

static PyObject*
read_bool(PyObject *self, PyObject *const *args, size_t nargs, PyObject *kwnames) {
    static const char * const kwlist[] = {"data", 0};
    static CPyArg_Parser parser = {"O:read_bool", kwlist, 0};
    PyObject *data;
    if (unlikely(!CPyArg_ParseStackAndKeywordsOneArg(args, nargs, kwnames, &parser, &data))) {
        return NULL;
    }
    char res = read_bool_internal(data);
    if (unlikely(res == CPY_BOOL_ERROR))
        return NULL;
    PyObject *retval = res ? Py_True : Py_False;
    Py_INCREF(retval);
    return retval;
}

static char
write_bool_internal(PyObject *data, char value) {
    _CHECK_BUFFER(data, CPY_NONE_ERROR)
    _CHECK_SIZE(data, 1)
    _WRITE(data, char, value)
    ((BufferObject *)data)->end += 1;
    return CPY_NONE;
}

static PyObject*
write_bool(PyObject *self, PyObject *const *args, size_t nargs, PyObject *kwnames) {
    static const char * const kwlist[] = {"data", "value", 0};
    static CPyArg_Parser parser = {"OO:write_bool", kwlist, 0};
    PyObject *data;
    PyObject *value;
    if (unlikely(!CPyArg_ParseStackAndKeywordsSimple(args, nargs, kwnames, &parser, &data, &value))) {
        return NULL;
    }
    if (unlikely(!PyBool_Check(value))) {
        PyErr_SetString(PyExc_TypeError, "value must be a bool");
        return NULL;
    }
    if (unlikely(write_bool_internal(data, value == Py_True) == CPY_NONE_ERROR)) {
        return NULL;
    }
    Py_INCREF(Py_None);
    return Py_None;
}

/*
str format: size followed by UTF-8 bytes
    short strings (len <= 127): single byte for size as `(uint8_t)size << 1`
    long strings: \x01 followed by size as Py_ssize_t
*/

static PyObject*
read_str_internal(PyObject *data) {
    _CHECK_BUFFER(data, NULL)

    // Read string length.
    Py_ssize_t size;
    _CHECK_READ(data, 1, NULL)
    uint8_t first = _READ(data, uint8_t)
    if (likely(first != LONG_STR_TAG)) {
        // Common case: short string (len <= 127).
        size = (Py_ssize_t)(first >> 1);
    } else {
        _CHECK_READ(data, sizeof(CPyTagged), NULL)
        size = _READ(data, Py_ssize_t)
    }
    // Read string content.
    char *buf = ((BufferObject *)data)->buf;
    _CHECK_READ(data, size, NULL)
    PyObject *res = PyUnicode_FromStringAndSize(
        buf + ((BufferObject *)data)->pos, (Py_ssize_t)size
    );
    if (unlikely(res == NULL))
        return NULL;
    ((BufferObject *)data)->pos += size;
    return res;
}

static PyObject*
read_str(PyObject *self, PyObject *const *args, size_t nargs, PyObject *kwnames) {
    static const char * const kwlist[] = {"data", 0};
    static CPyArg_Parser parser = {"O:read_str", kwlist, 0};
    PyObject *data;
    if (unlikely(!CPyArg_ParseStackAndKeywordsOneArg(args, nargs, kwnames, &parser, &data))) {
        return NULL;
    }
    return read_str_internal(data);
}

static char
write_str_internal(PyObject *data, PyObject *value) {
    _CHECK_BUFFER(data, CPY_NONE_ERROR)

    Py_ssize_t size;
    const char *chunk = PyUnicode_AsUTF8AndSize(value, &size);
    if (unlikely(chunk == NULL))
        return CPY_NONE_ERROR;

    Py_ssize_t need;
    // Write string length.
    if (likely(size <= MAX_SHORT_LEN)) {
        // Common case: short string (len <= 127) store as single byte.
        need = size + 1;
        _CHECK_SIZE(data, need)
        _WRITE(data, uint8_t, (uint8_t)size << 1)
    } else {
        need = size + sizeof(Py_ssize_t) + 1;
        _CHECK_SIZE(data, need)
        _WRITE(data, uint8_t, LONG_STR_TAG)
        _WRITE(data, Py_ssize_t, size)
    }
    // Write string content.
    char *buf = ((BufferObject *)data)->buf;
    memcpy(buf + ((BufferObject *)data)->pos, chunk, size);
    ((BufferObject *)data)->pos += size;
    ((BufferObject *)data)->end += need;
    return CPY_NONE;
}

static PyObject*
write_str(PyObject *self, PyObject *const *args, size_t nargs, PyObject *kwnames) {
    static const char * const kwlist[] = {"data", "value", 0};
    static CPyArg_Parser parser = {"OO:write_str", kwlist, 0};
    PyObject *data;
    PyObject *value;
    if (unlikely(!CPyArg_ParseStackAndKeywordsSimple(args, nargs, kwnames, &parser, &data, &value))) {
        return NULL;
    }
    if (unlikely(!PyUnicode_Check(value))) {
        PyErr_SetString(PyExc_TypeError, "value must be a str");
        return NULL;
    }
    if (unlikely(write_str_internal(data, value) == CPY_NONE_ERROR)) {
        return NULL;
    }
    Py_INCREF(Py_None);
    return Py_None;
}

/*
float format:
    stored as a C double
*/

static double
read_float_internal(PyObject *data) {
    _CHECK_BUFFER(data, CPY_FLOAT_ERROR)
    _CHECK_READ(data, sizeof(double), CPY_FLOAT_ERROR)
    double res = _READ(data, double);
    return res;
}

static PyObject*
read_float(PyObject *self, PyObject *const *args, size_t nargs, PyObject *kwnames) {
    static const char * const kwlist[] = {"data", 0};
    static CPyArg_Parser parser = {"O:read_float", kwlist, 0};
    PyObject *data;
    if (unlikely(!CPyArg_ParseStackAndKeywordsOneArg(args, nargs, kwnames, &parser, &data))) {
        return NULL;
    }
    double retval = read_float_internal(data);
    if (unlikely(retval == CPY_FLOAT_ERROR && PyErr_Occurred())) {
        return NULL;
    }
    return PyFloat_FromDouble(retval);
}

static char
write_float_internal(PyObject *data, double value) {
    _CHECK_BUFFER(data, CPY_NONE_ERROR)
    _CHECK_SIZE(data, sizeof(double))
    _WRITE(data, double, value)
    ((BufferObject *)data)->end += sizeof(double);
    return CPY_NONE;
}

static PyObject*
write_float(PyObject *self, PyObject *const *args, size_t nargs, PyObject *kwnames) {
    static const char * const kwlist[] = {"data", "value", 0};
    static CPyArg_Parser parser = {"OO:write_float", kwlist, 0};
    PyObject *data;
    PyObject *value;
    if (unlikely(!CPyArg_ParseStackAndKeywordsSimple(args, nargs, kwnames, &parser, &data, &value))) {
        return NULL;
    }
    if (unlikely(!PyFloat_Check(value))) {
        PyErr_SetString(PyExc_TypeError, "value must be a float");
        return NULL;
    }
    if (unlikely(write_float_internal(data, PyFloat_AsDouble(value)) == CPY_NONE_ERROR)) {
        return NULL;
    }
    Py_INCREF(Py_None);
    return Py_None;
}

/*
int format:
    most common values (-10 <= value <= 117): single byte as `(uint8_t)(value + 10) << 1`
    medium values (fit in CPyTagged): \x01 followed by CPyTagged value
    long values (very rare): \x03 followed by decimal string (see str format)
*/

static CPyTagged
read_int_internal(PyObject *data) {
    _CHECK_BUFFER(data, CPY_INT_TAG)
    _CHECK_READ(data, 1, CPY_INT_TAG)

    uint8_t first = _READ(data, uint8_t)
    if ((first & MEDIUM_INT_TAG) == 0) {
       // Most common case: int that is small in absolute value.
       return ((Py_ssize_t)(first >> 1) + MIN_SHORT_INT) << 1;
    }
    if (first == MEDIUM_INT_TAG) {
        _CHECK_READ(data, sizeof(CPyTagged), CPY_INT_TAG)
        CPyTagged ret = _READ(data, CPyTagged)
        return ret;
    }
    // People who have literal ints not fitting in size_t should be punished :-)
    PyObject *str_ret = read_str_internal(data);
    if (unlikely(str_ret == NULL))
        return CPY_INT_TAG;
    PyObject* ret_long = PyLong_FromUnicodeObject(str_ret, 10);
    Py_DECREF(str_ret);
    return ((CPyTagged)ret_long) | CPY_INT_TAG;
}

static PyObject*
read_int(PyObject *self, PyObject *const *args, size_t nargs, PyObject *kwnames) {
    static const char * const kwlist[] = {"data", 0};
    static CPyArg_Parser parser = {"O:read_int", kwlist, 0};
    PyObject *data;
    if (unlikely(!CPyArg_ParseStackAndKeywordsOneArg(args, nargs, kwnames, &parser, &data))) {
        return NULL;
    }
    CPyTagged retval = read_int_internal(data);
    if (unlikely(retval == CPY_INT_TAG)) {
        return NULL;
    }
    return CPyTagged_StealAsObject(retval);
}

static char
write_int_internal(PyObject *data, CPyTagged value) {
    _CHECK_BUFFER(data, CPY_NONE_ERROR)

    if (likely((value & CPY_INT_TAG) == 0)) {
        Py_ssize_t real_value = CPyTagged_ShortAsSsize_t(value);
        if (real_value >= MIN_SHORT_INT && real_value <= MAX_SHORT_INT) {
            // Most common case: int that is small in absolute value.
            _CHECK_SIZE(data, 1)
            _WRITE(data, uint8_t, (uint8_t)(real_value - MIN_SHORT_INT) << 1)
            ((BufferObject *)data)->end += 1;
        } else {
            _CHECK_SIZE(data, sizeof(CPyTagged) + 1)
            _WRITE(data, uint8_t, MEDIUM_INT_TAG)
            _WRITE(data, CPyTagged, value)
            ((BufferObject *)data)->end += sizeof(CPyTagged) + 1;
        }
    } else {
        _CHECK_SIZE(data, 1)
        _WRITE(data, uint8_t, LONG_INT_TAG)
        ((BufferObject *)data)->end += 1;
        PyObject *str_value = PyObject_Str(CPyTagged_LongAsObject(value));
        if (unlikely(str_value == NULL))
            return CPY_NONE_ERROR;
        char res = write_str_internal(data, str_value);
        Py_DECREF(str_value);
        if (unlikely(res == CPY_NONE_ERROR))
            return CPY_NONE_ERROR;
    }
    return CPY_NONE;
}

static PyObject*
write_int(PyObject *self, PyObject *const *args, size_t nargs, PyObject *kwnames) {
    static const char * const kwlist[] = {"data", "value", 0};
    static CPyArg_Parser parser = {"OO:write_int", kwlist, 0};
    PyObject *data;
    PyObject *value;
    if (unlikely(!CPyArg_ParseStackAndKeywordsSimple(args, nargs, kwnames, &parser, &data, &value))) {
        return NULL;
    }
    if (unlikely(!PyLong_Check(value))) {
        PyErr_SetString(PyExc_TypeError, "value must be an int");
        return NULL;
    }
    CPyTagged tagged_value = CPyTagged_BorrowFromObject(value);
    if (unlikely(write_int_internal(data, tagged_value) == CPY_NONE_ERROR)) {
        return NULL;
    }
    Py_INCREF(Py_None);
    return Py_None;
}

/*
integer tag format (0 <= t <= 255):
    stored as a uint8_t
*/

static uint8_t
read_tag_internal(PyObject *data) {
    _CHECK_BUFFER(data, CPY_LL_UINT_ERROR)
    _CHECK_READ(data, 1, CPY_LL_UINT_ERROR)
    uint8_t ret = _READ(data, uint8_t)
    return ret;
}

static PyObject*
read_tag(PyObject *self, PyObject *const *args, size_t nargs, PyObject *kwnames) {
    static const char * const kwlist[] = {"data", 0};
    static CPyArg_Parser parser = {"O:read_tag", kwlist, 0};
    PyObject *data;
    if (unlikely(!CPyArg_ParseStackAndKeywordsOneArg(args, nargs, kwnames, &parser, &data))) {
        return NULL;
    }
    uint8_t retval = read_tag_internal(data);
    if (unlikely(retval == CPY_LL_UINT_ERROR && PyErr_Occurred())) {
        return NULL;
    }
    return PyLong_FromLong(retval);
}

static char
write_tag_internal(PyObject *data, uint8_t value) {
    _CHECK_BUFFER(data, CPY_NONE_ERROR)
    _CHECK_SIZE(data, 1)
    _WRITE(data, uint8_t, value)
    ((BufferObject *)data)->end += 1;
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

static PyMethodDef native_internal_module_methods[] = {
    {"write_bool", (PyCFunction)write_bool, METH_FASTCALL | METH_KEYWORDS, PyDoc_STR("write a bool")},
    {"read_bool", (PyCFunction)read_bool, METH_FASTCALL | METH_KEYWORDS, PyDoc_STR("read a bool")},
    {"write_str", (PyCFunction)write_str, METH_FASTCALL | METH_KEYWORDS, PyDoc_STR("write a string")},
    {"read_str", (PyCFunction)read_str, METH_FASTCALL | METH_KEYWORDS, PyDoc_STR("read a string")},
    {"write_float", (PyCFunction)write_float, METH_FASTCALL | METH_KEYWORDS, PyDoc_STR("write a float")},
    {"read_float", (PyCFunction)read_float, METH_FASTCALL | METH_KEYWORDS, PyDoc_STR("read a float")},
    {"write_int", (PyCFunction)write_int, METH_FASTCALL | METH_KEYWORDS, PyDoc_STR("write an int")},
    {"read_int", (PyCFunction)read_int, METH_FASTCALL | METH_KEYWORDS, PyDoc_STR("read an int")},
    {"write_tag", (PyCFunction)write_tag, METH_FASTCALL | METH_KEYWORDS, PyDoc_STR("write a short int")},
    {"read_tag", (PyCFunction)read_tag, METH_FASTCALL | METH_KEYWORDS, PyDoc_STR("read a short int")},
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
