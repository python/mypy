from typing import Dict, List

from mypy.nodes import (
    Block, AssignmentStmt, NameExpr, MypyFile, FuncDef, Lvalue, ListExpr, TupleExpr, TempNode,
    WhileStmt, ForStmt, BreakStmt, ContinueStmt, TryStmt, WithStmt, StarExpr, ImportFrom, MemberExpr,
    IndexExpr
)
from mypy.traverser import TraverserVisitor
from mypy.semanal_shared import VarDefAnalyzer


class VariableRenameVisitor(TraverserVisitor):
    """Rename variables to allow redefinition of variables.

    For example, consider this code:

      x = 0
      f(x)
      x = ''
      g(x)

    It can be renamed to this:

      x~ = 0
      f(x~)
      x = ''
      g(X)

    TODO:
     * renaming in functions (argument redef)
     * loops
     * break/continue
     * break/continue
     * inititalizer / no initializer
     * nested functions
       * prevent redefinition -> no need to rename internally
     * Final

     - multiple renamings
       * global
       - local

     - kinds of names
       * for index variables
       * imports
       - funcdef and such
       - classdef
       - other ways of assigning to variables

     - nested class
     - overloaded func
     - decorated func
    """

    def __init__(self) -> None:
        self.var_def_analyzer = VarDefAnalyzer()
        self.refs = []  # type: List[Dict[str, List[List[NameExpr]]]]

    def visit_mypy_file(self, file_node: MypyFile) -> None:
        self.var_def_analyzer.clear()
        self.var_def_analyzer.enter_block()
        self.refs.append({})
        for d in file_node.defs:
            d.accept(self)
        self.flush_refs()
        self.var_def_analyzer.leave_block()

    def visit_func_def(self, fdef: FuncDef) -> None:
        # Conservatively do not allow variable defined before a function to
        # be redefined later, since function could refer to either definition.
        self.var_def_analyzer.reject_redefinition_of_vars_in_scope()
        self.var_def_analyzer.process_assignment(fdef.name(), can_be_redefined=False)
        self.var_def_analyzer.enter_scope()
        self.refs.append({})

        for arg in fdef.arguments:
            name = arg.variable.name()
            self.var_def_analyzer.process_assignment(arg.variable.name(),
                                                     can_be_redefined=True)
            self.handle_arg(name)

        self.visit_block(fdef.body, enter=False)
        self.flush_refs()
        self.var_def_analyzer.leave_scope()

    def visit_block(self, block: Block, enter: bool = True) -> None:
        if enter:
            self.var_def_analyzer.enter_block()
        super().visit_block(block)
        if enter:
            self.var_def_analyzer.leave_block()

    def visit_while_stmt(self, stmt: WhileStmt) -> None:
        self.var_def_analyzer.enter_loop()
        super().visit_while_stmt(stmt)
        self.var_def_analyzer.leave_loop()

    def visit_for_stmt(self, stmt: ForStmt) -> None:
        self.analyze_lvalue(stmt.index, True)
        self.var_def_analyzer.enter_loop()
        super().visit_for_stmt(stmt)
        self.var_def_analyzer.leave_loop()

    def visit_break_stmt(self, stmt: BreakStmt) -> None:
        self.var_def_analyzer.reject_redefinition_of_vars_in_loop()

    def visit_continue_stmt(self, stmt: ContinueStmt) -> None:
        self.var_def_analyzer.reject_redefinition_of_vars_in_loop()

    def visit_try_stmt(self, stmt: TryStmt) -> None:
        self.var_def_analyzer.enter_with_or_try()
        super().visit_try_stmt(stmt)
        self.var_def_analyzer.leave_with_or_try()

    def visit_with_stmt(self, stmt: WithStmt) -> None:
        self.var_def_analyzer.enter_with_or_try()
        super().visit_with_stmt(stmt)
        self.var_def_analyzer.leave_with_or_try()

    def visit_assignment_stmt(self, s: AssignmentStmt) -> None:
        has_initializer = not isinstance(s.rvalue, TempNode)
        s.rvalue.accept(self)
        for lvalue in s.lvalues:
            self.analyze_lvalue(lvalue, has_initializer)

    def analyze_lvalue(self, lvalue: Lvalue, has_initializer: bool) -> None:
        if isinstance(lvalue, NameExpr):
            name = lvalue.name
            is_new = self.var_def_analyzer.process_assignment(name, True, not has_initializer)
            if is_new: # and name != '_':  # Underscore gets special handling later
                self.handle_def(lvalue)
            else:
                self.handle_ref(lvalue)
        elif isinstance(lvalue, (ListExpr, TupleExpr)):
            for item in lvalue.items:
                self.analyze_lvalue(item, has_initializer)
        elif isinstance(lvalue, MemberExpr):
            lvalue.expr.accept(self)
        elif isinstance(lvalue, IndexExpr):
            lvalue.base.accept(self)
            lvalue.index.accept(self)
        elif isinstance(lvalue, StarExpr):
            self.analyze_lvalue(lvalue.expr, has_initializer)

    def visit_import_from(self, imp: ImportFrom) -> None:
        for id, as_id in imp.names:
            self.var_def_analyzer.process_assignment(as_id or id, False, False)

    def visit_name_expr(self, expr: NameExpr) -> None:
        self.handle_ref(expr)

    def handle_arg(self, name: str) -> None:
        if name not in self.refs[-1]:
            self.refs[-1][name] = [[]]

    def handle_def(self, expr: NameExpr) -> None:
        names = self.refs[-1].setdefault(expr.name, [])
        names.append([expr])

    def handle_ref(self, expr: NameExpr) -> None:
        name = expr.name
        if name in self.refs[-1]:
            names = self.refs[-1][name]
            if not names:
                names.append([])
            names[-1].append(expr)

    def flush_refs(self) -> None:
        is_func = self.var_def_analyzer.is_nested()
        for name, refs in self.refs[-1].items():
            if len(refs) == 1:
                continue
            if is_func:
                to_rename = refs[1:]
            else:
                to_rename = refs[:-1]
            for i, item in enumerate(to_rename):
                self.rename_refs(item, i)
        self.refs.pop()

    def rename_refs(self, names: List[NameExpr], index: int) -> None:
        name = names[0].name
        new_name = name + "'" * (index + 1)
        for expr in names:
            expr.name = new_name
