"""Subtype check for RTypes."""

from mypyc.ops import (
    RType, ObjectRType, OptionalRType, NoneRType, UserRType, IntRType, BoolRType, TupleRType,
    SequenceTupleRType, ListRType, DictRType, UnicodeRType, RTypeVisitor
)


def is_subtype(left: RType, right: RType) -> bool:
    if isinstance(right, ObjectRType):
        return True
    elif isinstance(right, OptionalRType):
        if is_subtype(left, NoneRType()) or is_subtype(left, right.value_type):
            return True
    return left.accept(SubtypeVisitor(right))


class SubtypeVisitor(RTypeVisitor[bool]):
    """Is left a subtype of right?

    A few special cases such as right being 'object' are handled in
    is_subtype and don't need to be covered here.
    """

    def __init__(self, right: RType) -> None:
        self.right = right

    def visit_object_rtype(self, left: ObjectRType) -> bool:
        return False  # 'object' as right handled elsewhere

    def visit_user_rtype(self, left: UserRType) -> bool:
        # TODO: Inheritance
        return isinstance(self.right, UserRType) and self.right.name == left.name

    def visit_optional_rtype(self, left: OptionalRType) -> bool:
        return isinstance(self.right, OptionalRType) and is_subtype(left.value_type,
                                                                    self.right.value_type)

    def visit_int_rtype(self, left: IntRType) -> bool:
        return isinstance(self.right, IntRType)

    def visit_bool_rtype(self, left: BoolRType) -> bool:
        return isinstance(self.right, (BoolRType, IntRType))

    def visit_tuple_rtype(self, left: TupleRType) -> bool:
        if isinstance(self.right, SequenceTupleRType):
            return True
        if isinstance(self.right, TupleRType):
            return len(self.right.types) == len(left.types) and all(
                is_subtype(t1, t2) for t1, t2 in zip(left.types, self.right.types))
        return False

    def visit_sequence_tuple_rtype(self, left: SequenceTupleRType) -> bool:
        return isinstance(self.right, SequenceTupleRType)

    def visit_none_rtype(self, left: NoneRType) -> bool:
        return isinstance(self.right, NoneRType)

    def visit_list_rtype(self, left: ListRType) -> bool:
        return isinstance(self.right, ListRType)

    def visit_dict_rtype(self, left: DictRType) -> bool:
        return isinstance(self.right, DictRType)

    def visit_unicode_rtype(self, left: UnicodeRType) -> bool:
        return isinstance(self.right, UnicodeRType)
