#ifndef LIBRT_RANDOM_H
#define LIBRT_RANDOM_H

#include <Python.h>

#define LIBRT_RANDOM_ABI_VERSION 1
#define LIBRT_RANDOM_API_VERSION 9
#define LIBRT_RANDOM_API_LEN 13

#ifdef MYPYC_STATIC_LINKING
// With static linking, the API is used directly (see librt_random_api.h)
#include <stdbool.h>
#include <stdint.h>
extern PyTypeObject LibRTRandom_RandomType;
int LibRTRandom_ABIVersion(void);
int LibRTRandom_APIVersion(void);
PyObject *LibRTRandom_Random_internal(void);
PyObject *LibRTRandom_Random_from_seed_internal(int64_t seed_val);
PyTypeObject *LibRTRandom_Random_type_internal(void);
double LibRTRandom_Random_random_internal(PyObject *self);
int64_t LibRTRandom_Random_randint_internal(PyObject *self, int64_t a, int64_t b);
int64_t LibRTRandom_Random_randrange1_internal(PyObject *self, int64_t stop);
int64_t LibRTRandom_Random_randrange2_internal(PyObject *self, int64_t start, int64_t stop);
double LibRTRandom_module_random_internal(void);
int64_t LibRTRandom_module_randint_internal(int64_t a, int64_t b);
int64_t LibRTRandom_module_randrange1_internal(int64_t stop);
int64_t LibRTRandom_module_randrange2_internal(int64_t start, int64_t stop);
#endif

#endif  // LIBRT_RANDOM_H
