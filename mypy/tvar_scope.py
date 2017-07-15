from typing import Optional, Dict, Union
from mypy.types import TypeVarDef, TypeVarId
from mypy.nodes import TypeVarExpr, SymbolTableNode


class TypeVarScope:
    """Scope that holds bindings for type variables. Node fullname -> TypeVarDef."""

    def __init__(self,
                 parent: 'Optional[TypeVarScope]' = None,
                 is_class_scope: bool = False,
                 prohibited: 'Optional[TypeVarScope]' = None) -> None:
        """Initializer for TypeVarScope

        Parameters:
          parent: the outer scope for this scope
          is_class_scope: True if this represents a generic class
          prohibited: Type variables that aren't strictly in scope exactly,
                      but can't be bound because they're part of an outer class's scope.
        """
        self.scope = {}  # type: Dict[str, TypeVarDef]
        self.parent = parent
        self.func_id = 0
        self.class_id = 0
        self.is_class_scope = is_class_scope
        self.prohibited = prohibited
        if parent is not None:
            self.func_id = parent.func_id
            self.class_id = parent.class_id

    def get_function_scope(self) -> 'Optional[TypeVarScope]':
        """Get the nearest parent that's a function scope, not a class scope"""
        it = self  # type: Optional[TypeVarScope]
        while it is not None and it.is_class_scope:
            it = it.parent
        return it

    def allow_binding(self, fullname: str) -> bool:
        if fullname in self.scope:
            return False
        elif self.parent and not self.parent.allow_binding(fullname):
            return False
        elif self.prohibited and not self.prohibited.allow_binding(fullname):
            return False
        return True

    def method_frame(self) -> 'TypeVarScope':
        """A new scope frame for binding a method"""
        return TypeVarScope(self, False, None)

    def class_frame(self) -> 'TypeVarScope':
        """A new scope frame for binding a class. Prohibits *this* class's tvars"""
        return TypeVarScope(self.get_function_scope(), True, self)

    def bind(self, name: str, tvar_expr: TypeVarExpr) -> TypeVarDef:
        if self.is_class_scope:
            self.class_id += 1
            i = self.class_id
        else:
            self.func_id -= 1
            i = self.func_id
        tvar_def = TypeVarDef(
            name, i, values=tvar_expr.values,
            upper_bound=tvar_expr.upper_bound, variance=tvar_expr.variance,
            line=tvar_expr.line, column=tvar_expr.column)
        self.scope[tvar_expr.fullname()] = tvar_def
        return tvar_def

    def get_binding(self, item: Union[str, SymbolTableNode]) -> Optional[TypeVarDef]:
        fullname = item.fullname if isinstance(item, SymbolTableNode) else item
        assert fullname is not None
        if fullname in self.scope:
            return self.scope[fullname]
        elif self.parent is not None:
            return self.parent.get_binding(fullname)
        else:
            return None

    def __str__(self) -> str:
        me = ", ".join('{}: {}`{}'.format(k, v.name, v.id) for k, v in self.scope.items())
        if self.parent is None:
            return me
        return "{} <- {}".format(str(self.parent), me)
