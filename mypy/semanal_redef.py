from typing import Dict, List

from mypy.nodes import (
    Block, AssignmentStmt, NameExpr, MypyFile, FuncDef, Lvalue, ListExpr, TupleExpr, TempNode,
    WhileStmt, ForStmt, BreakStmt, ContinueStmt, TryStmt, WithStmt, StarExpr, ImportFrom,
    MemberExpr, IndexExpr
)
from mypy.traverser import TraverserVisitor


class VariableRenameVisitor(TraverserVisitor):
    """Rename variables to allow redefinition of variables.

    For example, consider this code:

      x = 0
      f(x)

      x = ''
      g(x)

    It would be transformed to this:

      x' = 0
      f(x')

      x = ''
      g(x)

    There will be two independent variables (x' and x) that will have separate
    inferred types.

    Renaming only happens for assignments within the same block.

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
        # Counter for labeling new blocks
        self.block_id = 0
        self.disallow_redef_depth = 0
        self.loop_depth = 0
        # Map block id to loop depth.
        self.block_loop_depth = {}  # type: Dict[int, int]
        # Stack of block ids being processed.
        self.blocks = []  # type: List[int]
        # List of scopes; each scope maps short name to block id.
        self.var_blocks = [{}]  # type: List[Dict[str, int]]
        # Variables which have no assigned value yet (e.g., "x: t" but no assigment).
        # Assignment in any block is considered an initialization.
        self.uninitialized = set()  # type: Set[str]

        # References to variables
        self.refs = []  # type: List[Dict[str, List[List[NameExpr]]]]

    def visit_mypy_file(self, file_node: MypyFile) -> None:
        self.clear()
        self.enter_block()
        self.refs.append({})
        for d in file_node.defs:
            d.accept(self)
        self.flush_refs()
        self.leave_block()

    def visit_func_def(self, fdef: FuncDef) -> None:
        # Conservatively do not allow variable defined before a function to
        # be redefined later, since function could refer to either definition.
        self.reject_redefinition_of_vars_in_scope()
        self.process_assignment(fdef.name(), can_be_redefined=False)
        self.enter_scope()
        self.refs.append({})

        for arg in fdef.arguments:
            name = arg.variable.name()
            self.process_assignment(arg.variable.name(), can_be_redefined=True)
            self.handle_arg(name)

        self.visit_block(fdef.body, enter=False)
        self.flush_refs()
        self.leave_scope()

    def visit_block(self, block: Block, enter: bool = True) -> None:
        if enter:
            self.enter_block()
        super().visit_block(block)
        if enter:
            self.leave_block()

    def visit_while_stmt(self, stmt: WhileStmt) -> None:
        self.enter_loop()
        super().visit_while_stmt(stmt)
        self.leave_loop()

    def visit_for_stmt(self, stmt: ForStmt) -> None:
        self.analyze_lvalue(stmt.index, True)
        self.enter_loop()
        super().visit_for_stmt(stmt)
        self.leave_loop()

    def visit_break_stmt(self, stmt: BreakStmt) -> None:
        self.reject_redefinition_of_vars_in_loop()

    def visit_continue_stmt(self, stmt: ContinueStmt) -> None:
        self.reject_redefinition_of_vars_in_loop()

    def visit_try_stmt(self, stmt: TryStmt) -> None:
        self.enter_with_or_try()
        super().visit_try_stmt(stmt)
        self.leave_with_or_try()

    def visit_with_stmt(self, stmt: WithStmt) -> None:
        self.enter_with_or_try()
        super().visit_with_stmt(stmt)
        self.leave_with_or_try()

    def visit_assignment_stmt(self, s: AssignmentStmt) -> None:
        has_initializer = not isinstance(s.rvalue, TempNode)
        s.rvalue.accept(self)
        for lvalue in s.lvalues:
            self.analyze_lvalue(lvalue, has_initializer)

    def analyze_lvalue(self, lvalue: Lvalue, has_initializer: bool) -> None:
        if isinstance(lvalue, NameExpr):
            name = lvalue.name
            is_new = self.process_assignment(name, True, not has_initializer)
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
            self.process_assignment(as_id or id, False, False)

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
        is_func = self.is_nested()
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

    # ----

    def clear(self) -> None:
        self.blocks = []
        self.var_blocks = [{}]

    def enter_block(self) -> None:
        self.block_id += 1
        self.blocks.append(self.block_id)
        self.block_loop_depth[self.block_id] = self.loop_depth

    def leave_block(self) -> None:
        self.blocks.pop()

    def enter_with_or_try(self) -> None:
        self.disallow_redef_depth += 1

    def leave_with_or_try(self) -> None:
        self.disallow_redef_depth -= 1

    def enter_loop(self) -> None:
        self.loop_depth += 1

    def leave_loop(self) -> None:
        self.loop_depth -= 1

    def current_block(self) -> int:
        return self.blocks[-1]

    def enter_scope(self) -> None:
        self.var_blocks.append({})

    def leave_scope(self) -> None:
        self.var_blocks.pop()

    def is_nested(self) -> int:
        return len(self.var_blocks) > 1

    def reject_redefinition_of_vars_in_scope(self) -> None:
        """Make it impossible to redefine defined variables in the current scope.

        This is used if we encounter a function definition or break/continue that
        can make it ambiguous which definition is live.
        """
        var_blocks = self.var_blocks[-1]
        for key in var_blocks:
            var_blocks[key] = -1

    def reject_redefinition_of_vars_in_loop(self) -> None:
        var_blocks = self.var_blocks[-1]
        for key, block in var_blocks.items():
            if self.block_loop_depth.get(block) == self.loop_depth:
                var_blocks[key] = -1

    def process_assignment(self, name: str, can_be_redefined: bool, no_value: bool = False) -> bool:
        """Record assignment to given name and return True if it defines a new name.

        Args:
            can_be_redefined: If True, allows assignment in the same block to redefine the name
            no_value: If True, the first assignment we encounter will not be considered to redefine
                this but to initilize it (in any block)
        """
        if self.disallow_redef_depth > 0:
            can_be_redefined = False
        block = self.current_block()
        var_blocks = self.var_blocks[-1]
        uninitialized = self.uninitialized
        existing_no_value = name in self.uninitialized
        if no_value:
            uninitialized.add(name)
        else:
            uninitialized.discard(name)
        if name not in var_blocks:
            # New definition
            if can_be_redefined:
                var_blocks[name] = block
            else:
                # This doesn't support arbitrary redefinition.
                # TODO: Make this less restricted.
                var_blocks[name] = -1
            return True
        elif var_blocks[name] == block and not existing_no_value:
            # Redefinition
            return True
        else:
            return False
