from typing import List, Tuple, Set, cast, Union, Optional

from mypy.errors import Errors
from mypy.nodes import MypyFile

# Can't use TYPE_CHECKING because it's not in the Python 3.5.1 stdlib
MYPY = False
if MYPY:
    from mypy.options import Options


def parse(source: Union[str, bytes],
          fnam: str,
          errors: Optional[Errors],
          options: 'Options') -> MypyFile:
    """Parse a source file, without doing any semantic analysis.

    Return the parse tree. If errors is not provided, raise ParseError
    on failure. Otherwise, use the errors object to report parse errors.

    The python_version (major, minor) option determines the Python syntax variant.
    """
    is_stub_file = bool(fnam) and fnam.endswith('.pyi')
    if options.python_version[0] >= 3 or is_stub_file:
        import mypy.fastparse
        return mypy.fastparse.parse(source,
                                    fnam=fnam,
                                    errors=errors,
                                    pyversion=options.python_version,
                                    custom_typing_module=options.custom_typing_module)
    else:
        import mypy.fastparse2
        return mypy.fastparse2.parse(source,
                                     fnam=fnam,
                                     errors=errors,
                                     pyversion=options.python_version,
                                     custom_typing_module=options.custom_typing_module)
