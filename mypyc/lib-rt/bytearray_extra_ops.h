#ifndef MYPYC_BYTEARRAY_EXTRA_OPS_H
#define MYPYC_BYTEARRAY_EXTRA_OPS_H

#include <Python.h>
#include "CPy.h"

// Construct empty bytearray
PyObject *CPyByteArray_New(void);

// Construct a bytearray from a bytes slice, avoiding an intermediate bytes object.
// An omitted bound is represented by CPY_INT_TAG.
PyObject *CPyByteArray_FromBytesSlice(PyObject *obj, CPyTagged start, CPyTagged end);

// bytearray[index]
CPyTagged CPyByteArray_GetItem(PyObject *obj, CPyTagged index);

// bytearray[index] = value
bool CPyByteArray_SetItem(PyObject *obj, CPyTagged index, CPyTagged value);

// bytearray[start:end]
PyObject *CPyByteArray_GetSlice(PyObject *obj, CPyTagged start, CPyTagged end);

#endif
