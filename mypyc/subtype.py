"""Subtype check for RTypes."""

from mypyc.ops import (
    RType, ROptional, RInstance, RPrimitive, RTuple, RVoid, RTypeVisitor,
    is_bool_rprimitive, is_int_rprimitive, is_tuple_rprimitive, none_rprimitive,
    is_object_rprimitive
)


def is_subtype(left: RType, right: RType) -> bool:
    if is_object_rprimitive(right):
        return True
    elif isinstance(right, ROptional):
        if is_subtype(left, none_rprimitive) or is_subtype(left, right.value_type):
            return True
    return left.accept(SubtypeVisitor(right))


class SubtypeVisitor(RTypeVisitor[bool]):
    """Is left a subtype of right?

    A few special cases such as right being 'object' are handled in
    is_subtype and don't need to be covered here.
    """

    def __init__(self, right: RType) -> None:
        self.right = right

    def visit_rinstance(self, left: RInstance) -> bool:
        return isinstance(self.right, RInstance) and self.right.class_ir in left.class_ir.mro

    def visit_roptional(self, left: ROptional) -> bool:
        return isinstance(self.right, ROptional) and is_subtype(left.value_type,
                                                                self.right.value_type)

    def visit_rprimitive(self, left: RPrimitive) -> bool:
        if is_bool_rprimitive(left) and is_int_rprimitive(self.right):
            return True
        return isinstance(self.right, RPrimitive) and left.name == self.right.name

    def visit_rtuple(self, left: RTuple) -> bool:
        if is_tuple_rprimitive(self.right):
            return True
        if isinstance(self.right, RTuple):
            return len(self.right.types) == len(left.types) and all(
                is_subtype(t1, t2) for t1, t2 in zip(left.types, self.right.types))
        return False

    def visit_rvoid(self, left: RVoid) -> bool:
        return isinstance(self.right, RVoid)
