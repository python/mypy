#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "vecs.h"

static VecI64Object *vec_i64_alloc(Py_ssize_t size)
{
    VecI64Object *v;
    /* TODO: Check for overflow */
    v = PyObject_NewVar(VecI64Object, &VecI64Type, size);
    if (v == NULL)
        return NULL;
    return v;
}

PyObject *Vec_I64_New(Py_ssize_t size)
{
    VecI64Object *v;
    v = vec_i64_alloc(size);
    if (v == NULL)
        return NULL;
    for (Py_ssize_t i = 0; i < size; i++) {
        v->items[i] = 0;
    }
    v->len = size;
    return (PyObject *)v;
}

VecI64Object *Vec_I64_FromIterable(PyObject *iterable) {
    VecI64Object *v = vec_i64_alloc(0);
    if (v == NULL)
        return NULL;
    v->len = 0;

    PyObject *iter = PyObject_GetIter(iterable);
    if (iter == NULL) {
        Py_DECREF(v);
        return NULL;
    }
    PyObject *item;
    while ((item = PyIter_Next(iter)) != NULL) {
        int64_t x = PyLong_AsLongLong(item);
        Py_DECREF(item);
        if (x == -1 && PyErr_Occurred()) {
            Py_DECREF(iter);
            Py_DECREF(v);
            return NULL;
        }
        v = (VecI64Object *)Vec_I64_Append((PyObject *)v, x);
        if (v == NULL) {
            Py_DECREF(iter);
            Py_DECREF(v);
            return NULL;
        }
    }
    Py_DECREF(iter);
    if (PyErr_Occurred()) {
        Py_DECREF(v);
        return NULL;
    }
    return v;
}

PyObject *vec_i64_new(PyTypeObject *self, PyObject *args, PyObject *kw) {
    static char *kwlist[] = {"", NULL};
    PyObject *init = NULL;
    if (!PyArg_ParseTupleAndKeywords(args, kw, "|O:vec", kwlist, &init)) {
        return NULL;
    }
    if (init == NULL) {
        return Vec_I64_New(0);
    } else {
        return (PyObject *)Vec_I64_FromIterable(init);
    }
}

PyObject *vec_i64_repr(PyObject *self) {
    return vec_repr(self, I64TypeObj, 0, 0, 1);
}

PyObject *vec_i64_get_item(PyObject *o, Py_ssize_t i) {
    VecI64Object *v = (VecI64Object *)o;
    if ((size_t)i < (size_t)v->len) {
        return PyLong_FromLongLong(v->items[i]);
    } else {
        PyErr_SetString(PyExc_IndexError, "index out of range");
        return NULL;
    }
}

PyObject *vec_i64_subscript(PyObject *self, PyObject *item) {
    VecI64Object *vec = (VecI64Object *)self;
    if (PyIndex_Check(item)) {
        Py_ssize_t i = PyNumber_AsSsize_t(item, PyExc_IndexError);
        if (i == -1 && PyErr_Occurred())
            return NULL;
        if ((size_t)i < (size_t)vec->len) {
            return PyLong_FromLongLong(vec->items[i]);
        } else {
            PyErr_SetString(PyExc_IndexError, "index out of range");
            return NULL;
        }
    } else if (PySlice_Check(item)) {
        Py_ssize_t start, stop, step;
        if (PySlice_Unpack(item, &start, &stop, &step) < 0)
            return NULL;
        Py_ssize_t slicelength = PySlice_AdjustIndices(vec->len, &start, &stop, step);
        VecI64Object *res = vec_i64_alloc(slicelength);
        if (res == NULL)
            return NULL;
        res->len = slicelength;
        Py_ssize_t j = start;
        for (Py_ssize_t i = 0; i < slicelength; i++) {
            res->items[i] = vec->items[j];
            j += step;
        }
        return (PyObject *)res;
    } else {
        PyErr_Format(PyExc_TypeError, "vec indices must be integers or slices, not %.100s",
                     item->ob_type->tp_name);
        return NULL;
    }
}

int vec_i64_ass_item(PyObject *self, Py_ssize_t i, PyObject *o) {
    if (check_float_error(o))
        return -1;
    VecI64Object *v = (VecI64Object *)self;
    if ((size_t)i < (size_t)v->len) {
        long long x = PyLong_AsLongLong(o);
        if (x == -1 && PyErr_Occurred())
            return -1;
        v->items[i] = x;
        return 0;
    } else {
        PyErr_SetString(PyExc_IndexError, "index out of range");
        return -1;
    }
}

static Py_ssize_t vec_length(PyObject *o) {
    // TODO: Type check o
    return ((VecI64Object *)o)->len;
}

static PyObject *vec_i64_richcompare(PyObject *self, PyObject *other, int op) {
    int cmp = 1;
    PyObject *res;
    if (op == Py_EQ || op == Py_NE) {
        if (other->ob_type != &VecI64Type)
            cmp = 0;
        else {
            VecI64Object *x = (VecI64Object *)self;
            VecI64Object *y = (VecI64Object *)other;
            if (x->len != y->len) {
                cmp = 0;
            } else {
                for (Py_ssize_t i = 0; i < x->len; i++) {
                    if (x->items[i] != y->items[i]) {
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

static int Vec_I64_Remove(PyObject *self, int64_t x) {
    VecI64Object *v = (VecI64Object *)self;

    for (Py_ssize_t i = 0; i < v->len; i++) {
        if (v->items[i] == x) {
            for (; i < v->len - 1; i++) {
                v->items[i] = v->items[i + 1];
            }
            v->len--;
            return 1;
        }
    }
    PyErr_SetString(PyExc_ValueError, "vec.remove(x): x not in vec");
    return 0;
}

static PyObject *vec_i64_remove(PyObject *self, PyObject *arg) {
    if (check_float_error(arg))
        return NULL;
    long long x = PyLong_AsLongLong(arg);
    if (x == -1 && PyErr_Occurred())
        return NULL;

    if (!Vec_I64_Remove(self, x))
        return NULL;
    Py_RETURN_NONE;
}

static int64_t Vec_I64_Pop(PyObject *self, Py_ssize_t index) {
    VecI64Object *v = (VecI64Object *)self;
    if (index < 0)
        index += v->len;

    if (index < 0 || index >= v->len) {
        PyErr_SetString(PyExc_IndexError, "index out of range");
        return MYPYC_INT_ERROR;
    }

    int64_t item = v->items[index];
    for (Py_ssize_t i = index; i < v->len - 1; i++)
        v->items[i] = v->items[i + 1];

    v->len--;
    return item;
}

static PyObject *vec_i64_pop(PyObject *self, PyObject *args) {
    Py_ssize_t index = -1;
    if (!PyArg_ParseTuple(args, "|n:pop", &index))
        return NULL;

    int64_t res = Vec_I64_Pop(self, index);
    if (res == MYPYC_INT_ERROR && PyErr_Occurred())
        return NULL;

    return PyLong_FromLongLong(res);
}

static PyMappingMethods VecI64Mapping = {
    .mp_length = vec_length,
    .mp_subscript = vec_i64_subscript,
};

static PySequenceMethods VecI64Sequence = {
    .sq_item = vec_i64_get_item,
    .sq_ass_item = vec_i64_ass_item,
};

static PyMethodDef vec_i64_methods[] = {
    {"remove", vec_i64_remove, METH_O, NULL},
    {"pop", vec_i64_pop, METH_VARARGS, NULL},
    {NULL, NULL, 0, NULL},  /* Sentinel */
};

PyTypeObject VecI64Type = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "vec[i64]",
    .tp_doc = "vec doc",
    .tp_basicsize = sizeof(VecI64Object) - sizeof(int64_t),
    .tp_itemsize = sizeof(int64_t),
    .tp_flags = Py_TPFLAGS_DEFAULT,
    .tp_new = vec_i64_new,
    .tp_free = PyObject_Del,
    .tp_repr = (reprfunc)vec_i64_repr,
    .tp_as_sequence = &VecI64Sequence,
    .tp_as_mapping = &VecI64Mapping,
    .tp_richcompare = vec_i64_richcompare,
    .tp_methods = vec_i64_methods,
};

PyObject *Vec_I64_Append(PyObject *obj, int64_t x) {
    VecI64Object *vec = (VecI64Object *)obj;
    Py_ssize_t cap = VEC_SIZE(vec);
    Py_ssize_t len = vec->len;
    if (len < cap) {
        vec->items[len] = x;
        vec->len = len + 1;
        return (PyObject *)vec;
    } else {
        Py_ssize_t new_size = 2 * cap + 1;
        VecI64Object *new = vec_i64_alloc(new_size);
        if (new == NULL)
            return NULL;
        memcpy(new->items, vec->items, sizeof(int64_t) * len);
        new->items[len] = x;
        new->len = len + 1;
        Py_DECREF(vec);
        return (PyObject *)new;
    }
}

VecI64Features I64Features = {
    &VecI64Type,
    Vec_I64_New,
    Vec_I64_Append,
    Vec_I64_Pop,
    Vec_I64_Remove,
};
