#define VEC VecI8
#define VEC_TYPE VecI8Type
#define VEC_OBJECT VecI8Object
#define BUF_OBJECT VecI8BufObject
#define BUF_TYPE VecI8BufType
#define NAME(suffix) VecI8##suffix
#define FUNC(suffix) VecI8_##suffix
#define ITEM_TYPE_STR "i8"
#define ITEM_TYPE_MAGIC VEC_ITEM_TYPE_I8
#define ITEM_C_TYPE int8_t
#define FEATURES Vec_I8API

#define BOX_ITEM VecI8_BoxItem
#define UNBOX_ITEM VecI8_UnboxItem
#define IS_UNBOX_ERROR VecI8_IsUnboxError
#define BUFFER_FORMAT_CHAR_OK(c) ((c) == 'b')
#define BUFFER_FORMAT "b"

#include "vec_template.c"
