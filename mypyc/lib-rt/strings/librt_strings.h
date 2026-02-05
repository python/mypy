#ifndef LIBRT_STRINGS_H
#define LIBRT_STRINGS_H

#ifndef MYPYC_EXPERIMENTAL

static int
import_librt_strings(void)
{
    // All librt.base64 features are experimental for now, so don't set up the API here
    return 0;
}

#else  // MYPYC_EXPERIMENTAL

#include <Python.h>
#include "librt_strings_common.h"

// ABI version -- only an exact match is compatible. This will only be changed in
// very exceptional cases (likely never) due to strict backward compatibility
// requirements.
#define LIBRT_STRINGS_ABI_VERSION 1

// API version -- more recent versions must maintain backward compatibility, i.e.
// we can add new features but not remove or change existing features (unless
// ABI version is changed, but see the comment above).
 #define LIBRT_STRINGS_API_VERSION 4

// Number of functions in the capsule API. If you add a new function, also increase
// LIBRT_STRINGS_API_VERSION.
#define LIBRT_STRINGS_API_LEN 14

static void *LibRTStrings_API[LIBRT_STRINGS_API_LEN];

typedef struct {
    PyObject_HEAD
    char *buf;  // Beginning of the buffer
    char kind;  // Bytes per code point (1, 2 or 4)
    Py_ssize_t len;  // Current length (number of code points written)
    Py_ssize_t capacity;  // Total capacity of the buffer (number of code points)
    char data[WRITER_EMBEDDED_BUF_LEN];  // Default buffer
} StringWriterObject;

#define LibRTStrings_ABIVersion (*(int (*)(void)) LibRTStrings_API[0])
#define LibRTStrings_APIVersion (*(int (*)(void)) LibRTStrings_API[1])
#define LibRTStrings_BytesWriter_internal (*(PyObject* (*)(void)) LibRTStrings_API[2])
#define LibRTStrings_BytesWriter_getvalue_internal (*(PyObject* (*)(PyObject *source)) LibRTStrings_API[3])
#define LibRTStrings_BytesWriter_append_internal (*(char (*)(PyObject *source, uint8_t value)) LibRTStrings_API[4])
#define LibRTStrings_ByteWriter_grow_buffer_internal (*(bool (*)(BytesWriterObject *obj, Py_ssize_t size)) LibRTStrings_API[5])
#define LibRTStrings_BytesWriter_type_internal (*(PyTypeObject* (*)(void)) LibRTStrings_API[6])
#define LibRTStrings_BytesWriter_truncate_internal (*(char (*)(PyObject *self, int64_t size)) LibRTStrings_API[7])
#define LibRTStrings_StringWriter_internal (*(PyObject* (*)(void)) LibRTStrings_API[8])
#define LibRTStrings_StringWriter_getvalue_internal (*(PyObject* (*)(PyObject *source)) LibRTStrings_API[9])
#define LibRTStrings_string_append_slow_path (*(char (*)(StringWriterObject *obj, int32_t value)) LibRTStrings_API[10])
#define LibRTStrings_StringWriter_type_internal (*(PyTypeObject* (*)(void)) LibRTStrings_API[11])
#define LibRTStrings_StringWriter_write_internal (*(char (*)(PyObject *source, PyObject *value)) LibRTStrings_API[12])
#define LibRTStrings_grow_string_buffer (*(bool (*)(StringWriterObject *obj, Py_ssize_t n)) LibRTStrings_API[13])

static int
import_librt_strings(void)
{
    PyObject *mod = PyImport_ImportModule("librt.strings");
    if (mod == NULL)
        return -1;
    Py_DECREF(mod);  // we import just for the side effect of making the below work.
    void *capsule = PyCapsule_Import("librt.strings._C_API", 0);
    if (capsule == NULL)
        return -1;
    memcpy(LibRTStrings_API, capsule, sizeof(LibRTStrings_API));
    if (LibRTStrings_ABIVersion() != LIBRT_STRINGS_ABI_VERSION) {
        char err[128];
        snprintf(err, sizeof(err), "ABI version conflict for librt.strings, expected %d, found %d",
            LIBRT_STRINGS_ABI_VERSION,
            LibRTStrings_ABIVersion()
        );
        PyErr_SetString(PyExc_ValueError, err);
        return -1;
    }
    if (LibRTStrings_APIVersion() < LIBRT_STRINGS_API_VERSION) {
        char err[128];
        snprintf(err, sizeof(err),
                 "API version conflict for librt.strings, expected %d or newer, found %d (hint: upgrade librt)",
            LIBRT_STRINGS_API_VERSION,
            LibRTStrings_APIVersion()
        );
        PyErr_SetString(PyExc_ValueError, err);
        return -1;
    }
    return 0;
}

static inline bool CPyBytesWriter_Check(PyObject *obj) {
    return Py_TYPE(obj) == LibRTStrings_BytesWriter_type_internal();
}

static inline bool CPyStringWriter_Check(PyObject *obj) {
    return Py_TYPE(obj) == LibRTStrings_StringWriter_type_internal();
}

#endif  // MYPYC_EXPERIMENTAL

#endif  // LIBRT_STRINGS_H
