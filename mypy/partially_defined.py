from __future__ import annotations

from mypy import checker
from mypy.messages import MessageBuilder
from mypy.nodes import (
    AssertStmt,
    AssignmentExpr,
    AssignmentStmt,
    BreakStmt,
    ContinueStmt,
    DictionaryComprehension,
    Expression,
    ExpressionStmt,
    ForStmt,
    FuncDef,
    FuncItem,
    GeneratorExpr,
    IfStmt,
    ListExpr,
    Lvalue,
    MatchStmt,
    NameExpr,
    RaiseStmt,
    ReturnStmt,
    TupleExpr,
    WhileStmt,
    WithStmt,
)
from mypy.patterns import AsPattern, StarredPattern
from mypy.reachability import ALWAYS_TRUE, infer_pattern_value
from mypy.traverser import ExtendedTraverserVisitor
from mypy.types import Type, UninhabitedType


class BranchState:
    """BranchState contains information about variable definition at the end of a branching statement.
    `if` and `match` are examples of branching statements.

    `may_be_defined` contains variables that were defined in only some branches.
    `must_be_defined` contains variables that were defined in all branches.
    """

    def __init__(
        self,
        must_be_defined: set[str] | None = None,
        may_be_defined: set[str] | None = None,
        skipped: bool = False,
    ) -> None:
        if may_be_defined is None:
            may_be_defined = set()
        if must_be_defined is None:
            must_be_defined = set()

        self.may_be_defined = set(may_be_defined)
        self.must_be_defined = set(must_be_defined)
        self.skipped = skipped


class BranchStatement:
    def __init__(self, initial_state: BranchState) -> None:
        self.initial_state = initial_state
        self.branches: list[BranchState] = [
            BranchState(
                must_be_defined=self.initial_state.must_be_defined,
                may_be_defined=self.initial_state.may_be_defined,
            )
        ]

    def next_branch(self) -> None:
        self.branches.append(
            BranchState(
                must_be_defined=self.initial_state.must_be_defined,
                may_be_defined=self.initial_state.may_be_defined,
            )
        )

    def record_definition(self, name: str) -> None:
        assert len(self.branches) > 0
        self.branches[-1].must_be_defined.add(name)
        self.branches[-1].may_be_defined.discard(name)

    def record_nested_branch(self, state: BranchState) -> None:
        assert len(self.branches) > 0
        current_branch = self.branches[-1]
        if state.skipped:
            current_branch.skipped = True
            return
        current_branch.must_be_defined.update(state.must_be_defined)
        current_branch.may_be_defined.update(state.may_be_defined)
        current_branch.may_be_defined.difference_update(current_branch.must_be_defined)

    def skip_branch(self) -> None:
        assert len(self.branches) > 0
        self.branches[-1].skipped = True

    def is_possibly_undefined(self, name: str) -> bool:
        assert len(self.branches) > 0
        return name in self.branches[-1].may_be_defined

    def done(self) -> BranchState:
        branches = [b for b in self.branches if not b.skipped]
        if len(branches) == 0:
            return BranchState(skipped=True)
        if len(branches) == 1:
            return branches[0]

        # must_be_defined is a union of must_be_defined of all branches.
        must_be_defined = set(branches[0].must_be_defined)
        for b in branches[1:]:
            must_be_defined.intersection_update(b.must_be_defined)
        # may_be_defined are all variables that are not must be defined.
        all_vars = set()
        for b in branches:
            all_vars.update(b.may_be_defined)
            all_vars.update(b.must_be_defined)
        may_be_defined = all_vars.difference(must_be_defined)
        return BranchState(may_be_defined=may_be_defined, must_be_defined=must_be_defined)


class DefinedVariableTracker:
    """DefinedVariableTracker manages the state and scope for the UndefinedVariablesVisitor."""

    def __init__(self) -> None:
        # There's always at least one scope. Within each scope, there's at least one "global" BranchingStatement.
        self.scopes: list[list[BranchStatement]] = [[BranchStatement(BranchState())]]

    def _scope(self) -> list[BranchStatement]:
        assert len(self.scopes) > 0
        return self.scopes[-1]

    def enter_scope(self) -> None:
        assert len(self._scope()) > 0
        self.scopes.append([BranchStatement(self._scope()[-1].branches[-1])])

    def exit_scope(self) -> None:
        self.scopes.pop()

    def start_branch_statement(self) -> None:
        assert len(self._scope()) > 0
        self._scope().append(BranchStatement(self._scope()[-1].branches[-1]))

    def next_branch(self) -> None:
        assert len(self._scope()) > 1
        self._scope()[-1].next_branch()

    def end_branch_statement(self) -> None:
        assert len(self._scope()) > 1
        result = self._scope().pop().done()
        self._scope()[-1].record_nested_branch(result)

    def skip_branch(self) -> None:
        # Only skip branch if we're outside of "root" branch statement.
        if len(self._scope()) > 1:
            self._scope()[-1].skip_branch()

    def record_declaration(self, name: str) -> None:
        assert len(self.scopes) > 0
        assert len(self.scopes[-1]) > 0
        self._scope()[-1].record_definition(name)

    def is_possibly_undefined(self, name: str) -> bool:
        assert len(self._scope()) > 0
        # A variable is undefined if it's in a set of `may_be_defined` but not in `must_be_defined`.
        # Cases where a variable is not defined altogether are handled by semantic analyzer.
        return self._scope()[-1].is_possibly_undefined(name)


class PartiallyDefinedVariableVisitor(ExtendedTraverserVisitor):
    """Detect variables that are defined only part of the time.

    This visitor detects the following case:
    if foo():
        x = 1
    print(x)  # Error: "x" may be undefined.

    Note that this code does not detect variables not defined in any of the branches -- that is
    handled by the semantic analyzer.
    """

    def __init__(self, msg: MessageBuilder, type_map: dict[Expression, Type]) -> None:
        self.msg = msg
        self.type_map = type_map
        self.tracker = DefinedVariableTracker()

    def process_lvalue(self, lvalue: Lvalue | None) -> None:
        if isinstance(lvalue, NameExpr):
            self.tracker.record_declaration(lvalue.name)
        elif isinstance(lvalue, (ListExpr, TupleExpr)):
            for item in lvalue.items:
                self.process_lvalue(item)

    def visit_assignment_stmt(self, o: AssignmentStmt) -> None:
        for lvalue in o.lvalues:
            self.process_lvalue(lvalue)
        super().visit_assignment_stmt(o)

    def visit_assignment_expr(self, o: AssignmentExpr) -> None:
        o.value.accept(self)
        self.process_lvalue(o.target)

    def visit_if_stmt(self, o: IfStmt) -> None:
        for e in o.expr:
            e.accept(self)
        self.tracker.start_branch_statement()
        for b in o.body:
            b.accept(self)
            self.tracker.next_branch()
        if o.else_body:
            o.else_body.accept(self)
        self.tracker.end_branch_statement()

    def visit_match_stmt(self, o: MatchStmt) -> None:
        self.tracker.start_branch_statement()
        o.subject.accept(self)
        for i in range(len(o.patterns)):
            pattern = o.patterns[i]
            pattern.accept(self)
            guard = o.guards[i]
            if guard is not None:
                guard.accept(self)
            o.bodies[i].accept(self)
            is_catchall = infer_pattern_value(pattern) == ALWAYS_TRUE
            if not is_catchall:
                self.tracker.next_branch()
        self.tracker.end_branch_statement()

    def visit_func_def(self, o: FuncDef) -> None:
        self.tracker.enter_scope()
        super().visit_func_def(o)
        self.tracker.exit_scope()

    def visit_func(self, o: FuncItem) -> None:
        if o.arguments is not None:
            for arg in o.arguments:
                self.tracker.record_declaration(arg.variable.name)
        super().visit_func(o)

    def visit_generator_expr(self, o: GeneratorExpr) -> None:
        self.tracker.enter_scope()
        for idx in o.indices:
            self.process_lvalue(idx)
        super().visit_generator_expr(o)
        self.tracker.exit_scope()

    def visit_dictionary_comprehension(self, o: DictionaryComprehension) -> None:
        self.tracker.enter_scope()
        for idx in o.indices:
            self.process_lvalue(idx)
        super().visit_dictionary_comprehension(o)
        self.tracker.exit_scope()

    def visit_for_stmt(self, o: ForStmt) -> None:
        o.expr.accept(self)
        self.process_lvalue(o.index)
        o.index.accept(self)
        self.tracker.start_branch_statement()
        o.body.accept(self)
        self.tracker.next_branch()
        if o.else_body:
            o.else_body.accept(self)
        self.tracker.end_branch_statement()

    def visit_return_stmt(self, o: ReturnStmt) -> None:
        super().visit_return_stmt(o)
        self.tracker.skip_branch()

    def visit_assert_stmt(self, o: AssertStmt) -> None:
        super().visit_assert_stmt(o)
        if checker.is_false_literal(o.expr):
            self.tracker.skip_branch()

    def visit_raise_stmt(self, o: RaiseStmt) -> None:
        super().visit_raise_stmt(o)
        self.tracker.skip_branch()

    def visit_continue_stmt(self, o: ContinueStmt) -> None:
        super().visit_continue_stmt(o)
        self.tracker.skip_branch()

    def visit_break_stmt(self, o: BreakStmt) -> None:
        super().visit_break_stmt(o)
        self.tracker.skip_branch()

    def visit_expression_stmt(self, o: ExpressionStmt) -> None:
        if isinstance(self.type_map.get(o.expr, None), UninhabitedType):
            self.tracker.skip_branch()
        super().visit_expression_stmt(o)

    def visit_while_stmt(self, o: WhileStmt) -> None:
        o.expr.accept(self)
        self.tracker.start_branch_statement()
        o.body.accept(self)
        if not checker.is_true_literal(o.expr):
            self.tracker.next_branch()
            if o.else_body:
                o.else_body.accept(self)
        self.tracker.end_branch_statement()

    def visit_as_pattern(self, o: AsPattern) -> None:
        if o.name is not None:
            self.process_lvalue(o.name)
        super().visit_as_pattern(o)

    def visit_starred_pattern(self, o: StarredPattern) -> None:
        if o.capture is not None:
            self.process_lvalue(o.capture)
        super().visit_starred_pattern(o)

    def visit_name_expr(self, o: NameExpr) -> None:
        if self.tracker.is_possibly_undefined(o.name):
            self.msg.variable_may_be_undefined(o.name, o)
            # We don't want to report the error on the same variable multiple times.
            self.tracker.record_declaration(o.name)
        super().visit_name_expr(o)

    def visit_with_stmt(self, o: WithStmt) -> None:
        for expr, idx in zip(o.expr, o.target):
            expr.accept(self)
            self.process_lvalue(idx)
        o.body.accept(self)
