// Implementation of generic vec[t], when t is a plain type object.
//
// Examples of types supported:
//
//  - vec[str]
//  - vec[object]
//  - vec[UserClass]

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "vecs.h"

// Alloc a partially initialized vec. Caller *must* initialize len and items, and
// call PyObject_GC_Track().
static VecTObject *vec_t_alloc(Py_ssize_t size, PyTypeObject *item_type) {
    VecTObject *v = PyObject_GC_NewVar(VecTObject, &VecTType, size);
    if (v == NULL)
        return NULL;
    Py_INCREF(item_type);
    v->item_type = item_type;
    return v;
}

VecTObject *Vec_T_New(Py_ssize_t size, PyTypeObject *item_type) {
    VecTObject *v;
    v = PyObject_GC_NewVar(VecTObject, &VecTType, size);
    //v = VecTType.tp_alloc(&VecTType, size);
    if (v == NULL)
        return NULL;

    Py_INCREF(item_type);
    v->item_type = item_type;
    v->len = size;
    for (Py_ssize_t i = 0; i < size; i++) {
        v->items[i] = NULL;
    }

    PyObject_GC_Track(v);
    return v;
}

PyObject *vec_t_repr(PyObject *self) {
    VecTObject *v = (VecTObject *)self;
    return vec_repr(self, v->item_type, 0, 0, 1);
}

PyObject *vec_t_get_item(PyObject *o, Py_ssize_t i) {
    VecTObject *v = (VecTObject *)o;
    if ((size_t)i < (size_t)v->len) {
        PyObject *item = v->items[i];
        Py_INCREF(item);
        return item;
    } else {
        PyErr_SetString(PyExc_IndexError, "index out of range");
        return NULL;
    }
}

PyObject *vec_t_subscript(PyObject *self, PyObject *item) {
    VecTObject *vec = (VecTObject *)self;
    if (PyIndex_Check(item)) {
        Py_ssize_t i = PyNumber_AsSsize_t(item, PyExc_IndexError);
        if (i == -1 && PyErr_Occurred())
            return NULL;
        if ((size_t)i < (size_t)vec->len) {
            PyObject *item = vec->items[i];
            Py_INCREF(item);
            return item;
        } else {
            PyErr_SetString(PyExc_IndexError, "index out of range");
            return NULL;
        }
    } else if (PySlice_Check(item)) {
        Py_ssize_t start, stop, step;
        if (PySlice_Unpack(item, &start, &stop, &step) < 0)
            return NULL;
        Py_ssize_t slicelength = PySlice_AdjustIndices(vec->len, &start, &stop, step);
        VecTObject *res = vec_t_alloc(slicelength, vec->item_type);
        if (res == NULL)
            return NULL;
        res->len = slicelength;
        Py_ssize_t j = start;
        for (Py_ssize_t i = 0; i < slicelength; i++) {
            PyObject *item = vec->items[j];
            Py_INCREF(item);
            res->items[i] = item;
            j += step;
        }
        PyObject_GC_Track(res);
        return (PyObject *)res;
    } else {
        PyErr_Format(PyExc_TypeError, "vec indices must be integers or slices, not %.100s",
                     item->ob_type->tp_name);
        return NULL;
    }
}

int vec_t_ass_item(PyObject *self, Py_ssize_t i, PyObject *o) {
    VecTObject *v = (VecTObject *)self;
    if (!VecT_ItemCheck(v, o))
        return -1;
    if ((size_t)i < (size_t)v->len) {
        Py_INCREF(o);
        v->items[i] = o;
        return 0;
    } else {
        PyErr_SetString(PyExc_IndexError, "index out of range");
        return -1;
    }
}

PyObject *vec_t_richcompare(PyObject *self, PyObject *other, int op) {
    PyObject *res;
    if (op == Py_EQ || op == Py_NE) {
        if (other->ob_type != &VecTType) {
            res = op == Py_EQ ? Py_False : Py_True;
        } else {
            VecTObject *x = (VecTObject *)self;
            VecTObject *y = (VecTObject *)other;
            if (x->item_type != y->item_type) {
                res = op == Py_EQ ? Py_False : Py_True;
            } else
                return vec_generic_richcompare(&x->len, x->items, &y->len, y->items, op);
        }
    } else
        res = Py_NotImplemented;
    Py_INCREF(res);
    return res;
}

static PyObject *vec_t_remove(PyObject *self, PyObject *arg) {
    VecTObject *v = (VecTObject *)self;
    if (!VecT_ItemCheck(v, arg))
        return NULL;
    return vec_generic_remove(&v->len, v->items, arg);
}

static int
VecT_traverse(VecTObject *self, visitproc visit, void *arg)
{
    Py_VISIT(self->item_type);
    for (Py_ssize_t i = 0; i < self->len; i++) {
        Py_VISIT(self->items[i]);
    }
    return 0;
}

static int
VecT_clear(VecTObject *self)
{
    Py_CLEAR(self->item_type);
    for (Py_ssize_t i = 0; i < self->len; i++) {
        Py_CLEAR(self->items[i]);
    }
    return 0;
}

static void
VecT_dealloc(VecTObject *self)
{
    PyObject_GC_UnTrack(self);
    Py_TRASHCAN_BEGIN(self, VecT_dealloc)
    VecT_clear(self);
    //Py_DECREF(self->item_type);
    //for (Py_ssize_t i = 0; i < self->len; i++) {
    //    Py_XDECREF(self->items[i]);
    //}
    //PyObject_GC_Del(self);
    Py_TYPE(self)->tp_free((PyObject *)self);
    Py_TRASHCAN_END
}

static Py_ssize_t vec_length(PyObject *o) {
    // TODO: Type check o
    return ((VecTObject *)o)->len;
}

static PyMappingMethods VecTMapping = {
    .mp_length = vec_length,
    .mp_subscript = vec_t_subscript,
};

static PySequenceMethods VecTSequence = {
    .sq_item = vec_t_get_item,
    .sq_ass_item = vec_t_ass_item,
};

static PyMethodDef vec_t_methods[] = {
    {"remove", vec_t_remove, METH_O, NULL},
    {NULL, NULL, 0, NULL},  /* Sentinel */
};

PyTypeObject VecTType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "vec",
    .tp_doc = "vec doc",
    .tp_basicsize = sizeof(VecTObject) - sizeof(PyObject *),
    .tp_itemsize = sizeof(PyObject *),
    .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC,
    .tp_traverse = (traverseproc)VecT_traverse,
    .tp_clear = (inquiry)VecT_clear,
    .tp_dealloc = (destructor)VecT_dealloc,
    //.tp_free = PyObject_GC_Del,
    .tp_repr = (reprfunc)vec_t_repr,
    .tp_as_sequence = &VecTSequence,
    .tp_as_mapping = &VecTMapping,
    .tp_richcompare = vec_t_richcompare,
    .tp_methods = vec_t_methods,
    // TODO: free
};

VecTObject *Vec_T_FromIterable(PyTypeObject *item_type, PyObject *iterable) {
    VecTObject *v = PyObject_GC_NewVar(VecTObject, &VecTType, 0);
    if (v == NULL)
        return NULL;
    v->len = 0;
    Py_INCREF(item_type);
    v->item_type = item_type;
    PyObject_GC_Track(v);

    PyObject *iter = PyObject_GetIter(iterable);
    if (iter == NULL) {
        Py_DECREF(v);
        return NULL;
    }
    PyObject *item;
    while ((item = PyIter_Next(iter)) != NULL) {
        if (!VecT_ItemCheck(v, item)) {
            Py_DECREF(iter);
            Py_DECREF(v);
            Py_DECREF(item);
            return NULL;
        }
        v = (VecTObject *)Vec_T_Append((PyObject *)v, item);
        Py_DECREF(item);
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

PyObject *Vec_T_Append(PyObject *obj, PyObject *x) {
    VecTObject *vec = (VecTObject *)obj;
    Py_ssize_t cap = VEC_SIZE(vec);
    Py_ssize_t len = vec->len;
    Py_INCREF(x);
    if (len < cap) {
        vec->items[len] = x;
        vec->len = len + 1;
        return (PyObject *)vec;
    } else {
        Py_ssize_t new_size = 2 * cap + 1;
        // TODO: Avoid initializing to zero here
        VecTObject *new = Vec_T_New(new_size, vec->item_type);
        if (new == NULL)
            return NULL;
        memcpy(new->items, vec->items, sizeof(PyObject *) * len);
        memset(vec->items, 0, sizeof(PyObject *) * len);
        new->items[len] = x;
        new->len = len + 1;
        Py_DECREF(vec);
        return (PyObject *)new;
    }
}
