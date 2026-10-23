// List primitive operations
//
// These are registered in mypyc.primitives.list_ops.

#include <Python.h>
#include "CPy.h"

#ifndef Py_TPFLAGS_SEQUENCE
#define Py_TPFLAGS_SEQUENCE (1 << 5)
#endif

PyObject *CPyList_Build(Py_ssize_t len, ...) {
    Py_ssize_t i;

    PyObject *res = PyList_New(len);
    if (res == NULL) {
        va_list args;
        va_start(args, len);
        for (i = 0; i < len; i++) {
            Py_DECREF(va_arg(args, PyObject *));
        }
        va_end(args);
        return NULL;
    }

    va_list args;
    va_start(args, len);
    for (i = 0; i < len; i++) {
        // Steals the reference
        PyObject *value = va_arg(args, PyObject *);
        PyList_SET_ITEM(res, i, value);
    }
    va_end(args);

    return res;
}

char CPyList_Clear(PyObject *list) {
    if (PyList_CheckExact(list)) {
        PyList_Clear(list);
    } else {
        PyObject *res = PyObject_CallMethodNoArgs(list, mypyc_interned_str.clear);
        if (res == NULL) {
            return 0;
        }
        Py_DECREF(res);
    }
    return 1;
}

PyObject *CPyList_Copy(PyObject *list) {
    if(PyList_CheckExact(list)) {
        return PyList_GetSlice(list, 0, PyList_GET_SIZE(list));
    }
    return PyObject_CallMethodNoArgs(list, mypyc_interned_str.copy);
}

#ifndef Py_GIL_DISABLED

PyObject *CPyList_GetItemShort(PyObject *list, CPyTagged index) {
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

PyObject *CPyList_GetItem(PyObject *list, CPyTagged index) {
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
        PyErr_SetString(PyExc_OverflowError, CPYTHON_LARGE_INT_ERRMSG);
        return NULL;
    }
}

PyObject *CPyList_GetItemInt64(PyObject *list, int64_t index) {
    size_t size = PyList_GET_SIZE(list);
    if (likely((uint64_t)index < size)) {
        PyObject *result = PyList_GET_ITEM(list, index);
        Py_INCREF(result);
        return result;
    }
    if (index >= 0) {
        PyErr_SetString(PyExc_IndexError, "list index out of range");
        return NULL;
    }
    index += size;
    if (index < 0) {
        PyErr_SetString(PyExc_IndexError, "list index out of range");
        return NULL;
    }
    PyObject *result = PyList_GET_ITEM(list, index);
    Py_INCREF(result);
    return result;
}

bool CPyList_SetItem(PyObject *list, CPyTagged index, PyObject *value) {
    if (CPyTagged_CheckShort(index)) {
        Py_ssize_t n = CPyTagged_ShortAsSsize_t(index);
        Py_ssize_t size = PyList_GET_SIZE(list);
        if (n >= 0) {
            if (n >= size) {
                Py_DECREF(value);
                PyErr_SetString(PyExc_IndexError, "list assignment index out of range");
                return false;
            }
        } else {
            n += size;
            if (n < 0) {
                Py_DECREF(value);
                PyErr_SetString(PyExc_IndexError, "list assignment index out of range");
                return false;
            }
        }
        // Set the replacement before decref, which may run reentrant Python code.
        PyObject *old = PyList_GET_ITEM(list, n);
        // N.B: Steals reference
        PyList_SET_ITEM(list, n, value);
        Py_DECREF(old);
        return true;
    } else {
        Py_DECREF(value);
        PyErr_SetString(PyExc_OverflowError, CPYTHON_LARGE_INT_ERRMSG);
        return false;
    }
}

bool CPyList_SetItemInt64(PyObject *list, int64_t index, PyObject *value) {
    size_t size = PyList_GET_SIZE(list);
    if (unlikely((uint64_t)index >= size)) {
        if (index >= 0) {
            Py_DECREF(value);
            PyErr_SetString(PyExc_IndexError, "list assignment index out of range");
            return false;
        }
        index += size;
        if (index < 0) {
            Py_DECREF(value);
            PyErr_SetString(PyExc_IndexError, "list assignment index out of range");
            return false;
        }
    }
    // Set the replacement before decref, which may run reentrant Python code.
    PyObject *old = PyList_GET_ITEM(list, index);
    // N.B: Steals reference
    PyList_SET_ITEM(list, index, value);
    Py_DECREF(old);
    return true;
}

#else /* Py_GIL_DISABLED */

PyObject *CPyList_GetItem_(PyObject *list, CPyTagged index) {
    if (CPyTagged_CheckShort(index)) {
        Py_ssize_t n = CPyTagged_ShortAsSsize_t(index);
        if (n < 0) {
            n += PyList_GET_SIZE(list);
        }
        return PyList_GetItemRef(list, n);
    } else {
        PyErr_SetString(PyExc_OverflowError, CPYTHON_LARGE_INT_ERRMSG);
        return NULL;
    }
}

bool CPyList_SetItem_(PyObject *list, CPyTagged index, PyObject *value) {
    if (CPyTagged_CheckShort(index)) {
        Py_ssize_t n = CPyTagged_ShortAsSsize_t(index);
        Py_ssize_t size = PyList_GET_SIZE(list);
        if (n < 0) {
            n += size;
        }
        return PyList_SetItem(list, n, value) >= 0;
    } else {
        Py_DECREF(value);
        PyErr_SetString(PyExc_OverflowError, CPYTHON_LARGE_INT_ERRMSG);
        return false;
    }
}

#endif

PyObject *CPyList_GetItemShortBorrow(PyObject *list, CPyTagged index) {
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
    return PyList_GET_ITEM(list, n);
}

PyObject *CPyList_GetItemBorrow(PyObject *list, CPyTagged index) {
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
        return PyList_GET_ITEM(list, n);
    } else {
        PyErr_SetString(PyExc_OverflowError, CPYTHON_LARGE_INT_ERRMSG);
        return NULL;
    }
}

PyObject *CPyList_GetItemInt64Borrow(PyObject *list, int64_t index) {
    size_t size = PyList_GET_SIZE(list);
    if (likely((uint64_t)index < size)) {
        return PyList_GET_ITEM(list, index);
    }
    if (index >= 0) {
        PyErr_SetString(PyExc_IndexError, "list index out of range");
        return NULL;
    }
    index += size;
    if (index < 0) {
        PyErr_SetString(PyExc_IndexError, "list index out of range");
        return NULL;
    }
    return PyList_GET_ITEM(list, index);
}

// This function should only be used to fill in brand new lists.
void CPyList_SetItemUnsafe(PyObject *list, Py_ssize_t index, PyObject *value) {
    PyList_SET_ITEM(list, index, value);
}

#ifdef Py_GIL_DISABLED
// The original optimized list.pop implementation may reallocate the item array,
// which doesn't work on free-threaded builds, so provide an alternative that
// never reallocates it (like del a[i] in CPython, the array never shrinks).
//
// The list is locked so that the item is removed atomically. A negative index
// is relative to the end of the list.
static inline PyObject *list_pop_index(PyObject *list, Py_ssize_t index) {
    PyObject *item = NULL;
    Py_BEGIN_CRITICAL_SECTION(list);
    Py_ssize_t size = PyList_GET_SIZE(list);
    if (index < 0) {
        index += size;
    }
    if (size == 0) {
        PyErr_SetString(PyExc_IndexError, "pop from empty list");
    } else if (index < 0 || index >= size) {
        PyErr_SetString(PyExc_IndexError, "pop index out of range");
    } else {
        // Same steps as del a[i] in CPython (list_ass_item_lock_held), except that
        // the list's reference to the item is passed to the caller. Never resize
        // the item array here: on free-threaded builds it must be freed using QSBR.
        PyObject **items = ((PyListObject *)list)->ob_item;
        item = items[index];
        for (Py_ssize_t i = index; i < size - 1; i++) {
            _Py_atomic_store_ptr_release(&items[i], items[i + 1]);
        }
        Py_SET_SIZE(list, size - 1);
    }
    Py_END_CRITICAL_SECTION();
    return item;
}
#endif

PyObject *CPyList_PopLast(PyObject *list)
{
#ifdef Py_GIL_DISABLED
    // The other implementation causes segfaults on a free-threaded Python 3.14b4 build.
    return list_pop_index(list, -1);
#else
    // I tried a specialized version of pop_impl for just removing the
    // last element and it wasn't any faster in microbenchmarks than
    // the generic one so I ditched it.
    return list_pop_impl((PyListObject *)list, -1);
#endif
}

PyObject *CPyList_Pop(PyObject *obj, CPyTagged index)
{
    if (CPyTagged_CheckShort(index)) {
        Py_ssize_t n = CPyTagged_ShortAsSsize_t(index);
#ifdef Py_GIL_DISABLED
        // We must use a slower implementation on free-threaded builds.
        return list_pop_index(obj, n);
#else
        return list_pop_impl((PyListObject *)obj, n);
#endif
    } else {
        PyErr_SetString(PyExc_OverflowError, CPYTHON_LARGE_INT_ERRMSG);
        return NULL;
    }
}

CPyTagged CPyList_Count(PyObject *obj, PyObject *value)
{
    return list_count((PyListObject *)obj, value);
}

int CPyList_Insert(PyObject *list, CPyTagged index, PyObject *value)
{
    if (CPyTagged_CheckShort(index)) {
        Py_ssize_t n = CPyTagged_ShortAsSsize_t(index);
        return PyList_Insert(list, n, value);
    }
    // The max range doesn't exactly coincide with ssize_t, but we still
    // want to keep the error message compatible with CPython.
    PyErr_SetString(PyExc_OverflowError, CPYTHON_LARGE_INT_ERRMSG);
    return -1;
}

PyObject *CPyList_Extend(PyObject *o1, PyObject *o2) {
    if (PyList_Extend(o1, o2) < 0) {
        return NULL;
    }
    Py_RETURN_NONE;
}

// Return -2 or error, -1 if not found, or index of first match otherwise.
//
// The caller must hold a critical section on the list.
static Py_ssize_t _CPyList_Find(PyObject *list, PyObject *obj) {
    Py_ssize_t i;
    for (i = 0; i < Py_SIZE(list); i++) {
        PyObject *item = PyList_GET_ITEM(list, i);
        Py_INCREF(item);
        int cmp = PyObject_RichCompareBool(item, obj, Py_EQ);
        Py_DECREF(item);
        if (cmp != 0) {
            if (cmp > 0) {
                return i;
            } else {
                return -2;
            }
        }
    }
    return -1;
}

int CPyList_Remove(PyObject *list, PyObject *obj) {
    int retval;
    Py_BEGIN_CRITICAL_SECTION(list);
    Py_ssize_t index = _CPyList_Find(list, obj);
    if (index == -2) {
        retval = -1;
    } else if (index == -1) {
        PyErr_SetString(PyExc_ValueError, "list.remove(x): x not in list");
        retval = -1;
    } else {
        retval = PyList_SetSlice(list, index, index + 1, NULL);
    }
    Py_END_CRITICAL_SECTION();
    return retval;
}

CPyTagged CPyList_Index(PyObject *list, PyObject *obj) {
    CPyTagged retval;
    Py_BEGIN_CRITICAL_SECTION(list);
    Py_ssize_t index = _CPyList_Find(list, obj);
    if (index == -2) {
        retval = CPY_INT_TAG;
    } else if (index == -1) {
        PyErr_SetString(PyExc_ValueError, "value is not in list");
        retval = CPY_INT_TAG;
    } else {
        retval = index << 1;
    }
    Py_END_CRITICAL_SECTION();
    return retval;
}

PyObject *CPySequence_Sort(PyObject *seq) {
    PyObject *newlist = PySequence_List(seq);
    if (newlist == NULL)
        return NULL;
    int res = PyList_Sort(newlist);
    if (res < 0) {
        Py_DECREF(newlist);
        return NULL;
    }
    return newlist;
}

PyObject *CPySequence_Multiply(PyObject *seq, CPyTagged t_size) {
    Py_ssize_t size = CPyTagged_AsSsize_t(t_size);
    if (size == -1 && PyErr_Occurred()) {
        return NULL;
    }
    return PySequence_Repeat(seq, size);
}

PyObject *CPySequence_RMultiply(CPyTagged t_size, PyObject *seq) {
    return CPySequence_Multiply(seq, t_size);
}

PyObject *CPySequence_InPlaceMultiply(PyObject *seq, CPyTagged t_size) {
    Py_ssize_t size = CPyTagged_AsSsize_t(t_size);
    if (size == -1 && PyErr_Occurred()) {
        return NULL;
    }
    return PySequence_InPlaceRepeat(seq, size);
}

PyObject *CPyList_GetSlice(PyObject *obj, CPyTagged start, CPyTagged end) {
    if (likely(PyList_CheckExact(obj)
               && CPyTagged_CheckShort(start) && CPyTagged_CheckShort(end))) {
        Py_ssize_t startn = CPyTagged_ShortAsSsize_t(start);
        Py_ssize_t endn = CPyTagged_ShortAsSsize_t(end);
        if (startn < 0) {
            startn += PyList_GET_SIZE(obj);
        }
        if (endn < 0) {
            endn += PyList_GET_SIZE(obj);
        }
        return PyList_GetSlice(obj, startn, endn);
    }
    return CPyObject_GetSlice(obj, start, end);
}

int CPySequence_Check(PyObject *obj) {
    return Py_TYPE(obj)->tp_flags & Py_TPFLAGS_SEQUENCE;
}
