PREFIX = 'CPyPy_'  # Python wrappers
NATIVE_PREFIX = 'CPyDef_'  # Native functions etc.
DUNDER_PREFIX = 'CPyDunder_'  # Wrappers for exposing dunder methods to the API
REG_PREFIX = 'cpy_r_'  # Registers
STATIC_PREFIX = 'CPyStatic_'  # Static variables (for literals etc.)
TYPE_PREFIX = 'CPyType_'  # Type object struct

ENV_ATTR_NAME = '__mypyc_env__'
NEXT_LABEL_ATTR_NAME = '__mypyc_next_label__'
TEMP_ATTR_NAME = '__mypyc_temp__'
LAMBDA_NAME = '__mypyc_lambda__'

MAX_SHORT_INT = (1 << 62) - 1

TOP_LEVEL_NAME = '__top_level__'  # Special function representing module top level


def decorator_helper_name(func_name: str) -> str:
    return '__mypyc_{}_decorator_helper__'.format(func_name)
