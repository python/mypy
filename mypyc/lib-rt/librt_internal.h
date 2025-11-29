#ifndef LIBRT_INTERNAL_H
#define LIBRT_INTERNAL_H

// ABI version -- only an exact match is compatible. This will only be changed in
// very exceptional cases (likely never) due to strict backward compatibility
// requirements.
#define LIBRT_INTERNAL_ABI_VERSION 2

// API version -- more recent versions must maintain backward compatibility, i.e.
// we can add new features but not remove or change existing features (unless
// ABI version is changed, but see the comment above).
 #define LIBRT_INTERNAL_API_VERSION 0

// Number of functions in the capsule API. If you add a new function, also increase
// LIBRT_INTERNAL_API_VERSION.
#define LIBRT_INTERNAL_API_LEN 20

#ifdef LIBRT_INTERNAL_MODULE

static PyObject *ReadBuffer_internal(PyObject *source);
static PyObject *WriteBuffer_internal(void);
static PyObject *WriteBuffer_getvalue_internal(PyObject *self);
static PyObject *ReadBuffer_internal(PyObject *source);
static PyObject *ReadBuffer_internal_empty(void);
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
static char write_bytes_internal(PyObject *data, PyObject *value);
static PyObject *read_bytes_internal(PyObject *data);
static uint8_t cache_version_internal(void);
static PyTypeObject *ReadBuffer_type_internal(void);
static PyTypeObject *WriteBuffer_type_internal(void);
static int NativeInternal_API_Version(void);

#else

static void *NativeInternal_API[LIBRT_INTERNAL_API_LEN];

#define ReadBuffer_internal (*(PyObject* (*)(PyObject *source)) NativeInternal_API[0])
#define WriteBuffer_internal (*(PyObject* (*)(void)) NativeInternal_API[1])
#define WriteBuffer_getvalue_internal (*(PyObject* (*)(PyObject *source)) NativeInternal_API[2])
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
#define write_bytes_internal (*(char (*)(PyObject *source, PyObject *value)) NativeInternal_API[14])
#define read_bytes_internal (*(PyObject* (*)(PyObject *source)) NativeInternal_API[15])
#define cache_version_internal (*(uint8_t (*)(void)) NativeInternal_API[16])
#define ReadBuffer_type_internal (*(PyTypeObject* (*)(void)) NativeInternal_API[17])
#define WriteBuffer_type_internal (*(PyTypeObject* (*)(void)) NativeInternal_API[18])
#define NativeInternal_API_Version (*(int (*)(void)) NativeInternal_API[19])

static int
import_librt_internal(void)
{
    PyObject *mod = PyImport_ImportModule("librt.internal");
    if (mod == NULL)
        return -1;
    Py_DECREF(mod);  // we import just for the side effect of making the below work.
    void *capsule = PyCapsule_Import("librt.internal._C_API", 0);
    if (capsule == NULL)
        return -1;
    memcpy(NativeInternal_API, capsule, sizeof(NativeInternal_API));
    if (NativeInternal_ABI_Version() != LIBRT_INTERNAL_ABI_VERSION) {
        char err[128];
        snprintf(err, sizeof(err), "ABI version conflict for librt.internal, expected %d, found %d",
            LIBRT_INTERNAL_ABI_VERSION,
            NativeInternal_ABI_Version()
        );
        PyErr_SetString(PyExc_ValueError, err);
        return -1;
    }
    if (NativeInternal_API_Version() < LIBRT_INTERNAL_API_VERSION) {
        char err[128];
        snprintf(err, sizeof(err),
                 "API version conflict for librt.internal, expected %d or newer, found %d (hint: upgrade librt)",
            LIBRT_INTERNAL_API_VERSION,
            NativeInternal_API_Version()
        );
        PyErr_SetString(PyExc_ValueError, err);
        return -1;
    }
    return 0;
}

#endif

static inline bool CPyReadBuffer_Check(PyObject *obj) {
    return Py_TYPE(obj) == ReadBuffer_type_internal();
}

static inline bool CPyWriteBuffer_Check(PyObject *obj) {
    return Py_TYPE(obj) == WriteBuffer_type_internal();
}

#endif  // LIBRT_INTERNAL_H
