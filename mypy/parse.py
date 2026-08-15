from __future__ import annotations

import re

from librt.internal import ReadBuffer

from mypy import errorcodes as codes
from mypy.cache import read_int
from mypy.errors import Errors
from mypy.nodes import FileRawData, MypyFile, ParseError
from mypy.options import Options


def parse(
    source: str | bytes | None,
    fnam: str,
    module: str | None,
    errors: Errors,
    options: Options,
    eager: bool = False,
) -> MypyFile:
    """Parse a source file, without doing any semantic analysis.

    Return the parse tree, use the errors object to report parse errors.
    The python_version (major, minor) option determines the Python syntax variant.

    New parser returns empty tree with serialized data. To get the full tree and
    the parse errors, use eager=True.

    `source` must not be `None` if the old parser is used. The new parser will read and
    parse contents from path `fnam` if `source` is `None`.
    """
    if options.native_parser:
        try:
            import mypy.nativeparse
            ignore_errors = options.ignore_errors or fnam in errors.ignored_files
            strip_function_bodies = ignore_errors and not options.preserve_asts
            tree, _, _ = mypy.nativeparse.native_parse(
                fnam, options, source, skip_function_bodies=strip_function_bodies
            )
            tree.is_stub = fnam.endswith(".pyi")
            if eager and tree.raw_data is not None:
                tree = load_from_raw(fnam, module, tree.raw_data, errors, options)
            return tree
        except (ImportError, AttributeError):
            pass

    if source is None:
        raise ValueError("Source cannot be `None` when using the old parser")
    if options.transform_source is not None:
        source = options.transform_source(source)
    import mypy.fastparse

    return mypy.fastparse.parse(source, fnam=fnam, module=module, errors=errors, options=options)


def load_from_raw(
    fnam: str,
    module: str | None,
    raw_data: bytes,
    errors: Errors,
    options: Options,
) -> MypyFile:
    read_buf = ReadBuffer(raw_data)
    errors.set_file(fnam)
    version = read_int(read_buf)
    if version != 1:
        raise ParseError(f"Unsupported AST binary version: {version}")
    errors.has_blockers()
    errors.raise_if_new()
    import mypy.fastparse

    return mypy.fastparse.parse_from_raw(
        read_buf, fnam=fnam, module=module, errors=errors, options=options
    )
