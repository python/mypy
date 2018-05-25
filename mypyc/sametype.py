"""Same type check for RTypes."""

from mypyc.ops import (
    RType, RTypeVisitor, RInstance, ROptional, RPrimitive, RTuple
)


def is_same_type(a: RType, b: RType) -> bool:
    return a.accept(SameTypeVisitor(b))


class SameTypeVisitor(RTypeVisitor[bool]):
    def __init__(self, right: RType) -> None:
        self.right = right

    def visit_rinstance(self, left: RInstance) -> bool:
        return isinstance(self.right, RInstance) and left.name == self.right.name

    def visit_roptional(self, left: ROptional) -> bool:
        return isinstance(self.right, ROptional) and is_same_type(left.value_type,
                                                                  self.right.value_type)

    def visit_rprimitive(self, left: RPrimitive) -> bool:
        return isinstance(self.right, RPrimitive) and left.name == self.right.name

    def visit_rtuple(self, left: RTuple) -> bool:
        return (isinstance(self.right, RTuple)
            and len(self.right.types) == len(left.types)
            and all(is_same_type(t1, t2) for t1, t2 in zip(left.types, self.right.types)))
