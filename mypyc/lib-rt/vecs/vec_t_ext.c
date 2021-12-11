// Implementation of generic vec[t], when t is an optional type or nested generic vec.
//
// Examples of types supported:
//  - vec[str | None]
//  - vec[vec[str]]
//  - vec[vec[str | None] | None]

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "vecs.h"

// Alloc a partially initialized vec. Caller *must* initialize len and items, and
// call PyObject_GC_Track().
static VecTExtObject *vec_t_ext_alloc(Py_ssize_t size, PyTypeObject *item_type, int32_t optionals,
                                      int32_t depth) {
    VecTExtObject *v = PyObject_GC_NewVar(VecTExtObject, &VecTExtType, size);
    if (v == NULL)
        return NULL;
    Py_INCREF(item_type);
    v->item_type = item_type;
    v->optionals = optionals;
    v->depth = depth;
    return v;
}

PyObject *Vec_T_Ext_New(Py_ssize_t size, PyObject *item_type, int32_t optionals, int32_t depth) {
    VecTExtObject *v;
    v = PyObject_GC_NewVar(VecTExtObject, &VecTExtType, size);
    //v = VecTType.tp_alloc(&VecTType, size);
    if (v == NULL)
        return NULL;

    Py_INCREF(item_type);
    v->item_type = (PyTypeObject *)item_type;
    v->len = size;
    for (Py_ssize_t i = 0; i < size; i++) {
        v->items[i] = NULL;
    }
    v->optionals = optionals;
    v->depth = depth;

    PyObject_GC_Track(v);
    return (PyObject *)v;
}

PyObject *vec_t_ext_repr(PyObject *self) {
    VecTExtObject *v = (VecTExtObject *)self;
    return vec_repr(self, v->item_type, v->depth, v->optionals, 1);
}

PyObject *vec_t_ext_get_item(PyObject *o, Py_ssize_t i) {
    VecTExtObject *v = (VecTExtObject *)o;
    if ((size_t)i < (size_t)v->len) {
        PyObject *item = v->items[i];
        Py_INCREF(item);
        return item;
    } else {
        PyErr_SetString(PyExc_IndexError, "index out of range");
        return NULL;
    }
}

PyObject *vec_t_ext_subscript(PyObject *self, PyObject *item) {
    VecTExtObject *vec = (VecTExtObject *)self;
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
        VecTExtObject *res = vec_t_ext_alloc(slicelength, vec->item_type, vec->optionals,
                                             vec->depth);
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

int vec_t_ext_ass_item(PyObject *self, Py_ssize_t i, PyObject *o) {
    VecTExtObject *v = (VecTExtObject *)self;
    if (!VecTExt_ItemCheck(v, o))
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

PyObject *vec_t_ext_richcompare(PyObject *self, PyObject *other, int op) {
    PyObject *res;
    if (op == Py_EQ || op == Py_NE) {
        if (other->ob_type != &VecTExtType) {
            res = op == Py_EQ ? Py_False : Py_True;
        } else {
            VecTExtObject *x = (VecTExtObject *)self;
            VecTExtObject *y = (VecTExtObject *)other;
            if (x->item_type != y->item_type
                    || x->depth != y->depth
                    || x->optionals != y->optionals) {
                res = op == Py_EQ ? Py_False : Py_True;
            } else
                return vec_generic_richcompare(&x->len, x->items, &y->len, y->items, op);
        }
    } else
        res = Py_NotImplemented;
    Py_INCREF(res);
    return res;
}

static int Vec_T_Ext_Remove(PyObject *self, PyObject *arg) {
    VecTExtObject *v = (VecTExtObject *)self;
    return vec_generic_remove(&v->len, v->items, arg);
}

static PyObject *vec_t_ext_remove(PyObject *self, PyObject *arg) {
    VecTExtObject *v = (VecTExtObject *)self;
    if (!VecTExt_ItemCheck(v, arg))
        return NULL;
    if (!vec_generic_remove(&v->len, v->items, arg))
        return NULL;
    Py_RETURN_NONE;
}

static PyObject *Vec_T_Ext_Pop(PyObject *self, Py_ssize_t index) {
    VecTExtObject *v = (VecTExtObject *)self;
    return vec_generic_pop(&v->len, v->items, index);
}

static PyObject *vec_t_ext_pop(PyObject *self, PyObject *args) {
    VecTExtObject *v = (VecTExtObject *)self;
    return vec_generic_pop_wrapper(&v->len, v->items, args);
}

static int
VecTExt_traverse(VecTExtObject *self, visitproc visit, void *arg)
{
    Py_VISIT(self->item_type);
    for (Py_ssize_t i = 0; i < self->len; i++) {
        Py_VISIT(self->items[i]);
    }
    return 0;
}

static int
VecTExt_clear(VecTExtObject *self)
{
    Py_CLEAR(self->item_type);
    for (Py_ssize_t i = 0; i < self->len; i++) {
        Py_CLEAR(self->items[i]);
    }
    return 0;
}

static void
VecTExt_dealloc(VecTExtObject *self)
{
    PyObject_GC_UnTrack(self);
    Py_TRASHCAN_BEGIN(self, VecTExt_dealloc)
    Py_XDECREF(self->item_type);
    for (Py_ssize_t i = 0; i < self->len; i++) {
        Py_XDECREF(self->items[i]);
    }
    Py_TYPE(self)->tp_free((PyObject *)self);
    Py_TRASHCAN_END
}

static Py_ssize_t vec_ext_length(PyObject *o) {
    // TODO: Type check o
    return ((VecTExtObject *)o)->len;
}

static PyMappingMethods VecTExtMapping = {
    .mp_length = vec_ext_length,
    .mp_subscript = vec_t_ext_subscript,
};

static PySequenceMethods VecTExtSequence = {
    .sq_item = vec_t_ext_get_item,
    .sq_ass_item = vec_t_ext_ass_item,
};

static PyMethodDef vec_t_ext_methods[] = {
    {"remove", vec_t_ext_remove, METH_O, NULL},
    {"pop", vec_t_ext_pop, METH_VARARGS, NULL},
    {NULL, NULL, 0, NULL},  /* Sentinel */
};

PyTypeObject VecTExtType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "vec",
    .tp_doc = "vec doc",
    .tp_basicsize = sizeof(VecTExtObject) - sizeof(PyObject *),
    .tp_itemsize = sizeof(PyObject *),
    .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC,
    .tp_traverse = (traverseproc)VecTExt_traverse,
    .tp_clear = (inquiry)VecTExt_clear,
    .tp_dealloc = (destructor)VecTExt_dealloc,
    //.tp_free = PyObject_GC_Del,
    .tp_repr = (reprfunc)vec_t_ext_repr,
    .tp_as_sequence = &VecTExtSequence,
    .tp_as_mapping = &VecTExtMapping,
    .tp_richcompare = vec_t_ext_richcompare,
    .tp_methods = vec_t_ext_methods,
    // TODO: free
};

VecTExtObject *Vec_T_Ext_FromIterable(PyTypeObject *item_type, int32_t optionals, int32_t depth,
                                      PyObject *iterable) {
    VecTExtObject *v = PyObject_GC_NewVar(VecTExtObject, &VecTExtType, 0);
    if (v == NULL)
        return NULL;
    v->len = 0;
    Py_INCREF(item_type);
    v->item_type = item_type;
    v->optionals = optionals;
    v->depth = depth;
    PyObject_GC_Track(v);

    PyObject *iter = PyObject_GetIter(iterable);
    if (iter == NULL) {
        Py_DECREF(v);
        return NULL;
    }
    PyObject *item;
    while ((item = PyIter_Next(iter)) != NULL) {
        if (!VecTExt_ItemCheck(v, item)) {
            Py_DECREF(iter);
            Py_DECREF(v);
            Py_DECREF(item);
            return NULL;
        }
        v = (VecTExtObject *)Vec_T_Ext_Append((PyObject *)v, item);
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

PyObject *Vec_T_Ext_Append(PyObject *obj, PyObject *x) {
    VecTExtObject *vec = (VecTExtObject *)obj;
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
        VecTExtObject *new = (VecTExtObject *)Vec_T_Ext_New(
            new_size, (PyObject *)vec->item_type, vec->optionals, vec->depth);
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

VecTExtFeatures TExtFeatures = {
    &VecTExtType,
    Vec_T_Ext_New,
    Vec_T_Ext_Append,
    Vec_T_Ext_Pop,
    Vec_T_Ext_Remove,
};
