// Implementation of generic vec[t], when t is an optional type or nested generic vec.
//
// Examples of types supported:
//  - vec[str | None]
//  - vec[vec[str]]
//  - vec[vec[str | None] | None]

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "vecs.h"

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
                return vec_generic_richcompare(x->len, x->items, y->len, y->items, op);
        }
    } else
        res = Py_NotImplemented;
    Py_INCREF(res);
    return res;
}

static int
VecTExt_traverse(VecTExtObject *self, visitproc visit, void *arg)
{
    Py_VISIT(self->item_type);
    for (Py_ssize_t i = 0; i < self->len; i++) {
        // TODO: NULL checks?
        Py_VISIT(self->items[i]);
    }
    return 0;
}

static int
VecTExt_clear(VecTExtObject *self)
{
    Py_CLEAR(self->item_type);
    for (Py_ssize_t i = 0; i < self->len; i++) {
        // TODO: NULL checks?
        Py_CLEAR(self->items[i]);
    }
    return 0;
}

static void
VecTExt_dealloc(VecTExtObject *self)
{
    PyObject_GC_UnTrack(self);
    Py_TRASHCAN_BEGIN(self, VecTExt_dealloc)
    VecTExt_clear(self);
    //Py_DECREF(self->item_type);
    //for (Py_ssize_t i = 0; i < self->len; i++) {
    //    Py_XDECREF(self->items[i]);
    //}
    //PyObject_GC_Del(self);
    Py_TYPE(self)->tp_free((PyObject *)self);
    Py_TRASHCAN_END
}

static Py_ssize_t vec_ext_length(PyObject *o) {
    // TODO: Type check o
    return ((VecTExtObject *)o)->len;
}

static PyMappingMethods VecTExtMapping = {
    .mp_length = vec_ext_length,
};

static PySequenceMethods VecTExtSequence = {
    .sq_item = vec_t_ext_get_item,
    .sq_ass_item = vec_t_ext_ass_item,
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
    // TODO: free
};

VecTExtObject *Vec_T_Ext_New(Py_ssize_t size, PyTypeObject *item_type, int32_t optionals,
                             int32_t depth) {
    VecTExtObject *v;
    v = PyObject_GC_NewVar(VecTExtObject, &VecTExtType, size);
    //v = VecTType.tp_alloc(&VecTType, size);
    if (v == NULL)
        return NULL;

    v->item_type = item_type;
    v->len = size;
    for (Py_ssize_t i = 0; i < size; i++) {
        v->items[i] = NULL;
    }
    v->optionals = optionals;
    v->depth = depth;

    PyObject_GC_Track(v);
    return v;
}

VecTExtObject *Vec_T_Ext_FromIterable(PyTypeObject *item_type, int32_t optionals, int32_t depth,
                                      PyObject *iterable) {
    VecTExtObject *v = PyObject_GC_NewVar(VecTExtObject, &VecTExtType, 0);
    if (v == NULL)
        return NULL;
    v->len = 0;
    v->item_type = item_type;
    v->optionals = optionals;
    v->depth = depth;

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
        VecTExtObject *new = Vec_T_Ext_New(new_size, vec->item_type, vec->optionals, vec->depth);
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
