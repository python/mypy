from mypyc.ops import object_rprimitive, str_rprimitive, ERR_MAGIC
from mypyc.ops_primitive import func_op, binary_op, simple_emit


func_op(name='builtins.str',
        arg_types=[object_rprimitive],
        result_type=str_rprimitive,
        error_kind=ERR_MAGIC,
        emit=simple_emit('{dest} = PyObject_Str({args[0]});'))


binary_op(op='+',
          arg_types=[str_rprimitive, str_rprimitive],
          result_type=str_rprimitive,
          error_kind=ERR_MAGIC,
          format_str='{dest} = {args[0]} + {args[1]} :: str',
          emit=simple_emit('{dest} = PyUnicode_Concat({args[0]}, {args[1]});'))
