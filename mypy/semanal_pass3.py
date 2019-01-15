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
from mypy.typeanal import TypeAnalyserPass3, collect_any_types
from mypy.typevars import has_no_typevars
from mypy.semanal_shared import PRIORITY_FORWARD_REF, PRIORITY_TYPEVAR_VALUES
from mypy.semanal import SemanticAnalyzerPass2
from mypy.subtypes import is_subtype
from mypy.sametypes import is_same_type
from mypy.scope import Scope
from mypy.semanal_shared import SemanticAnalyzerCoreInterface


class SemanticAnalyzerPass3(TraverserVisitor, SemanticAnalyzerCoreInterface):
    """The third and final pass of semantic analysis.

    Check type argument counts and values of generic types, and perform some
    straightforward type inference.
    """

    def __init__(self, modules: Dict[str, MypyFile], errors: Errors,
                 sem: SemanticAnalyzerPass2) -> None:
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
        self.errors.set_file(fnam, file_node.fullname(), scope=self.scope)
        self.options = options
        self.sem.options = options
        self.patches = patches
        self.is_typeshed_file = self.errors.is_typeshed_file(fnam)
        self.sem.cur_mod_id = file_node.fullname()
        self.cur_mod_node = file_node
        self.sem.globals = file_node.names
        with state.strict_optional_set(options.strict_optional):
            self.scope.enter_file(file_node.fullname())
            self.update_imported_vars()
            self.accept(file_node)
            self.analyze_symbol_table(file_node.names)
            self.scope.leave()
        del self.cur_mod_node
        self.patches = []

    def update_imported_vars(self) -> None:
        """Update nodes for imported names, if they got updated from Var to TypeInfo or TypeAlias.

        This is a simple _band-aid_ fix for "Invalid type" error in import cycles where type
        aliases, named tuples, or typed dicts appear. The root cause is that during first pass
        definitions like:

            A = List[int]

        are seen by mypy as variables, because it doesn't know yet that `List` refers to a type.
        In the second pass, such `Var` is replaced with a `TypeAlias`. But in import cycle,
        import of `A` will still refer to the old `Var` node. Therefore we need to update it.

        Note that this is a partial fix that only fixes the "Invalid type" error when a type alias
        etc. appears in type context. This doesn't fix errors (e.g. "Cannot determine type of A")
        that may appear if the type alias etc. appear in runtime context.

        The motivation for partial fix is two-fold:
          * The "Invalid type" error often appears in stub files (especially for large
            libraries/frameworks) where we have more import cycles, but no runtime
            context at all.
          * Ideally we should refactor semantic analysis to have deferred nodes, and process
            them in smaller passes when there is more info (like we do in type checking phase).
            But this is _much_ harder since this requires a large refactoring. Also an alternative
            fix of updating node of every `NameExpr` and `MemberExpr` in third pass is costly
            from performance point of view, and still nontrivial.
        """
        for sym in self.cur_mod_node.names.values():
            if sym and isinstance(sym.node, Var):
                fullname = sym.node.fullname()
                if '.' not in fullname:
                    continue
                mod_name, _, name = fullname.rpartition('.')
                if mod_name not in self.sem.modules:
                    continue
                if mod_name != self.sem.cur_mod_id:  # imported
                    new_sym = self.sem.modules[mod_name].names.get(name)
                    if new_sym and isinstance(new_sym.node, (TypeInfo, TypeAlias)):
                        # This Var was replaced with a class (like named tuple)
                        # or alias, update this.
                        sym.node = new_sym.node

    def refresh_partial(self, node: Union[MypyFile, FuncDef, OverloadedFuncDef],
                        patches: List[Tuple[int, Callable[[], None]]]) -> None:
        """Refresh a stale target in fine-grained incremental mode."""
        self.options = self.sem.options
        self.patches = patches
        if isinstance(node, MypyFile):
            self.recurse_into_functions = False
            self.refresh_top_level(node)
        else:
            self.recurse_into_functions = True
            self.accept(node)
        self.patches = []

    def refresh_top_level(self, file_node: MypyFile) -> None:
        """Reanalyze a stale module top-level in fine-grained incremental mode."""
        for d in file_node.defs:
            self.accept(d)
        self.analyze_symbol_table(file_node.names)

    def accept(self, node: Node) -> None:
        try:
            node.accept(self)
        except Exception as err:
            report_internal_error(err, self.errors.file, node.line, self.errors, self.options)

    def visit_block(self, b: Block) -> None:
        if b.is_unreachable:
            return
        super().visit_block(b)

    def visit_func_def(self, fdef: FuncDef) -> None:
        if not self.recurse_into_functions:
            return
        with self.scope.function_scope(fdef):
            self.analyze(fdef.type, fdef)
            super().visit_func_def(fdef)

    def visit_overloaded_func_def(self, fdef: OverloadedFuncDef) -> None:
        if not self.recurse_into_functions:
            return
        with self.scope.function_scope(fdef):
            self.analyze(fdef.type, fdef)
            super().visit_overloaded_func_def(fdef)

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
        if tdef.analyzed is not None:
            # Also check synthetic types associated with this ClassDef.
            # Currently these are TypedDict, and NamedTuple.
            if isinstance(tdef.analyzed, TypedDictExpr):
                self.analyze(tdef.analyzed.info.typeddict_type, tdef.analyzed, warn=True)
            elif isinstance(tdef.analyzed, NamedTupleExpr):
                self.analyze(tdef.analyzed.info.tuple_type, tdef.analyzed, warn=True)
                self.analyze_synthetic_info(tdef.analyzed.info)
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
            if isinstance(analyzed, NewTypeExpr):
                self.analyze(analyzed.old_type, analyzed)
                if analyzed.info:
                    # Currently NewTypes only have __init__, but to be future proof,
                    # we analyze all symbols.
                    self.analyze_synthetic_info(analyzed.info)
                if analyzed.info and analyzed.info.mro:
                    analyzed.info.mro = []  # Force recomputation
                    self.sem.calculate_class_mro(analyzed.info.defn)
            if isinstance(analyzed, TypeVarExpr):
                types = []
                if analyzed.upper_bound:
                    types.append(analyzed.upper_bound)
                if analyzed.values:
                    types.extend(analyzed.values)
                self.analyze_types(types, analyzed)
            if isinstance(analyzed, TypedDictExpr):
                self.analyze(analyzed.info.typeddict_type, analyzed, warn=True)
            if isinstance(analyzed, NamedTupleExpr):
                self.analyze(analyzed.info.tuple_type, analyzed, warn=True)
                self.analyze_synthetic_info(analyzed.info)
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

    def visit_for_stmt(self, s: ForStmt) -> None:
        self.analyze(s.index_type, s)
        super().visit_for_stmt(s)

    def visit_with_stmt(self, s: WithStmt) -> None:
        self.analyze(s.target_type, s)
        super().visit_with_stmt(s)

    def visit_cast_expr(self, e: CastExpr) -> None:
        self.analyze(e.type, e)
        super().visit_cast_expr(e)

    def visit_reveal_expr(self, e: RevealExpr) -> None:
        super().visit_reveal_expr(e)

    def visit_type_application(self, e: TypeApplication) -> None:
        for type in e.types:
            self.analyze(type, e)
        super().visit_type_application(e)

    # Helpers

    def perform_transform(self, node: Node, transform: Callable[[Type], Type]) -> None:
        """Apply transform to all types associated with node."""
        if isinstance(node, ForStmt):
            if node.index_type:
                node.index_type = transform(node.index_type)
            self.transform_types_in_lvalue(node.index, transform)
        if isinstance(node, WithStmt):
            if node.target_type:
                node.target_type = transform(node.target_type)
            for n in node.target:
                if isinstance(n, NameExpr) and isinstance(n.node, Var) and n.node.type:
                    n.node.type = transform(n.node.type)
        if isinstance(node, (FuncDef, OverloadedFuncDef, CastExpr, AssignmentStmt,
                             TypeAliasExpr, Var)):
            assert node.type, "Scheduled patch for non-existent type"
            node.type = transform(node.type)
        if isinstance(node, TypeAlias):
            node.target = transform(node.target)
        if isinstance(node, NewTypeExpr):
            assert node.old_type, "Scheduled patch for non-existent type"
            node.old_type = transform(node.old_type)
            if node.info:
                new_bases = []  # type: List[Instance]
                for b in node.info.bases:
                    new_b = transform(b)
                    # TODO: this code can be combined with code in second pass.
                    if isinstance(new_b, Instance):
                        new_bases.append(new_b)
                    elif isinstance(new_b, TupleType):
                        new_bases.append(new_b.fallback)
                    else:
                        self.fail("Argument 2 to NewType(...) must be subclassable"
                                  " (got {})".format(new_b), node)
                        new_bases.append(self.builtin_type('object'))
                node.info.bases = new_bases
        if isinstance(node, TypeVarExpr):
            if node.upper_bound:
                node.upper_bound = transform(node.upper_bound)
            if node.values:
                node.values = [transform(v) for v in node.values]
        if isinstance(node, TypedDictExpr):
            assert node.info.typeddict_type, "Scheduled patch for non-existent type"
            node.info.typeddict_type = cast(TypedDictType,
                                            transform(node.info.typeddict_type))
        if isinstance(node, NamedTupleExpr):
            assert node.info.tuple_type, "Scheduled patch for non-existent type"
            node.info.tuple_type = cast(TupleType,
                                        transform(node.info.tuple_type))
        if isinstance(node, TypeApplication):
            node.types = [transform(t) for t in node.types]
        if isinstance(node, TypeInfo):
            for tvar in node.defn.type_vars:
                if tvar.upper_bound:
                    tvar.upper_bound = transform(tvar.upper_bound)
                if tvar.values:
                    tvar.values = [transform(v) for v in tvar.values]
            new_bases = []
            for base in node.bases:
                new_base = transform(base)
                if isinstance(new_base, Instance):
                    new_bases.append(new_base)
                else:
                    # Don't fix the NamedTuple bases, they are Instance's intentionally.
                    # Patch the 'args' just in case, although generic tuple types are
                    # not supported yet.
                    alt_base = Instance(base.type, [transform(a) for a in base.args])
                    new_bases.append(alt_base)
            node.bases = new_bases
            if node.tuple_type:
                new_tuple_type = transform(node.tuple_type)
                assert isinstance(new_tuple_type, TupleType)
                node.tuple_type = new_tuple_type

    def transform_types_in_lvalue(self, lvalue: Lvalue,
                                  transform: Callable[[Type], Type]) -> None:
        if isinstance(lvalue, RefExpr):
            if isinstance(lvalue.node, Var):
                var = lvalue.node
                if var.type:
                    var.type = transform(var.type)
        elif isinstance(lvalue, TupleExpr):
            for item in lvalue.items:
                self.transform_types_in_lvalue(item, transform)

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
            self.generate_type_patches(node, indicator, warn)
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
        self.generate_type_patches(node, indicator, warn=False)

    def analyze_symbol_table(self, names: SymbolTable) -> None:
        """Analyze types in symbol table nodes only (shallow)."""
        for node in names.values():
            if isinstance(node.node, TypeAlias):
                self.analyze(node.node.target, node.node)

    def make_scoped_patch(self, fn: Callable[[], None]) -> Callable[[], None]:
        saved_scope = self.scope.save()

        def patch() -> None:
            with self.scope.saved_scope(saved_scope):
                fn()
        return patch

    def generate_type_patches(self,
                              node: Node,
                              indicator: Dict[str, bool],
                              warn: bool) -> None:
        if indicator.get('forward') or indicator.get('synthetic'):
            def patch() -> None:
                self.perform_transform(node,
                    lambda tp: tp.accept(ForwardReferenceResolver(self.fail,
                                                                  node, warn)))
            self.patches.append((PRIORITY_FORWARD_REF, self.make_scoped_patch(patch)))
        if indicator.get('typevar'):
            def patch2() -> None:
                self.perform_transform(node,
                    lambda tp: tp.accept(TypeVariableChecker(self.fail)))

            self.patches.append((PRIORITY_TYPEVAR_VALUES, self.make_scoped_patch(patch2)))

    def analyze_synthetic_info(self, info: TypeInfo) -> None:
        # Similar to above but for nodes with synthetic TypeInfos (NamedTuple and NewType).
        for name in info.names:
            sym = info.names[name]
            if isinstance(sym.node, (FuncDef, Decorator)):
                # Since we are analyzing a synthetic type info, the methods there
                # are not real independent targets, and should be processed when
                # the enclosing synthetic type is processed.
                old_recurse = self.recurse_into_functions
                self.recurse_into_functions = True
                self.accept(sym.node)
                self.recurse_into_functions = old_recurse
            if isinstance(sym.node, Var):
                self.analyze(sym.node.type, sym.node)

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

    def dereference_module_cross_ref(
            self, node: Optional[SymbolTableNode]) -> Optional[SymbolTableNode]:
        return self.sem.dereference_module_cross_ref(node)

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


class ForwardReferenceResolver(TypeTranslator):
    """Visitor to replace previously detected forward reference to synthetic types.

    This is similar to TypeTranslator but tracks visited nodes to avoid
    infinite recursion on potentially circular (self- or mutually-referential) types.
    This visitor:
    * Fixes forward references by unwrapping the linked type.
    * Generates errors for unsupported type recursion and breaks recursion by resolving
      recursive back references to Any types.
    * Replaces instance types generated from unanalyzed NamedTuple and TypedDict class syntax
      found in first pass with analyzed TupleType and TypedDictType.
    """
    def __init__(self, fail: Callable[[str, Context], None],
                 start: Union[Node, SymbolTableNode], warn: bool) -> None:
        self.seen = []  # type: List[Type]
        self.fail = fail
        self.start = start
        self.warn = warn

    def check_recursion(self, t: Type) -> bool:
        if any(t is s for s in self.seen):
            if self.warn:
                assert isinstance(self.start, Node), "Internal error: invalid error context"
                self.fail('Recursive types not fully supported yet,'
                          ' nested types replaced with "Any"', self.start)
            return True
        self.seen.append(t)
        return False

    def visit_forwardref_type(self, t: ForwardRef) -> Type:
        """This visitor method tracks situations like this:

            x: A  # This type is not yet known and therefore wrapped in ForwardRef,
                  # its content is updated in SemanticAnalyzerPass3, now we need to unwrap
                  # this type.
            A = NewType('A', int)
        """
        assert t.resolved, 'Internal error: Unresolved forward reference: {}'.format(
            t.unbound.name)
        return t.resolved.accept(self)

    def visit_instance(self, t: Instance, from_fallback: bool = False) -> Type:
        """This visitor method tracks situations like this:

               x: A  # When analyzing this type we will get an Instance from SemanticAnalyzerPass1.
                     # Now we need to update this to actual analyzed TupleType.
               class A(NamedTuple):
                   attr: str

        If from_fallback is True, then we always return an Instance type. This is needed
        since TupleType and TypedDictType fallbacks are always instances.
        """
        info = t.type
        # Special case, analyzed bases transformed the type into TupleType.
        if info.tuple_type and not from_fallback:
            items = [it.accept(self) for it in info.tuple_type.items]
            info.tuple_type.items = items
            return TupleType(items, Instance(info, []))
        # Update forward Instances to corresponding analyzed NamedTuples.
        if info.replaced and info.replaced.tuple_type:
            tp = info.replaced.tuple_type
            if self.check_recursion(tp):
                # The key idea is that when we recursively return to a type already traversed,
                # then we break the cycle and put AnyType as a leaf.
                return AnyType(TypeOfAny.from_error)
            return tp.copy_modified(fallback=Instance(info.replaced, [],
                                                      line=t.line)).accept(self)
        # Same as above but for TypedDicts.
        if info.replaced and info.replaced.typeddict_type:
            td = info.replaced.typeddict_type
            if self.check_recursion(td):
                # We also break the cycles for TypedDicts as explained above for NamedTuples.
                return AnyType(TypeOfAny.from_error)
            return td.copy_modified(fallback=Instance(info.replaced, [],
                                                      line=t.line)).accept(self)
        if self.check_recursion(t):
            # We also need to break a potential cycle with normal (non-synthetic) instance types.
            return Instance(t.type, [AnyType(TypeOfAny.from_error)] * len(t.type.defn.type_vars),
                            line=t.line)
        return super().visit_instance(t)

    def visit_type_var(self, t: TypeVarType) -> Type:
        if self.check_recursion(t):
            return AnyType(TypeOfAny.from_error)
        if t.upper_bound:
            t.upper_bound = t.upper_bound.accept(self)
        if t.values:
            t.values = [v.accept(self) for v in t.values]
        return t

    def visit_callable_type(self, t: CallableType) -> Type:
        if self.check_recursion(t):
            return AnyType(TypeOfAny.from_error)
        arg_types = [tp.accept(self) for tp in t.arg_types]
        ret_type = t.ret_type.accept(self)
        variables = t.variables.copy()
        for v in variables:
            if v.upper_bound:
                v.upper_bound = v.upper_bound.accept(self)
            if v.values:
                v.values = [val.accept(self) for val in v.values]
        return t.copy_modified(arg_types=arg_types, ret_type=ret_type, variables=variables)

    def visit_overloaded(self, t: Overloaded) -> Type:
        if self.check_recursion(t):
            return AnyType(TypeOfAny.from_error)
        return super().visit_overloaded(t)

    def visit_tuple_type(self, t: TupleType) -> Type:
        if self.check_recursion(t):
            return AnyType(TypeOfAny.from_error)
        items = [it.accept(self) for it in t.items]
        fallback = self.visit_instance(t.fallback, from_fallback=True)
        assert isinstance(fallback, Instance)
        return TupleType(items, fallback, t.line, t.column)

    def visit_typeddict_type(self, t: TypedDictType) -> Type:
        if self.check_recursion(t):
            return AnyType(TypeOfAny.from_error)
        items = OrderedDict([
            (item_name, item_type.accept(self))
            for (item_name, item_type) in t.items.items()
        ])
        fallback = self.visit_instance(t.fallback, from_fallback=True)
        assert isinstance(fallback, Instance)
        return TypedDictType(items, t.required_keys, fallback, t.line, t.column)

    def visit_literal_type(self, t: LiteralType) -> Type:
        if self.check_recursion(t):
            return AnyType(TypeOfAny.from_error)
        fallback = self.visit_instance(t.fallback, from_fallback=True)
        assert isinstance(fallback, Instance)
        return LiteralType(t.value, fallback, t.line, t.column)

    def visit_union_type(self, t: UnionType) -> Type:
        if self.check_recursion(t):
            return AnyType(TypeOfAny.from_error)
        return super().visit_union_type(t)

    def visit_type_type(self, t: TypeType) -> Type:
        if self.check_recursion(t):
            return AnyType(TypeOfAny.from_error)
        return super().visit_type_type(t)


class TypeVariableChecker(TypeTranslator):
    """Visitor that checks that type variables in generic types have valid values.

    Note: This must be run at the end of semantic analysis when MROs are
    complete and forward references have been resolved.

    This does two things:

    - If type variable in C has a value restriction, check that X in C[X] conforms
      to the restriction.
    - If type variable in C has a non-default upper bound, check that X in C[X]
      conforms to the upper bound.

    (This doesn't need to be a type translator, but it simplifies the implementation.)
    """

    def __init__(self, fail: Callable[[str, Context], None]) -> None:
        self.fail = fail

    def visit_instance(self, t: Instance) -> Type:
        info = t.type
        for (i, arg), tvar in zip(enumerate(t.args), info.defn.type_vars):
            if tvar.values:
                if isinstance(arg, TypeVarType):
                    arg_values = arg.values
                    if not arg_values:
                        self.fail('Type variable "{}" not valid as type '
                                  'argument value for "{}"'.format(
                                      arg.name, info.name()), t)
                        continue
                else:
                    arg_values = [arg]
                self.check_type_var_values(info, arg_values, tvar.name, tvar.values, i + 1, t)
            if not is_subtype(arg, tvar.upper_bound):
                self.fail('Type argument "{}" of "{}" must be '
                          'a subtype of "{}"'.format(
                              arg, info.name(), tvar.upper_bound), t)
        return super().visit_instance(t)

    def check_type_var_values(self, type: TypeInfo, actuals: List[Type], arg_name: str,
                              valids: List[Type], arg_number: int, context: Context) -> None:
        for actual in actuals:
            if (not isinstance(actual, AnyType) and
                    not any(is_same_type(actual, value)
                            for value in valids)):
                if len(actuals) > 1 or not isinstance(actual, Instance):
                    self.fail('Invalid type argument value for "{}"'.format(
                        type.name()), context)
                else:
                    class_name = '"{}"'.format(type.name())
                    actual_type_name = '"{}"'.format(actual.type.name())
                    self.fail(message_registry.INCOMPATIBLE_TYPEVAR_VALUE.format(
                        arg_name, class_name, actual_type_name), context)
