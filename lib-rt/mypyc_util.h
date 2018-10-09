#ifndef MYPYC_UTIL_H
#define MYPYC_UTIL_H

#include <Python.h>
#include <frameobject.h>
#include <assert.h>

#define likely(x)       __builtin_expect((x),1)
#define unlikely(x)     __builtin_expect((x),0)
#define CPy_Unreachable() __builtin_unreachable()

#define CPY_TAGGED_MAX ((1LL << 62) - 1)
#define CPY_TAGGED_MIN (-(1LL << 62))
#define CPY_TAGGED_ABS_MIN (0-(unsigned long long)CPY_TAGGED_MIN)

// INCREF and DECREF that assert the pointer is not NULL.
// asserts are disabled in release builds so there shouldn't be a perf hit.
// I'm honestly kind of surprised that this isn't done by default.
#define CPy_INCREF(p) do { assert(p); Py_INCREF(p); } while (0)
#define CPy_DECREF(p) do { assert(p); Py_DECREF(p); } while (0)
// Here just for consistency
#define CPy_XDECREF(p) Py_XDECREF(p)

typedef unsigned long long CPyTagged;
typedef long long CPySignedInt;
typedef PyObject CPyModule;

#define CPY_INT_TAG 1

typedef void (*CPyVTableItem)(void);

static inline CPyTagged CPyTagged_ShortFromInt(int x) {
    return x << 1;
}

static inline CPyTagged CPyTagged_ShortFromLongLong(long long x) {
    return x << 1;
}

#endif
