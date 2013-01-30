#include <stdio.h>
#include "mypy.h"


MValue MAbort(MEnv *e)
{
    abort();
}


MBool MIntEq(MValue left, MValue right)
{
    abort();
}


MBool MIntNe(MValue left, MValue right)
{
    abort();
}


MBool MIntLt(MValue left, MValue right)
{
    abort();
}


MBool MIntLe(MValue left, MValue right)
{
    abort();
}


MBool MIntGt(MValue left, MValue right)
{
    abort();
}


MBool MIntGe(MValue left, MValue right)
{
    abort();
}


MValue MIntAdd(MEnv *e, MValue x, MValue y)
{
    abort();
}


MValue MIntSub(MEnv *e, MValue x, MValue y)
{
    abort();
}


MValue MIntMul(MEnv *e, MValue x, MValue y)
{
    /* TODO handle at least multiplications that fit within a short int */
    abort();
}


MValue MIntFloorDiv(MEnv *e, MValue x, MValue y)
{
    /* TODO handle at least divisions that fit within a short int */
    abort();
}


MValue MIntMod(MEnv *e, MValue x, MValue y)
{
    /* TODO handle at least mod operations that fit within a short int */
    abort();
}


MValue MIntUnaryMinus(MEnv *e, MValue x)
{
    abort();
}


MValue MIntAnd(MEnv *e, MValue x, MValue y)
{
    abort();
}


MValue MIntOr(MEnv *e, MValue x, MValue y)
{
    abort();
}


MValue MIntXor(MEnv *e, MValue x, MValue y)
{
    abort();
}


MValue MIntShl(MEnv *e, MValue x, MValue y)
{
    abort();
}


MValue MIntShr(MEnv *e, MValue x, MValue y)
{
    abort();
}


MValue MIntInvert(MEnv *e, MValue v)
{
    abort();
}


MValue Mprint(MEnv *e)
{
    /* TODO implement properly */
    /* TODO don't use blindly assume that the argument is a short int */
    /* Integer division truncates in C99 (but not necessarily in C89). */
    MSignedValue arg = e->frame[0];
    if (!MIsShort(arg)) {
        if (arg == MNone)
            printf("None\n");
        else {
            MInstanceHeader *h = MHeader(arg);
            printf("<%s object>\n", h->type->full_name);
        }
    } else
        printf("%ld\n", arg / 2);
    return 0;
}



MValue Mobject___init__(MEnv *e)
{
    return MNone;
}
