from __future__ import annotations

from mypyc.common import PROPSET_PREFIX
from mypyc.ir.ops import Register, Value
from mypyc.ir.rtypes import RInstance, RType, object_rprimitive


class AssignmentTarget:
    """Abstract base class for assignment targets during IR building."""

    type: RType = object_rprimitive


class AssignmentTargetRegister(AssignmentTarget):
    """Register as an assignment target.

    This is used for local variables and some temporaries.
    """

    def __init__(self, register: Register) -> None:
        self.register = register
        self.type = register.type

    def __repr__(self) -> str:
        return f"AssignmentTargetRegister({self.register.name})"


class AssignmentTargetIndex(AssignmentTarget):
    """base[index] as assignment target"""

    def __init__(self, base: Value, index: Value) -> None:
        self.base = base
        self.index = index
        # TODO: object_rprimitive won't be right for user-defined classes. Store the
        #       lvalue type in mypy and use a better type to avoid unneeded boxing.
        self.type = object_rprimitive

    def __repr__(self) -> str:
        return f"AssignmentTargetIndex({self.base!r}, {self.index!r})"


class AssignmentTargetAttr(AssignmentTarget):
    """obj.attr as assignment target"""

    def __init__(self, obj: Value, attr: str, can_borrow: bool = False) -> None:
        self.obj = obj
        self.attr = attr
        self.can_borrow = can_borrow
        if isinstance(obj.type, RInstance) and obj.type.class_ir.has_attr(attr):
            # Native attribute reference
            self.obj_type: RType = obj.type
            self.type = obj.type.attr_type(attr)
            # A property setter may accept a wider type than its getter returns,
            # so values assigned through it are coerced to the setter's argument type
            for ir in obj.type.class_ir.mro:
                setter = ir.method_decls.get(PROPSET_PREFIX + attr)
                if setter is not None:
                    if not setter.implicit:
                        self.type = setter.sig.args[1].type
                    break
        else:
            # Python attribute reference
            self.obj_type = object_rprimitive
            self.type = object_rprimitive

    def __repr__(self) -> str:
        can_borrow_str = ", can_borrow=True" if self.can_borrow else ""
        return f"AssignmentTargetAttr({self.obj!r}.{self.attr}{can_borrow_str})"


class AssignmentTargetTuple(AssignmentTarget):
    """x, ..., y as assignment target"""

    def __init__(self, items: list[AssignmentTarget], star_idx: int | None = None) -> None:
        self.items = items
        self.star_idx = star_idx

    def __repr__(self) -> str:
        return f"AssignmentTargetTuple({self.items}, {self.star_idx})"
