#include "pythoncapi_compat.h"

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdint.h>
#include "CPy.h"
#define LIBRT_INTERNAL_MODULE
#include "librt_internal.h"

#define START_SIZE 512

// See comment in read_int_internal() on motivation for these values.
#define MIN_ONE_BYTE_INT -10
#define MAX_ONE_BYTE_INT 117  // 2 ** 7 - 1 - 10
#define MIN_TWO_BYTES_INT -100
#define MAX_TWO_BYTES_INT 16283  // 2 ** (8 + 6) - 1 - 100
#define MIN_FOUR_BYTES_INT -10000
#define MAX_FOUR_BYTES_INT 536860911  // 2 ** (3 * 8 + 5) - 1 - 10000

#define TWO_BYTES_INT_BIT 1
#define FOUR_BYTES_INT_BIT 2
#define LONG_INT_BIT 4

#define FOUR_BYTES_INT_TRAILER 3
// We add one reserved bit here so that we can potentially support
// 8 bytes format in the future.
#define LONG_INT_TRAILER 15

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

#if PY_BIG_ENDIAN
uint16_t reverse_16(uint16_t number) {
  return (number << 8) | (number >> 8);
}

uint32_t reverse_32(uint32_t number) {
  return ((number & 0xFF) << 24) | ((number & 0xFF00) << 8) | ((number & 0xFF0000) >> 8) | (number >> 24);
}
#endif

typedef struct {
    PyObject_HEAD
    Py_ssize_t pos;
    Py_ssize_t end;
    Py_ssize_t size;
    char *buf;
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
        self->end = PyBytes_GET_SIZE(source);
        // Allocate at least one byte to simplify resizing logic.
        // The original bytes buffer has last null byte, so this is safe.
        self->size = self->end + 1;
        // This returns a pointer to internal bytes data, so make our own copy.
        char *buf = PyBytes_AsString(source);
        self->buf = PyMem_Malloc(self->size);
        memcpy(self->buf, buf, self->end);
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
    if (unlikely((res != 0) & (res != 1))) {
        PyErr_SetString(PyExc_ValueError, "invalid bool value");
        return CPY_BOOL_ERROR;
    }
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
    if (unlikely(write_bool_internal(data, Py_IsTrue(value)) == CPY_NONE_ERROR)) {
        return NULL;
    }
    Py_INCREF(Py_None);
    return Py_None;
}

/*
str format: size as int (see below) followed by UTF-8 bytes
*/

static inline CPyTagged
_read_short_int(PyObject *data, uint8_t first) {
    uint8_t second;
    uint16_t two_more;
    if ((first & TWO_BYTES_INT_BIT) == 0) {
       // Note we use tagged ints since this function can return an error.
       return ((Py_ssize_t)(first >> 1) + MIN_ONE_BYTE_INT) << 1;
    }
    if ((first & FOUR_BYTES_INT_BIT) == 0) {
       _CHECK_READ(data, 1, CPY_INT_TAG)
       second = _READ(data, uint8_t)
       return ((((Py_ssize_t)second) << 6) + (Py_ssize_t)(first >> 2) + MIN_TWO_BYTES_INT) << 1;
    }
    // The caller is responsible to verify this is called only for short ints.
    _CHECK_READ(data, 3, CPY_INT_TAG)
    // TODO: check if compilers emit optimal code for these two reads, and tweak if needed.
    second = _READ(data, uint8_t)
    two_more = _READ(data, uint16_t)
#if PY_BIG_ENDIAN
    two_more = reverse_16(two_more);
#endif
    Py_ssize_t higher = (((Py_ssize_t)two_more) << 13) + (((Py_ssize_t)second) << 5);
    return (higher + (Py_ssize_t)(first >> 3) + MIN_FOUR_BYTES_INT) << 1;
}

static PyObject*
read_str_internal(PyObject *data) {
    _CHECK_BUFFER(data, NULL)

    // Read string length.
    _CHECK_READ(data, 1, NULL)
    uint8_t first = _READ(data, uint8_t)
    if (unlikely(first == LONG_INT_TRAILER)) {
        // Fail fast for invalid/tampered data.
        PyErr_SetString(PyExc_ValueError, "invalid str size");
        return NULL;
    }
    CPyTagged tagged_size = _read_short_int(data, first);
    if (tagged_size == CPY_INT_TAG)
        return NULL;
    if ((Py_ssize_t)tagged_size < 0) {
        // Fail fast for invalid/tampered data.
        PyErr_SetString(PyExc_ValueError, "invalid str size");
        return NULL;
    }
    Py_ssize_t size = tagged_size >> 1;
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

// The caller *must* check that real_value is within allowed range (29 bits).
static inline char
_write_short_int(PyObject *data, Py_ssize_t real_value) {
    if (real_value >= MIN_ONE_BYTE_INT && real_value <= MAX_ONE_BYTE_INT) {
        _CHECK_SIZE(data, 1)
        _WRITE(data, uint8_t, (uint8_t)(real_value - MIN_ONE_BYTE_INT) << 1)
        ((BufferObject *)data)->end += 1;
    } else if (real_value >= MIN_TWO_BYTES_INT && real_value <= MAX_TWO_BYTES_INT) {
        _CHECK_SIZE(data, 2)
#if PY_BIG_ENDIAN
        uint16_t to_write = ((uint16_t)(real_value - MIN_TWO_BYTES_INT) << 2) | TWO_BYTES_INT_BIT;
        _WRITE(data, uint16_t, reverse_16(to_write))
#else
        _WRITE(data, uint16_t, ((uint16_t)(real_value - MIN_TWO_BYTES_INT) << 2) | TWO_BYTES_INT_BIT)
#endif
        ((BufferObject *)data)->end += 2;
    } else {
        _CHECK_SIZE(data, 4)
#if PY_BIG_ENDIAN
        uint32_t to_write = ((uint32_t)(real_value - MIN_FOUR_BYTES_INT) << 3) | FOUR_BYTES_INT_TRAILER;
        _WRITE(data, uint32_t, reverse_32(to_write))
#else
        _WRITE(data, uint32_t, ((uint32_t)(real_value - MIN_FOUR_BYTES_INT) << 3) | FOUR_BYTES_INT_TRAILER)
#endif
        ((BufferObject *)data)->end += 4;
    }
    return CPY_NONE;
}

static char
write_str_internal(PyObject *data, PyObject *value) {
    _CHECK_BUFFER(data, CPY_NONE_ERROR)

    Py_ssize_t size;
    const char *chunk = PyUnicode_AsUTF8AndSize(value, &size);
    if (unlikely(chunk == NULL))
        return CPY_NONE_ERROR;

    // Write string length.
    if (likely(size >= MIN_FOUR_BYTES_INT && size <= MAX_FOUR_BYTES_INT)) {
        if (_write_short_int(data, size) == CPY_NONE_ERROR)
            return CPY_NONE_ERROR;
    } else {
        PyErr_SetString(PyExc_ValueError, "str too long to serialize");
        return CPY_NONE_ERROR;
    }
    // Write string content.
    _CHECK_SIZE(data, size)
    char *buf = ((BufferObject *)data)->buf;
    memcpy(buf + ((BufferObject *)data)->pos, chunk, size);
    ((BufferObject *)data)->pos += size;
    ((BufferObject *)data)->end += size;
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
bytes format: size as int (see below) followed by bytes
*/

static PyObject*
read_bytes_internal(PyObject *data) {
    _CHECK_BUFFER(data, NULL)

    // Read length.
    _CHECK_READ(data, 1, NULL)
    uint8_t first = _READ(data, uint8_t)
    if (unlikely(first == LONG_INT_TRAILER)) {
        // Fail fast for invalid/tampered data.
        PyErr_SetString(PyExc_ValueError, "invalid bytes size");
        return NULL;
    }
    CPyTagged tagged_size = _read_short_int(data, first);
    if (tagged_size == CPY_INT_TAG)
        return NULL;
    if ((Py_ssize_t)tagged_size < 0) {
        // Fail fast for invalid/tampered data.
        PyErr_SetString(PyExc_ValueError, "invalid bytes size");
        return NULL;
    }
    Py_ssize_t size = tagged_size >> 1;
    // Read bytes content.
    char *buf = ((BufferObject *)data)->buf;
    _CHECK_READ(data, size, NULL)
    PyObject *res = PyBytes_FromStringAndSize(
        buf + ((BufferObject *)data)->pos, (Py_ssize_t)size
    );
    if (unlikely(res == NULL))
        return NULL;
    ((BufferObject *)data)->pos += size;
    return res;
}

static PyObject*
read_bytes(PyObject *self, PyObject *const *args, size_t nargs, PyObject *kwnames) {
    static const char * const kwlist[] = {"data", 0};
    static CPyArg_Parser parser = {"O:read_bytes", kwlist, 0};
    PyObject *data;
    if (unlikely(!CPyArg_ParseStackAndKeywordsOneArg(args, nargs, kwnames, &parser, &data))) {
        return NULL;
    }
    return read_bytes_internal(data);
}

static char
write_bytes_internal(PyObject *data, PyObject *value) {
    _CHECK_BUFFER(data, CPY_NONE_ERROR)

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
    _CHECK_SIZE(data, size)
    char *buf = ((BufferObject *)data)->buf;
    memcpy(buf + ((BufferObject *)data)->pos, chunk, size);
    ((BufferObject *)data)->pos += size;
    ((BufferObject *)data)->end += size;
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

/*
float format:
    stored using PyFloat helpers in little-endian format.
*/

static double
read_float_internal(PyObject *data) {
    _CHECK_BUFFER(data, CPY_FLOAT_ERROR)
    _CHECK_READ(data, 8, CPY_FLOAT_ERROR)
    char *buf = ((BufferObject *)data)->buf;
    double res = PyFloat_Unpack8(buf + ((BufferObject *)data)->pos, 1);
    if (unlikely((res == -1.0) && PyErr_Occurred()))
        return CPY_FLOAT_ERROR;
    ((BufferObject *)data)->pos += 8;
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
    _CHECK_SIZE(data, 8)
    char *buf = ((BufferObject *)data)->buf;
    int res = PyFloat_Pack8(value, buf + ((BufferObject *)data)->pos, 1);
    if (unlikely(res == -1))
        return CPY_NONE_ERROR;
    ((BufferObject *)data)->pos += 8;
    ((BufferObject *)data)->end += 8;
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
    one byte: last bit 0, 7 bits used
    two bytes: last two bits 01, 14 bits used
    four bytes: last three bits 011, 29 bits used
    everything else: 00001111 followed by serialized string representation

Note: for fixed size formats we skew ranges towards more positive values,
since negative integers are much more rare.
*/

static CPyTagged
read_int_internal(PyObject *data) {
    _CHECK_BUFFER(data, CPY_INT_TAG)
    _CHECK_READ(data, 1, CPY_INT_TAG)

    uint8_t first = _READ(data, uint8_t)
    if (likely(first != LONG_INT_TRAILER)) {
        return _read_short_int(data, first);
    }

    // Long integer encoding -- byte length and sign, followed by a byte array.

    // Read byte length and sign.
    _CHECK_READ(data, 1, CPY_INT_TAG)
    first = _READ(data, uint8_t)
    Py_ssize_t size_and_sign = _read_short_int(data, first);
    if (size_and_sign == CPY_INT_TAG)
        return CPY_INT_TAG;
    if ((Py_ssize_t)size_and_sign < 0) {
        PyErr_SetString(PyExc_ValueError, "invalid int data");
        return CPY_INT_TAG;
    }
    bool sign = (size_and_sign >> 1) & 1;
    Py_ssize_t size = size_and_sign >> 2;

    // Construct an int object from the byte array.
    _CHECK_READ(data, size, CPY_INT_TAG)
    char *buf = ((BufferObject *)data)->buf;
    PyObject *num = _PyLong_FromByteArray(
        (unsigned char *)(buf + ((BufferObject *)data)->pos), size, 1, 0);
    if (num == NULL)
        return CPY_INT_TAG;
    ((BufferObject *)data)->pos += size;
    if (sign) {
        PyObject *old = num;
        num = PyNumber_Negative(old);
        Py_DECREF(old);
        if (num == NULL) {
            return CPY_INT_TAG;
        }
    }
    return CPyTagged_StealFromObject(num);
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


static inline int hex_to_int(char c) {
    if (c >= '0' && c <= '9')
        return c - '0';
    else if (c >= 'a' && c <= 'f')
        return c - 'a' + 10;
    else
        return c - 'A' + 10;  // Assume valid hex digit
}

static inline char
_write_long_int(PyObject *data, CPyTagged value) {
    _CHECK_SIZE(data, 1)
    _WRITE(data, uint8_t, LONG_INT_TRAILER)
    ((BufferObject *)data)->end += 1;

    PyObject *hex_str = NULL;
    PyObject* int_value = CPyTagged_AsObject(value);
    if (unlikely(int_value == NULL))
        goto error;

    hex_str = PyNumber_ToBase(int_value, 16);
    if (hex_str == NULL)
        goto error;
    Py_DECREF(int_value);
    int_value = NULL;

    const char *str = PyUnicode_AsUTF8(hex_str);
    if (str == NULL)
        goto error;
    Py_ssize_t len = strlen(str);
    bool neg;
    if (str[0] == '-') {
        str++;
        len--;
        neg = true;
    } else {
        neg = false;
    }
    // Skip the 0x hex prefix.
    str += 2;
    len -= 2;

    // Write bytes encoded length and sign.
    Py_ssize_t size = (len + 1) / 2;
    Py_ssize_t encoded_size = (size << 1) | neg;
    if (encoded_size <= MAX_FOUR_BYTES_INT) {
        if (_write_short_int(data, encoded_size) == CPY_NONE_ERROR)
            goto error;
    } else {
        PyErr_SetString(PyExc_ValueError, "int too long to serialize");
        goto error;
    }

    // Write absolute integer value as byte array in a variable-length little endian format.
    int i;
    for (i = len; i > 1; i -= 2) {
        if (write_tag_internal(
                data, hex_to_int(str[i - 1]) | (hex_to_int(str[i - 2]) << 4)) == CPY_NONE_ERROR)
            goto error;
    }
    // The final byte may correspond to only one hex digit.
    if (i == 1) {
        if (write_tag_internal(data, hex_to_int(str[i - 1])) == CPY_NONE_ERROR)
            goto error;
    }

    Py_DECREF(hex_str);
    return CPY_NONE;

  error:

    Py_XDECREF(int_value);
    Py_XDECREF(hex_str);
    return CPY_NONE_ERROR;
}

static char
write_int_internal(PyObject *data, CPyTagged value) {
    _CHECK_BUFFER(data, CPY_NONE_ERROR)

    if (likely((value & CPY_INT_TAG) == 0)) {
        Py_ssize_t real_value = CPyTagged_ShortAsSsize_t(value);
        if (likely(real_value >= MIN_FOUR_BYTES_INT && real_value <= MAX_FOUR_BYTES_INT)) {
            return _write_short_int(data, real_value);
        } else {
            return _write_long_int(data, value);
        }
    } else {
        return _write_long_int(data, value);
    }
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

static uint8_t
cache_version_internal(void) {
    return 0;
}

static PyObject*
cache_version(PyObject *self, PyObject *Py_UNUSED(ignored)) {
    return PyLong_FromLong(cache_version_internal());
}

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
librt_internal_module_exec(PyObject *m)
{
    if (PyType_Ready(&BufferType) < 0) {
        return -1;
    }
    if (PyModule_AddObjectRef(m, "Buffer", (PyObject *) &BufferType) < 0) {
        return -1;
    }

    // Export mypy internal C API, be careful with the order!
    static void *NativeInternal_API[17] = {
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
        (void *)write_bytes_internal,
        (void *)read_bytes_internal,
        (void *)cache_version_internal,
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
