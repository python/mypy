#define VEC VecI64
#define VEC_TYPE VecI64Type
#define VEC_OBJECT VecI64Object
#define BUF_OBJECT VecI64BufObject
#define BUF_TYPE VecI64BufType
#define NAME(suffix) VecI64##suffix
#define FUNC(suffix) VecI64_##suffix
#define ITEM_TYPE_STR "i64"
#define ITEM_C_TYPE int64_t
#define FEATURES I64Features

#define BOX_ITEM(x) PyLong_FromLongLong(x)
#define UNBOX_ITEM(x) PyLong_AsLongLong(x)
#define IS_UNBOX_ERROR(x) ((x) == -1 && PyErr_Occurred())

#include "vec_template.c"
