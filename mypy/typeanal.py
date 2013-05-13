"""Semantic analysis of types"""

from mypy.types import (
    Type, UnboundType, TypeVar, TupleType, Instance, Any, Callable, TypeVars,
    Void, NoneTyp, TypeVarDef, TypeVisitor
)
from mypy.typerepr import TypeVarRepr
from mypy.nodes import GDEF, TypeInfo, Context, SymbolTableNode, TVAR
from mypy import nodes


class TypeAnalyser(TypeVisitor<Type>):
    """Semantic analyzer for types."""

    func<SymbolTableNode(str, Context)> lookup
    func<void(str, Context)> fail
    
    void __init__(self, func<SymbolTableNode(str, Context)> lookup_func,
                  func<void(str, Context)> fail_func):
        self.lookup = lookup_func
        self.fail = fail_func
    
    Type visit_unbound_type(self, UnboundType t):
        sym = self.lookup(t.name, t)
        if sym is not None:
            if sym.kind == TVAR:
                if len(t.args) > 0:
                    self.fail('Type variable "{}" used with arguments'.format(
                        t.name), t)
                return TypeVar(t.name, sym.tvar_id, False, t.line,
                               TypeVarRepr(t.repr.components[0]))
            elif sym.node.fullname() == 'builtins.None':
                return Void()
            elif sym.node.fullname() == 'typing.Any':
                return Any()
            elif not isinstance(sym.node, TypeInfo):
                name = sym.fullname()
                if name is None:
                    name = sym.node.name()
                self.fail('Invalid type "{}"'.format(name), t)
                return t
            info = (TypeInfo)sym.node
            if len(t.args) > 0 and info.fullname() == 'builtins.tuple':
                return TupleType(self.anal_array(t.args), t.line, t.repr)
            elif len(t.args) != len(info.type_vars):
                if len(t.args) == 0:
                    # Implicit 'any' type arguments.
                    # TODO remove <Type> below
                    return Instance((TypeInfo)sym.node,
                                    <Type> [Any()] * len(info.type_vars),
                                    t.line, t.repr)
                # Invalid number of type parameters.
                n = len(((TypeInfo)sym.node).type_vars)
                s = '{} type arguments'.format(n)
                if n == 0:
                    s = 'no type arguments'
                elif n == 1:
                    s = '1 type argument'
                act = str(len(t.args))
                if act == '0':
                    act = 'none'
                self.fail('"{}" expects {}, but {} given'.format(
                    ((TypeInfo)sym.node).name(), s, act), t)
                return t
            else:
                # Ok; analyze arguments and construct Instance type. Upper
                # bounds are never present at this stage, as they are only used
                # during type inference.
                return Instance((TypeInfo)sym.node, self.anal_array(t.args),
                                t.line, t.repr)
        else:
            return t
    
    Type visit_any(self, Any t):
        return t
    
    Type visit_void(self, Void t):
        return t
    
    Type visit_none_type(self, NoneTyp t):
        return t
    
    Type visit_instance(self, Instance t):
        return t
    
    Type visit_type_var(self, TypeVar t):
        raise RuntimeError('TypeVar is already analysed')
    
    Type visit_callable(self, Callable t):
        res = Callable(self.anal_array(t.arg_types),
                       t.arg_kinds,
                       t.arg_names,
                       t.ret_type.accept(self),
                       t.is_type_obj(),
                       t.name,
                       self.anal_var_defs(t.variables),
                       self.anal_bound_vars(t.bound_vars), t.line, t.repr)
        
        return res
    
    Type visit_tuple_type(self, TupleType t):
        return TupleType(self.anal_array(t.items), t.line, t.repr)
    
    Type[] anal_array(self, Type[] a):
        Type[] res = []
        for t in a:
            res.append(t.accept(self))
        return res
    
    tuple<int, Type>[] anal_bound_vars(self, tuple<int, Type>[] a):
        res = <tuple<int, Type>> []
        for id, t in a:
            res.append((id, t.accept(self)))
        return res
    
    TypeVars anal_var_defs(self, TypeVars var_defs):
        TypeVarDef[] a = []
        for vd in var_defs.items:
            Type bound = None
            if vd.bound is not None:
                bound = vd.bound.accept(self)
            a.append(TypeVarDef(vd.name, vd.id, bound, vd.line, vd.repr))
        return TypeVars(a, var_defs.repr)
