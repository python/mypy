#ifndef CPY_CPY_H
#define CPY_CPY_H

#include <stdbool.h>
#include <Python.h>
#include <frameobject.h>
#include <assert.h>
#include "pythonsupport.h"

#ifdef __cplusplus
extern "C" {
#endif
#if 0
} // why isn't emacs smart enough to not indent this
#endif

#define likely(x)       __builtin_expect((x),1)
#define unlikely(x)     __builtin_expect((x),0)
#define CPy_Unreachable() __builtin_unreachable()

// Naming conventions:
//
// Tagged: tagged int
// Long: tagged long int (pointer)
// Short: tagged short int (unboxed)
// LongLong: C long long (64 bit)
// Int: C int
// Object: CPython object (PyObject *)

typedef unsigned long long CPyTagged;
typedef long long CPySignedInt;
typedef PyObject CPyModule;

#define CPY_INT_TAG 1

typedef void (*CPyVTableItem)(void);

static void CPyDebug_Print(const char *msg) {
    printf("%s\n", msg);
    fflush(stdout);
}

// INCREF and DECREF that assert the pointer is not NULL.
// asserts are disabled in release builds so there shouldn't be a perf hit.
// I'm honestly kind of surprised that this isn't done by default.
#define CPy_INCREF(p) do { assert(p); Py_INCREF(p); } while (0)
#define CPy_DECREF(p) do { assert(p); Py_DECREF(p); } while (0)

// Search backwards through the trait part of a vtable (which sits *before*
// the start of the vtable proper) looking for the subvtable describing a trait
// implementation. We don't do any bounds checking so we'd better be pretty sure
// we know that it is there.
static inline CPyVTableItem *CPy_FindTraitVtable(PyTypeObject *trait, CPyVTableItem *vtable) {
    int i;
    for (i = -2; ; i -= 2) {
        if ((PyTypeObject *)vtable[i] == trait) {
            return (CPyVTableItem *)vtable[i + 1];
        }
    }
}

// At load time, we need to patch up trait vtables to contain actual pointers
// to the type objects of the trait, rather than an indirection.
static inline void CPy_FixupTraitVtable(CPyVTableItem *vtable, int count) {
    int i;
    for (i = 0; i < count; i++) {
        vtable[i*2] = *(CPyVTableItem *)vtable[i*2];
    }
}

// Create a heap type based on a template non-heap type.
// This is super hacky and maybe we should suck it up and use PyType_FromSpec instead.
// We allow bases to be NULL to represent just inheriting from object.
// We don't support NULL bases and a non-type metaclass.
static inline PyObject *CPyType_FromTemplate(PyTypeObject *template_,
                                             PyObject *orig_bases,
                                             PyObject *modname) {
    PyHeapTypeObject *t = NULL;
    PyTypeObject *dummy_class = NULL;
    PyObject *name = NULL;
    PyObject *bases = NULL;
    PyObject *slots;

    PyTypeObject *metaclass = Py_TYPE(template_);

    if (orig_bases) {
        bases = update_bases(orig_bases);
        // update_bases doesn't increment the refcount if nothing changes,
        // so we do it to make sure we have distinct "references" to both
        if (bases == orig_bases)
            Py_INCREF(bases);

        // Find the appropriate metaclass from our base classes. We
        // care about this because Generic uses a metaclass prior to
        // Python 3.7.
        metaclass = _PyType_CalculateMetaclass(metaclass, bases);
        if (!metaclass)
            goto error;
    }

    name = PyUnicode_FromString(template_->tp_name);
    if (!name)
        goto error;

    // If there is a metaclass other than type, we would like to call
    // its __new__ function. Unfortunately there doesn't seem to be a
    // good way to mix a C extension class and creating it via a
    // metaclass. We need to do it anyways, though, in order to
    // support subclassing Generic[T] prior to Python 3.7.
    //
    // We solve this with a kind of atrocious hack: create a parallel
    // class using the metaclass, determine the bases of the real
    // class by pulling them out of the parallel class, creating the
    // real class, and then merging its dict back into the original
    // class. There are lots of cases where this won't really work,
    // but for the case of GenericMeta setting a bunch of properties
    // on the class we should be fine.
    if (metaclass != &PyType_Type) {
        assert(bases && "non-type metaclasses require non-NULL bases");

        PyObject *ns = PyDict_New();
        if (!ns)
            goto error;

        dummy_class = (PyTypeObject *)PyObject_CallFunctionObjArgs(
            (PyObject *)metaclass, name, bases, ns, NULL);
        Py_DECREF(ns);
        if (!dummy_class)
            goto error;

        Py_DECREF(bases);
        bases = dummy_class->tp_bases;
        Py_INCREF(bases);
    }

    // Allocate the type and then copy the main stuff in.
    t = (PyHeapTypeObject*)PyType_GenericAlloc(&PyType_Type, 0);
    if (!t)
        goto error;
    memcpy((char *)t + sizeof(PyVarObject),
           (char *)template_ + sizeof(PyVarObject),
           sizeof(PyTypeObject) - sizeof(PyVarObject));

    if (bases != orig_bases) {
        if (PyObject_SetAttrString((PyObject *)t, "__orig_bases__", orig_bases) < 0)
            goto error;
    }

    // Having tp_base set is I think required for stuff to get
    // inherited in PyType_Ready, which we needed for subclassing
    // BaseException. XXX: Taking the first element is wrong I think though.
    if (bases) {
        t->ht_type.tp_base = (PyTypeObject *)PyTuple_GET_ITEM(bases, 0);
        Py_INCREF((PyObject *)t->ht_type.tp_base);
    }

    t->ht_name = name;
    Py_INCREF(name);
    t->ht_qualname = name;
    t->ht_type.tp_bases = bases;
    // references stolen so NULL these out
    bases = name = NULL;

    if (PyType_Ready((PyTypeObject *)t) < 0)
        goto error;

    assert(t->ht_type.tp_base != NULL);

    // XXX: This is a terrible hack to work around a cpython check on
    // the mro. It was needed for mypy.stats. I need to investigate
    // what is actually going on here.
    Py_INCREF(metaclass);
    Py_TYPE(t) = metaclass;

    if (dummy_class) {
        if (PyDict_Merge(t->ht_type.tp_dict, dummy_class->tp_dict, 0) != 0)
            goto error;
        // This is the *really* tasteless bit. GenericMeta's __new__
        // in certain versions of typing sets _gorg to point back to
        // the class. We need to override it to keep it from pointing
        // to the proxy.
        if (PyDict_SetItemString(t->ht_type.tp_dict, "_gorg", (PyObject *)t) < 0)
            goto error;
    }

    // Reject anything that would give us a nontrivial __slots__,
    // because the layout will conflict
    slots = PyObject_GetAttrString((PyObject *)t, "__slots__");
    if (slots) {
        // don't fail on an empty __slots__
        int is_true = PyObject_IsTrue(slots);
        Py_DECREF(slots);
        if (is_true > 0)
            PyErr_SetString(PyExc_TypeError, "mypyc classes can't have __slots__");
        if (is_true != 0)
            goto error;
    } else {
        PyErr_Clear();
    }

    if (PyObject_SetAttrString((PyObject *)t, "__module__", modname) < 0)
        goto error;

    if (init_subclass((PyTypeObject *)t, NULL))
        goto error;

    Py_XDECREF(dummy_class);

    return (PyObject *)t;

error:
    Py_XDECREF(t);
    Py_XDECREF(bases);
    Py_XDECREF(dummy_class);
    Py_XDECREF(name);
    return NULL;
}

// Get attribute value using vtable (may return an undefined value)
#define CPY_GET_ATTR(obj, type, vtable_index, object_type, attr_type)    \
    ((attr_type (*)(object_type *))((object_type *)obj)->vtable[vtable_index])((object_type *)obj)

#define CPY_GET_ATTR_TRAIT(obj, trait, vtable_index, object_type, attr_type)   \
    ((attr_type (*)(object_type *))(CPy_FindTraitVtable(trait, ((object_type *)obj)->vtable))[vtable_index])((object_type *)obj)

// Set attribute value using vtable
#define CPY_SET_ATTR(obj, type, vtable_index, value, object_type, attr_type) \
    ((bool (*)(object_type *, attr_type))((object_type *)obj)->vtable[vtable_index])( \
        (object_type *)obj, value)

#define CPY_SET_ATTR_TRAIT(obj, trait, vtable_index, value, object_type, attr_type) \
    ((bool (*)(object_type *, attr_type))(CPy_FindTraitVtable(trait, ((object_type *)obj)->vtable))[vtable_index])( \
        (object_type *)obj, value)

#define CPY_GET_METHOD(obj, type, vtable_index, object_type, method_type) \
    ((method_type)(((object_type *)obj)->vtable[vtable_index]))

#define CPY_GET_METHOD_TRAIT(obj, trait, vtable_index, object_type, method_type) \
    ((method_type)(CPy_FindTraitVtable(trait, ((object_type *)obj)->vtable)[vtable_index]))


static void CPyError_OutOfMemory(void) {
    fprintf(stderr, "fatal: out of memory\n");
    fflush(stderr);
    abort();
}

static inline int CPyTagged_CheckLong(CPyTagged x) {
    return x & CPY_INT_TAG;
}

static inline int CPyTagged_CheckShort(CPyTagged x) {
    return !CPyTagged_CheckLong(x);
}

static inline CPyTagged CPyTagged_ShortFromInt(int x) {
    return x << 1;
}

static inline CPyTagged CPyTagged_ShortFromLongLong(long long x) {
    return x << 1;
}

static inline long long CPyTagged_ShortAsLongLong(CPyTagged x) {
    // NOTE: Assume that we sign extend.
    return (CPySignedInt)x >> 1;
}

static inline PyObject *CPyTagged_LongAsObject(CPyTagged x) {
    // NOTE: Assume target is not a short int.
    return (PyObject *)(x & ~CPY_INT_TAG);
}

static inline bool CPyTagged_LongLongTooBig(long long value) {
    // Micro-optimized where the common case where long long is small
    // enough.
    return (unsigned long long)value >= (1LL << 62)
        && (value >= 0 || value < -(1LL << 62));
}

static CPyTagged CPyTagged_FromLongLong(long long value) {
    // We use a Python object if the value shifted left by 1 is too
    // large for long long.
    if (CPyTagged_LongLongTooBig(value)) {
        PyObject *object = PyLong_FromLongLong(value);
        return ((CPyTagged)object) | CPY_INT_TAG;
    } else {
        return value << 1;
    }
}

static CPyTagged CPyTagged_FromObject(PyObject *object) {
    int overflow;
    // TODO: This may call __int__ and raise exceptions.
    PY_LONG_LONG value = PyLong_AsLongLongAndOverflow(object, &overflow);
    // We use a Python object if the value shifted left by 1 is too
    // large for long long.
    if (overflow != 0 || CPyTagged_LongLongTooBig(value)) {
        Py_INCREF(object);
        return ((CPyTagged)object) | CPY_INT_TAG;
    } else {
        return value << 1;
    }
}

static CPyTagged CPyTagged_StealFromObject(PyObject *object) {
    int overflow;
    // TODO: This may call __int__ and raise exceptions.
    PY_LONG_LONG value = PyLong_AsLongLongAndOverflow(object, &overflow);
    // We use a Python object if the value shifted left by 1 is too
    // large for long long.
    if (overflow != 0 || CPyTagged_LongLongTooBig(value)) {
        return ((CPyTagged)object) | CPY_INT_TAG;
    } else {
        Py_DECREF(object);
        return value << 1;
    }
}

static CPyTagged CPyTagged_BorrowFromObject(PyObject *object) {
    int overflow;
    // TODO: This may call __int__ and raise exceptions.
    PY_LONG_LONG value = PyLong_AsLongLongAndOverflow(object, &overflow);
    // We use a Python object if the value shifted left by 1 is too
    // large for long long.  The latter check is micro-optimized where
    // the common case where long long is small enough.
    if (overflow != 0 || (((unsigned long long)value >= (1LL << 62)) &&
                          (value >= 0 || value < -(1LL << 62)))) {
        return ((CPyTagged)object) | CPY_INT_TAG;
    } else {
        return value << 1;
    }
}

static PyObject *CPyTagged_AsObject(CPyTagged x) {
    PyObject *value;
    if (CPyTagged_CheckLong(x)) {
        value = CPyTagged_LongAsObject(x);
        Py_INCREF(value);
    } else {
        value = PyLong_FromLongLong(CPyTagged_ShortAsLongLong(x));
        if (value == NULL) {
            CPyError_OutOfMemory();
        }
    }
    return value;
}

static PyObject *CPyTagged_StealAsObject(CPyTagged x) {
    PyObject *value;
    if (CPyTagged_CheckLong(x)) {
        value = CPyTagged_LongAsObject(x);
    } else {
        value = PyLong_FromLongLong(CPyTagged_ShortAsLongLong(x));
        if (value == NULL) {
            CPyError_OutOfMemory();
        }
    }
    return value;
}

static long long CPyTagged_AsLongLong(CPyTagged x) {
    if (CPyTagged_CheckShort(x)) {
        return CPyTagged_ShortAsLongLong(x);
    } else {
        long long result = PyLong_AsLongLong(CPyTagged_LongAsObject(x));
        if (PyErr_Occurred()) {
            return -1;
        }
        return result;
    }
}

static inline void CPyTagged_IncRef(CPyTagged x) {
    if (CPyTagged_CheckLong(x)) {
        Py_INCREF(CPyTagged_LongAsObject(x));
    }
}

static inline void CPyTagged_DecRef(CPyTagged x) {
    if (CPyTagged_CheckLong(x)) {
        Py_DECREF(CPyTagged_LongAsObject(x));
    }
}

static inline bool CPyTagged_IsAddOverflow(CPyTagged sum, CPyTagged left, CPyTagged right) {
    // This check was copied from some of my old code I believe that it works :-)
    return (long long)(sum ^ left) < 0 && (long long)(sum ^ right) < 0;
}

static CPyTagged CPyTagged_Negate(CPyTagged num) {
    if (CPyTagged_CheckShort(num) && num != (CPyTagged) (1LL << 63)) {
        // The only possibility of an overflow error happening when negating a short is if we
        // attempt to negate the most negative number.
        return -num;
    }
    PyObject *num_obj = CPyTagged_AsObject(num);
    PyObject *result = PyNumber_Negative(num_obj);
    if (result == NULL) {
        CPyError_OutOfMemory();
    }
    Py_DECREF(num_obj);
    return CPyTagged_StealFromObject(result);
}

static CPyTagged CPyTagged_Add(CPyTagged left, CPyTagged right) {
    // TODO: Use clang/gcc extension __builtin_saddll_overflow instead.
    if (CPyTagged_CheckShort(left) && CPyTagged_CheckShort(right)) {
        CPyTagged sum = left + right;
        if (!CPyTagged_IsAddOverflow(sum, left, right)) {
            return sum;
        }
    }
    PyObject *left_obj = CPyTagged_AsObject(left);
    PyObject *right_obj = CPyTagged_AsObject(right);
    PyObject *result = PyNumber_Add(left_obj, right_obj);
    if (result == NULL) {
        CPyError_OutOfMemory();
    }
    Py_DECREF(left_obj);
    Py_DECREF(right_obj);
    return CPyTagged_StealFromObject(result);
}

static inline bool CPyTagged_IsSubtractOverflow(CPyTagged diff, CPyTagged left, CPyTagged right) {
    // This check was copied from some of my old code I believe that it works :-)
    return (long long)(diff ^ left) < 0 && (long long)(diff ^ right) >= 0;
}

static CPyTagged CPyTagged_Subtract(CPyTagged left, CPyTagged right) {
    // TODO: Use clang/gcc extension __builtin_saddll_overflow instead.
    if (CPyTagged_CheckShort(left) && CPyTagged_CheckShort(right)) {
        CPyTagged diff = left - right;
        if (!CPyTagged_IsSubtractOverflow(diff, left, right)) {
            return diff;
        }
    }
    PyObject *left_obj = CPyTagged_AsObject(left);
    PyObject *right_obj = CPyTagged_AsObject(right);
    PyObject *result = PyNumber_Subtract(left_obj, right_obj);
    if (result == NULL) {
        CPyError_OutOfMemory();
    }
    Py_DECREF(left_obj);
    Py_DECREF(right_obj);
    return CPyTagged_StealFromObject(result);
}

static inline bool CPyTagged_IsMultiplyOverflow(CPyTagged left, CPyTagged right) {
    // This is conservative -- return false only in a small number of all non-overflow cases
    return left >= (1U << 31) || right >= (1U << 31);
}

static CPyTagged CPyTagged_Multiply(CPyTagged left, CPyTagged right) {
    // TODO: Consider using some clang/gcc extension
    if (CPyTagged_CheckShort(left) && CPyTagged_CheckShort(right)) {
        if (!CPyTagged_IsMultiplyOverflow(left, right)) {
            return left * CPyTagged_ShortAsLongLong(right);
        }
    }
    PyObject *left_obj = CPyTagged_AsObject(left);
    PyObject *right_obj = CPyTagged_AsObject(right);
    PyObject *result = PyNumber_Multiply(left_obj, right_obj);
    if (result == NULL) {
        CPyError_OutOfMemory();
    }
    Py_DECREF(left_obj);
    Py_DECREF(right_obj);
    return CPyTagged_StealFromObject(result);
}

static inline bool CPyTagged_MaybeFloorDivideOverflow(CPyTagged left, CPyTagged right) {
    return right == -0x8000000000000000ULL || left == -0x8000000000000000ULL;
}

static CPyTagged CPyTagged_FloorDivide(CPyTagged left, CPyTagged right) {
    if (CPyTagged_CheckShort(left) && CPyTagged_CheckShort(right)
        && !CPyTagged_MaybeFloorDivideOverflow(left, right)) {
        if (right == 0)
            abort();
        CPySignedInt result = ((CPySignedInt)left / CPyTagged_ShortAsLongLong(right)) & ~1;
        if (((CPySignedInt)left < 0) != (((CPySignedInt)right) < 0)) {
            if (result / 2 * right != left) {
                // Round down
                result -= 2;
            }
        }
        return result;
    }
    PyObject *left_obj = CPyTagged_AsObject(left);
    PyObject *right_obj = CPyTagged_AsObject(right);
    PyObject *result = PyNumber_FloorDivide(left_obj, right_obj);
    if (result == NULL) {
        CPyError_OutOfMemory();
    }
    Py_DECREF(left_obj);
    Py_DECREF(right_obj);
    return CPyTagged_StealFromObject(result);
}

static inline bool CPyTagged_MaybeRemainderOverflow(CPyTagged left, CPyTagged right) {
    return right == -0x8000000000000000ULL || left == -0x8000000000000000ULL;
}

static CPyTagged CPyTagged_Remainder(CPyTagged left, CPyTagged right) {
    if (CPyTagged_CheckShort(left) && CPyTagged_CheckShort(right)
        && !CPyTagged_MaybeRemainderOverflow(left, right)) {
        CPySignedInt result = (CPySignedInt)left % (CPySignedInt)right;
        if (((CPySignedInt)right < 0) != ((CPySignedInt)left < 0) && result != 0) {
            result += right;
        }
        return result;
    }
    PyObject *left_obj = CPyTagged_AsObject(left);
    PyObject *right_obj = CPyTagged_AsObject(right);
    PyObject *result = PyNumber_Remainder(left_obj, right_obj);
    if (result == NULL) {
        CPyError_OutOfMemory();
    }
    Py_DECREF(left_obj);
    Py_DECREF(right_obj);
    return CPyTagged_StealFromObject(result);
}

static bool CPyTagged_IsEq_(CPyTagged left, CPyTagged right) {
    if (CPyTagged_CheckShort(right)) {
        return false;
    } else {
        int result = PyObject_RichCompareBool(CPyTagged_LongAsObject(left),
                                              CPyTagged_LongAsObject(right), Py_EQ);
        if (result == -1) {
            CPyError_OutOfMemory();
        }
        return result;
    }
}

static inline bool CPyTagged_IsEq(CPyTagged left, CPyTagged right) {
    if (CPyTagged_CheckShort(left)) {
        return left == right;
    } else {
        return CPyTagged_IsEq_(left, right);
    }
}

static inline bool CPyTagged_IsNe(CPyTagged left, CPyTagged right) {
    if (CPyTagged_CheckShort(left)) {
        return left != right;
    } else {
        return !CPyTagged_IsEq_(left, right);
    }
}

static bool CPyTagged_IsLt_(CPyTagged left, CPyTagged right) {
    PyObject *left_obj = CPyTagged_AsObject(left);
    PyObject *right_obj = CPyTagged_AsObject(right);
    int result = PyObject_RichCompareBool(left_obj, right_obj, Py_LT);
    Py_DECREF(left_obj);
    Py_DECREF(right_obj);
    if (result == -1) {
        CPyError_OutOfMemory();
    }
    return result;
}

static inline bool CPyTagged_IsLt(CPyTagged left, CPyTagged right) {
    if (CPyTagged_CheckShort(left) && CPyTagged_CheckShort(right)) {
        return (CPySignedInt)left < (CPySignedInt)right;
    } else {
        return CPyTagged_IsLt_(left, right);
    }
}

static inline bool CPyTagged_IsGe(CPyTagged left, CPyTagged right) {
    if (CPyTagged_CheckShort(left) && CPyTagged_CheckShort(right)) {
        return (CPySignedInt)left >= (CPySignedInt)right;
    } else {
        return !CPyTagged_IsLt_(left, right);
    }
}

static inline bool CPyTagged_IsGt(CPyTagged left, CPyTagged right) {
    if (CPyTagged_CheckShort(left) && CPyTagged_CheckShort(right)) {
        return (CPySignedInt)left > (CPySignedInt)right;
    } else {
        return CPyTagged_IsLt_(right, left);
    }
}

static inline bool CPyTagged_IsLe(CPyTagged left, CPyTagged right) {
    if (CPyTagged_CheckShort(left) && CPyTagged_CheckShort(right)) {
        return (CPySignedInt)left <= (CPySignedInt)right;
    } else {
        return !CPyTagged_IsLt_(right, left);
    }
}

static PyObject *CPyList_GetItem(PyObject *list, CPyTagged index) {
    if (CPyTagged_CheckShort(index)) {
        long long n = CPyTagged_ShortAsLongLong(index);
        Py_ssize_t size = PyList_GET_SIZE(list);
        if (n >= 0) {
            if (n >= size) {
                PyErr_SetString(PyExc_IndexError, "list index out of range");
                return NULL;
            }
        } else {
            n += size;
            if (n < 0) {
                PyErr_SetString(PyExc_IndexError, "list index out of range");
                return NULL;
            }
        }
        PyObject *result = PyList_GET_ITEM(list, n);
        Py_INCREF(result);
        return result;
    } else {
        PyErr_SetString(PyExc_IndexError, "list index out of range");
        return NULL;
    }
}

static bool CPyList_SetItem(PyObject *list, CPyTagged index, PyObject *value) {
    if (CPyTagged_CheckShort(index)) {
        long long n = CPyTagged_ShortAsLongLong(index);
        Py_ssize_t size = PyList_GET_SIZE(list);
        if (n >= 0) {
            if (n >= size) {
                PyErr_SetString(PyExc_IndexError, "list assignment index out of range");
                return false;
            }
        } else {
            n += size;
            if (n < 0) {
                PyErr_SetString(PyExc_IndexError, "list assignment index out of range");
                return false;
            }
        }
        // N.B: Steals reference
        PyList_SET_ITEM(list, n, value);
        return true;
    } else {
        PyErr_SetString(PyExc_IndexError, "list assignment index out of range");
        return false;
    }
}

static bool CPySet_Remove(PyObject *set, PyObject *key) {
    int success = PySet_Discard(set, key);
    if (success == 1) {
        return true;
    }
    if (success == 0) {
        _PyErr_SetKeyError(key);
    }
    return false;
}

static PyObject *CPySequenceTuple_GetItem(PyObject *tuple, CPyTagged index) {
    if (CPyTagged_CheckShort(index)) {
        long long n = CPyTagged_ShortAsLongLong(index);
        Py_ssize_t size = PyTuple_GET_SIZE(tuple);
        if (n >= 0) {
            if (n >= size) {
                PyErr_SetString(PyExc_IndexError, "tuple index out of range");
                return NULL;
            }
        } else {
            n += size;
            if (n < 0) {
                PyErr_SetString(PyExc_IndexError, "tuple index out of range");
                return NULL;
            }
        }
        PyObject *result = PyTuple_GET_ITEM(tuple, n);
        Py_INCREF(result);
        return result;
    } else {
        PyErr_SetString(PyExc_IndexError, "tuple index out of range");
        return NULL;
    }
}

static CPyTagged CPyObject_Hash(PyObject *o) {
    Py_hash_t h = PyObject_Hash(o);
    if (h == -1) {
        return CPY_INT_TAG;
    } else {
        // This is tragically annoying. The range of hash values in
        // 64-bit python covers 64-bits, and our short integers only
        // cover 63. This means that half the time we are boxing the
        // result for basically no good reason. To add insult to
        // injury it is probably about to be immediately unboxed by a
        // tp_hash wrapper.
        return CPyTagged_FromLongLong(h);
    }
}

static inline int CPy_ObjectToStatus(PyObject *obj) {
    if (obj) {
        Py_DECREF(obj);
        return 0;
    } else {
        return -1;
    }
}

// dict subclasses like defaultdict override things in interesting
// ways, so we don't want to just directly use the dict methods. Not
// sure if it is actually worth doing all this stuff, but it saves
// some indirections.
static PyObject *CPyDict_GetItem(PyObject *dict, PyObject *key) {
    if (PyDict_CheckExact(dict)) {
        PyObject *res = PyDict_GetItemWithError(dict, key);
        if (!res) {
            PyErr_SetObject(PyExc_KeyError, key);
        } else {
            Py_INCREF(res);
        }
        return res;
    } else {
        return PyObject_GetItem(dict, key);
    }
}

static int CPyDict_SetItem(PyObject *dict, PyObject *key, PyObject *value) {
    if (PyDict_CheckExact(dict)) {
        return PyDict_SetItem(dict, key, value);
    } else {
        return PyObject_SetItem(dict, key, value);
    }
}

static int CPyDict_UpdateGeneral(PyObject *dict, PyObject *stuff) {
    static PyObject *update_str = NULL;
    if (!update_str) {
        update_str = PyUnicode_FromString("update");
        if (!update_str) {
            return -1;
        }
    }
    PyObject *res = PyObject_CallMethodObjArgs(dict, update_str, stuff, NULL);
    return CPy_ObjectToStatus(res);
}

static int CPyDict_Update(PyObject *dict, PyObject *stuff) {
    if (PyDict_CheckExact(dict)) {
        return PyDict_Update(dict, stuff);
    } else {
        return CPyDict_UpdateGeneral(dict, stuff);
    }
}

static int CPyDict_UpdateFromSeq(PyObject *dict, PyObject *stuff) {
    if (PyDict_CheckExact(dict)) {
        // Argh this sucks
        if (PyDict_Check(stuff)) {
            return PyDict_Update(dict, stuff);
        } else {
            return PyDict_MergeFromSeq2(dict, stuff, 1);
        }
    } else {
        return CPyDict_UpdateGeneral(dict, stuff);
    }
}

static PyCodeObject *CPy_CreateCodeObject(const char *filename, const char *funcname, int line) {
    PyObject *filename_obj = PyUnicode_FromString(filename);
    PyObject *funcname_obj = PyUnicode_FromString(funcname);
    PyObject *empty_bytes = PyBytes_FromStringAndSize("", 0);
    PyObject *empty_tuple = PyTuple_New(0);
    PyCodeObject *code_obj = NULL;
    if (filename_obj == NULL || funcname_obj == NULL || empty_bytes == NULL
        || empty_tuple == NULL) {
        goto Error;
    }
    code_obj = PyCode_New(0, 0, 0, 0, 0,
                          empty_bytes,
                          empty_tuple,
                          empty_tuple,
                          empty_tuple,
                          empty_tuple,
                          empty_tuple,
                          filename_obj,
                          funcname_obj,
                          line,
                          empty_bytes);
  Error:
    Py_XDECREF(empty_bytes);
    Py_XDECREF(empty_tuple);
    Py_XDECREF(filename_obj);
    Py_XDECREF(funcname_obj);
    return code_obj;
}

static void CPy_AddTraceback(const char *filename, const char *funcname, int line,
                             PyObject *globals) {
    PyCodeObject *code_obj = CPy_CreateCodeObject(filename, funcname, line);
    if (code_obj == NULL) {
        return;
    }
    PyThreadState *thread_state = PyThreadState_GET();
    PyFrameObject *frame_obj = PyFrame_New(thread_state, code_obj, globals, 0);
    if (frame_obj == NULL) {
        Py_DECREF(code_obj);
        return;
    }
    frame_obj->f_lineno = line;
    PyTraceBack_Here(frame_obj);
    Py_DECREF(code_obj);
    Py_DECREF(frame_obj);
}

// mypyc is not very good at dealing with refcount management of
// pointers that might be NULL. As a workaround for this, the
// exception APIs that might want to return NULL pointers instead
// return properly refcounted pointers to this dummy object.
struct ExcDummyStruct { PyObject_HEAD };
static struct ExcDummyStruct _CPy_ExcDummyStruct = { PyObject_HEAD_INIT(&PyBaseObject_Type) };
static PyObject *_CPy_ExcDummy = (PyObject *)&_CPy_ExcDummyStruct;

static inline void _CPy_ToDummy(PyObject **p) {
    if (*p == NULL) {
        Py_INCREF(_CPy_ExcDummy);
        *p = _CPy_ExcDummy;
    }
}

static inline PyObject *_CPy_FromDummy(PyObject *p) {
    if (p == _CPy_ExcDummy) return NULL;
    Py_INCREF(p);
    return p;
}

static void CPy_CatchError(PyObject **p_type, PyObject **p_value, PyObject **p_traceback) {
    // We need to return the existing sys.exc_info() information, so
    // that it can be restored when we finish handling the error we
    // are catching now. Grab that triple and convert NULL values to
    // the ExcDummy object in order to simplify refcount handling in
    // generated code.
    PyErr_GetExcInfo(p_type, p_value, p_traceback);
    _CPy_ToDummy(p_type);
    _CPy_ToDummy(p_value);
    _CPy_ToDummy(p_traceback);

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
}

static void CPy_RestoreExcInfo(PyObject *type, PyObject *value, PyObject *traceback) {
    // PyErr_SetExcInfo steals the references to the values passed to it.
    PyErr_SetExcInfo(_CPy_FromDummy(type), _CPy_FromDummy(value), _CPy_FromDummy(traceback));
}

static void CPy_Raise(PyObject *exc) {
    if (PyObject_IsInstance(exc, (PyObject *)&PyType_Type)) {
        PyObject *obj = PyObject_CallFunctionObjArgs(exc, NULL);
        if (!obj)
            return;
        PyErr_SetObject(exc, obj);
        Py_DECREF(obj);
    } else {
        PyErr_SetObject((PyObject *)Py_TYPE(exc), exc);
    }
}

static void CPy_Reraise(void) {
    PyObject *p_type, *p_value, *p_traceback;
    PyErr_GetExcInfo(&p_type, &p_value, &p_traceback);
    PyErr_Restore(p_type, p_value, p_traceback);
}

static void CPyErr_SetObjectAndTraceback(PyObject *type, PyObject *value, PyObject *traceback) {
    // Set the value and traceback of an error. Because calling
    // PyErr_Restore takes away a reference to each object passed in
    // as an argument, we manually increase the reference count of
    // each argument before calling it.
    Py_INCREF(type);
    Py_INCREF(value);
    Py_INCREF(traceback);
    PyErr_Restore(type, value, traceback);
}

// We want to avoid the public PyErr_GetExcInfo API for these because
// it requires a bunch of spurious refcount traffic on the parts of
// the triple we don't care about. Unfortunately the layout of the
// data structure changed in 3.7 so we need to handle that.
#if PY_MAJOR_VERSION >= 3 && PY_MINOR_VERSION >= 7
#define CPy_ExcState() PyThreadState_GET()->exc_info
#else
#define CPy_ExcState() PyThreadState_GET()
#endif

static bool CPy_ExceptionMatches(PyObject *type) {
    return PyErr_GivenExceptionMatches(CPy_ExcState()->exc_type, type);
}

static PyObject *CPy_GetExcValue(void) {
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

static void CPy_GetExcInfo(PyObject **p_type, PyObject **p_value, PyObject **p_traceback) {
    PyErr_GetExcInfo(p_type, p_value, p_traceback);
    _CPy_ToNone(p_type);
    _CPy_ToNone(p_value);
    _CPy_ToNone(p_traceback);
}

#ifdef __cplusplus
}
#endif

#endif // CPY_CPY_H
