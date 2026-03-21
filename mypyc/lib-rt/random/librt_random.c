#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdint.h>
#include <string.h>

#include "mypyc_util.h"

//
// ChaCha8 PRNG with forward secrecy
//

#define CHACHA8_RESEED_INTERVAL 16

typedef struct {
    uint32_t seed[8];       // 256-bit key
    uint32_t buf[16];       // output buffer: one ChaCha8 block
    uint32_t counter;       // block counter
    uint8_t  used;          // index into buf
    uint8_t  n;             // usable values in buf (8 or 16)
    uint8_t  blocks_left;   // blocks until next reseed
} chacha8_rng;

static inline uint32_t
rotl32(uint32_t x, int n) {
    return (x << n) | (x >> (32 - n));
}

#define QUARTERROUND(a, b, c, d) \
    do { \
        a += b; d ^= a; d = rotl32(d, 16); \
        c += d; b ^= c; b = rotl32(b, 12); \
        a += b; d ^= a; d = rotl32(d, 8);  \
        c += d; b ^= c; b = rotl32(b, 7);  \
    } while (0)

static void
chacha8_block(const uint32_t seed[8], uint32_t counter, uint32_t out[16])
{
    // "expand 32-byte k"
    uint32_t s[16] = {
        0x61707865, 0x3320646e, 0x79622d32, 0x6b206574,
        seed[0], seed[1], seed[2], seed[3],
        seed[4], seed[5], seed[6], seed[7],
        counter, 0, 0, 0   // counter (low 32), counter (high 32), nonce
    };

    memcpy(out, s, sizeof(uint32_t) * 16);

    // 4 double-rounds = 8 rounds
    for (int i = 0; i < 4; i++) {
        // Column rounds
        QUARTERROUND(out[0], out[4], out[ 8], out[12]);
        QUARTERROUND(out[1], out[5], out[ 9], out[13]);
        QUARTERROUND(out[2], out[6], out[10], out[14]);
        QUARTERROUND(out[3], out[7], out[11], out[15]);
        // Diagonal rounds
        QUARTERROUND(out[0], out[5], out[10], out[15]);
        QUARTERROUND(out[1], out[6], out[11], out[12]);
        QUARTERROUND(out[2], out[7], out[ 8], out[13]);
        QUARTERROUND(out[3], out[4], out[ 9], out[14]);
    }

    // Add original state back (non-invertible)
    for (int i = 0; i < 16; i++)
        out[i] += s[i];
}

// Fill entropy from OS via os.urandom(), which handles short reads,
// EINTR, and platform differences internally.
// Returns 0 on success, -1 on failure (with Python exception set).
static int
fill_os_entropy(void *buf, size_t len)
{
    PyObject *os_mod = PyImport_ImportModule("os");
    if (os_mod == NULL)
        return -1;
    PyObject *bytes = PyObject_CallMethod(os_mod, "urandom", "n", (Py_ssize_t)len);
    Py_DECREF(os_mod);
    if (bytes == NULL)
        return -1;
    memcpy(buf, PyBytes_AS_STRING(bytes), len);
    Py_DECREF(bytes);
    return 0;
}

static void
chacha8_refill(chacha8_rng *rng)
{
    chacha8_block(rng->seed, rng->counter, rng->buf);
    rng->counter++;
    rng->used = 0;
    rng->blocks_left--;

    if (unlikely(rng->blocks_left == 0)) {
        // Forward secrecy reseed: steal last 8 words as new key
        memcpy(rng->seed, rng->buf + 8, sizeof(uint32_t) * 8);
        rng->n = 8;  // only 8 words usable this block
        rng->counter = 0;
        rng->blocks_left = CHACHA8_RESEED_INTERVAL;
    } else {
        rng->n = 16;
    }
}

static inline uint32_t
chacha8_next(chacha8_rng *rng)
{
    if (unlikely(rng->used >= rng->n))
        chacha8_refill(rng);
    return rng->buf[rng->used++];
}

static int
chacha8_init(chacha8_rng *rng)
{
    if (fill_os_entropy(rng->seed, sizeof(rng->seed)) < 0)
        return -1;
    rng->counter = 0;
    rng->used = 16;  // force immediate refill on first call
    rng->n = 16;
    rng->blocks_left = CHACHA8_RESEED_INTERVAL;
    return 0;
}

//
// Random Python type
//

typedef struct {
    PyObject_HEAD
    chacha8_rng rng;
} RandomObject;

static PyTypeObject RandomType;

static PyObject*
Random_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    if (type != &RandomType) {
        PyErr_SetString(PyExc_TypeError, "Random cannot be subclassed");
        return NULL;
    }

    RandomObject *self = (RandomObject *)type->tp_alloc(type, 0);
    if (self != NULL) {
        if (chacha8_init(&self->rng) < 0) {
            Py_DECREF(self);
            return NULL;
        }
    }
    return (PyObject *)self;
}

static int
Random_init(RandomObject *self, PyObject *args, PyObject *kwds)
{
    if (!PyArg_ParseTuple(args, "")) {
        return -1;
    }

    if (kwds != NULL && PyDict_Size(kwds) > 0) {
        PyErr_SetString(PyExc_TypeError,
                        "Random() takes no keyword arguments");
        return -1;
    }

    return 0;
}

static PyObject*
Random_randint(RandomObject *self, PyObject *const *args, Py_ssize_t nargs) {
    if (nargs != 2) {
        PyErr_Format(PyExc_TypeError,
                     "randint() takes exactly 2 arguments (%zd given)", nargs);
        return NULL;
    }

    long long a = PyLong_AsLongLong(args[0]);
    if (a == -1 && PyErr_Occurred())
        return NULL;

    long long b = PyLong_AsLongLong(args[1]);
    if (b == -1 && PyErr_Occurred())
        return NULL;

    if (a > b) {
        PyErr_SetString(PyExc_ValueError,
                        "empty range for randint()");
        return NULL;
    }

    unsigned long long range = (unsigned long long)(b - a) + 1;
    uint32_t r = chacha8_next(&self->rng);
    long long result = a + (long long)(r % range);
    return PyLong_FromLongLong(result);
}

static PyObject*
Random_random(RandomObject *self, PyObject *Py_UNUSED(ignored)) {
    uint32_t r = chacha8_next(&self->rng);
    // Scale to [0.0, 1.0)
    double result = r / 4294967296.0;  // 2^32
    return PyFloat_FromDouble(result);
}

static PyMethodDef Random_methods[] = {
    {"randint", (PyCFunction) Random_randint, METH_FASTCALL,
     PyDoc_STR("Return random integer in range [a, b], including both end points.")
    },
    {"random", (PyCFunction) Random_random, METH_NOARGS,
     PyDoc_STR("Return random float in [0.0, 1.0).")
    },
    {NULL}  /* Sentinel */
};

static PyTypeObject RandomType = {
    .ob_base = PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "Random",
    .tp_doc = PyDoc_STR("Fast random number generator using ChaCha8"),
    .tp_basicsize = sizeof(RandomObject),
    .tp_itemsize = 0,
    .tp_flags = Py_TPFLAGS_DEFAULT,
    .tp_new = Random_new,
    .tp_init = (initproc) Random_init,
    .tp_methods = Random_methods,
};

// Module definition

static PyMethodDef librt_random_module_methods[] = {
    {NULL, NULL, 0, NULL}
};

static int
librt_random_module_exec(PyObject *m)
{
    if (PyType_Ready(&RandomType) < 0) {
        return -1;
    }
    if (PyModule_AddObjectRef(m, "Random", (PyObject *) &RandomType) < 0) {
        return -1;
    }
    return 0;
}

static PyModuleDef_Slot librt_random_module_slots[] = {
    {Py_mod_exec, librt_random_module_exec},
#ifdef Py_MOD_GIL_NOT_USED
    {Py_mod_gil, Py_MOD_GIL_NOT_USED},
#endif
    {0, NULL}
};

static PyModuleDef librt_random_module = {
    .m_base = PyModuleDef_HEAD_INIT,
    .m_name = "random",
    .m_doc = "Fast random number generation using ChaCha8",
    .m_size = 0,
    .m_methods = librt_random_module_methods,
    .m_slots = librt_random_module_slots,
};

PyMODINIT_FUNC
PyInit_random(void)
{
    return PyModuleDef_Init(&librt_random_module);
}
