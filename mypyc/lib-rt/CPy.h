#ifndef CPY_CPY_H
#define CPY_CPY_H

#include <stdbool.h>
#include <Python.h>
#include <frameobject.h>
#include <structmember.h>
#include <assert.h>
#include "pythonsupport.h"
#include "mypyc_util.h"

#ifdef __cplusplus
extern "C" {
#endif
#if 0
} // why isn't emacs smart enough to not indent this
#endif

/* We use intentionally non-inlined decrefs since it pretty
 * substantially speeds up compile time while only causing a ~1%
 * performance degradation. We have our own copies both to avoid the
 * null check in Py_DecRef and to avoid making an indirect PIC
 * call. */
CPy_NOINLINE
static void CPy_DecRef(PyObject *p) {
    CPy_DECREF(p);
}

CPy_NOINLINE
static void CPy_XDecRef(PyObject *p) {
    CPy_XDECREF(p);
}

// Naming conventions:
//
// Tagged: tagged int
// Long: tagged long int (pointer)
// Short: tagged short int (unboxed)
// Ssize_t: A Py_ssize_t, which ought to be the same width as pointers
// Object: CPython object (PyObject *)

static void CPyDebug_Print(const char *msg) {
    printf("%s\n", msg);
    fflush(stdout);
}

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

static bool _CPy_IsSafeMetaClass(PyTypeObject *metaclass) {
    // mypyc classes can't work with metaclasses in
    // general. Through some various nasty hacks we *do*
    // manage to work with TypingMeta and its friends.
    if (metaclass == &PyType_Type)
        return true;
    PyObject *module = PyObject_GetAttrString((PyObject *)metaclass, "__module__");
    if (!module) {
        PyErr_Clear();
        return false;
    }

    bool matches = false;
    if (PyUnicode_CompareWithASCIIString(module, "typing") == 0 &&
            (strcmp(metaclass->tp_name, "TypingMeta") == 0
             || strcmp(metaclass->tp_name, "GenericMeta") == 0)) {
        matches = true;
    } else if (PyUnicode_CompareWithASCIIString(module, "abc") == 0 &&
               strcmp(metaclass->tp_name, "ABCMeta") == 0) {
        matches = true;
    }
    Py_DECREF(module);
    return matches;
}

// Create a heap type based on a template non-heap type.
// This is super hacky and maybe we should suck it up and use PyType_FromSpec instead.
// We allow bases to be NULL to represent just inheriting from object.
// We don't support NULL bases and a non-type metaclass.
static PyObject *CPyType_FromTemplate(PyTypeObject *template_,
                                      PyObject *orig_bases,
                                      PyObject *modname) {
    PyHeapTypeObject *t = NULL;
    PyTypeObject *dummy_class = NULL;
    PyObject *name = NULL;
    PyObject *bases = NULL;
    PyObject *slots;

    // If the type of the class (the metaclass) is NULL, we default it
    // to being type.  (This allows us to avoid needing to initialize
    // it explicitly on windows.)
    if (!Py_TYPE(template_)) {
        Py_TYPE(template_) = &PyType_Type;
    }
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

        if (!_CPy_IsSafeMetaClass(metaclass)) {
            PyErr_SetString(PyExc_TypeError, "mypyc classes can't have a metaclass");
            goto error;
        }
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

        if (bases != orig_bases) {
            if (PyDict_SetItemString(ns, "__orig_bases__", orig_bases) < 0)
                goto error;
        }

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

static inline Py_ssize_t CPyTagged_ShortAsSsize_t(CPyTagged x) {
    // NOTE: Assume that we sign extend.
    return (Py_ssize_t)x >> 1;
}

static inline PyObject *CPyTagged_LongAsObject(CPyTagged x) {
    // NOTE: Assume target is not a short int.
    return (PyObject *)(x & ~CPY_INT_TAG);
}

static inline bool CPyTagged_TooBig(Py_ssize_t value) {
    // Micro-optimized for the common case where it fits.
    return (size_t)value > CPY_TAGGED_MAX
        && (value >= 0 || value < CPY_TAGGED_MIN);
}

static CPyTagged CPyTagged_FromSsize_t(Py_ssize_t value) {
    // We use a Python object if the value shifted left by 1 is too
    // large for Py_ssize_t
    if (CPyTagged_TooBig(value)) {
        PyObject *object = PyLong_FromSsize_t(value);
        return ((CPyTagged)object) | CPY_INT_TAG;
    } else {
        return value << 1;
    }
}

static CPyTagged CPyTagged_FromObject(PyObject *object) {
    int overflow;
    // The overflow check knows about CPyTagged's width
    Py_ssize_t value = CPyLong_AsSsize_tAndOverflow(object, &overflow);
    if (overflow != 0) {
        Py_INCREF(object);
        return ((CPyTagged)object) | CPY_INT_TAG;
    } else {
        return value << 1;
    }
}

static CPyTagged CPyTagged_StealFromObject(PyObject *object) {
    int overflow;
    // The overflow check knows about CPyTagged's width
    Py_ssize_t value = CPyLong_AsSsize_tAndOverflow(object, &overflow);
    if (overflow != 0) {
        return ((CPyTagged)object) | CPY_INT_TAG;
    } else {
        Py_DECREF(object);
        return value << 1;
    }
}

static CPyTagged CPyTagged_BorrowFromObject(PyObject *object) {
    int overflow;
    // The overflow check knows about CPyTagged's width
    Py_ssize_t value = CPyLong_AsSsize_tAndOverflow(object, &overflow);
    if (overflow != 0) {
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
        value = PyLong_FromSsize_t(CPyTagged_ShortAsSsize_t(x));
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
        value = PyLong_FromSsize_t(CPyTagged_ShortAsSsize_t(x));
        if (value == NULL) {
            CPyError_OutOfMemory();
        }
    }
    return value;
}

static Py_ssize_t CPyTagged_AsSsize_t(CPyTagged x) {
    if (CPyTagged_CheckShort(x)) {
        return CPyTagged_ShortAsSsize_t(x);
    } else {
        return PyLong_AsSsize_t(CPyTagged_LongAsObject(x));
    }
}

CPy_NOINLINE
static void CPyTagged_IncRef(CPyTagged x) {
    if (CPyTagged_CheckLong(x)) {
        Py_INCREF(CPyTagged_LongAsObject(x));
    }
}

CPy_NOINLINE
static void CPyTagged_DecRef(CPyTagged x) {
    if (CPyTagged_CheckLong(x)) {
        Py_DECREF(CPyTagged_LongAsObject(x));
    }
}

CPy_NOINLINE
static void CPyTagged_XDecRef(CPyTagged x) {
    if (CPyTagged_CheckLong(x)) {
        Py_XDECREF(CPyTagged_LongAsObject(x));
    }
}

static inline bool CPyTagged_IsAddOverflow(CPyTagged sum, CPyTagged left, CPyTagged right) {
    // This check was copied from some of my old code I believe that it works :-)
    return (Py_ssize_t)(sum ^ left) < 0 && (Py_ssize_t)(sum ^ right) < 0;
}

static CPyTagged CPyTagged_Negate(CPyTagged num) {
    if (CPyTagged_CheckShort(num)
            && num != (CPyTagged) ((Py_ssize_t)1 << (CPY_INT_BITS - 1))) {
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
    return (Py_ssize_t)(diff ^ left) < 0 && (Py_ssize_t)(diff ^ right) >= 0;
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
    return left >= (1U << (CPY_INT_BITS/2 - 1)) || right >= (1U << (CPY_INT_BITS/2 - 1));
}

static CPyTagged CPyTagged_Multiply(CPyTagged left, CPyTagged right) {
    // TODO: Consider using some clang/gcc extension
    if (CPyTagged_CheckShort(left) && CPyTagged_CheckShort(right)) {
        if (!CPyTagged_IsMultiplyOverflow(left, right)) {
            return left * CPyTagged_ShortAsSsize_t(right);
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

static inline bool CPyTagged_MaybeFloorDivideFault(CPyTagged left, CPyTagged right) {
    return right == 0 || left == -((size_t)1 << (CPY_INT_BITS-1));
}

static CPyTagged CPyTagged_FloorDivide(CPyTagged left, CPyTagged right) {
    if (CPyTagged_CheckShort(left) && CPyTagged_CheckShort(right)
        && !CPyTagged_MaybeFloorDivideFault(left, right)) {
        Py_ssize_t result = ((Py_ssize_t)left / CPyTagged_ShortAsSsize_t(right)) & ~1;
        if (((Py_ssize_t)left < 0) != (((Py_ssize_t)right) < 0)) {
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
    Py_DECREF(left_obj);
    Py_DECREF(right_obj);
    // Handle exceptions honestly because it could be ZeroDivisionError
    if (result == NULL) {
        return CPY_INT_TAG;
    } else {
        return CPyTagged_StealFromObject(result);
    }
}

static inline bool CPyTagged_MaybeRemainderFault(CPyTagged left, CPyTagged right) {
    // Division/modulus can fault when dividing INT_MIN by -1, but we
    // do our mods on still-tagged integers with the low-bit clear, so
    // -1 is actually represented as -2 and can't overflow.
    // Mod by 0 can still fault though.
    return right == 0;
}

static CPyTagged CPyTagged_Remainder(CPyTagged left, CPyTagged right) {
    if (CPyTagged_CheckShort(left) && CPyTagged_CheckShort(right)
        && !CPyTagged_MaybeRemainderFault(left, right)) {
        Py_ssize_t result = (Py_ssize_t)left % (Py_ssize_t)right;
        if (((Py_ssize_t)right < 0) != ((Py_ssize_t)left < 0) && result != 0) {
            result += right;
        }
        return result;
    }
    PyObject *left_obj = CPyTagged_AsObject(left);
    PyObject *right_obj = CPyTagged_AsObject(right);
    PyObject *result = PyNumber_Remainder(left_obj, right_obj);
    Py_DECREF(left_obj);
    Py_DECREF(right_obj);
    // Handle exceptions honestly because it could be ZeroDivisionError
    if (result == NULL) {
        return CPY_INT_TAG;
    } else {
        return CPyTagged_StealFromObject(result);
    }
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
        return (Py_ssize_t)left < (Py_ssize_t)right;
    } else {
        return CPyTagged_IsLt_(left, right);
    }
}

static inline bool CPyTagged_IsGe(CPyTagged left, CPyTagged right) {
    if (CPyTagged_CheckShort(left) && CPyTagged_CheckShort(right)) {
        return (Py_ssize_t)left >= (Py_ssize_t)right;
    } else {
        return !CPyTagged_IsLt_(left, right);
    }
}

static inline bool CPyTagged_IsGt(CPyTagged left, CPyTagged right) {
    if (CPyTagged_CheckShort(left) && CPyTagged_CheckShort(right)) {
        return (Py_ssize_t)left > (Py_ssize_t)right;
    } else {
        return CPyTagged_IsLt_(right, left);
    }
}

static inline bool CPyTagged_IsLe(CPyTagged left, CPyTagged right) {
    if (CPyTagged_CheckShort(left) && CPyTagged_CheckShort(right)) {
        return (Py_ssize_t)left <= (Py_ssize_t)right;
    } else {
        return !CPyTagged_IsLt_(right, left);
    }
}

static CPyTagged CPyTagged_Id(PyObject *o) {
    return CPyTagged_FromSsize_t((Py_ssize_t)o);
}

static PyObject *CPyList_GetItemUnsafe(PyObject *list, CPyTagged index) {
    Py_ssize_t n = CPyTagged_ShortAsSsize_t(index);
    PyObject *result = PyList_GET_ITEM(list, n);
    Py_INCREF(result);
    return result;
}

static PyObject *CPyList_GetItemShort(PyObject *list, CPyTagged index) {
    Py_ssize_t n = CPyTagged_ShortAsSsize_t(index);
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
}

static PyObject *CPyList_GetItem(PyObject *list, CPyTagged index) {
    if (CPyTagged_CheckShort(index)) {
        Py_ssize_t n = CPyTagged_ShortAsSsize_t(index);
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
        Py_ssize_t n = CPyTagged_ShortAsSsize_t(index);
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
        // PyList_SET_ITEM doesn't decref the old element, so we do
        Py_DECREF(PyList_GET_ITEM(list, n));
        // N.B: Steals reference
        PyList_SET_ITEM(list, n, value);
        return true;
    } else {
        PyErr_SetString(PyExc_IndexError, "list assignment index out of range");
        return false;
    }
}

static PyObject *CPyList_PopLast(PyObject *obj)
{
    // I tried a specalized version of pop_impl for just removing the
    // last element and it wasn't any faster in microbenchmarks than
    // the generic one so I ditched it.
    return list_pop_impl((PyListObject *)obj, -1);
}

static PyObject *CPyList_Pop(PyObject *obj, CPyTagged index)
{
    if (CPyTagged_CheckShort(index)) {
        Py_ssize_t n = CPyTagged_ShortAsSsize_t(index);
        return list_pop_impl((PyListObject *)obj, n);
    } else {
        PyErr_SetString(PyExc_IndexError, "pop index out of range");
        return NULL;
    }
}

static CPyTagged CPyList_Count(PyObject *obj, PyObject *value)
{
    return list_count((PyListObject *)obj, value);
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
        Py_ssize_t n = CPyTagged_ShortAsSsize_t(index);
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
        return CPyTagged_FromSsize_t(h);
    }
}

static inline CPyTagged CPyObject_Size(PyObject *obj) {
    Py_ssize_t s = PyObject_Size(obj);
    if (s < 0) {
        return CPY_INT_TAG;
    } else {
        // Technically __len__ could return a really big number, so we
        // should allow this to produce a boxed int. In practice it
        // shouldn't ever if the data structure actually contains all
        // the elements, but...
        return CPyTagged_FromSsize_t(s);
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
            if (!PyErr_Occurred()) {
                PyErr_SetObject(PyExc_KeyError, key);
            }
        } else {
            Py_INCREF(res);
        }
        return res;
    } else {
        return PyObject_GetItem(dict, key);
    }
}

static PyObject *CPyDict_Build(Py_ssize_t size, ...) {
    Py_ssize_t i;

    PyObject *res = _PyDict_NewPresized(size);
    if (res == NULL) {
        return NULL;
    }

    va_list args;
    va_start(args, size);

    for (i = 0; i < size; i++) {
        PyObject *key = va_arg(args, PyObject *);
        PyObject *value = va_arg(args, PyObject *);
        if (PyDict_SetItem(res, key, value)) {
            Py_DECREF(res);
            return NULL;
        }
    }

    va_end(args);
    return res;
}

static PyObject *CPyDict_Get(PyObject *dict, PyObject *key, PyObject *fallback) {
    // We are dodgily assuming that get on a subclass doesn't have
    // different behavior.
    PyObject *res = PyDict_GetItemWithError(dict, key);
    if (!res) {
        if (PyErr_Occurred()) {
            return NULL;
        }
        res = fallback;
    }
    Py_INCREF(res);
    return res;
}

static int CPyDict_SetItem(PyObject *dict, PyObject *key, PyObject *value) {
    if (PyDict_CheckExact(dict)) {
        return PyDict_SetItem(dict, key, value);
    } else {
        return PyObject_SetItem(dict, key, value);
    }
}

static int CPyDict_UpdateGeneral(PyObject *dict, PyObject *stuff) {
    _Py_IDENTIFIER(update);
    PyObject *res = _PyObject_CallMethodIdObjArgs(dict, &PyId_update, stuff, NULL);
    return CPy_ObjectToStatus(res);
}

static int CPyDict_UpdateInDisplay(PyObject *dict, PyObject *stuff) {
    // from https://github.com/python/cpython/blob/55d035113dfb1bd90495c8571758f504ae8d4802/Python/ceval.c#L2710
    int ret = PyDict_Update(dict, stuff);
    if (ret < 0) {
        if (PyErr_ExceptionMatches(PyExc_AttributeError)) {
            PyErr_Format(PyExc_TypeError,
                    "'%.200s' object is not a mapping",
                    stuff->ob_type->tp_name);
        }
    }
    return ret;
}

static int CPyDict_Update(PyObject *dict, PyObject *stuff) {
    if (PyDict_CheckExact(dict)) {
        return PyDict_Update(dict, stuff);
    } else {
        return CPyDict_UpdateGeneral(dict, stuff);
    }
}

static int CPyDict_UpdateFromAny(PyObject *dict, PyObject *stuff) {
    if (PyDict_CheckExact(dict)) {
        // Argh this sucks
        _Py_IDENTIFIER(keys);
        if (PyDict_Check(stuff) || _PyObject_HasAttrId(stuff, &PyId_keys)) {
            return PyDict_Update(dict, stuff);
        } else {
            return PyDict_MergeFromSeq2(dict, stuff, 1);
        }
    } else {
        return CPyDict_UpdateGeneral(dict, stuff);
    }
}

static PyObject *CPyDict_FromAny(PyObject *obj) {
    if (PyDict_Check(obj)) {
        return PyDict_Copy(obj);
    } else {
        int res;
        PyObject *dict = PyDict_New();
        if (!dict) {
            return NULL;
        }
        _Py_IDENTIFIER(keys);
        if (_PyObject_HasAttrId(obj, &PyId_keys)) {
            res = PyDict_Update(dict, obj);
        } else {
            res = PyDict_MergeFromSeq2(dict, obj, 1);
        }
        if (res < 0) {
            Py_DECREF(dict);
            return NULL;
        }
        return dict;
    }
}

static PyObject *CPyStr_Split(PyObject *str, PyObject *sep, CPyTagged max_split)
{
    Py_ssize_t temp_max_split = CPyTagged_AsSsize_t(max_split);
    if (temp_max_split == -1 && PyErr_Occurred()) {
        PyErr_SetString(PyExc_OverflowError, "Python int too large to convert to C ssize_t");
            return NULL;
    }
    return PyUnicode_Split(str, sep, temp_max_split);
}

static PyObject *CPyIter_Next(PyObject *iter)
{
    return (*iter->ob_type->tp_iternext)(iter);
}

static PyObject *CPy_FetchStopIterationValue(void)
{
    PyObject *val = NULL;
    _PyGen_FetchStopIterationValue(&val);
    return val;
}

static PyObject *CPyIter_Send(PyObject *iter, PyObject *val)
{
    // Do a send, or a next if second arg is None.
    // (This behavior is to match the PEP 380 spec for yield from.)
    _Py_IDENTIFIER(send);
    if (val == Py_None) {
        return CPyIter_Next(iter);
    } else {
        return _PyObject_CallMethodIdObjArgs(iter, &PyId_send, val, NULL);
    }
}

static PyObject *CPy_GetCoro(PyObject *obj)
{
    // If the type has an __await__ method, call it,
    // otherwise, fallback to calling __iter__.
    PyAsyncMethods* async_struct = obj->ob_type->tp_as_async;
    if (async_struct != NULL && async_struct->am_await != NULL) {
        return (async_struct->am_await)(obj);
    } else {
        // TODO: We should check that the type is a generator decorated with
        // asyncio.coroutine
        return PyObject_GetIter(obj);
    }
}

static PyObject *CPyObject_GetAttr3(PyObject *v, PyObject *name, PyObject *defl)
{
    PyObject *result = PyObject_GetAttr(v, name);
    if (!result && PyErr_ExceptionMatches(PyExc_AttributeError)) {
        PyErr_Clear();
        Py_INCREF(defl);
        result = defl;
    }
    return result;
}

// mypy lets ints silently coerce to floats, so a mypyc runtime float
// might be an int also
static inline bool CPyFloat_Check(PyObject *o) {
    return PyFloat_Check(o) || PyLong_Check(o);
}

static PyObject *CPyLong_FromFloat(PyObject *o) {
    if (PyLong_Check(o)) {
        CPy_INCREF(o);
        return o;
    } else {
        return PyLong_FromDouble(PyFloat_AS_DOUBLE(o));
    }
}

// Construct a nicely formatted type name based on __module__ and __name__.
static PyObject *CPy_GetTypeName(PyObject *type) {
    PyObject *module = NULL, *name = NULL;
    PyObject *full = NULL;

    module = PyObject_GetAttrString(type, "__module__");
    if (!module || !PyUnicode_Check(module)) {
        goto out;
    }
    name = PyObject_GetAttrString(type, "__qualname__");
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
    if (value == Py_None) {
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
static void CPy_TypeError(const char *expected, PyObject *value) {
    PyObject *out = CPy_FormatTypeName(value);
    if (out) {
        PyErr_Format(PyExc_TypeError, "%s object expected; got %U", expected, out);
        Py_DECREF(out);
    } else {
        PyErr_Format(PyExc_TypeError, "%s object expected; and errored formatting real type!",
                     expected);
    }
}

// These functions are basically exactly PyCode_NewEmpty and
// _PyTraceback_Add which are available in all the versions we support.
// We're continuing to use them because we'll probably optimize them later.
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
    PyCodeObject *code_obj = CPy_CreateCodeObject(filename, funcname, line);
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
    _PyErr_ChainExceptions(exc, val, tb);
}

// mypyc is not very good at dealing with refcount management of
// pointers that might be NULL. As a workaround for this, the
// exception APIs that might want to return NULL pointers instead
// return properly refcounted pointers to this dummy object.
struct ExcDummyStruct { PyObject_HEAD };
extern struct ExcDummyStruct _CPy_ExcDummyStruct;
extern PyObject *_CPy_ExcDummy;

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

void CPy_Init(void);


// A somewhat hairy implementation of specifically most of the error handling
// in `yield from` error handling. The point here is to reduce code size.
//
// This implements most of the bodies of the `except` blocks in the
// pseudocode in PEP 380.
//
// Returns true (1) if a StopIteration was received and we should return.
// Returns false (0) if a value should be yielded.
// In both cases the value is stored in outp.
// Signals an error (2) if the an exception should be propagated.
static int CPy_YieldFromErrorHandle(PyObject *iter, PyObject **outp)
{
    _Py_IDENTIFIER(close);
    _Py_IDENTIFIER(throw);
    PyObject *exc_type = CPy_ExcState()->exc_type;
    PyObject *type, *value, *traceback;
    PyObject *_m;
    PyObject *res;
    *outp = NULL;

    if (PyErr_GivenExceptionMatches(exc_type, PyExc_GeneratorExit)) {
        _m = _PyObject_GetAttrId(iter, &PyId_close);
        if (_m) {
            res = PyObject_CallFunctionObjArgs(_m, NULL);
            Py_DECREF(_m);
            if (!res)
                return 2;
            Py_DECREF(res);
        } else if (PyErr_ExceptionMatches(PyExc_AttributeError)) {
            PyErr_Clear();
        } else {
            return 2;
        }
    } else {
        _m = _PyObject_GetAttrId(iter, &PyId_throw);
        if (_m) {
            CPy_GetExcInfo(&type, &value, &traceback);
            res = PyObject_CallFunctionObjArgs(_m, type, value, traceback, NULL);
            Py_DECREF(type);
            Py_DECREF(value);
            Py_DECREF(traceback);
            Py_DECREF(_m);
            if (res) {
                *outp = res;
                return 0;
            } else {
                res = CPy_FetchStopIterationValue();
                if (res) {
                    *outp = res;
                    return 1;
                }
            }
        } else if (PyErr_ExceptionMatches(PyExc_AttributeError)) {
            PyErr_Clear();
        } else {
            return 2;
        }
    }

    CPy_Reraise();
    return 2;
}

static int _CPy_UpdateObjFromDict(PyObject *obj, PyObject *dict)
{
    Py_ssize_t pos = 0;
    PyObject *key, *value;
    while (PyDict_Next(dict, &pos, &key, &value)) {
        if (PyObject_SetAttr(obj, key, value) != 0) {
            return -1;
        }
    }
    return 0;
}

// Support for pickling; reusable getstate and setstate functions
static PyObject *
CPyPickle_SetState(PyObject *obj, PyObject *state)
{
    if (_CPy_UpdateObjFromDict(obj, state) != 0) {
        return NULL;
    }
    Py_RETURN_NONE;
}

static PyObject *
CPyPickle_GetState(PyObject *obj)
{
    PyObject *attrs = NULL, *state = NULL;

    attrs = PyObject_GetAttrString((PyObject *)Py_TYPE(obj), "__mypyc_attrs__");
    if (!attrs) {
        goto fail;
    }
    if (!PyTuple_Check(attrs)) {
        PyErr_SetString(PyExc_TypeError, "__mypyc_attrs__ is not a tuple");
        goto fail;
    }
    state = PyDict_New();
    if (!state) {
        goto fail;
    }

    // Collect all the values of attributes in __mypyc_attrs__
    // Attributes that are missing we just ignore
    int i;
    for (i = 0; i < PyTuple_GET_SIZE(attrs); i++) {
        PyObject *key = PyTuple_GET_ITEM(attrs, i);
        PyObject *value = PyObject_GetAttr(obj, key);
        if (!value) {
            if (PyErr_ExceptionMatches(PyExc_AttributeError)) {
                PyErr_Clear();
                continue;
            }
            goto fail;
        }
        int result = PyDict_SetItem(state, key, value);
        Py_DECREF(value);
        if (result != 0) {
            goto fail;
        }
    }

    Py_DECREF(attrs);

    return state;
fail:
    Py_XDECREF(attrs);
    Py_XDECREF(state);
    return NULL;
}

/* Support for our partial built-in support for dataclasses.
 *
 * Take a class we want to make a dataclass, remove any descriptors
 * for annotated attributes, swap in the actual values of the class
 * variables invoke dataclass, and then restore all of the
 * descriptors.
 *
 * The purpose of all this is that dataclasses uses the values of
 * class variables to drive which attributes are required and what the
 * default values/factories are for optional attributes. This means
 * that the class dict needs to contain those values instead of getset
 * descriptors for the attributes when we invoke dataclass.
 *
 * We need to remove descriptors for attributes even when there is no
 * default value for them, or else dataclass will think the descriptor
 * is the default value. We remove only the attributes, since we don't
 * want dataclasses to try generating functions when they are already
 * implemented.
 *
 * Args:
 *   dataclass_dec: The decorator to apply
 *   tp: The class we are making a dataclass
 *   dict: The dictionary containing values that dataclasses needs
 *   annotations: The type annotation dictionary
 */
static int
CPyDataclass_SleightOfHand(PyObject *dataclass_dec, PyObject *tp,
                           PyObject *dict, PyObject *annotations) {
    PyTypeObject *ttp = (PyTypeObject *)tp;
    Py_ssize_t pos;
    PyObject *res;

    /* Make a copy of the original class __dict__ */
    PyObject *orig_dict = PyDict_Copy(ttp->tp_dict);
    if (!orig_dict) {
        goto fail;
    }

    /* Delete anything that had an annotation */
    pos = 0;
    PyObject *key;
    while (PyDict_Next(annotations, &pos, &key, NULL)) {
        if (PyObject_DelAttr(tp, key) != 0) {
            goto fail;
        }
    }

    /* Copy in all the attributes that we want dataclass to see */
    if (_CPy_UpdateObjFromDict(tp, dict) != 0) {
        goto fail;
    }

    /* Run the @dataclass descriptor */
    res = PyObject_CallFunctionObjArgs(dataclass_dec, tp, NULL);
    if (!res) {
        goto fail;
    }
    Py_DECREF(res);

    /* Copy back the original contents of the dict */
    if (_CPy_UpdateObjFromDict(tp, orig_dict) != 0) {
        goto fail;
    }

    Py_DECREF(orig_dict);
    return 1;

fail:
    Py_XDECREF(orig_dict);
    return 0;
}


int CPyArg_ParseTupleAndKeywords(PyObject *, PyObject *,
                                 const char *, char **, ...);

#ifdef __cplusplus
}
#endif

#endif // CPY_CPY_H
