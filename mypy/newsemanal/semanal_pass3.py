"""The semantic analyzer pass 3.

This pass checks that type argument counts are valid; for example, it
will reject Dict[int].  We don't do this in the second pass, since we
infer the type argument counts of classes during this pass, and it is
possible to refer to classes defined later in a file, which would not
have the type argument count set yet. This pass also recomputes the
method resolution order of each class, in case one of its bases
belongs to a module involved in an import loop.
"""

from collections import OrderedDict
from typing import Dict, List, Callable, Optional, Union, cast, Tuple

from mypy import message_registry, state
from mypy.nodes import (
    Node, Expression, MypyFile, FuncDef, Decorator, RefExpr, Context, TypeInfo, ClassDef,
    Block, TypedDictExpr, NamedTupleExpr, AssignmentStmt, IndexExpr, TypeAliasExpr, NameExpr,
    CallExpr, NewTypeExpr, ForStmt, WithStmt, CastExpr, TypeVarExpr, TypeApplication, Lvalue,
    TupleExpr, RevealExpr, SymbolTableNode, SymbolTable, Var, ARG_POS, OverloadedFuncDef,
    MDEF, TypeAlias
)
from mypy.types import (
    Type, Instance, AnyType, TypeOfAny, CallableType, TupleType, TypeVarType, TypedDictType,
    UnionType, TypeType, Overloaded, ForwardRef, TypeTranslator, function_type, LiteralType,
)
from mypy.errors import Errors, report_internal_error
from mypy.options import Options
from mypy.traverser import TraverserVisitor
from mypy.newsemanal.typeanal import TypeAnalyserPass3, collect_any_types
from mypy.typevars import has_no_typevars
from mypy.newsemanal.semanal_shared import PRIORITY_FORWARD_REF, PRIORITY_TYPEVAR_VALUES
from mypy.newsemanal.semanal import NewSemanticAnalyzer
from mypy.subtypes import is_subtype
from mypy.sametypes import is_same_type
from mypy.scope import Scope
from mypy.newsemanal.semanal_shared import SemanticAnalyzerCoreInterface


class SemanticAnalyzerPass3(TraverserVisitor, SemanticAnalyzerCoreInterface):
    """The third and final pass of semantic analysis.

    Check type argument counts and values of generic types, and perform some
    straightforward type inference.
    """

    def __init__(self, modules: Dict[str, MypyFile], errors: Errors,
                 sem: NewSemanticAnalyzer) -> None:
        self.modules = modules
        self.errors = errors
        self.sem = sem
        self.scope = Scope()
        # If True, process function definitions. If False, don't. This is used
        # for processing module top levels in fine-grained incremental mode.
        self.recurse_into_functions = True

    def visit_file(self, file_node: MypyFile, fnam: str, options: Options,
                   patches: List[Tuple[int, Callable[[], None]]]) -> None:
        self.recurse_into_functions = True
        self.options = options
        self.sem.options = options
        self.patches = patches
        self.is_typeshed_file = self.errors.is_typeshed_file(fnam)
        self.sem.cur_mod_id = file_node.fullname()
        self.cur_mod_node = file_node
        self.sem.globals = file_node.names

    def visit_class_def(self, tdef: ClassDef) -> None:
        # NamedTuple base classes are validated in check_namedtuple_classdef; we don't have to
        # check them again here.
        self.scope.enter_class(tdef.info)
        if not tdef.info.is_named_tuple:
            types = list(tdef.info.bases)  # type: List[Type]
            for tvar in tdef.type_vars:
                if tvar.upper_bound:
                    types.append(tvar.upper_bound)
                if tvar.values:
                    types.extend(tvar.values)
            if tdef.info.tuple_type:
                types.append(tdef.info.tuple_type)
            self.analyze_types(types, tdef.info)
            for type in tdef.info.bases:
                if tdef.info.is_protocol:
                    if not isinstance(type, Instance) or not type.type.is_protocol:
                        if type.type.fullname() != 'builtins.object':
                            self.fail('All bases of a protocol must be protocols', tdef)
        # Recompute MRO now that we have analyzed all modules, to pick
        # up superclasses of bases imported from other modules in an
        # import loop. (Only do so if we succeeded the first time.)
        if tdef.info.mro:
            tdef.info.mro = []  # Force recomputation
            self.sem.calculate_class_mro(tdef)
        super().visit_class_def(tdef)
        self.analyze_symbol_table(tdef.info.names)
        self.scope.leave()

    def visit_decorator(self, dec: Decorator) -> None:
        """Try to infer the type of the decorated function.

        This lets us resolve references to decorated functions during
        type checking when there are cyclic imports, as otherwise the
        type might not be available when we need it.

        This basically uses a simple special-purpose type inference
        engine just for decorators.
        """
        # Don't just call the super method since we don't unconditionally traverse the decorated
        # function.
        dec.var.accept(self)
        for decorator in dec.decorators:
            decorator.accept(self)
        if self.recurse_into_functions:
            dec.func.accept(self)
        if dec.var.is_property:
            # Decorators are expected to have a callable type (it's a little odd).
            if dec.func.type is None:
                dec.var.type = CallableType(
                    [AnyType(TypeOfAny.special_form)],
                    [ARG_POS],
                    [None],
                    AnyType(TypeOfAny.special_form),
                    self.builtin_type('function'),
                    name=dec.var.name())
            elif isinstance(dec.func.type, CallableType):
                dec.var.type = dec.func.type
                self.analyze(dec.var.type, dec.var)
            return
        decorator_preserves_type = True
        for expr in dec.decorators:
            preserve_type = False
            if isinstance(expr, RefExpr) and isinstance(expr.node, FuncDef):
                if expr.node.type and is_identity_signature(expr.node.type):
                    preserve_type = True
            if not preserve_type:
                decorator_preserves_type = False
                break
        if decorator_preserves_type:
            # No non-identity decorators left. We can trivially infer the type
            # of the function here.
            dec.var.type = function_type(dec.func, self.builtin_type('function'))
        if dec.decorators:
            return_type = calculate_return_type(dec.decorators[0])
            if return_type and isinstance(return_type, AnyType):
                # The outermost decorator will return Any so we know the type of the
                # decorated function.
                dec.var.type = AnyType(TypeOfAny.from_another_any, source_any=return_type)
            sig = find_fixed_callable_return(dec.decorators[0])
            if sig:
                # The outermost decorator always returns the same kind of function,
                # so we know that this is the type of the decorated function.
                orig_sig = function_type(dec.func, self.builtin_type('function'))
                sig.name = orig_sig.items()[0].name
                dec.var.type = sig
        self.analyze(dec.var.type, dec.var)

    def visit_assignment_stmt(self, s: AssignmentStmt) -> None:
        """Traverse the assignment statement.

        This includes the actual assignment and synthetic types
        resulted from this assignment (if any). Currently this includes
        NewType, TypedDict, NamedTuple, and TypeVar.
        """
        self.analyze(s.type, s)
        if isinstance(s.rvalue, IndexExpr) and isinstance(s.rvalue.analyzed, TypeAliasExpr):
            self.analyze(s.rvalue.analyzed.type, s.rvalue.analyzed, warn=True)
        if isinstance(s.rvalue, CallExpr):
            analyzed = s.rvalue.analyzed
            if isinstance(analyzed, TypeVarExpr):
                types = []
                if analyzed.upper_bound:
                    types.append(analyzed.upper_bound)
                if analyzed.values:
                    types.extend(analyzed.values)
                self.analyze_types(types, analyzed)
        if isinstance(s.lvalues[0], RefExpr) and isinstance(s.lvalues[0].node, Var):
            self.analyze(s.lvalues[0].node.type, s.lvalues[0].node)
        # Subclass attribute assignments with no type annotation should be
        # assumed to be classvar if overriding a declared classvar from the base
        # class.
        if (isinstance(s.lvalues[0], NameExpr) and s.lvalues[0].kind == MDEF
                and isinstance(s.lvalues[0].node, Var)):
            var = s.lvalues[0].node
            if var.info and var.is_inferred and not var.is_classvar:
                for base in var.info.mro[1:]:
                    tnode = base.names.get(var.name())
                    if (tnode is not None and isinstance(tnode.node, Var)
                            and tnode.node.is_classvar):
                        var.is_classvar = True
        super().visit_assignment_stmt(s)

    # Helpers

    def analyze(self, type: Optional[Type], node: Node,
                warn: bool = False) -> None:
        # Recursive type warnings are only emitted on type definition 'node's, marked by 'warn'
        # Flags appeared during analysis of 'type' are collected in this dict.
        indicator = {}  # type: Dict[str, bool]
        if type:
            analyzer = self.make_type_analyzer(indicator)
            type.accept(analyzer)
            if not (isinstance(node, TypeAlias) and node.no_args):
                # We skip bare type aliases like `A = List`, these
                # are still valid. In contrast, use/expansion points
                # like `x: A` will be flagged.
                self.check_for_omitted_generics(type)
            if analyzer.aliases_used:
                target = self.scope.current_target()
                self.cur_mod_node.alias_deps[target].update(analyzer.aliases_used)

    def analyze_types(self, types: List[Type], node: Node) -> None:
        # Similar to above but for nodes with multiple types.
        indicator = {}  # type: Dict[str, bool]
        for type in types:
            analyzer = self.make_type_analyzer(indicator)
            type.accept(analyzer)
            self.check_for_omitted_generics(type)
            if analyzer.aliases_used:
                target = self.scope.current_target()
                self.cur_mod_node.alias_deps[target].update(analyzer.aliases_used)

    def analyze_symbol_table(self, names: SymbolTable) -> None:
        """Analyze types in symbol table nodes only (shallow)."""
        for node in names.values():
            if isinstance(node.node, TypeAlias):
                self.analyze(node.node.target, node.node)

    def make_type_analyzer(self, indicator: Dict[str, bool]) -> TypeAnalyserPass3:
        return TypeAnalyserPass3(self,
                                 self.sem.plugin,
                                 self.options,
                                 self.is_typeshed_file,
                                 indicator,
                                 self.patches)

    def check_for_omitted_generics(self, typ: Type) -> None:
        if not self.options.disallow_any_generics or self.is_typeshed_file:
            return

        for t in collect_any_types(typ):
            if t.type_of_any == TypeOfAny.from_omitted_generics:
                self.fail(message_registry.BARE_GENERIC, t)

    def lookup_qualified(self, name: str, ctx: Context,
                         suppress_errors: bool = False) -> Optional[SymbolTableNode]:
        return self.sem.lookup_qualified(name, ctx, suppress_errors=suppress_errors)

    def lookup_fully_qualified(self, fullname: str) -> SymbolTableNode:
        return self.sem.lookup_fully_qualified(fullname)

    def fail(self, msg: str, ctx: Context, serious: bool = False, *,
             blocker: bool = False) -> None:
        self.sem.fail(msg, ctx, serious, blocker=blocker)

    def fail_blocker(self, msg: str, ctx: Context) -> None:
        self.fail(msg, ctx, blocker=True)

    def note(self, msg: str, ctx: Context) -> None:
        self.sem.note(msg, ctx)

    def builtin_type(self, name: str, args: Optional[List[Type]] = None) -> Instance:
        names = self.modules['builtins']
        sym = names.names[name]
        node = sym.node
        assert isinstance(node, TypeInfo)
        if args:
            # TODO: assert len(args) == len(node.defn.type_vars)
            return Instance(node, args)
        any_type = AnyType(TypeOfAny.special_form)
        return Instance(node, [any_type] * len(node.defn.type_vars))


def is_identity_signature(sig: Type) -> bool:
    """Is type a callable of form T -> T (where T is a type variable)?"""
    if isinstance(sig, CallableType) and sig.arg_kinds == [ARG_POS]:
        if isinstance(sig.arg_types[0], TypeVarType) and isinstance(sig.ret_type, TypeVarType):
            return sig.arg_types[0].id == sig.ret_type.id
    return False


def calculate_return_type(expr: Expression) -> Optional[Type]:
    """Return the return type if we can calculate it.

    This only uses information available during semantic analysis so this
    will sometimes return None because of insufficient information (as
    type inference hasn't run yet).
    """
    if isinstance(expr, RefExpr):
        if isinstance(expr.node, FuncDef):
            typ = expr.node.type
            if typ is None:
                # No signature -> default to Any.
                return AnyType(TypeOfAny.unannotated)
            # Explicit Any return?
            if isinstance(typ, CallableType):
                return typ.ret_type
            return None
        elif isinstance(expr.node, Var):
            return expr.node.type
    elif isinstance(expr, CallExpr):
        return calculate_return_type(expr.callee)
    return None


def find_fixed_callable_return(expr: Expression) -> Optional[CallableType]:
    if isinstance(expr, RefExpr):
        if isinstance(expr.node, FuncDef):
            typ = expr.node.type
            if typ:
                if isinstance(typ, CallableType) and has_no_typevars(typ.ret_type):
                    if isinstance(typ.ret_type, CallableType):
                        return typ.ret_type
    elif isinstance(expr, CallExpr):
        t = find_fixed_callable_return(expr.callee)
        if t:
            if isinstance(t.ret_type, CallableType):
                return t.ret_type
    return None
