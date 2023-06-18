"""Type inference constraint solving"""

from __future__ import annotations

from typing import Iterable

from mypy.constraints import SUBTYPE_OF, SUPERTYPE_OF, Constraint, neg_op
from mypy.expandtype import expand_type
from mypy.graph_utils import prepare_sccs, strongly_connected_components, topsort
from mypy.join import join_types
from mypy.meet import meet_types
from mypy.subtypes import is_subtype
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
    remove_dups,
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
        solutions = {}
        for tv, cs in cmap.items():
            if not cs:
                continue
            lowers = [c.target for c in cs if c.op == SUPERTYPE_OF]
            uppers = [c.target for c in cs if c.op == SUBTYPE_OF]
            solutions[tv] = solve_one(lowers, uppers, [])

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
      * Find dependencies between type variables, group them in SCCs, and sort topologically
      * Check all SCC are intrinsically linear, we can't solve (express) T <: List[T]
      * Variables in leaf SCCs that don't have constant bounds are free (choose one per SCC)
      * Solve constraints iteratively starting from leafs, updating targets after each step.
    """
    extra_constraints = []
    for tvar in vars:
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
            # If all constrain targets in this SCC are type variables within the
            # same SCC then the only meaningful solution we can express, is that
            # each variable is equal to a new free variable. For example if we
            # have T <: S, S <: U, we deduce: T = S = U = <free>.
            if all(
                isinstance(c.target, TypeVarType) and c.target.id in vars
                for tv in scc
                for c in cmap[tv]
            ):
                # For convenience with current type application machinery, we randomly
                # choose one of the existing type variables in SCC and designate it as free
                # instead of defining a new type variable as a common solution.
                # TODO: be careful about upper bounds (or values) when introducing free vars.
                free_vars.append(sorted(scc, key=lambda x: x.raw_id)[0])

        # Flatten the SCCs that are independent, we can solve them together,
        # since we don't need to update any targets in between.
        batches = []
        for batch in raw_batches:
            next_bc = []
            for scc in batch:
                next_bc.extend(list(scc))
            batches.append(next_bc)

        solutions: dict[TypeVarId, Type | None] = {}
        for flat_batch in batches:
            solutions.update(solve_iteratively(flat_batch, cmap, free_vars))
        # We remove the solutions like T = T for free variables. This will indicate
        # to the apply function, that they should not be touched.
        # TODO: return list of free type variables explicitly, this logic is fragile
        # (but if we do, we need to be careful everything works in incremental modes).
        for tv in free_vars:
            if tv in solutions:
                del solutions[tv]
        return solutions
    return {}


def solve_iteratively(
    batch: list[TypeVarId], cmap: dict[TypeVarId, list[Constraint]], free_vars: list[TypeVarId]
) -> dict[TypeVarId, Type | None]:
    """Solve constraints sequentially, updating constraint targets after each step.

    We solve for type variables that appear in `batch`. If a constraint target is not constant
    (i.e. constraint looks like T :> F[S, ...]), we substitute solutions found so far in
    the target F[S, ...].  This way we can gradually solve for all variables in the batch taking
    one solvable variable at a time (i.e. such a variable that has at least one constant bound).

    Importantly, variables in free_vars are considered constants, so for example if we have just
    one initial constraint T <: List[S], we will have two SCCs {T} and {S}, then we first
    designate S as free, and therefore T = List[S] is a valid solution for T.
    """
    solutions = {}
    relevant_constraints = []
    for tv in batch:
        relevant_constraints.extend(cmap.get(tv, []))
    lowers, uppers = transitive_closure(batch, relevant_constraints)
    s_batch = set(batch)
    not_allowed_vars = [v for v in batch if v not in free_vars]
    while s_batch:
        for tv in s_batch:
            if any(not get_vars(l, not_allowed_vars) for l in lowers[tv]) or any(
                not get_vars(u, not_allowed_vars) for u in uppers[tv]
            ):
                solvable_tv = tv
                break
        else:
            break
        # Solve each solvable type variable separately.
        s_batch.remove(solvable_tv)
        result = solve_one(lowers[solvable_tv], uppers[solvable_tv], not_allowed_vars)
        solutions[solvable_tv] = result
        if result is None:
            # TODO: support backtracking lower/upper bound choices
            # (will require switching this function from iterative to recursive).
            continue
        # Update the (transitive) constraints if there is a solution.
        subs = {solvable_tv: result}
        lowers = {tv: {expand_type(l, subs) for l in lowers[tv]} for tv in lowers}
        uppers = {tv: {expand_type(u, subs) for u in uppers[tv]} for tv in uppers}
        for v in cmap:
            for c in cmap[v]:
                c.target = expand_type(c.target, subs)
    return solutions


def solve_one(
    lowers: Iterable[Type], uppers: Iterable[Type], not_allowed_vars: list[TypeVarId]
) -> Type | None:
    """Solve constraints by finding by using meets of upper bounds, and joins of lower bounds."""
    bottom: Type | None = None
    top: Type | None = None
    candidate: Type | None = None

    # Process each bound separately, and calculate the lower and upper
    # bounds based on constraints. Note that we assume that the constraint
    # targets do not have constraint references.
    for target in lowers:
        # There may be multiple steps needed to solve all vars within a
        # (linear) SCC. We ignore targets pointing to not yet solved vars.
        if get_vars(target, not_allowed_vars):
            continue
        if bottom is None:
            bottom = target
        else:
            if type_state.infer_unions:
                # This deviates from the general mypy semantics because
                # recursive types are union-heavy in 95% of cases.
                bottom = UnionType.make_union([bottom, target])
            else:
                bottom = join_types(bottom, target)

    for target in uppers:
        # Same as above.
        if get_vars(target, not_allowed_vars):
            continue
        if top is None:
            top = target
        else:
            top = meet_types(top, target)

    p_top = get_proper_type(top)
    p_bottom = get_proper_type(bottom)
    if isinstance(p_top, AnyType) or isinstance(p_bottom, AnyType):
        source_any = top if isinstance(p_top, AnyType) else bottom
        assert isinstance(source_any, ProperType) and isinstance(source_any, AnyType)
        return AnyType(TypeOfAny.from_another_any, source_any=source_any)
    elif bottom is None:
        if top:
            candidate = top
        else:
            # No constraints for type variable
            return None
    elif top is None:
        candidate = bottom
    elif is_subtype(bottom, top):
        candidate = bottom
    else:
        candidate = None
    return candidate


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


def transitive_closure(
    tvars: list[TypeVarId], constraints: list[Constraint]
) -> tuple[dict[TypeVarId, set[Type]], dict[TypeVarId, set[Type]]]:
    """Find transitive closure for given constraints on type variables.

    Transitive closure gives maximal set of lower/upper bounds for each type variable,
    such that we cannot deduce any further bounds by chaining other existing bounds.

    For example if we have initial constraints [T <: S, S <: U, U <: int], the transitive
    closure is given by:
      * {} <: T <: {S, U, int}
      * {T} <: S <: {U, int}
      * {T, S} <: U <: {int}
    """
    # TODO: merge propagate_constraints_for() into this function.
    # TODO: add secondary constraints here to make the algorithm complete.
    uppers: dict[TypeVarId, set[Type]] = {tv: set() for tv in tvars}
    lowers: dict[TypeVarId, set[Type]] = {tv: set() for tv in tvars}
    graph: set[tuple[TypeVarId, TypeVarId]] = set()

    # Prime the closure with the initial trivial values.
    for c in constraints:
        if isinstance(c.target, TypeVarType) and c.target.id in tvars:
            if c.op == SUBTYPE_OF:
                graph.add((c.type_var, c.target.id))
            else:
                graph.add((c.target.id, c.type_var))
        if c.op == SUBTYPE_OF:
            uppers[c.type_var].add(c.target)
        else:
            lowers[c.type_var].add(c.target)

    # At this stage we know that constant bounds have been propagated already, so we
    # only need to propagate linear constraints.
    for c in constraints:
        if isinstance(c.target, TypeVarType) and c.target.id in tvars:
            if c.op == SUBTYPE_OF:
                lower, upper = c.type_var, c.target.id
            else:
                lower, upper = c.target.id, c.type_var
            extras = {
                (l, u) for l in tvars for u in tvars if (l, lower) in graph and (upper, u) in graph
            }
            graph |= extras
            for u in tvars:
                if (upper, u) in graph:
                    lowers[u] |= lowers[lower]
            for l in tvars:
                if (l, lower) in graph:
                    uppers[l] |= uppers[upper]
    return lowers, uppers


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
