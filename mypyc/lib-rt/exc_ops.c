#include "pythoncapi_compat.h"

// Exception related primitive operations
//
// These are registered in mypyc.primitives.exc_ops.

#include <Python.h>
#include "CPy.h"

// Return a new exception instance, or NULL with an error set.
static PyObject *instantiate_exception(PyObject *type) {
    PyObject *value = PyObject_CallNoArgs(type);
    if (!value)
        return NULL;
    if (!PyExceptionInstance_Check(value)) {
        PyErr_Format(PyExc_TypeError,
                     "calling %R should have returned an instance of "
                     "BaseException, not %R", type, Py_TYPE(value));
        Py_DECREF(value);
        return NULL;
    }
    return value;
}

// A NULL cause means no 'from' clause; Py_None means 'from None'.
static void raise_exception(PyObject *exc, PyObject *cause) {
    PyObject *type;
    PyObject *value;
    if (PyExceptionClass_Check(exc)) {
        type = exc;
        value = instantiate_exception(exc);
        if (!value)
            return;
    } else if (PyExceptionInstance_Check(exc)) {
        type = (PyObject *)Py_TYPE(exc);
        value = Py_NewRef(exc);
    } else {
        PyErr_SetString(PyExc_TypeError, "exceptions must derive from BaseException");
        return;
    }

    if (cause != NULL) {
        PyObject *fixed_cause;
        if (PyExceptionClass_Check(cause)) {
            fixed_cause = instantiate_exception(cause);
            if (!fixed_cause)
                goto fail;
        } else if (PyExceptionInstance_Check(cause)) {
            fixed_cause = Py_NewRef(cause);
        } else if (Py_IsNone(cause)) {
            fixed_cause = NULL;
        } else {
            PyErr_SetString(PyExc_TypeError, "exception causes must derive from BaseException");
            goto fail;
        }
        // This steals the reference to the cause and sets __suppress_context__
        PyException_SetCause(value, fixed_cause);
    }
    // Normalize against the original class, even if __new__ returned an unrelated exception.
    PyErr_SetObject(type, value);
fail:
    Py_DECREF(value);
}

void CPy_Raise(PyObject *exc) {
    raise_exception(exc, NULL);
}

void CPy_RaiseFrom(PyObject *exc, PyObject *cause) {
    raise_exception(exc, cause);
}

void CPy_Reraise(void) {
    PyObject *p_type, *p_value, *p_traceback;
    PyErr_GetExcInfo(&p_type, &p_value, &p_traceback);
    if (p_value == NULL || Py_IsNone(p_value)) {
        Py_XDECREF(p_type);
        Py_XDECREF(p_value);
        Py_XDECREF(p_traceback);
        PyErr_SetString(PyExc_RuntimeError, "No active exception to reraise");
        return;
    }
    PyErr_Restore(p_type, p_value, p_traceback);
}

void CPyErr_SetObjectAndTraceback(PyObject *type, PyObject *value, PyObject *traceback) {
    if (!PyType_Check(type) && Py_IsNone(value)) {
        // The first argument must be an exception instance
        value = type;
        type = (PyObject *)Py_TYPE(value);
    }

    // PyErr_Restore steals a reference to each argument.
    Py_INCREF(type);
    Py_INCREF(value);
    // An omitted traceback (or None) preserves an exception instance's
    // existing traceback, as generator.throw() and coroutine.throw() do.
    if (Py_IsNone(traceback) && PyExceptionInstance_Check(value)) {
        traceback = PyException_GetTraceback(value);
    } else {
        Py_INCREF(traceback);
    }
    PyErr_Restore(type, value, traceback);
}

// Validate the arguments of generator.throw() before resuming the generator, like
// CPython's _gen_throw. Return false and set an error if they are invalid.
bool CPyGen_CheckThrowArgs(PyObject *type, PyObject *value, PyObject *traceback) {
    if (!Py_IsNone(traceback) && !PyTraceBack_Check(traceback)) {
        PyErr_SetString(PyExc_TypeError, "throw() third argument must be a traceback object");
        return false;
    }
    if (PyExceptionClass_Check(type)) {
        return true;
    }
    if (PyExceptionInstance_Check(type)) {
        if (!Py_IsNone(value)) {
            PyErr_SetString(PyExc_TypeError, "instance exception may not have a separate value");
            return false;
        }
        return true;
    }
    PyErr_Format(PyExc_TypeError,
                 "exceptions must be classes or instances deriving from BaseException, not %s",
                 Py_TYPE(type)->tp_name);
    return false;
}

tuple_T3OOO CPy_CatchError(void) {
    // We need to return the existing sys.exc_info() information, so
    // that it can be restored when we finish handling the error we
    // are catching now. Grab that triple and convert NULL values to
    // the ExcDummy object in order to simplify refcount handling in
    // generated code.
    tuple_T3OOO ret;
    PyErr_GetExcInfo(&ret.f0, &ret.f1, &ret.f2);
    _CPy_ToDummy(&ret.f0);
    _CPy_ToDummy(&ret.f1);
    _CPy_ToDummy(&ret.f2);

    if (!PyErr_Occurred()) {
        PyErr_SetString(PyExc_RuntimeError, "CPy_CatchError called with no error!");
    }

    // Retrieve the error info and normalize it so that it looks like
    // what python code needs it to be.
    PyObject *type, *value, *traceback;
    PyErr_Fetch(&type, &value, &traceback);
    // Could we avoid always normalizing?
    PyErr_NormalizeException(&type, &value, &traceback);
    if (traceback != NULL) {
        PyException_SetTraceback(value, traceback);
    }
    // Indicate that we are now handling this exception by stashing it
    // in sys.exc_info().  mypyc routines that need access to the
    // exception will read it out of there.
    PyErr_SetExcInfo(type, value, traceback);
    // Clear the error indicator, since the exception isn't
    // propagating anymore.
    PyErr_Clear();

    return ret;
}

void CPy_RestoreExcInfo(tuple_T3OOO info) {
    PyErr_SetExcInfo(_CPy_FromDummy(info.f0), _CPy_FromDummy(info.f1), _CPy_FromDummy(info.f2));
}

bool CPy_ExceptionMatches(PyObject *type) {
    return PyErr_GivenExceptionMatches((PyObject *)Py_TYPE(CPy_ExcState()->exc_value), type);
}

PyObject *CPy_GetExcValue(void) {
    PyObject *exc = CPy_ExcState()->exc_value;
    Py_INCREF(exc);
    return exc;
}

static inline void _CPy_ToNone(PyObject **p) {
    if (*p == NULL) {
        Py_INCREF(Py_None);
        *p = Py_None;
    }
}

void _CPy_GetExcInfo(PyObject **p_type, PyObject **p_value, PyObject **p_traceback) {
    PyErr_GetExcInfo(p_type, p_value, p_traceback);
    _CPy_ToNone(p_type);
    _CPy_ToNone(p_value);
    _CPy_ToNone(p_traceback);
}

tuple_T3OOO CPy_GetExcInfo(void) {
    tuple_T3OOO ret;
    _CPy_GetExcInfo(&ret.f0, &ret.f1, &ret.f2);
    return ret;
}

void CPyError_OutOfMemory(void) {
    fprintf(stderr, "fatal: out of memory\n");
    fflush(stderr);
    abort();
}

// Construct a nicely formatted type name based on __module__ and __name__.
static PyObject *CPy_GetTypeName(PyObject *type) {
    PyObject *module = NULL, *name = NULL;
    PyObject *full = NULL;

    module = PyObject_GetAttr(type, mypyc_interned_str.__module__);
    if (!module || !PyUnicode_Check(module)) {
        goto out;
    }
    name = PyObject_GetAttr(type, mypyc_interned_str.__qualname__);
    if (!name || !PyUnicode_Check(name)) {
        goto out;
    }

    if (PyUnicode_CompareWithASCIIString(module, "builtins") == 0) {
        Py_INCREF(name);
        full = name;
    } else {
        full = PyUnicode_FromFormat("%U.%U", module, name);
    }

out:
    Py_XDECREF(module);
    Py_XDECREF(name);
    return full;
}

// Get the type of a value as a string, expanding tuples to include
// all the element types.
static PyObject *CPy_FormatTypeName(PyObject *value) {
    if (Py_IsNone(value)) {
        return PyUnicode_FromString("None");
    }

    if (!PyTuple_CheckExact(value)) {
        return CPy_GetTypeName((PyObject *)Py_TYPE(value));
    }

    if (PyTuple_GET_SIZE(value) > 10) {
        return PyUnicode_FromFormat("tuple[<%d items>]", PyTuple_GET_SIZE(value));
    }

    // Most of the logic is all for tuples, which is the only interesting case
    PyObject *output = PyUnicode_FromString("tuple[");
    if (!output) {
        return NULL;
    }
    /* This is quadratic but if that ever matters something is really weird. */
    int i;
    for (i = 0; i < PyTuple_GET_SIZE(value); i++) {
        PyObject *s = CPy_FormatTypeName(PyTuple_GET_ITEM(value, i));
        if (!s) {
            Py_DECREF(output);
            return NULL;
        }
        PyObject *next = PyUnicode_FromFormat("%U%U%s", output, s,
                                              i + 1 == PyTuple_GET_SIZE(value) ? "]" : ", ");
        Py_DECREF(output);
        Py_DECREF(s);
        if (!next) {
            return NULL;
        }
        output = next;
    }
    return output;
}

CPy_NOINLINE
void CPy_TypeError(const char *expected, PyObject *value) {
    PyObject *out = CPy_FormatTypeName(value);
    if (out) {
        PyErr_Format(PyExc_TypeError, "%s object expected; got %U", expected, out);
        Py_DECREF(out);
    } else {
        PyErr_Format(PyExc_TypeError, "%s object expected; and errored formatting real type!",
                     expected);
    }
}

// The PyFrameObject type definition (struct _frame) has been moved
// to the internal C API: to the pycore_frame.h header file.
// https://github.com/python/cpython/pull/31530
#if PY_VERSION_HEX >= 0x030b00a6
#include "internal/pycore_frame.h"
#endif

// Cache of the code objects used for traceback entries.
//
// Creating a new code object for each traceback entry is slow. It's also a
// problem for memory use on free-threaded builds, since code objects use
// deferred reference counting there and are only freed by the cyclic GC. The
// GC only runs when the eval breaker is handled, which doesn't happen in a
// native loop that doesn't call interpreted code, so a loop that repeatedly
// raises and catches an exception would accumulate dead code objects until
// it returns.
//
// The cache is direct-mapped. The slot is chosen based on the string pointers
// and the line number, but the string contents are compared on lookup, since
// the strings aren't required to have static storage duration.
#define CPY_TB_CODE_CACHE_SIZE 256

typedef struct {
    char *filename;  // Owned copy
    char *funcname;  // Owned copy
    int line;
    PyCodeObject *code;
} CPyTracebackCodeCacheEntry;

static CPyTracebackCodeCacheEntry tb_code_cache[CPY_TB_CODE_CACHE_SIZE];

#ifdef Py_GIL_DISABLED
static PyMutex tb_code_cache_mutex;
#define TB_CODE_CACHE_LOCK() PyMutex_Lock(&tb_code_cache_mutex)
#define TB_CODE_CACHE_UNLOCK() PyMutex_Unlock(&tb_code_cache_mutex)
#else
#define TB_CODE_CACHE_LOCK()
#define TB_CODE_CACHE_UNLOCK()
#endif

static inline size_t tb_code_cache_index(const char *filename, const char *funcname, int line) {
    size_t h = (size_t)(uintptr_t)funcname + (size_t)(uintptr_t)filename * 3
        + (size_t)line * 0x9e3779b1u;
    h ^= h >> 16;
    h ^= h >> 8;
    return h & (CPY_TB_CODE_CACHE_SIZE - 1);
}

static char *copy_c_string(const char *s) {
    size_t size = strlen(s) + 1;
    char *result = PyMem_RawMalloc(size);
    if (result != NULL) {
        memcpy(result, s, size);
    }
    return result;
}

// Return a new reference to a code object for a traceback entry, or NULL with
// an error set.
static PyCodeObject *get_traceback_code(const char *filename, const char *funcname, int line) {
    CPyTracebackCodeCacheEntry *entry =
        &tb_code_cache[tb_code_cache_index(filename, funcname, line)];
    PyCodeObject *code = NULL;

    TB_CODE_CACHE_LOCK();
    if (entry->code != NULL && entry->line == line
            && strcmp(entry->funcname, funcname) == 0
            && strcmp(entry->filename, filename) == 0) {
        code = (PyCodeObject *)Py_NewRef(entry->code);
    }
    TB_CODE_CACHE_UNLOCK();
    if (code != NULL) {
        return code;
    }

    code = PyCode_NewEmpty(filename, funcname, line);
    if (code == NULL) {
        return NULL;
    }
    char *filename_copy = copy_c_string(filename);
    char *funcname_copy = copy_c_string(funcname);
    if (filename_copy == NULL || funcname_copy == NULL) {
        // Not being able to cache the code object is fine.
        PyMem_RawFree(filename_copy);
        PyMem_RawFree(funcname_copy);
        return code;
    }

    TB_CODE_CACHE_LOCK();
    CPyTracebackCodeCacheEntry old = *entry;
    entry->filename = filename_copy;
    entry->funcname = funcname_copy;
    entry->line = line;
    entry->code = (PyCodeObject *)Py_NewRef(code);
    TB_CODE_CACHE_UNLOCK();

    // Release the evicted entry only after the cache is consistent again, since
    // the decref could run arbitrary code.
    PyMem_RawFree(old.filename);
    PyMem_RawFree(old.funcname);
    Py_XDECREF(old.code);
    return code;
}

// This function is basically exactly the same with _PyTraceback_Add
// which is available in all the versions we support, except that
// code objects are cached (see above).
void CPy_AddTraceback(const char *filename, const char *funcname, int line, PyObject *globals) {
    PyObject *exc, *val, *tb;
    PyThreadState *thread_state = PyThreadState_GET();
    PyFrameObject *frame_obj;

    // We need to save off the exception state because in 3.8,
    // PyFrame_New fails if there is an error set and it fails to look
    // up builtins in the globals. (_PyTraceback_Add documents that it
    // needs to do it because it decodes the filename according to the
    // FS encoding, which could have a decoder in Python. We don't do
    // that so *that* doesn't apply to us.)
    PyErr_Fetch(&exc, &val, &tb);
    PyCodeObject *code_obj = get_traceback_code(filename, funcname, line);
    if (code_obj == NULL) {
        goto error;
    }

    frame_obj = PyFrame_New(thread_state, code_obj, globals, 0);
    if (frame_obj == NULL) {
        Py_DECREF(code_obj);
        goto error;
    }
    frame_obj->f_lineno = line;
    PyErr_Restore(exc, val, tb);
    PyTraceBack_Here(frame_obj);
    Py_DECREF(code_obj);
    Py_DECREF(frame_obj);

    return;

error:
#if CPY_3_12_FEATURES
    _PyErr_ChainExceptions1(exc);
#else
    _PyErr_ChainExceptions(exc, val, tb);
#endif
}

CPy_NOINLINE
void CPy_TypeErrorTraceback(const char *filename, const char *funcname, int line,
                            PyObject *globals, const char *expected, PyObject *value) {
    CPy_TypeError(expected, value);
    CPy_AddTraceback(filename, funcname, line, globals);
}

void CPy_AttributeError(const char *filename, const char *funcname, const char *classname,
                        const char *attrname, int line, PyObject *globals) {
    char buf[500];
    snprintf(buf, sizeof(buf), "attribute '%.200s' of '%.200s' undefined", attrname, classname);
    PyErr_SetString(PyExc_AttributeError, buf);
    CPy_AddTraceback(filename, funcname, line, globals);
}
