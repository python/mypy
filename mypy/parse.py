from __future__ import annotations

import ast
import re

from librt.internal import ReadBuffer

from mypy import errorcodes as codes
from mypy.cache import read_int
from mypy.errors import Errors
from mypy.nodes import (
    FileRawData,
    Import,
    ImportAll,
    ImportBase,
    ImportFrom,
    MypyFile,
    ParseError,
    StrExpr,
)
from mypy.options import Options
from mypy.types import ProperType


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
        # Use import from as workaround for cpython#149728 - accessing mypy.nativeparse
        # after importing it may fail when this function is called concurrently.
        from mypy import nativeparse

        ignore_errors = options.ignore_errors or fnam in errors.ignored_files
        # If errors are ignored, we can drop many function bodies to speed up type checking.
        strip_function_bodies = ignore_errors and not options.preserve_asts
        tree, _, _ = nativeparse.native_parse(
            fnam, options, source, skip_function_bodies=strip_function_bodies
        )
        # Set is_stub based on file extension
        tree.is_stub = fnam.endswith(".pyi")
        # Note: tree.imports is populated directly by load_from_raw() with deserialized
        # import metadata, so we don't need to collect imports via AST traversal
        if eager and tree.raw_data is not None:
            tree = load_from_raw(fnam, module, tree.raw_data, errors, options)
        return tree

    if source is None:
        raise ValueError("Source cannot be `None` when using the old parser")
    if options.transform_source is not None:
        source = options.transform_source(source)
    import mypy.fastparse

    return mypy.fastparse.parse(source, fnam=fnam, module=module, errors=errors, options=options)


def load_from_raw(
    fnam: str,
    module: str | None,
    raw_data: FileRawData,
    errors: Errors,
    options: Options,
    imports_only: bool = False,
) -> MypyFile:
    """Load AST from parsed binary data and report stored errors.

    If imports_only is true, only deserialize imports and return a mostly
    empty AST.
    """
    from mypy.nativeparse import State, deserialize_imports, read_statements

    state = State(options, is_stub=fnam.endswith(".pyi"))
    if imports_only:
        defs = []
    else:
        data = ReadBuffer(raw_data.defs)
        n = read_int(data)
        defs = read_statements(state, data, n)
    imports = deserialize_imports(raw_data.imports)

    tree = MypyFile(defs, imports)
    tree.path = fnam
    tree.ignored_lines = raw_data.ignored_lines
    tree.is_partial_stub_package = raw_data.is_partial_stub_package
    tree.uses_template_strings = raw_data.uses_template_strings
    tree.is_stub = fnam.endswith(".pyi")
    if module is not None:
        tree._fullname = module

    # Report parse errors, this replicates the logic in parse().
    all_errors = raw_data.raw_errors + state.errors
    errors.set_file(fnam, module, options=options)
    errors.set_file_ignored_lines(fnam, tree.ignored_lines, options.ignore_errors)
    for error in all_errors:
        # Note we never raise in this function, so it should not be called in coordinator.
        report_parse_error(error, errors)
    if imports_only:
        # Preserve raw data when only de-serializing imports, it will be sent to
        # the parallel workers.
        tree.raw_data = raw_data
    return tree


class ImportCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.collected: list[ImportBase] = []
        self.in_function = 0

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.in_function += 1
        self.generic_visit(node)
        self.in_function -= 1

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.in_function += 1
        self.generic_visit(node)
        self.in_function -= 1

    def visit_Import(self, node: ast.Import) -> None:
        if self.in_function > 0:
            names = [(alias.name, alias.asname) for alias in node.names]
            self.collected.append(Import(names))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if self.in_function > 0:
            if len(node.names) == 1 and node.names[0].name == "*":
                mod = node.module if node.module is not None else ""
                self.collected.append(ImportAll(mod, node.level))
            else:
                names = [(a.name, a.asname) for a in node.names]
                mod = node.module if node.module is not None else ""
                self.collected.append(ImportFrom(mod, node.level, names))
        self.generic_visit(node)


def _restore_stripped_body_imports(
    fnam: str, source: str | bytes | None, imports: list[ImportBase]
) -> None:
    """Collect imports from inside function bodies when the native parser strips them.

    When ``ignore_errors`` is set, the native parser skips function bodies to
    speed up type checking. This means ``Import`` / ``ImportFrom`` nodes inside
    function bodies never get serialized into ``tree.imports``, and the imported
    modules are never tracked as dependencies. This function scans the source
    with Python's ``ast`` module and adds any imports found inside function
    bodies to the imports list.
    """
    if source is None:
        try:
            with open(fnam, encoding="utf-8") as f:
                source = f.read()
        except OSError:
            return
    try:
        src_tree = ast.parse(source)
    except SyntaxError:
        return

    collector = ImportCollector()
    collector.visit(src_tree)
    imports.extend(collector.collected)


def report_parse_error(error: ParseError, errors: Errors) -> None:
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
    errors.report(error["line"], error["column"], message, blocker=is_blocker, code=error_code)


def parse_type_string(expr: StrExpr, options: Options) -> ProperType:
    if options.native_parser:
        # Use a import from as workaround for cpython#149728 - accessing mypy.nativeparse
        # after importing it may fail when this function is called concurrently.
        from mypy import nativeparse

        return nativeparse.native_parse_type_string(
            expr.value,
            expr.line,
            expr.column,
            expr.end_line or expr.line,
            expr.end_column or expr.column,
            options,
        )
    import mypy.fastparse

    return mypy.fastparse.parse_type_string(expr.value, "builtins.str", expr.line, expr.column)
