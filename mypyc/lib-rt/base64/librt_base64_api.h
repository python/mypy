#ifndef LIBRT_BASE64_API_H
#define LIBRT_BASE64_API_H

#include "librt_base64.h"

#ifdef MYPYC_STATIC_LINKING
// librt is statically linked, so the API functions (declared in librt_base64.h) are
// called directly, and type objects are referred to directly
#else
extern void *LibRTBase64_API[LIBRT_BASE64_API_LEN];

#define LibRTBase64_ABIVersion (*(int (*)(void)) LibRTBase64_API[0])
#define LibRTBase64_APIVersion (*(int (*)(void)) LibRTBase64_API[1])
#define LibRTBase64_b64encode_internal (*(PyObject* (*)(PyObject *source, bool urlsafe)) LibRTBase64_API[2])
#define LibRTBase64_b64decode_internal (*(PyObject* (*)(PyObject *source, bool urlsafe)) LibRTBase64_API[3])
#endif

int import_librt_base64(void);

#endif  // LIBRT_BASE64_API_H
