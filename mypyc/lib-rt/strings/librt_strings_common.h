#ifndef LIBRT_STRINGS_COMMON_H
#define LIBRT_STRINGS_COMMON_H

#include <Python.h>

// Length of the default buffer embedded directly in a BytesWriter object
#define WRITER_EMBEDDED_BUF_LEN 256

typedef struct {
    PyObject_HEAD
    char *buf;  // Beginning of the buffer
    Py_ssize_t len;  // Current length (number of bytes written)
    Py_ssize_t capacity;  // Total capacity of the buffer
    char data[WRITER_EMBEDDED_BUF_LEN];  // Default buffer
} BytesWriterObject;

#endif  // LIBRT_STRINGS_COMMON_H
