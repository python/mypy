#define VEC VecU64
#define VEC_TYPE VecU64Type
#define VEC_OBJECT VecU64Object
#define BUF_OBJECT VecU64BufObject
#define BUF_TYPE VecU64BufType
#define NAME(suffix) VecU64##suffix
#define FUNC(suffix) VecU64_##suffix
#define ITEM_TYPE_STR "u64"
#define ITEM_TYPE_MAGIC VEC_ITEM_TYPE_U64
#define ITEM_C_TYPE uint64_t
#define FEATURES Vec_U64API

#define BOX_ITEM VecU64_BoxItem
#define UNBOX_ITEM VecU64_UnboxItem
#define IS_UNBOX_ERROR VecU64_IsUnboxError
#define BUFFER_FORMAT_CHAR_OK(c) ((c) == 'Q' || ((c) == 'L' && sizeof(unsigned long) == 8))
#define BUFFER_FORMAT "Q"

#include "vec_template.c"
