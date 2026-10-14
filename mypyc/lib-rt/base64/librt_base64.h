#ifndef LIBRT_BASE64_H
#define LIBRT_BASE64_H

#include <Python.h>

#define LIBRT_BASE64_ABI_VERSION 1
#define LIBRT_BASE64_API_VERSION 2
#define LIBRT_BASE64_API_LEN 4

#ifdef MYPYC_STATIC_LINKING
// With static linking, the API is used directly (see librt_base64_api.h)
#include <stdbool.h>
#include <stdint.h>
int LibRTBase64_ABIVersion(void);
int LibRTBase64_APIVersion(void);
PyObject *LibRTBase64_b64encode_internal(PyObject *obj, bool urlsafe);
PyObject *LibRTBase64_b64decode_internal(PyObject *arg, bool urlsafe);
#endif

#endif  // LIBRT_BASE64_H
