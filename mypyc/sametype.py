"""Same type check for RTypes."""

from mypyc.ops import (
    RType, RTypeVisitor, ObjectRType, UserRType, OptionalRType, IntRType, BoolRType, TupleRType,
    SequenceTupleRType, NoneRType, ListRType, DictRType, UnicodeRType
)


def is_same_type(a: RType, b: RType) -> bool:
    return a.accept(SameTypeVisitor(b))


class SameTypeVisitor(RTypeVisitor[bool]):
    def __init__(self, right: RType) -> None:
        self.right = right

    def visit_object_rtype(self, left: ObjectRType) -> bool:
        return isinstance(self.right, ObjectRType)

    def visit_user_rtype(self, left: UserRType) -> bool:
        return isinstance(self.right, UserRType) and left.name == self.right.name

    def visit_optional_rtype(self, left: OptionalRType) -> bool:
        return isinstance(self.right, OptionalRType) and is_same_type(left.value_type,
                                                                      self.right.value_type)

    def visit_int_rtype(self, left: IntRType) -> bool:
        return isinstance(self.right, IntRType)

    def visit_bool_rtype(self, left: BoolRType) -> bool:
        return isinstance(self.right, BoolRType)

    def visit_tuple_rtype(self, left: TupleRType) -> bool:
        return (isinstance(self.right, TupleRType)
            and len(self.right.types) == len(left.types)
            and all(is_same_type(t1, t2) for t1, t2 in zip(left.types, self.right.types)))

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
