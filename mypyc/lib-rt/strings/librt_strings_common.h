#ifndef LIBRT_STRINGS_COMMON_H
#define LIBRT_STRINGS_COMMON_H

#include <Python.h>
#include <stdint.h>
#include <string.h>

// Length of the default buffer embedded directly in a BytesWriter object
#define WRITER_EMBEDDED_BUF_LEN 256

typedef struct {
    PyObject_HEAD
    char *buf;  // Beginning of the buffer
    Py_ssize_t len;  // Current length (number of bytes written)
    Py_ssize_t capacity;  // Total capacity of the buffer
    char data[WRITER_EMBEDDED_BUF_LEN];  // Default buffer
} BytesWriterObject;

// Write a 16-bit signed integer in little-endian format to BytesWriter.
// NOTE: This does NOT check buffer capacity - caller must ensure space is available.
static inline void
BytesWriter_write_i16_le_unchecked(BytesWriterObject *self, int16_t value) {
    // Store len in local to help optimizer reduce struct member accesses
    Py_ssize_t len = self->len;
    unsigned char *p = (unsigned char *)(self->buf + len);
    uint16_t uval = (uint16_t)value;

    // Write in little-endian format
    // Modern compilers optimize this pattern well, often to a single store on LE systems
    p[0] = (unsigned char)uval;
    p[1] = (unsigned char)(uval >> 8);

    self->len = len + 2;
}

// Read a 16-bit signed integer in little-endian format from bytes.
// NOTE: This does NOT check bounds - caller must ensure valid index.
static inline int16_t
read_i16_le_unchecked(const unsigned char *data) {
    // Read in little-endian format
    // Modern compilers optimize this pattern well, often to a single load on LE systems
    uint16_t uval = (uint16_t)data[0] | ((uint16_t)data[1] << 8);
    return (int16_t)uval;
}

#endif  // LIBRT_STRINGS_COMMON_H
