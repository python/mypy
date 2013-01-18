#ifndef _MYPY_H
#define _MYPY_H

#include <stdlib.h>

typedef unsigned long MValue;
typedef long MSignedValue;

typedef struct {
    MValue *frame;
} MEnv;

#define MNone 0x1L

#define MIsShort(v) (((v) & 1) == 0)

static inline int MIsAddOverflow(MValue sum, MValue left, MValue right) {
    return ((MSignedValue)(sum ^ left) < 0 &&
            (MSignedValue)(sum ^ right) < 0);
}

static inline int MIsSubOverflow(MValue diff, MValue left, MValue right) {
    return ((MSignedValue)(diff ^ left) < 0 && 
            (MSignedValue)(diff ^ right) >= 0);
}

static inline int MIntLt(MValue left, MValue right) {
    if (MIsShort(left) && MIsShort(right))
        return (MSignedValue)left < (MSignedValue)right;
    else
        abort();
}

#endif
