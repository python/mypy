#ifndef LIBRT_TIME_API_H
#define LIBRT_TIME_API_H

int
import_librt_time(void);

#ifdef MYPYC_EXPERIMENTAL

#include <Python.h>

#define LIBRT_TIME_ABI_VERSION 1
#define LIBRT_TIME_API_VERSION 1
#define LIBRT_TIME_API_LEN 3

extern void *LibRTTime_API[LIBRT_TIME_API_LEN];

#define LibRTTime_ABIVersion (*(int (*)(void)) LibRTTime_API[0])
#define LibRTTime_APIVersion (*(int (*)(void)) LibRTTime_API[1])
#define LibRTTime_time (*(double (*)(void)) LibRTTime_API[2])

#endif  // MYPYC_EXPERIMENTAL

#endif  // LIBRT_TIME_API_H
