#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "librt_vecs.h"


PyTypeObject *I64TypeObj;
PyTypeObject *I32TypeObj;
PyTypeObject *I16TypeObj;
PyTypeObject *U8TypeObj;


// vec type proxy
//
// Used for the result of generic vec[t] that must preserve knowledge of 't'.
// These aren't really types. This only supports constructing instances.
typedef struct {
    PyObject_HEAD
    // Tagged pointer to PyTypeObject *, lowest bit set for optional item type
    // Can also be one of magic VEC_ITEM_TYPE_* constants
    size_t item_type;
    size_t depth;  // Number of nested VecNested or VecT types
} VecProxy;

static PyObject *vec_proxy_call(PyObject *self, PyObject *args, PyObject *kw)
{
    static char *kwlist[] = {"", NULL};
    PyObject *init = NULL;
    if (!PyArg_ParseTupleAndKeywords(args, kw, "|O:vec", kwlist, &init)) {
        return NULL;
    }
    VecProxy *p = (VecProxy *)self;
    if (p->depth == 0) {
        if (init == NULL) {
            VecT vec = VecT_New(0, 0, p->item_type);
            if (VEC_IS_ERROR(vec))
                return NULL;
            return VecT_Box(vec, p->item_type);
        } else {
            return VecT_FromIterable(p->item_type, init);
        }
    } else {
        if (init == NULL) {
            VecNested vec = VecVec_New(0, 0, p->item_type, p->depth);
            if (VEC_IS_ERROR(vec))
                return NULL;
            return VecVec_Box(vec);
        } else {
            return VecVec_FromIterable(p->item_type, p->depth, init);
        }
    }
}

static int
VecProxy_traverse(VecProxy *self, visitproc visit, void *arg)
{
    if (!Vec_IsMagicItemType(self->item_type))
        Py_VISIT((PyObject *)(self->item_type & ~1));
    return 0;
}

static void
VecProxy_dealloc(VecProxy *self)
{
    if (self->item_type && !Vec_IsMagicItemType(self->item_type)) {
        Py_DECREF((PyObject *)(self->item_type & ~1));
        self->item_type = 0;
    }
    PyObject_GC_Del(self);
}

PyObject *Vec_TypeToStr(size_t item_type, size_t depth) {
    PyObject *item = NULL;
    PyObject *result = NULL;

    if (depth == 0) {
        if ((item_type & ~1) == VEC_ITEM_TYPE_I64) {
            item = PyUnicode_FromFormat("i64");
        } else if ((item_type & ~1) == VEC_ITEM_TYPE_U8) {
            item = PyUnicode_FromFormat("u8");
        } else if ((item_type & ~1) == VEC_ITEM_TYPE_FLOAT) {
            item = PyUnicode_FromFormat("float");
        } else if ((item_type & ~1) == VEC_ITEM_TYPE_I32) {
            item = PyUnicode_FromFormat("i32");
        } else if ((item_type & ~1) == VEC_ITEM_TYPE_I16) {
            item = PyUnicode_FromFormat("i16");
        } else if ((item_type & ~1) == VEC_ITEM_TYPE_BOOL) {
            item = PyUnicode_FromFormat("bool");
        } else {
            item = PyObject_GetAttrString((PyObject *)(item_type & ~1), "__name__");
            if (item == NULL) {
                return NULL;
            }
            if (item_type & 1) {
                PyObject *optional_item = PyUnicode_FromFormat("%U | None", item);
                Py_DECREF(item);
                if (optional_item == NULL) {
                    return NULL;
                }
                item = optional_item;
            }
        }
    } else {
        item = Vec_TypeToStr(item_type, depth - 1);
    }

    if (item == NULL) {
        return NULL;
    }

    result = PyUnicode_FromFormat("vec[%U]", item);
    Py_DECREF(item);
    return result;
}

PyObject *VecProxy_repr(PyObject *self) {
    PyObject *l = NULL;
    PyObject *prefix = NULL;
    PyObject *suffix = NULL;
    PyObject *sep = NULL;
    PyObject *type_str = NULL;
    PyObject *result = NULL;

    l = PyList_New(0);
    if (l == NULL) goto error;

    prefix = PyUnicode_FromString("<class_proxy '");
    if (prefix == NULL) goto error;

    suffix = PyUnicode_FromString("'>");
    if (suffix == NULL) goto error;

    sep = PyUnicode_FromString("");
    if (sep == NULL) goto error;

    if (PyList_Append(l, prefix) < 0) goto error;

    VecProxy *v = (VecProxy *)self;
    type_str = Vec_TypeToStr(v->item_type, v->depth);
    if (type_str == NULL) goto error;

    if (PyList_Append(l, type_str) < 0) goto error;
    if (PyList_Append(l, suffix) < 0) goto error;

    result = PyUnicode_Join(sep, l);

error:
    Py_XDECREF(l);
    Py_XDECREF(prefix);
    Py_XDECREF(suffix);
    Py_XDECREF(sep);
    Py_XDECREF(type_str);
    return result;
}

PyTypeObject VecProxyType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "vec_proxy",
    .tp_basicsize = sizeof(VecProxy),
    .tp_itemsize = 0,
    .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC,
    .tp_call = vec_proxy_call,
    .tp_traverse = (traverseproc)VecProxy_traverse,
    .tp_dealloc = (destructor)VecProxy_dealloc,
    .tp_repr = (reprfunc)VecProxy_repr,
};


// The 'vec' type
//
// This cannot be instantiated, and it's only used for isinstance and indexing: vec[T].

typedef struct {
    PyObject_HEAD
} VecGeneric;

static PyObject *extract_optional_item(PyObject *item) {
    PyObject *args = PyObject_GetAttrString(item, "__args__");
    if (args == NULL) {
        PyErr_Clear();
        return NULL;
    }
    if (!PyTuple_CheckExact(args))
        goto error;
    if (PyTuple_GET_SIZE(args) != 2)
        goto error;
    PyObject *item0 = PyTuple_GET_ITEM(args, 0);
    PyObject *item1 = PyTuple_GET_ITEM(args, 1);
    if (item0 == (PyObject *)Py_None->ob_type) {
        Py_DECREF(args);
        return item1;
    } else if (item1 == (PyObject *)Py_None->ob_type) {
        Py_DECREF(args);
        return item0;
    }
  error:
    Py_DECREF(args);
    return NULL;
}

static PyObject *vec_class_getitem(PyObject *type, PyObject *item)
{
    if (item == (PyObject *)I64TypeObj) {
        Py_INCREF(&VecI64Type);
        return (PyObject *)&VecI64Type;
    } else if (item == (PyObject *)U8TypeObj) {
        Py_INCREF(&VecU8Type);
        return (PyObject *)&VecU8Type;
    } else if (item == (PyObject *)&PyFloat_Type) {
        Py_INCREF(&VecFloatType);
        return (PyObject *)&VecFloatType;
    } else if (item == (PyObject *)I32TypeObj) {
        Py_INCREF(&VecI32Type);
        return (PyObject *)&VecI32Type;
    } else if (item == (PyObject *)I16TypeObj) {
        Py_INCREF(&VecI16Type);
        return (PyObject *)&VecI16Type;
    } else if (item == (PyObject *)&PyBool_Type) {
        Py_INCREF(&VecBoolType);
        return (PyObject *)&VecBoolType;
    } else {
        size_t depth = 0;
        size_t item_type;
        int optional = 0;
        if (!PyObject_TypeCheck(item, &PyType_Type)) {
            PyObject *it = extract_optional_item(item);
            if (it != NULL) {
                optional = 1;
                item = it;
            }
            if (item->ob_type == &VecProxyType) {
                if (optional) {
                    PyErr_SetString(PyExc_TypeError, "optional type not expected in vec[...]");
                    return NULL;
                }
                VecProxy *p = (VecProxy *)item;
                item_type = p->item_type;
                depth = p->depth + 1;
            } else if (!PyObject_TypeCheck(item, &PyType_Type)) {
                PyErr_SetString(PyExc_TypeError, "type object expected in vec[...]");
                return NULL;
            } else {
                item_type = (size_t)item | optional;
            }
        } else {
            if (item == (PyObject *)&VecI64Type) {
                item_type = VEC_ITEM_TYPE_I64;
                depth = 1;
                // TODO: Check optionals?
            } else if (item == (PyObject *)&VecU8Type) {
                item_type = VEC_ITEM_TYPE_U8;
                depth = 1;
                // TODO: Check optionals?
            } else if (item == (PyObject *)&VecFloatType) {
                item_type = VEC_ITEM_TYPE_FLOAT;
                depth = 1;
                // TODO: Check optionals?
            } else if (item == (PyObject *)&VecI32Type) {
                item_type = VEC_ITEM_TYPE_I32;
                depth = 1;
                // TODO: Check optionals?
            } else if (item == (PyObject *)&VecI16Type) {
                item_type = VEC_ITEM_TYPE_I16;
                depth = 1;
                // TODO: Check optionals?
            } else if (item == (PyObject *)&VecBoolType) {
                item_type = VEC_ITEM_TYPE_BOOL;
                depth = 1;
                // TODO: Check optionals?
            } else {
                item_type = (size_t)item;
            }
        }
        if (item == (PyObject *)&PyLong_Type) {
            PyErr_Format(PyExc_ValueError, "unsupported type in vec[%s] (use i64, i32, i16, or u8)",
                         ((PyTypeObject *)item)->tp_name);
            return NULL;
        }
        VecProxy *p;
        p = PyObject_GC_New(VecProxy, &VecProxyType);
        if (p == NULL)
            return NULL;
        Py_INCREF(item);
        p->item_type = item_type;
        p->depth = depth;
        PyObject_GC_Track(p);
        return (PyObject *)p;
    }
}

static PyMethodDef vec_methods[] = {
    {"__class_getitem__", vec_class_getitem, METH_O|METH_CLASS, NULL},
    {NULL, NULL, 0, NULL},  /* Sentinel */
};

PyTypeObject VecGenericType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "vec",
    .tp_basicsize = sizeof(VecGeneric),
    .tp_itemsize = 0,
    .tp_flags = Py_TPFLAGS_DEFAULT,
    .tp_methods = vec_methods,
};

PyObject *Vec_GenericRepr(PyObject *vec, size_t item_type, size_t depth, int verbose) {
    PyObject *l = NULL;
    PyObject *prefix = NULL;
    PyObject *mid = NULL;
    PyObject *suffix = NULL;
    PyObject *sep = NULL;
    PyObject *comma = NULL;
    PyObject *result = NULL;

    l = PyList_New(0);
    if (l == NULL) goto error;

    sep = PyUnicode_FromString("");
    if (sep == NULL) goto error;

    comma = PyUnicode_FromString(", ");
    if (comma == NULL) goto error;

    if (verbose) {
        prefix = Vec_TypeToStr(item_type, depth);
        if (prefix == NULL) goto error;

        mid = PyUnicode_FromString("([");
        if (mid == NULL) goto error;

        suffix = PyUnicode_FromString("])");
        if (suffix == NULL) goto error;
    } else {
        prefix = PyUnicode_FromString("");
        if (prefix == NULL) goto error;

        mid = PyUnicode_FromString("[");
        if (mid == NULL) goto error;

        suffix = PyUnicode_FromString("]");
        if (suffix == NULL) goto error;
    }

    if (PyList_Append(l, prefix) < 0) goto error;
    if (PyList_Append(l, mid) < 0) goto error;

    Py_ssize_t len = PyObject_Length(vec);
    if (len < 0) goto error;

    for (Py_ssize_t i = 0; i < len; i++) {
        PyObject *it = PySequence_GetItem(vec, i);
        if (it == NULL) goto error;

        PyObject *r;
        if (depth == 0 || it == Py_None) {
            r = PyObject_Repr(it);
        } else {
            r = Vec_GenericRepr(it, item_type, depth - 1, 0);
        }
        Py_DECREF(it);

        if (r == NULL) goto error;

        if (PyList_Append(l, r) < 0) {
            Py_DECREF(r);
            goto error;
        }
        Py_DECREF(r);

        if (i + 1 < len) {
            if (PyList_Append(l, comma) < 0) goto error;
        }
    }

    if (PyList_Append(l, suffix) < 0) goto error;

    result = PyUnicode_Join(sep, l);

error:
    Py_XDECREF(l);
    Py_XDECREF(prefix);
    Py_XDECREF(mid);
    Py_XDECREF(suffix);
    Py_XDECREF(sep);
    Py_XDECREF(comma);
    return result;
}

// Generic comparison implementation for vecs with PyObject * items.
PyObject *Vec_GenericRichcompare(Py_ssize_t *len, PyObject **items,
                                  Py_ssize_t *other_len, PyObject **other_items,
                                  int op) {
    int cmp = 1;
    PyObject *res;
    if (op == Py_EQ || op == Py_NE) {
        if (*len != *other_len) {
            cmp = 0;
        } else {
            for (Py_ssize_t i = 0; i < *len && i < *other_len; i++) {
                int itemcmp = PyObject_RichCompareBool(items[i], other_items[i], Py_EQ);
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
    } else
        res = Py_NotImplemented;
    Py_INCREF(res);
    return res;
}

int Vec_GenericRemove(Py_ssize_t *len, PyObject **items, PyObject *item) {
    for (Py_ssize_t i = 0; i < *len; i++) {
        int match = 0;
        if (items[i] == item)
            match = 1;
        else {
            int itemcmp = PyObject_RichCompareBool(items[i], item, Py_EQ);
            if (itemcmp < 0)
                return 0;
            match = itemcmp;
        }
        if (match) {
            Py_CLEAR(items[i]);
            for (; i < *len - 1; i++) {
                items[i] = items[i + 1];
            }
            (*len)--;
            return 1;
        }
    }
    PyErr_SetString(PyExc_ValueError, "vec.remove(x): x not in vec");
    return 0;
}

PyObject *Vec_GenericPop(Py_ssize_t *len, PyObject **items, Py_ssize_t index) {
    if (index < 0)
        index += *len;

    if (index < 0 || index >= *len) {
        PyErr_SetString(PyExc_IndexError, "index out of range");
        return NULL;
    }

    PyObject *item = items[index];
    for (Py_ssize_t i = index; i < *len - 1; i++)
        items[i] = items[i + 1];

    (*len)--;
    return item;
}

PyObject *Vec_GenericPopWrapper(Py_ssize_t *len, PyObject **items, PyObject *args) {
    Py_ssize_t index = -1;
    if (!PyArg_ParseTuple(args, "|n:pop", &index))
        return NULL;

    return Vec_GenericPop(len, items, index);
}

// Module-level functions

static PyObject *vec_append(PyObject *self, PyObject *args)
{
    PyObject *vec;
    PyObject *item;

    if (!PyArg_ParseTuple(args, "OO", &vec, &item))
        return NULL;

    if (VecI64_Check(vec)) {
        int64_t x = VecI64_UnboxItem(item);
        if (VecI64_IsUnboxError(x)) {
            return NULL;
        }
        VecI64 v = ((VecI64Object *)vec)->vec;
        VEC_INCREF(v);
        v = VecI64_Append(v, x);
        if (VEC_IS_ERROR(v))
            return NULL;
        return VecI64_Box(v);
    } else if (VecU8_Check(vec)) {
        uint8_t x = VecU8_UnboxItem(item);
        if (VecU8_IsUnboxError(x)) {
            return NULL;
        }
        VecU8 v = ((VecU8Object *)vec)->vec;
        VEC_INCREF(v);
        v = VecU8_Append(v, x);
        if (VEC_IS_ERROR(v))
            return NULL;
        return VecU8_Box(v);
    } else if (VecFloat_Check(vec)) {
        double x = VecFloat_UnboxItem(item);
        if (VecFloat_IsUnboxError(x)) {
            return NULL;
        }
        VecFloat v = ((VecFloatObject *)vec)->vec;
        VEC_INCREF(v);
        v = VecFloat_Append(v, x);
        if (VEC_IS_ERROR(v))
            return NULL;
        return VecFloat_Box(v);
    } else if (VecI32_Check(vec)) {
        int32_t x = VecI32_UnboxItem(item);
        if (VecI32_IsUnboxError(x)) {
            return NULL;
        }
        VecI32 v = ((VecI32Object *)vec)->vec;
        VEC_INCREF(v);
        v = VecI32_Append(v, x);
        if (VEC_IS_ERROR(v))
            return NULL;
        return VecI32_Box(v);
    } else if (VecI16_Check(vec)) {
        int16_t x = VecI16_UnboxItem(item);
        if (VecI16_IsUnboxError(x)) {
            return NULL;
        }
        VecI16 v = ((VecI16Object *)vec)->vec;
        VEC_INCREF(v);
        v = VecI16_Append(v, x);
        if (VEC_IS_ERROR(v))
            return NULL;
        return VecI16_Box(v);
    } else if (VecBool_Check(vec)) {
        double x = VecBool_UnboxItem(item);
        if (VecBool_IsUnboxError(x)) {
            return NULL;
        }
        VecBool v = ((VecBoolObject *)vec)->vec;
        VEC_INCREF(v);
        v = VecBool_Append(v, x);
        if (VEC_IS_ERROR(v))
            return NULL;
        return VecBool_Box(v);
    } else if (VecT_Check(vec)) {
        VecT v = ((VecTObject *)vec)->vec;
        if (!VecT_ItemCheck(v, item, v.buf->item_type)) {
            return NULL;
        }
        VEC_INCREF(v);
        v = VecT_Append(v, item, v.buf->item_type);
        if (VEC_IS_ERROR(v))
            return NULL;
        return VecT_Box(v, v.buf->item_type);
    } else if (VecVec_Check(vec)) {
        VecNested v = ((VecNestedObject *)vec)->vec;
        VecNestedBufItem vecitem;
        if (VecVec_UnboxItem(v, item, &vecitem) < 0)
            return NULL;
        VEC_INCREF(v);
        v = VecVec_Append(v, vecitem);
        if (VEC_IS_ERROR(v))
            return NULL;
        return VecVec_Box(v);
    } else {
        PyErr_Format(PyExc_TypeError, "vec argument expected, got %.100s",
                     Py_TYPE(vec)->tp_name);
        return NULL;
    }
}

static PyObject *vec_remove(PyObject *self, PyObject *args)
{
    PyObject *vec;
    PyObject *item;

    if (!PyArg_ParseTuple(args, "OO", &vec, &item))
        return NULL;

    if (VecI64_Check(vec)) {
        int64_t x = VecI64_UnboxItem(item);
        if (VecI64_IsUnboxError(x)) {
            return NULL;
        }
        VecI64 v = ((VecI64Object *)vec)->vec;
        VEC_INCREF(v);
        v = VecI64_Remove(v, x);
        if (VEC_IS_ERROR(v))
            return NULL;
        return VecI64_Box(v);
    } else if (VecU8_Check(vec)) {
        uint8_t x = VecU8_UnboxItem(item);
        if (VecU8_IsUnboxError(x)) {
            return NULL;
        }
        VecU8 v = ((VecU8Object *)vec)->vec;
        VEC_INCREF(v);
        v = VecU8_Remove(v, x);
        if (VEC_IS_ERROR(v))
            return NULL;
        return VecU8_Box(v);
    } else if (VecFloat_Check(vec)) {
        double x = VecFloat_UnboxItem(item);
        if (VecFloat_IsUnboxError(x)) {
            return NULL;
        }
        VecFloat v = ((VecFloatObject *)vec)->vec;
        VEC_INCREF(v);
        v = VecFloat_Remove(v, x);
        if (VEC_IS_ERROR(v))
            return NULL;
        return VecFloat_Box(v);
    } else if (VecI32_Check(vec)) {
        int32_t x = VecI32_UnboxItem(item);
        if (VecI32_IsUnboxError(x)) {
            return NULL;
        }
        VecI32 v = ((VecI32Object *)vec)->vec;
        VEC_INCREF(v);
        v = VecI32_Remove(v, x);
        if (VEC_IS_ERROR(v))
            return NULL;
        return VecI32_Box(v);
    } else if (VecI16_Check(vec)) {
        int16_t x = VecI16_UnboxItem(item);
        if (VecI16_IsUnboxError(x)) {
            return NULL;
        }
        VecI16 v = ((VecI16Object *)vec)->vec;
        VEC_INCREF(v);
        v = VecI16_Remove(v, x);
        if (VEC_IS_ERROR(v))
            return NULL;
        return VecI16_Box(v);
    } else if (VecBool_Check(vec)) {
        char x = VecBool_UnboxItem(item);
        if (VecBool_IsUnboxError(x)) {
            return NULL;
        }
        VecBool v = ((VecBoolObject *)vec)->vec;
        VEC_INCREF(v);
        v = VecBool_Remove(v, x);
        if (VEC_IS_ERROR(v))
            return NULL;
        return VecBool_Box(v);
    } else if (VecT_Check(vec)) {
        VecT v = ((VecTObject *)vec)->vec;
        if (!VecT_ItemCheck(v, item, v.buf->item_type)) {
            return NULL;
        }
        VEC_INCREF(v);
        v = VecT_Remove(v, item);
        if (VEC_IS_ERROR(v))
            return NULL;
        return VecT_Box(v, v.buf->item_type);
    } else if (VecVec_Check(vec)) {
        VecNested v = ((VecNestedObject *)vec)->vec;
        VecNestedBufItem vecitem;
        if (VecVec_UnboxItem(v, item, &vecitem) < 0)
            return NULL;
        VEC_INCREF(v);
        v = VecVec_Remove(v, vecitem);
        if (VEC_IS_ERROR(v))
            return NULL;
        return VecVec_Box(v);
    } else {
        PyErr_Format(PyExc_TypeError, "vec argument expected, got %.100s",
                     Py_TYPE(vec)->tp_name);
        return NULL;
    }
}

static PyObject *vec_pop(PyObject *self, PyObject *args)
{
    PyObject *vec;
    Py_ssize_t index = -1;

    if (!PyArg_ParseTuple(args, "O|n:pop", &vec, &index))
        return NULL;

    PyObject *result_item0;
    PyObject *result_item1;

    if (VecI64_Check(vec)) {
        VecI64 v = ((VecI64Object *)vec)->vec;
        VecI64PopResult r;
        r = VecI64_Pop(v, index);
        if (VEC_IS_ERROR(r.f0))
            return NULL;
        if ((result_item0 = VecI64_Box(r.f0)) == NULL)
            return NULL;
        result_item1 = VecI64_BoxItem(r.f1);
    } else if (VecU8_Check(vec)) {
        VecU8 v = ((VecU8Object *)vec)->vec;
        VecU8PopResult r;
        r = VecU8_Pop(v, index);
        if (VEC_IS_ERROR(r.f0))
            return NULL;
        if ((result_item0 = VecU8_Box(r.f0)) == NULL)
            return NULL;
        result_item1 = VecU8_BoxItem(r.f1);
    } else if (VecFloat_Check(vec)) {
        VecFloat v = ((VecFloatObject *)vec)->vec;
        VecFloatPopResult r;
        r = VecFloat_Pop(v, index);
        if (VEC_IS_ERROR(r.f0))
            return NULL;
        if ((result_item0 = VecFloat_Box(r.f0)) == NULL)
            return NULL;
        result_item1 = VecFloat_BoxItem(r.f1);
    } else if (VecI32_Check(vec)) {
        VecI32 v = ((VecI32Object *)vec)->vec;
        VecI32PopResult r;
        r = VecI32_Pop(v, index);
        if (VEC_IS_ERROR(r.f0))
            return NULL;
        if ((result_item0 = VecI32_Box(r.f0)) == NULL)
            return NULL;
        result_item1 = VecI32_BoxItem(r.f1);
    } else if (VecI16_Check(vec)) {
        VecI16 v = ((VecI16Object *)vec)->vec;
        VecI16PopResult r;
        r = VecI16_Pop(v, index);
        if (VEC_IS_ERROR(r.f0))
            return NULL;
        if ((result_item0 = VecI16_Box(r.f0)) == NULL)
            return NULL;
        result_item1 = VecI16_BoxItem(r.f1);
    } else if (VecBool_Check(vec)) {
        VecBool v = ((VecBoolObject *)vec)->vec;
        VecBoolPopResult r;
        r = VecBool_Pop(v, index);
        if (VEC_IS_ERROR(r.f0))
            return NULL;
        if ((result_item0 = VecBool_Box(r.f0)) == NULL)
            return NULL;
        result_item1 = VecBool_BoxItem(r.f1);
    } else if (VecT_Check(vec)) {
        VecT v = ((VecTObject *)vec)->vec;
        VecTPopResult r;
        r = VecT_Pop(v, index);
        if (VEC_IS_ERROR(r.f0))
            return NULL;
        result_item0 = VecT_Box(r.f0, v.buf->item_type);
        if (result_item0 == NULL) {
            Py_DECREF(r.f1);
            return NULL;
        }
        result_item1 = r.f1;
    } else if (VecVec_Check(vec)) {
        VecNested v = ((VecNestedObject *)vec)->vec;
        VecNestedPopResult r;
        r = VecVec_Pop(v, index);
        if (VEC_IS_ERROR(r.f0))
            return NULL;
        result_item0 = VecVec_Box(r.f0);
        if (result_item0 == NULL) {
            Py_DECREF(r.f0.buf);
            Py_DECREF(r.f1.buf);
            return NULL;
        }
        result_item1 = VecVec_BoxItem(r.f0, r.f1);
        if (result_item1 == NULL) {
            Py_DECREF(result_item0);
            Py_DECREF(r.f1.buf);
            return NULL;
        }
    } else {
        PyErr_Format(PyExc_TypeError, "vec argument expected, got %.100s",
                     Py_TYPE(vec)->tp_name);
        return NULL;
    }

    if (result_item1 == NULL) {
        Py_DECREF(result_item0);
        return NULL;
    }

    PyObject *res = PyTuple_New(2);
    if (res == NULL) {
        Py_DECREF(result_item0);
        Py_DECREF(result_item1);
        return NULL;
    }

    PyTuple_SET_ITEM(res, 0, result_item0);
    PyTuple_SET_ITEM(res, 1, result_item1);
    return res;
}

static PyMethodDef VecsMethods[] = {
    {"append",  vec_append, METH_VARARGS, "Append a value to the end of a vec"},
    {"remove",  vec_remove, METH_VARARGS, "Remove first occurrence of value"},
    {"pop",  vec_pop, METH_VARARGS, "Remove and return item at index (default last)"},
    {NULL, NULL, 0, NULL}        /* Sentinel */
};

static PyModuleDef vecsmodule = {
    PyModuleDef_HEAD_INIT,
    .m_name = "vecs",
    .m_doc = "vecs doc",
    .m_size = -1,
    .m_methods = VecsMethods,
};

static VecCapsule Capsule = {
    &TFeatures,
    &TExtFeatures,
    &I64Features,
    &I32Features,
    &I16Features,
    &U8Features,
    &FloatFeatures,
    &BoolFeatures,
};

PyMODINIT_FUNC
PyInit_vecs(void)
{
    PyObject *ext = PyImport_ImportModule("mypy_extensions");
    if (ext == NULL) {
        return NULL;
    }

    I64TypeObj = (PyTypeObject *)PyObject_GetAttrString(ext, "i64");
    // TODO: Check that it's a type object!
    if (I64TypeObj == NULL) {
        return NULL;
    }
    I32TypeObj = (PyTypeObject *)PyObject_GetAttrString(ext, "i32");
    // TODO: Check that it's a type object!
    if (I32TypeObj == NULL) {
        return NULL;
    }
    I16TypeObj = (PyTypeObject *)PyObject_GetAttrString(ext, "i16");
    // TODO: Check that it's a type object!
    if (I16TypeObj == NULL) {
        return NULL;
    }
    U8TypeObj = (PyTypeObject *)PyObject_GetAttrString(ext, "u8");
    // TODO: Check that it's a type object!
    if (U8TypeObj == NULL) {
        return NULL;
    }

    if (PyType_Ready(&VecGenericType) < 0)
        return NULL;
    if (PyType_Ready(&VecProxyType) < 0)
        return NULL;

    if (PyType_Ready(&VecTType) < 0)
        return NULL;
    if (PyType_Ready(&VecTBufType) < 0)
        return NULL;

    if (PyType_Ready(&VecNestedType) < 0)
        return NULL;
    if (PyType_Ready(&VecNestedBufType) < 0)
        return NULL;

    if (PyType_Ready(&VecI64Type) < 0)
        return NULL;
    if (PyType_Ready(&VecI64BufType) < 0)
        return NULL;
    if (PyType_Ready(&VecI32Type) < 0)
        return NULL;
    if (PyType_Ready(&VecI32BufType) < 0)
        return NULL;
    if (PyType_Ready(&VecI16Type) < 0)
        return NULL;
    if (PyType_Ready(&VecI16BufType) < 0)
        return NULL;
    if (PyType_Ready(&VecU8Type) < 0)
        return NULL;
    if (PyType_Ready(&VecU8BufType) < 0)
        return NULL;
    if (PyType_Ready(&VecFloatType) < 0)
        return NULL;
    if (PyType_Ready(&VecFloatBufType) < 0)
        return NULL;
    if (PyType_Ready(&VecBoolType) < 0)
        return NULL;
    if (PyType_Ready(&VecBoolBufType) < 0)
        return NULL;

    PyObject *m = PyModule_Create(&vecsmodule);
    if (m == NULL)
        return NULL;

    Py_INCREF(&VecGenericType);
    if (PyModule_AddObject(m, "vec", (PyObject *)&VecGenericType) < 0) {
        Py_DECREF(&VecGenericType);
        Py_DECREF(m);
        return NULL;
    }

    PyObject *c_api = PyCapsule_New(&Capsule, "librt.vecs._C_API", NULL);
    if (c_api == NULL)
        return NULL;

    if (PyModule_AddObject(m, "_C_API", c_api) < 0) {
        Py_XDECREF(c_api);
        Py_DECREF(&VecGenericType);
        Py_DECREF(m);
        return NULL;
    }

    Py_DECREF(ext);

    return m;
}
