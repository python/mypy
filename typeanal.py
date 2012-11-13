from mtypes import (
    Typ, UnboundType, TypeVar, TupleType, Instance, Any, Callable, TypeVars,
    Void, NoneTyp, TypeVarDef, TypeVisitor
)
from typerepr import TypeVarRepr
from nodes import GDEF, TypeInfo, Context
from symtable import SymbolTableNode, TVAR


# Semantic analyzer for types.
class TypeAnalyser(TypeVisitor<Typ>):
    func<str, Context, SymbolTableNode> lookup
    func<str, Context, void> fail
    
    void __init__(self, func<str, Context, SymbolTableNode> lookup_func,
                  func<str, Context, void> fail_func):
        self.lookup = lookup_func
        self.fail = fail_func
    
    Typ visit_unbound_type(self, UnboundType t):
        if t.name == 'func':
            return self.anal_function_type(t)
        sym = self.lookup(t.name, t)
        if sym is not None:
            if sym.kind == TVAR:
                if len(t.args) > 0:
                    self.fail('Type variable "{}" used with arguments'.format(
                        t.name), t)
                return TypeVar(t.name, sym.tvar_id, False, t.line,
                               TypeVarRepr(t.repr.components[0]))
            elif sym.kind != GDEF or not isinstance(sym.node, TypeInfo):
                name = sym.full_name()
                if name is None:
                    name = sym.node.name()
                self.fail('Invalid type "{}"'.format(name), t)
                return t
            info = (TypeInfo)sym.node
            if len(t.args) > 0 and info.full_name() == 'builtins.tuple':
                return TupleType(self.anal_array(t.args), t.line, t.repr)
            elif len(t.args) != len(info.type_vars):
                if len(t.args) == 0:
                    # Implicit 'any' type arguments.
                    # TODO remove <Typ> below
                    return Instance((TypeInfo)sym.node,
                                    <Typ> [Any()] * len(info.type_vars),
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
    
    Callable anal_function_type(self, UnboundType t):
        list<Typ> a = []
        for at in t.args[:-1]:
            a.append(at.accept(self))
        return Callable(a, len(a), False, t.args[-1].accept(self), False, None,
                        TypeVars([]), [], t.line, t.repr)
    
    Typ visit_any(self, Any t):
        return t
    
    Typ visit_void(self, Void t):
        return t
    
    Typ visit_none_type(self, NoneTyp t):
        return t
    
    Typ visit_instance(self, Instance t):
        raise RuntimeError('Instance is already analysed')
    
    Typ visit_type_var(self, TypeVar t):
        raise RuntimeError('TypeVar is already analysed')
    
    Typ visit_callable(self, Callable t):
        res = Callable(self.anal_array(t.arg_types),
                       t.min_args,
                       t.is_var_arg,
                       t.ret_type.accept(self),
                       t.is_type_obj(),
                       t.name,
                       self.anal_var_defs(t.variables),
                       self.anal_bound_vars(t.bound_vars), t.line, t.repr)
        
        return res
    
    Typ visit_tuple_type(self, TupleType t):
        return TupleType(self.anal_array(t.items), t.line, t.repr)
    
    list<Typ> anal_array(self, list<Typ> a):
        list<Typ> res = []
        for t in a:
            res.append(t.accept(self))
        return res
    
    list<tuple<int, Typ>> anal_bound_vars(self, list<tuple<int, Typ>> a):
        list<tuple<int, Typ>> res = []
        for id, t in a:
            res.append((id, t.accept(self)))
        return res
    
    TypeVars anal_var_defs(self, TypeVars var_defs):
        list<TypeVarDef> a = []
        for vd in var_defs.items:
            Typ bound = None
            if vd.bound is not None:
                bound = vd.bound.accept(self)
            a.append(TypeVarDef(vd.name, vd.id, bound, vd.line, vd.repr))
        return TypeVars(a, var_defs.repr)
