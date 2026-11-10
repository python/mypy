// Header file providing new C API functions to old Python versions.
// Python 3.6 or newer is required.
//
// File distributed under the Zero Clause BSD (0BSD) license.
// Copyright Contributors to the pythoncapi_compat project.
//
// Homepage:
// https://github.com/python/pythoncapi_compat
//
// Latest version:
// https://raw.githubusercontent.com/python/pythoncapi-compat/main/pythoncapi_compat.h
//
// SPDX-License-Identifier: 0BSD

#ifndef PYTHONCAPI_COMPAT
#define PYTHONCAPI_COMPAT

#ifdef __cplusplus
extern "C" {
#endif

#include <Python.h>
#include <stddef.h>               // offsetof()
#include <stdio.h>                // fclose()
#include <string.h>               // memcpy()

// Python 3.11 added PyFrame_GetBack() to Python.h
#if PY_VERSION_HEX < 0x030B0000 && !defined(PYPY_VERSION)
#   include "frameobject.h"        // PyFrameObject, PyFrame_GetBack()
#endif


#ifndef _Py_CAST
#   define _Py_CAST(type, expr) ((type)(expr))
#endif

// Static inline functions should use _Py_NULL rather than using directly NULL
// to prevent C++ compiler warnings. On C23 and newer and on C++11 and newer,
// _Py_NULL is defined as nullptr.
#ifndef _Py_NULL
#   if (defined (__STDC_VERSION__) && __STDC_VERSION__ > 201710L) \
           || (defined(__cplusplus) && __cplusplus >= 201103)
#       define _Py_NULL nullptr
#   else
#       define _Py_NULL NULL
#   endif
#endif

// Cast argument to PyObject* type.
#ifndef _PyObject_CAST
#   define _PyObject_CAST(op) _Py_CAST(PyObject*, op)
#endif
#ifndef _PyVarObject_CAST
#   define _PyVarObject_CAST(op) _Py_CAST(PyVarObject*, (op))
#endif

#ifndef Py_BUILD_ASSERT
#   define Py_BUILD_ASSERT(cond) \
         do { (void)sizeof(char [1 - 2 * !(cond)]); } while(0)
#endif

#ifndef _Py_COMP_DIAG_PUSH
#   if defined(__clang__)
#       define _Py_COMP_DIAG_PUSH _Pragma("clang diagnostic push")
#       define _Py_COMP_DIAG_IGNORE_DEPR_DECLS \
            _Pragma("clang diagnostic ignored \"-Wdeprecated-declarations\"")
#       define _Py_COMP_DIAG_POP _Pragma("clang diagnostic pop")
#   elif defined(__GNUC__) \
       && ((__GNUC__ >= 5) || (__GNUC__ == 4) && (__GNUC_MINOR__ >= 6))
#       define _Py_COMP_DIAG_PUSH _Pragma("GCC diagnostic push")
#       define _Py_COMP_DIAG_IGNORE_DEPR_DECLS \
            _Pragma("GCC diagnostic ignored \"-Wdeprecated-declarations\"")
#       define _Py_COMP_DIAG_POP _Pragma("GCC diagnostic pop")
#   elif defined(_MSC_VER)
#       define _Py_COMP_DIAG_PUSH __pragma(warning(push))
#       define _Py_COMP_DIAG_IGNORE_DEPR_DECLS __pragma(warning(disable: 4996))
#       define _Py_COMP_DIAG_POP __pragma(warning(pop))
#   else
#       define _Py_COMP_DIAG_PUSH
#       define _Py_COMP_DIAG_IGNORE_DEPR_DECLS
#       define _Py_COMP_DIAG_POP
#   endif
#endif

#ifndef _Py_PACK_VERSION
#   define _Py_PACK_FULL_VERSION(X, Y, Z, LEVEL, SERIAL) (  \
        (((X) & 0xff) << 24) |                              \
        (((Y) & 0xff) << 16) |                              \
        (((Z) & 0xff) << 8) |                               \
        (((LEVEL) & 0xf) << 4) |                            \
        (((SERIAL) & 0xf) << 0))
#   define _Py_PACK_VERSION(X, Y) _Py_PACK_FULL_VERSION(X, Y, 0, 0, 0)
#endif

#if (PY_VERSION_HEX >= _Py_PACK_VERSION(3, 13) \
     && (!defined(Py_LIMITED_API) || Py_LIMITED_API+0 >= _Py_PACK_VERSION(3, 13)))
    // "%T" format was added to Python 3.13
#   define PYTHONCAPI_COMPAT_EXPECT_TYPE(ERRMSG, OBJ) \
        PyErr_Format(PyExc_TypeError, ERRMSG "%T", (OBJ))
#elif !defined(Py_LIMITED_API)
#   define PYTHONCAPI_COMPAT_EXPECT_TYPE(ERRMSG, OBJ) \
        PyErr_Format(PyExc_TypeError, ERRMSG "%s", Py_TYPE(OBJ)->tp_name)
#elif Py_LIMITED_API+0 >= _Py_PACK_VERSION(3, 11)
#   define PYTHONCAPI_COMPAT_EXPECT_TYPE(ERRMSG, OBJ) \
        do { \
            PyObject *_type_name = PyType_GetName(Py_TYPE(OBJ)); \
            if (_type_name != NULL) { \
                PyErr_Format(PyExc_TypeError, ERRMSG "%S", (OBJ)); \
                Py_DECREF(_type_name); \
            } \
        } while (0)
#else
#   define PYTHONCAPI_COMPAT_EXPECT_TYPE(ERRMSG, OBJ) \
        do { \
            PyObject *_type = _PyObject_CAST(Py_TYPE(OBJ)); \
            PyObject *_type_name = PyObject_GetAttrString(_type, "__name__"); \
            if (_type_name != NULL) { \
                PyErr_Format(PyExc_TypeError, ERRMSG "%S", (OBJ)); \
                Py_DECREF(_type_name); \
            } \
        } while (0)
#endif


// bpo-42262 added Py_NewRef() to Python 3.10
#if PY_VERSION_HEX < _Py_PACK_VERSION(3, 10) && !defined(Py_NewRef)
static inline PyObject* _Py_NewRef(PyObject *obj)
{
    Py_INCREF(obj);
    return obj;
}
#define Py_NewRef(obj) _Py_NewRef(_PyObject_CAST(obj))
#endif


// bpo-42262 added Py_XNewRef() to Python 3.10
#if PY_VERSION_HEX < _Py_PACK_VERSION(3, 10) && !defined(Py_XNewRef)
static inline PyObject* _Py_XNewRef(PyObject *obj)
{
    Py_XINCREF(obj);
    return obj;
}
#define Py_XNewRef(obj) _Py_XNewRef(_PyObject_CAST(obj))
#endif


// bpo-39573 added Py_SET_REFCNT() to Python 3.9
#if PY_VERSION_HEX < _Py_PACK_VERSION(3, 9) && !defined(Py_SET_REFCNT)
static inline void _Py_SET_REFCNT(PyObject *ob, Py_ssize_t refcnt)
{
    ob->ob_refcnt = refcnt;
}
#define Py_SET_REFCNT(ob, refcnt) _Py_SET_REFCNT(_PyObject_CAST(ob), refcnt)
#endif


// bpo-43753 added Py_Is(), Py_IsNone(), Py_IsTrue() and Py_IsFalse()
// to Python 3.10.
// PyPy 3.11 provides Py_Is() and Py_IsNone().
// PyPy 3.12 provides Py_IsTrue() and Py_IsFalse().
#if !defined(Py_Is) && PY_VERSION_HEX < _Py_PACK_VERSION(3, 10)
#   define Py_Is(x, y) ((x) == (y))
#   define Py_IsNone(x) Py_Is(x, Py_None)
#endif
#if (!defined(Py_IsTrue) \
     && (PY_VERSION_HEX < _Py_PACK_VERSION(3, 10) || defined(PYPY_VERSION)))
#   define Py_IsTrue(x) Py_Is(x, Py_True)
#   define Py_IsFalse(x) Py_Is(x, Py_False)
#endif


// bpo-39573 added Py_SET_TYPE() to Python 3.9
#if !defined(Py_SET_TYPE) && PY_VERSION_HEX < _Py_PACK_VERSION(3, 9)
static inline void _Py_SET_TYPE(PyObject *ob, PyTypeObject *type)
{
    ob->ob_type = type;
}
#define Py_SET_TYPE(ob, type) _Py_SET_TYPE(_PyObject_CAST(ob), type)
#endif


// bpo-39573 added Py_SET_SIZE() to Python 3.9
#if !defined(Py_SET_SIZE) && PY_VERSION_HEX < _Py_PACK_VERSION(3, 9)
static inline void _Py_SET_SIZE(PyVarObject *ob, Py_ssize_t size)
{
    ob->ob_size = size;
}
#define Py_SET_SIZE(ob, size) _Py_SET_SIZE((PyVarObject*)(ob), size)
#endif


// bpo-40421 added PyFrame_GetCode() to Python 3.9
// PyPy added PyFrame_GetCode() to PyPy3.12 v8.0.0
#if (PY_VERSION_HEX < _Py_PACK_VERSION(3, 9) \
     || (defined(PYPY_VERSION) && PY_VERSION_HEX < _Py_PACK_VERSION(3, 12))) \
     && !defined(Py_LIMITED_API)
static inline PyCodeObject* PyFrame_GetCode(PyFrameObject *frame)
{
    assert(frame != _Py_NULL);
    assert(frame->f_code != _Py_NULL);
    return _Py_CAST(PyCodeObject*, Py_NewRef(frame->f_code));
}
#endif


// bpo-40421 added PyFrame_GetBack() to Python 3.9
#if (PY_VERSION_HEX < _Py_PACK_VERSION(3, 9) \
     && !defined(PYPY_VERSION) && !defined(Py_LIMITED_API))
static inline PyFrameObject* PyFrame_GetBack(PyFrameObject *frame)
{
    assert(frame != _Py_NULL);
    return _Py_CAST(PyFrameObject*, Py_XNewRef(frame->f_back));
}
#endif


// bpo-40421 added PyFrame_GetLocals() to Python 3.11
#if (PY_VERSION_HEX < _Py_PACK_VERSION(3, 11) \
     && !defined(PYPY_VERSION) && !defined(Py_LIMITED_API))
static inline PyObject* PyFrame_GetLocals(PyFrameObject *frame)
{
    if (PyFrame_FastToLocalsWithError(frame) < 0) {
        return NULL;
    }
    return Py_NewRef(frame->f_locals);
}
#endif


// bpo-40421 added PyFrame_GetGlobals() to Python 3.11
#if (PY_VERSION_HEX < _Py_PACK_VERSION(3, 11) \
     && !defined(PYPY_VERSION) && !defined(Py_LIMITED_API))
static inline PyObject* PyFrame_GetGlobals(PyFrameObject *frame)
{
    return Py_NewRef(frame->f_globals);
}
#endif


// bpo-40421 added PyFrame_GetBuiltins() to Python 3.11
#if (PY_VERSION_HEX < _Py_PACK_VERSION(3, 11) \
     && !defined(PYPY_VERSION) && !defined(Py_LIMITED_API))
static inline PyObject* PyFrame_GetBuiltins(PyFrameObject *frame)
{
    return Py_NewRef(frame->f_builtins);
}
#endif


// bpo-40421 added PyFrame_GetLasti() to Python 3.11
#if (PY_VERSION_HEX < _Py_PACK_VERSION(3, 11) \
     && !defined(PYPY_VERSION) && !defined(Py_LIMITED_API))
static inline int PyFrame_GetLasti(PyFrameObject *frame)
{
#if PY_VERSION_HEX >= _Py_PACK_VERSION(3, 10)
    // bpo-27129: Since Python 3.10, f_lasti is an instruction offset,
    // not a bytes offset anymore. Python uses 16-bit "wordcode" (2 bytes)
    // instructions.
    if (frame->f_lasti < 0) {
        return -1;
    }
    return frame->f_lasti * 2;
#else
    return frame->f_lasti;
#endif
}
#endif


// gh-91248 added PyFrame_GetVar() to Python 3.12
#if (PY_VERSION_HEX < _Py_PACK_VERSION(3, 12) \
     && !defined(PYPY_VERSION) && !defined(Py_LIMITED_API))
static inline PyObject* PyFrame_GetVar(PyFrameObject *frame, PyObject *name)
{
    PyObject *locals, *value;

    locals = PyFrame_GetLocals(frame);
    if (locals == NULL) {
        return NULL;
    }
    value = PyDict_GetItemWithError(locals, name);
    Py_DECREF(locals);

    if (value == NULL) {
        if (PyErr_Occurred()) {
            return NULL;
        }
        PyErr_Format(PyExc_NameError, "variable %R does not exist", name);
        return NULL;
    }
    return Py_NewRef(value);
}
#endif


// gh-91248 added PyFrame_GetVarString() to Python 3.12
#if (PY_VERSION_HEX < _Py_PACK_VERSION(3, 12) \
     && !defined(PYPY_VERSION) && !defined(Py_LIMITED_API))
static inline PyObject*
PyFrame_GetVarString(PyFrameObject *frame, const char *name)
{
    PyObject *name_obj, *value;
    name_obj = PyUnicode_FromString(name);
    if (name_obj == NULL) {
        return NULL;
    }
    value = PyFrame_GetVar(frame, name_obj);
    Py_DECREF(name_obj);
    return value;
}
#endif


// Added to Python 3.9 and limited C API 3.9.
// Added to PyPy 3.11.
#if ((PY_VERSION_HEX < _Py_PACK_VERSION(3, 9) \
     || (defined(PYPY_VERSION) && PY_VERSION_HEX < _Py_PACK_VERSION(3, 11))) \
     && !defined(Py_LIMITED_API))
static inline PyInterpreterState *
PyThreadState_GetInterpreter(PyThreadState *tstate)
{
    assert(tstate != _Py_NULL);
    return tstate->interp;
}
#endif


// bpo-40429 added PyThreadState_GetFrame() to Python 3.9
#if (PY_VERSION_HEX < _Py_PACK_VERSION(3, 9) \
     && !defined(PYPY_VERSION) && !defined(Py_LIMITED_API))
static inline PyFrameObject* PyThreadState_GetFrame(PyThreadState *tstate)
{
    assert(tstate != _Py_NULL);
    return _Py_CAST(PyFrameObject *, Py_XNewRef(tstate->frame));
}
#endif


// Added to Python 3.9 and limited C API 3.9. On Windows, it's not available
// before stable ABI 3.10.
// Added to PyPy3.12 v8.0.0.
#if ((PY_VERSION_HEX < _Py_PACK_VERSION(3, 9) \
     || (defined(PYPY_VERSION) && PY_VERSION_HEX < _Py_PACK_VERSION(3, 12))) \
     && !defined(Py_LIMITED_API))
static inline PyInterpreterState* PyInterpreterState_Get(void)
{
    PyThreadState *tstate;
    PyInterpreterState *interp;

    tstate = PyThreadState_GET();
    if (tstate == _Py_NULL) {
        Py_FatalError("GIL released (tstate is NULL)");
    }
    interp = tstate->interp;
    if (interp == _Py_NULL) {
        Py_FatalError("no current interpreter");
    }
    return interp;
}
#endif


// bpo-39947 added PyThreadState_GetID() to Python 3.9
#if (_Py_PACK_VERSION(3, 7) <= PY_VERSION_HEX && PY_VERSION_HEX < _Py_PACK_VERSION(3, 9) \
     && !defined(PYPY_VERSION) && !defined(Py_LIMITED_API))
static inline uint64_t PyThreadState_GetID(PyThreadState *tstate)
{
    assert(tstate != _Py_NULL);
    return tstate->id;
}
#endif

// bpo-43760 added PyThreadState_EnterTracing() to Python 3.11
#if (PY_VERSION_HEX < _Py_PACK_VERSION(3, 11) \
     && !defined(PYPY_VERSION) && !defined(Py_LIMITED_API))
static inline void PyThreadState_EnterTracing(PyThreadState *tstate)
{
    tstate->tracing++;
#if PY_VERSION_HEX >= _Py_PACK_VERSION(3, 10)
    tstate->cframe->use_tracing = 0;
#else
    tstate->use_tracing = 0;
#endif
}
#endif

// bpo-43760 added PyThreadState_LeaveTracing() to Python 3.11
#if (PY_VERSION_HEX < _Py_PACK_VERSION(3, 11) \
     && !defined(PYPY_VERSION) && !defined(Py_LIMITED_API))
static inline void PyThreadState_LeaveTracing(PyThreadState *tstate)
{
    int use_tracing = (tstate->c_tracefunc != _Py_NULL
                       || tstate->c_profilefunc != _Py_NULL);
    tstate->tracing--;
#if PY_VERSION_HEX >= _Py_PACK_VERSION(3, 10)
    tstate->cframe->use_tracing = use_tracing;
#else
    tstate->use_tracing = use_tracing;
#endif
}
#endif


// bpo-37194 added PyObject_CallNoArgs() to Python 3.9
// PyObject_CallNoArgs() added to PyPy 3.9.16-v7.3.11
#if (!defined(PyObject_CallNoArgs) \
     && (PY_VERSION_HEX < _Py_PACK_VERSION(3, 9) \
         || (defined(Py_LIMITED_API) && Py_LIMITED_API+0 < _Py_PACK_VERSION(3, 9))))
static inline PyObject* PyObject_CallNoArgs(PyObject *func)
{
    return PyObject_CallFunctionObjArgs(func, NULL);
}
#endif


// bpo-39245 made PyObject_CallOneArg() public (previously called
// _PyObject_CallOneArg) in Python 3.9
// PyObject_CallOneArg() added to PyPy 3.9.16-v7.3.11
#if (!defined(PyObject_CallOneArg) \
     && (PY_VERSION_HEX < _Py_PACK_VERSION(3, 9) || defined(Py_LIMITED_API)))
static inline PyObject* PyObject_CallOneArg(PyObject *func, PyObject *arg)
{
    return PyObject_CallFunctionObjArgs(func, arg, NULL);
}
#endif


// bpo-1635741 added PyModule_AddObjectRef() to Python 3.10.
// The function was added to the limited C API 3.10.
#if (PY_VERSION_HEX < _Py_PACK_VERSION(3, 10) \
     || (defined(Py_LIMITED_API) && Py_LIMITED_API+0 < _Py_PACK_VERSION(3, 10)) \
         && !(_Py_PACK_VERSION(3, 10) <= PY_VERSION_HEX && PY_VERSION_HEX < _Py_PACK_VERSION(3, 11)))
static inline int
PyModule_AddObjectRef(PyObject *module, const char *name, PyObject *value)
{
    int res;

    if (!value && !PyErr_Occurred()) {
        // PyModule_AddObject() raises TypeError in this case
        PyErr_SetString(PyExc_SystemError,
                        "PyModule_AddObjectRef() must be called "
                        "with an exception raised if value is NULL");
        return -1;
    }

    Py_XINCREF(value);
    res = PyModule_AddObject(module, name, value);
    if (res < 0) {
        Py_XDECREF(value);
    }
    return res;
}
#endif


// bpo-40024 added PyModule_AddType() to Python 3.9
// On Windows, PyModule_AddType() was added to limited C API 3.9.
#if (PY_VERSION_HEX < _Py_PACK_VERSION(3, 9) \
     || (defined(Py_LIMITED_API) && Py_LIMITED_API+0 < _Py_PACK_VERSION(3, 9)) \
     || (defined(Py_LIMITED_API) && Py_LIMITED_API+0 < _Py_PACK_VERSION(3, 10) && defined(MS_WINDOWS)))
static inline int
_PythonCAPICompat_Module_AddType(PyObject *module, PyTypeObject *type)
{
#ifndef Py_LIMITED_API
    const char *name, *dot;
#else
    PyObject *name;
    int res;
#endif

    if (PyType_Ready(type) < 0) {
        return -1;
    }

#ifndef Py_LIMITED_API
    // inline _PyType_Name()
    name = type->tp_name;
    assert(name != _Py_NULL);
    dot = strrchr(name, '.');
    if (dot != _Py_NULL) {
        name = dot + 1;
    }

    return PyModule_AddObjectRef(module, name, _PyObject_CAST(type));
#else
    if (!PyModule_Check(module)) {
        PyErr_SetString(PyExc_TypeError,
                        "PyModule_AddObjectRef() first argument "
                        "must be a module");
        return -1;
    }

    name = PyObject_GetAttrString(_PyObject_CAST(type), "__name__");
    if (name == NULL) {
        return -1;
    }

    PyObject *dict = PyModule_GetDict(module);  // borrowed ref
    res = PyDict_SetItem(dict, name, _PyObject_CAST(type));
    Py_DECREF(name);
    return res;
#endif
}

#if defined(Py_LIMITED_API) && Py_LIMITED_API+0 < _Py_PACK_VERSION(3, 10) && defined(MS_WINDOWS)
    // On Python 3.9, PyModule_AddType() is part of the limited C API,
    // but the function is not exported in the stable ABI.
#   define PyModule_AddType _PythonCAPICompat_Module_AddType
#else
static inline int PyModule_AddType(PyObject *module, PyTypeObject *type)
{
    return _PythonCAPICompat_Module_AddType(module, type);
}
#endif
#endif


// bpo-40241 added PyObject_GC_IsTracked() to Python 3.9.
// bpo-4688 added _PyObject_GC_IS_TRACKED() to Python 2.7.0a2.
// On Windows, PyObject_GC_IsTracked() was only added to stable ABI 3.10.
#if (PY_VERSION_HEX < _Py_PACK_VERSION(3, 9) \
     && !defined(PYPY_VERSION) && !defined(Py_LIMITED_API))
static inline int PyObject_GC_IsTracked(PyObject* obj)
{
    return (PyObject_IS_GC(obj) && _PyObject_GC_IS_TRACKED(obj));
}
#endif

// bpo-40241 added PyObject_GC_IsFinalized() to Python 3.9.
// bpo-18112 added _PyGCHead_FINALIZED() to Python 3.4.0 final.
// On Windows, PyObject_GC_IsFinalized() was only added to stable ABI 3.10.
#if (PY_VERSION_HEX < _Py_PACK_VERSION(3, 9) \
     && !defined(PYPY_VERSION) && !defined(Py_LIMITED_API))
static inline int PyObject_GC_IsFinalized(PyObject *obj)
{
    PyGC_Head *gc = _Py_CAST(PyGC_Head*, obj) - 1;
    return (PyObject_IS_GC(obj) && _PyGCHead_FINALIZED(gc));
}
#endif


// bpo-39573 added Py_IS_TYPE() to Python 3.9
#if  !defined(Py_IS_TYPE) && PY_VERSION_HEX < _Py_PACK_VERSION(3, 9)
static inline int _Py_IS_TYPE(PyObject *ob, PyTypeObject *type) {
    return Py_TYPE(ob) == type;
}
#define Py_IS_TYPE(ob, type) _Py_IS_TYPE(_PyObject_CAST(ob), type)
#endif


// bpo-46906 added PyFloat_Pack2() and PyFloat_Unpack2() to Python 3.11a7.
// bpo-11734 added _PyFloat_Pack2() and _PyFloat_Unpack2() to Python 3.6.
// Python 3.11a2 moved _PyFloat_Pack2() and _PyFloat_Unpack2() to the internal
// C API: Python 3.11a2-3.11a6 versions are not supported.
#if (PY_VERSION_HEX <= _Py_PACK_VERSION(3, 11) \
     && !defined(PYPY_VERSION) && !defined(Py_LIMITED_API))
static inline int PyFloat_Pack2(double x, char *p, int le)
{ return _PyFloat_Pack2(x, (unsigned char*)p, le); }

static inline double PyFloat_Unpack2(const char *p, int le)
{ return _PyFloat_Unpack2((const unsigned char *)p, le); }
#endif


// bpo-46906 added PyFloat_Pack4(), PyFloat_Pack8(), PyFloat_Unpack4() and
// PyFloat_Unpack8() to Python 3.11a7.
// Python 3.11a2 moved _PyFloat_Pack4(), _PyFloat_Pack8(), _PyFloat_Unpack4()
// and _PyFloat_Unpack8() to the internal C API: Python 3.11a2-3.11a6 versions
// are not supported.
#if (PY_VERSION_HEX <= _Py_PACK_VERSION(3, 11) \
     && !defined(PYPY_VERSION) && !defined(Py_LIMITED_API))
static inline int PyFloat_Pack4(double x, char *p, int le)
{ return _PyFloat_Pack4(x, (unsigned char*)p, le); }

static inline int PyFloat_Pack8(double x, char *p, int le)
{ return _PyFloat_Pack8(x, (unsigned char*)p, le); }

static inline double PyFloat_Unpack4(const char *p, int le)
{ return _PyFloat_Unpack4((const unsigned char *)p, le); }

static inline double PyFloat_Unpack8(const char *p, int le)
{ return _PyFloat_Unpack8((const unsigned char *)p, le); }
#endif


// gh-92154 added PyCode_GetCode() to Python 3.11
#if (PY_VERSION_HEX < _Py_PACK_VERSION(3, 11) \
     && !defined(PYPY_VERSION) && !defined(Py_LIMITED_API))
static inline PyObject* PyCode_GetCode(PyCodeObject *code)
{
    return Py_NewRef(code->co_code);
}
#endif


// gh-95008 added PyCode_GetVarnames() to Python 3.11.0rc1
#if (PY_VERSION_HEX < _Py_PACK_VERSION(3, 11) \
     && !defined(PYPY_VERSION) && !defined(Py_LIMITED_API))
static inline PyObject* PyCode_GetVarnames(PyCodeObject *code)
{
    return Py_NewRef(code->co_varnames);
}
#endif

// gh-95008 added PyCode_GetFreevars() to Python 3.11.0rc1
#if (PY_VERSION_HEX < _Py_PACK_VERSION(3, 11) \
     && !defined(PYPY_VERSION) && !defined(Py_LIMITED_API))
static inline PyObject* PyCode_GetFreevars(PyCodeObject *code)
{
    return Py_NewRef(code->co_freevars);
}
#endif

// gh-95008 added PyCode_GetCellvars() to Python 3.11.0rc1
#if (PY_VERSION_HEX < _Py_PACK_VERSION(3, 11) \
     && !defined(PYPY_VERSION) && !defined(Py_LIMITED_API))
static inline PyObject* PyCode_GetCellvars(PyCodeObject *code)
{
    return Py_NewRef(code->co_cellvars);
}
#endif


// Py_UNUSED() was added to Python 3.4.
#ifndef Py_UNUSED
#   if defined(__GNUC__) || defined(__clang__)
#       define Py_UNUSED(name) _unused_ ## name __attribute__((unused))
#   else
#       define Py_UNUSED(name) _unused_ ## name
#   endif
#endif


// PyImport_AddModuleRef() was added to Python 3.13 and limited C API 3.13
#if (PY_VERSION_HEX < _Py_PACK_VERSION(3, 13) \
        || (defined(Py_LIMITED_API) && Py_LIMITED_API+0 < _Py_PACK_VERSION(3, 13)))
static inline PyObject* PyImport_AddModuleRef(const char *name)
{
    return Py_XNewRef(PyImport_AddModule(name));
}
#endif


// gh-105927 added PyWeakref_GetRef() to Python 3.13
#if (PY_VERSION_HEX < _Py_PACK_VERSION(3, 13) \
     || (defined(Py_LIMITED_API) && Py_LIMITED_API+0 < _Py_PACK_VERSION(3, 13)))

#if (defined(Py_LIMITED_API) && Py_LIMITED_API+0 < _Py_PACK_VERSION(3, 13) \
     && PY_VERSION_HEX >= _Py_PACK_VERSION(3, 15))
// Function removed from Python 3.15 C API, but it remains available
// in the stable ABI
PyAPI_FUNC(PyObject *) PyWeakref_GetObject(PyObject *ref);
#endif

static inline int PyWeakref_GetRef(PyObject *ref, PyObject **pobj)
{
    PyObject *obj;
    if (ref != NULL && !PyWeakref_Check(ref)) {
        *pobj = NULL;
        PyErr_SetString(PyExc_TypeError, "expected a weakref");
        return -1;
    }

_Py_COMP_DIAG_PUSH
_Py_COMP_DIAG_IGNORE_DEPR_DECLS
    obj = PyWeakref_GetObject(ref);
_Py_COMP_DIAG_POP
    if (obj == NULL) {
        // SystemError if ref is NULL
        *pobj = NULL;
        return -1;
    }
    if (obj == Py_None) {
        *pobj = NULL;
        return 0;
    }
    *pobj = Py_NewRef(obj);
    return 1;
}
#endif


// bpo-36974 added PY_VECTORCALL_ARGUMENTS_OFFSET to Python 3.8b1
#ifndef PY_VECTORCALL_ARGUMENTS_OFFSET
#  define PY_VECTORCALL_ARGUMENTS_OFFSET (_Py_CAST(size_t, 1) << (8 * sizeof(size_t) - 1))
#endif

// bpo-36974 added PyVectorcall_NARGS() to Python 3.8b1
#if (PY_VERSION_HEX < _Py_PACK_VERSION(3, 8) \
     || (defined(Py_LIMITED_API) && PY_VERSION_HEX < _Py_PACK_VERSION(3, 12)))
static inline Py_ssize_t PyVectorcall_NARGS(size_t n)
{
    return n & ~PY_VECTORCALL_ARGUMENTS_OFFSET;
}
#endif


// gh-105922 added PyObject_Vectorcall() to Python 3.9
#if (PY_VERSION_HEX < _Py_PACK_VERSION(3, 9) \
     || (defined(Py_LIMITED_API) && Py_LIMITED_API+0 < _Py_PACK_VERSION(3, 12)))
static inline PyObject*
PyObject_Vectorcall(PyObject *callable, PyObject *const *args,
                     size_t nargsf, PyObject *kwnames)
{
#if (PY_VERSION_HEX >= _Py_PACK_VERSION(3, 8) \
     && !defined(PYPY_VERSION) && !defined(Py_LIMITED_API))
    // bpo-36974 added _PyObject_Vectorcall() to Python 3.8
    return _PyObject_Vectorcall(callable, args, nargsf, kwnames);
#else
    PyObject *posargs = NULL, *kwargs = NULL;
    PyObject *res;
    Py_ssize_t nposargs, nkwargs, i;

    if (nargsf != 0 && args == NULL) {
        PyErr_BadInternalCall();
        goto error;
    }
    if (kwnames != NULL && !PyTuple_Check(kwnames)) {
        PyErr_BadInternalCall();
        goto error;
    }

    nposargs = (Py_ssize_t)PyVectorcall_NARGS(nargsf);
    if (kwnames) {
#ifndef Py_LIMITED_API
        nkwargs = PyTuple_GET_SIZE(kwnames);
#else
        nkwargs = PyTuple_Size(kwnames);
#endif
    }
    else {
        nkwargs = 0;
    }

    posargs = PyTuple_New(nposargs);
    if (posargs == NULL) {
        goto error;
    }
    if (nposargs) {
        for (i=0; i < nposargs; i++) {
#ifndef Py_LIMITED_API
            PyTuple_SET_ITEM(posargs, i, Py_NewRef(*args));
#else
            if (PyTuple_SetItem(posargs, i, Py_NewRef(*args)) < 0) {
                goto error;
            }
#endif
            args++;
        }
    }

    if (nkwargs) {
        kwargs = PyDict_New();
        if (kwargs == NULL) {
            goto error;
        }

        for (i = 0; i < nkwargs; i++) {
#ifndef Py_LIMITED_API
            PyObject *key = PyTuple_GET_ITEM(kwnames, i);  // borrowed ref
#else
            PyObject *key = PyTuple_GetItem(kwnames, i);  // borrowed ref
            if (key == NULL) {
                goto error;
            }
#endif
            PyObject *value = *args;
            args++;
            if (PyDict_SetItem(kwargs, key, value) < 0) {
                goto error;
            }
        }
    }
    else {
        kwargs = NULL;
    }

    res = PyObject_Call(callable, posargs, kwargs);
    Py_DECREF(posargs);
    Py_XDECREF(kwargs);
    return res;

error:
    Py_DECREF(posargs);
    Py_XDECREF(kwargs);
    return NULL;
#endif
}
#endif


// gh-106521 added PyObject_GetOptionalAttr() and
// PyObject_GetOptionalAttrString() to Python 3.13
#if (PY_VERSION_HEX < _Py_PACK_VERSION(3, 13) \
     || (defined(Py_LIMITED_API) && Py_LIMITED_API+0 < _Py_PACK_VERSION(3, 13)))
static inline int
PyObject_GetOptionalAttr(PyObject *obj, PyObject *attr_name, PyObject **result)
{
    // bpo-32571 added _PyObject_LookupAttr() to Python 3.7
#if (PY_VERSION_HEX >= _Py_PACK_VERSION(3, 7) \
     && !defined(PYPY_VERSION) && !defined(Py_LIMITED_API))
    return _PyObject_LookupAttr(obj, attr_name, result);
#else
    *result = PyObject_GetAttr(obj, attr_name);
    if (*result != NULL) {
        return 1;
    }
    if (!PyErr_Occurred()) {
        return 0;
    }
    if (PyErr_ExceptionMatches(PyExc_AttributeError)) {
        PyErr_Clear();
        return 0;
    }
    return -1;
#endif
}

static inline int
PyObject_GetOptionalAttrString(PyObject *obj, const char *attr_name, PyObject **result)
{
    int rc;
    PyObject *name_obj = PyUnicode_FromString(attr_name);
    if (name_obj == NULL) {
        *result = NULL;
        return -1;
    }
    rc = PyObject_GetOptionalAttr(obj, name_obj, result);
    Py_DECREF(name_obj);
    return rc;
}
#endif


// gh-106307 added PyObject_GetOptionalAttr() and
// PyMapping_GetOptionalItemString() to Python 3.13
#if (PY_VERSION_HEX < _Py_PACK_VERSION(3, 13) \
     || (defined(Py_LIMITED_API) && Py_LIMITED_API+0 < _Py_PACK_VERSION(3, 13)))
static inline int
PyMapping_GetOptionalItem(PyObject *obj, PyObject *key, PyObject **result)
{
    *result = PyObject_GetItem(obj, key);
    if (*result) {
        return 1;
    }
    if (!PyErr_ExceptionMatches(PyExc_KeyError)) {
        return -1;
    }
    PyErr_Clear();
    return 0;
}

static inline int
PyMapping_GetOptionalItemString(PyObject *obj, const char *key, PyObject **result)
{
    int rc;
    PyObject *key_obj = PyUnicode_FromString(key);
    if (key_obj == NULL) {
        *result = NULL;
        return -1;
    }
    rc = PyMapping_GetOptionalItem(obj, key_obj, result);
    Py_DECREF(key_obj);
    return rc;
}
#endif

// gh-108511 added PyMapping_HasKeyWithError() and
// PyMapping_HasKeyStringWithError() to Python 3.13
#if PY_VERSION_HEX < _Py_PACK_VERSION(3, 13)
static inline int
PyMapping_HasKeyWithError(PyObject *obj, PyObject *key)
{
    PyObject *res;
    int rc = PyMapping_GetOptionalItem(obj, key, &res);
    Py_XDECREF(res);
    return rc;
}

static inline int
PyMapping_HasKeyStringWithError(PyObject *obj, const char *key)
{
    PyObject *res;
    int rc = PyMapping_GetOptionalItemString(obj, key, &res);
    Py_XDECREF(res);
    return rc;
}
#endif


// gh-108511 added PyObject_HasAttrWithError() and
// PyObject_HasAttrStringWithError() to Python 3.13
#if (PY_VERSION_HEX < _Py_PACK_VERSION(3, 13) \
     || (defined(Py_LIMITED_API) && Py_LIMITED_API+0 < _Py_PACK_VERSION(3, 13)))
static inline int
PyObject_HasAttrWithError(PyObject *obj, PyObject *attr)
{
    PyObject *res;
    int rc = PyObject_GetOptionalAttr(obj, attr, &res);
    Py_XDECREF(res);
    return rc;
}

static inline int
PyObject_HasAttrStringWithError(PyObject *obj, const char *attr)
{
    PyObject *res;
    int rc = PyObject_GetOptionalAttrString(obj, attr, &res);
    Py_XDECREF(res);
    return rc;
}
#endif


// gh-106004 added PyDict_GetItemRef() and PyDict_GetItemStringRef()
// to Python 3.13
#if (PY_VERSION_HEX < _Py_PACK_VERSION(3, 13) \
     || (defined(Py_LIMITED_API) && Py_LIMITED_API+0 < _Py_PACK_VERSION(3, 13)))
static inline int
PyDict_GetItemRef(PyObject *mp, PyObject *key, PyObject **result)
{
    PyObject *item = PyDict_GetItemWithError(mp, key);
    if (item != NULL) {
        *result = Py_NewRef(item);
        return 1;  // found
    }
    if (!PyErr_Occurred()) {
        *result = NULL;
        return 0;  // not found
    }
    *result = NULL;
    return -1;
}

static inline int
PyDict_GetItemStringRef(PyObject *mp, const char *key, PyObject **result)
{
    int res;
    PyObject *key_obj = PyUnicode_FromString(key);
    if (key_obj == NULL) {
        *result = NULL;
        return -1;
    }
    res = PyDict_GetItemRef(mp, key_obj, result);
    Py_DECREF(key_obj);
    return res;
}
#endif


// gh-106307 added PyModule_Add() to Python 3.13
#if (PY_VERSION_HEX < _Py_PACK_VERSION(3, 13) \
     || (defined(Py_LIMITED_API) && Py_LIMITED_API+0 < _Py_PACK_VERSION(3, 13)))
static inline int
PyModule_Add(PyObject *mod, const char *name, PyObject *value)
{
    int res = PyModule_AddObjectRef(mod, name, value);
    Py_XDECREF(value);
    return res;
}
#endif


// gh-108014 added Py_IsFinalizing() to Python 3.13 (limited C API).
// bpo-1856 added _Py_Finalizing to Python 3.2.1b1.
// _Py_IsFinalizing() was added to PyPy 7.3.0.
#if ((PY_VERSION_HEX < _Py_PACK_VERSION(3, 13)) \
     && (!defined(PYPY_VERSION_NUM) || PYPY_VERSION_NUM >= 0x7030000) \
     && !defined(Py_LIMITED_API))
static inline int Py_IsFinalizing(void)
{
#if PY_VERSION_HEX >= _Py_PACK_VERSION(3, 7)
    // _Py_IsFinalizing() was added to Python 3.7.
    return _Py_IsFinalizing();
#else
    return (_Py_Finalizing != NULL);
#endif
}
#endif


// gh-108323 added PyDict_ContainsString() to Python 3.13
#if PY_VERSION_HEX < _Py_PACK_VERSION(3, 13) || defined(Py_LIMITED_API)
static inline int PyDict_ContainsString(PyObject *op, const char *key)
{
    PyObject *key_obj = PyUnicode_FromString(key);
    if (key_obj == NULL) {
        return -1;
    }
    int res = PyDict_Contains(op, key_obj);
    Py_DECREF(key_obj);
    return res;
}
#endif


// gh-108445 added PyLong_AsInt() to Python 3.13
#if (PY_VERSION_HEX < _Py_PACK_VERSION(3, 13) \
     || (defined(Py_LIMITED_API) && Py_LIMITED_API+0 < _Py_PACK_VERSION(3, 13)))
static inline int PyLong_AsInt(PyObject *obj)
{
#if defined(PYPY_VERSION) || defined(Py_LIMITED_API)
    long value = PyLong_AsLong(obj);
    if (value == -1 && PyErr_Occurred()) {
        return -1;
    }
    if (value < (long)INT_MIN || (long)INT_MAX < value) {
        PyErr_SetString(PyExc_OverflowError,
                        "Python int too large to convert to C int");
        return -1;
    }
    return (int)value;
#else
    return _PyLong_AsInt(obj);
#endif
}
#endif


// gh-107073 added PyObject_VisitManagedDict() to Python 3.13
#if PY_VERSION_HEX < _Py_PACK_VERSION(3, 13) && !defined(Py_LIMITED_API)
static inline int
PyObject_VisitManagedDict(PyObject *obj, visitproc visit, void *arg)
{
    PyObject **dict = _PyObject_GetDictPtr(obj);
    if (dict == NULL || *dict == NULL) {
        // Nothing to do.
        return 0;
    }
    Py_VISIT(*dict);
    return 0;
}

static inline void
PyObject_ClearManagedDict(PyObject *obj)
{
    PyObject **dict = _PyObject_GetDictPtr(obj);
    if (dict == NULL || *dict == NULL) {
        return;
    }
    Py_CLEAR(*dict);
}
#endif

// gh-108867 added PyThreadState_GetUnchecked() to Python 3.13
// Python 3.5.2 added _PyThreadState_UncheckedGet().
#if PY_VERSION_HEX < _Py_PACK_VERSION(3, 13) && !defined(Py_LIMITED_API)
static inline PyThreadState*
PyThreadState_GetUnchecked(void)
{
    return _PyThreadState_UncheckedGet();
}
#endif

// gh-110289 added PyUnicode_EqualToUTF8() and PyUnicode_EqualToUTF8AndSize()
// to Python 3.13
#if (PY_VERSION_HEX < _Py_PACK_VERSION(3, 13) \
     || (defined(Py_LIMITED_API) && Py_LIMITED_API+0 < _Py_PACK_VERSION(3, 13)))
static inline int
PyUnicode_EqualToUTF8AndSize(PyObject *unicode, const char *str, Py_ssize_t str_len)
{
    Py_ssize_t len;
#if defined(Py_LIMITED_API) && Py_LIMITED_API+0 < _Py_PACK_VERSION(3, 10)
    PyObject *bytes;
#endif
    const void *utf8;
    PyObject *exc_type, *exc_value, *exc_tb;
    int res;

    // API cannot report errors so save/restore the exception
    PyErr_Fetch(&exc_type, &exc_value, &exc_tb);

#ifndef Py_LIMITED_API
    if (PyUnicode_READY(unicode) < 0) {
        // Memory allocation failure. The API cannot report error,
        // so ignore the exception and return 0.
        res = 0;
        goto done;
    }

    if (PyUnicode_IS_ASCII(unicode)) {
        utf8 = PyUnicode_DATA(unicode);
        len = PyUnicode_GET_LENGTH(unicode);
    }
    else
#endif
    {
#if defined(Py_LIMITED_API) && Py_LIMITED_API+0 < _Py_PACK_VERSION(3, 10)
        // Limited C API 3.9 and older
        bytes = PyUnicode_AsUTF8String(unicode);
        if (bytes == NULL) {
            // Memory allocation failure. The API cannot report error,
            // so ignore the exception and return 0.
            res = 0;
            goto done;
        }
        utf8 = PyBytes_AsString(bytes);
        len = PyBytes_Size(bytes);
#else
        // Python 3.12 and older, and limited C API 3.10 and newer.
        // Python 3.10 added PyUnicode_AsUTF8AndSize() to the limited C API.
        utf8 = PyUnicode_AsUTF8AndSize(unicode, &len);
        if (utf8 == NULL) {
            // Memory allocation failure. The API cannot report error,
            // so ignore the exception and return 0.
            res = 0;
            goto done;
        }
#endif
    }

    if (len != str_len) {
        res = 0;
    }
    else {
        res = (memcmp(utf8, str, (size_t)len) == 0);
    }
#if defined(Py_LIMITED_API) && Py_LIMITED_API+0 < _Py_PACK_VERSION(3, 10)
    Py_DECREF(bytes);
#endif

done:
    PyErr_Restore(exc_type, exc_value, exc_tb);
    return res;
}

static inline int
PyUnicode_EqualToUTF8(PyObject *unicode, const char *str)
{
    return PyUnicode_EqualToUTF8AndSize(unicode, str, (Py_ssize_t)strlen(str));
}
#endif


// gh-111138 added PyList_Extend() and PyList_Clear() to Python 3.13
#if PY_VERSION_HEX < _Py_PACK_VERSION(3, 13) || defined(Py_LIMITED_API)
static inline int
PyList_Extend(PyObject *list, PyObject *iterable)
{
    return PyList_SetSlice(list, PY_SSIZE_T_MAX, PY_SSIZE_T_MAX, iterable);
}

static inline int
PyList_Clear(PyObject *list)
{
    return PyList_SetSlice(list, 0, PY_SSIZE_T_MAX, NULL);
}
#endif

// gh-111262 added PyDict_Pop() and PyDict_PopString() to Python 3.13
#if PY_VERSION_HEX < _Py_PACK_VERSION(3, 13) || defined(Py_LIMITED_API)
static inline int
PyDict_Pop(PyObject *dict, PyObject *key, PyObject **result)
{
    PyObject *value;

    if (!PyDict_Check(dict)) {
        PyErr_BadInternalCall();
        if (result) {
            *result = NULL;
        }
        return -1;
    }

    // bpo-16991 added _PyDict_Pop() to Python 3.5.
    // Python 3.6 changed _PyDict_Pop() first argument type to PyObject*.
    // Python 3.13 removed _PyDict_Pop().
#if defined(PYPY_VERSION) || PY_VERSION_HEX >= _Py_PACK_VERSION(3, 13) || defined(Py_LIMITED_API)
    value = PyObject_CallMethod(dict, "pop", "O", key);
#else
    value = _PyDict_Pop(dict, key, NULL);
#endif
    if (value == NULL) {
        if (result) {
            *result = NULL;
        }
        if (PyErr_Occurred() && !PyErr_ExceptionMatches(PyExc_KeyError)) {
            return -1;
        }
        PyErr_Clear();
        return 0;
    }
    if (result) {
        *result = value;
    }
    else {
        Py_DECREF(value);
    }
    return 1;
}

static inline int
PyDict_PopString(PyObject *dict, const char *key, PyObject **result)
{
    PyObject *key_obj = PyUnicode_FromString(key);
    if (key_obj == NULL) {
        if (result != NULL) {
            *result = NULL;
        }
        return -1;
    }

    int res = PyDict_Pop(dict, key_obj, result);
    Py_DECREF(key_obj);
    return res;
}
#endif


// gh-111545 added Py_HashPointer() to Python 3.13
#if PY_VERSION_HEX < _Py_PACK_VERSION(3, 13) || defined(Py_LIMITED_API)
static inline Py_hash_t Py_HashPointer(const void *ptr)
{
#if PY_VERSION_HEX >= _Py_PACK_VERSION(3, 9) && !defined(PYPY_VERSION) && !defined(Py_LIMITED_API)
    return _Py_HashPointer(ptr);
#elif !defined(Py_LIMITED_API)
    // PyPy _Py_HashPointer() argument type is "void*", not "const void*"
    return _Py_HashPointer(_Py_CAST(void*, ptr));
#else
    // Limited C API implementation
    uintptr_t x = (uintptr_t)ptr;
    Py_BUILD_ASSERT(sizeof(x) == sizeof(ptr));

    // Bottom 3 or 4 bits are likely to be 0; rotate x by 4 to the right
    // to avoid excessive hash collisions for dicts and sets.
    x = (x >> 4) | (x << (8 * sizeof(uintptr_t) - 4));

    if (x == (uintptr_t)-1) {
        x = (uintptr_t)-2;
    }

    Py_BUILD_ASSERT(sizeof(x) == sizeof(Py_hash_t));
    return (Py_hash_t)x;
#endif
}
#endif


#if PY_VERSION_HEX < _Py_PACK_VERSION(3, 13) || defined(Py_LIMITED_API)
static inline Py_hash_t
PyObject_GenericHash(PyObject *obj)
{
    return Py_HashPointer(obj);
}
#endif


// Python 3.13a4 added a PyTime API.
// Use the private API added to Python 3.5.
#if PY_VERSION_HEX < _Py_PACK_VERSION(3, 13) && !defined(Py_LIMITED_API)
typedef _PyTime_t PyTime_t;
#define PyTime_MIN _PyTime_MIN
#define PyTime_MAX _PyTime_MAX

static inline double PyTime_AsSecondsDouble(PyTime_t t)
{ return _PyTime_AsSecondsDouble(t); }

static inline int PyTime_Monotonic(PyTime_t *result)
{ return _PyTime_GetMonotonicClockWithInfo(result, NULL); }

static inline int PyTime_Time(PyTime_t *result)
{ return _PyTime_GetSystemClockWithInfo(result, NULL); }

static inline int PyTime_PerfCounter(PyTime_t *result)
{
#if PY_VERSION_HEX >= _Py_PACK_VERSION(3, 7) && !defined(PYPY_VERSION)
    return _PyTime_GetPerfCounterWithInfo(result, NULL);
#elif PY_VERSION_HEX >= _Py_PACK_VERSION(3, 7)
    // Call time.perf_counter_ns() and convert Python int object to PyTime_t.
    // Cache time.perf_counter_ns() function for best performance.
    static PyObject *func = NULL;
    if (func == NULL) {
        PyObject *mod = PyImport_ImportModule("time");
        if (mod == NULL) {
            return -1;
        }

        func = PyObject_GetAttrString(mod, "perf_counter_ns");
        Py_DECREF(mod);
        if (func == NULL) {
            return -1;
        }
    }

    PyObject *res = PyObject_CallNoArgs(func);
    if (res == NULL) {
        return -1;
    }
    long long value = PyLong_AsLongLong(res);
    Py_DECREF(res);

    if (value == -1 && PyErr_Occurred()) {
        return -1;
    }

    Py_BUILD_ASSERT(sizeof(value) >= sizeof(PyTime_t));
    *result = (PyTime_t)value;
    return 0;
#else
    // Call time.perf_counter() and convert C double to PyTime_t.
    // Cache time.perf_counter() function for best performance.
    static PyObject *func = NULL;
    if (func == NULL) {
        PyObject *mod = PyImport_ImportModule("time");
        if (mod == NULL) {
            return -1;
        }

        func = PyObject_GetAttrString(mod, "perf_counter");
        Py_DECREF(mod);
        if (func == NULL) {
            return -1;
        }
    }

    PyObject *res = PyObject_CallNoArgs(func);
    if (res == NULL) {
        return -1;
    }
    double d = PyFloat_AsDouble(res);
    Py_DECREF(res);

    if (d == -1.0 && PyErr_Occurred()) {
        return -1;
    }

    // Avoid floor() to avoid having to link to libm
    *result = (PyTime_t)(d * 1e9);
    return 0;
#endif
}

#endif

// gh-111389 added hash constants to Python 3.13. These constants were
// added first as private macros to Python 3.4 and PyPy 7.3.8.
#if (!defined(PyHASH_BITS) \
     && ((!defined(PYPY_VERSION) && PY_VERSION_HEX >= _Py_PACK_VERSION(3, 4)) \
         || (defined(PYPY_VERSION) && PY_VERSION_HEX >= _Py_PACK_VERSION(3, 7) \
             && PYPY_VERSION_NUM >= _Py_PACK_FULL_VERSION(7, 3, 8, 0, 0))) \
     && !defined(Py_LIMITED_API))
#   define PyHASH_BITS _PyHASH_BITS
#   define PyHASH_MODULUS _PyHASH_MODULUS
#   define PyHASH_INF _PyHASH_INF
#   define PyHASH_IMAG _PyHASH_IMAG
#endif


// gh-111545 added Py_GetConstant() and Py_GetConstantBorrowed()
// to Python 3.13
#if (PY_VERSION_HEX < _Py_PACK_VERSION(3, 13) \
     || (defined(Py_LIMITED_API) && Py_LIMITED_API+0 < _Py_PACK_VERSION(3, 13)))

#ifndef Py_CONSTANT_NONE
#   define Py_CONSTANT_NONE 0
#   define Py_CONSTANT_FALSE 1
#   define Py_CONSTANT_TRUE 2
#   define Py_CONSTANT_ELLIPSIS 3
#   define Py_CONSTANT_NOT_IMPLEMENTED 4
#   define Py_CONSTANT_ZERO 5
#   define Py_CONSTANT_ONE 6
#   define Py_CONSTANT_EMPTY_STR 7
#   define Py_CONSTANT_EMPTY_BYTES 8
#   define Py_CONSTANT_EMPTY_TUPLE 9
#endif

static inline PyObject* Py_GetConstant(unsigned int constant_id)
{
    static PyObject* constants[Py_CONSTANT_EMPTY_TUPLE + 1] = {NULL};

    if (constants[Py_CONSTANT_NONE] == NULL) {
        constants[Py_CONSTANT_NONE] = Py_None;
        constants[Py_CONSTANT_FALSE] = Py_False;
        constants[Py_CONSTANT_TRUE] = Py_True;
        constants[Py_CONSTANT_ELLIPSIS] = Py_Ellipsis;
        constants[Py_CONSTANT_NOT_IMPLEMENTED] = Py_NotImplemented;

        constants[Py_CONSTANT_ZERO] = PyLong_FromLong(0);
        if (constants[Py_CONSTANT_ZERO] == NULL) {
            goto fatal_error;
        }

        constants[Py_CONSTANT_ONE] = PyLong_FromLong(1);
        if (constants[Py_CONSTANT_ONE] == NULL) {
            goto fatal_error;
        }

        constants[Py_CONSTANT_EMPTY_STR] = PyUnicode_FromStringAndSize("", 0);
        if (constants[Py_CONSTANT_EMPTY_STR] == NULL) {
            goto fatal_error;
        }

        constants[Py_CONSTANT_EMPTY_BYTES] = PyBytes_FromStringAndSize("", 0);
        if (constants[Py_CONSTANT_EMPTY_BYTES] == NULL) {
            goto fatal_error;
        }

        constants[Py_CONSTANT_EMPTY_TUPLE] = PyTuple_New(0);
        if (constants[Py_CONSTANT_EMPTY_TUPLE] == NULL) {
            goto fatal_error;
        }
        // goto dance to avoid compiler warnings about Py_FatalError()
        goto init_done;

fatal_error:
        // This case should never happen
        Py_FatalError("Py_GetConstant() failed to get constants");
    }

init_done:
    if (constant_id <= Py_CONSTANT_EMPTY_TUPLE) {
        return Py_NewRef(constants[constant_id]);
    }
    else {
        PyErr_BadInternalCall();
        return NULL;
    }
}

static inline PyObject* Py_GetConstantBorrowed(unsigned int constant_id)
{
    PyObject *obj = Py_GetConstant(constant_id);
    Py_XDECREF(obj);
    return obj;
}
#endif


// gh-114329 added PyList_GetItemRef() to Python 3.13
#if (PY_VERSION_HEX < _Py_PACK_VERSION(3, 13) \
     || (defined(Py_LIMITED_API) && Py_LIMITED_API+0 < _Py_PACK_VERSION(3, 13)))
static inline PyObject *
PyList_GetItemRef(PyObject *op, Py_ssize_t index)
{
    PyObject *item = PyList_GetItem(op, index);
    Py_XINCREF(item);
    return item;
}
#endif


// gh-114329 added PyList_GetItemRef() to Python 3.13
#if (PY_VERSION_HEX < _Py_PACK_VERSION(3, 13) \
     || (defined(Py_LIMITED_API) && Py_LIMITED_API+0 < _Py_PACK_VERSION(3, 15)))
static inline int
PyDict_SetDefaultRef(PyObject *d, PyObject *key, PyObject *default_value,
                     PyObject **result)
{
    PyObject *value;
    if (PyDict_GetItemRef(d, key, &value) < 0) {
        // get error
        if (result) {
            *result = NULL;
        }
        return -1;
    }
    if (value != NULL) {
        // present
        if (result) {
            *result = value;
        }
        else {
            Py_DECREF(value);
        }
        return 1;
    }

    // missing: set the item
    if (PyDict_SetItem(d, key, default_value) < 0) {
        // set error
        if (result) {
            *result = NULL;
        }
        return -1;
    }
    if (result) {
        *result = Py_NewRef(default_value);
    }
    return 0;
}
#endif

#if PY_VERSION_HEX < _Py_PACK_VERSION(3, 13)
#   define Py_BEGIN_CRITICAL_SECTION(op) {
#   define Py_END_CRITICAL_SECTION() }
#   define Py_BEGIN_CRITICAL_SECTION2(a, b) {
#   define Py_END_CRITICAL_SECTION2() }
#endif

#if (PY_VERSION_HEX < _Py_PACK_VERSION(3, 14) \
     && !defined(PYPY_VERSION) && !defined(Py_LIMITED_API))
typedef struct PyUnicodeWriter PyUnicodeWriter;

static inline void PyUnicodeWriter_Discard(PyUnicodeWriter *writer)
{
    _PyUnicodeWriter_Dealloc((_PyUnicodeWriter*)writer);
    PyMem_Free(writer);
}

static inline PyUnicodeWriter* PyUnicodeWriter_Create(Py_ssize_t length)
{
    if (length < 0) {
        PyErr_SetString(PyExc_ValueError,
                        "length must be positive");
        return NULL;
    }

    const size_t size = sizeof(_PyUnicodeWriter);
    PyUnicodeWriter *pub_writer = (PyUnicodeWriter *)PyMem_Malloc(size);
    if (pub_writer == _Py_NULL) {
        PyErr_NoMemory();
        return _Py_NULL;
    }
    _PyUnicodeWriter *writer = (_PyUnicodeWriter *)pub_writer;

    _PyUnicodeWriter_Init(writer);
    if (_PyUnicodeWriter_Prepare(writer, length, 127) < 0) {
        PyUnicodeWriter_Discard(pub_writer);
        return NULL;
    }
    writer->overallocate = 1;
    return pub_writer;
}

static inline PyObject* PyUnicodeWriter_Finish(PyUnicodeWriter *writer)
{
    PyObject *str = _PyUnicodeWriter_Finish((_PyUnicodeWriter*)writer);
    assert(((_PyUnicodeWriter*)writer)->buffer == NULL);
    PyMem_Free(writer);
    return str;
}

static inline int
PyUnicodeWriter_WriteChar(PyUnicodeWriter *writer, Py_UCS4 ch)
{
    if (ch > 0x10ffff) {
        PyErr_SetString(PyExc_ValueError,
                        "character must be in range(0x110000)");
        return -1;
    }

    return _PyUnicodeWriter_WriteChar((_PyUnicodeWriter*)writer, ch);
}

static inline int
PyUnicodeWriter_WriteStr(PyUnicodeWriter *writer, PyObject *obj)
{
    PyObject *str = PyObject_Str(obj);
    if (str == NULL) {
        return -1;
    }

    int res = _PyUnicodeWriter_WriteStr((_PyUnicodeWriter*)writer, str);
    Py_DECREF(str);
    return res;
}

static inline int
PyUnicodeWriter_WriteRepr(PyUnicodeWriter *writer, PyObject *obj)
{
    if (obj == NULL) {
        return _PyUnicodeWriter_WriteASCIIString((_PyUnicodeWriter*)writer,
                                                 "<NULL>", 6);
    }

    PyObject *str = PyObject_Repr(obj);
    if (str == NULL) {
        return -1;
    }

    int res = _PyUnicodeWriter_WriteStr((_PyUnicodeWriter*)writer, str);
    Py_DECREF(str);
    return res;
}

static inline int
PyUnicodeWriter_WriteUTF8(PyUnicodeWriter *writer,
                          const char *str, Py_ssize_t size)
{
    if (size < 0) {
        size = (Py_ssize_t)strlen(str);
    }

    PyObject *str_obj = PyUnicode_FromStringAndSize(str, size);
    if (str_obj == _Py_NULL) {
        return -1;
    }

    int res = _PyUnicodeWriter_WriteStr((_PyUnicodeWriter*)writer, str_obj);
    Py_DECREF(str_obj);
    return res;
}

static inline int
PyUnicodeWriter_WriteASCII(PyUnicodeWriter *writer,
                           const char *str, Py_ssize_t size)
{
    if (size < 0) {
        size = (Py_ssize_t)strlen(str);
    }

    return _PyUnicodeWriter_WriteASCIIString((_PyUnicodeWriter*)writer,
                                             str, size);
}

static inline int
PyUnicodeWriter_WriteWideChar(PyUnicodeWriter *writer,
                              const wchar_t *str, Py_ssize_t size)
{
    if (size < 0) {
        size = (Py_ssize_t)wcslen(str);
    }

    PyObject *str_obj = PyUnicode_FromWideChar(str, size);
    if (str_obj == _Py_NULL) {
        return -1;
    }

    int res = _PyUnicodeWriter_WriteStr((_PyUnicodeWriter*)writer, str_obj);
    Py_DECREF(str_obj);
    return res;
}

static inline int
PyUnicodeWriter_WriteSubstring(PyUnicodeWriter *writer, PyObject *str,
                               Py_ssize_t start, Py_ssize_t end)
{
    if (!PyUnicode_Check(str)) {
        PYTHONCAPI_COMPAT_EXPECT_TYPE("expect str, not ", str);
        return -1;
    }
    if (start < 0 || start > end) {
        PyErr_Format(PyExc_ValueError, "invalid start argument");
        return -1;
    }
    if (end > PyUnicode_GET_LENGTH(str)) {
        PyErr_Format(PyExc_ValueError, "invalid end argument");
        return -1;
    }

    return _PyUnicodeWriter_WriteSubstring((_PyUnicodeWriter*)writer, str,
                                           start, end);
}

static inline int
PyUnicodeWriter_WriteUCS4(PyUnicodeWriter *writer,
                          const Py_UCS4 *ucs4, Py_ssize_t size)
{
    PyObject *str = PyUnicode_FromKindAndData(PyUnicode_4BYTE_KIND,
                                              ucs4, size);
    if (str == NULL) {
        return -1;
    }

    int res = _PyUnicodeWriter_WriteStr((_PyUnicodeWriter*)writer, str);
    Py_DECREF(str);
    return res;
}

static inline int
PyUnicodeWriter_Format(PyUnicodeWriter *writer, const char *format, ...)
{
    va_list vargs;
    va_start(vargs, format);
    PyObject *str = PyUnicode_FromFormatV(format, vargs);
    va_end(vargs);
    if (str == _Py_NULL) {
        return -1;
    }

    int res = _PyUnicodeWriter_WriteStr((_PyUnicodeWriter*)writer, str);
    Py_DECREF(str);
    return res;
}
#endif  // PY_VERSION_HEX < _Py_PACK_VERSION(3, 14)

// gh-116560 added PyLong_GetSign() to Python 3.14
#if PY_VERSION_HEX < _Py_PACK_VERSION(3, 14) || defined(Py_LIMITED_API)
static inline int PyLong_GetSign(PyObject *obj, int *sign)
{
#ifndef Py_LIMITED_API
    if (!PyLong_Check(obj)) {
        PYTHONCAPI_COMPAT_EXPECT_TYPE("expect int, got ", obj);
        return -1;
    }

    *sign = _PyLong_Sign(obj);
    return 0;
#else
    PyObject *zero = Py_GetConstant(Py_CONSTANT_ZERO);
    int cmp;

    if (!PyLong_Check(obj)) {
        PYTHONCAPI_COMPAT_EXPECT_TYPE("expect int, got ", obj);
        return -1;
    }

    cmp = PyObject_RichCompareBool(obj, zero, Py_GT);
    if (cmp > 0) {
        *sign = 1;
        return 0;
    }
    if (cmp < 0) {
        return -1;
    }

    cmp = PyObject_RichCompareBool(obj, zero, Py_LT);
    if (cmp > 0) {
        *sign = -1;
        return 0;
    }
    if (cmp < 0) {
        return -1;
    }
    *sign = 0;
    return 0;
#endif
}
#endif

// gh-126061 added PyLong_IsPositive/Negative/Zero() to Python in 3.14.0
#if PY_VERSION_HEX < _Py_PACK_VERSION(3, 14) || defined(Py_LIMITED_API)
static inline int PyLong_IsPositive(PyObject *obj)
{
#ifndef Py_LIMITED_API
    if (!PyLong_Check(obj)) {
        PYTHONCAPI_COMPAT_EXPECT_TYPE("expected int, got ", obj);
        return -1;
    }
    return _PyLong_Sign(obj) == 1;
#else
    PyObject *zero = Py_GetConstant(Py_CONSTANT_ZERO);

    if (!PyLong_Check(obj)) {
        PyErr_Format(PyExc_TypeError, "expect int, got %R", obj);
        return -1;
    }

    return PyObject_RichCompareBool(obj, zero, Py_GT);
#endif
}

static inline int PyLong_IsNegative(PyObject *obj)
{
#ifndef Py_LIMITED_API
    if (!PyLong_Check(obj)) {
        PYTHONCAPI_COMPAT_EXPECT_TYPE("expected int, got ", obj);
        return -1;
    }
    return _PyLong_Sign(obj) == -1;
#else
    PyObject *zero = Py_GetConstant(Py_CONSTANT_ZERO);
    int cmp;

    if (!PyLong_Check(obj)) {
        PYTHONCAPI_COMPAT_EXPECT_TYPE("expect int, got ", obj);
        return -1;
    }

    cmp = PyObject_RichCompareBool(obj, zero, Py_LT);
    if (cmp > 0) {
        return 1;
    }
    if (cmp < 0) {
        return -1;
    }
    return 0;
#endif
}

static inline int PyLong_IsZero(PyObject *obj)
{
#ifndef Py_LIMITED_API
    if (!PyLong_Check(obj)) {
        PYTHONCAPI_COMPAT_EXPECT_TYPE("expected int, got ", obj);
        return -1;
    }
    return _PyLong_Sign(obj) == 0;
#else
    PyObject *zero = Py_GetConstant(Py_CONSTANT_ZERO);

    if (!PyLong_Check(obj)) {
        PYTHONCAPI_COMPAT_EXPECT_TYPE("expect int, got ", obj);
        return -1;
    }

    return PyObject_RichCompareBool(obj, zero, Py_EQ);
#endif
}
#endif


// gh-124502 added PyUnicode_Equal() to Python 3.14
#if (PY_VERSION_HEX < _Py_PACK_VERSION(3, 14) \
     || (defined(Py_LIMITED_API) && Py_LIMITED_API+0 < _Py_PACK_VERSION(3, 14)))

#if (PY_VERSION_HEX >= _Py_PACK_VERSION(3, 13) \
     && !defined(PYPY_VERSION) && !defined(Py_LIMITED_API))
PyAPI_FUNC(int) _PyUnicode_Equal(PyObject *str1, PyObject *str2);
#endif

static inline int PyUnicode_Equal(PyObject *str1, PyObject *str2)
{
    if (!PyUnicode_Check(str1)) {
        PYTHONCAPI_COMPAT_EXPECT_TYPE("first argument must be str, not ", str1);
        return -1;
    }
    if (!PyUnicode_Check(str2)) {
        PYTHONCAPI_COMPAT_EXPECT_TYPE("second argument must be str, not ", str2);
        return -1;
    }

#if (PY_VERSION_HEX >= _Py_PACK_VERSION(3, 13) \
     && !defined(PYPY_VERSION) && !defined(Py_LIMITED_API))
    return _PyUnicode_Equal(str1, str2);
#elif !defined(PYPY_VERSION) && !defined(Py_LIMITED_API)
    return _PyUnicode_EQ(str1, str2);
#elif (PY_VERSION_HEX >= _Py_PACK_VERSION(3, 9) \
       && defined(PYPY_VERSION) && !defined(Py_LIMITED_API))
    return _PyUnicode_EQ(str1, str2);
#else
    {
        int cmp = PyUnicode_Compare(str1, str2);
        if (cmp == -1 && PyErr_Occurred()) {
            return -1;
        }
        return (cmp == 0);
    }
#endif
}
#endif


// gh-121645 added PyBytes_Join() to Python 3.14
#if PY_VERSION_HEX < _Py_PACK_VERSION(3, 14) || defined(Py_LIMITED_API)
static inline PyObject* PyBytes_Join(PyObject *sep, PyObject *iterable)
{
#ifndef Py_LIMITED_API
    return _PyBytes_Join(sep, iterable);
#else
    if (sep == NULL) {
        PyErr_BadInternalCall();
        return NULL;
    }
    if (!PyBytes_Check(sep)) {
        PyErr_Format(PyExc_TypeError,
                     "sep: expected bytes, got %T", sep);
        return NULL;
    }

    return PyObject_CallMethod(sep, "join", "O", iterable);
#endif
}
#endif


#if (PY_VERSION_HEX < _Py_PACK_VERSION(3, 14) \
     || (defined(Py_LIMITED_API) && Py_LIMITED_API+0 < _Py_PACK_VERSION(3, 16)))

#if !defined(PYPY_VERSION) && !defined(Py_LIMITED_API)
PyAPI_FUNC(Py_hash_t) _Py_HashBytes(const void *src, Py_ssize_t len);
#endif

static inline Py_hash_t Py_HashBuffer(const void *ptr, Py_ssize_t len)
{
#if !defined(PYPY_VERSION) && !defined(Py_LIMITED_API)
    return _Py_HashBytes(ptr, len);
#else
    Py_hash_t hash;
    PyObject *bytes = PyBytes_FromStringAndSize((const char*)ptr, len);
    if (bytes == NULL) {
        return -1;
    }
    hash = PyObject_Hash(bytes);
    Py_DECREF(bytes);
    return hash;
#endif
}
#endif


#if (PY_VERSION_HEX < _Py_PACK_VERSION(3, 14) \
     || (defined(Py_LIMITED_API) && Py_LIMITED_API+0 < _Py_PACK_VERSION(3, 14)))
static inline int PyIter_NextItem(PyObject *iter, PyObject **item)
{
    // Limited API: PyType_GetSlot() only accepts all types since Python 3.10
#if !defined(Py_LIMITED_API) || Py_LIMITED_API+0 >= _Py_PACK_VERSION(3, 10)
    iternextfunc tp_iternext;

    assert(iter != NULL);
    assert(item != NULL);

#ifndef Py_LIMITED_API
    tp_iternext = Py_TYPE(iter)->tp_iternext;
#else
    tp_iternext = _Py_CAST(iternextfunc, PyType_GetSlot(Py_TYPE(iter), Py_tp_iternext));
#endif
    if (tp_iternext == NULL) {
        *item = NULL;
        PYTHONCAPI_COMPAT_EXPECT_TYPE("expected an iterator, got ", iter);
        return -1;
    }

    if ((*item = tp_iternext(iter))) {
        return 1;
    }
    if (!PyErr_Occurred()) {
        return 0;
    }
    if (PyErr_ExceptionMatches(PyExc_StopIteration)) {
        PyErr_Clear();
        return 0;
    }
    return -1;
#else
    // Implementation for limited C API 3.9 and older

    assert(iter != NULL);
    assert(item != NULL);

    // Cannot check if iter is an iterator: PyIter_Check() is only implemented
    // as a function since Python 3.8.

    *item = PyIter_Next(iter);
    if (*item != NULL) {
        return 1;
    }
    else if (!PyErr_Occurred()) {
        return 0;
    }
    else {
        return -1;
    }
#endif
}
#endif


#if (PY_VERSION_HEX < _Py_PACK_VERSION(3, 14) \
     || (defined(Py_LIMITED_API) && Py_LIMITED_API+0 < _Py_PACK_VERSION(3, 14)))
static inline PyObject* PyLong_FromInt32(int32_t value)
{
    Py_BUILD_ASSERT(sizeof(long) >= 4);
    return PyLong_FromLong(value);
}

static inline PyObject* PyLong_FromInt64(int64_t value)
{
    Py_BUILD_ASSERT(sizeof(long long) >= 8);
    return PyLong_FromLongLong(value);
}

static inline PyObject* PyLong_FromUInt32(uint32_t value)
{
    Py_BUILD_ASSERT(sizeof(unsigned long) >= 4);
    return PyLong_FromUnsignedLong(value);
}

static inline PyObject* PyLong_FromUInt64(uint64_t value)
{
    Py_BUILD_ASSERT(sizeof(unsigned long long) >= 8);
    return PyLong_FromUnsignedLongLong(value);
}

static inline int PyLong_AsInt32(PyObject *obj, int32_t *pvalue)
{
    Py_BUILD_ASSERT(sizeof(int) == 4);
    int value = PyLong_AsInt(obj);
    if (value == -1 && PyErr_Occurred()) {
        return -1;
    }
    *pvalue = (int32_t)value;
    return 0;
}

static inline int PyLong_AsInt64(PyObject *obj, int64_t *pvalue)
{
    Py_BUILD_ASSERT(sizeof(long long) == 8);
    long long value = PyLong_AsLongLong(obj);
    if (value == -1 && PyErr_Occurred()) {
        return -1;
    }
    *pvalue = (int64_t)value;
    return 0;
}

static inline int PyLong_AsUInt32(PyObject *obj, uint32_t *pvalue)
{
    Py_BUILD_ASSERT(sizeof(long) >= 4);
    unsigned long value = PyLong_AsUnsignedLong(obj);
    if (value == (unsigned long)-1 && PyErr_Occurred()) {
        return -1;
    }
#if SIZEOF_LONG > 4
    if ((unsigned long)UINT32_MAX < value) {
        PyErr_SetString(PyExc_OverflowError,
                        "Python int too large to convert to C uint32_t");
        return -1;
    }
#endif
    *pvalue = (uint32_t)value;
    return 0;
}

static inline int PyLong_AsUInt64(PyObject *obj, uint64_t *pvalue)
{
    Py_BUILD_ASSERT(sizeof(long long) == 8);
    unsigned long long value = PyLong_AsUnsignedLongLong(obj);
    if (value == (unsigned long long)-1 && PyErr_Occurred()) {
        return -1;
    }
    *pvalue = (uint64_t)value;
    return 0;
}
#endif


// gh-102471 added import and export API for integers to 3.14.0.
#if (PY_VERSION_HEX < _Py_PACK_VERSION(3, 14) \
     && !defined(PYPY_VERSION) && !defined(Py_LIMITED_API))
// Helpers to access PyLongObject internals.
static inline void
_PyLong_SetSignAndDigitCount(PyLongObject *op, int sign, Py_ssize_t size)
{
#if PY_VERSION_HEX >= _Py_PACK_VERSION(3, 12)
    op->long_value.lv_tag = (uintptr_t)(1 - sign) | ((uintptr_t)(size) << 3);
#elif PY_VERSION_HEX >= _Py_PACK_VERSION(3, 9)
    Py_SET_SIZE(op, sign * size);
#else
    Py_SIZE(op) = sign * size;
#endif
}

static inline Py_ssize_t
_PyLong_DigitCount(const PyLongObject *op)
{
#if PY_VERSION_HEX >= _Py_PACK_VERSION(3, 12)
    return (Py_ssize_t)(op->long_value.lv_tag >> 3);
#else
    return _PyLong_Sign((PyObject*)op) < 0 ? -Py_SIZE(op) : Py_SIZE(op);
#endif
}

static inline digit*
_PyLong_GetDigits(const PyLongObject *op)
{
#if PY_VERSION_HEX >= _Py_PACK_VERSION(3, 12)
    return (digit*)(op->long_value.ob_digit);
#else
    return (digit*)(op->ob_digit);
#endif
}

typedef struct PyLongLayout {
    uint8_t bits_per_digit;
    uint8_t digit_size;
    int8_t digits_order;
    int8_t digit_endianness;
} PyLongLayout;

typedef struct PyLongExport {
    int64_t value;
    uint8_t negative;
    Py_ssize_t ndigits;
    const void *digits;
    Py_uintptr_t _reserved;
} PyLongExport;

typedef struct PyLongWriter PyLongWriter;

static inline const PyLongLayout*
PyLong_GetNativeLayout(void)
{
    static const PyLongLayout PyLong_LAYOUT = {
        PyLong_SHIFT,
        sizeof(digit),
        -1,  // least significant first
        PY_LITTLE_ENDIAN ? -1 : 1,
    };

    return &PyLong_LAYOUT;
}

static inline int
PyLong_Export(PyObject *obj, PyLongExport *export_long)
{
    if (!PyLong_Check(obj)) {
        memset(export_long, 0, sizeof(*export_long));
        PYTHONCAPI_COMPAT_EXPECT_TYPE("expected int, got ", obj);
        return -1;
    }

    // Fast-path: try to convert to a int64_t
    PyLongObject *self = (PyLongObject*)obj;
    int overflow;
#if SIZEOF_LONG == 8
    long value = PyLong_AsLongAndOverflow(obj, &overflow);
#else
    // Windows has 32-bit long, so use 64-bit long long instead
    long long value = PyLong_AsLongLongAndOverflow(obj, &overflow);
#endif
    Py_BUILD_ASSERT(sizeof(value) == sizeof(int64_t));
    // the function cannot fail since obj is a PyLongObject
    assert(!(value == -1 && PyErr_Occurred()));

    if (!overflow) {
        export_long->value = value;
        export_long->negative = 0;
        export_long->ndigits = 0;
        export_long->digits = 0;
        export_long->_reserved = 0;
    }
    else {
        export_long->value = 0;
        export_long->negative = _PyLong_Sign(obj) < 0;
        export_long->ndigits = _PyLong_DigitCount(self);
        if (export_long->ndigits == 0) {
            export_long->ndigits = 1;
        }
        export_long->digits = _PyLong_GetDigits(self);
        export_long->_reserved = (Py_uintptr_t)Py_NewRef(obj);
    }
    return 0;
}

static inline void
PyLong_FreeExport(PyLongExport *export_long)
{
    PyObject *obj = (PyObject*)export_long->_reserved;

    if (obj) {
        export_long->_reserved = 0;
        Py_DECREF(obj);
    }
}

static inline PyLongWriter*
PyLongWriter_Create(int negative, Py_ssize_t ndigits, void **digits)
{
    if (ndigits <= 0) {
        PyErr_SetString(PyExc_ValueError, "ndigits must be positive");
        return NULL;
    }
    assert(digits != NULL);

    PyLongObject *obj = _PyLong_New(ndigits);
    if (obj == NULL) {
        return NULL;
    }
    _PyLong_SetSignAndDigitCount(obj, negative?-1:1, ndigits);

    *digits = _PyLong_GetDigits(obj);
    return (PyLongWriter*)obj;
}

static inline void
PyLongWriter_Discard(PyLongWriter *writer)
{
    PyLongObject *obj = (PyLongObject *)writer;

    assert(Py_REFCNT(obj) == 1);
    Py_DECREF(obj);
}

static inline PyObject*
PyLongWriter_Finish(PyLongWriter *writer)
{
    PyObject *obj = (PyObject *)writer;
    PyLongObject *self = (PyLongObject*)obj;
    Py_ssize_t j = _PyLong_DigitCount(self);
    Py_ssize_t i = j;
    int sign = _PyLong_Sign(obj);

    assert(Py_REFCNT(obj) == 1);

    // Normalize and get singleton if possible
    while (i > 0 && _PyLong_GetDigits(self)[i-1] == 0) {
        --i;
    }
    if (i != j) {
        if (i == 0) {
            sign = 0;
        }
        _PyLong_SetSignAndDigitCount(self, sign, i);
    }
    if (i <= 1) {
        long val = sign * (long)(_PyLong_GetDigits(self)[0]);
        Py_DECREF(obj);
        return PyLong_FromLong(val);
    }

    return obj;
}
#endif


#if PY_VERSION_HEX < _Py_PACK_VERSION(3, 12)
#   define Py_T_SHORT      0
#   define Py_T_INT        1
#   define Py_T_LONG       2
#   define Py_T_FLOAT      3
#   define Py_T_DOUBLE     4
#   define Py_T_STRING     5
#   define _Py_T_OBJECT    6
#   define Py_T_CHAR       7
#   define Py_T_BYTE       8
#   define Py_T_UBYTE      9
#   define Py_T_USHORT     10
#   define Py_T_UINT       11
#   define Py_T_ULONG      12
#   define Py_T_STRING_INPLACE  13
#   define Py_T_BOOL       14
#   define Py_T_OBJECT_EX  16
#   define Py_T_LONGLONG   17
#   define Py_T_ULONGLONG  18
#   define Py_T_PYSSIZET   19

#   ifndef PYPY_VERSION
#       define _Py_T_NONE      20
#   endif

#   define Py_READONLY            1
#   define Py_AUDIT_READ          2
#   define _Py_WRITE_RESTRICTED   4
#endif


// gh-127350 added Py_fopen() and Py_fclose() to Python 3.14a4
#if PY_VERSION_HEX < _Py_PACK_VERSION(3, 14) || defined(Py_LIMITED_API)

#if !defined(PYPY_VERSION) && !defined(Py_LIMITED_API)
PyAPI_FUNC(FILE*) _Py_fopen_obj(PyObject *path, const char *mode);
#endif

static inline FILE* Py_fopen(PyObject *path, const char *mode)
{
#if !defined(PYPY_VERSION) && !defined(Py_LIMITED_API)
    return _Py_fopen_obj(path, mode);
#else
    FILE *f;
    PyObject *bytes;
    const char *path_bytes;
    if (!PyUnicode_FSConverter(path, &bytes)) {
        return NULL;
    }
#ifndef Py_LIMITED_API
    path_bytes = PyBytes_AS_STRING(bytes);
#else
    path_bytes = PyBytes_AsString(bytes);
#endif

    f = fopen(path_bytes, mode);
    Py_DECREF(bytes);

    if (f == NULL) {
        PyErr_SetFromErrnoWithFilenameObject(PyExc_OSError, path);
        return NULL;
    }
    return f;
#endif
}

static inline int Py_fclose(FILE *file)
{
    return fclose(file);
}
#endif


#if (_Py_PACK_VERSION(3, 9) <= PY_VERSION_HEX \
     && PY_VERSION_HEX < _Py_PACK_VERSION(3, 14) \
     && !defined(PYPY_VERSION) && !defined(Py_LIMITED_API))

// Use the internal C API added to Python 3.9
PyAPI_FUNC(const PyConfig*) _Py_GetConfig(void);

static inline PyObject*
PyConfig_Get(const char *name)
{
    typedef enum {
        _PyConfig_MEMBER_INT,
        _PyConfig_MEMBER_UINT,
        _PyConfig_MEMBER_ULONG,
        _PyConfig_MEMBER_BOOL,
        _PyConfig_MEMBER_WSTR,
        _PyConfig_MEMBER_WSTR_OPT,
        _PyConfig_MEMBER_WSTR_LIST,
    } PyConfigMemberType;

    typedef struct {
        const char *name;
        size_t offset;
        PyConfigMemberType type;
        const char *sys_attr;
    } PyConfigSpec;

#define PYTHONCAPI_COMPAT_SPEC(MEMBER, TYPE, sys_attr) \
    {#MEMBER, offsetof(PyConfig, MEMBER), \
     _PyConfig_MEMBER_##TYPE, sys_attr}

    static const PyConfigSpec config_spec[] = {
        PYTHONCAPI_COMPAT_SPEC(argv, WSTR_LIST, "argv"),
        PYTHONCAPI_COMPAT_SPEC(base_exec_prefix, WSTR_OPT, "base_exec_prefix"),
        PYTHONCAPI_COMPAT_SPEC(base_executable, WSTR_OPT, "_base_executable"),
        PYTHONCAPI_COMPAT_SPEC(base_prefix, WSTR_OPT, "base_prefix"),
        PYTHONCAPI_COMPAT_SPEC(bytes_warning, UINT, _Py_NULL),
        PYTHONCAPI_COMPAT_SPEC(exec_prefix, WSTR_OPT, "exec_prefix"),
        PYTHONCAPI_COMPAT_SPEC(executable, WSTR_OPT, "executable"),
        PYTHONCAPI_COMPAT_SPEC(inspect, BOOL, _Py_NULL),
#if _Py_PACK_VERSION(3, 12) <= PY_VERSION_HEX
        PYTHONCAPI_COMPAT_SPEC(int_max_str_digits, UINT, _Py_NULL),
#endif
        PYTHONCAPI_COMPAT_SPEC(interactive, BOOL, _Py_NULL),
        PYTHONCAPI_COMPAT_SPEC(module_search_paths, WSTR_LIST, "path"),
        PYTHONCAPI_COMPAT_SPEC(optimization_level, UINT, _Py_NULL),
        PYTHONCAPI_COMPAT_SPEC(parser_debug, BOOL, _Py_NULL),
#if _Py_PACK_VERSION(3, 9) <= PY_VERSION_HEX
        PYTHONCAPI_COMPAT_SPEC(platlibdir, WSTR, "platlibdir"),
#endif
        PYTHONCAPI_COMPAT_SPEC(prefix, WSTR_OPT, "prefix"),
        PYTHONCAPI_COMPAT_SPEC(pycache_prefix, WSTR_OPT, "pycache_prefix"),
        PYTHONCAPI_COMPAT_SPEC(quiet, BOOL, _Py_NULL),
#if _Py_PACK_VERSION(3, 11) <= PY_VERSION_HEX
        PYTHONCAPI_COMPAT_SPEC(stdlib_dir, WSTR_OPT, "_stdlib_dir"),
#endif
        PYTHONCAPI_COMPAT_SPEC(use_environment, BOOL, _Py_NULL),
        PYTHONCAPI_COMPAT_SPEC(verbose, UINT, _Py_NULL),
        PYTHONCAPI_COMPAT_SPEC(warnoptions, WSTR_LIST, "warnoptions"),
        PYTHONCAPI_COMPAT_SPEC(write_bytecode, BOOL, _Py_NULL),
        PYTHONCAPI_COMPAT_SPEC(xoptions, WSTR_LIST, "_xoptions"),
        PYTHONCAPI_COMPAT_SPEC(buffered_stdio, BOOL, _Py_NULL),
        PYTHONCAPI_COMPAT_SPEC(check_hash_pycs_mode, WSTR, _Py_NULL),
#if _Py_PACK_VERSION(3, 11) <= PY_VERSION_HEX
        PYTHONCAPI_COMPAT_SPEC(code_debug_ranges, BOOL, _Py_NULL),
#endif
        PYTHONCAPI_COMPAT_SPEC(configure_c_stdio, BOOL, _Py_NULL),
#if _Py_PACK_VERSION(3, 13) <= PY_VERSION_HEX
        PYTHONCAPI_COMPAT_SPEC(cpu_count, INT, _Py_NULL),
#endif
        PYTHONCAPI_COMPAT_SPEC(dev_mode, BOOL, _Py_NULL),
        PYTHONCAPI_COMPAT_SPEC(dump_refs, BOOL, _Py_NULL),
#if _Py_PACK_VERSION(3, 11) <= PY_VERSION_HEX
        PYTHONCAPI_COMPAT_SPEC(dump_refs_file, WSTR_OPT, _Py_NULL),
#endif
#ifdef Py_GIL_DISABLED
        PYTHONCAPI_COMPAT_SPEC(enable_gil, INT, _Py_NULL),
#endif
        PYTHONCAPI_COMPAT_SPEC(faulthandler, BOOL, _Py_NULL),
        PYTHONCAPI_COMPAT_SPEC(filesystem_encoding, WSTR, _Py_NULL),
        PYTHONCAPI_COMPAT_SPEC(filesystem_errors, WSTR, _Py_NULL),
        PYTHONCAPI_COMPAT_SPEC(hash_seed, ULONG, _Py_NULL),
        PYTHONCAPI_COMPAT_SPEC(home, WSTR_OPT, _Py_NULL),
        PYTHONCAPI_COMPAT_SPEC(import_time, BOOL, _Py_NULL),
        PYTHONCAPI_COMPAT_SPEC(install_signal_handlers, BOOL, _Py_NULL),
        PYTHONCAPI_COMPAT_SPEC(isolated, BOOL, _Py_NULL),
#ifdef MS_WINDOWS
        PYTHONCAPI_COMPAT_SPEC(legacy_windows_stdio, BOOL, _Py_NULL),
#endif
        PYTHONCAPI_COMPAT_SPEC(malloc_stats, BOOL, _Py_NULL),
#if _Py_PACK_VERSION(3, 10) <= PY_VERSION_HEX
        PYTHONCAPI_COMPAT_SPEC(orig_argv, WSTR_LIST, "orig_argv"),
#endif
        PYTHONCAPI_COMPAT_SPEC(parse_argv, BOOL, _Py_NULL),
        PYTHONCAPI_COMPAT_SPEC(pathconfig_warnings, BOOL, _Py_NULL),
#if _Py_PACK_VERSION(3, 12) <= PY_VERSION_HEX
        PYTHONCAPI_COMPAT_SPEC(perf_profiling, UINT, _Py_NULL),
#endif
        PYTHONCAPI_COMPAT_SPEC(program_name, WSTR, _Py_NULL),
        PYTHONCAPI_COMPAT_SPEC(run_command, WSTR_OPT, _Py_NULL),
        PYTHONCAPI_COMPAT_SPEC(run_filename, WSTR_OPT, _Py_NULL),
        PYTHONCAPI_COMPAT_SPEC(run_module, WSTR_OPT, _Py_NULL),
#if _Py_PACK_VERSION(3, 11) <= PY_VERSION_HEX
        PYTHONCAPI_COMPAT_SPEC(safe_path, BOOL, _Py_NULL),
#endif
        PYTHONCAPI_COMPAT_SPEC(show_ref_count, BOOL, _Py_NULL),
        PYTHONCAPI_COMPAT_SPEC(site_import, BOOL, _Py_NULL),
        PYTHONCAPI_COMPAT_SPEC(skip_source_first_line, BOOL, _Py_NULL),
        PYTHONCAPI_COMPAT_SPEC(stdio_encoding, WSTR, _Py_NULL),
        PYTHONCAPI_COMPAT_SPEC(stdio_errors, WSTR, _Py_NULL),
        PYTHONCAPI_COMPAT_SPEC(tracemalloc, UINT, _Py_NULL),
#if _Py_PACK_VERSION(3, 11) <= PY_VERSION_HEX
        PYTHONCAPI_COMPAT_SPEC(use_frozen_modules, BOOL, _Py_NULL),
#endif
        PYTHONCAPI_COMPAT_SPEC(use_hash_seed, BOOL, _Py_NULL),
        PYTHONCAPI_COMPAT_SPEC(user_site_directory, BOOL, _Py_NULL),
#if _Py_PACK_VERSION(3, 10) <= PY_VERSION_HEX
        PYTHONCAPI_COMPAT_SPEC(warn_default_encoding, BOOL, _Py_NULL),
#endif
    };

#undef PYTHONCAPI_COMPAT_SPEC

    const PyConfigSpec *spec;
    int found = 0;
    for (size_t i=0; i < sizeof(config_spec) / sizeof(config_spec[0]); i++) {
        spec = &config_spec[i];
        if (strcmp(spec->name, name) == 0) {
            found = 1;
            break;
        }
    }
    if (found) {
        if (spec->sys_attr != NULL) {
            PyObject *value = PySys_GetObject(spec->sys_attr);
            if (value == NULL) {
                PyErr_Format(PyExc_RuntimeError, "lost sys.%s", spec->sys_attr);
                return NULL;
            }
            return Py_NewRef(value);
        }

        const PyConfig *config = _Py_GetConfig();
        void *member = (char *)config + spec->offset;
        switch (spec->type) {
        case _PyConfig_MEMBER_INT:
        case _PyConfig_MEMBER_UINT:
        {
            int value = *(int *)member;
            return PyLong_FromLong(value);
        }
        case _PyConfig_MEMBER_BOOL:
        {
            int value = *(int *)member;
            return PyBool_FromLong(value != 0);
        }
        case _PyConfig_MEMBER_ULONG:
        {
            unsigned long value = *(unsigned long *)member;
            return PyLong_FromUnsignedLong(value);
        }
        case _PyConfig_MEMBER_WSTR:
        case _PyConfig_MEMBER_WSTR_OPT:
        {
            wchar_t *wstr = *(wchar_t **)member;
            if (wstr != NULL) {
                return PyUnicode_FromWideChar(wstr, -1);
            }
            else {
                return Py_NewRef(Py_None);
            }
        }
        case _PyConfig_MEMBER_WSTR_LIST:
        {
            const PyWideStringList *list = (const PyWideStringList *)member;
            PyObject *tuple = PyTuple_New(list->length);
            if (tuple == NULL) {
                return NULL;
            }

            for (Py_ssize_t i = 0; i < list->length; i++) {
                PyObject *item = PyUnicode_FromWideChar(list->items[i], -1);
                if (item == NULL) {
                    Py_DECREF(tuple);
                    return NULL;
                }
                PyTuple_SET_ITEM(tuple, i, item);
            }
            return tuple;
        }
        default:
            Py_UNREACHABLE();
        }
    }

    PyErr_Format(PyExc_ValueError, "unknown config option name: %s", name);
    return NULL;
}

static inline int
PyConfig_GetInt(const char *name, int *value)
{
    PyObject *obj = PyConfig_Get(name);
    if (obj == NULL) {
        return -1;
    }

    if (!PyLong_Check(obj)) {
        Py_DECREF(obj);
        PyErr_Format(PyExc_TypeError, "config option %s is not an int", name);
        return -1;
    }

    int as_int = PyLong_AsInt(obj);
    Py_DECREF(obj);
    if (as_int == -1 && PyErr_Occurred()) {
        PyErr_Format(PyExc_OverflowError,
                     "config option %s value does not fit into a C int", name);
        return -1;
    }

    *value = as_int;
    return 0;
}
#endif  // PY_VERSION_HEX > _Py_PACK_VERSION(3, 9) && !defined(PYPY_VERSION)

// gh-133144 added PyUnstable_Object_IsUniquelyReferenced() to Python 3.14.
// Adapted from  _PyObject_IsUniquelyReferenced() implementation.
// Not available on PyPy: Py_REFCNT() semantics is different on PyPy.
#if (PY_VERSION_HEX < _Py_PACK_VERSION(3, 14) \
     && !defined(PYPY_VERSION) && !defined(Py_LIMITED_API))
static inline int PyUnstable_Object_IsUniquelyReferenced(PyObject *obj)
{
#if !defined(Py_GIL_DISABLED)
    return Py_REFCNT(obj) == 1;
#else
    // NOTE: the entire ob_ref_shared field must be zero, including flags, to
    // ensure that other threads cannot concurrently create new references to
    // this object.
    return (_Py_IsOwnedByCurrentThread(obj) &&
            _Py_atomic_load_uint32_relaxed(&obj->ob_ref_local) == 1 &&
            _Py_atomic_load_ssize_relaxed(&obj->ob_ref_shared) == 0);
#endif
}
#endif

// gh-128926 added PyUnstable_TryIncRef() and PyUnstable_EnableTryIncRef() to
// Python 3.14. Adapted from _Py_TryIncref() and _PyObject_SetMaybeWeakref().
// Not available on PyPy: Py_REFCNT() semantics is different on PyPy.
#if PY_VERSION_HEX < _Py_PACK_VERSION(3, 14) && !defined(PYPY_VERSION)
static inline int PyUnstable_TryIncRef(PyObject *op)
{
#ifndef Py_GIL_DISABLED
    if (Py_REFCNT(op) > 0) {
        Py_INCREF(op);
        return 1;
    }
    return 0;
#else
    // _Py_TryIncrefFast()
    uint32_t local = _Py_atomic_load_uint32_relaxed(&op->ob_ref_local);
    local += 1;
    if (local == 0) {
        // immortal
        return 1;
    }
    if (_Py_IsOwnedByCurrentThread(op)) {
        _Py_INCREF_STAT_INC();
        _Py_atomic_store_uint32_relaxed(&op->ob_ref_local, local);
#ifdef Py_REF_DEBUG
        _Py_INCREF_IncRefTotal();
#endif
        return 1;
    }

    // _Py_TryIncRefShared()
    Py_ssize_t shared = _Py_atomic_load_ssize_relaxed(&op->ob_ref_shared);
    for (;;) {
        // If the shared refcount is zero and the object is either merged
        // or may not have weak references, then we cannot incref it.
        if (shared == 0 || shared == _Py_REF_MERGED) {
            return 0;
        }

        if (_Py_atomic_compare_exchange_ssize(
                &op->ob_ref_shared,
                &shared,
                shared + (1 << _Py_REF_SHARED_SHIFT))) {
#ifdef Py_REF_DEBUG
            _Py_INCREF_IncRefTotal();
#endif
            _Py_INCREF_STAT_INC();
            return 1;
        }
    }
#endif
}

static inline void PyUnstable_EnableTryIncRef(PyObject *op)
{
#ifdef Py_GIL_DISABLED
    // _PyObject_SetMaybeWeakref()
    if (_Py_IsImmortal(op)) {
        return;
    }
    for (;;) {
        Py_ssize_t shared = _Py_atomic_load_ssize_relaxed(&op->ob_ref_shared);
        if ((shared & _Py_REF_SHARED_FLAG_MASK) != 0) {
            // Nothing to do if it's in WEAKREFS, QUEUED, or MERGED states.
            return;
        }
        if (_Py_atomic_compare_exchange_ssize(
                &op->ob_ref_shared, &shared, shared | _Py_REF_MAYBE_WEAKREF)) {
            return;
        }
    }
#else
    (void)op;  // unused argument
#endif
}
#endif  // PY_VERSION_HEX < _Py_PACK_VERSION(3, 14) && !defined(PYPY_VERSION)


#if (PY_VERSION_HEX < _Py_PACK_VERSION(3, 15) \
     || (defined(Py_LIMITED_API) && Py_LIMITED_API+0 < _Py_PACK_VERSION(3, 15)))
static inline PyObject*
PySys_GetAttrString(const char *name)
{
    PyObject *value = Py_XNewRef(PySys_GetObject(name));
    if (value != NULL) {
        return value;
    }
    if (!PyErr_Occurred()) {
        PyErr_Format(PyExc_RuntimeError, "lost sys.%s", name);
    }
    return NULL;
}

static inline PyObject*
PySys_GetAttr(PyObject *name)
{
#if defined(Py_LIMITED_API) && Py_LIMITED_API+0 < _Py_PACK_VERSION(3, 10)
    // Limited C API 3.9 and older
    PyObject *bytes, *result;
    bytes = PyUnicode_AsUTF8String(name);
    if (bytes == NULL) {
        return NULL;
    }
    result = PySys_GetAttrString(PyBytes_AsString(bytes));
    Py_DECREF(bytes);
    return result;
#else
    // Python 3.14 and newer, and limited C API 3.10 and newer
#ifndef Py_LIMITED_API
    const char *name_str = PyUnicode_AsUTF8(name);
#else
    const char *name_str = PyUnicode_AsUTF8AndSize(name, NULL);
#endif
    if (name_str == NULL) {
        return NULL;
    }

    return PySys_GetAttrString(name_str);
#endif
}

static inline int
PySys_GetOptionalAttrString(const char *name, PyObject **value)
{
    *value = Py_XNewRef(PySys_GetObject(name));
    if (*value != NULL) {
        return 1;
    }
    return 0;
}

static inline int
PySys_GetOptionalAttr(PyObject *name, PyObject **value)
{
#if defined(Py_LIMITED_API) && Py_LIMITED_API+0 < _Py_PACK_VERSION(3, 10)
    // Limited C API 3.9 and older
    PyObject *bytes;
    int res;
    bytes = PyUnicode_AsUTF8String(name);
    if (bytes == NULL) {
        *value = NULL;
        return -1;
    }
    res = PySys_GetOptionalAttrString(PyBytes_AsString(bytes), value);
    Py_DECREF(bytes);
    return res;
#else
#ifndef Py_LIMITED_API
    const char *name_str = PyUnicode_AsUTF8(name);
#else
    const char *name_str = PyUnicode_AsUTF8AndSize(name, NULL);
#endif
    if (name_str == NULL) {
        *value = NULL;
        return -1;
    }

    return PySys_GetOptionalAttrString(name_str, value);
#endif
}
#endif  // PY_VERSION_HEX < _Py_PACK_VERSION(3, 15)


// _PyBytes_Resize() is not available in the limited C API.
#if PY_VERSION_HEX < _Py_PACK_VERSION(3, 15) && !defined(Py_LIMITED_API)
typedef struct PyBytesWriter {
    char small_buffer[256];
    PyObject *obj;
    Py_ssize_t size;
} PyBytesWriter;

static inline Py_ssize_t
_PyBytesWriter_GetAllocated(PyBytesWriter *writer)
{
    if (writer->obj == NULL) {
        return sizeof(writer->small_buffer);
    }
    else {
        return PyBytes_GET_SIZE(writer->obj);
    }
}


static inline int
_PyBytesWriter_Resize_impl(PyBytesWriter *writer, Py_ssize_t size,
                           int resize)
{
    int overallocate = resize;
    assert(size >= 0);

    if (size <= _PyBytesWriter_GetAllocated(writer)) {
        return 0;
    }

    if (overallocate) {
#ifdef MS_WINDOWS
        /* On Windows, overallocate by 50% is the best factor */
        if (size <= (PY_SSIZE_T_MAX - size / 2)) {
            size += size / 2;
        }
#else
        /* On Linux, overallocate by 25% is the best factor */
        if (size <= (PY_SSIZE_T_MAX - size / 4)) {
            size += size / 4;
        }
#endif
    }

    if (writer->obj != NULL) {
        if (_PyBytes_Resize(&writer->obj, size)) {
            return -1;
        }
        assert(writer->obj != NULL);
    }
    else {
        writer->obj = PyBytes_FromStringAndSize(NULL, size);
        if (writer->obj == NULL) {
            return -1;
        }

        if (resize) {
            assert((size_t)size > sizeof(writer->small_buffer));
            memcpy(PyBytes_AS_STRING(writer->obj),
                   writer->small_buffer,
                   sizeof(writer->small_buffer));
        }
    }
    return 0;
}

static inline void*
PyBytesWriter_GetData(PyBytesWriter *writer)
{
    if (writer->obj == NULL) {
        return writer->small_buffer;
    }
    else {
        return PyBytes_AS_STRING(writer->obj);
    }
}

static inline Py_ssize_t
PyBytesWriter_GetSize(PyBytesWriter *writer)
{
    return writer->size;
}

static inline void
PyBytesWriter_Discard(PyBytesWriter *writer)
{
    if (writer == NULL) {
        return;
    }

    Py_XDECREF(writer->obj);
    PyMem_Free(writer);
}

static inline PyBytesWriter*
PyBytesWriter_Create(Py_ssize_t size)
{
    if (size < 0) {
        PyErr_SetString(PyExc_ValueError, "size must be >= 0");
        return NULL;
    }

    PyBytesWriter *writer = (PyBytesWriter*)PyMem_Malloc(sizeof(PyBytesWriter));
    if (writer == NULL) {
        PyErr_NoMemory();
        return NULL;
    }

    writer->obj = NULL;
    writer->size = 0;

    if (size >= 1) {
        if (_PyBytesWriter_Resize_impl(writer, size, 0) < 0) {
            PyBytesWriter_Discard(writer);
            return NULL;
        }
        writer->size = size;
    }
    return writer;
}

static inline PyObject*
PyBytesWriter_FinishWithSize(PyBytesWriter *writer, Py_ssize_t size)
{
    PyObject *result;
    if (size == 0) {
        result = PyBytes_FromStringAndSize("", 0);
    }
    else if (writer->obj != NULL) {
        Py_ssize_t old_size = PyBytes_GET_SIZE(writer->obj);
        if (size != old_size) {
            if (_PyBytes_Resize(&writer->obj, size)) {
                goto error;
            }
        }
        result = writer->obj;
        writer->obj = NULL;
    }
    else {
        result = PyBytes_FromStringAndSize(writer->small_buffer, size);
    }
    PyBytesWriter_Discard(writer);
    return result;

error:
    PyBytesWriter_Discard(writer);
    return NULL;
}

static inline PyObject*
PyBytesWriter_Finish(PyBytesWriter *writer)
{
    return PyBytesWriter_FinishWithSize(writer, writer->size);
}

static inline PyObject*
PyBytesWriter_FinishWithPointer(PyBytesWriter *writer, void *buf)
{
    Py_ssize_t size = (char*)buf - (char*)PyBytesWriter_GetData(writer);
    if (size < 0 || size > _PyBytesWriter_GetAllocated(writer)) {
        PyBytesWriter_Discard(writer);
        PyErr_SetString(PyExc_ValueError, "invalid end pointer");
        return NULL;
    }

    return PyBytesWriter_FinishWithSize(writer, size);
}

static inline int
PyBytesWriter_Resize(PyBytesWriter *writer, Py_ssize_t size)
{
    if (size < 0) {
        PyErr_SetString(PyExc_ValueError, "size must be >= 0");
        return -1;
    }
    if (_PyBytesWriter_Resize_impl(writer, size, 1) < 0) {
        return -1;
    }
    writer->size = size;
    return 0;
}

static inline int
PyBytesWriter_Grow(PyBytesWriter *writer, Py_ssize_t size)
{
    if (size < 0 && writer->size + size < 0) {
        PyErr_SetString(PyExc_ValueError, "invalid size");
        return -1;
    }
    if (size > PY_SSIZE_T_MAX - writer->size) {
        PyErr_NoMemory();
        return -1;
    }
    size = writer->size + size;

    if (_PyBytesWriter_Resize_impl(writer, size, 1) < 0) {
        return -1;
    }
    writer->size = size;
    return 0;
}

static inline void*
PyBytesWriter_GrowAndUpdatePointer(PyBytesWriter *writer,
                                   Py_ssize_t size, void *buf)
{
    Py_ssize_t pos = (char*)buf - (char*)PyBytesWriter_GetData(writer);
    if (PyBytesWriter_Grow(writer, size) < 0) {
        return NULL;
    }
    return (char*)PyBytesWriter_GetData(writer) + pos;
}

static inline int
PyBytesWriter_WriteBytes(PyBytesWriter *writer,
                         const void *bytes, Py_ssize_t size)
{
    if (size < 0) {
        size_t len = strlen((const char*)bytes);
        if (len > (size_t)PY_SSIZE_T_MAX) {
            PyErr_NoMemory();
            return -1;
        }
        size = (Py_ssize_t)len;
    }

    Py_ssize_t pos = writer->size;
    if (PyBytesWriter_Grow(writer, size) < 0) {
        return -1;
    }
    char *buf = (char*)PyBytesWriter_GetData(writer);
    memcpy(buf + pos, bytes, (size_t)size);
    return 0;
}

static inline int
PyBytesWriter_Format(PyBytesWriter *writer, const char *format, ...)
                     Py_GCC_ATTRIBUTE((format(printf, 2, 3)));

static inline int
PyBytesWriter_Format(PyBytesWriter *writer, const char *format, ...)
{
    va_list vargs;
    va_start(vargs, format);
    PyObject *str = PyBytes_FromFormatV(format, vargs);
    va_end(vargs);

    if (str == NULL) {
        return -1;
    }
    int res = PyBytesWriter_WriteBytes(writer,
                                       PyBytes_AS_STRING(str),
                                       PyBytes_GET_SIZE(str));
    Py_DECREF(str);
    return res;
}
#endif  // PY_VERSION_HEX < _Py_PACK_VERSION(3, 15)


#if PY_VERSION_HEX < _Py_PACK_VERSION(3, 15) || defined(Py_LIMITED_API)
static inline PyObject*
PyTuple_FromArray(PyObject *const *array, Py_ssize_t size)
{
    PyObject *tuple = PyTuple_New(size);
    if (tuple == NULL) {
        return NULL;
    }
    for (Py_ssize_t i=0; i < size; i++) {
        PyObject *item = array[i];
#ifndef Py_LIMITED_API
        PyTuple_SET_ITEM(tuple, i, Py_NewRef(item));
#else
        if (PyTuple_SetItem(tuple, i, Py_NewRef(item)) < 0) {
            Py_DECREF(tuple);
            return NULL;
        }
#endif
    }
    return tuple;
}
#endif


#if PY_VERSION_HEX < _Py_PACK_VERSION(3, 15) && !defined(Py_LIMITED_API)
static inline Py_hash_t
PyUnstable_Unicode_GET_CACHED_HASH(PyObject *op)
{
#ifdef PYPY_VERSION
    (void)op;  // unused argument
    return -1;
#else
    return ((PyASCIIObject*)op)->hash;
#endif
}
#endif

#if (_Py_PACK_VERSION(3, 13) <= PY_VERSION_HEX \
     && PY_VERSION_HEX < _Py_PACK_VERSION(3, 15) \
     && !defined(PYPY_VERSION) && !defined(Py_LIMITED_API))
// Immortal objects were implemented in Python 3.12, however there is no easy API
// to make objects immortal until 3.14 which has _Py_SetImmortal(). Since
// immortal objects are primarily needed for free-threading, this API is implemented
// for 3.14 using _Py_SetImmortal() and uses private macros on 3.13.
#if _Py_PACK_VERSION(3, 14) <= PY_VERSION_HEX
PyAPI_FUNC(void) _Py_SetImmortal(PyObject *op);
#endif

static inline int
PyUnstable_SetImmortal(PyObject *op)
{
    assert(op != NULL);
    if (!PyUnstable_Object_IsUniquelyReferenced(op) || PyUnicode_Check(op)) {
        return 0;
    }
#if _Py_PACK_VERSION(3, 14) <= PY_VERSION_HEX
    _Py_SetImmortal(op);
#else
    // Python 3.13 doesn't export _Py_SetImmortal() function
    if (PyObject_GC_IsTracked(op)) {
        PyObject_GC_UnTrack(op);
    }
#ifdef Py_GIL_DISABLED
    op->ob_tid = _Py_UNOWNED_TID;
    op->ob_ref_local = _Py_IMMORTAL_REFCNT_LOCAL;
    op->ob_ref_shared = 0;
#else
    op->ob_refcnt = _Py_IMMORTAL_REFCNT;
#endif
#endif
    return 1;
}
#endif


// Python 3.14 added PyImport_ImportModuleAttr()
// and PyImport_ImportModuleAttrString()
#if PY_VERSION_HEX < _Py_PACK_VERSION(3, 14) || defined(Py_LIMITED_API)
static inline PyObject*
PyImport_ImportModuleAttr(PyObject *mod_name, PyObject *attr_name)
{
    PyObject *mod = PyImport_Import(mod_name);
    if (mod == NULL) {
        return NULL;
    }

    PyObject *result = PyObject_GetAttr(mod, attr_name);
    Py_DECREF(mod);
    return result;
}

static inline PyObject *
PyImport_ImportModuleAttrString(const char *mod_name, const char *attr_name)
{
    PyObject *mod_name_obj = PyUnicode_FromString(mod_name);
    if (mod_name_obj == NULL) {
        return NULL;
    }
    PyObject *attr_name_obj = PyUnicode_FromString(attr_name);
    if (attr_name_obj == NULL) {
        Py_DECREF(mod_name_obj);
        return NULL;
    }

    PyObject *result = PyImport_ImportModuleAttr(mod_name_obj, attr_name_obj);
    Py_DECREF(attr_name_obj);
    Py_DECREF(mod_name_obj);
    return result;
}
#endif


// Python 3.11 added PyType_GetName() and PyType_GetQualName()
#if (PY_VERSION_HEX < _Py_PACK_VERSION(3, 11) \
     || (defined(Py_LIMITED_API) && Py_LIMITED_API+0 < _Py_PACK_VERSION(3, 11)))
static inline PyObject*
PyType_GetName(PyTypeObject *type)
{
    return PyObject_GetAttrString(_PyObject_CAST(type), "__name__");
}

static inline PyObject*
PyType_GetQualName(PyTypeObject *type)
{
    return PyObject_GetAttrString(_PyObject_CAST(type), "__qualname__");
}
#endif


// Python 3.13 added PyType_GetModuleName() and PyType_GetFullyQualifiedName()
#if (PY_VERSION_HEX < _Py_PACK_VERSION(3, 13) \
     || (defined(Py_LIMITED_API) && Py_LIMITED_API+0 < _Py_PACK_VERSION(3, 13)))
static inline PyObject*
PyType_GetModuleName(PyTypeObject *type)
{
    return PyObject_GetAttrString(_PyObject_CAST(type), "__module__");
}

static inline PyObject *
PyType_GetFullyQualifiedName(PyTypeObject *type)
{
    PyObject *qualname = PyType_GetQualName(type);
    if (qualname == NULL) {
        return NULL;
    }

    PyObject *module = PyType_GetModuleName(type);
    if (module == NULL) {
        Py_DECREF(qualname);
        return NULL;
    }

    PyObject *result;
    if (PyUnicode_Check(module)
        && PyUnicode_EqualToUTF8(module, "builtins") == 0
        && PyUnicode_EqualToUTF8(module, "__main__") == 0)
    {
        result = PyUnicode_FromFormat("%U.%U", module, qualname);
    }
    else {
        result = Py_NewRef(qualname);
    }
    Py_DECREF(module);
    Py_DECREF(qualname);
    return result;
}
#endif


// Python 3.13 added PyEval_GetFrameLocals(), PyEval_GetFrameGlobals() and
// PyEval_GetFrameBuiltins() (PEP 667).
#if PY_VERSION_HEX < _Py_PACK_VERSION(3, 13)
static inline PyObject*
PyEval_GetFrameLocals(void)
{
    return Py_XNewRef(PyEval_GetLocals());
}

static inline PyObject*
PyEval_GetFrameGlobals(void)
{
    return Py_XNewRef(PyEval_GetGlobals());
}

static inline PyObject*
PyEval_GetFrameBuiltins(void)
{
    return Py_XNewRef(PyEval_GetBuiltins());
}
#endif


#ifdef __cplusplus
}
#endif
#endif  // PYTHONCAPI_COMPAT
