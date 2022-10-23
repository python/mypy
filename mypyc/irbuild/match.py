from contextlib import contextmanager
from typing import Generator

from mypy.nodes import MatchStmt, TypeInfo
from mypyc.ir.ops import Value, BasicBlock
from mypy.patterns import (
    AsPattern,
    ClassPattern,
    OrPattern,
    MappingPattern,
    SingletonPattern,
    ValuePattern,
)
from mypy.traverser import TraverserVisitor
from mypy.types import Instance, TupleType

from mypyc.primitives.generic_ops import py_getattr_op
from mypyc.primitives.misc_ops import (
    check_mapping_protocol,
    dict_copy,
    dict_del_item,
    slow_isinstance_op,
)
from mypyc.irbuild.builder import IRBuilder

class MatchVisitor(TraverserVisitor):
    builder: IRBuilder
    code_block: BasicBlock
    next_block: BasicBlock
    final_block: BasicBlock
    subject: Value
    match: MatchStmt

    as_pattern: AsPattern | None = None

    def __init__(self, builder: IRBuilder, match_node: MatchStmt) -> None:
        self.builder = builder

        self.code_block = BasicBlock()
        self.next_block = BasicBlock()
        self.final_block = BasicBlock()

        self.match = match_node
        self.subject = builder.accept(match_node.subject)

    def build_match_body(self, index: int) -> None:
        self.builder.activate_block(self.code_block)

        if guard := self.match.guards[index]:
            self.code_block = BasicBlock()

            cond = self.builder.accept(guard)
            self.builder.add_bool_branch(cond, self.code_block, self.next_block)

            self.builder.activate_block(self.code_block)

        self.builder.accept(self.match.bodies[index])
        self.builder.goto(self.final_block)

    def visit_match_stmt(self, m: MatchStmt) -> None:
        for i, pattern in enumerate(m.patterns):
            self.code_block = BasicBlock()
            self.next_block = BasicBlock()

            pattern.accept(self)

            self.build_match_body(i)
            self.builder.activate_block(self.next_block)

        self.builder.goto_and_activate(self.final_block)

    def visit_value_pattern(self, pattern: ValuePattern) -> None:
        value = self.builder.accept(pattern.expr)

        cond = self.builder.binary_op(
            self.subject,
            value,
            "==",
            pattern.expr.line
        )

        self.bind_as_pattern(value)

        self.builder.add_bool_branch(cond, self.code_block, self.next_block)

    def visit_or_pattern(self, pattern: OrPattern) -> None:
        backup_block = self.next_block
        self.next_block = BasicBlock()

        for p in pattern.patterns:
            # Hack to ensure the as pattern is bound to each pattern in the
            # "or" pattern, but not every subpattern
            backup = self.as_pattern
            p.accept(self)
            self.as_pattern = backup

            self.builder.activate_block(self.next_block)
            self.next_block = BasicBlock()

        self.next_block = backup_block
        self.builder.goto(self.next_block)

    def visit_class_pattern(self, pattern: ClassPattern) -> None:
        cond = self.builder.call_c(
            slow_isinstance_op,
            [self.subject, self.builder.accept(pattern.class_ref)],
            pattern.line
        )

        self.bind_as_pattern(self.subject)

        self.builder.add_bool_branch(cond, self.code_block, self.next_block)

        if pattern.positionals:
            node = pattern.class_ref.node
            assert isinstance(node, TypeInfo)

            ty = node.names.get("__match_args__")
            assert ty and isinstance(ty.type, TupleType)

            match_args: list[str] = []

            for item in ty.type.items:
                assert isinstance(item, Instance) and item.last_known_value

                value = item.last_known_value.value
                assert isinstance(value, str)

                match_args.append(value)

            for i, expr in enumerate(pattern.positionals):
                self.builder.activate_block(self.code_block)
                self.code_block = BasicBlock()

                value = self.builder.py_get_attr(
                    self.subject, match_args[i], expr.line
                )

                with self.enter_subpattern(value):
                    expr.accept(self)

        for key, value in zip(pattern.keyword_keys, pattern.keyword_values):
            self.builder.activate_block(self.code_block)
            self.code_block = BasicBlock()

            attr = self.builder.py_get_attr(self.subject, key, value.line)

            with self.enter_subpattern(attr):
                value.accept(self)

    def visit_as_pattern(self, pattern: AsPattern) -> None:
        if pattern.pattern:
            with self.enter_as_pattern(pattern):
                pattern.pattern.accept(self)

        elif pattern.name:
            target = self.builder.get_assignment_target(pattern.name)

            self.builder.assign(target, self.subject, pattern.line)

        self.builder.goto(self.code_block)

    def visit_singleton_pattern(self, pattern: SingletonPattern) -> None:
        if pattern.value is None:
            obj = self.builder.none_object()
        elif pattern.value is True:
            obj = self.builder.true()
        else:
            obj = self.builder.false()

        cond = self.builder.binary_op(self.subject, obj, "is", pattern.line)

        self.builder.add_bool_branch(cond, self.code_block, self.next_block)

    def visit_mapping_pattern(self, pattern: MappingPattern) -> None:
        is_map = self.builder.call_c(
            check_mapping_protocol,
            [self.subject],
            pattern.line,
        )

        self.builder.add_bool_branch(is_map, self.code_block, self.next_block)

        keys: list[Value] = []

        for key, value in zip(pattern.keys, pattern.values):
            self.builder.activate_block(self.code_block)
            self.code_block = BasicBlock()

            key_value = self.builder.accept(key)
            keys.append(key_value)

            attr = self.builder.call_c(
                py_getattr_op,
                [self.subject, key_value],
                pattern.line
            )

            with self.enter_subpattern(attr):
                value.accept(self)

        if pattern.rest:
            self.builder.activate_block(self.code_block)
            self.code_block = BasicBlock()

            rest = self.builder.call_c(
                dict_copy,
                [self.subject],
                pattern.rest.line,
            )

            target = self.builder.get_assignment_target(pattern.rest)

            self.builder.assign(target, rest, pattern.rest.line)

            for i, key in enumerate(keys):
                self.builder.call_c(dict_del_item, [rest, key], pattern.keys[i].line)

            self.builder.goto(self.code_block)

    def bind_as_pattern(self, value: Value) -> None:
        if self.as_pattern and self.as_pattern.name:
            target = self.builder.get_assignment_target(self.as_pattern.name)
            self.builder.assign(target, value, self.as_pattern.pattern.line)  # type: ignore

            self.as_pattern = None

    @contextmanager
    def enter_subpattern(self, subject: Value) -> Generator[None, None, None]:
        old_subject = self.subject
        self.subject = subject
        yield
        self.subject = old_subject

    @contextmanager
    def enter_as_pattern(self, pattern: AsPattern) -> Generator[None, None, None]:
        old_pattern = self.as_pattern
        self.as_pattern = pattern
        yield
        self.as_pattern = old_pattern
