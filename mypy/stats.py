"""Utilities for calculating and reporting statistics about types."""

import cgi
import os.path
import re

from typing import Any, Dict, List, cast, Tuple

from mypy.traverser import TraverserVisitor
from mypy.types import (
    Type, AnyType, Instance, FunctionLike, TupleType, Void, TypeVarType,
    TypeQuery, ANY_TYPE_STRATEGY, CallableType
)
from mypy import nodes
from mypy.nodes import (
    Node, FuncDef, TypeApplication, AssignmentStmt, NameExpr, CallExpr,
    MemberExpr, OpExpr, ComparisonExpr, IndexExpr, UnaryExpr, YieldFromExpr
)


TYPE_EMPTY = 0
TYPE_PRECISE = 1
TYPE_IMPRECISE = 2
TYPE_ANY = 3

precision_names = [
    'empty',
    'precise',
    'imprecise',
    'any',
]


class StatisticsVisitor(TraverserVisitor):
    def __init__(self, inferred: bool, typemap: Dict[Node, Type] = None,
                 all_nodes: bool = False) -> None:
        self.inferred = inferred
        self.typemap = typemap
        self.all_nodes = all_nodes

        self.num_precise = 0
        self.num_imprecise = 0
        self.num_any = 0

        self.num_simple = 0
        self.num_generic = 0
        self.num_tuple = 0
        self.num_function = 0
        self.num_typevar = 0
        self.num_complex = 0

        self.line = -1

        self.line_map = {}  # type: Dict[int, int]

        self.output = []  # type: List[str]

        TraverserVisitor.__init__(self)

    def visit_func_def(self, o: FuncDef) -> None:
        self.line = o.line
        if len(o.expanded) > 1:
            if o in o.expanded:
                print('ERROR: cycle in function expansion; skipping')
                return
            for defn in o.expanded:
                self.visit_func_def(cast(FuncDef, defn))
        else:
            if o.type:
                sig = cast(CallableType, o.type)
                arg_types = sig.arg_types
                if (sig.arg_names and sig.arg_names[0] == 'self' and
                        not self.inferred):
                    arg_types = arg_types[1:]
                for arg in arg_types:
                    self.type(arg)
                self.type(sig.ret_type)
            elif self.all_nodes:
                self.record_line(self.line, TYPE_ANY)
            super().visit_func_def(o)

    def visit_type_application(self, o: TypeApplication) -> None:
        self.line = o.line
        for t in o.types:
            self.type(t)
        super().visit_type_application(o)

    def visit_assignment_stmt(self, o: AssignmentStmt) -> None:
        self.line = o.line
        if (isinstance(o.rvalue, nodes.CallExpr) and
                isinstance(o.rvalue.analyzed, nodes.TypeVarExpr)):
            # Type variable definition -- not a real assignment.
            return
        if o.type:
            self.type(o.type)
        elif self.inferred:
            for lvalue in o.lvalues:
                if isinstance(lvalue, nodes.TupleExpr):
                    items = lvalue.items
                elif isinstance(lvalue, nodes.ListExpr):
                    items = lvalue.items
                else:
                    items = [lvalue]
                for item in items:
                    if hasattr(item, 'is_def') and cast(Any, item).is_def:
                        t = self.typemap.get(item)
                        if t:
                            self.type(t)
                        else:
                            self.log('  !! No inferred type on line %d' %
                                     self.line)
                            self.record_line(self.line, TYPE_ANY)
        super().visit_assignment_stmt(o)

    def visit_name_expr(self, o: NameExpr) -> None:
        self.process_node(o)
        super().visit_name_expr(o)

    def visit_yield_from_expr(self, o: YieldFromExpr) -> None:
        if o.expr:
            o.expr.accept(self)

    def visit_call_expr(self, o: CallExpr) -> None:
        self.process_node(o)
        if o.analyzed:
            o.analyzed.accept(self)
        else:
            o.callee.accept(self)
            for a in o.args:
                a.accept(self)

    def visit_member_expr(self, o: MemberExpr) -> None:
        self.process_node(o)
        super().visit_member_expr(o)

    def visit_op_expr(self, o: OpExpr) -> None:
        self.process_node(o)
        super().visit_op_expr(o)

    def visit_comparison_expr(self, o: ComparisonExpr) -> None:
        self.process_node(o)
        super().visit_comparison_expr(o)

    def visit_index_expr(self, o: IndexExpr) -> None:
        self.process_node(o)
        super().visit_index_expr(o)

    def visit_unary_expr(self, o: UnaryExpr) -> None:
        self.process_node(o)
        super().visit_unary_expr(o)

    def process_node(self, node: Node) -> None:
        if self.all_nodes:
            typ = self.typemap.get(node)
            if typ:
                self.line = node.line
                self.type(typ)

    def type(self, t: Type) -> None:
        if isinstance(t, AnyType):
            self.log('  !! Any type around line %d' % self.line)
            self.num_any += 1
            self.record_line(self.line, TYPE_ANY)
        elif ((not self.all_nodes and is_imprecise(t)) or
              (self.all_nodes and is_imprecise2(t))):
            self.log('  !! Imprecise type around line %d' % self.line)
            self.num_imprecise += 1
            self.record_line(self.line, TYPE_IMPRECISE)
        else:
            self.num_precise += 1
            self.record_line(self.line, TYPE_PRECISE)

        if isinstance(t, Instance):
            if t.args:
                if any(is_complex(arg) for arg in t.args):
                    self.num_complex += 1
                else:
                    self.num_generic += 1
            else:
                self.num_simple += 1
        elif isinstance(t, Void):
            self.num_simple += 1
        elif isinstance(t, FunctionLike):
            self.num_function += 1
        elif isinstance(t, TupleType):
            if any(is_complex(item) for item in t.items):
                self.num_complex += 1
            else:
                self.num_tuple += 1
        elif isinstance(t, TypeVarType):
            self.num_typevar += 1

    def log(self, string: str) -> None:
        self.output.append(string)

    def record_line(self, line: int, precision: int) -> None:
        self.line_map[line] = max(precision,
                                  self.line_map.get(line, TYPE_PRECISE))


def dump_type_stats(tree: Node, path: str, inferred: bool = False,
                    typemap: Dict[Node, Type] = None) -> None:
    if is_special_module(path):
        return
    print(path)
    visitor = StatisticsVisitor(inferred, typemap)
    tree.accept(visitor)
    for line in visitor.output:
        print(line)
    print('  ** precision **')
    print('  precise  ', visitor.num_precise)
    print('  imprecise', visitor.num_imprecise)
    print('  any      ', visitor.num_any)
    print('  ** kinds **')
    print('  simple   ', visitor.num_simple)
    print('  generic  ', visitor.num_generic)
    print('  function ', visitor.num_function)
    print('  tuple    ', visitor.num_tuple)
    print('  TypeVar  ', visitor.num_typevar)
    print('  complex  ', visitor.num_complex)
    print('  any      ', visitor.num_any)


def is_special_module(path: str) -> bool:
    return os.path.basename(path) in ('abc.pyi', 'typing.pyi', 'builtins.pyi')


def is_imprecise(t: Type) -> bool:
    return t.accept(HasAnyQuery())


class HasAnyQuery(TypeQuery):
    def __init__(self) -> None:
        super().__init__(False, ANY_TYPE_STRATEGY)

    def visit_any(self, t: AnyType) -> bool:
        return True

    def visit_instance(self, t: Instance) -> bool:
        if t.type.fullname() == 'builtins.tuple':
            return True
        else:
            return super().visit_instance(t)


def is_imprecise2(t: Type) -> bool:
    return t.accept(HasAnyQuery2())


class HasAnyQuery2(HasAnyQuery):
    def visit_callable_type(self, t: CallableType) -> bool:
        # We don't want to flag references to functions with some Any
        # argument types (etc.) since they generally don't mean trouble.
        return False


def is_generic(t: Type) -> bool:
    return isinstance(t, Instance) and bool(t.args)


def is_complex(t: Type) -> bool:
    return is_generic(t) or isinstance(t, (FunctionLike, TupleType,
                                           TypeVarType))


html_files = []  # type: List[Tuple[str, str, int, int]]


def generate_html_report(tree: Node, path: str, type_map: Dict[Node, Type],
                         output_dir: str) -> None:
    if is_special_module(path):
        return
    # There may be more than one right answer for "what should we do here?"
    # but this is a reasonable one.
    path = os.path.relpath(path)
    if path.startswith('..'):
        return
    visitor = StatisticsVisitor(inferred=True, typemap=type_map, all_nodes=True)
    tree.accept(visitor)
    assert not os.path.isabs(path) and not path.startswith('..')
    # This line is *wrong* if the preceding assert fails.
    target_path = os.path.join(output_dir, 'html', path)
    # replace .py or .pyi with .html
    target_path = os.path.splitext(target_path)[0] + '.html'
    assert target_path.endswith('.html')
    ensure_dir_exists(os.path.dirname(target_path))
    output = []  # type: List[str]
    append = output.append
    append('''\
<html>
<head>
  <style>
    .red { background-color: #faa; }
    .yellow { background-color: #ffa; }
    .white { }
    .lineno { color: #999; }
  </style>
</head>
<body>
<pre>''')
    num_imprecise_lines = 0
    num_lines = 0
    with open(path) as input_file:
        for i, line in enumerate(input_file):
            lineno = i + 1
            status = visitor.line_map.get(lineno, TYPE_PRECISE)
            style_map = {TYPE_PRECISE: 'white',
                         TYPE_IMPRECISE: 'yellow',
                         TYPE_ANY: 'red'}
            style = style_map[status]
            append('<span class="lineno">%4d</span>   ' % lineno +
                   '<span class="%s">%s</span>' % (style,
                                                   cgi.escape(line)))
            if status != TYPE_PRECISE:
                num_imprecise_lines += 1
            if line.strip():
                num_lines += 1
    append('</pre>')
    append('</body></html>')
    with open(target_path, 'w') as output_file:
        output_file.writelines(output)
    target_path = target_path[len(output_dir) + 1:]
    html_files.append((path, target_path, num_lines, num_imprecise_lines))


def generate_html_index(output_dir: str) -> None:
    path = os.path.join(output_dir, 'index.html')
    output = []  # type: List[str]
    append = output.append
    append('''\
<html>
<head>
  <style>
  body { font-family: courier; }
  table { border-collapse: collapse; }
  table tr td { border: 1px solid black; }
  td { padding: 0.4em; }
  .red { background-color: #faa; }
  .yellow { background-color: #ffa; }
  </style>
</head>
<body>''')
    append('<h1>Mypy Type Check Coverage Report</h1>\n')
    append('<table>\n')
    for source_path, target_path, num_lines, num_imprecise in sorted(html_files):
        if num_lines == 0:
            continue
        source_path = os.path.normpath(source_path)
        # TODO: Windows paths.
        if (source_path.startswith('stubs/') or
                '/stubs/' in source_path):
            continue
        percent = 100.0 * num_imprecise / num_lines
        style = ''
        if percent >= 20:
            style = 'class="red"'
        elif percent >= 5:
            style = 'class="yellow"'
        append('<tr %s><td><a href="%s">%s</a><td>%.1f%% imprecise<td>%d LOC\n' % (
            style, target_path, source_path, percent, num_lines))
    append('</table>\n')
    append('</body></html>')
    with open(path, 'w') as file:
        file.writelines(output)
    print('Generated HTML report (old): %s' % os.path.abspath(path))


def ensure_dir_exists(dir: str) -> None:
    if not os.path.exists(dir):
        os.makedirs(dir)
