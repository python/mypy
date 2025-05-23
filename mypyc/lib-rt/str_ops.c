// String primitive operations
//
// These are registered in mypyc.primitives.str_ops.

#include <Python.h>
#include "CPy.h"

// The _PyUnicode_CheckConsistency definition has been moved to the internal API
// https://github.com/python/cpython/pull/106398
#if defined(Py_DEBUG) && defined(CPY_3_13_FEATURES)
#include "internal/pycore_unicodeobject.h"
#endif

// Copied from cpython.git:Objects/unicodeobject.c@0ef4ffeefd1737c18dc9326133c7894d58108c2e.
#define BLOOM_MASK unsigned long
#define BLOOM(mask, ch)     ((mask &  (1UL << ((ch) & (BLOOM_WIDTH - 1)))))
#if LONG_BIT >= 128
#define BLOOM_WIDTH 128
#elif LONG_BIT >= 64
#define BLOOM_WIDTH 64
#elif LONG_BIT >= 32
#define BLOOM_WIDTH 32
#else
#error "LONG_BIT is smaller than 32"
#endif

// Copied from cpython.git:Objects/unicodeobject.c@0ef4ffeefd1737c18dc9326133c7894d58108c2e.
// This is needed for str.strip("...").
static inline BLOOM_MASK
make_bloom_mask(int kind, const void* ptr, Py_ssize_t len)
{
#define BLOOM_UPDATE(TYPE, MASK, PTR, LEN)             \
    do {                                               \
        TYPE *data = (TYPE *)PTR;                      \
        TYPE *end = data + LEN;                        \
        Py_UCS4 ch;                                    \
        for (; data != end; data++) {                  \
            ch = *data;                                \
            MASK |= (1UL << (ch & (BLOOM_WIDTH - 1))); \
        }                                              \
        break;                                         \
    } while (0)

    /* calculate simple bloom-style bitmask for a given unicode string */

    BLOOM_MASK mask;

    mask = 0;
    switch (kind) {
    case PyUnicode_1BYTE_KIND:
        BLOOM_UPDATE(Py_UCS1, mask, ptr, len);
        break;
    case PyUnicode_2BYTE_KIND:
        BLOOM_UPDATE(Py_UCS2, mask, ptr, len);
        break;
    case PyUnicode_4BYTE_KIND:
        BLOOM_UPDATE(Py_UCS4, mask, ptr, len);
        break;
    default:
        Py_UNREACHABLE();
    }
    return mask;

#undef BLOOM_UPDATE
}

PyObject *CPyStr_GetItem(PyObject *str, CPyTagged index) {
    if (PyUnicode_READY(str) != -1) {
        if (CPyTagged_CheckShort(index)) {
            Py_ssize_t n = CPyTagged_ShortAsSsize_t(index);
            Py_ssize_t size = PyUnicode_GET_LENGTH(str);
            if (n < 0)
                n += size;
            if (n < 0 || n >= size) {
                PyErr_SetString(PyExc_IndexError, "string index out of range");
                return NULL;
            }
            enum PyUnicode_Kind kind = (enum PyUnicode_Kind)PyUnicode_KIND(str);
            void *data = PyUnicode_DATA(str);
            Py_UCS4 ch = PyUnicode_READ(kind, data, n);
            PyObject *unicode = PyUnicode_New(1, ch);
            if (unicode == NULL)
                return NULL;

            if (PyUnicode_KIND(unicode) == PyUnicode_1BYTE_KIND) {
                PyUnicode_1BYTE_DATA(unicode)[0] = (Py_UCS1)ch;
            } else if (PyUnicode_KIND(unicode) == PyUnicode_2BYTE_KIND) {
                PyUnicode_2BYTE_DATA(unicode)[0] = (Py_UCS2)ch;
            } else {
                assert(PyUnicode_KIND(unicode) == PyUnicode_4BYTE_KIND);
                PyUnicode_4BYTE_DATA(unicode)[0] = ch;
            }
            return unicode;
        } else {
            PyErr_SetString(PyExc_OverflowError, CPYTHON_LARGE_INT_ERRMSG);
            return NULL;
        }
    } else {
        PyObject *index_obj = CPyTagged_AsObject(index);
        return PyObject_GetItem(str, index_obj);
    }
}

// A simplification of _PyUnicode_JoinArray() from CPython 3.9.6
PyObject *CPyStr_Build(Py_ssize_t len, ...) {
    Py_ssize_t i;
    va_list args;

    // Calculate the total amount of space and check
    // whether all components have the same kind.
    Py_ssize_t sz = 0;
    Py_UCS4 maxchar = 0;
    int use_memcpy = 1; // Use memcpy by default
    PyObject *last_obj = NULL;

    va_start(args, len);
    for (i = 0; i < len; i++) {
        PyObject *item = va_arg(args, PyObject *);
        if (!PyUnicode_Check(item)) {
            PyErr_Format(PyExc_TypeError,
                         "sequence item %zd: expected str instance,"
                         " %.80s found",
                         i, Py_TYPE(item)->tp_name);
            return NULL;
        }
        if (PyUnicode_READY(item) == -1)
            return NULL;

        size_t add_sz = PyUnicode_GET_LENGTH(item);
        Py_UCS4 item_maxchar = PyUnicode_MAX_CHAR_VALUE(item);
        maxchar = Py_MAX(maxchar, item_maxchar);

        // Using size_t to avoid overflow during arithmetic calculation
        if (add_sz > (size_t)(PY_SSIZE_T_MAX - sz)) {
            PyErr_SetString(PyExc_OverflowError,
                            "join() result is too long for a Python string");
            return NULL;
        }
        sz += add_sz;

        // If these strings have different kind, we would call
        // _PyUnicode_FastCopyCharacters() in the following part.
        if (use_memcpy && last_obj != NULL) {
            if (PyUnicode_KIND(last_obj) != PyUnicode_KIND(item))
                use_memcpy = 0;
        }
        last_obj = item;
    }
    va_end(args);

    // Construct the string
    PyObject *res = PyUnicode_New(sz, maxchar);
    if (res == NULL)
        return NULL;

    if (use_memcpy) {
        unsigned char *res_data = PyUnicode_1BYTE_DATA(res);
        unsigned int kind = PyUnicode_KIND(res);

        va_start(args, len);
        for (i = 0; i < len; ++i) {
            PyObject *item = va_arg(args, PyObject *);
            Py_ssize_t itemlen = PyUnicode_GET_LENGTH(item);
            if (itemlen != 0) {
                memcpy(res_data, PyUnicode_DATA(item), kind * itemlen);
                res_data += kind * itemlen;
            }
        }
        va_end(args);
        assert(res_data == PyUnicode_1BYTE_DATA(res) + kind * PyUnicode_GET_LENGTH(res));
    } else {
        Py_ssize_t res_offset = 0;

        va_start(args, len);
        for (i = 0; i < len; ++i) {
            PyObject *item = va_arg(args, PyObject *);
            Py_ssize_t itemlen = PyUnicode_GET_LENGTH(item);
            if (itemlen != 0) {
#if CPY_3_13_FEATURES
                PyUnicode_CopyCharacters(res, res_offset, item, 0, itemlen);
#else
                _PyUnicode_FastCopyCharacters(res, res_offset, item, 0, itemlen);
#endif
                res_offset += itemlen;
            }
        }
        va_end(args);
        assert(res_offset == PyUnicode_GET_LENGTH(res));
    }

#ifdef Py_DEBUG
    assert(_PyUnicode_CheckConsistency(res, 1));
#endif
    return res;
}

CPyTagged CPyStr_Find(PyObject *str, PyObject *substr, CPyTagged start, int direction) {
    CPyTagged end = PyUnicode_GET_LENGTH(str) << 1;
    return CPyStr_FindWithEnd(str, substr, start, end, direction);
}

CPyTagged CPyStr_FindWithEnd(PyObject *str, PyObject *substr, CPyTagged start, CPyTagged end, int direction) {
    Py_ssize_t temp_start = CPyTagged_AsSsize_t(start);
    if (temp_start == -1 && PyErr_Occurred()) {
        PyErr_SetString(PyExc_OverflowError, CPYTHON_LARGE_INT_ERRMSG);
        return CPY_INT_TAG;
    }
    Py_ssize_t temp_end = CPyTagged_AsSsize_t(end);
    if (temp_end == -1 && PyErr_Occurred()) {
        PyErr_SetString(PyExc_OverflowError, CPYTHON_LARGE_INT_ERRMSG);
        return CPY_INT_TAG;
    }
    Py_ssize_t index = PyUnicode_Find(str, substr, temp_start, temp_end, direction);
    if (unlikely(index == -2)) {
        return CPY_INT_TAG;
    }
    return index << 1;
}

PyObject *CPyStr_Split(PyObject *str, PyObject *sep, CPyTagged max_split) {
    Py_ssize_t temp_max_split = CPyTagged_AsSsize_t(max_split);
    if (temp_max_split == -1 && PyErr_Occurred()) {
        PyErr_SetString(PyExc_OverflowError, CPYTHON_LARGE_INT_ERRMSG);
        return NULL;
    }
    return PyUnicode_Split(str, sep, temp_max_split);
}

PyObject *CPyStr_RSplit(PyObject *str, PyObject *sep, CPyTagged max_split) {
    Py_ssize_t temp_max_split = CPyTagged_AsSsize_t(max_split);
    if (temp_max_split == -1 && PyErr_Occurred()) {
        PyErr_SetString(PyExc_OverflowError, CPYTHON_LARGE_INT_ERRMSG);
        return NULL;
    }
    return PyUnicode_RSplit(str, sep, temp_max_split);
}

// This function has been copied from _PyUnicode_XStrip in cpython.git:Objects/unicodeobject.c@0ef4ffeefd1737c18dc9326133c7894d58108c2e.
static PyObject *_PyStr_XStrip(PyObject *self, int striptype, PyObject *sepobj) {
    const void *data;
    int kind;
    Py_ssize_t i, j, len;
    BLOOM_MASK sepmask;
    Py_ssize_t seplen;

    // This check is needed from Python 3.9 and earlier.
    if (PyUnicode_READY(self) == -1 || PyUnicode_READY(sepobj) == -1)
        return NULL;

    kind = PyUnicode_KIND(self);
    data = PyUnicode_DATA(self);
    len = PyUnicode_GET_LENGTH(self);
    seplen = PyUnicode_GET_LENGTH(sepobj);
    sepmask = make_bloom_mask(PyUnicode_KIND(sepobj),
                              PyUnicode_DATA(sepobj),
                              seplen);

    i = 0;
    if (striptype != RIGHTSTRIP) {
        while (i < len) {
            Py_UCS4 ch = PyUnicode_READ(kind, data, i);
            if (!BLOOM(sepmask, ch))
                break;
            if (PyUnicode_FindChar(sepobj, ch, 0, seplen, 1) < 0)
                break;
            i++;
        }
    }

    j = len;
    if (striptype != LEFTSTRIP) {
        j--;
        while (j >= i) {
            Py_UCS4 ch = PyUnicode_READ(kind, data, j);
            if (!BLOOM(sepmask, ch))
                break;
            if (PyUnicode_FindChar(sepobj, ch, 0, seplen, 1) < 0)
                break;
            j--;
        }

        j++;
    }

    return PyUnicode_Substring(self, i, j);
}

// Copied from do_strip function in cpython.git/Objects/unicodeobject.c@0ef4ffeefd1737c18dc9326133c7894d58108c2e.
PyObject *_CPyStr_Strip(PyObject *self, int strip_type, PyObject *sep) {
    if (sep == NULL || sep == Py_None) {
        Py_ssize_t len, i, j;

        // This check is needed from Python 3.9 and earlier.
        if (PyUnicode_READY(self) == -1)
            return NULL;

        len = PyUnicode_GET_LENGTH(self);

        if (PyUnicode_IS_ASCII(self)) {
            const Py_UCS1 *data = PyUnicode_1BYTE_DATA(self);

            i = 0;
            if (strip_type != RIGHTSTRIP) {
                while (i < len) {
                    Py_UCS1 ch = data[i];
                    if (!_Py_ascii_whitespace[ch])
                        break;
                    i++;
                }
            }

            j = len;
            if (strip_type != LEFTSTRIP) {
                j--;
                while (j >= i) {
                    Py_UCS1 ch = data[j];
                    if (!_Py_ascii_whitespace[ch])
                        break;
                    j--;
                }
                j++;
            }
        }
        else {
            int kind = PyUnicode_KIND(self);
            const void *data = PyUnicode_DATA(self);

            i = 0;
            if (strip_type != RIGHTSTRIP) {
                while (i < len) {
                    Py_UCS4 ch = PyUnicode_READ(kind, data, i);
                    if (!Py_UNICODE_ISSPACE(ch))
                        break;
                    i++;
                }
            }

            j = len;
            if (strip_type != LEFTSTRIP) {
                j--;
                while (j >= i) {
                    Py_UCS4 ch = PyUnicode_READ(kind, data, j);
                    if (!Py_UNICODE_ISSPACE(ch))
                        break;
                    j--;
                }
                j++;
            }
        }

        return PyUnicode_Substring(self, i, j);
    }
    return _PyStr_XStrip(self, strip_type, sep);
}

PyObject *CPyStr_Replace(PyObject *str, PyObject *old_substr,
                         PyObject *new_substr, CPyTagged max_replace) {
    Py_ssize_t temp_max_replace = CPyTagged_AsSsize_t(max_replace);
    if (temp_max_replace == -1 && PyErr_Occurred()) {
        PyErr_SetString(PyExc_OverflowError, CPYTHON_LARGE_INT_ERRMSG);
        return NULL;
    }
    return PyUnicode_Replace(str, old_substr, new_substr, temp_max_replace);
}

int CPyStr_Startswith(PyObject *self, PyObject *subobj) {
    Py_ssize_t start = 0;
    Py_ssize_t end = PyUnicode_GET_LENGTH(self);
    if (PyTuple_Check(subobj)) {
        Py_ssize_t i;
        for (i = 0; i < PyTuple_GET_SIZE(subobj); i++) {
            PyObject *substring = PyTuple_GET_ITEM(subobj, i);
            if (!PyUnicode_Check(substring)) {
                PyErr_Format(PyExc_TypeError,
                             "tuple for startswith must only contain str, "
                             "not %.100s",
                             Py_TYPE(substring)->tp_name);
                return 2;
            }
            int result = PyUnicode_Tailmatch(self, substring, start, end, -1);
            if (result) {
                return 1;
            }
        }
        return 0;
    }
    return PyUnicode_Tailmatch(self, subobj, start, end, -1);
}

int CPyStr_Endswith(PyObject *self, PyObject *subobj) {
    Py_ssize_t start = 0;
    Py_ssize_t end = PyUnicode_GET_LENGTH(self);
    if (PyTuple_Check(subobj)) {
        Py_ssize_t i;
        for (i = 0; i < PyTuple_GET_SIZE(subobj); i++) {
            PyObject *substring = PyTuple_GET_ITEM(subobj, i);
            if (!PyUnicode_Check(substring)) {
                PyErr_Format(PyExc_TypeError,
                             "tuple for endswith must only contain str, "
                             "not %.100s",
                             Py_TYPE(substring)->tp_name);
                return 2;
            }
            int result = PyUnicode_Tailmatch(self, substring, start, end, 1);
            if (result) {
                return 1;
            }
        }
        return 0;
    }
    return PyUnicode_Tailmatch(self, subobj, start, end, 1);
}

PyObject *CPyStr_Removeprefix(PyObject *self, PyObject *prefix) {
    Py_ssize_t end = PyUnicode_GET_LENGTH(self);
    int match = PyUnicode_Tailmatch(self, prefix, 0, end, -1);
    if (match) {
        Py_ssize_t prefix_end = PyUnicode_GET_LENGTH(prefix);
        return PyUnicode_Substring(self, prefix_end, end);
    }
    return Py_NewRef(self);
}

PyObject *CPyStr_Removesuffix(PyObject *self, PyObject *suffix) {
    Py_ssize_t end = PyUnicode_GET_LENGTH(self);
    int match = PyUnicode_Tailmatch(self, suffix, 0, end, 1);
    if (match) {
        Py_ssize_t suffix_end = PyUnicode_GET_LENGTH(suffix);
        return PyUnicode_Substring(self, 0, end - suffix_end);
    }
    return Py_NewRef(self);
}

/* This does a dodgy attempt to append in place  */
PyObject *CPyStr_Append(PyObject *o1, PyObject *o2) {
    PyUnicode_Append(&o1, o2);
    return o1;
}

PyObject *CPyStr_GetSlice(PyObject *obj, CPyTagged start, CPyTagged end) {
    if (likely(PyUnicode_CheckExact(obj)
               && CPyTagged_CheckShort(start) && CPyTagged_CheckShort(end))) {
        Py_ssize_t startn = CPyTagged_ShortAsSsize_t(start);
        Py_ssize_t endn = CPyTagged_ShortAsSsize_t(end);
        if (startn < 0) {
            startn += PyUnicode_GET_LENGTH(obj);
            if (startn < 0) {
                startn = 0;
            }
        }
        if (endn < 0) {
            endn += PyUnicode_GET_LENGTH(obj);
            if (endn < 0) {
                endn = 0;
            }
        }
        return PyUnicode_Substring(obj, startn, endn);
    }
    return CPyObject_GetSlice(obj, start, end);
}

/* Check if the given string is true (i.e. its length isn't zero) */
bool CPyStr_IsTrue(PyObject *obj) {
    Py_ssize_t length = PyUnicode_GET_LENGTH(obj);
    return length != 0;
}

Py_ssize_t CPyStr_Size_size_t(PyObject *str) {
    if (PyUnicode_READY(str) != -1) {
        return PyUnicode_GET_LENGTH(str);
    }
    return -1;
}

PyObject *CPy_Decode(PyObject *obj, PyObject *encoding, PyObject *errors) {
    const char *enc = NULL;
    const char *err = NULL;
    if (encoding) {
        enc = PyUnicode_AsUTF8AndSize(encoding, NULL);
        if (!enc) return NULL;
    }
    if (errors) {
        err = PyUnicode_AsUTF8AndSize(errors, NULL);
        if (!err) return NULL;
    }
    if (PyBytes_Check(obj)) {
        return PyUnicode_Decode(((PyBytesObject *)obj)->ob_sval,
                                ((PyVarObject *)obj)->ob_size,
                                enc, err);
    } else {
        return PyUnicode_FromEncodedObject(obj, enc, err);
    }
}

PyObject *CPy_Encode(PyObject *obj, PyObject *encoding, PyObject *errors) {
    const char *enc = NULL;
    const char *err = NULL;
    if (encoding) {
        enc = PyUnicode_AsUTF8AndSize(encoding, NULL);
        if (!enc) return NULL;
    }
    if (errors) {
        err = PyUnicode_AsUTF8AndSize(errors, NULL);
        if (!err) return NULL;
    }
    if (PyUnicode_Check(obj)) {
        return PyUnicode_AsEncodedString(obj, enc, err);
    } else {
        PyErr_BadArgument();
        return NULL;
    }
}


CPyTagged CPyStr_Ord(PyObject *obj) {
    Py_ssize_t s = PyUnicode_GET_LENGTH(obj);
    if (s == 1) {
        int kind = PyUnicode_KIND(obj);
        return PyUnicode_READ(kind, PyUnicode_DATA(obj), 0) << 1;
    }
    PyErr_Format(
        PyExc_TypeError, "ord() expected a character, but a string of length %zd found", s);
    return CPY_INT_TAG;
}
