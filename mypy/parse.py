from __future__ import annotations

import os
import re

from librt.internal import ReadBuffer

from mypy import errorcodes as codes
from mypy.cache import read_int
from mypy.errors import Errors
from mypy.nativeparse import State, deserialize_imports, read_statements
from mypy.nodes import FileRawData, MypyFile
from mypy.options import Options


def parse(
    source: str | bytes,
    fnam: str,
    module: str | None,
    errors: Errors,
    options: Options,
    raise_on_error: bool = False,
    imports_only: bool = False,
) -> MypyFile:
    """Parse a source file, without doing any semantic analysis.

    Return the parse tree. If errors is not provided, raise ParseError
    on failure. Otherwise, use the errors object to report parse errors.

    The python_version (major, minor) option determines the Python syntax variant.
    """
    if options.native_parser:
        # Native parser only works with actual files on disk
        # Fall back to fastparse for in-memory source or non-existent files
        if os.path.exists(fnam):
            import mypy.nativeparse

            ignore_errors = options.ignore_errors or fnam in errors.ignored_files
            # If errors are ignored, we can drop many function bodies to speed up type checking.
            strip_function_bodies = ignore_errors and not options.preserve_asts

            errors.set_file(fnam, module, options=options)
            tree, parse_errors, type_ignores = mypy.nativeparse.native_parse(
                fnam,
                options,
                skip_function_bodies=strip_function_bodies,
                imports_only=imports_only,
            )
            # Convert type ignores list to dict
            tree.ignored_lines = dict(type_ignores)
            # Set is_stub based on file extension
            tree.is_stub = fnam.endswith(".pyi")
            # Note: tree.imports is populated directly by native_parse with deserialized
            # import metadata, so we don't need to collect imports via AST traversal

            # Report parse errors
            for error in parse_errors:
                message = error["message"]
                # Standardize error message by capitalizing the first word
                message = re.sub(r"^(\s*\w)", lambda m: m.group(1).upper(), message)
                # Respect blocker status from error, default to True for syntax errors
                is_blocker = error.get("blocker", True)
                error_code = error.get("code")
                if error_code is None:
                    error_code = codes.SYNTAX
                else:
                    # Fallback to [syntax] for backwards compatibility.
                    error_code = codes.error_codes.get(error_code) or codes.SYNTAX
                errors.report(
                    error["line"], error["column"], message, blocker=is_blocker, code=error_code
                )
            if raise_on_error and errors.is_errors():
                errors.raise_error()
            return tree
        # Fall through to fastparse for non-existent files

    assert not imports_only
    if options.transform_source is not None:
        source = options.transform_source(source)
    import mypy.fastparse

    tree = mypy.fastparse.parse(source, fnam=fnam, module=module, errors=errors, options=options)
    if raise_on_error and errors.is_errors():
        errors.raise_error()
    return tree


def load_from_raw(
    fnam: str, module: str | None, raw_data: FileRawData, errors: Errors, options: Options
) -> MypyFile:
    """Load AST from parsed binary data.

    This essentially replicates parse() above but expects FileRawData instead of actually
    parsing the source code in the file.
    """
    # This part mimics the logic in native_parse().
    data = ReadBuffer(raw_data.defs)
    n = read_int(data)
    state = State(options)
    defs = read_statements(state, data, n)
    imports = deserialize_imports(raw_data.imports)

    tree = MypyFile(defs, imports)
    tree.path = fnam
    tree.ignored_lines = raw_data.ignored_lines
    tree.is_partial_stub_package = raw_data.is_partial_stub_package
    tree.is_stub = fnam.endswith(".pyi")

    # Report parse errors, this replicates the logic in parse().
    all_errors = raw_data.raw_errors + state.errors
    errors.set_file(fnam, module, options=options)
    for error in all_errors:
        message = error["message"]
        message = re.sub(r"^(\s*\w)", lambda m: m.group(1).upper(), message)
        is_blocker = error.get("blocker", True)
        error_code = error.get("code")
        if error_code is None:
            error_code = codes.SYNTAX
        else:
            error_code = codes.error_codes.get(error_code) or codes.SYNTAX
        # Note we never raise in this function, so it should not be called in coordinator.
        errors.report(error["line"], error["column"], message, blocker=is_blocker, code=error_code)
    return tree
