#ifndef LIBRT_STRINGS_COMMON_H
#define LIBRT_STRINGS_COMMON_H

#include <Python.h>
#include <stdint.h>

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
    // Write in little-endian format
    self->buf[self->len] = (uint8_t)(value & 0xFF);
    self->buf[self->len + 1] = (uint8_t)((value >> 8) & 0xFF);
    self->len += 2;
}

#endif  // LIBRT_STRINGS_COMMON_H
