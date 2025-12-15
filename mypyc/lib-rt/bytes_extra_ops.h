#ifndef MYPYC_BYTES_EXTRA_OPS_H
#define MYPYC_BYTES_EXTRA_OPS_H

#include <Python.h>
#include "CPy.h"

// Optimized bytes translate operation
PyObject *CPyBytes_Translate(PyObject *bytes, PyObject *table);

#endif
