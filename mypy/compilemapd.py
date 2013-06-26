from typing import Undefined, List, Tuple, cast

from nodes import TypeInfo
from types import Instance, Type, TypeVar, AnyType


class MapPremise: pass


class MapExpr: pass


class AssertClass(MapPremise):
    i = Undefined(MapExpr)
    c = Undefined(TypeInfo)
    
    def __init__(self, i: MapExpr, c: TypeInfo) -> None:
        self.i = i
        self.c = c
    
    def __str__(self):
        return str(self.i) + ' = ' + self.c.name + '[...]'


class AssertDyn(MapPremise):
    i = Undefined(MapExpr)
    
    def __init__(self, i: MapExpr) -> None:
        self.i = i
    
    def __str__(self):
        return str(self.i) + ' = Any'


class AssertEq(MapPremise):
    i1 = Undefined(MapExpr)
    i2 = Undefined(MapExpr)
    
    def __init__(self, i1: MapExpr, i2: MapExpr) -> None:
        self.i1 = i1
        self.i2 = i2
    
    def __str__(self):
        return str(self.i1) + ' = ' + str(self.i2)


class TypeVarRef(MapExpr):
    n = 0
    
    def __init__(self, n: int) -> None:
        self.n = n
    
    def __str__(self):
        return str(self.n)


class TypeArgRef(MapExpr):
    base = Undefined(MapExpr)
    n = 0
    
    def __init__(self, base: MapExpr, n: int) -> None:
        self.base = base
        self.n = n
    
    def __str__(self):
        return str(self.base) + '.' + str(self.n)


class DefaultArg(MapExpr):
    def __str__(self):
        return 'd'


def compile_subclass_mapping(num_subtype_type_vars: int,
                             super_type: Instance) -> Tuple[List[MapPremise],
                                                            List[MapExpr]]:
    """Compile mapping from superclass to subclass type variables.

    Args:
      num_subtype_type_vars: number of type variables in subclass
      super_type:         definition of supertype; this may contain type
                          variable references
    """
    
    # TODO describe what's going on
    
    premises = find_eq_premises(super_type, None)
    exprs = [] # type: List[MapExpr]
    
    for i in range(1, num_subtype_type_vars + 1):
        paths = find_all_paths(i, super_type, None)
        if len(paths) == 0:
            exprs.append(DefaultArg())
        else:
            exprs.append(paths[0])
            if len(paths) > 1:
                # Multiple paths; make sure they are all the same.
                for j in range(1, len(paths)):
                    premises.append(AssertEq(paths[0], paths[j]))
    
    return premises, exprs  


def find_all_paths(tv: int, typ: Type, expr: MapExpr) -> List[MapExpr]:
    if isinstance(typ, TypeVar) and (cast(TypeVar, typ)).id == tv:
        return [expr]
    elif isinstance(typ, Instance) and (cast(Instance, typ)).args != []:
        inst = cast(Instance, typ)
        res = [] # type: List[MapExpr]
        for i in range(len(inst.args)):
            e = Undefined # type: MapExpr
            if not expr:
                e = TypeVarRef(i + 1)
            else:
                e = TypeArgRef(expr, i + 1)
            res += find_all_paths(tv, inst.args[i], e)
        return res
    else:
        return []


def find_eq_premises(typ: Type, expr: MapExpr) -> List[MapPremise]:
    if isinstance(typ, Instance):
        inst = cast(Instance, typ)
        res = [] # type: List[MapPremise]
        if expr:
            res.append(AssertClass(expr, inst.type))
        for i in range(len(inst.args)):
            e = Undefined # type: MapExpr
            if not expr:
                e = TypeVarRef(i + 1)
            else:
                e = TypeArgRef(expr, i + 1)
            res += find_eq_premises(inst.args[i], e)
        return res
    elif isinstance(typ, AnyType):
        return [AssertDyn(expr)]
    else:
        return []
