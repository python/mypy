"""Type inference constraint solving"""

from __future__ import annotations

from collections import defaultdict

from mypy.constraints import SUPERTYPE_OF, Constraint, neg_op
from mypy.join import join_types
from mypy.meet import meet_types
from mypy.subtypes import is_subtype
from mypy.typeanal import remove_dups
from mypy.typeops import get_type_vars
from mypy.types import (
    AnyType,
    ProperType,
    Type,
    TypeOfAny,
    TypeVarId,
    UninhabitedType,
    UnionType,
    get_proper_type,
    ParamSpecType,
    TypeVarType,
)
from mypy.typestate import type_state


def remove_mirror(constraints: list[Constraint]) -> list[Constraint]:
    seen = set()
    result = []
    for c in constraints:
        if isinstance(c.target, TypeVarType):
            if (c.target.id, neg_op(c.op), c.type_var) in seen:
                continue
            seen.add((c.type_var, c.op, c.target.id))
        result.append(c)
    return result


def solve_constraints(
    vars: list[TypeVarId], constraints: list[Constraint], strict: bool = True,
    allow_polymorphic: bool = False,
) -> list[Type | None]:
    """Solve type constraints.

    Return the best type(s) for type variables; each type can be None if the value of the variable
    could not be solved.

    If a variable has no constraints, if strict=True then arbitrarily
    pick NoneType as the value of the type variable.  If strict=False,
    pick AnyType.
    """
    constraints = remove_dups(constraints)
    constraints = remove_mirror(constraints)

    # Collect a list of constraints for each type variable.
    cmap: dict[TypeVarId, list[Constraint]] = defaultdict(list)
    for con in constraints:
        cmap[con.type_var].append(con)

    res: list[Type | None] = []
    if allow_polymorphic:
        extra: set[TypeVarId] = set()
    else:
        extra = set(vars)

    # Solve each type variable separately.
    for tvar in vars:
        bottom: Type | None = None
        top: Type | None = None
        candidate: Type | None = None

        # Process each constraint separately, and calculate the lower and upper
        # bounds based on constraints. Note that we assume that the constraint
        # targets do not have constraint references.
        for c in cmap.get(tvar, []):
            if set(t.id for t in get_type_vars(c.target)) & ({tvar} | extra):
                if not isinstance(c.origin_type_var, ParamSpecType):
                    # TODO: figure out def [U] (U) -> U vs itself
                    continue
            if c.op == SUPERTYPE_OF:
                if bottom is None:
                    bottom = c.target
                else:
                    if type_state.infer_unions:
                        # This deviates from the general mypy semantics because
                        # recursive types are union-heavy in 95% of cases.
                        bottom = UnionType.make_union([bottom, c.target])
                    else:
                        bottom = join_types(bottom, c.target)
            else:
                if top is None:
                    top = c.target
                else:
                    top = meet_types(top, c.target)

        p_top = get_proper_type(top)
        p_bottom = get_proper_type(bottom)
        if isinstance(p_top, AnyType) or isinstance(p_bottom, AnyType):
            source_any = top if isinstance(p_top, AnyType) else bottom
            assert isinstance(source_any, ProperType) and isinstance(source_any, AnyType)
            res.append(AnyType(TypeOfAny.from_another_any, source_any=source_any))
            continue
        elif bottom is None:
            if top:
                candidate = top
            else:
                # No constraints for type variable -- 'UninhabitedType' is the most specific type.
                if strict:
                    candidate = UninhabitedType()
                    candidate.ambiguous = True
                else:
                    candidate = AnyType(TypeOfAny.special_form)
        elif top is None:
            candidate = bottom
        elif is_subtype(bottom, top):
            candidate = bottom
        else:
            candidate = None
        res.append(candidate)

    return res
