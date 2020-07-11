#include <stdbool.h>
#include <Python.h>
#include <frameobject.h>
#include <assert.h>
#include "CPy.h"

// Because its dynamic linker is more restricted than linux/OS X,
// Windows doesn't allow initializing globals with values from
// other dynamic libraries. This means we need to initialize
// things at load time.
void CPy_Init(void) {
    _CPy_ExcDummyStruct.ob_base.ob_type = &PyBaseObject_Type;
}
