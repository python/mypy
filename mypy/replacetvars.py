"""Type operations"""

from typing import cast

from mypy.lex import Token
from mypy.types import Type, AnyType, NoneTyp, TypeTranslator, TypeVarType, CallableType, TypeVarDef


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
        if t.id <= -90:
            return self.target_type
        else:
            return t


def rename_func_type_vars(typ: Type) -> Type:
    """Replace function type variables in a type with the target type."""
    return typ.accept(RenameFuncTypeVarsVisitor())


class RenameFuncTypeVarsVisitor(TypeTranslator):
    def visit_type_var(self, t: TypeVarType) -> Type:
        if -90 < t.id < 0:
            assert t.id > -90, t  # Guido
            # Offset type ID with 1000 so it will be erased
            return TypeVarType(t.name, t.id - 1000, t.values, t.upper_bound, t.variance, t.line)
        else:
            return t

    def visit_callable_type(self, t: CallableType) -> Type:
        result = cast(CallableType, super().visit_callable_type(t))
        variables = []
        for v in result.variables:
            if -90 < v.id < 0:
                assert v.id > -90, v  # Guido
                vv = TypeVarDef(v.name, v.id - 1000, v.values, v.upper_bound, v.variance, v.line)
                variables.append(vv)
            else:
                variables.append(v)
        result.variables = variables
        return result
