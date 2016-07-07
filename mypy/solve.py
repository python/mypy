"""Type inference constraint solving"""

from typing import List, Dict

from mypy.types import Type, Void, NoneTyp, AnyType, ErrorType, UninhabitedType, TypeVarId
from mypy.constraints import Constraint, SUPERTYPE_OF
from mypy.join import join_types
from mypy.meet import meet_types
from mypy.subtypes import is_subtype

from mypy import experiments


def solve_constraints(vars: List[TypeVarId], constraints: List[Constraint],
                      strict: bool =True) -> List[Type]:
    """Solve type constraints.

    Return the best type(s) for type variables; each type can be None if the value of the variable
    could not be solved.

    If a variable has no constraints, if strict=True then arbitrarily
    pick NoneTyp as the value of the type variable.  If strict=False,
    pick AnyType.
    """
    # Collect a list of constraints for each type variable.
    cmap = {}  # type: Dict[TypeVarId, List[Constraint]]
    for con in constraints:
        a = cmap.get(con.type_var, [])  # type: List[Constraint]
        a.append(con)
        cmap[con.type_var] = a

    res = []  # type: List[Type]

    # Solve each type variable separately.
    for tvar in vars:
        bottom = None  # type: Type
        top = None  # type: Type

        # Process each constraint separately, and calculate the lower and upper
        # bounds based on constraints. Note that we assume that the constraint
        # targets do not have constraint references.
        for c in cmap.get(tvar, []):
            if c.op == SUPERTYPE_OF:
                if bottom is None:
                    bottom = c.target
                else:
                    bottom = join_types(bottom, c.target)
            else:
                if top is None:
                    top = c.target
                else:
                    top = meet_types(top, c.target)

        if isinstance(top, AnyType) or isinstance(bottom, AnyType):
            res.append(AnyType())
            continue
        elif bottom is None:
            if top:
                candidate = top
            else:
                # No constraints for type variable -- type 'None' is the most specific type.
                if strict:
                    if experiments.STRICT_OPTIONAL:
                        candidate = UninhabitedType()
                    else:
                        candidate = NoneTyp()
                else:
                    candidate = AnyType()
        elif top is None:
            candidate = bottom
        elif is_subtype(bottom, top):
            candidate = bottom
        else:
            candidate = None
        if isinstance(candidate, ErrorType):
            res.append(None)
        else:
            res.append(candidate)

    return res
