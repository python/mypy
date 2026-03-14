#ifdef MYPYC_EXPERIMENTAL
// Implementation of generic vec[t], when t is a plain type object (possibly optional).
//
// Examples of types supported:
//
//  - vec[str]
//  - vec[str | None]
//  - vec[object]
//  - vec[UserClass]

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "librt_vecs.h"
#include "vecs_internal.h"

static inline VecT vec_error() {
    VecT v = { .len = -1 };
    return v;
}

static inline VecTBufObject *alloc_buf(Py_ssize_t size, size_t item_type) {
    VecTBufObject *buf = PyObject_GC_NewVar(VecTBufObject, &VecTBufType, size);
    if (buf == NULL)
        return NULL;
    buf->item_type = item_type;
    Py_INCREF(VEC_BUF_ITEM_TYPE(buf));
    PyObject_GC_Track(buf);
    return buf;
}

// Alloc a partially initialized vec. Caller *must* immediately initialize len, and buf->items
// if size > 0.
static VecT vec_alloc(Py_ssize_t size, size_t item_type) {
    VecTBufObject *buf;

    if (size == 0) {
        buf = NULL;
    } else {
        buf = alloc_buf(size, item_type);
        if (buf == NULL)
            return vec_error();
    }
    return (VecT) { .buf = buf };
}

// Box a VecT value, stealing 'vec'. On failure, return NULL and decref 'vec'.
PyObject *VecT_Box(VecT vec, size_t item_type) {
    // An unboxed empty vec may have a NULL buf, but a boxed vec must have it
    // allocated, since it contains the item type
    if (vec.buf == NULL) {
        vec.buf = alloc_buf(0, item_type);
        if (vec.buf == NULL)
            return NULL;
    }
    VecTObject *obj = PyObject_GC_New(VecTObject, &VecTType);
    if (obj == NULL) {
        // vec.buf is always defined, so no need for a NULL check
        Py_DECREF(vec.buf);
        return NULL;
    }
    obj->vec = vec;
    PyObject_GC_Track(obj);
    return (PyObject *)obj;
}

VecT VecT_Unbox(PyObject *obj, size_t item_type) {
    if (obj->ob_type == &VecTType) {
        VecT result = ((VecTObject *)obj)->vec;
        if (result.buf->item_type == item_type) {
            VEC_INCREF(result);  // TODO: Should we borrow instead?
            return result;
        }
    }
    // TODO: Better error message, with name of type
    PyErr_SetString(PyExc_TypeError, "vec[t] expected");
    return vec_error();
}

VecT VecT_ConvertFromNested(VecNestedBufItem item) {
    return (VecT) { item.len, (VecTBufObject *)item.buf };
}

VecT VecT_New(Py_ssize_t size, Py_ssize_t cap, size_t item_type) {
    if (cap < size)
        cap = size;
    VecT vec = vec_alloc(cap, item_type);
    if (VEC_IS_ERROR(vec))
        return vec;
    for (Py_ssize_t i = 0; i < cap; i++) {
        vec.buf->items[i] = NULL;
    }
    vec.len = size;
    return vec;
}

static PyObject *vec_repr(PyObject *self) {
    VecTObject *v = (VecTObject *)self;
    return Vec_GenericRepr(self, v->vec.buf->item_type, 0, 1);
}

static PyObject *vec_get_item(PyObject *o, Py_ssize_t i) {
    VecT v = ((VecTObject *)o)->vec;
    if ((size_t)i < (size_t)v.len) {
        PyObject *item = v.buf->items[i];
        Py_INCREF(item);
        return item;
    } else if ((size_t)i + (size_t)v.len < (size_t)v.len) {
        PyObject *item = v.buf->items[i + v.len];
        Py_INCREF(item);
        return item;
    } else {
        PyErr_SetString(PyExc_IndexError, "index out of range");
        return NULL;
    }
}

VecT VecT_Slice(VecT vec, int64_t start, int64_t end) {
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
    if (slicelength == 0)
        return (VecT) { .len = 0, .buf = NULL };
    VecT res = vec_alloc(slicelength, vec.buf->item_type);
    if (VEC_IS_ERROR(res))
        return res;
    res.len = slicelength;
    for (Py_ssize_t i = 0; i < slicelength; i++) {
        PyObject *item = vec.buf->items[start + i];
        Py_INCREF(item);
        res.buf->items[i] = item;
    }
    return res;
}

static PyObject *vec_subscript(PyObject *self, PyObject *item) {
    VecT vec = ((VecTObject *)self)->vec;
    if (PyIndex_Check(item)) {
        Py_ssize_t i = PyNumber_AsSsize_t(item, PyExc_IndexError);
        if (i == -1 && PyErr_Occurred())
            return NULL;
        if ((size_t)i < (size_t)vec.len) {
            PyObject *result = vec.buf->items[i];
            Py_INCREF(result);
            return result;
        } else if ((size_t)i + (size_t)vec.len < (size_t)vec.len) {
            PyObject *result = vec.buf->items[i + vec.len];
            Py_INCREF(result);
            return result;
        } else {
            PyErr_SetString(PyExc_IndexError, "index out of range");
            return NULL;
        }
    } else if (PySlice_Check(item)) {
        Py_ssize_t start, stop, step;
        if (PySlice_Unpack(item, &start, &stop, &step) < 0)
            return NULL;
        Py_ssize_t slicelength = PySlice_AdjustIndices(vec.len, &start, &stop, step);
        VecT res = vec_alloc(slicelength, vec.buf->item_type);
        if (VEC_IS_ERROR(res))
            return NULL;
        res.len = slicelength;
        Py_ssize_t j = start;
        for (Py_ssize_t i = 0; i < slicelength; i++) {
            PyObject *item = vec.buf->items[j];
            Py_INCREF(item);
            res.buf->items[i] = item;
            j += step;
        }
        PyObject *result = VecT_Box(res, vec.buf->item_type);
        if (result == NULL) {
            VEC_DECREF(res);
        }
        return result;
    } else {
        PyErr_Format(PyExc_TypeError, "vec indices must be integers or slices, not %.100s",
                     item->ob_type->tp_name);
        return NULL;
    }
}

static int vec_ass_item(PyObject *self, Py_ssize_t i, PyObject *o) {
    VecT v = ((VecTObject *)self)->vec;
    if (!VecT_ItemCheck(v, o, v.buf->item_type))
        return -1;
    if ((size_t)i < (size_t)v.len) {
        PyObject *old = v.buf->items[i];
        Py_INCREF(o);
        v.buf->items[i] = o;
        Py_XDECREF(old);
        return 0;
    } else if ((size_t)i + (size_t)v.len < (size_t)v.len) {
        PyObject *old = v.buf->items[i + v.len];
        Py_INCREF(o);
        v.buf->items[i + v.len] = o;
        Py_XDECREF(old);
        return 0;
    } else {
        PyErr_SetString(PyExc_IndexError, "index out of range");
        return -1;
    }
}

static PyObject *vec_richcompare(PyObject *self, PyObject *other, int op) {
    PyObject *res;
    if (op == Py_EQ || op == Py_NE) {
        if (other->ob_type != &VecTType) {
            res = op == Py_EQ ? Py_False : Py_True;
        } else {
            VecT x = ((VecTObject *)self)->vec;
            VecT y = ((VecTObject *)other)->vec;
            if (x.buf->item_type != y.buf->item_type) {
                res = op == Py_EQ ? Py_False : Py_True;
            } else {
                // TODO: why pointers to len?
                return Vec_GenericRichcompare(&x.len, x.buf->items, &y.len, y.buf->items, op);
            }
        }
    } else
        res = Py_NotImplemented;
    Py_INCREF(res);
    return res;
}

// Append item to 'vec', stealing 'vec'. Return 'vec' with item appended.
VecT VecT_Append(VecT vec, PyObject *x, size_t item_type) {
    if (vec.buf == NULL) {
        VecT new = vec_alloc(1, item_type);
        if (VEC_IS_ERROR(new))
            return new;
        Py_INCREF(x);
        new.len = 1;
        new.buf->items[0] = x;
        return new;
    }
    Py_ssize_t cap = VEC_CAP(vec);
    Py_INCREF(x);
    if (vec.len < cap) {
        // Slot may have duplicate ref from prior remove/pop
        Py_XSETREF(vec.buf->items[vec.len], x);
        vec.len++;
        return vec;
    } else {
        Py_ssize_t new_size = 2 * cap + 1;
        // TODO: Avoid initializing to zero here
        VecT new = vec_alloc(new_size, vec.buf->item_type);
        if (VEC_IS_ERROR(new)) {
            Py_DECREF(x);
            // The input vec is being consumed/stolen by this function, so on error
            // we must decref it to avoid leaking the buffer.
            VEC_DECREF(vec);
            return new;
        }
        // Copy items to new vec.
        memcpy(new.buf->items, vec.buf->items, sizeof(PyObject *) * vec.len);
        memset(new.buf->items + vec.len, 0, sizeof(PyObject *) * (new_size - vec.len));
        // Clear the items in the old vec. We avoid reference count manipulation.
        memset(vec.buf->items, 0, sizeof(PyObject *) * vec.len);
        new.buf->items[vec.len] = x;
        new.len = vec.len + 1;
        VEC_DECREF(vec);
        return new;
    }
}

// Remove item from 'vec', stealing 'vec'. Return 'vec' with item removed.
VecT VecT_Remove(VecT v, PyObject *arg) {
    PyObject **items = v.buf->items;
    for (Py_ssize_t i = 0; i < v.len; i++) {
        int match = 0;
        if (items[i] == arg)
            match = 1;
        else {
            int itemcmp = PyObject_RichCompareBool(items[i], arg, Py_EQ);
            if (itemcmp < 0) {
                // The input v is being consumed/stolen by this function, so on error
                // we must decref it to avoid leaking the buffer.
                VEC_DECREF(v);
                return vec_error();
            }
            match = itemcmp;
        }
        if (match) {
            if (i < v.len - 1) {
                Py_CLEAR(items[i]);
                for (; i < v.len - 1; i++) {
                    items[i] = items[i + 1];
                }
                // Keep a duplicate item, since there could be another reference
                // to the buffer with a longer length, and they expect a valid reference.
                Py_XINCREF(items[v.len - 1]);
            }
            v.len--;
            // Return the stolen reference without INCREF
            return v;
        }
    }
    PyErr_SetString(PyExc_ValueError, "vec.remove(x): x not in vec");
    // The input v is being consumed/stolen by this function, so on error
    // we must decref it to avoid leaking the buffer.
    VEC_DECREF(v);
    return vec_error();
}

// Pop item from 'vec', stealing 'vec'. Return struct with modified 'vec' and the popped item.
VecTPopResult VecT_Pop(VecT v, Py_ssize_t index) {
    VecTPopResult result;

    if (index < 0)
        index += v.len;

    if (index < 0 || index >= v.len) {
        PyErr_SetString(PyExc_IndexError, "index out of range");
        // The input v is being consumed/stolen by this function, so on error
        // we must decref it to avoid leaking the buffer.
        VEC_DECREF(v);
        result.f0 = vec_error();
        result.f1 = NULL;
        return result;
    }

    PyObject **items = v.buf->items;
    result.f1 = items[index];
    for (Py_ssize_t i = index; i < v.len - 1; i++)
        items[i] = items[i + 1];
    // Keep duplicate item, since there could be another reference
    // to the buffer with a longer length, and they expect a valid reference.
    Py_XINCREF(items[v.len - 1]);
    v.len--;
    // Return the stolen reference without INCREF
    result.f0 = v;
    return result;
}

static int
VecT_traverse(VecTObject *self, visitproc visit, void *arg)
{
    Py_VISIT(self->vec.buf);
    return 0;
}

static int
VecT_clear(VecTObject *self)
{
    Py_CLEAR(self->vec.buf);
    return 0;
}

static void
VecT_dealloc(VecTObject *self)
{
    PyObject_GC_UnTrack(self);
    Py_TRASHCAN_BEGIN(self, VecT_dealloc)
    Py_CLEAR(self->vec.buf);
    Py_TYPE(self)->tp_free((PyObject *)self);
    Py_TRASHCAN_END
}

static int
VecTBuf_traverse(VecTBufObject *self, visitproc visit, void *arg)
{
    Py_VISIT(VEC_BUF_ITEM_TYPE(self));
    for (Py_ssize_t i = 0; i < VEC_BUF_SIZE(self); i++) {
        Py_VISIT(self->items[i]);
    }
    return 0;
}

static inline int
VecTBuf_clear(VecTBufObject *self)
{
    if (self->item_type) {
        Py_DECREF(VEC_BUF_ITEM_TYPE(self));
        self->item_type = 0;
    }
    for (Py_ssize_t i = 0; i < VEC_BUF_SIZE(self); i++) {
        Py_CLEAR(self->items[i]);
    }
    return 0;
}

static void
VecTBuf_dealloc(VecTBufObject *self)
{
    PyObject_GC_UnTrack(self);
    Py_TRASHCAN_BEGIN(self, VecTBuf_dealloc)
    VecTBuf_clear(self);
    Py_TYPE(self)->tp_free((PyObject *)self);
    Py_TRASHCAN_END
}

static Py_ssize_t vec_length(PyObject *o) {
    return ((VecTObject *)o)->vec.len;
}

static PyMappingMethods VecTMapping = {
    .mp_length = vec_length,
    .mp_subscript = vec_subscript,
};

static PySequenceMethods VecTSequence = {
    .sq_item = vec_get_item,
    .sq_ass_item = vec_ass_item,
};

static PyMethodDef vec_methods[] = {
    {NULL, NULL, 0, NULL},  /* Sentinel */
};

PyTypeObject VecTBufType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "vecbuf",
    .tp_doc = "Internal data buffer used by vec objects",
    .tp_basicsize = sizeof(VecTBufObject) - sizeof(PyObject *),
    .tp_itemsize = sizeof(PyObject *),
    .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC,
    .tp_traverse = (traverseproc)VecTBuf_traverse,
    //.tp_new = vecbuf_i64_new, //??
    .tp_free = PyObject_GC_Del,
    .tp_clear = (inquiry)VecTBuf_clear,
    .tp_dealloc = (destructor)VecTBuf_dealloc,
};

PyTypeObject VecTType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "vec",
    .tp_doc = "Mutable sequence-like container optimized for compilation with mypyc",
    .tp_basicsize = sizeof(VecTObject),
    .tp_itemsize = 0,
    .tp_base = &VecType,  // Inherit from base vec type for isinstance() support
    .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC,
    .tp_traverse = (traverseproc)VecT_traverse,
    .tp_clear = (inquiry)VecT_clear,
    .tp_dealloc = (destructor)VecT_dealloc,
    //.tp_free = PyObject_GC_Del,
    .tp_repr = (reprfunc)vec_repr,
    .tp_as_sequence = &VecTSequence,
    .tp_as_mapping = &VecTMapping,
    .tp_richcompare = vec_richcompare,
    .tp_methods = vec_methods,
    // TODO: free
};

PyObject *VecT_FromIterable(size_t item_type, PyObject *iterable) {
    VecT v = vec_alloc(0, item_type);
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
        if (!VecT_ItemCheck(v, item, item_type)) {
            Py_DECREF(iter);
            VEC_DECREF(v);
            Py_DECREF(item);
            return NULL;
        }
        v = VecT_Append(v, item, item_type);
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
    return VecT_Box(v, item_type);
}

VecTAPI Vec_TAPI = {
    &VecTType,
    &VecTBufType,
    VecT_New,
    VecT_Box,
    VecT_Unbox,
    VecT_ConvertFromNested,
    VecT_Append,
    VecT_Pop,
    VecT_Remove,
    VecT_Slice,
};

#endif  // MYPYC_EXPERIMENTAL
