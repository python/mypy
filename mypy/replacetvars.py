"""Type operations"""

from mypy.types import Type, AnyType, TypeTranslator, TypeVarType


def replace_type_vars(typ: Type, func_tvars: bool = True) -> Type:
    """Replace type variable references in a type with the Any type. If
    func_tvars is false, only replace instance type variables.
    """
    return typ.accept(ReplaceTypeVarsVisitor(func_tvars))


class ReplaceTypeVarsVisitor(TypeTranslator):
    # Only override type variable handling; otherwise perform an indentity
    # transformation.

    func_tvars = False

    def __init__(self, func_tvars: bool) -> None:
        self.func_tvars = func_tvars

    def visit_type_var(self, t: TypeVarType) -> Type:
        if t.id > 0 or self.func_tvars:
            if t.line is not None:
                return AnyType(t.line)
            else:
                return AnyType()
        else:
            return t


def replace_func_type_vars(typ: Type, target_type: Type) -> Type:
    """Replace function type variables in a type with the target type."""
    return typ.accept(ReplaceFuncTypeVarsVisitor(target_type))


class ReplaceFuncTypeVarsVisitor(TypeTranslator):
    def __init__(self, target_type: Type) -> None:
        self.target_type = target_type

    def visit_type_var(self, t: TypeVarType) -> Type:
        if t.id < 0:
            return self.target_type
        else:
            return t
