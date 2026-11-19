// Primitives related to librt.strings.BytesWriter that get linked statically
// with compiled modules, instead of being called via a capsule.

#include "byteswriter_extra_ops.h"

static inline char write_data(BytesWriterObject *self, const char *data, Py_ssize_t size) {
    if (!CPyBytesWriter_EnsureSize(self, size))
        return CPY_NONE_ERROR;
    if (size < 8) {
        // Loop tends to be faster for small sizes
        char *p = self->buf + self->len;
        for (Py_ssize_t i = 0; i < size; i++) {
            p[i] = data[i];
        }
    } else {
        memcpy(self->buf + self->len, data, size);
    }
    self->len += size;
    return CPY_NONE;
}

char CPyBytesWriter_Write(PyObject *obj, PyObject *value) {
    BytesWriterObject *self = (BytesWriterObject *)obj;
    if (likely(PyBytes_Check(value))) {
        return write_data(self, PyBytes_AS_STRING(value), PyBytes_GET_SIZE(value));
    }
    // On free-threaded builds another thread could resize the bytearray while we
    // copy it, so lock it like the bytearray methods do (no-op on other builds).
    char result;
    Py_BEGIN_CRITICAL_SECTION(value);
    result = write_data(self, PyByteArray_AS_STRING(value), PyByteArray_GET_SIZE(value));
    Py_END_CRITICAL_SECTION();
    return result;
}

void CPyBytes_ReadError(int64_t index, Py_ssize_t size) {
    if (index < 0) {
        PyErr_SetString(PyExc_ValueError, "index must be non-negative");
    } else {
        PyErr_Format(PyExc_IndexError,
                     "index %lld out of range for bytes of length %zd",
                     (long long)index, size);
    }
}
