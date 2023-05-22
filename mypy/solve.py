"""Type inference constraint solving"""

from __future__ import annotations

from mypy.constraints import SUBTYPE_OF, SUPERTYPE_OF, Constraint, neg_op
from mypy.expandtype import expand_type
from mypy.graph_utils import prepare_sccs, strongly_connected_components, topsort
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
    TypeVarType,
    UninhabitedType,
    UnionType,
    get_proper_type,
)
from mypy.typestate import type_state


def solve_constraints(
    vars: list[TypeVarId],
    constraints: list[Constraint],
    strict: bool = True,
    allow_polymorphic: bool = False,
) -> list[Type | None]:
    """Solve type constraints.

    Return the best type(s) for type variables; each type can be None if the value of the variable
    could not be solved.

    If a variable has no constraints, if strict=True then arbitrarily
    pick NoneType as the value of the type variable.  If strict=False,
    pick AnyType.
    """
    if not vars:
        return []
    if allow_polymorphic:
        # Constraints like T :> S and S <: T are semantically the same, but they are
        # represented differently. Normalize the constraint list w.r.t this equivalence.
        constraints = normalize_constraints(constraints, vars)

    # Collect a list of constraints for each type variable.
    cmap: dict[TypeVarId, list[Constraint]] = {tv: [] for tv in vars}
    for con in constraints:
        if con.type_var in vars:
            cmap[con.type_var].append(con)

    if allow_polymorphic:
        solutions = solve_non_linear(vars, constraints, cmap)
    else:
        solutions = solve_iteratively([vars], cmap, vars)

    res: list[Type | None] = []
    for v in vars:
        if v in solutions:
            res.append(solutions[v])
        else:
            # No constraints for type variable -- 'UninhabitedType' is the most specific type.
            candidate: Type
            if strict:
                candidate = UninhabitedType()
                candidate.ambiguous = True
            else:
                candidate = AnyType(TypeOfAny.special_form)
            res.append(candidate)
    return res


def solve_non_linear(
    vars: list[TypeVarId], constraints: list[Constraint], cmap: dict[TypeVarId, list[Constraint]]
) -> dict[TypeVarId, Type | None]:
    """Solve set of constraints that may include non-linear ones, like T <: List[S].

    The whole algorithm consists of five steps:
      * Propagate via linear constraints to get all possible constraints for each variable
      * Find dependencies between type variables, group them in SCCs, and sor topologically
      * Check all SCC are intrinsically linear, it is impossible to solve T <: List[T]
      * Variables in leaf SCCs that don't have constant bounds are free (choose one per SCC)
      * Solve constraints iteratively starting from leafs, updating targets after each step.
    """
    extra_constraints = []
    for tvar in vars:
        # TODO: support iteratively inferring secondary constraints like
        # Sequence[T] <: S <: Sequence[U] => T <: U
        extra_constraints.extend(propagate_constraints_for(tvar, SUBTYPE_OF, cmap))
        extra_constraints.extend(propagate_constraints_for(tvar, SUPERTYPE_OF, cmap))
    constraints += remove_dups(extra_constraints)

    # Recompute constraint map after propagating.
    cmap = {tv: [] for tv in vars}
    for con in constraints:
        if con.type_var in vars:
            cmap[con.type_var].append(con)

    dmap = compute_dependencies(cmap)
    sccs = list(strongly_connected_components(set(vars), dmap))
    if all(check_linear(scc, cmap) for scc in sccs):
        raw_batches = list(topsort(prepare_sccs(sccs, dmap)))
        leafs = raw_batches[0]
        free_vars = []
        for scc in leafs:
            if all(
                isinstance(c.target, TypeVarType) and c.target.id in vars
                for tv in scc
                for c in cmap[tv]
            ):
                free_vars.append(next(tv for tv in scc))

        # Flatten the SCCs that are independent, we can solve them together,
        # since we don't need to update any targets in between.
        batches = []
        for batch in raw_batches:
            next_bc = []
            for scc in batch:
                next_bc.extend(list(scc))
            batches.append(next_bc)

        solutions = solve_iteratively(batches, cmap, free_vars)
        # We remove the solutions like T = T for free variables. This will indicate
        # to the apply function, that they should not be touched.
        for tv in free_vars:
            if tv in solutions:
                del solutions[tv]
        return solutions
    return {}


def solve_iteratively(
    batches: list[list[TypeVarId]],
    cmap: dict[TypeVarId, list[Constraint]],
    free_vars: list[TypeVarId],
) -> dict[TypeVarId, Type | None]:
    """Solve constraints for type variables sequentially, updating targets after each step."""
    solutions: dict[TypeVarId, Type | None] = {}
    for batch in batches:
        tmap = solve_once(batch, cmap, free_vars)
        if not tmap:
            continue
        for v in cmap:
            for c in cmap[v]:
                c.target = expand_type(
                    c.target, {k: v for (k, v) in tmap.items() if v is not None}
                )
        solutions.update(tmap)
    return solutions


def solve_once(
    vars: list[TypeVarId], cmap: dict[TypeVarId, list[Constraint]], free_vars: list[TypeVarId]
) -> dict[TypeVarId, Type | None]:
    """Solve constraints by finding by using meets of upper bounds, and joins of lower bounds."""
    res: dict[TypeVarId, Type | None] = {}
    # Solve each type variable separately.
    for tvar in vars:
        bottom: Type | None = None
        top: Type | None = None
        candidate: Type | None = None

        # Process each constraint separately, and calculate the lower and upper
        # bounds based on constraints. Note that we assume that the constraint
        # targets do not have constraint references.
        for c in cmap.get(tvar, []):
            if get_vars(c.target, [v for v in vars if v not in free_vars]):
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
            res[tvar] = AnyType(TypeOfAny.from_another_any, source_any=source_any)
            continue
        elif bottom is None:
            if top:
                candidate = top
            else:
                # No constraints for type variable
                continue
        elif top is None:
            candidate = bottom
        elif is_subtype(bottom, top):
            candidate = bottom
        else:
            candidate = None
        res[tvar] = candidate
    return res


def normalize_constraints(
    constraints: list[Constraint], vars: list[TypeVarId]
) -> list[Constraint]:
    """Normalize list of constraints (to simplify life for the non-linear solver).

     This includes two things currently:
       * Complement T :> S by S <: T
       * Remove strict duplicates
     """
    res = constraints.copy()
    for c in constraints:
        if isinstance(c.target, TypeVarType):
            res.append(Constraint(c.target, neg_op(c.op), c.origin_type_var))
    return [c for c in remove_dups(constraints) if c.type_var in vars]


def propagate_constraints_for(
    var: TypeVarId, direction: int, cmap: dict[TypeVarId, list[Constraint]]
) -> list[Constraint]:
    """Propagate via linear constraints to get additional constraints for `var`.

    For example if we have constraints:
        [T <: int, S <: T, S :> str]
    we can add two more
        [S <: int, T :> str]
    """
    extra_constraints = []
    seen = set()
    front = [var]
    if cmap[var]:
        var_def = cmap[var][0].origin_type_var
    else:
        return []
    while front:
        tv = front.pop(0)
        for c in cmap[tv]:
            if (
                isinstance(c.target, TypeVarType)
                and c.target.id not in seen
                and c.target.id in cmap
                and c.op == direction
            ):
                front.append(c.target.id)
                seen.add(c.target.id)
            elif c.op == direction:
                new_c = Constraint(var_def, direction, c.target)
                if new_c not in cmap[var]:
                    extra_constraints.append(new_c)
    return extra_constraints


def compute_dependencies(
    cmap: dict[TypeVarId, list[Constraint]]
) -> dict[TypeVarId, list[TypeVarId]]:
    """Compute dependencies between type variables induced by constraints.

    If we have a constraint like T <: List[S], we say that T depends on S, since
    we will need to solve for S first before we can solve for T.
    """
    res = {}
    vars = list(cmap.keys())
    for tv in cmap:
        deps = set()
        for c in cmap[tv]:
            deps |= get_vars(c.target, vars)
        res[tv] = list(deps)
    return res


def check_linear(scc: set[TypeVarId], cmap: dict[TypeVarId, list[Constraint]]) -> bool:
    """Check there are only linear constraints between type variables in SCC.

    Linear are constraints like T <: S (while T <: F[S] are non-linear).
    """
    for tv in scc:
        if any(
            get_vars(c.target, list(scc)) and not isinstance(c.target, TypeVarType)
            for c in cmap[tv]
        ):
            return False
    return True


def get_vars(target: Type, vars: list[TypeVarId]) -> set[TypeVarId]:
    """Find type variables for which we are solving in a target type."""
    return {tv.id for tv in get_type_vars(target)} & set(vars)
