"""Semantic analysis of types"""

from mypy.types import (
    Type, UnboundType, TypeVar, TupleType, Instance, Any, Callable, TypeVars,
    Void, NoneTyp, TypeList, TypeVarDef, TypeVisitor
)
from mypy.typerepr import TypeVarRepr
from mypy.nodes import GDEF, TypeInfo, Context, SymbolTableNode, TVAR
from mypy import nodes


class TypeAnalyser(TypeVisitor<Type>):
    """Semantic analyzer for types (semantic analysis pass 2)."""

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
                if t.repr:
                    rep = TypeVarRepr(t.repr.components[0])
                else:
                    rep = None
                return TypeVar(t.name, sym.tvar_id, False, t.line, rep)
            elif sym.node.fullname() == 'builtins.None':
                return Void()
            elif sym.node.fullname() == 'typing.Any':
                return Any()
            elif sym.node.fullname() == 'typing.Tuple':
                return TupleType(self.anal_array(t.args))
            elif sym.node.fullname() == 'typing.Function':
                return self.analyze_function_type(t)
            elif not isinstance(sym.node, TypeInfo):
                name = sym.fullname()
                if name is None:
                    name = sym.node.name()
                self.fail('Invalid type "{}"'.format(name), t)
                return t
            info = (TypeInfo)sym.node
            if len(t.args) > 0 and info.fullname() == 'builtins.tuple':
                return TupleType(self.anal_array(t.args), t.line, t.repr)
            else:
                # Analyze arguments and construct Instance type. The
                # number of type arguments is checked only later,
                # since we do not always know the valid count at this
                # point. Thus we may construct an Instance with an
                # invalid number of type arguments.
                return Instance(info, self.anal_array(t.args), t.line, t.repr)
        else:
            return t
    
    Type visit_any(self, Any t):
        return t
    
    Type visit_void(self, Void t):
        return t
    
    Type visit_none_type(self, NoneTyp t):
        return t

    Type visit_type_list(self, TypeList t):
        self.fail('Invalid type', t)
    
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

    Type analyze_function_type(self, UnboundType t):
        if len(t.args) != 2:
            self.fail('Invalid function type', t)
        if not isinstance(t.args[0], TypeList):
            self.fail('Invalid function type', t)
            return Any()
        args = ((TypeList)t.args[0]).items
        return Callable(self.anal_array(args),
                        [nodes.ARG_POS] * len(args),
                        <str> [None] * len(args),
                        ret_type=t.args[1].accept(self),
                        is_type_obj=False)
    
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


class TypeAnalyserPass3(TypeVisitor<void>):
    """Analyze type argument counts of types.

    This is semantic analysis pass 3 for types.

    Perform these operations:

     * Report error for invalid type argument counts, such as List[x, y].
     * Make implicit Any type argumenents explicit my modifying types
       in-place. For example, modify Foo into Foo[Any] if Foo expects a single
       type argument.

    We can't do this earlier than the third pass, since type argument counts
    are only determined in pass 2, and we have to support forward references
    to types.
    """

    void __init__(self, func<void(str, Context)> fail_func):
        self.fail = fail_func
    
    void visit_instance(self, Instance t):
        info = t.type
        if len(t.args) != len(info.type_vars):
            if len(t.args) == 0:
                # Implicit 'Any' type arguments.
                # TODO remove <Type> below
                t.args = <Type> [Any()] * len(info.type_vars)
                return
            # Invalid number of type parameters.
            n = len(info.type_vars)
            s = '{} type arguments'.format(n)
            if n == 0:
                s = 'no type arguments'
            elif n == 1:
                s = '1 type argument'
            act = str(len(t.args))
            if act == '0':
                act = 'none'
            self.fail('"{}" expects {}, but {} given'.format(
                info.name(), s, act), t)
        for arg in t.args:
            arg.accept(self)

    void visit_callable(self, Callable t):
        t.ret_type.accept(self)
        for arg_type in t.arg_types:
            arg_type.accept(self)
    
    void visit_tuple_type(self, TupleType t):
        for item in t.items:
            item.accept(self)

    # Other kinds of type are trivial, since they are atomic (or invalid).

    void visit_unbound_type(self, UnboundType t):
        pass
    
    void visit_any(self, Any t):
        pass
    
    void visit_void(self, Void t):
        pass
    
    void visit_none_type(self, NoneTyp t):
        pass

    void visit_type_list(self, TypeList t):
        self.fail('Invalid type', t)
    
    void visit_type_var(self, TypeVar t):
        pass
