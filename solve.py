from mtypes import Typ, Void, NoneTyp, Any, ErrorType
from constraints import Constraint, SUPERTYPE_OF
from checker import BasicTypes
from join import join_types
from meet import meet_types
from subtypes import is_subtype


# Solve type constraints. Return lower bound for each type variable or
# nil if the variable could not be solved.
list<Typ> solve_constraints(list<int> vars, list<Constraint> constraints,
                            BasicTypes basic):
    # Collect a list of constraints for each type variable.
    dict<int, list<Constraint>> cmap = {}
    for con in constraints:
        a = cmap.get(con.type_var, [])
        a.append(con)
        cmap[con.type_var] = a
    
    list<Typ> res = []
    
    # Solve each type variable separately.
    for tvar in vars:
        Typ bottom = None
        Typ top = None
        
        # Process each contraint separely, and calculate the lower and upper
        # bounds based on constraints. Note that we assume that the contraint
        # targets do not have contraint references.
        for c in cmap.get(tvar, []):
            if c.op == SUPERTYPE_OF:
                if bottom is None:
                    bottom = c.target
                else:
                    bottom = join_types(bottom, c.target, basic)
            else:
                if top is None:
                    top = c.target
                else:
                    top = meet_types(top, c.target, basic)
        
        if top is None:
            if isinstance(bottom, Void):
                top = Void()
            else:
                top = basic.object
        
        if bottom is None:
            if isinstance(top, Void):
                bottom = Void()
            else:
                bottom = NoneTyp()
        
        if isinstance(top, Any) or isinstance(bottom, Any):
            top = Any()
            bottom = Any()
        
        # Pick the most specific type if it satisfies the constraints.
        if (not top or not bottom or is_subtype(bottom, top)) and (
                not isinstance(top, ErrorType) and
                not isinstance(bottom, ErrorType)):
            res.append(bottom)
        else:
            res.append(None)
    
    return res
