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

// Give a contextmanager's generator factory the same binding as its wrapper.
// The returned callable is owned; static methods remain unbound.
PyObject *CPyContextManager_Bind(PyObject *callable, PyObject *wrapped) {
    if (PyMethod_Check(callable)) {
        // Use the actual bound instance or class, not the attribute lookup's receiver.
        return PyMethod_New(wrapped, PyMethod_GET_SELF(callable));
    }
    Py_INCREF(wrapped);
    return wrapped;
}

// Implement contextlib's generator entry protocol. The returned value is owned.
PyObject *CPyContextManager_Enter(PyObject *gen) {
    if (!PyIter_Check(gen)) {
        PyErr_Format(PyExc_TypeError, "'%.200s' object is not an iterator", Py_TYPE(gen)->tp_name);
        return NULL;
    }
    PyObject *value = Py_TYPE(gen)->tp_iternext(gen);
    if (value != NULL) {
        return value;
    }
    if (!PyErr_Occurred()) {
        // Iterators may signal exhaustion without setting StopIteration.
        PyErr_SetNone(PyExc_StopIteration);
    }
    if (PyErr_ExceptionMatches(PyExc_StopIteration)) {
        // raise RuntimeError(...) from None, retaining the suppressed context.
        tuple_T3OOO old_exc = CPy_CatchError();
        PyObject *error = PyObject_CallFunction(PyExc_RuntimeError, "s", "generator didn't yield");
        if (error != NULL) {
            CPy_RaiseFrom(error, Py_None);
            Py_DECREF(error);
        }
        CPy_RestoreExcInfo(old_exc);
        Py_DECREF(old_exc.f0);
        Py_DECREF(old_exc.f1);
        Py_DECREF(old_exc.f2);
    }
    return NULL;
}

// An extra yield is a protocol error. Always leave an exception pending.
static void contextmanager_exit_error(PyObject *gen, const char *message) {
    PyErr_SetString(PyExc_RuntimeError, message);
#if PY_VERSION_HEX >= 0x030B0000
    // Since Python 3.11, contextlib closes the generator in a finally block
    tuple_T3OOO old_exc = CPy_CatchError();
    PyObject *type, *value, *traceback;
    PyErr_GetExcInfo(&type, &value, &traceback);
    PyObject *closed = PyObject_CallMethod(gen, "close", NULL);
    if (closed != NULL) {
        Py_DECREF(closed);
        // A native generator can change the handled exception during close()
        // Reraise the saved protocol error, as a Python finally block does
        PyErr_Restore(type, value, traceback);
    } else {
        Py_XDECREF(type);
        Py_XDECREF(value);
        Py_XDECREF(traceback);
    }
    CPy_RestoreExcInfo(old_exc);
    Py_DECREF(old_exc.f0);
    Py_DECREF(old_exc.f1);
    Py_DECREF(old_exc.f2);
#endif
}

// Finish a contextmanager whose body succeeded. Return false on error.
bool CPyContextManager_ExitNormal(PyObject *gen) {
    // try:
    //     next(self.gen)
    if (!PyIter_Check(gen)) {
        PyErr_Format(PyExc_TypeError, "'%.200s' object is not an iterator", Py_TYPE(gen)->tp_name);
        return false;
    }
    PyObject *value = Py_TYPE(gen)->tp_iternext(gen);

    // except StopIteration:
    //     return False
    if (value == NULL) {
        if (!PyErr_Occurred() || PyErr_ExceptionMatches(PyExc_StopIteration)) {
            PyErr_Clear();
            return true;
        }
        return false;
    }

    // else:
    //     try:
    //         raise RuntimeError("generator didn't stop")
    //     finally:
    //         self.gen.close()
    Py_DECREF(value);
    contextmanager_exit_error(gen, "generator didn't stop");
    return false;
}

// Match contextlib._GeneratorContextManager.__exit__ for a failed with body.
int CPyContextManager_ExitException(PyObject *gen, PyObject *type,
                                    PyObject *value, PyObject *traceback) {

    // Native generators can change the handled exception when throw() unwinds
    // an except block. Preserve the caller's state before interpreting the result
    PyObject *saved_type, *saved_value, *saved_traceback;
    PyErr_GetExcInfo(&saved_type, &saved_value, &saved_traceback);

    // try:
    //     self.gen.throw(typ, value, traceback)
#if PY_VERSION_HEX >= 0x030C0000
    PyObject *yielded = PyObject_CallMethod(gen, "throw", "(O)", value);
#else
    PyObject *yielded = PyObject_CallMethod(gen, "throw", "(OOO)", type, value, traceback);
#endif
    PyErr_SetExcInfo(saved_type, saved_value, saved_traceback);

    // ... if we didn't get an exception from throw, in particular, StopIteration ...
    if (yielded != NULL) {
        // try:
        //     raise RuntimeError("generator didn't stop after throw()")
        // finally:
        //     self.gen.close()
        Py_DECREF(yielded);
        contextmanager_exit_error(gen, "generator didn't stop after throw()");
        return -1;
    }

    tuple_T3OOO old_exc = CPy_CatchError();
    PyObject *error = CPy_GetExcValue();
    int result = -1;

    // # Note the `return False` in the code comments is how contextlib tells Python to
    // # propagate the exception being handled by __exit__

    // except StopIteration as exc:
    //     return exc is not value
    if (CPy_ExceptionMatches(PyExc_StopIteration)) {
        // A body StopIteration must not be mistaken for generator completion.
        result = error != value;
        goto done;
    }
    // except RuntimeError as exc:
    //     if exc is value:
    //         exc.__traceback__ = traceback
    //         return False
    //     if (
    //         isinstance(value, StopIteration)
    //         and exc.__cause__ is value
    //     ):
    //         value.__traceback__ = traceback
    //         return False
    //     raise
    if (CPy_ExceptionMatches(PyExc_RuntimeError)) {
        if (error == value) {
            goto original;
        }
        // PEP 479 can wrap the original StopIteration (including subclasses).
        int is_stop = PyObject_IsInstance(value, PyExc_StopIteration);
        if (is_stop < 0) {
            goto done;
        }
        if (is_stop) {
            PyObject *cause = PyObject_GetAttrString(error, "__cause__");
            if (cause == NULL) {
                goto done;
            }
            bool is_original = cause == value;
            Py_DECREF(cause);
            if (is_original) {
                goto original;
            }
        }
    }
    // except BaseException as exc:
    //     if exc is not value:
    //         raise
    //     exc.__traceback__ = traceback
    //     return False
    else if (error == value) {
        goto original;
    }
    CPy_Reraise();
    goto done;

original:
#if PY_VERSION_HEX >= 0x030B0000
    if (PyObject_SetAttrString(value, "__traceback__", traceback) < 0) {
        goto done;
    }
#endif
    result = 0;

done:
    Py_DECREF(error);
    CPy_RestoreExcInfo(old_exc);
    Py_DECREF(old_exc.f0);
    Py_DECREF(old_exc.f1);
    Py_DECREF(old_exc.f2);
    return result;
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

// This function is basically exactly the same with _PyTraceback_Add
// which is available in all the versions we support.
// We're continuing to use this because we'll probably optimize this later.
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
    PyCodeObject *code_obj = PyCode_NewEmpty(filename, funcname, line);
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
