from typing import Dict, Any

from typing_extensions import Final

PREFIX = 'CPyPy_'  # type: Final # Python wrappers
NATIVE_PREFIX = 'CPyDef_'  # type: Final # Native functions etc.
DUNDER_PREFIX = 'CPyDunder_'  # type: Final # Wrappers for exposing dunder methods to the API
REG_PREFIX = 'cpy_r_'  # type: Final # Registers
STATIC_PREFIX = 'CPyStatic_'  # type: Final # Static variables (for literals etc.)
TYPE_PREFIX = 'CPyType_'  # type: Final # Type object struct
MODULE_PREFIX = 'CPyModule_'  # type: Final # Cached modules
ATTR_PREFIX = '_'  # type: Final # Attributes

ENV_ATTR_NAME = '__mypyc_env__'  # type: Final
NEXT_LABEL_ATTR_NAME = '__mypyc_next_label__'  # type: Final
TEMP_ATTR_NAME = '__mypyc_temp__'  # type: Final
LAMBDA_NAME = '__mypyc_lambda__'  # type: Final
PROPSET_PREFIX = '__mypyc_setter__'  # type: Final
SELF_NAME = '__mypyc_self__'  # type: Final
INT_PREFIX = '__tmp_literal_int_'  # type: Final

# Max short int we accept as a literal is based on 32-bit platforms,
# so that we can just always emit the same code.
MAX_LITERAL_SHORT_INT = (1 << 30) - 1  # type: Final

TOP_LEVEL_NAME = '__top_level__'  # type: Final # Special function representing module top level

# Maximal number of subclasses for a class to trigger fast path in isinstance() checks.
FAST_ISINSTANCE_MAX_SUBCLASSES = 2  # type: Final


def decorator_helper_name(func_name: str) -> str:
    return '__mypyc_{}_decorator_helper__'.format(func_name)


def shared_lib_name(group_name: str) -> str:
    """Given a group name, return the actual name of its extension module.

    (This just adds a suffix to the final component.)
    """
    return '{}__mypyc'.format(group_name)


def short_name(name: str) -> str:
    if name.startswith('builtins.'):
        return name[9:]
    return name


JsonDict = Dict[str, Any]
