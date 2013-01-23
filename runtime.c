#include <stdio.h>
#include "mypy.h"


MBool MIntLt(MValue left, MValue right)
{
    abort();
}


MBool MIntLe(MValue left, MValue right)
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


MValue MIntUnaryMinus(MEnv *e, MValue x)
{
    abort();
}


MValue Mprint(MEnv *e)
{
    /* TODO implement properly */
    /* TODO don't use blindly assume that the argument is a short int */
    /* Integer division truncates in C99 (but not necessarily in C89). */
    printf("%ld\n", (MSignedValue)e->frame[0] / 2);
    return 0;
}
