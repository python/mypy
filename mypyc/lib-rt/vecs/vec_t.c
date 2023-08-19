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

// Alloc a partially initialized vec. Caller *must* initialize len and buf->items.
static VecT vec_t_alloc(Py_ssize_t size, size_t item_type) {
    VecbufTObject *buf = PyObject_GC_NewVar(VecbufTObject, &VecbufTType, size);
    if (buf == NULL)
        return Vec_T_Error();
    buf->item_type = item_type;
    Py_INCREF(BUF_ITEM_TYPE(buf));
    VecT res = { .buf = buf };
    PyObject_GC_Track(buf);
    return res;
}

PyObject *Vec_T_Box(VecT vec) {
    VecTObject *obj = PyObject_GC_New(VecTObject, &VecTType);
    if (obj == NULL)
        return NULL;
    obj->vec = vec;
    PyObject_GC_Track(obj);
    return (PyObject *)obj;
}

VecT Vec_T_Unbox(PyObject *obj, size_t item_type) {
    if (obj->ob_type == &VecTType) {
        VecT result = ((VecTObject *)obj)->vec;
        if (result.buf->item_type == item_type) {
            VEC_INCREF(result);  // TODO: Should we borrow instead?
            return result;
        }
    }
    // TODO: Better error message, with name of type
    PyErr_SetString(PyExc_TypeError, "vec[t] expected");
    return Vec_T_Error();
}

VecT Vec_T_New(Py_ssize_t size, size_t item_type) {
    VecT vec = vec_t_alloc(size, item_type);
    if (VEC_IS_ERROR(vec))
        return vec;
    for (Py_ssize_t i = 0; i < size; i++) {
        vec.buf->items[i] = NULL;
    }
    vec.len = size;
    return vec;
}

PyObject *vec_t_repr(PyObject *self) {
    VecTObject *v = (VecTObject *)self;
    return vec_repr(self, v->vec.buf->item_type, 0, 1);
}

PyObject *vec_t_get_item(PyObject *o, Py_ssize_t i) {
    VecT v = ((VecTObject *)o)->vec;
    if ((size_t)i < (size_t)v.len) {
        PyObject *item = v.buf->items[i];
        Py_INCREF(item);
        return item;
    } else {
        PyErr_SetString(PyExc_IndexError, "index out of range");
        return NULL;
    }
}

VecT Vec_T_Slice(VecT vec, int64_t start, int64_t end) {
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
    VecT res = vec_t_alloc(slicelength, vec.buf->item_type);
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

PyObject *vec_t_subscript(PyObject *self, PyObject *item) {
    VecT vec = ((VecTObject *)self)->vec;
    if (PyIndex_Check(item)) {
        Py_ssize_t i = PyNumber_AsSsize_t(item, PyExc_IndexError);
        if (i == -1 && PyErr_Occurred())
            return NULL;
        if ((size_t)i < (size_t)vec.len) {
            PyObject *item = vec.buf->items[i];
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
        Py_ssize_t slicelength = PySlice_AdjustIndices(vec.len, &start, &stop, step);
        VecT res = vec_t_alloc(slicelength, vec.buf->item_type);
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
        return Vec_T_Box(res);
    } else {
        PyErr_Format(PyExc_TypeError, "vec indices must be integers or slices, not %.100s",
                     item->ob_type->tp_name);
        return NULL;
    }
}

int vec_t_ass_item(PyObject *self, Py_ssize_t i, PyObject *o) {
    VecT v = ((VecTObject *)self)->vec;
    if (!VecT_ItemCheck(v, o))
        return -1;
    if ((size_t)i < (size_t)v.len) {
        Py_INCREF(o);
        v.buf->items[i] = o;
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
            VecT x = ((VecTObject *)self)->vec;
            VecT y = ((VecTObject *)other)->vec;
            if (x.buf->item_type != y.buf->item_type) {
                res = op == Py_EQ ? Py_False : Py_True;
            } else {
                // TODO: why pointers to len?
                return vec_generic_richcompare(&x.len, x.buf->items, &y.len, y.buf->items, op);
            }
        }
    } else
        res = Py_NotImplemented;
    Py_INCREF(res);
    return res;
}

VecT Vec_T_Append(VecT vec, PyObject *x) {
    Py_ssize_t cap = VEC_CAP(vec);
    Py_INCREF(x);
    if (vec.len < cap) {
        vec.buf->items[vec.len] = x;
        vec.len++;
        return vec;
    } else {
        Py_ssize_t new_size = 2 * cap + 1;
        // TODO: Avoid initializing to zero here
        VecT new = vec_t_alloc(new_size, vec.buf->item_type);
        if (VEC_IS_ERROR(new))
            return new;
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

VecT Vec_T_Remove(VecT v, PyObject *arg) {
    PyObject **items = v.buf->items;
    for (Py_ssize_t i = 0; i < v.len; i++) {
        int match = 0;
        if (items[i] == arg)
            match = 1;
        else {
            int itemcmp = PyObject_RichCompareBool(items[i], arg, Py_EQ);
            if (itemcmp < 0)
                return Vec_T_Error();
            match = itemcmp;
        }
        if (match) {
            if (i < v.len - 1) {
                Py_CLEAR(items[i]);
                for (; i < v.len - 1; i++) {
                    items[i] = items[i + 1];
                }
                Py_XINCREF(items[v.len - 1]);
            }
            v.len--;
            VEC_INCREF(v);
            return v;
        }
    }
    PyErr_SetString(PyExc_ValueError, "vec.remove(x): x not in vec");
    return Vec_T_Error();
}

VecTPopResult Vec_T_Pop(VecT v, Py_ssize_t index) {
    VecTPopResult result;

    if (index < 0)
        index += v.len;

    if (index < 0 || index >= v.len) {
        PyErr_SetString(PyExc_IndexError, "index out of range");
        result.f0 = Vec_T_Error();
        result.f1 = NULL;
        return result;
    }

    PyObject **items = v.buf->items;
    result.f1 = items[index];
    for (Py_ssize_t i = index; i < v.len - 1; i++)
        items[i] = items[i + 1];
    if (v.len > 0)
        Py_XINCREF(items[v.len - 1]);
    v.len--;
    VEC_INCREF(v);
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
VecbufT_traverse(VecbufTObject *self, visitproc visit, void *arg)
{
    Py_VISIT(BUF_ITEM_TYPE(self));
    for (Py_ssize_t i = 0; i < BUF_SIZE(self); i++) {
        Py_VISIT(self->items[i]);
    }
    return 0;
}

static int
VecbufT_clear(VecbufTObject *self)
{
    if (self->item_type) {
        Py_DECREF(BUF_ITEM_TYPE(self));
        self->item_type = 0;
    }
    for (Py_ssize_t i = 0; i < BUF_SIZE(self); i++) {
        Py_CLEAR(self->items[i]);
    }
    return 0;
}

static void
VecbufT_dealloc(VecbufTObject *self)
{
    PyObject_GC_UnTrack(self);
    Py_TRASHCAN_BEGIN(self, VecbufT_dealloc)
    if (self->item_type) {
        Py_DECREF(BUF_ITEM_TYPE(self));
        self->item_type = 0;
    }
    for (Py_ssize_t i = 0; i < BUF_SIZE(self); i++) {
        Py_CLEAR(self->items[i]);
    }
    Py_TYPE(self)->tp_free((PyObject *)self);
    Py_TRASHCAN_END
}

static Py_ssize_t vec_length(PyObject *o) {
    // TODO: Type check o
    return ((VecTObject *)o)->vec.len;
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
    {NULL, NULL, 0, NULL},  /* Sentinel */
};

PyTypeObject VecbufTType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "vecbuf",
    .tp_doc = "vec doc",
    .tp_basicsize = sizeof(VecbufTObject) - sizeof(PyObject *),
    .tp_itemsize = sizeof(PyObject *),
    .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC,
    .tp_traverse = (traverseproc)VecbufT_traverse,
    //.tp_new = vecbuf_i64_new, //??
    .tp_free = PyObject_GC_Del,
    .tp_clear = (inquiry)VecbufT_clear,
    .tp_dealloc = (destructor)VecbufT_dealloc,
};

PyTypeObject VecTType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "vec",
    .tp_doc = "vec doc",
    .tp_basicsize = sizeof(VecTObject),
    .tp_itemsize = 0,
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

PyObject *Vec_T_FromIterable(size_t item_type, PyObject *iterable) {
    VecT v = vec_t_alloc(0, item_type);
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
        if (!VecT_ItemCheck(v, item)) {
            Py_DECREF(iter);
            VEC_DECREF(v);
            Py_DECREF(item);
            return NULL;
        }
        v = Vec_T_Append(v, item);
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
    return Vec_T_Box(v);
}

VecTFeatures TFeatures = {
    &VecTType,
    &VecbufTType,
    Vec_T_New,
    Vec_T_Box,
    Vec_T_Unbox,
    Vec_T_Append,
    Vec_T_Pop,
    Vec_T_Remove,
    Vec_T_Slice,
};
