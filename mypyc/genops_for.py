"""Helpers for generating for loops.

We special case certain kinds for loops such as "for x in range(...)"
for better efficiency.  Each for loop generator class below deals one
such special case.
"""

from typing import Union, List
from typing_extensions import TYPE_CHECKING

from mypy.nodes import Lvalue, Expression
from mypyc.ops import (
    Value, BasicBlock, is_short_int_rprimitive, LoadInt, RType,
    PrimitiveOp, Branch, Register, AssignmentTarget
)
from mypyc.ops_int import unsafe_short_add
from mypyc.ops_list import list_len_op, list_get_item_unsafe_op
from mypyc.ops_misc import iter_op, next_op
from mypyc.ops_exc import no_err_occurred_op

if TYPE_CHECKING:
    import mypyc.genops


class ForGenerator:
    """Abstract base class for generating for loops."""

    def __init__(self,
                 builder: 'mypyc.genops.IRBuilder',
                 index: Lvalue,
                 body_block: BasicBlock,
                 loop_exit: BasicBlock,
                 line: int,
                 nested: bool) -> None:
        self.builder = builder
        self.index = index
        self.body_block = body_block
        self.line = line
        # Some for loops need a cleanup block that we execute at exit. We
        # create a cleanup block if needed. However, if we are generating a for
        # loop for a nested iterator, such as "e" in "enumerate(e)", the
        # outermost generator should generate the cleanup block -- we don't
        # need to do it here.
        if self.need_cleanup() and not nested:
            # Create a new block to handle cleanup after loop exit.
            self.loop_exit = BasicBlock()
        else:
            # Just use the existing loop exit block.
            self.loop_exit = loop_exit

    def need_cleanup(self) -> bool:
        """If this returns true, we need post-loop cleanup."""
        return False

    def add_cleanup(self, exit_block: BasicBlock) -> None:
        """Add post-loop cleanup, if needed."""
        if self.need_cleanup():
            self.builder.activate_block(self.loop_exit)
            self.gen_cleanup()
            self.builder.goto(exit_block)

    def gen_condition(self) -> None:
        """Generate check for loop exit (e.g. exhaustion of iteration)."""

    def begin_body(self) -> None:
        """Generate ops at the beginning of the body (if needed)."""

    def gen_step(self) -> None:
        """Generate stepping to the next item (if needed)."""

    def gen_cleanup(self) -> None:
        """Generate post-loop cleanup (if needed)."""


class ForIterable(ForGenerator):
    """Generate IR for a for loop over an arbitrary iterable (the normal case)."""

    def need_cleanup(self) -> bool:
        # Create a new cleanup block for when the loop is finished.
        return True

    def init(self, expr_reg: Value, target_type: RType) -> None:
        # Define targets to contain the expression, along with the iterator that will be used
        # for the for-loop. If we are inside of a generator function, spill these into the
        # environment class.
        builder = self.builder
        iter_reg = builder.primitive_op(iter_op, [expr_reg], self.line)
        builder.maybe_spill(expr_reg)
        self.iter_target = builder.maybe_spill(iter_reg)
        self.target_type = target_type

    def gen_condition(self) -> None:
        # We call __next__ on the iterator and check to see if the return value
        # is NULL, which signals either the end of the Iterable being traversed
        # or an exception being raised. Note that Branch.IS_ERROR checks only
        # for NULL (an exception does not necessarily have to be raised).
        builder = self.builder
        line = self.line
        self.next_reg = builder.primitive_op(next_op, [builder.read(self.iter_target, line)], line)
        builder.add(Branch(self.next_reg, self.loop_exit, self.body_block, Branch.IS_ERROR))

    def begin_body(self) -> None:
        # Assign the value obtained from __next__ to the
        # lvalue so that it can be referenced by code in the body of the loop.
        builder = self.builder
        line = self.line
        # We unbox here so that iterating with tuple unpacking generates a tuple based
        # unpack instead of an iterator based one.
        next_reg = builder.coerce(self.next_reg, self.target_type, line)
        builder.assign(builder.get_assignment_target(self.index), next_reg, line)

    def gen_step(self) -> None:
        # Nothing to do here, since we get the next item as part of gen_condition().
        pass

    def gen_cleanup(self) -> None:
        # We set the branch to go here if the conditional evaluates to true. If
        # an exception was raised during the loop, then err_reg wil be set to
        # True. If no_err_occurred_op returns False, then the exception will be
        # propagated using the ERR_FALSE flag.
        self.builder.primitive_op(no_err_occurred_op, [], self.line)


# TODO: Generalize to support other sequences (tuples at least) with
# different length and indexing ops.
class ForList(ForGenerator):
    """Generate optimized IR for a for loop over a list.

    Supports iterating in both forward and reverse."""

    def init(self, expr_reg: Value, target_type: RType, reverse: bool) -> None:
        builder = self.builder
        self.reverse = reverse
        # Define target to contain the expression, along with the index that will be used
        # for the for-loop. If we are inside of a generator function, spill these into the
        # environment class.
        self.expr_target = builder.maybe_spill(expr_reg)
        if not reverse:
            index_reg = builder.add(LoadInt(0))
        else:
            index_reg = builder.binary_op(self.load_len(), builder.add(LoadInt(1)), '-', self.line)
        self.index_target = builder.maybe_spill_assignable(index_reg)
        self.target_type = target_type

    def load_len(self) -> Value:
        return self.builder.add(PrimitiveOp([self.builder.read(self.expr_target, self.line)],
                                            list_len_op, self.line))

    def gen_condition(self) -> None:
        builder = self.builder
        line = self.line
        if self.reverse:
            # If we are iterating in reverse order, we obviously need
            # to check that the index is still positive. Somewhat less
            # obviously we still need to check against the length,
            # since it could shrink out from under us.
            comparison = builder.binary_op(builder.read(self.index_target, line),
                                           builder.add(LoadInt(0)), '>=', line)
            second_check = BasicBlock()
            builder.add_bool_branch(comparison, second_check, self.loop_exit)
            builder.activate_block(second_check)
        # For compatibility with python semantics we recalculate the length
        # at every iteration.
        len_reg = self.load_len()
        comparison = builder.binary_op(builder.read(self.index_target, line), len_reg, '<', line)
        builder.add_bool_branch(comparison, self.body_block, self.loop_exit)

    def begin_body(self) -> None:
        builder = self.builder
        line = self.line
        # Read the next list item.
        value_box = builder.primitive_op(
            list_get_item_unsafe_op,
            [builder.read(self.expr_target, line), builder.read(self.index_target, line)],
            line)
        assert value_box
        # We coerce to the type of list elements here so that
        # iterating with tuple unpacking generates a tuple based
        # unpack instead of an iterator based one.
        builder.assign(builder.get_assignment_target(self.index),
                       builder.coerce(value_box, self.target_type, line), line)

    def gen_step(self) -> None:
        # Step to the next item.
        builder = self.builder
        line = self.line
        step = 1 if not self.reverse else -1
        builder.assign(self.index_target, builder.primitive_op(
            unsafe_short_add,
            [builder.read(self.index_target, line),
             builder.add(LoadInt(step))], line), line)


class ForRange(ForGenerator):
    """Generate optimized IR for a for loop over an integer range."""

    # TODO: Use a separate register for the index to allow safe index mutation.

    def init(self, start_reg: Value, end_reg: Value, step: int) -> None:
        builder = self.builder
        self.start_reg = start_reg
        self.end_reg = end_reg
        self.step = step
        self.end_target = builder.maybe_spill(end_reg)
        self.index_reg = builder.maybe_spill_assignable(start_reg)
        # Initialize loop index to 0. Assert that the index target is assignable.
        self.index_target = builder.get_assignment_target(
            self.index)  # type: Union[Register, AssignmentTarget]
        builder.assign(self.index_target, builder.read(self.index_reg, self.line), self.line)

    def gen_condition(self) -> None:
        builder = self.builder
        line = self.line
        # Add loop condition check.
        cmp = '<' if self.step > 0 else '>'
        comparison = builder.binary_op(builder.read(self.index_target, line),
                                       builder.read(self.end_target, line), cmp, line)
        builder.add_bool_branch(comparison, self.body_block, self.loop_exit)

    def gen_step(self) -> None:
        builder = self.builder
        line = self.line

        # Increment index register. If the range is known to fit in short ints, use
        # short ints.
        if (is_short_int_rprimitive(self.start_reg.type)
                and is_short_int_rprimitive(self.end_reg.type)):
            new_val = builder.primitive_op(
                unsafe_short_add, [builder.read(self.index_reg, line),
                                   builder.add(LoadInt(self.step))], line)

        else:
            new_val = builder.binary_op(
                builder.read(self.index_reg, line), builder.add(LoadInt(self.step)), '+', line)
        builder.assign(self.index_reg, new_val, line)
        builder.assign(self.index_target, new_val, line)


class ForInfiniteCounter(ForGenerator):
    """Generate optimized IR for a for loop counting from 0 to infinity."""

    def init(self) -> None:
        builder = self.builder
        # Create a register to store the state of the loop index and
        # initialize this register along with the loop index to 0.
        zero = builder.add(LoadInt(0))
        self.index_reg = builder.maybe_spill_assignable(zero)
        self.index_target = builder.get_assignment_target(
            self.index)  # type: Union[Register, AssignmentTarget]
        builder.assign(self.index_target, zero, self.line)

    def gen_step(self) -> None:
        builder = self.builder
        line = self.line
        # We can safely assume that the integer is short, since we are not going to wrap
        # around a 63-bit integer.
        # NOTE: This would be questionable if short ints could be 32 bits.
        new_val = builder.primitive_op(
            unsafe_short_add, [builder.read(self.index_reg, line),
                               builder.add(LoadInt(1))], line)
        builder.assign(self.index_reg, new_val, line)
        builder.assign(self.index_target, new_val, line)


class ForEnumerate(ForGenerator):
    """Generate optimized IR for a for loop of form "for i, x in enumerate(it)"."""

    def need_cleanup(self) -> bool:
        # The wrapped for loop might need cleanup. This might generate a
        # redundant cleanup block, but that's okay.
        return True

    def init(self, index1: Lvalue, index2: Lvalue, expr: Expression) -> None:
        # Count from 0 to infinity (for the index lvalue).
        self.index_gen = ForInfiniteCounter(
            self.builder,
            index1,
            self.body_block,
            self.loop_exit,
            self.line, nested=True)
        self.index_gen.init()
        # Iterate over the actual iterable.
        self.main_gen = self.builder.make_for_loop_generator(
            index2,
            expr,
            self.body_block,
            self.loop_exit,
            self.line, nested=True)

    def gen_condition(self) -> None:
        # No need for a check for the index generator, since it's unconditional.
        self.main_gen.gen_condition()

    def begin_body(self) -> None:
        self.index_gen.begin_body()
        self.main_gen.begin_body()

    def gen_step(self) -> None:
        self.index_gen.gen_step()
        self.main_gen.gen_step()

    def gen_cleanup(self) -> None:
        self.index_gen.gen_cleanup()
        self.main_gen.gen_cleanup()


class ForZip(ForGenerator):
    """Generate IR for a for loop of form `for x, ... in zip(a, ...)`."""

    def need_cleanup(self) -> bool:
        # The wrapped for loops might need cleanup. We might generate a
        # redundant cleanup block, but that's okay.
        return True

    def init(self, indexes: List[Lvalue], exprs: List[Expression]) -> None:
        assert len(indexes) == len(exprs)
        # Condition check will require multiple basic blocks, since there will be
        # multiple conditions to check.
        self.cond_blocks = [BasicBlock() for _ in range(len(indexes) - 1)] + [self.body_block]
        self.gens = []  # type: List[ForGenerator]
        for index, expr, next_block in zip(indexes, exprs, self.cond_blocks):
            gen = self.builder.make_for_loop_generator(
                index,
                expr,
                next_block,
                self.loop_exit,
                self.line, nested=True)
            self.gens.append(gen)

    def gen_condition(self) -> None:
        for i, gen in enumerate(self.gens):
            gen.gen_condition()
            if i < len(self.gens) - 1:
                self.builder.activate_block(self.cond_blocks[i])

    def begin_body(self) -> None:
        for gen in self.gens:
            gen.begin_body()

    def gen_step(self) -> None:
        for gen in self.gens:
            gen.gen_step()

    def gen_cleanup(self) -> None:
        for gen in self.gens:
            gen.gen_cleanup()
