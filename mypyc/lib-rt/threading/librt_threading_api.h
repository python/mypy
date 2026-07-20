#ifndef LIBRT_THREADING_API_H
#define LIBRT_THREADING_API_H

#include "librt_threading.h"

int
import_librt_threading(void);

extern void *LibRTThreading_API[LIBRT_THREADING_API_LEN];

#define LibRTThreading_ABIVersion (*(int (*)(void)) LibRTThreading_API[0])
#define LibRTThreading_APIVersion (*(int (*)(void)) LibRTThreading_API[1])
#define LibRTThreading_Lock_type_internal (*(PyTypeObject* (*)(void)) LibRTThreading_API[2])
#define LibRTThreading_Lock_new_internal (*(PyObject* (*)(void)) LibRTThreading_API[3])
#define LibRTThreading_Lock_acquire_internal (*(char (*)(PyObject *self)) LibRTThreading_API[4])
#define LibRTThreading_Lock_release_internal (*(char (*)(PyObject *self)) LibRTThreading_API[5])
#define LibRTThreading_Lock_locked_internal (*(char (*)(PyObject *self)) LibRTThreading_API[6])
#define LibRTThreading_Lock_acquire_blocking_internal (*(char (*)(PyObject *self, char blocking)) LibRTThreading_API[7])

#endif  // LIBRT_THREADING_API_H
