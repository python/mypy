#ifndef BYTESWRITER_EXTRA_OPS_H
#define BYTESWRITER_EXTRA_OPS_H

#ifdef MYPYC_EXPERIMENTAL

#include "vecs/librt_vecs.h"

// Check if obj is an instance of vec (any vec type)
static inline int CPyVec_Check(PyObject *obj) {
    return PyObject_TypeCheck(obj, VecApi->get_vec_type());
}

#endif // MYPYC_EXPERIMENTAL

#endif
