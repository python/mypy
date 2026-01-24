from __future__ import annotations

import os
import re

from mypy import errorcodes as codes
from mypy.errors import Errors
from mypy.nodes import Import, ImportAll, ImportBase, ImportFrom, MypyFile
from mypy.options import Options
from mypy.traverser import TraverserVisitor


class ImportCollector(TraverserVisitor):
    """Visitor that collects all import nodes from an AST."""

    def __init__(self) -> None:
        self.imports: list[ImportBase] = []

    def visit_import(self, node: Import) -> None:
        self.imports.append(node)
        super().visit_import(node)

    def visit_import_from(self, node: ImportFrom) -> None:
        self.imports.append(node)
        super().visit_import_from(node)

    def visit_import_all(self, node: ImportAll) -> None:
        self.imports.append(node)
        super().visit_import_all(node)


def parse(
    source: str | bytes,
    fnam: str,
    module: str | None,
    errors: Errors,
    options: Options,
    raise_on_error: bool = False,
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
                fnam, skip_function_bodies=strip_function_bodies
            )
            # Convert type ignores list to dict
            tree.ignored_lines = dict(type_ignores)
            # Set is_stub based on file extension
            tree.is_stub = fnam.endswith(".pyi")
            # Collect all import nodes from the tree
            collector = ImportCollector()
            tree.accept(collector)
            tree.imports = collector.imports
            # Report parse errors
            for error in parse_errors:
                message = error["message"]
                # Standardize error message by capitalizing the first word
                message = re.sub(r"^(\s*\w)", lambda m: m.group(1).upper(), message)
                errors.report(
                    error["line"], error["column"], message, blocker=True, code=codes.SYNTAX
                )
            if raise_on_error and errors.is_errors():
                errors.raise_error()
            return tree
        # Fall through to fastparse for non-existent files

    if options.transform_source is not None:
        source = options.transform_source(source)
    import mypy.fastparse

    tree = mypy.fastparse.parse(source, fnam=fnam, module=module, errors=errors, options=options)
    if raise_on_error and errors.is_errors():
        errors.raise_error()
    return tree
