#ifndef _MYPY_H
#define _MYPY_H

#include <stdlib.h>

typedef unsigned long MValue;
typedef long MSignedValue;
typedef int MBool;

typedef struct {
    MValue *frame;
    MValue *stack_top;
} MEnv;

#define MNone  0x1L
#define MError 0x3L

#define MIsShort(v) (((v) & 1) == 0)

MBool MIntLt(MValue left, MValue right);
MBool MIntLe(MValue left, MValue right);
MValue MIntAdd(MEnv *e, MValue x, MValue y);
MValue MIntSub(MEnv *e, MValue x, MValue y);

/* TODO this is just a trivial dummy print placeholder for test cases */
MValue Mprint(MEnv *e);

static inline MBool MIsAddOverflow(MValue sum, MValue left, MValue right) {
    return ((MSignedValue)(sum ^ left) < 0 &&
            (MSignedValue)(sum ^ right) < 0);
}

static inline MBool MIsSubOverflow(MValue diff, MValue left, MValue right) {
    return ((MSignedValue)(diff ^ left) < 0 && 
            (MSignedValue)(diff ^ right) >= 0);
}

static inline MBool MShortLt(MValue left, MValue right) {
    if (MIsShort(left) && MIsShort(right))
        return (MSignedValue)left < (MSignedValue)right;
    else
        return MIntLt(left, right);
}

static inline MBool MShortLe(MValue left, MValue right) {
    if (MIsShort(left) && MIsShort(right))
        return (MSignedValue)left <= (MSignedValue)right;
    else
        return MIntLe(left, right);
}

#endif
