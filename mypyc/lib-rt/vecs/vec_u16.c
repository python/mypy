#define VEC VecU16
#define VEC_TYPE VecU16Type
#define VEC_OBJECT VecU16Object
#define BUF_OBJECT VecU16BufObject
#define BUF_TYPE VecU16BufType
#define NAME(suffix) VecU16##suffix
#define FUNC(suffix) VecU16_##suffix
#define ITEM_TYPE_STR "u16"
#define ITEM_TYPE_MAGIC VEC_ITEM_TYPE_U16
#define ITEM_C_TYPE uint16_t
#define FEATURES Vec_U16API

#define BOX_ITEM VecU16_BoxItem
#define UNBOX_ITEM VecU16_UnboxItem
#define IS_UNBOX_ERROR VecU16_IsUnboxError
#define BUFFER_FORMAT_CHAR_OK(c) ((c) == 'H')
#define BUFFER_FORMAT "H"

#include "vec_template.c"
