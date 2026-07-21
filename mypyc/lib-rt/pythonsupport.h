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
#include "internal/pycore_object.h"  // _Py_TryIncrefFast, _Py_TryIncRefShared
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
// returning a new reference (or NULL if the field is NULL/undefined).
//
// On free-threaded builds a plain load followed by an incref races with a
// concurrent setter that may decref the old value to zero and free it before the
// incref runs (use-after-free). CPy_SetAttrRef avoids that by reclaiming old
// values through QSBR-delayed decref, so a value observed in the field remains
// safe to touch while this reader is running.
//
// Only the hot case is inlined here: an incref of a value owned by this thread or
// immortal, via '_Py_TryIncrefFast' (no CAS, no loop). Everything colder -- the
// cross-thread shared-refcount CAS and the _Py_NewRefWithLock fallback -- lives
// out-of-line in 'CPy_GetAttrRefSlow'. Splitting it this way keeps each call
// site's fast path small enough to inline, which is measurably faster than
// letting the compiler auto-out-line the whole helper (that merges every read
// site's branch history into one shared copy and mispredicts). It is only used in
// free-threaded builds; the default (GIL) build keeps the plain load + incref
// generated inline by mypyc.
PyObject *CPy_GetAttrRefSlow(PyObject *v);

static inline PyObject *CPy_GetAttrRef(PyObject **field) {
    PyObject *v = (PyObject *)_Py_atomic_load_ptr_acquire(field);
    if (v == NULL) {
        return NULL;
    }
    if (_Py_TryIncrefFast(v)) {
        return v;
    }
    return CPy_GetAttrRefSlow(v);
}

// Read a native attribute that is a single reference-counted 'PyObject *' field
// AND is Final (assigned once during construction, never rebound -- mypyc emits no
// setter for it), returning a new reference (or NULL if undefined).
//
// A Final attribute has no concurrent writer after 'self' is published, so the
// use-after-free race that CPy_GetAttrRef guards against cannot happen: the field
// holds a strong reference for the object's whole lifetime, and any thread reading
// it necessarily holds 'self', which keeps the value alive. So the try-incref +
// _Py_NewRefWithLock fallback are unnecessary here -- a plain load + Py_INCREF is
// safe. A cross-thread Py_INCREF is an unconditional
// atomic add on ob_ref_shared, so (unlike CPy_GetAttrRef's try-incref) it needs no
// maybe-weakref and has no slow path. The load is relaxed rather than acquire: the
// reader reached 'self' through a synchronization edge (self's own publication)
// that already ordered the construction stores before it, exactly as with
// CPy_InitAttrRef's relaxed store. Relaxed keeps it TSan-clean at zero cost (plain
// mov/ldr).
static inline PyObject *CPy_GetAttrRefFinal(PyObject **field) {
    PyObject *v = (PyObject *)_Py_atomic_load_ptr_relaxed(field);
    if (v != NULL) {
        Py_INCREF(v);
    }
    return v;
}

// Reclaim the previous value of a native attribute after it has been replaced.
//
// CPy_GetAttrRef reads the field optimistically without holding any lock the
// writer also takes, so a reader can load the old pointer and then try to take a
// reference after this store. The old value must therefore stay alive until every
// thread has passed a quiescent point, which is exactly what a QSBR-deferred
// decref guarantees. So all mortal old values are
// reclaimed via _PyObject_XDecRefDelayed, matching CPython's own replace-a-slot
// paths (e.g. _PyObject_SetDict / _PyObject_SetManagedDict).
//
// We deliberately do NOT take a "local refcount > 1, owned by this thread" fast
// path: dropping the field's reference is not the only decref of the object, so a
// non-freeing local decrement here does not prevent an unrelated reference holder
// from driving the object to zero (a plain, non-deferred Py_DECREF -> _Py_Dealloc)
// while an in-flight reader still holds the stale pointer -- a use-after-free that
// only QSBR deferral closes. Immortal objects are never freed, so skipping their
// decref entirely is safe and avoids queuing a no-op onto the delayed-free list.
static inline void CPy_DecRefAttrOld(PyObject *op) {
    if (op == NULL) {
        return;
    }
    if (_Py_IsImmortal(op)) {
        return;
    }
    _PyObject_XDecRefDelayed(op);
}

// Set a native attribute that is a single reference-counted 'PyObject *' field,
// stealing the reference to 'value' (which may be NULL to delete the attribute)
// and safely reclaiming the previous value.
//
// Memory safety does NOT depend on SetMaybeWeakref here, so (unlike an earlier
// version) we do not call it. Two things keep this safe:
//   - The old value is reclaimed via CPy_DecRefAttrOld, a QSBR-deferred decref, so
//     it cannot be freed while an in-flight CPy_GetAttrRef still holds the stale
//     pointer.
//   - A concurrent cross-thread reader whose inline fast-path try-incref fails on
//     an unflagged 'value' still cannot fail and never blocks on this writer:
//     CPy_GetAttrRef falls into CPy_GetAttrRefSlow, which is fully lock-free. It
//     retries with a lock-free shared-refcount CAS (_Py_TryIncRefShared) and, only
//     if that also fails, forces a reference via _Py_NewRefWithLock, which cannot
//     fail and lazily sets maybe-weakref so later cross-thread reads take the CAS.
// This mirrors CPy_InitAttrRef, which already omits SetMaybeWeakref for the same
// reason. Setting the flag here would only be a possible performance tuning knob
// (it would let that first cross-thread reader succeed on the cheaper
// _Py_TryIncRefShared CAS instead of falling through to _Py_NewRefWithLock); it is
// not needed for correctness. The atomic exchange publishes the new pointer and
// hands back the old one without a writer/writer race.
static inline void CPy_SetAttrRef(PyObject **field, PyObject *value) {
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
// the first cross-thread read that needs it.
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
