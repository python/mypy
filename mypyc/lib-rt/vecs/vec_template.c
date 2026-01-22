// NOTE: This file can't be compiled on its own, it must be #included
//       with certain #defines set, as described below.
//
// Implementation of a vec class specialized to a specific item type, such
// as vec[i64] or vec[float]. Assume that certain #defines are provided that
// provide all the item type specific definitions:
//
//   VEC      vec C type (e.g. VecI64)

#ifndef VEC
#error "VEC must be defined"
#endif

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "librt_vecs.h"

inline static VEC vec_error() {
    VEC v = { .len = -1 };
    return v;
}

// Alloc a partially initialized vec. Caller *must* initialize len.
static VEC vec_alloc(Py_ssize_t size)
{
    BUF_OBJECT *buf;
    /* TODO: Check for overflow */
    if (size == 0) {
        buf = NULL;
    } else {
        buf = PyObject_NewVar(BUF_OBJECT, &BUF_TYPE, size);
        if (buf == NULL)
            return vec_error();
    }
    VEC res = { .buf = buf };
    return res;
}

static void vec_dealloc(VEC_OBJECT *self) {
    Py_CLEAR(self->vec.buf);
    PyObject_Del(self);
}

// Box a vec[<itemtype>] value, stealing the buffer reference.
PyObject *FUNC(Box)(VEC vec) {
    VEC_OBJECT *obj = PyObject_New(VEC_OBJECT, &VEC_TYPE);
    if (obj == NULL)
        return NULL;
    obj->vec = vec;
    return (PyObject *)obj;
}

VEC FUNC(Unbox)(PyObject *obj) {
    if (obj->ob_type == &VEC_TYPE) {
        VEC result = ((VEC_OBJECT *)obj)->vec;
        VEC_INCREF(result);  // TODO: Should we borrow instead?
        return result;
    } else {
        // TODO: Better error message
        PyErr_SetString(PyExc_TypeError, "vec[i64] expected");
        return vec_error();
    }
}

VEC FUNC(ConvertFromNested)(VecNestedBufItem item) {
    return (VEC) { item.len, (BUF_OBJECT *)item.buf };
}

VEC FUNC(New)(Py_ssize_t size, Py_ssize_t cap) {
    if (cap < size)
        size = cap;
    VEC vec = vec_alloc(cap);
    if (VEC_IS_ERROR(vec))
        return vec;
    for (Py_ssize_t i = 0; i < cap; i++) {
        vec.buf->items[i] = 0;
    }
    vec.len = size;
    return vec;
}

PyObject *FUNC(FromIterable)(PyObject *iterable) {
    VEC v = vec_alloc(0);
    if (VEC_IS_ERROR(v))
        return NULL;
    v.len = 0;

    PyObject *iter = PyObject_GetIter(iterable);
    if (iter == NULL) {
        VEC_DECREF(v);
        return NULL;
    }
    PyObject *item;
    while ((item = PyIter_Next(iter)) != NULL) {
        ITEM_C_TYPE x = UNBOX_ITEM(item);
        Py_DECREF(item);
        if (IS_UNBOX_ERROR(x)) {
            Py_DECREF(iter);
            VEC_DECREF(v);
            return NULL;
        }
        v = FUNC(Append)(v, x);
        if (VEC_IS_ERROR(v)) {
            Py_DECREF(iter);
            VEC_DECREF(v);
            return NULL;
        }
    }
    Py_DECREF(iter);
    if (PyErr_Occurred()) {
        VEC_DECREF(v);
        return NULL;
    }
    return FUNC(Box)(v);
}

static PyObject *vec_new(PyTypeObject *self, PyObject *args, PyObject *kw) {
    static char *kwlist[] = {"", NULL};
    PyObject *init = NULL;
    if (!PyArg_ParseTupleAndKeywords(args, kw, "|O:vec", kwlist, &init)) {
        return NULL;
    }
    if (init == NULL) {
        return FUNC(Box)(FUNC(New)(0, 0));
    } else {
        return (PyObject *)FUNC(FromIterable)(init);
    }
}

static PyObject *vec_repr(PyObject *self) {
    return Vec_GenericRepr(self, ITEM_TYPE_MAGIC, 0, 1);
}

static PyObject *vec_get_item(PyObject *o, Py_ssize_t i) {
    VEC v = ((VEC_OBJECT *)o)->vec;
    if ((size_t)i < (size_t)v.len) {
        return BOX_ITEM(v.buf->items[i]);
    } else if ((size_t)i + (size_t)v.len < (size_t)v.len) {
        return BOX_ITEM(v.buf->items[i + v.len]);
    } else {
        PyErr_SetString(PyExc_IndexError, "index out of range");
        return NULL;
    }
}

VEC FUNC(Slice)(VEC vec, int64_t start, int64_t end) {
    if (start < 0)
        start += vec.len;
    if (end < 0)
        end += vec.len;
    if (start < 0)
        start = 0;
    if (start >= vec.len)
        start = vec.len;
    if (end < start)
        end = start;
    if (end > vec.len)
        end = vec.len;
    int64_t slicelength = end - start;
    VEC res = vec_alloc(slicelength);
    if (VEC_IS_ERROR(res))
        return res;
    res.len = slicelength;
    for (Py_ssize_t i = 0; i < slicelength; i++)
        res.buf->items[i] = vec.buf->items[start + i];
    return res;
}

static PyObject *vec_subscript(PyObject *self, PyObject *item) {
    VEC vec = ((VEC_OBJECT *)self)->vec;
    if (PyIndex_Check(item)) {
        Py_ssize_t i = PyNumber_AsSsize_t(item, PyExc_IndexError);
        if (i == -1 && PyErr_Occurred())
            return NULL;
        if ((size_t)i < (size_t)vec.len) {
            return BOX_ITEM(vec.buf->items[i]);
        } else if ((size_t)i + (size_t)vec.len < (size_t)vec.len) {
            return BOX_ITEM(vec.buf->items[i + vec.len]);
        } else {
            PyErr_SetString(PyExc_IndexError, "index out of range");
            return NULL;
        }
    } else if (PySlice_Check(item)) {
        Py_ssize_t start, stop, step;
        if (PySlice_Unpack(item, &start, &stop, &step) < 0)
            return NULL;
        Py_ssize_t slicelength = PySlice_AdjustIndices(vec.len, &start, &stop, step);
        VEC res = vec_alloc(slicelength);
        if (VEC_IS_ERROR(res))
            return NULL;
        res.len = slicelength;
        Py_ssize_t j = start;
        for (Py_ssize_t i = 0; i < slicelength; i++) {
            res.buf->items[i] = vec.buf->items[j];
            j += step;
        }
        return FUNC(Box)(res);
    } else {
        PyErr_Format(PyExc_TypeError, "vec indices must be integers or slices, not %.100s",
                     item->ob_type->tp_name);
        return NULL;
    }
}

static int vec_ass_item(PyObject *self, Py_ssize_t i, PyObject *o) {
    ITEM_C_TYPE x = UNBOX_ITEM(o);
    if (IS_UNBOX_ERROR(x))
        return -1;
    VEC v = ((VEC_OBJECT *)self)->vec;
    if ((size_t)i < (size_t)v.len) {
        v.buf->items[i] = x;
        return 0;
    } else if ((size_t)i + (size_t)v.len < (size_t)v.len) {
        v.buf->items[i + v.len] = x;
        return 0;
    } else {
        PyErr_SetString(PyExc_IndexError, "index out of range");
        return -1;
    }
}

static Py_ssize_t vec_length(PyObject *o) {
    // TODO: Type check o
    return ((VEC_OBJECT *)o)->vec.len;
}

static PyObject *vec_richcompare(PyObject *self, PyObject *other, int op) {
    int cmp = 1;
    PyObject *res;
    if (op == Py_EQ || op == Py_NE) {
        if (other->ob_type != &VEC_TYPE)
            cmp = 0;
        else {
            VEC x = ((VEC_OBJECT *)self)->vec;
            VEC y = ((VEC_OBJECT *)other)->vec;
            if (x.len != y.len) {
                cmp = 0;
            } else {
                for (Py_ssize_t i = 0; i < x.len; i++) {
                    if (x.buf->items[i] != y.buf->items[i]) {
                        cmp = 0;
                        break;
                    }
                }
            }
        }
        if (op == Py_NE)
            cmp = cmp ^ 1;
        res = cmp ? Py_True : Py_False;
    } else
        res = Py_NotImplemented;
    Py_INCREF(res);
    return res;
}

VEC FUNC(Append)(VEC vec, ITEM_C_TYPE x) {
    if (vec.buf && vec.len < VEC_CAP(vec)) {
        vec.buf->items[vec.len] = x;
        vec.len++;
        return vec;
    } else {
        Py_ssize_t cap = vec.buf ? VEC_CAP(vec) : 0;
        Py_ssize_t new_size = 2 * cap + 1;
        VEC new = vec_alloc(new_size);
        if (VEC_IS_ERROR(new))
            return vec_error();
        new.len = vec.len + 1;
        if (vec.len > 0)
            memcpy(new.buf->items, vec.buf->items, sizeof(ITEM_C_TYPE) * vec.len);
        new.buf->items[vec.len] = x;
        Py_XDECREF(vec.buf);
        return new;
    }
}

VEC FUNC(Remove)(VEC v, ITEM_C_TYPE x) {
    for (Py_ssize_t i = 0; i < v.len; i++) {
        if (v.buf->items[i] == x) {
            for (; i < v.len - 1; i++) {
                v.buf->items[i] = v.buf->items[i + 1];
            }
            v.len--;
            VEC_INCREF(v);
            return v;
        }
    }
    PyErr_SetString(PyExc_ValueError, "vec.remove(x): x not in vec");
    return vec_error();
}

NAME(PopResult) FUNC(Pop)(VEC v, Py_ssize_t index) {
    NAME(PopResult) result;

    if (index < 0)
        index += v.len;

    if (index < 0 || index >= v.len) {
        PyErr_SetString(PyExc_IndexError, "index out of range");
        result.f0 = vec_error();
        result.f1 = 0;
        return result;
    }

    result.f1 = v.buf->items[index];
    for (Py_ssize_t i = index; i < v.len - 1; i++) {
        v.buf->items[i] = v.buf->items[i + 1];
    }

    v.len--;
    VEC_INCREF(v);
    result.f0 = v;
    return result;
}

static PyMappingMethods vec_mapping_methods = {
    .mp_length = vec_length,
    .mp_subscript = vec_subscript,
};

static PySequenceMethods vec_sequence_methods = {
    .sq_item = vec_get_item,
    .sq_ass_item = vec_ass_item,
};

static PyMethodDef vec_methods[] = {
    {NULL, NULL, 0, NULL},  /* Sentinel */
};

PyTypeObject BUF_TYPE = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "vecbuf[" ITEM_TYPE_STR "]",
    .tp_doc = "vec doc",
    .tp_basicsize = sizeof(VEC_OBJECT) - sizeof(ITEM_C_TYPE),
    .tp_itemsize = sizeof(ITEM_C_TYPE),
    .tp_flags = Py_TPFLAGS_DEFAULT,
    //.tp_new = ??
    .tp_free = PyObject_Del,
};

PyTypeObject VEC_TYPE = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "vec[" ITEM_TYPE_STR "]",
    .tp_doc = "vec doc",
    .tp_basicsize = sizeof(VEC_OBJECT),
    .tp_itemsize = 0,
    .tp_flags = Py_TPFLAGS_DEFAULT,
    .tp_new = vec_new,
    //.tp_free = PyObject_Del,
    .tp_dealloc = (destructor)vec_dealloc,
    .tp_repr = (reprfunc)vec_repr,
    .tp_as_sequence = &vec_sequence_methods,
    .tp_as_mapping = &vec_mapping_methods,
    .tp_richcompare = vec_richcompare,
    .tp_methods = vec_methods,
};

NAME(Features) FEATURES = {
    &VEC_TYPE,
    &BUF_TYPE,
    FUNC(New),
    FUNC(Box),
    FUNC(Unbox),
    FUNC(ConvertFromNested),
    FUNC(Append),
    FUNC(Pop),
    FUNC(Remove),
    FUNC(Slice),
};
