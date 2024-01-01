#define VEC VecFloat
#define VEC_TYPE VecFloatType
#define VEC_OBJECT VecFloatObject
#define BUF_OBJECT VecFloatBufObject
#define BUF_TYPE VecFloatBufType
#define NAME(suffix) VecFloat##suffix
#define FUNC(suffix) VecFloat_##suffix
#define ITEM_TYPE_STR "float"
#define ITEM_TYPE_MAGIC VEC_ITEM_TYPE_FLOAT
#define ITEM_C_TYPE double
#define FEATURES FloatFeatures

#define BOX_ITEM(x) PyFloat_FromDouble(x)
#define UNBOX_ITEM(x) PyFloat_AsDouble(x)
#define IS_UNBOX_ERROR(x) ((x) == -1.0 && PyErr_Occurred())

#include "vec_template.c"
