#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "vecs.h"

//static PyObject *vec_t_new(PyTypeObject *self, PyObject *args, PyObject *kw);

PyObject *vec_t_repr(PyObject *self) {
    // TODO: Type check, refcounting, error handling
    VecTObject *o = (VecTObject *)self;
    // TODO: Display actual type
    PyObject *prefix = Py_BuildValue("s", "vec[");
    PyObject *mid = Py_BuildValue("s", "]([");
    PyObject *suffix = Py_BuildValue("s", "])");
    PyObject *l = Py_BuildValue("[]");
    PyObject *sep = Py_BuildValue("s", "");
    PyObject *comma = Py_BuildValue("s", ", ");
    PyList_Append(l, prefix);
    PyList_Append(l, PyObject_GetAttrString(o->item_type, "__name__"));
    PyList_Append(l, mid);
    for (int i = 0; i < o->len; i++) {
        PyObject *r = PyObject_Repr(o->items[i]);
        if (r == NULL) {
            return NULL;
        }
        PyList_Append(l, r);
        if (i + 1 < o->len)
            PyList_Append(l, comma);
    }
    PyList_Append(l, suffix);
    return PyUnicode_Join(sep, l);
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

PyTypeObject VecTType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "vec[t]",
    .tp_doc = "vec doc",
    .tp_basicsize = sizeof(VecTObject) - sizeof(PyObject *),
    .tp_itemsize = sizeof(PyObject *),
    .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC,
    .tp_traverse = (traverseproc)VecT_traverse,
    .tp_clear = (inquiry)VecT_clear,
    .tp_dealloc = (destructor)VecT_dealloc,
    //.tp_free = PyObject_GC_Del,
    .tp_repr = (reprfunc)vec_t_repr,
    //.tp_as_sequence = &VecI64Sequence,
    //.tp_as_mapping = &VecI64Mapping,
    // TODO: free
};

PyObject *Vec_T_New(Py_ssize_t size, PyObject *item_type)
{
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
    return (PyObject *)v;
}
