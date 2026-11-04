#define VEC VecU32
#define VEC_TYPE VecU32Type
#define VEC_OBJECT VecU32Object
#define BUF_OBJECT VecU32BufObject
#define BUF_TYPE VecU32BufType
#define NAME(suffix) VecU32##suffix
#define FUNC(suffix) VecU32_##suffix
#define ITEM_TYPE_STR "u32"
#define ITEM_TYPE_MAGIC VEC_ITEM_TYPE_U32
#define ITEM_C_TYPE uint32_t
#define FEATURES Vec_U32API

#define BOX_ITEM VecU32_BoxItem
#define UNBOX_ITEM VecU32_UnboxItem
#define IS_UNBOX_ERROR VecU32_IsUnboxError
#define BUFFER_FORMAT_CHAR_OK(c) ((c) == 'I' || ((c) == 'L' && sizeof(unsigned long) == 4))
#define BUFFER_FORMAT "I"

#include "vec_template.c"
