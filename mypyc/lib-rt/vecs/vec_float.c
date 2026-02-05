#ifdef MYPYC_EXPERIMENTAL
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
#define FEATURES Vec_FloatAPI

#define BOX_ITEM VecFloat_BoxItem
#define UNBOX_ITEM VecFloat_UnboxItem
#define IS_UNBOX_ERROR VecFloat_IsUnboxError

#include "vec_template.c"

#endif  // MYPYC_EXPERIMENTAL
