// Implementation of generic vec[t], when t is an optional type or nested generic vec.
//
// Examples of types supported:
//  - vec[str | None]
//  - vec[vec[str]]
//  - vec[vec[str | None] | None]

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "vecs.h"

static inline PyObject *box_vec_item_by_index(VecTExt v, Py_ssize_t index) {
    return Vec_T_Ext_BoxItem(v, v.buf->items[index]);
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
        return box_vec_item_by_index(v, i);
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
            return box_vec_item_by_index(vec, i);
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

int vec_t_ext_ass_item(PyObject *self, Py_ssize_t i, PyObject *o) {
    VecTExt v = ((VecTExtObject *)self)->vec;
    if ((size_t)i < (size_t)v.len) {
        VecbufTExtItem item;
        if (Vec_T_Ext_UnboxItem(v, o, &item) < 0)
            return -1;
        VEC_INCREF(item);
        VEC_DECREF(v.buf->items[i]);
        v.buf->items[i] = item;
        return 0;
    } else {
        PyErr_SetString(PyExc_IndexError, "index out of range");
        return -1;
    }
}

static PyObject *compare_vec_t_ext_eq(VecTExt x, VecTExt y, int op) {
    int cmp = 1;
    PyObject *res;
    if (x.len != y.len
            || x.buf->item_type != y.buf->item_type
            || x.buf->depth != y.buf->depth
            || x.buf->optionals != y.buf->optionals) {
        cmp = 0;
    } else {
        for (Py_ssize_t i = 0; i < x.len; i++) {
            PyObject *x_item = box_vec_item_by_index(x, i);
            PyObject *y_item = box_vec_item_by_index(y, i);
            int itemcmp = PyObject_RichCompareBool(x_item, y_item, Py_EQ);
            Py_DECREF(x_item);
            Py_DECREF(y_item);
            if (itemcmp < 0)
                return NULL;
            if (!itemcmp) {
                cmp = 0;
                break;
            }
        }
    }
    if (op == Py_NE)
        cmp = cmp ^ 1;
    res = cmp ? Py_True : Py_False;
    Py_INCREF(res);
    return res;
}

PyObject *vec_t_ext_richcompare(PyObject *self, PyObject *other, int op) {
    PyObject *res;
    if (op == Py_EQ || op == Py_NE) {
        if (other->ob_type != &VecTExtType) {
            res = op == Py_EQ ? Py_False : Py_True;
        } else {
            return compare_vec_t_ext_eq(((VecTExtObject *)self)->vec,
                                        ((VecTExtObject *)other)->vec, op);
        }
    } else
        res = Py_NotImplemented;
    Py_INCREF(res);
    return res;
}

// Steals reference to vec (but not x)
VecTExt Vec_T_Ext_Append(VecTExt vec, VecbufTExtItem x) {
    Py_ssize_t cap = VEC_CAP(vec);
    VEC_INCREF(x);
    if (vec.len < cap) {
        vec.buf->items[vec.len] = x;
        vec.len++;
        return vec;
    } else {
        Py_ssize_t new_size = 2 * cap + 1;
        // TODO: Avoid initializing to zero here
        VecTExt new = vec_t_ext_alloc(new_size, vec.buf->item_type, vec.buf->optionals,
                                      vec.buf->depth);
        if (VEC_IS_ERROR(new)) {
            VEC_DECREF(x);
            return new;
        }
        // Copy items to new vec.
        memcpy(new.buf->items, vec.buf->items, sizeof(VecbufTExtItem) * vec.len);
        // TODO: How to safely represent deleted items?
        memset(new.buf->items + vec.len, 0, sizeof(VecbufTExtItem) * (new_size - vec.len));
        // Clear the items in the old vec. We avoid reference count manipulation.
        memset(vec.buf->items, 0, sizeof(VecbufTExtItem) * vec.len);
        new.buf->items[vec.len] = x;
        new.len = vec.len + 1;
        VEC_DECREF(vec);
        return new;
    }
}

VecTExt Vec_T_Ext_Remove(VecTExt self, VecbufTExtItem arg) {
    VecbufTExtItem *items = self.buf->items;

    PyObject *boxed_arg = Vec_T_Ext_BoxItem(self, arg);
    if (boxed_arg == NULL)
        return Vec_T_Ext_Error();

    for (Py_ssize_t i = 0; i < self.len; i++) {
        int match = 0;
        if (items[i].len == arg.len && items[i].buf == arg.buf)
            match = 1;
        else {
            PyObject *item = box_vec_item_by_index(self, i);
            if (item == NULL) {
                Py_DECREF(boxed_arg);
                return Vec_T_Ext_Error();
            }
            int itemcmp = PyObject_RichCompareBool(item, boxed_arg, Py_EQ);
            Py_DECREF(item);
            if (itemcmp < 0) {
                Py_DECREF(boxed_arg);
                return Vec_T_Ext_Error();
            }
            match = itemcmp;
        }
        if (match) {
            Py_CLEAR(items[i].buf);
            for (; i < self.len - 1; i++) {
                items[i] = items[i + 1];
            }
            if (self.len > 0)
                Py_XINCREF(items[self.len - 1].buf);
            self.len--;
            Py_INCREF(self.buf);
            Py_DECREF(boxed_arg);
            return self;
        }
    }
    Py_DECREF(boxed_arg);
    PyErr_SetString(PyExc_ValueError, "vec.remove(x): x not in vec");
    return Vec_T_Ext_Error();
}

VecTExtPopResult Vec_T_Ext_Pop(VecTExt v, Py_ssize_t index) {
    VecTExtPopResult result;

    if (index < 0)
        index += v.len;

    if (index < 0 || index >= v.len) {
        PyErr_SetString(PyExc_IndexError, "index out of range");
        result.vec = Vec_T_Ext_Error();
        result.item.len = 0;
        result.item.buf = NULL;
        return result;
    }

    VecbufTExtItem *items = v.buf->items;
    result.item = items[index];
    for (Py_ssize_t i = index; i < v.len - 1; i++)
        items[i] = items[i + 1];
    if (v.len > 0)
        Py_XINCREF(items[v.len - 1].buf);
    v.len--;
    VEC_INCREF(v);
    result.vec = v;
    return result;
}

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
        if (Vec_T_Ext_UnboxItem(v, item, &vecitem) < 0) {
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

VecTExtFeatures TExtFeatures = {
    &VecTExtType,
    &VecbufTExtType,
    Vec_T_Ext_New,
    Vec_T_Ext_Box,
    NULL,  // TODO: unbox
    Vec_T_Ext_Append,
    Vec_T_Ext_Pop,
    Vec_T_Ext_Remove,
    Vec_T_Ext_Slice,
};
