#ifdef MYPYC_EXPERIMENTAL
// Implementation of nested vec[t], when t is a vec type.
//
// Examples of types supported:
//  - vec[vec[i64]]
//  - vec[vec[vec[str]]]
//  - vec[vec[str | None]]

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "librt_vecs.h"
#include "vecs_internal.h"

static inline VecNested vec_error() {
    VecNested v = { .len = -1 };
    return v;
}

static inline PyObject *box_vec_item_by_index(VecNested v, Py_ssize_t index) {
    return VecNested_BoxItem(v, v.buf->items[index]);
}

// Alloc a partially initialized vec. Caller *must* initialize len and buf->items of the
// return value.
static VecNested vec_alloc(Py_ssize_t size, size_t item_type, size_t depth) {
    VecNestedBufObject *buf = PyObject_GC_NewVar(VecNestedBufObject, &VecNestedBufType, size);
    if (buf == NULL)
        return vec_error();
    buf->item_type = item_type;
    buf->depth = depth;
    if (!Vec_IsMagicItemType(item_type))
        Py_INCREF(VEC_BUF_ITEM_TYPE(buf));
    VecNested res = { .buf = buf };
    PyObject_GC_Track(buf);
    return res;
}

// Box a nested vec value, stealing 'vec'. On error, decref 'vec'.
PyObject *VecNested_Box(VecNested vec) {
    VecNestedObject *obj = PyObject_GC_New(VecNestedObject, &VecNestedType);
    if (obj == NULL) {
        VEC_DECREF(vec);
        return NULL;
    }
    obj->vec = vec;
    PyObject_GC_Track(obj);
    return (PyObject *)obj;
}

VecNested VecNested_Unbox(PyObject *obj, size_t item_type, size_t depth) {
    if (obj->ob_type == &VecNestedType) {
        VecNested result = ((VecNestedObject *)obj)->vec;
        if (result.buf->item_type == item_type && result.buf->depth == depth) {
            VEC_INCREF(result);  // TODO: Should we borrow instead?
            return result;
        }
    }
    // TODO: Better error message, with name of type
    PyErr_SetString(PyExc_TypeError, "vec[t] expected");
    return vec_error();
}

VecNested VecNested_ConvertFromNested(VecNestedBufItem item) {
    return (VecNested) { item.len, (VecNestedBufObject *)item.buf };
}

VecNested VecNested_New(Py_ssize_t size, Py_ssize_t cap, size_t item_type, size_t depth) {
    if (cap < size)
        cap = size;
    VecNested vec = vec_alloc(cap, item_type, depth);
    if (VEC_IS_ERROR(vec))
        return vec;
    for (Py_ssize_t i = 0; i < cap; i++) {
        vec.buf->items[i].len = -1;
        vec.buf->items[i].buf = NULL;
    }
    vec.len = size;
    return vec;
}

static PyObject *vec_repr(PyObject *self) {
    VecNested v = ((VecNestedObject *)self)->vec;
    return Vec_GenericRepr(self, v.buf->item_type, v.buf->depth, 1);
}

static PyObject *vec_get_item(PyObject *o, Py_ssize_t i) {
    VecNested v = ((VecNestedObject *)o)->vec;
    if ((size_t)i < (size_t)v.len) {
        return box_vec_item_by_index(v, i);
    } else if ((size_t)i + (size_t)v.len < (size_t)v.len) {
        return box_vec_item_by_index(v, i + v.len);
    } else {
        PyErr_SetString(PyExc_IndexError, "index out of range");
        return NULL;
    }
}

VecNested VecNested_Slice(VecNested vec, int64_t start, int64_t end) {
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
    VecNested res = vec_alloc(slicelength, vec.buf->item_type, vec.buf->depth);
    if (VEC_IS_ERROR(res))
        return res;
    res.len = slicelength;
    for (Py_ssize_t i = 0; i < slicelength; i++) {
        VecNestedBufItem item = vec.buf->items[start + i];
        Py_XINCREF(item.buf);
        res.buf->items[i] = item;
    }
    return res;
}

static PyObject *vec_subscript(PyObject *self, PyObject *item) {
    VecNested vec = ((VecNestedObject *)self)->vec;
    if (PyIndex_Check(item)) {
        Py_ssize_t i = PyNumber_AsSsize_t(item, PyExc_IndexError);
        if (i == -1 && PyErr_Occurred())
            return NULL;
        if ((size_t)i < (size_t)vec.len) {
            return box_vec_item_by_index(vec, i);
        } else if ((size_t)i + (size_t)vec.len < (size_t)vec.len) {
            return box_vec_item_by_index(vec, i + vec.len);
        } else {
            PyErr_SetString(PyExc_IndexError, "index out of range");
            return NULL;
        }
    } else if (PySlice_Check(item)) {
        Py_ssize_t start, stop, step;
        if (PySlice_Unpack(item, &start, &stop, &step) < 0)
            return NULL;
        Py_ssize_t slicelength = PySlice_AdjustIndices(vec.len, &start, &stop, step);
        VecNested res = vec_alloc(slicelength, vec.buf->item_type, vec.buf->depth);
        if (VEC_IS_ERROR(res))
            return NULL;
        res.len = slicelength;
        Py_ssize_t j = start;
        for (Py_ssize_t i = 0; i < slicelength; i++) {
            VecNestedBufItem item = vec.buf->items[j];
            Py_INCREF(item.buf);
            res.buf->items[i] = item;
            j += step;
        }
        return VecNested_Box(res);
    } else {
        PyErr_Format(PyExc_TypeError, "vec indices must be integers or slices, not %.100s",
                     item->ob_type->tp_name);
        return NULL;
    }
}

static int vec_ass_item(PyObject *self, Py_ssize_t i, PyObject *o) {
    VecNested v = ((VecNestedObject *)self)->vec;
    if ((size_t)i + (size_t)v.len < (size_t)v.len) {
        i += v.len;
    }
    if ((size_t)i < (size_t)v.len) {
        VecNestedBufItem item;
        if (VecNested_UnboxItem(v, o, &item) < 0)
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

static PyObject *compare_vec_eq(VecNested x, VecNested y, int op) {
    int cmp = 1;
    PyObject *res;
    if (x.len != y.len
            || x.buf->item_type != y.buf->item_type
            || x.buf->depth != y.buf->depth) {
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

PyObject *vec_richcompare(PyObject *self, PyObject *other, int op) {
    PyObject *res;
    if (op == Py_EQ || op == Py_NE) {
        if (other->ob_type != &VecNestedType) {
            res = op == Py_EQ ? Py_False : Py_True;
        } else {
            return compare_vec_eq(((VecNestedObject *)self)->vec,
                                        ((VecNestedObject *)other)->vec, op);
        }
    } else
        res = Py_NotImplemented;
    Py_INCREF(res);
    return res;
}

// Append item to 'vec', stealing 'vec'. Return 'vec' with item appended.
VecNested VecNested_Append(VecNested vec, VecNestedBufItem x) {
    Py_ssize_t cap = VEC_CAP(vec);
    VEC_INCREF(x);
    if (vec.len < cap) {
        // Slot may have duplicate ref from prior remove/pop
        Py_XDECREF(vec.buf->items[vec.len].buf);
        vec.buf->items[vec.len] = x;
        vec.len++;
        return vec;
    } else {
        Py_ssize_t new_size = 2 * cap + 1;
        // TODO: Avoid initializing to zero here
        VecNested new = vec_alloc(new_size, vec.buf->item_type, vec.buf->depth);
        if (VEC_IS_ERROR(new)) {
            VEC_DECREF(x);
            // The input vec is being consumed/stolen by this function, so on error
            // we must decref it to avoid leaking the buffer.
            VEC_DECREF(vec);
            return new;
        }
        // Copy items to new vec.
        memcpy(new.buf->items, vec.buf->items, sizeof(VecNestedBufItem) * vec.len);
        // TODO: How to safely represent deleted items?
        memset(new.buf->items + vec.len, 0, sizeof(VecNestedBufItem) * (new_size - vec.len));
        // Clear the items in the old vec. We avoid reference count manipulation.
        memset(vec.buf->items, 0, sizeof(VecNestedBufItem) * vec.len);
        new.buf->items[vec.len] = x;
        new.len = vec.len + 1;
        VEC_DECREF(vec);
        return new;
    }
}

// Remove item from 'vec', stealing 'vec'. Return 'vec' with item removed.
VecNested VecNested_Remove(VecNested self, VecNestedBufItem arg) {
    VecNestedBufItem *items = self.buf->items;

    PyObject *boxed_arg = VecNested_BoxItem(self, arg);
    if (boxed_arg == NULL) {
        // The input self is being consumed/stolen by this function, so on error
        // we must decref it to avoid leaking the buffer.
        VEC_DECREF(self);
        return vec_error();
    }

    for (Py_ssize_t i = 0; i < self.len; i++) {
        int match = 0;
        if (items[i].len == arg.len && items[i].buf == arg.buf)
            match = 1;
        else {
            PyObject *item = box_vec_item_by_index(self, i);
            if (item == NULL) {
                Py_DECREF(boxed_arg);
                // The input self is being consumed/stolen by this function, so on error
                // we must decref it to avoid leaking the buffer.
                VEC_DECREF(self);
                return vec_error();
            }
            int itemcmp = PyObject_RichCompareBool(item, boxed_arg, Py_EQ);
            Py_DECREF(item);
            if (itemcmp < 0) {
                Py_DECREF(boxed_arg);
                // The input self is being consumed/stolen by this function, so on error
                // we must decref it to avoid leaking the buffer.
                VEC_DECREF(self);
                return vec_error();
            }
            match = itemcmp;
        }
        if (match) {
            if (i < self.len - 1) {
                Py_CLEAR(items[i].buf);
                for (; i < self.len - 1; i++) {
                    items[i] = items[i + 1];
                }
                Py_XINCREF(items[self.len - 1].buf);
            }
            self.len--;
            Py_DECREF(boxed_arg);
            // Return the stolen reference without INCREF
            return self;
        }
    }
    Py_DECREF(boxed_arg);
    PyErr_SetString(PyExc_ValueError, "vec.remove(x): x not in vec");
    // The input self is being consumed/stolen by this function, so on error
    // we must decref it to avoid leaking the buffer.
    VEC_DECREF(self);
    return vec_error();
}

// Pop item from 'vec', stealing 'vec'. Return struct with modified 'vec' and the popped item.
VecNestedPopResult VecNested_Pop(VecNested v, Py_ssize_t index) {
    VecNestedPopResult result;

    if (index < 0)
        index += v.len;

    if (index < 0 || index >= v.len) {
        PyErr_SetString(PyExc_IndexError, "index out of range");
        // The input v is being consumed/stolen by this function, so on error
        // we must decref it to avoid leaking the buffer.
        VEC_DECREF(v);
        result.f0 = vec_error();
        result.f1.len = 0;
        result.f1.buf = NULL;
        return result;
    }

    VecNestedBufItem *items = v.buf->items;
    result.f1 = items[index];
    for (Py_ssize_t i = index; i < v.len - 1; i++)
        items[i] = items[i + 1];
    if (v.len > 0)
        Py_XINCREF(items[v.len - 1].buf);
    v.len--;
    // Return the stolen reference without INCREF
    result.f0 = v;
    return result;
}

static int
VecNested_traverse(VecNestedObject *self, visitproc visit, void *arg)
{
    Py_VISIT(self->vec.buf);
    return 0;
}

static int
VecNested_clear(VecNestedObject *self)
{
    Py_CLEAR(self->vec.buf);
    return 0;
}

static void
VecNested_dealloc(VecNestedObject *self)
{
    PyObject_GC_UnTrack(self);
    Py_TRASHCAN_BEGIN(self, VecNested_dealloc)
    Py_CLEAR(self->vec.buf);
    Py_TYPE(self)->tp_free((PyObject *)self);
    Py_TRASHCAN_END
}

static int
VecNestedBuf_traverse(VecNestedBufObject *self, visitproc visit, void *arg)
{
    if (!Vec_IsMagicItemType(self->item_type))
        Py_VISIT(VEC_BUF_ITEM_TYPE(self));
    for (Py_ssize_t i = 0; i < VEC_BUF_SIZE(self); i++) {
        Py_VISIT(self->items[i].buf);
    }
    return 0;
}

static inline int
VecNestedBuf_clear(VecNestedBufObject *self)
{
    if (self->item_type && !Vec_IsMagicItemType(self->item_type)) {
        Py_DECREF(VEC_BUF_ITEM_TYPE(self));
        self->item_type = 0;
    }
    for (Py_ssize_t i = 0; i < VEC_BUF_SIZE(self); i++) {
        Py_CLEAR(self->items[i].buf);
    }
    return 0;
}

static void
VecNestedBuf_dealloc(VecNestedBufObject *self)
{
    PyObject_GC_UnTrack(self);
    Py_TRASHCAN_BEGIN(self, VecNestedBuf_dealloc)
    VecNestedBuf_clear(self);
    Py_TYPE(self)->tp_free((PyObject *)self);
    Py_TRASHCAN_END
}

static Py_ssize_t vec_ext_length(PyObject *o) {
    return ((VecNestedObject *)o)->vec.len;
}

static PyMappingMethods VecNestedMapping = {
    .mp_length = vec_ext_length,
    .mp_subscript = vec_subscript,
};

static PySequenceMethods VecNestedSequence = {
    .sq_item = vec_get_item,
    .sq_ass_item = vec_ass_item,
};

static PyMethodDef vec_methods[] = {
    {NULL, NULL, 0, NULL},  /* Sentinel */
};

PyTypeObject VecNestedBufType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "vecbuf",
    .tp_doc = "Internal data buffer used by vec objects",
    .tp_basicsize = sizeof(VecNestedBufObject) - sizeof(VecNestedBufItem),
    .tp_itemsize = sizeof(VecNestedBufItem),
    .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC,
    .tp_traverse = (traverseproc)VecNestedBuf_traverse,
    //.tp_new = vecbuf_i64_new, //??
    .tp_free = PyObject_GC_Del,
    .tp_clear = (inquiry)VecNestedBuf_clear,
    .tp_dealloc = (destructor)VecNestedBuf_dealloc,
};

PyTypeObject VecNestedType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "vec",
    .tp_doc = "Mutable sequence-like container optimized for compilation with mypyc",
    .tp_basicsize = sizeof(VecNestedObject),
    .tp_itemsize = 0,
    .tp_base = &VecType,  // Inherit from base vec type for isinstance() support
    .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC,
    .tp_traverse = (traverseproc)VecNested_traverse,
    .tp_clear = (inquiry)VecNested_clear,
    .tp_dealloc = (destructor)VecNested_dealloc,
    //.tp_free = PyObject_GC_Del,
    .tp_repr = (reprfunc)vec_repr,
    .tp_as_sequence = &VecNestedSequence,
    .tp_as_mapping = &VecNestedMapping,
    .tp_richcompare = vec_richcompare,
    .tp_methods = vec_methods,
    // TODO: free
};

PyObject *VecNested_FromIterable(size_t item_type, size_t depth, PyObject *iterable) {
    VecNested v = vec_alloc(0, item_type, depth);
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
        VecNestedBufItem vecitem;
        if (VecNested_UnboxItem(v, item, &vecitem) < 0) {
            Py_DECREF(iter);
            VEC_DECREF(v);
            Py_DECREF(item);
            return NULL;
        }
        v = VecNested_Append(v, vecitem);
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
    return VecNested_Box(v);
}

VecNestedAPI Vec_NestedAPI = {
    &VecNestedType,
    &VecNestedBufType,
    VecNested_New,
    VecNested_Box,
    VecNested_Unbox,
    VecNested_ConvertFromNested,
    VecNested_Append,
    VecNested_Pop,
    VecNested_Remove,
    VecNested_Slice,
};

#endif  // MYPYC_EXPERIMENTAL
