#ifndef LIBRT_STRINGS_COMMON_H
#define LIBRT_STRINGS_COMMON_H

#include <Python.h>
#include <stdint.h>
#include <string.h>

// Byte-swap macros for big-endian support
#if PY_BIG_ENDIAN
#  if defined(_MSC_VER)
#    include <stdlib.h>
#    define BSWAP16(x) _byteswap_ushort(x)
#    define BSWAP32(x) _byteswap_ulong(x)
#    define BSWAP64(x) _byteswap_uint64(x)
#  elif defined(__GNUC__) || defined(__clang__)
#    define BSWAP16(x) __builtin_bswap16(x)
#    define BSWAP32(x) __builtin_bswap32(x)
#    define BSWAP64(x) __builtin_bswap64(x)
#  else
#    error "Unsupported compiler for big-endian byte swapping"
#  endif
#endif

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
    // memcpy is reliably optimized to a single store by GCC, Clang, and MSVC
#if PY_BIG_ENDIAN
    uint16_t swapped = BSWAP16((uint16_t)value);
    memcpy(self->buf + self->len, &swapped, 2);
#else
    memcpy(self->buf + self->len, &value, 2);
#endif
    self->len += 2;
}

// Read a 16-bit signed integer in little-endian format from bytes.
// NOTE: This does NOT check bounds - caller must ensure valid index.
static inline int16_t
read_i16_le_unchecked(const unsigned char *data) {
    // memcpy is reliably optimized to a single load by GCC, Clang, and MSVC
    uint16_t value;
    memcpy(&value, data, 2);
#if PY_BIG_ENDIAN
    value = BSWAP16(value);
#endif
    return (int16_t)value;
}

// Write a 32-bit signed integer in little-endian format to BytesWriter.
// NOTE: This does NOT check buffer capacity - caller must ensure space is available.
static inline void
BytesWriter_write_i32_le_unchecked(BytesWriterObject *self, int32_t value) {
    // memcpy is reliably optimized to a single store by GCC, Clang, and MSVC
#if PY_BIG_ENDIAN
    uint32_t swapped = BSWAP32((uint32_t)value);
    memcpy(self->buf + self->len, &swapped, 4);
#else
    memcpy(self->buf + self->len, &value, 4);
#endif
    self->len += 4;
}

// Read a 32-bit signed integer in little-endian format from bytes.
// NOTE: This does NOT check bounds - caller must ensure valid index.
static inline int32_t
read_i32_le_unchecked(const unsigned char *data) {
    // memcpy is reliably optimized to a single load by GCC, Clang, and MSVC
    uint32_t value;
    memcpy(&value, data, 4);
#if PY_BIG_ENDIAN
    value = BSWAP32(value);
#endif
    return (int32_t)value;
}

// Write a 64-bit signed integer in little-endian format to BytesWriter.
// NOTE: This does NOT check buffer capacity - caller must ensure space is available.
static inline void
BytesWriter_write_i64_le_unchecked(BytesWriterObject *self, int64_t value) {
    // memcpy is reliably optimized to a single store by GCC, Clang, and MSVC
#if PY_BIG_ENDIAN
    uint64_t swapped = BSWAP64((uint64_t)value);
    memcpy(self->buf + self->len, &swapped, 8);
#else
    memcpy(self->buf + self->len, &value, 8);
#endif
    self->len += 8;
}

// Read a 64-bit signed integer in little-endian format from bytes.
// NOTE: This does NOT check bounds - caller must ensure valid index.
static inline int64_t
read_i64_le_unchecked(const unsigned char *data) {
    // memcpy is reliably optimized to a single load by GCC, Clang, and MSVC
    uint64_t value;
    memcpy(&value, data, 8);
#if PY_BIG_ENDIAN
    value = BSWAP64(value);
#endif
    return (int64_t)value;
}

#endif  // LIBRT_STRINGS_COMMON_H
