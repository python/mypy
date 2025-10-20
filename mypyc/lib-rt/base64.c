#include <Python.h>
#include "CPy.h"


PyObject *CPyBase64_Encode(PyObject *b) {
    return PyBytes_FromStringAndSize("xyz", 3);
}
