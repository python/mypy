import os
from typing import Tuple, List, Optional, Dict, Callable

from mypy.build import State
from mypy.find_sources import SourceFinder, InvalidSourceList
from mypy.messages import format_type
from mypy.modulefinder import PYTHON_EXTENSIONS
from mypy.nodes import Expression, Node, MypyFile, RefExpr, TypeInfo, MemberExpr
from mypy.server.update import FineGrainedBuildManager
from mypy.traverser import ExtendedTraverserVisitor
from mypy.typeops import tuple_fallback
from mypy.types import (
    get_proper_type, ProperType, Instance, TupleType, TypedDictType,
    FunctionLike, LiteralType
)


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


def expr_span(expr: Expression) -> str:
    """Format expression span as in mypy error messages."""
    return f'{expr.line}:{expr.column + 1}:{expr.end_line}:{expr.end_column}'


def get_instance_fallback(typ: ProperType) -> Optional[Instance]:
    """Returns the Instance fallback for this type if one exists or None."""
    if isinstance(typ, Instance):
        return typ
    elif isinstance(typ, TupleType):
        return tuple_fallback(typ)
    elif isinstance(typ, TypedDictType):
        return typ.fallback
    elif isinstance(typ, FunctionLike):
        return typ.fallback
    elif isinstance(typ, LiteralType):
        return typ.fallback
    return None


def find_module_by_fullname(fullname: str, modules: Dict[str, State]) -> Optional[State]:
    """Find module by a node fullname.

    This logic mimics the one we use in fixup, so should be good enough.
    """
    head = fullname
    while True:
        if '.' not in head:
            return None
        head, tail = head.rsplit('.', maxsplit=1)
        mod = modules.get(head)
        if mod is not None:
            return mod
    return None


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
        verbosity: int = 0,
        limit: int = 0,
        include_span: bool = False,
        include_kind: bool = False,
        include_object_attrs: bool = False,
        force_reload: bool = False,
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
        self.include_object_attrs = include_object_attrs
        self.force_reload = force_reload

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
            return self.missing_type(expression), False

        type_str = format_type(expr_type, verbosity=self.verbosity)
        return self.add_prefixes(type_str, expression), True

    def object_type(self) -> TypeInfo:
        builtins = self.fg_manager.graph['builtins'].tree
        assert builtins is not None
        object_node = builtins.names['object'].node
        assert isinstance(object_node, TypeInfo)
        return object_node

    def expr_attrs(self, expression: Expression) -> Tuple[str, bool]:
        """Format attributes that are valid for a given expression.

        If expression type is not an Instance, try using fallback. Attributes are
        returned as a JSON (ordered by MRO) that maps base class name to list of
        attributes. Attributes may appear in multiple bases if overridden (we simply
        follow usual mypy logic for creating new Vars etc).
        """
        expr_type = self.fg_manager.manager.all_types.get(expression)
        if expr_type is None:
            return self.missing_type(expression), False

        instance = get_instance_fallback(get_proper_type(expr_type))
        if instance is not None:
            mro = instance.type.mro
        else:
            # Everything is an object in Python.
            mro = [self.object_type()]
        if not self.include_object_attrs:
            mro = mro[:-1]

        # We don't use JSON dump to be sure keys order is always preserved.
        base_attrs = []
        for base in mro:
            cls_name = base.name if self.verbosity < 1 else base.fullname
            attrs = [f'"{attr}"' for attr in sorted(base.names)]
            base_attrs.append(f'"{cls_name}": [{", ".join(attrs)}]')
        return self.add_prefixes(f'{{{", ".join(base_attrs)}}}', expression), True

    def expression_def(self, expression: Expression) -> Tuple[str, bool]:
        """Find and format definition location for an expression.

        If it is not a RefExpr, it is effectively skipped by returning an
        empty result.
        """
        if not isinstance(expression, RefExpr):
            # If there are no suitable matches at all, we return error later.
            return '', True

        if expression.node is None:
            if isinstance(expression, MemberExpr) and expression.kind is None:
                # TODO: "non-static" attributes require a lot of special logic,
                # essentially  duplicating those in checkmember.py.
                return "Non-static attributes are not supported yet", False
            return self.missing_node(expression), False

        module = find_module_by_fullname(expression.node.fullname, self.fg_manager.graph)
        # TODO: line/column are not stored in cache for vast majority of symbol nodes.
        if not module.tree or module.tree.is_cache_skeleton or self.force_reload:
            self.reload_module(module)

        symbol = expression.node.name
        line = expression.node.line
        column = expression.node.column
        if not module:
            return self.missing_node(expression), False
        result = f'{module.path}:{line}:{column + 1}:{symbol}'
        return self.add_prefixes(result, expression), True

    def missing_type(self, expression: Expression) -> str:
        alt_suggestion = ''
        if not self.force_reload:
            alt_suggestion = ' or try --force-reload'
        return (f'No known type available for "{type(expression).__name__}"'
                f' (maybe unreachable{alt_suggestion})')

    def missing_node(self, expression: Expression) -> str:
        return (f'Cannot find definition for "{type(expression).__name__}"'
                f' at {expr_span(expression)}')

    def add_prefixes(self, result: str, expression: Expression) -> str:
        prefixes = []
        if self.include_kind:
            prefixes.append(f'{type(expression).__name__}')
        if self.include_span:
            prefixes.append(expr_span(expression))
        if prefixes:
            prefix = ':'.join(prefixes) + ' -> '
        else:
            prefix = ''
        return prefix + result

    def run_inspection_by_exact_location(
        self,
        tree: MypyFile,
        line: int,
        column: int,
        end_line: int,
        end_column: int,
        method: Callable[[Expression], Tuple[str, bool]],
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

        inspection_str, success = method(expression)
        return {'out': inspection_str, 'err': '', 'status': 0 if success else 1}

    def run_inspection_by_position(
        self,
        tree: MypyFile,
        line: int,
        column: int,
        method: Callable[[Expression], Tuple[str, bool]],
    ) -> Dict[str, object]:
        """Get types of all expressions enclosing a position.

        Types and/or errors are returned as a standard daemon response dict.
        """
        expressions = find_all_by_location(tree, line, column - 1)
        if not expressions:
            position = f'{line}:{column}'
            return {'out': f"Can't find any expressions at position {position}",
                    'err': '', 'status': 1}

        inspection_strs = []
        status = 0
        for expression in expressions:
            inspection_str, success = method(expression)
            if not success:
                status = 1
            if inspection_str:
                inspection_strs.append(inspection_str)
        if self.limit:
            inspection_strs = inspection_strs[:self.limit]
        return {'out': '\n'.join(inspection_strs), 'err': '', 'status': status}

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

    def run_inspection(
        self,
        location: str,
        method: Callable[[Expression], Tuple[str, bool]],
    ) -> Dict[str, object]:
        """Top-level logic to inspect expression(s) at a location.

        This can be re-used by various simple inspections.
        """
        try:
            file, pos = self.parse_location(location)
        except ValueError as err:
            return {'error': str(err)}

        state, err_dict = self.find_module(file)
        if state is None:
            assert err_dict
            return err_dict

        # Force reloading to load from cache, account for any edits, etc.
        if not state.tree or state.tree.is_cache_skeleton or self.force_reload:
            self.reload_module(state)
        assert state.tree is not None

        if len(pos) == 4:
            # Full span, return an exact match only.
            line, column, end_line, end_column = pos
            return self.run_inspection_by_exact_location(
                state.tree, line, column, end_line, end_column, method
            )
        assert len(pos) == 2
        # Inexact location, return all expressions.
        line, column = pos
        return self.run_inspection_by_position(state.tree, line, column, method)

    def get_type(self, location: str) -> Dict[str, object]:
        """Get types of expression(s) at a location."""
        return self.run_inspection(location, self.expr_type)

    def get_attrs(self, location: str) -> Dict[str, object]:
        """Get attributes of expression(s) at a location."""
        return self.run_inspection(location, self.expr_attrs)

    def get_definition(self, location: str) -> Dict[str, object]:
        """Get symbol definitions of expression(s) at a location."""
        result = self.run_inspection(location, self.expression_def)
        if 'out' in result and not result['out']:
            # None of the expressions found turns out to be a RefExpr.
            _, location = location.split(':', maxsplit=1)
            result['out'] = f'No name or member expressions at {location}'
            result['status'] = 1
        return result
