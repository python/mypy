#ifndef LIBRT_TIME_H
#define LIBRT_TIME_H

#include <Python.h>

#define LIBRT_TIME_ABI_VERSION 1
#define LIBRT_TIME_API_VERSION 1
#define LIBRT_TIME_API_LEN 3

#ifdef MYPYC_STATIC_LINKING
// With static linking, the API is used directly (see librt_time_api.h)
#include <stdbool.h>
#include <stdint.h>
int LibRTTime_ABIVersion(void);
int LibRTTime_APIVersion(void);
double LibRTTime_time(void);
#endif

#endif  // LIBRT_TIME_H
