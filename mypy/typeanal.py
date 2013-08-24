"""Semantic analysis of types"""

from typing import Undefined, Function, cast, List, Tuple

from mypy.types import (
    Type, UnboundType, TypeVar, TupleType, Instance, AnyType, Callable,
    Void, NoneTyp, TypeList, TypeVarDef, TypeVisitor
)
from mypy.typerepr import TypeVarRepr
from mypy.nodes import GDEF, TypeInfo, Context, SymbolTableNode, TVAR
from mypy.sametypes import is_same_type
from mypy import nodes


class TypeAnalyser(TypeVisitor[Type]):
    """Semantic analyzer for types (semantic analysis pass 2)."""

    def __init__(self, lookup_func: Function[[str, Context], SymbolTableNode],
                 fail_func: Function[[str, Context], None]) -> None:
        self.lookup = lookup_func
        self.fail = fail_func
    
    def visit_unbound_type(self, t: UnboundType) -> Type:
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
                return AnyType()
            elif sym.node.fullname() == 'typing.Tuple':
                return TupleType(self.anal_array(t.args))
            elif sym.node.fullname() == 'typing.Function':
                return self.analyze_function_type(t)
            elif not isinstance(sym.node, TypeInfo):
                name = sym.fullname
                if name is None:
                    name = sym.node.name()
                self.fail('Invalid type "{}"'.format(name), t)
                return t
            info = cast(TypeInfo, sym.node)
            if len(t.args) > 0 and info.fullname() == 'builtins.tuple':
                return TupleType(self.anal_array(t.args), t.line, t.repr)
            else:
                # Analyze arguments and construct Instance type. The
                # number of type arguments and their values are
                # checked only later, since we do not always know the
                # valid count at this point. Thus we may construct an
                # Instance with an invalid number of type arguments.
                return Instance(info, self.anal_array(t.args), t.line, t.repr)
        else:
            return t
    
    def visit_any(self, t: AnyType) -> Type:
        return t
    
    def visit_void(self, t: Void) -> Type:
        return t
    
    def visit_none_type(self, t: NoneTyp) -> Type:
        return t

    def visit_type_list(self, t: TypeList) -> Type:
        self.fail('Invalid type', t)
    
    def visit_instance(self, t: Instance) -> Type:
        return t
    
    def visit_type_var(self, t: TypeVar) -> Type:
        raise RuntimeError('TypeVar is already analysed')
    
    def visit_callable(self, t: Callable) -> Type:
        res = Callable(self.anal_array(t.arg_types),
                       t.arg_kinds,
                       t.arg_names,
                       t.ret_type.accept(self),
                       t.is_type_obj(),
                       t.name,
                       self.anal_var_defs(t.variables),
                       self.anal_bound_vars(t.bound_vars), t.line, t.repr)
        
        return res
    
    def visit_tuple_type(self, t: TupleType) -> Type:
        return TupleType(self.anal_array(t.items), t.line, t.repr)

    def analyze_function_type(self, t: UnboundType) -> Type:
        if len(t.args) != 2:
            self.fail('Invalid function type', t)
        if not isinstance(t.args[0], TypeList):
            self.fail('Invalid function type', t)
            return AnyType()
        args = (cast(TypeList, t.args[0])).items
        return Callable(self.anal_array(args),
                        [nodes.ARG_POS] * len(args), [None] * len(args),
                        ret_type=t.args[1].accept(self),
                        is_type_obj=False)
    
    def anal_array(self, a: List[Type]) -> List[Type]:
        res = List[Type]()
        for t in a:
            res.append(t.accept(self))
        return res
    
    def anal_bound_vars(self,
                        a: List[Tuple[int, Type]]) -> List[Tuple[int, Type]]:
        res = List[Tuple[int, Type]]()
        for id, t in a:
            res.append((id, t.accept(self)))
        return res
    
    def anal_var_defs(self, var_defs: List[TypeVarDef]) -> List[TypeVarDef]:
        a = List[TypeVarDef]()
        for vd in var_defs:
            a.append(TypeVarDef(vd.name, vd.id, self.anal_array(vd.values),
                                vd.line, vd.repr))
        return a


class TypeAnalyserPass3(TypeVisitor[None]):
    """Analyze type argument counts and values of generic types.

    This is semantic analysis pass 3 for types.

    Perform these operations:

     * Report error for invalid type argument counts, such as List[x, y].
     * Make implicit Any type argumenents explicit my modifying types
       in-place. For example, modify Foo into Foo[Any] if Foo expects a single
       type argument.
     * If a type variable has a value restriction, ensure that the value is
       valid. For example, reject IO[int] if the type argument must be str
       or bytes.

    We can't do this earlier than the third pass, since type argument counts
    are only determined in pass 2, and we have to support forward references
    to types.
    """

    def __init__(self, fail_func: Function[[str, Context], None]) -> None:
        self.fail = fail_func
    
    def visit_instance(self, t: Instance) -> None:
        info = t.type
        # Check type argument count.
        if len(t.args) != len(info.type_vars):
            if len(t.args) == 0:
                # Insert implicit 'Any' type arguments.
                t.args = [AnyType()] * len(info.type_vars)
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
        elif info.defn.type_vars:
            # Check type argument values.
            for arg, typevar in zip(t.args, info.defn.type_vars):
                if typevar.values:
                    if (not isinstance(arg, AnyType) and
                        not any(is_same_type(arg, value)
                                for value in typevar.values)):
                        self.fail(
                            'Invalid type argument value for "{}"'.format(
                                info.name()), t)
        for arg in t.args:
            arg.accept(self)

    def visit_callable(self, t: Callable) -> None:
        t.ret_type.accept(self)
        for arg_type in t.arg_types:
            arg_type.accept(self)
    
    def visit_tuple_type(self, t: TupleType) -> None:
        for item in t.items:
            item.accept(self)

    # Other kinds of type are trivial, since they are atomic (or invalid).

    def visit_unbound_type(self, t: UnboundType) -> None:
        pass
    
    def visit_any(self, t: AnyType) -> None:
        pass
    
    def visit_void(self, t: Void) -> None:
        pass
    
    def visit_none_type(self, t: NoneTyp) -> None:
        pass

    def visit_type_list(self, t: TypeList) -> None:
        self.fail('Invalid type', t)
    
    def visit_type_var(self, t: TypeVar) -> None:
        pass
