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
    return buf;
}

static inline void vec_track_buffer(VecT *vec) {
    if (vec->buf != NULL) {
        PyObject_GC_Track(vec->buf);
    }
}

// Alloc a partially initialized vec. If size > 0, caller *must* immediately initialize len,
// and buf->items. Caller *must* also call vec_track_buffer on the returned vec but only
// after initializing the items.
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
        vec_track_buffer(&vec);
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
    if (cap < 0) {
        PyErr_SetString(PyExc_ValueError, "capacity must not be negative");
        return vec_error();
    }
    if (cap < size)
        cap = size;
    VecT vec = vec_alloc(cap, item_type);
    if (VEC_IS_ERROR(vec))
        return vec;
    for (Py_ssize_t i = 0; i < cap; i++) {
        vec.buf->items[i] = NULL;
    }
    vec_track_buffer(&vec);
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
    vec_track_buffer(&res);
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
        vec_track_buffer(&res);
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

static int vec_contains(PyObject *self, PyObject *value) {
    VecT v = ((VecTObject *)self)->vec;
    for (Py_ssize_t i = 0; i < v.len; i++) {
        PyObject *item = v.buf->items[i];
        if (item == value) {
            return 1;
        }
        Py_INCREF(item);
        int cmp = PyObject_RichCompareBool(item, value, Py_EQ);
        Py_DECREF(item);
        if (cmp != 0)
            return cmp;  // 1 if equal, -1 on error
    }
    return 0;
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
        vec_track_buffer(&new);
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
        Py_ssize_t new_size = Vec_GrowCapacity(cap);
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
        if (Py_REFCNT(vec.buf) > 1) {
            // Other references to old buffer exist; INCREF items in new buffer
            // so old buffer keeps valid references for aliases.
            for (Py_ssize_t i = 0; i < vec.len; i++)
                Py_XINCREF(new.buf->items[i]);
        } else {
            // No aliases; transfer ownership by clearing old buffer items.
            memset(vec.buf->items, 0, sizeof(PyObject *) * vec.len);
        }
        new.buf->items[vec.len] = x;
        new.len = vec.len + 1;
        vec_track_buffer(&new);
        VEC_DECREF(vec);
        return new;
    }
}

// Extend 'vec' with items from 'iterable', stealing 'vec'.
// Return extended 'vec', or error vec on failure.
VecT VecT_Extend(VecT vec, PyObject *iterable, size_t item_type) {
    if (VecT_Check(iterable)) {
        VecT src = ((VecTObject *)iterable)->vec;
        if (src.buf != NULL && src.buf->item_type == item_type) {
            return VecT_ExtendVec(vec, src, item_type);
        }
    }

    PyObject *iter = PyObject_GetIter(iterable);
    if (iter == NULL) {
        VEC_DECREF(vec);
        return vec_error();
    }
    PyObject *item;
    while ((item = PyIter_Next(iter)) != NULL) {
        if (!VecT_ItemCheck(vec, item, item_type)) {
            Py_DECREF(iter);
            VEC_DECREF(vec);
            Py_DECREF(item);
            return vec_error();
        }
        vec = VecT_Append(vec, item, item_type);
        Py_DECREF(item);
        if (VEC_IS_ERROR(vec)) {
            Py_DECREF(iter);
            return vec_error();
        }
    }
    Py_DECREF(iter);
    if (PyErr_Occurred()) {
        VEC_DECREF(vec);
        return vec_error();
    }
    return vec;
}

// Extend 'dst' with items from 'src' vec, stealing 'dst', borrowing 'src'.
// Return extended vec, or error vec on failure.
VecT VecT_ExtendVec(VecT dst, VecT src, size_t item_type) {
    if (src.len == 0)
        return dst;
    if (src.len > PY_SSIZE_T_MAX - dst.len) {
        PyErr_NoMemory();
        VEC_DECREF(dst);
        return vec_error();
    }
    Py_ssize_t new_len = dst.len + src.len;
    if (dst.buf == NULL) {
        // dst is empty, allocate new buf
        VecT new = vec_alloc(new_len, item_type);
        if (VEC_IS_ERROR(new)) {
            VEC_DECREF(dst);
            return new;
        }
        for (Py_ssize_t i = 0; i < src.len; i++) {
            Py_INCREF(src.buf->items[i]);
            new.buf->items[i] = src.buf->items[i];
        }
        memset(new.buf->items + src.len, 0, sizeof(PyObject *) * (new_len - src.len));
        new.len = new_len;
        vec_track_buffer(&new);
        return new;
    }
    Py_ssize_t cap = VEC_CAP(dst);
    if (new_len <= cap && dst.buf != src.buf) {
        // Fast path: enough capacity and no aliasing
        for (Py_ssize_t i = 0; i < src.len; i++) {
            Py_INCREF(src.buf->items[i]);
            // Slot may have duplicate ref from prior remove/pop
            Py_XSETREF(dst.buf->items[dst.len + i], src.buf->items[i]);
        }
        dst.len = new_len;
        return dst;
    }
    // Need to reallocate (or dst and src share a buffer)
    Py_ssize_t new_cap = Vec_GrowCapacityTo(cap, new_len);
    int aliased = dst.buf == src.buf;
    VecT new = vec_alloc(new_cap, dst.buf->item_type);
    if (VEC_IS_ERROR(new)) {
        VEC_DECREF(dst);
        return new;
    }
    if (aliased) {
        // dst and src share a buffer -- incref all items instead of
        // moving refs, to avoid mutating the shared buffer
        for (Py_ssize_t i = 0; i < dst.len; i++) {
            Py_INCREF(dst.buf->items[i]);
            new.buf->items[i] = dst.buf->items[i];
        }
    } else {
        memcpy(new.buf->items, dst.buf->items, sizeof(PyObject *) * dst.len);
        if (Py_REFCNT(dst.buf) > 1) {
            for (Py_ssize_t i = 0; i < dst.len; i++)
                Py_XINCREF(new.buf->items[i]);
        } else {
            memset(dst.buf->items, 0, sizeof(PyObject *) * dst.len);
        }
    }
    // Copy src items (incref each)
    for (Py_ssize_t i = 0; i < src.len; i++) {
        Py_INCREF(src.buf->items[i]);
        new.buf->items[dst.len + i] = src.buf->items[i];
    }
    memset(new.buf->items + new_len, 0, sizeof(PyObject *) * (new_cap - new_len));
    new.len = new_len;
    vec_track_buffer(&new);
    VEC_DECREF(dst);
    return new;
}

// Convert vec to list, stealing 'v'.
PyObject *VecT_ToList(VecT v) {
    Py_ssize_t n = v.len;
    PyObject *list = PyList_New(n);
    if (list == NULL) {
        VEC_DECREF(v);
        return NULL;
    }
    if (n > 0 && Py_REFCNT(v.buf) == 1) {
        for (Py_ssize_t i = 0; i < n; i++) {
            PyList_SET_ITEM(list, i, v.buf->items[i]);
            v.buf->items[i] = NULL;
        }
    } else {
        for (Py_ssize_t i = 0; i < n; i++) {
            PyObject *item = v.buf->items[i];
            Py_INCREF(item);
            PyList_SET_ITEM(list, i, item);
        }
    }
    VEC_DECREF(v);
    return list;
}

// Convert vec to tuple, stealing 'v'.
PyObject *VecT_ToTuple(VecT v) {
    Py_ssize_t n = v.len;
    PyObject *tuple = PyTuple_New(n);
    if (tuple == NULL) {
        VEC_DECREF(v);
        return NULL;
    }
    if (n > 0 && Py_REFCNT(v.buf) == 1) {
        for (Py_ssize_t i = 0; i < n; i++) {
            PyTuple_SET_ITEM(tuple, i, v.buf->items[i]);
            v.buf->items[i] = NULL;
        }
    } else {
        for (Py_ssize_t i = 0; i < n; i++) {
            PyObject *item = v.buf->items[i];
            Py_INCREF(item);
            PyTuple_SET_ITEM(tuple, i, item);
        }
    }
    VEC_DECREF(v);
    return tuple;
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
    .sq_contains = vec_contains,
};

static PyMethodDef vec_methods[] = {
    {NULL, NULL, 0, NULL},  /* Sentinel */
};

// Iterator type for vec[T] (reference types)

typedef struct {
    PyObject_HEAD
    VecT vec;             // Unboxed vec (keeps buffer alive via buf reference)
    Py_ssize_t index;     // Current iteration index
} VecTIterObject;

PyTypeObject VecTIterType;

static PyObject *VecT_iter(PyObject *self) {
    VecTIterObject *it = PyObject_GC_New(VecTIterObject, &VecTIterType);
    if (it == NULL)
        return NULL;
    it->vec = ((VecTObject *)self)->vec;
    Py_INCREF(it->vec.buf);
    it->index = 0;
    PyObject_GC_Track(it);
    return (PyObject *)it;
}

static int
VecTIter_traverse(VecTIterObject *self, visitproc visit, void *arg)
{
    Py_VISIT(self->vec.buf);
    return 0;
}

static int
VecTIter_clear(VecTIterObject *self)
{
    Py_CLEAR(self->vec.buf);
    return 0;
}

static void VecTIter_dealloc(VecTIterObject *self) {
    PyObject_GC_UnTrack(self);
    Py_XDECREF(self->vec.buf);
    PyObject_GC_Del(self);
}

static PyObject *VecTIter_next(VecTIterObject *self) {
    if (self->vec.buf == NULL)
        return NULL;
    if (self->index < self->vec.len) {
        PyObject *item = self->vec.buf->items[self->index];
        self->index++;
        Py_INCREF(item);
        return item;
    }
    Py_CLEAR(self->vec.buf);
    return NULL;  // StopIteration
}

static PyObject *VecTIter_len(VecTIterObject *self, PyObject *Py_UNUSED(ignored)) {
    if (self->vec.buf == NULL)
        return PyLong_FromSsize_t(0);
    Py_ssize_t remaining = self->vec.len - self->index;
    if (remaining < 0)
        remaining = 0;
    return PyLong_FromSsize_t(remaining);
}

static PyMethodDef VecTIter_methods[] = {
    {"__length_hint__", (PyCFunction)VecTIter_len, METH_NOARGS, NULL},
    {NULL, NULL, 0, NULL},
};

PyTypeObject VecTIterType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "vec_iterator",
    .tp_basicsize = sizeof(VecTIterObject),
    .tp_itemsize = 0,
    .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC,
    .tp_traverse = (traverseproc)VecTIter_traverse,
    .tp_clear = (inquiry)VecTIter_clear,
    .tp_dealloc = (destructor)VecTIter_dealloc,
    .tp_iter = PyObject_SelfIter,
    .tp_iternext = (iternextfunc)VecTIter_next,
    .tp_methods = VecTIter_methods,
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
    .tp_iter = VecT_iter,
    .tp_as_sequence = &VecTSequence,
    .tp_as_mapping = &VecTMapping,
    .tp_richcompare = vec_richcompare,
    .tp_methods = vec_methods,
    // TODO: free
};

static inline VecT vec_from_sequence(
        size_t item_type, PyObject *seq, int64_t cap, const int is_list) {
    Py_ssize_t n = is_list ? PyList_GET_SIZE(seq) : PyTuple_GET_SIZE(seq);
    Py_ssize_t alloc_size = n > cap ? n : cap;
    VecT v = vec_alloc(alloc_size, item_type);
    if (VEC_IS_ERROR(v))
        return vec_error();
    for (Py_ssize_t i = 0; i < n; i++) {
        PyObject *item = is_list ? PyList_GET_ITEM(seq, i) : PyTuple_GET_ITEM(seq, i);
        if (!VecT_ItemCheck(v, item, item_type)) {
            for (Py_ssize_t j = i; j < alloc_size; j++)
                v.buf->items[j] = NULL;
            VEC_DECREF(v);
            return vec_error();
        }
        Py_INCREF(item);
        v.buf->items[i] = item;
    }
    for (Py_ssize_t j = n; j < alloc_size; j++)
        v.buf->items[j] = NULL;
    vec_track_buffer(&v);
    v.len = n;
    return v;
}

VecT VecT_FromIterable(size_t item_type, PyObject *iterable, int64_t cap) {
    if (PyList_CheckExact(iterable)) {
        return vec_from_sequence(item_type, iterable, cap, 1);
    } else if (PyTuple_CheckExact(iterable)) {
        return vec_from_sequence(item_type, iterable, cap, 0);
    }

    VecT v = vec_alloc(cap, item_type);
    if (VEC_IS_ERROR(v))
        return vec_error();
    if (cap > 0) {
        for (int64_t i = 0; i < cap; i++)
            v.buf->items[i] = NULL;
    }
    v.len = 0;
    vec_track_buffer(&v);

    PyObject *iter = PyObject_GetIter(iterable);
    if (iter == NULL) {
        VEC_DECREF(v);
        return vec_error();
    }
    PyObject *item;
    while ((item = PyIter_Next(iter)) != NULL) {
        if (!VecT_ItemCheck(v, item, item_type)) {
            Py_DECREF(iter);
            VEC_DECREF(v);
            Py_DECREF(item);
            return vec_error();
        }
        v = VecT_Append(v, item, item_type);
        Py_DECREF(item);
        if (VEC_IS_ERROR(v)) {
            Py_DECREF(iter);
            VEC_DECREF(v);
            return vec_error();
        }
    }
    Py_DECREF(iter);
    if (PyErr_Occurred()) {
        VEC_DECREF(v);
        return vec_error();
    }
    return v;
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
    VecT_FromIterable,
    VecT_Extend,
    VecT_ExtendVec,
    VecT_ToList,
    VecT_ToTuple,
};

#endif  // MYPYC_EXPERIMENTAL
