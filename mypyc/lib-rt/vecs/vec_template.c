// NOTE: This file can't be compiled on its own, it must be #included
//       with certain #defines set, as described below.
//
// Implementation of a vec class specialized to a specific item type, such
// as vec[i64] or vec[float]. Assume that certain #defines are provided that
// provide all the item type specific definitions:
//
//   PREFIX      name prefix used for non-static definitions (e.g. VecI64)
//   VEC         C struct used for the vec (e.g. VecI64)
//   BOXTYPE     PyTypeObject used for a boxed vec (e.g. VecI64Object)
//   BUFOBJ      C struct used for the buffer object (e.g. VecI64BufObject)
//   BUFTYPE     PyTypeObject used for the buffer object (e.g. VecI64BufType)

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "vecs.h"

// Alloc a partially initialized vec. Caller *must* initialize len.
static VecI64 vec_alloc(Py_ssize_t size)
{
    VecI64BufObject *buf;
    /* TODO: Check for overflow */
    if (size == 0) {
        buf = NULL;
    } else {
        buf = PyObject_NewVar(VecI64BufObject, &VecI64BufType, size);
        if (buf == NULL)
            return PREFIX##Error();
    }
    VecI64 res = { .buf = buf };
    return res;
}

static void vec_dealloc(VecI64Object *self) {
    Py_CLEAR(self->vec.buf);
    PyObject_Del(self);
}

PyObject *PREFIX##Box(VecI64 vec) {
    VecI64Object *obj = PyObject_New(VecI64Object, &VecI64Type);
    if (obj == NULL)
        return NULL;
    obj->vec = vec;
    return (PyObject *)obj;
}

VecI64 PREFIX##Unbox(PyObject *obj) {
    if (obj->ob_type == &VecI64Type) {
        VecI64 result = ((VecI64Object *)obj)->vec;
        VEC_INCREF(result);  // TODO: Should we borrow instead?
        return result;
    } else {
        // TODO: Better error message
        PyErr_SetString(PyExc_TypeError, "vec[i64] expected");
        return PREFIX##Error();
    }
}

VecI64 PREFIX##ConvertFromNested(VecNestedBufItem item) {
    return (VecI64) { item.len, (VecI64BufObject *)item.buf };
}

VecI64 PREFIX##New(Py_ssize_t size, Py_ssize_t cap) {
    if (cap < size)
        size = cap;
    VecI64 vec = vec_alloc(cap);
    if (VEC_IS_ERROR(vec))
        return vec;
    for (Py_ssize_t i = 0; i < cap; i++) {
        vec.buf->items[i] = 0;
    }
    vec.len = size;
    return vec;
}

PyObject *PREFIX##FromIterable(PyObject *iterable) {
    VecI64 v = vec_alloc(0);
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
        int64_t x = PyLong_AsLongLong(item);
        Py_DECREF(item);
        if (x == -1 && PyErr_Occurred()) {
            Py_DECREF(iter);
            VEC_DECREF(v);
            return NULL;
        }
        v = PREFIX##Append(v, x);
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
    return PREFIX##Box(v);
}

PyObject *vec_new(PyTypeObject *self, PyObject *args, PyObject *kw) {
    static char *kwlist[] = {"", NULL};
    PyObject *init = NULL;
    if (!PyArg_ParseTupleAndKeywords(args, kw, "|O:vec", kwlist, &init)) {
        return NULL;
    }
    if (init == NULL) {
        return PREFIX##Box(PREFIX##New(0, 0));
    } else {
        return (PyObject *)PREFIX##FromIterable(init);
    }
}

PyObject *vec_repr(PyObject *self) {
    return Vec_GenericRepr(self, (size_t)I64TypeObj, 0, 1);
}

PyObject *vec_get_item(PyObject *o, Py_ssize_t i) {
    VecI64 v = ((VecI64Object *)o)->vec;
    if ((size_t)i < (size_t)v.len) {
        return PyLong_FromLongLong(v.buf->items[i]);
    } else if ((size_t)i + (size_t)v.len < (size_t)v.len) {
        return PyLong_FromLongLong(v.buf->items[i + v.len]);
    } else {
        PyErr_SetString(PyExc_IndexError, "index out of range");
        return NULL;
    }
}

VecI64 PREFIX##Slice(VecI64 vec, int64_t start, int64_t end) {
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
    VecI64 res = vec_alloc(slicelength);
    if (VEC_IS_ERROR(res))
        return res;
    res.len = slicelength;
    for (Py_ssize_t i = 0; i < slicelength; i++)
        res.buf->items[i] = vec.buf->items[start + i];
    return res;
}

PyObject *vec_subscript(PyObject *self, PyObject *item) {
    VecI64 vec = ((VecI64Object *)self)->vec;
    if (PyIndex_Check(item)) {
        Py_ssize_t i = PyNumber_AsSsize_t(item, PyExc_IndexError);
        if (i == -1 && PyErr_Occurred())
            return NULL;
        if ((size_t)i < (size_t)vec.len) {
            return PyLong_FromLongLong(vec.buf->items[i]);
        } else if ((size_t)i + (size_t)vec.len < (size_t)vec.len) {
            return PyLong_FromLongLong(vec.buf->items[i + vec.len]);
        } else {
            PyErr_SetString(PyExc_IndexError, "index out of range");
            return NULL;
        }
    } else if (PySlice_Check(item)) {
        Py_ssize_t start, stop, step;
        if (PySlice_Unpack(item, &start, &stop, &step) < 0)
            return NULL;
        Py_ssize_t slicelength = PySlice_AdjustIndices(vec.len, &start, &stop, step);
        VecI64 res = vec_alloc(slicelength);
        if (VEC_IS_ERROR(res))
            return NULL;
        res.len = slicelength;
        Py_ssize_t j = start;
        for (Py_ssize_t i = 0; i < slicelength; i++) {
            res.buf->items[i] = vec.buf->items[j];
            j += step;
        }
        return PREFIX##Box(res);
    } else {
        PyErr_Format(PyExc_TypeError, "vec indices must be integers or slices, not %.100s",
                     item->ob_type->tp_name);
        return NULL;
    }
}

int vec_ass_item(PyObject *self, Py_ssize_t i, PyObject *o) {
    if (Vec_CheckFloatError(o))
        return -1;
    VecI64 v = ((VecI64Object *)self)->vec;
    if ((size_t)i < (size_t)v.len) {
        long long x = PyLong_AsLongLong(o);
        if (x == -1 && PyErr_Occurred())
            return -1;
        v.buf->items[i] = x;
        return 0;
    } else if ((size_t)i + (size_t)v.len < (size_t)v.len) {
        long long x = PyLong_AsLongLong(o);
        if (x == -1 && PyErr_Occurred())
            return -1;
        v.buf->items[i + v.len] = x;
        return 0;
    } else {
        PyErr_SetString(PyExc_IndexError, "index out of range");
        return -1;
    }
}

static Py_ssize_t vec_length(PyObject *o) {
    // TODO: Type check o
    return ((VecI64Object *)o)->vec.len;
}

static PyObject *vec_richcompare(PyObject *self, PyObject *other, int op) {
    int cmp = 1;
    PyObject *res;
    if (op == Py_EQ || op == Py_NE) {
        if (other->ob_type != &VecI64Type)
            cmp = 0;
        else {
            VecI64 x = ((VecI64Object *)self)->vec;
            VecI64 y = ((VecI64Object *)other)->vec;
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

VecI64 PREFIX##Append(VecI64 vec, int64_t x) {
    if (vec.buf && vec.len < VEC_CAP(vec)) {
        vec.buf->items[vec.len] = x;
        vec.len++;
        return vec;
    } else {
        Py_ssize_t cap = vec.buf ? VEC_CAP(vec) : 0;
        Py_ssize_t new_size = 2 * cap + 1;
        VecI64 new = vec_alloc(new_size);
        if (VEC_IS_ERROR(new))
            return PREFIX##Error();
        new.len = vec.len + 1;
        if (vec.len > 0)
            memcpy(new.buf->items, vec.buf->items, sizeof(int64_t) * vec.len);
        new.buf->items[vec.len] = x;
        Py_XDECREF(vec.buf);
        return new;
    }
}

VecI64 PREFIX##Remove(VecI64 v, int64_t x) {
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
    return PREFIX##Error();
}

VecI64PopResult PREFIX##Pop(VecI64 v, Py_ssize_t index) {
    VecI64PopResult result;

    if (index < 0)
        index += v.len;

    if (index < 0 || index >= v.len) {
        PyErr_SetString(PyExc_IndexError, "index out of range");
        result.f0 = PREFIX##Error();
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

static PyMappingMethods VecI64Mapping = {
    .mp_length = vec_length,
    .mp_subscript = vec_subscript,
};

static PySequenceMethods VecI64Sequence = {
    .sq_item = vec_get_item,
    .sq_ass_item = vec_ass_item,
};

static PyMethodDef vec_methods[] = {
    {NULL, NULL, 0, NULL},  /* Sentinel */
};

PyTypeObject VecI64BufType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "vecbuf[i64]",
    .tp_doc = "vec doc",
    .tp_basicsize = sizeof(VecI64Object) - sizeof(int64_t),
    .tp_itemsize = sizeof(int64_t),
    .tp_flags = Py_TPFLAGS_DEFAULT,
    //.tp_new = vecbuf_i64_new, //??
    .tp_free = PyObject_Del,
};

PyTypeObject VecI64Type = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "vec[i64]",
    .tp_doc = "vec doc",
    .tp_basicsize = sizeof(VecI64Object),
    .tp_itemsize = 0,
    .tp_flags = Py_TPFLAGS_DEFAULT,
    .tp_new = vec_new,
    //.tp_free = PyObject_Del,
    .tp_dealloc = (destructor)vec_dealloc,
    .tp_repr = (reprfunc)vec_repr,
    .tp_as_sequence = &VecI64Sequence,
    .tp_as_mapping = &VecI64Mapping,
    .tp_richcompare = vec_richcompare,
    .tp_methods = vec_methods,
};

VecI64Features I64Features = {
    &VecI64Type,
    &VecI64BufType,
    PREFIX##New,
    PREFIX##Box,
    PREFIX##Unbox,
    PREFIX##ConvertFromNested,
    PREFIX##Append,
    PREFIX##Pop,
    PREFIX##Remove,
    PREFIX##Slice,
};
