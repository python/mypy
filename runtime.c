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


MValue Mprint(MEnv *e)
{
    /* TODO implement properly */
    /* TODO don't use blindly assume that the argument is a short int */
    printf("%ld\n", e->frame[0] >> 1);
    return 0;
}
