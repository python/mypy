from typing import Dict, Optional, Callable

# The docstring_parser hook is called for each function that has a docstring
# and no other type annotations applied, and the callable should accept the
# docstring as an argument and return a mapping of argument name to type.
#
# The function's return type, if specified, is stored in the mapping with the
# special key 'return'.  Other than 'return', the keys of the mapping must be
# a subset of the arguments of the function to which the docstring belongs; an
# error will be raised if the mapping contains stray arguments.
#
# The values of the mapping must be valid PEP484-compatible strings.
docstring_parser = None  # type: Callable[[str], Optional[Dict[str, str]]]
