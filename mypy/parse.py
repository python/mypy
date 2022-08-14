from __future__ import annotations

from typing import Optional, Union

from mypy.errors import Errors
from mypy.nodes import MypyFile
from mypy.options import Options


def parse(
    source: Union[str, bytes],
    fnam: str,
    module: Optional[str],
    errors: Optional[Errors],
    options: Options,
) -> MypyFile:
    """Parse a source file, without doing any semantic analysis.

    Return the parse tree. If errors is not provided, raise ParseError
    on failure. Otherwise, use the errors object to report parse errors.

    The python_version (major, minor) option determines the Python syntax variant.
    """
    if options.transform_source is not None:
        source = options.transform_source(source)
    import mypy.fastparse

    return mypy.fastparse.parse(source, fnam=fnam, module=module, errors=errors, options=options)
