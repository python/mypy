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

//static PyObject *vec_t_new(PyTypeObject *self, PyObject *args, PyObject *kw);

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
};

static PySequenceMethods VecTSequence = {
    .sq_item = vec_t_get_item,
    .sq_ass_item = vec_t_ass_item,
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
    // TODO: free
};

VecTObject *Vec_T_New(Py_ssize_t size, PyTypeObject *item_type) {
    VecTObject *v;
    v = PyObject_GC_NewVar(VecTObject, &VecTType, size);
    //v = VecTType.tp_alloc(&VecTType, size);
    if (v == NULL)
        return NULL;

    v->item_type = item_type;
    v->len = size;
    for (Py_ssize_t i = 0; i < size; i++) {
        v->items[i] = NULL;
    }

    PyObject_GC_Track(v);
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
