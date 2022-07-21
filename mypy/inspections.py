import os
from typing import Tuple, List, Optional, Dict

from mypy.build import State
from mypy.find_sources import SourceFinder, InvalidSourceList
from mypy.messages import format_type
from mypy.modulefinder import PYTHON_EXTENSIONS
from mypy.nodes import Expression, Node, MypyFile
from mypy.server.update import FineGrainedBuildManager
from mypy.traverser import ExtendedTraverserVisitor


def node_starts_after(o: Node, line: int, column: int) -> bool:
    return o.line > line or o.line == line and o.column > column


def node_ends_before(o: Node, line: int, column: int) -> bool:
    # Unfortunately, end positions for some statements are a mess,
    # e.g. overloaded functions, so we return False when we don't know.
    if o.end_line is not None and o.end_column is not None:
        if (o.end_line < line
                or o.end_line == line and o.end_column < column):
            return True
    return False


class SearchVisitor(ExtendedTraverserVisitor):
    """Visitor looking for an expression whose span matches given one exactly."""

    def __init__(
        self,
        line: int,
        column: int,
        end_line: int,
        end_column: int
    ) -> None:
        self.line = line
        self.column = column
        self.end_line = end_line
        self.end_column = end_column
        self.result: Optional[Expression] = None

    def visit(self, o: Node) -> bool:
        if node_starts_after(o, self.line, self.column):
            return False
        if node_ends_before(o, self.end_line, self.end_column):
            return False
        if (
            o.line == self.line
            and o.end_line == self.end_line
            and o.column == self.column
            and o.end_column == self.end_column
        ):
            if isinstance(o, Expression):
                self.result = o
        return self.result is None


def find_by_location(
    tree: MypyFile,
    line: int,
    column: int,
    end_line: int,
    end_column: int
) -> Optional[Expression]:
    """Find an expression matching given span, or None if not found."""
    if end_line < line:
        raise ValueError('"end_line" must not be before "line"')
    if end_line == line and end_column <= column:
        raise ValueError('"end_column" must be after "column"')
    visitor = SearchVisitor(line, column, end_line, end_column)
    tree.accept(visitor)
    return visitor.result


class SearchAllVisitor(ExtendedTraverserVisitor):
    """Visitor looking for all expressions whose spans enclose given position."""

    def __init__(
        self,
        line: int,
        column: int
    ) -> None:
        self.line = line
        self.column = column
        self.result: List[Expression] = []

    def visit(self, o: Node) -> bool:
        if node_starts_after(o, self.line, self.column):
            return False
        if node_ends_before(o, self.line, self.column):
            return False
        if isinstance(o, Expression):
            self.result.append(o)
        return True


def find_all_by_location(
    tree: MypyFile,
    line: int,
    column: int,
) -> List[Expression]:
    """Find all expressions enclosing given position starting from innermost."""
    visitor = SearchAllVisitor(line, column)
    tree.accept(visitor)
    return list(reversed(visitor.result))


class InspectionEngine:
    """Engine for locating and statically inspecting expressions."""

    def __init__(
        self,
        fg_manager: FineGrainedBuildManager,
        *,
        verbosity: Optional[int] = 0,
        limit: int = 0,
        include_span: bool = False,
        include_kind: bool = False,
    ) -> None:
        self.fg_manager = fg_manager
        self.finder = SourceFinder(
            self.fg_manager.manager.fscache,
            self.fg_manager.manager.options
        )
        self.verbosity = verbosity
        self.limit = limit
        self.include_span = include_span
        self.include_kind = include_kind

    def parse_location(self, location: str) -> Tuple[str, List[int]]:
        if location.count(':') not in [2, 4]:
            raise ValueError("Format should be file:line:column[:end_line:end_column]")
        parts = location.split(":")
        module, *rest = parts
        return module, [int(p) for p in rest]

    def reload_module(self, state: State) -> None:
        """Reload given module while temporary exporting types."""
        old = self.fg_manager.manager.options.export_types
        self.fg_manager.manager.options.export_types = True
        try:
            self.fg_manager.flush_cache()
            assert state.path is not None
            self.fg_manager.update([(state.id, state.path)], [])
        finally:
            self.fg_manager.manager.options.export_types = old

    def expr_type(self, expression: Expression) -> Tuple[str, bool]:
        """Format type for an expression using current options.

        If type is known, second item returned is True. If type is not known, an error
        message is returned instead, and second item returned is False.
        """
        expr_type = self.fg_manager.manager.all_types.get(expression)
        if expr_type is None:
            return (f'No known type available for "{type(expression).__name__}"'
                    f' (probably unreachable)', False)

        type_str = format_type(expr_type, verbosity=self.verbosity or 0)
        if self.include_span:
            type_str = f'{expression.end_line}:{expression.end_column}:{type_str}'
            type_str = f'{expression.line}:{expression.column + 1}:{type_str}'
        if self.include_kind:
            type_str = f'{type(expression).__name__}:{type_str}'
        return type_str, True

    def get_type_by_exact_location(
        self, tree: MypyFile, line: int, column: int, end_line: int, end_column: int
    ) -> Dict[str, object]:
        """Get type of an expression matching a span.

        Type or error is returned as a standard daemon response dict.
        """
        try:
            expression = find_by_location(tree, line, column - 1, end_line, end_column)
        except ValueError as err:
            return {'error': str(err)}

        if expression is None:
            span = f'{line}:{column}:{end_line}:{end_column}'
            return {'out': f"Can't find expression at span {span}", 'err': '', 'status': 1}

        type_str, found = self.expr_type(expression)
        return {'out': type_str, 'err': '', 'status': 0 if found else 1}

    def get_types_by_position(self, tree: MypyFile, line: int, column: int) -> Dict[str, object]:
        """Get types of all expressions enclosing a position.

        Types and/or errors are returned as a standard daemon response dict.
        """
        expressions = find_all_by_location(tree, line, column - 1)
        if not expressions:
            position = f'{line}:{column}'
            return {'out': f"Can't find any expressions at position {position}",
                    'err': '', 'status': 1}

        type_strs = []
        status = 0
        for expression in expressions:
            type_str, found = self.expr_type(expression)
            if not found:
                status = 1
            type_strs.append(type_str)
        if self.limit:
            type_strs = type_strs[:self.limit]
        return {'out': '\n'.join(type_strs), 'err': '', 'status': status}

    def find_module(self, file: str) -> Tuple[Optional[State], Dict[str, object]]:
        """Find module by path, or return a suitable error message.

        Note we don't use exceptions to simplify handling 1 vs 2 statuses.
        """
        if not any(file.endswith(ext) for ext in PYTHON_EXTENSIONS):
            return None, {'error': 'Source file is not a Python file'}

        try:
            module, _ = self.finder.crawl_up(os.path.normpath(file))
        except InvalidSourceList:
            return None, {'error': 'Invalid source file name: ' + file}

        state = self.fg_manager.graph.get(module)
        return (
            state,
            {'out': f'Unknown module: {module}', 'err': '', 'status': 1}
            if state is None else {}
        )

    def get_type(self, location: str) -> Dict[str, object]:
        """Top-level logic to get type of expression(s) at a location."""
        try:
            file, pos = self.parse_location(location)
        except ValueError as err:
            return {'error': str(err)}

        state, err_dict = self.find_module(file)
        if state is None:
            assert err_dict
            return err_dict

        # Force reloading to load from cache, account for any edits, etc.
        self.reload_module(state)
        assert state.tree is not None

        if len(pos) == 4:
            # Full span, return an exact match only.
            line, column, end_line, end_column = pos
            return self.get_type_by_exact_location(
                state.tree, line, column, end_line, end_column
            )
        assert len(pos) == 2
        # Inexact location, return all expressions.
        line, column = pos
        return self.get_types_by_position(state.tree, line, column)
