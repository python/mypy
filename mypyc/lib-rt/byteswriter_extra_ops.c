// Primitives related to librt.strings.BytesWriter that get linked statically
// with compiled modules, instead of being called via a capsule.

#include "byteswriter_extra_ops.h"

#ifdef MYPYC_EXPERIMENTAL

char CPyBytesWriter_Write(PyObject *obj, PyObject *value) {
    BytesWriterObject *self = (BytesWriterObject *)obj;
    const char *data;
    Py_ssize_t size;
    if (likely(PyBytes_Check(value))) {
        data = PyBytes_AS_STRING(value);
        size = PyBytes_GET_SIZE(value);
    } else {
        data = PyByteArray_AS_STRING(value);
        size = PyByteArray_GET_SIZE(value);
    }
    // Write bytes content.
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

#endif // MYPYC_EXPERIMENTAL
