// Implementation of generic vec[t], when t is an optional type or nested generic vec.
//
// Examples of types supported:
//  - vec[str | None]
//  - vec[vec[str]]
//  - vec[vec[str | None] | None]

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "vecs.h"

static inline PyObject *box_vec_item(VecTExt v, Py_ssize_t index) {
    VecbufTExtItem item = v.buf->items[index];
    if (item.len < 0)
        Py_RETURN_NONE;
    Py_INCREF(item.buf);
    if (v.buf->depth > 1) {
        // Item is a nested vec
        VecTExt v = { .len = item.len, .buf = (VecbufTExtObject *)item.buf };
        return Vec_T_Ext_Box(v);
    } else {
        // Item is a non-nested vec
        void *item_type = (void *)(v.buf->item_type & ~1);
        if (item_type == I64TypeObj) {
            // vec[i64]
            VecI64 v = { .len = item.len, .buf = (VecbufI64Object *)item.buf };
            return Vec_I64_Box(v);
        } else {
            // Generic vec[t]
            VecT v = { .len = item.len, .buf = (VecbufTObject *)item.buf };
            return Vec_T_Box(v);
        }
    }
}

// Return 0 on success, -1 on error
static inline int unbox_vec_item(VecTExt v, PyObject *item, VecbufTExtItem *unboxed) {
    int optionals = v.buf->optionals;
    if (item == Py_None && (optionals & 1)) {
        unboxed->len = -1;
        return 0;
    }
    int depth = v.buf->depth;
    if (depth == 1) {
        // TODO: vec[i64]
        if (item->ob_type == &VecTType) {
            VecTExtObject *o = (VecTExtObject *)item;
            if (o->vec.buf->item_type == v.buf->item_type) {
                unboxed->len = o->vec.len;
                unboxed->buf = (PyObject *)o->vec.buf;
                Py_INCREF(unboxed->buf);
                return 1;
            }
        } else if (item->ob_type == &VecI64Type && v.buf->item_type == (size_t)I64TypeObj) {
            VecI64Object *o = (VecI64Object *)item;
            unboxed->len = o->vec.len;
            unboxed->buf = (PyObject *)o->vec.buf;
            Py_INCREF(unboxed->buf);
            return 1;
        }
    } else if (item->ob_type == &VecTExtType) {
        VecTExtObject *o = (VecTExtObject *)item;
        if (o->vec.buf->depth == v.buf->depth - 1
            && o->vec.buf->item_type == v.buf->item_type
            && o->vec.buf->optionals == (optionals >> 1)) {
            unboxed->len = o->vec.len;
            unboxed->buf = (PyObject *)o->vec.buf;
            Py_INCREF(unboxed->buf);
            return 1;
        }
    }
    // TODO: better error message
    PyErr_SetString(PyExc_TypeError, "invalid item type");
    return 0;
}

// Alloc a partially initialized vec. Caller *must* initialize len and buf->items.
static VecTExt vec_t_ext_alloc(Py_ssize_t size, size_t item_type, int32_t optionals,
                               int32_t depth) {
    VecbufTExtObject *buf = PyObject_GC_NewVar(VecbufTExtObject, &VecbufTExtType, size);
    if (buf == NULL)
        return Vec_T_Ext_Error();
    buf->item_type = item_type;
    buf->optionals = optionals;
    buf->depth = depth;
    Py_INCREF(BUF_ITEM_TYPE(buf));
    VecTExt res = { .buf = buf };
    PyObject_GC_Track(buf);
    return res;
}

PyObject *Vec_T_Ext_Box(VecTExt vec) {
    VecTExtObject *obj = PyObject_GC_New(VecTExtObject, &VecTExtType);
    if (obj == NULL)
        return NULL;
    obj->vec = vec;
    PyObject_GC_Track(obj);
    return (PyObject *)obj;
}

VecTExt Vec_T_Ext_New(Py_ssize_t size, size_t item_type, int32_t optionals, int32_t depth) {
    VecTExt vec = vec_t_ext_alloc(size, item_type, optionals, depth);
    if (VEC_IS_ERROR(vec))
        return vec;
    for (Py_ssize_t i = 0; i < size; i++) {
        vec.buf->items[i].len = -1;
        vec.buf->items[i].buf = NULL;
    }
    vec.len = size;
    return vec;
}

PyObject *vec_t_ext_repr(PyObject *self) {
    VecTExt v = ((VecTExtObject *)self)->vec;
    return vec_repr(self, v.buf->item_type, v.buf->depth, v.buf->optionals, 1);
}

PyObject *vec_t_ext_get_item(PyObject *o, Py_ssize_t i) {
    VecTExt v = ((VecTExtObject *)o)->vec;
    if ((size_t)i < (size_t)v.len) {
        return box_vec_item(v, i);
    } else {
        PyErr_SetString(PyExc_IndexError, "index out of range");
        return NULL;
    }
}

VecTExt Vec_T_Ext_Slice(VecTExt vec, int64_t start, int64_t end) {
    if (start < 0)
        start += vec.len;
    if (end < 0)
        end += vec.len;
    if (end < start)
        end = start;
    if (start < 0)
        start = 0;
    if (end > vec.len)
        end = vec.len;
    int64_t slicelength = end - start;
    VecTExt res = vec_t_ext_alloc(slicelength, vec.buf->item_type, vec.buf->optionals,
                                  vec.buf->depth);
    if (VEC_IS_ERROR(res))
        return res;
    res.len = slicelength;
    for (Py_ssize_t i = 0; i < slicelength; i++) {
        VecbufTExtItem item = vec.buf->items[start + i];
        Py_INCREF(item.buf);
        res.buf->items[i] = item;
    }
    return res;
}

PyObject *vec_t_ext_subscript(PyObject *self, PyObject *item) {
    VecTExt vec = ((VecTExtObject *)self)->vec;
    if (PyIndex_Check(item)) {
        Py_ssize_t i = PyNumber_AsSsize_t(item, PyExc_IndexError);
        if (i == -1 && PyErr_Occurred())
            return NULL;
        if ((size_t)i < (size_t)vec.len) {
            return box_vec_item(vec, i);
        } else {
            PyErr_SetString(PyExc_IndexError, "index out of range");
            return NULL;
        }
    } else if (PySlice_Check(item)) {
        Py_ssize_t start, stop, step;
        if (PySlice_Unpack(item, &start, &stop, &step) < 0)
            return NULL;
        Py_ssize_t slicelength = PySlice_AdjustIndices(vec.len, &start, &stop, step);
        VecTExt res = vec_t_ext_alloc(slicelength, vec.buf->item_type, vec.buf->optionals,
                                      vec.buf->depth);
        if (VEC_IS_ERROR(res))
            return NULL;
        res.len = slicelength;
        Py_ssize_t j = start;
        for (Py_ssize_t i = 0; i < slicelength; i++) {
            VecbufTExtItem item = vec.buf->items[j];
            Py_INCREF(item.buf);
            res.buf->items[i] = item;
            j += step;
        }
        return Vec_T_Ext_Box(res);
    } else {
        PyErr_Format(PyExc_TypeError, "vec indices must be integers or slices, not %.100s",
                     item->ob_type->tp_name);
        return NULL;
    }
}

#if 0

int vec_t_ext_ass_item(PyObject *self, Py_ssize_t i, PyObject *o) {
    // TODO
    VecTExt v = ((VecTExtObject *)self)->vec;
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
    // TODO
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
    // TODO
    VecTExtObject *v = (VecTExtObject *)self;
    return vec_generic_remove(&v->len, v->items, arg);
}

static PyObject *vec_t_ext_remove(PyObject *self, PyObject *arg) {
    // TODO
    VecTExtObject *v = (VecTExtObject *)self;
    if (!VecTExt_ItemCheck(v, arg))
        return NULL;
    if (!vec_generic_remove(&v->len, v->items, arg))
        return NULL;
    Py_RETURN_NONE;
}

static VecTExt Vec_T_Ext_Pop(VecTExt vec, Py_ssize_t index, PyObject **result) {
    // TODO
    return Vec_T_Ext_Error();
}

static PyObject *vec_t_ext_pop(PyObject *self, PyObject *args) {
    // TODO
    VecTExtObject *v = (VecTExtObject *)self;
    return vec_generic_pop_wrapper(&v->len, v->items, args);
}

#endif

static int
VecTExt_traverse(VecTObject *self, visitproc visit, void *arg)
{
    Py_VISIT(self->vec.buf);
    return 0;
}

static int
VecTExt_clear(VecTObject *self)
{
    Py_CLEAR(self->vec.buf);
    return 0;
}

static void
VecTExt_dealloc(VecTObject *self)
{
    PyObject_GC_UnTrack(self);
    Py_TRASHCAN_BEGIN(self, VecTExt_dealloc)
    Py_CLEAR(self->vec.buf);
    Py_TYPE(self)->tp_free((PyObject *)self);
    Py_TRASHCAN_END
}

static int
VecbufTExt_traverse(VecbufTExtObject *self, visitproc visit, void *arg)
{
    Py_VISIT(BUF_ITEM_TYPE(self));
    for (Py_ssize_t i = 0; i < BUF_SIZE(self); i++) {
        Py_VISIT(self->items[i].buf);
    }
    return 0;
}

static int
VecbufTExt_clear(VecbufTExtObject *self)
{
    if (self->item_type) {
        Py_DECREF(BUF_ITEM_TYPE(self));
        self->item_type = 0;
    }
    for (Py_ssize_t i = 0; i < BUF_SIZE(self); i++) {
        Py_CLEAR(self->items[i].buf);
    }
    return 0;
}

static void
VecbufTExt_dealloc(VecbufTExtObject *self)
{
    PyObject_GC_UnTrack(self);
    Py_TRASHCAN_BEGIN(self, VecbufTExt_dealloc)
    if (self->item_type) {
        Py_DECREF(BUF_ITEM_TYPE(self));
        self->item_type = 0;
    }
    for (Py_ssize_t i = 0; i < BUF_SIZE(self); i++) {
        Py_CLEAR(self->items[i].buf);
    }
    Py_TYPE(self)->tp_free((PyObject *)self);
    Py_TRASHCAN_END
}

static Py_ssize_t vec_ext_length(PyObject *o) {
    // TODO: Type check o
    return ((VecTExtObject *)o)->vec.len;
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

PyTypeObject VecbufTExtType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "vecbuf",
    .tp_doc = "vec doc",
    .tp_basicsize = sizeof(VecbufTExtObject) - sizeof(VecbufTExtItem),
    .tp_itemsize = sizeof(VecbufTExtItem),
    .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC,
    .tp_traverse = (traverseproc)VecbufTExt_traverse,
    //.tp_new = vecbuf_i64_new, //??
    .tp_free = PyObject_GC_Del,
    .tp_clear = (inquiry)VecbufTExt_clear,
    .tp_dealloc = (destructor)VecbufTExt_dealloc,
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

PyObject *Vec_T_Ext_FromIterable(size_t item_type, int32_t optionals, int32_t depth,
                                 PyObject *iterable) {
    VecTExt v = vec_t_ext_alloc(0, item_type, optionals, depth);
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
        VecbufTExtItem vecitem;
        if (unbox_vec_item(v, item, &vecitem) < 0) {
            Py_DECREF(iter);
            VEC_DECREF(v);
            Py_DECREF(item);
            return NULL;
        }
        v = Vec_T_Ext_Append(v, vecitem);
        Py_DECREF(item);
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
    return Vec_T_Ext_Box(v);
}

#if 0

PyObject *Vec_T_Ext_Append(PyObject *obj, PyObject *x) {
    // TODO
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
    &VecbufTExtType,
    Vec_T_Ext_New,
    Vec_T_Ext_Box,
    Vec_T_Ext_Append,
    Vec_T_Ext_Pop,
    Vec_T_Ext_Remove,
    Vec_T_Ext_Slice,
};

#endif
