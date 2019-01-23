#include <stdbool.h>
#include <Python.h>
#include <frameobject.h>
#include <assert.h>
#include "CPy.h"

// TODO: Currently only the things that *need* to be defined a single time
// instead of copied into every module live here. This is silly, and most
// of the code in CPy.h and pythonsupport.h should move here.

struct ExcDummyStruct _CPy_ExcDummyStruct = { PyObject_HEAD_INIT(NULL) };
PyObject *_CPy_ExcDummy = (PyObject *)&_CPy_ExcDummyStruct;

// Because its dynamic linker is more restricted than linux/OS X,
// Windows doesn't allow initializing globals with values from
// other dynamic libraries. This means we need to initialize
// things at load time.
void CPy_Init(void) {
    _CPy_ExcDummyStruct.ob_base.ob_type = &PyBaseObject_Type;
}
