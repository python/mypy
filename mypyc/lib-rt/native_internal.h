#ifndef NATIVE_INTERNAL_H
#define NATIVE_INTERNAL_H

#define NATIVE_INTERNAL_ABI_VERSION 0

#ifdef NATIVE_INTERNAL_MODULE

static PyObject *Buffer_internal(PyObject *source);
static PyObject *Buffer_internal_empty(void);
static PyObject *Buffer_getvalue_internal(PyObject *self);
static char write_bool_internal(PyObject *data, char value);
static char read_bool_internal(PyObject *data);
static char write_str_internal(PyObject *data, PyObject *value);
static PyObject *read_str_internal(PyObject *data);
static char write_float_internal(PyObject *data, double value);
static double read_float_internal(PyObject *data);
static char write_int_internal(PyObject *data, CPyTagged value);
static CPyTagged read_int_internal(PyObject *data);
static char write_tag_internal(PyObject *data, uint8_t value);
static uint8_t read_tag_internal(PyObject *data);
static int NativeInternal_ABI_Version(void);

#else

static void **NativeInternal_API;

#define Buffer_internal (*(PyObject* (*)(PyObject *source)) NativeInternal_API[0])
#define Buffer_internal_empty (*(PyObject* (*)(void)) NativeInternal_API[1])
#define Buffer_getvalue_internal (*(PyObject* (*)(PyObject *source)) NativeInternal_API[2])
#define write_bool_internal (*(char (*)(PyObject *source, char value)) NativeInternal_API[3])
#define read_bool_internal (*(char (*)(PyObject *source)) NativeInternal_API[4])
#define write_str_internal (*(char (*)(PyObject *source, PyObject *value)) NativeInternal_API[5])
#define read_str_internal (*(PyObject* (*)(PyObject *source)) NativeInternal_API[6])
#define write_float_internal (*(char (*)(PyObject *source, double value)) NativeInternal_API[7])
#define read_float_internal (*(double (*)(PyObject *source)) NativeInternal_API[8])
#define write_int_internal (*(char (*)(PyObject *source, CPyTagged value)) NativeInternal_API[9])
#define read_int_internal (*(CPyTagged (*)(PyObject *source)) NativeInternal_API[10])
#define write_tag_internal (*(char (*)(PyObject *source, uint8_t value)) NativeInternal_API[11])
#define read_tag_internal (*(uint8_t (*)(PyObject *source)) NativeInternal_API[12])
#define NativeInternal_ABI_Version (*(int (*)(void)) NativeInternal_API[13])

static int
import_native_internal(void)
{
    NativeInternal_API = (void **)PyCapsule_Import("native_internal._C_API", 0);
    if (NativeInternal_API == NULL)
        return -1;
    if (NativeInternal_ABI_Version() != NATIVE_INTERNAL_ABI_VERSION) {
        PyErr_SetString(PyExc_ValueError, "ABI version conflict for native_internal");
        return -1;
    }
    return 0;
}

#endif
#endif  // NATIVE_INTERNAL_H
