// Collects code that was copied in from cpython, for a couple of different reasons:
//  * We wanted to modify it to produce a more efficient version for our uses
//  * We needed to call it and it was static :(
//  * We wanted to call it and needed to backport it

#ifndef CPY_PYTHONSUPPORT_H
#define CPY_PYTHONSUPPORT_H

#include <Python.h>
#include <stdbool.h>
#include "pythoncapi_compat.h"
#include <frameobject.h>
#include <assert.h>
#include "static_data.h"
#include "mypyc_util.h"

#if CPY_3_13_FEATURES
#ifndef Py_BUILD_CORE
#define Py_BUILD_CORE
#endif
#include "internal/pycore_genobject.h"  // _PyGen_FetchStopIterationValue
#include "internal/pycore_pyerrors.h"  // _PyErr_FormatFromCause, _PyErr_SetKeyError
#include "internal/pycore_setobject.h"  // _PySet_Update
#endif

#ifdef Py_GIL_DISABLED
#include "internal/pycore_object.h"  // _Py_TryIncrefCompare
#endif

#if CPY_3_12_FEATURES
#include "internal/pycore_frame.h"
#endif

#ifdef __cplusplus
extern "C" {
#endif
#if 0
} // why isn't emacs smart enough to not indent this
#endif

#ifdef Py_GIL_DISABLED
// Read a native attribute that is a single reference-counted 'PyObject *' field,
// returning a new reference (or NULL if the field is NULL/undefined). 'self' is
// the object owning the field, used only by the cold slow path below.
//
// On free-threaded builds a plain load followed by an incref races with a
// concurrent setter that may decref the old value to zero and free it before the
// incref runs (use-after-free). The fast path mirrors CPython's '_Py_XGetRef':
// optimistically incref via '_Py_TryIncrefCompare', which re-validates the
// pointer and backs out if a writer changed it.
//
// The slow path (cold) handles a value that has not had maybe-weakref set and is
// owned by another thread: '_Py_TryIncRefShared' then returns 0 permanently, so a
// plain retry loop would spin forever. This case arises because 'CPy_InitAttrRef'
// publishes initializer stores WITHOUT setting maybe-weakref (a measured win for
// construction-heavy code -- see docs/design/free-threaded-attr-safety.md). We
// recover exactly as CPython's lock-free dict reader does (Objects/dictobject.c,
// the 'read_failed' path): take the owning object's critical section and force a
// cross-thread reference via '_Py_NewRefWithLock', which cannot fail and sets
// maybe-weakref so subsequent reads take the fast path. QSBR keeps the loaded
// value alive across this, since setters defer the freeing decref past any
// quiescent point. This same fallback also covers a transient lost race with a
// concurrent writer. It is only used in free-threaded builds; the default (GIL)
// build keeps the plain load + incref generated inline by mypyc.
// Cold slow path of CPy_GetAttrRef, kept out-of-line (see pythonsupport.c) so the
// inline fast path stays small enough for the compiler to inline at call sites.
PyObject *CPy_GetAttrRefSlow(PyObject *self, PyObject **field);

static inline PyObject *CPy_GetAttrRef(PyObject *self, PyObject **field) {
    PyObject *v = (PyObject *)_Py_atomic_load_ptr_acquire(field);
    if (v == NULL) {
        return NULL;
    }
    // Hot case only: object is owned by this thread or immortal (no CAS, no loop).
    // Everything else -- the cross-thread shared-refcount CAS, the pointer
    // re-validation, and the not-yet-shared critical-section fallback -- lives in
    // the out-of-line slow path to keep this body small enough to inline.
    if (_Py_TryIncrefFast(v)) {
        return v;
    }
    return CPy_GetAttrRefSlow(self, field);
}

// Reclaim the previous value of a native attribute after it has been replaced.
//
// The fast path avoids QSBR deferral when the decref provably cannot free the
// object: immortal objects are never freed, and an object owned by the current
// thread with a local refcount > 1 stays at refcount >= 1 after a plain local
// decrement, so no concurrent reader can ever observe a freed header. Only the
// cases that could actually free (local refcount would reach zero, or the object
// is owned by another thread) defer the decref via QSBR, which keeps the memory
// valid until every thread has passed a quiescent point -- long enough for an
// in-flight reader that loaded the old pointer to finish its try-incref.
static inline void CPy_DecRefAttrOld(PyObject *op) {
    if (op == NULL) {
        return;
    }
    uint32_t local = _Py_atomic_load_uint32_relaxed(&op->ob_ref_local);
    if (local == _Py_IMMORTAL_REFCNT_LOCAL) {
        return;
    }
    if (local > 1 && _Py_IsOwnedByCurrentThread(op)) {
        // Same as Py_DECREF's owned-thread fast path: only this thread writes
        // ob_ref_local, and the refcount stays >= 1, so this is race-free.
        _Py_atomic_store_uint32_relaxed(&op->ob_ref_local, local - 1);
        return;
    }
    _PyObject_XDecRefDelayed(op);
}

// Set a native attribute that is a single reference-counted 'PyObject *' field,
// stealing the reference to 'value' (which may be NULL to delete the attribute)
// and safely reclaiming the previous value.
//
// SetMaybeWeakref is required for correctness, not just performance: it lets a
// concurrent cross-thread reader's shared-refcount CAS in CPy_GetAttrRef succeed
// instead of failing and spinning (see the "writer must set maybe-weakref"
// requirement documented on CPython's _Py_XGetRef). The atomic exchange publishes
// the new pointer and hands back the old one without a writer/writer race.
static inline void CPy_SetAttrRef(PyObject **field, PyObject *value) {
    if (value != NULL) {
        _PyObject_SetMaybeWeakref(value);
    }
    PyObject *old = (PyObject *)_Py_atomic_exchange_ptr(field, value);
    CPy_DecRefAttrOld(old);
}

// Initialize a native attribute that is known to be previously undefined (NULL),
// stealing the reference to 'value'.
//
// Initializer stores only happen while 'self' is still thread-local (the
// attribute-definedness analysis marks a SetAttr as an initializer only before
// 'self' can leak -- see mypyc/analysis/attrdefined.py). So there is no old value
// to reclaim, no competing writer, and the field store is not itself the
// publication point: 'self' is published later (when it escapes __init__ or is
// returned), and that publication carries the release barrier making all the
// construction stores visible. A relaxed store therefore suffices.
//
// Unlike CPy_SetAttrRef, this deliberately does NOT call SetMaybeWeakref (its CAS
// is pure overhead here, ~+2.6ns per fresh store, and construction-heavy code
// pays it on every attribute of every new object). The cost is moved off this hot
// path onto CPy_GetAttrRef's cold slow path, which sets maybe-weakref lazily on
// the first cross-thread read that needs it. See
// docs/design/free-threaded-attr-safety.md ("Experiment: reader-side fallback").
static inline void CPy_InitAttrRef(PyObject **field, PyObject *value) {
    _Py_atomic_store_ptr_relaxed(field, value);
}
#endif

PyObject* update_bases(PyObject *bases);
int init_subclass(PyTypeObject *type, PyObject *kwds);

Py_ssize_t
CPyLong_AsSsize_tAndOverflow_(PyObject *vv, int *overflow);

#if CPY_3_12_FEATURES

static inline Py_ssize_t
CPyLong_AsSsize_tAndOverflow(PyObject *vv, int *overflow)
{
    /* This version by Tim Peters */
    PyLongObject *v = (PyLongObject *)vv;
    Py_ssize_t res;
    Py_ssize_t i;

    *overflow = 0;

    res = -1;
    i = CPY_LONG_TAG(v);

    // TODO: Combine zero and non-zero cases helow?
    if (likely(i == (1 << CPY_NON_SIZE_BITS))) {
        res = CPY_LONG_DIGIT(v, 0);
    } else if (likely(i == CPY_SIGN_ZERO)) {
        res = 0;
    } else if (i == ((1 << CPY_NON_SIZE_BITS) | CPY_SIGN_NEGATIVE)) {
        res = -(sdigit)CPY_LONG_DIGIT(v, 0);
    } else {
        // Slow path is moved to a non-inline helper function to
        // limit size of generated code
        int overflow_local;
        res = CPyLong_AsSsize_tAndOverflow_(vv, &overflow_local);
        *overflow = overflow_local;
    }
    return res;
}

#else

// Adapted from longobject.c in Python 3.7.0

/* This function adapted from PyLong_AsLongLongAndOverflow, but with
 * some safety checks removed and specialized to only work for objects
 * that are already longs.
 * About half of the win this provides, though, just comes from being
 * able to inline the function, which in addition to saving function call
 * overhead allows the out-parameter overflow flag to be collapsed into
 * control flow.
 * Additionally, we check against the possible range of CPyTagged, not of
 * Py_ssize_t. */
static inline Py_ssize_t
CPyLong_AsSsize_tAndOverflow(PyObject *vv, int *overflow)
{
    /* This version by Tim Peters */
    PyLongObject *v = (PyLongObject *)vv;
    Py_ssize_t res;
    Py_ssize_t i;

    *overflow = 0;

    res = -1;
    i = Py_SIZE(v);

    if (likely(i == 1)) {
        res = CPY_LONG_DIGIT(v, 0);
    } else if (likely(i == 0)) {
        res = 0;
    } else if (i == -1) {
        res = -(sdigit)CPY_LONG_DIGIT(v, 0);
    } else {
        // Slow path is moved to a non-inline helper function to
        // limit size of generated code
        int overflow_local;
        res = CPyLong_AsSsize_tAndOverflow_(vv, &overflow_local);
        *overflow = overflow_local;
    }
    return res;
}

#endif

// Adapted from listobject.c in Python 3.7.0
static int
list_resize(PyListObject *self, Py_ssize_t newsize)
{
    PyObject **items;
    size_t new_allocated, num_allocated_bytes;
    Py_ssize_t allocated = self->allocated;

    /* Bypass realloc() when a previous overallocation is large enough
       to accommodate the newsize.  If the newsize falls lower than half
       the allocated size, then proceed with the realloc() to shrink the list.
    */
    if (allocated >= newsize && newsize >= (allocated >> 1)) {
        assert(self->ob_item != NULL || newsize == 0);
        Py_SET_SIZE(self, newsize);
        return 0;
    }

    /* This over-allocates proportional to the list size, making room
     * for additional growth.  The over-allocation is mild, but is
     * enough to give linear-time amortized behavior over a long
     * sequence of appends() in the presence of a poorly-performing
     * system realloc().
     * The growth pattern is:  0, 4, 8, 16, 25, 35, 46, 58, 72, 88, ...
     * Note: new_allocated won't overflow because the largest possible value
     *       is PY_SSIZE_T_MAX * (9 / 8) + 6 which always fits in a size_t.
     */
    new_allocated = (size_t)newsize + (newsize >> 3) + (newsize < 9 ? 3 : 6);
    if (new_allocated > (size_t)PY_SSIZE_T_MAX / sizeof(PyObject *)) {
        PyErr_NoMemory();
        return -1;
    }

    if (newsize == 0)
        new_allocated = 0;
    num_allocated_bytes = new_allocated * sizeof(PyObject *);
    items = (PyObject **)PyMem_Realloc(self->ob_item, num_allocated_bytes);
    if (items == NULL) {
        PyErr_NoMemory();
        return -1;
    }
    self->ob_item = items;
    Py_SET_SIZE(self, newsize);
    self->allocated = new_allocated;
    return 0;
}

// Changed to use PyList_SetSlice instead of the internal list_ass_slice
static PyObject *
list_pop_impl(PyListObject *self, Py_ssize_t index)
{
    PyObject *v;
    int status;

    if (Py_SIZE(self) == 0) {
        /* Special-case most common failure cause */
        PyErr_SetString(PyExc_IndexError, "pop from empty list");
        return NULL;
    }
    if (index < 0)
        index += Py_SIZE(self);
    if (index < 0 || index >= Py_SIZE(self)) {
        PyErr_SetString(PyExc_IndexError, "pop index out of range");
        return NULL;
    }
    v = self->ob_item[index];
    if (index == Py_SIZE(self) - 1) {
        status = list_resize(self, Py_SIZE(self) - 1);
        if (status >= 0)
            return v; /* and v now owns the reference the list had */
        else
            return NULL;
    }
    Py_INCREF(v);
    status = PyList_SetSlice((PyObject *)self, index, index+1, (PyObject *)NULL);
    if (status < 0) {
        Py_DECREF(v);
        return NULL;
    }
    return v;
}

// Tweaked to directly use CPyTagged
static CPyTagged
list_count(PyListObject *self, PyObject *value)
{
    Py_ssize_t count = 0;
    Py_ssize_t i;

#ifdef Py_GIL_DISABLED
    for (i = 0; i < PyList_GET_SIZE(self); i++) {
        PyObject *item = PyList_GetItemRef((PyObject *)self, i);
        if (unlikely(item == NULL)) {
            // Race condition: list shrank between size read and get item
            if (PyErr_ExceptionMatches(PyExc_IndexError)) {
                PyErr_Clear();
                break;
            }
            return CPY_INT_TAG;
        }
        int cmp = PyObject_RichCompareBool(item, value, Py_EQ);
        Py_DECREF(item);
        if (cmp > 0)
            count++;
        else if (cmp < 0)
            return CPY_INT_TAG;
    }
#else
    for (i = 0; i < Py_SIZE(self); i++) {
        int cmp = PyObject_RichCompareBool(self->ob_item[i], value, Py_EQ);
        if (cmp > 0)
            count++;
        else if (cmp < 0)
            return CPY_INT_TAG;
    }
#endif
    return CPyTagged_ShortFromSsize_t(count);
}

// Adapted from genobject.c in Python 3.7.2
// Copied because it wasn't in 3.5.2 and it is undocumented anyways.
/*
 * Set StopIteration with specified value.  Value can be arbitrary object
 * or NULL.
 *
 * Returns 0 if StopIteration is set and -1 if any other exception is set.
 */
static int
CPyGen_SetStopIterationValue(PyObject *value)
{
    PyObject *e;

    if (value == NULL ||
        (!PyTuple_Check(value) && !PyExceptionInstance_Check(value)))
    {
        /* Delay exception instantiation if we can */
        PyErr_SetObject(PyExc_StopIteration, value);
        return 0;
    }
    /* Construct an exception instance manually with
     * PyObject_CallOneArg and pass it to PyErr_SetObject.
     *
     * We do this to handle a situation when "value" is a tuple, in which
     * case PyErr_SetObject would set the value of StopIteration to
     * the first element of the tuple.
     *
     * (See PyErr_SetObject/_PyErr_CreateException code for details.)
     */
    e = PyObject_CallOneArg(PyExc_StopIteration, value);
    if (e == NULL) {
        return -1;
    }
    PyErr_SetObject(PyExc_StopIteration, e);
    Py_DECREF(e);
    return 0;
}

// Copied from dictobject.c and dictobject.h, these are not Public before
// Python 3.8. Also remove some error checks that we do in the callers.
typedef struct {
    PyObject_HEAD
    PyDictObject *dv_dict;
} _CPyDictViewObject;

static PyObject *
_CPyDictView_New(PyObject *dict, PyTypeObject *type)
{
    _CPyDictViewObject *dv = PyObject_GC_New(_CPyDictViewObject, type);
    if (dv == NULL)
        return NULL;
    Py_INCREF(dict);
    dv->dv_dict = (PyDictObject *)dict;
    PyObject_GC_Track(dv);
    return (PyObject *)dv;
}

#ifdef __cplusplus
}
#endif

#if CPY_3_12_FEATURES

// These are copied from genobject.c in Python 3.12

static int
gen_is_coroutine(PyObject *o)
{
    if (PyGen_CheckExact(o)) {
        PyCodeObject *code = PyGen_GetCode((PyGenObject*)o);
        if (code->co_flags & CO_ITERABLE_COROUTINE) {
            return 1;
        }
    }
    return 0;
}

#else

// Copied from genobject.c in Python 3.10
static int
gen_is_coroutine(PyObject *o)
{
    if (PyGen_CheckExact(o)) {
        PyCodeObject *code = (PyCodeObject *)((PyGenObject*)o)->gi_code;
        if (code->co_flags & CO_ITERABLE_COROUTINE) {
            return 1;
        }
    }
    return 0;
}

#endif

/*
 *   This helper function returns an awaitable for `o`:
 *     - `o` if `o` is a coroutine-object;
 *     - `type(o)->tp_as_async->am_await(o)`
 *
 *   Raises a TypeError if it's not possible to return
 *   an awaitable and returns NULL.
 */
static PyObject *
CPyCoro_GetAwaitableIter(PyObject *o)
{
    unaryfunc getter = NULL;
    PyTypeObject *ot;

    if (PyCoro_CheckExact(o) || gen_is_coroutine(o)) {
        /* 'o' is a coroutine. */
        Py_INCREF(o);
        return o;
    }

    ot = Py_TYPE(o);
    if (ot->tp_as_async != NULL) {
        getter = ot->tp_as_async->am_await;
    }
    if (getter != NULL) {
        PyObject *res = (*getter)(o);
        if (res != NULL) {
            if (PyCoro_CheckExact(res) || gen_is_coroutine(res)) {
                /* __await__ must return an *iterator*, not
                   a coroutine or another awaitable (see PEP 492) */
                PyErr_SetString(PyExc_TypeError,
                                "__await__() returned a coroutine");
                Py_CLEAR(res);
            } else if (!PyIter_Check(res)) {
                PyErr_Format(PyExc_TypeError,
                             "__await__() returned non-iterator "
                             "of type '%.100s'",
                             Py_TYPE(res)->tp_name);
                Py_CLEAR(res);
            }
        }
        return res;
    }

    PyErr_Format(PyExc_TypeError,
                 "object %.100s can't be used in 'await' expression",
                 ot->tp_name);
    return NULL;
}


#endif
