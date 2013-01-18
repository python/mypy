#ifndef _MYPY_H
#define _MYPY_H

typedef long MValue;

typedef struct {
    MValue *frame;
} MEnv;

#define MNone 0x1L

#endif
