"""The semantic analyzer pass 1.

This sets up externally visible names defined in a module but ignores
imports and local definitions.  It helps enable (some) cyclic references
between modules, such as module 'a' that imports module 'b' and used
names defined in b *and* vice versa.  The first pass can be performed
before dependent modules have been processed.

Since this pass can't assume that other modules have been processed,
this pass cannot determine the types of certain definitions that can
only be recognized in later passes. Examples of these include TypeVar
and NamedTuple definitions, as these look like regular assignments until
we are able to bind names, which only happens in pass 2.
"""

from typing import List, Tuple

from mypy import experiments
from mypy.nodes import (
    MypyFile, SymbolTable, SymbolTableNode, Var, Block, AssignmentStmt, FuncDef, Decorator,
    ClassDef, TypeInfo, ImportFrom, Import, ImportAll, IfStmt, WhileStmt, ForStmt, WithStmt,
    TryStmt, OverloadedFuncDef, Lvalue, LDEF, GDEF, MDEF, UNBOUND_IMPORTED, implicit_module_attrs
)
from mypy.types import Type, UnboundType, UnionType, AnyType, TypeOfAny, NoneTyp
from mypy.semanal import SemanticAnalyzerPass2, infer_reachability_of_if_statement
from mypy.options import Options
from mypy.visitor import NodeVisitor


class SemanticAnalyzerPass1(NodeVisitor[None]):
    """First phase of semantic analysis.

    See docstring of 'analyze()' below for a description of what this does.
    """

    def __init__(self, sem: SemanticAnalyzerPass2) -> None:
        self.sem = sem

    def visit_file(self, file: MypyFile, fnam: str, mod_id: str, options: Options) -> None:
        """Perform the first analysis pass.

        Populate module global table.  Resolve the full names of
        definitions not nested within functions and construct type
        info structures, but do not resolve inter-definition
        references such as base classes.

        Also add implicit definitions such as __name__.

        In this phase we don't resolve imports. For 'from ... import',
        we generate dummy symbol table nodes for the imported names,
        and these will get resolved in later phases of semantic
        analysis.
        """
        sem = self.sem
        self.sem.options = options  # Needed because we sometimes call into it
        self.pyversion = options.python_version
        self.platform = options.platform
        sem.cur_mod_id = mod_id
        sem.errors.set_file(fnam, mod_id)
        sem.globals = SymbolTable()
        sem.global_decls = [set()]
        sem.nonlocal_decls = [set()]
        sem.block_depth = [0]

        defs = file.defs

        with experiments.strict_optional_set(options.strict_optional):
            # Add implicit definitions of module '__name__' etc.
            for name, t in implicit_module_attrs.items():
                # unicode docstrings should be accepted in Python 2
                if name == '__doc__':
                    if self.pyversion >= (3, 0):
                        typ = UnboundType('__builtins__.str')  # type: Type
                    else:
                        typ = UnionType([UnboundType('__builtins__.str'),
                                        UnboundType('__builtins__.unicode')])
                else:
                    assert t is not None, 'type should be specified for {}'.format(name)
                    typ = UnboundType(t)
                v = Var(name, typ)
                v._fullname = self.sem.qualified_name(name)
                self.sem.globals[name] = SymbolTableNode(GDEF, v)

            for d in defs:
                d.accept(self)

            # Add implicit definition of literals/keywords to builtins, as we
            # cannot define a variable with them explicitly.
            if mod_id == 'builtins':
                literal_types = [
                    ('None', NoneTyp()),
                    # reveal_type is a mypy-only function that gives an error with
                    # the type of its arg.
                    ('reveal_type', AnyType(TypeOfAny.special_form)),
                ]  # type: List[Tuple[str, Type]]

                # TODO(ddfisher): This guard is only needed because mypy defines
                # fake builtins for its tests which often don't define bool.  If
                # mypy is fast enough that we no longer need those, this
                # conditional check should be removed.
                if 'bool' in self.sem.globals:
                    bool_type = self.sem.named_type('bool')
                    literal_types.extend([
                        ('True', bool_type),
                        ('False', bool_type),
                        ('__debug__', bool_type),
                    ])
                else:
                    # We are running tests without 'bool' in builtins.
                    # TODO: Find a permanent solution to this problem.
                    # Maybe add 'bool' to all fixtures?
                    literal_types.append(('True', AnyType(TypeOfAny.special_form)))

                for name, typ in literal_types:
                    v = Var(name, typ)
                    v._fullname = self.sem.qualified_name(name)
                    self.sem.globals[name] = SymbolTableNode(GDEF, v)

            del self.sem.options

    def visit_block(self, b: Block) -> None:
        if b.is_unreachable:
            return
        self.sem.block_depth[-1] += 1
        for node in b.body:
            node.accept(self)
        self.sem.block_depth[-1] -= 1

    def visit_assignment_stmt(self, s: AssignmentStmt) -> None:
        if self.sem.is_module_scope():
            for lval in s.lvalues:
                self.analyze_lvalue(lval, explicit_type=s.type is not None)

    def visit_func_def(self, func: FuncDef) -> None:
        sem = self.sem
        func.is_conditional = sem.block_depth[-1] > 0
        func._fullname = sem.qualified_name(func.name())
        at_module = sem.is_module_scope()
        if at_module and func.name() in sem.globals:
            # Already defined in this module.
            original_sym = sem.globals[func.name()]
            if original_sym.kind == UNBOUND_IMPORTED:
                # Ah this is an imported name. We can't resolve them now, so we'll postpone
                # this until the main phase of semantic analysis.
                return
            if not sem.set_original_def(original_sym.node, func):
                # Report error.
                sem.check_no_global(func.name(), func)
        else:
            if at_module:
                sem.globals[func.name()] = SymbolTableNode(GDEF, func)
            # Also analyze the function body (in case there are conditional imports).
            sem.function_stack.append(func)
            sem.errors.push_function(func.name())
            sem.enter()
            func.body.accept(self)
            sem.leave()
            sem.errors.pop_function()
            sem.function_stack.pop()

    def visit_overloaded_func_def(self, func: OverloadedFuncDef) -> None:
        kind = self.kind_by_scope()
        if kind == GDEF:
            self.sem.check_no_global(func.name(), func, True)
        func._fullname = self.sem.qualified_name(func.name())
        if kind == GDEF:
            self.sem.globals[func.name()] = SymbolTableNode(kind, func)
        if func.impl:
            impl = func.impl
            # Also analyze the function body (in case there are conditional imports).
            sem = self.sem

            if isinstance(impl, FuncDef):
                sem.function_stack.append(impl)
                sem.errors.push_function(func.name())
                sem.enter()
                impl.body.accept(self)
            elif isinstance(impl, Decorator):
                sem.function_stack.append(impl.func)
                sem.errors.push_function(func.name())
                sem.enter()
                impl.func.body.accept(self)
            else:
                assert False, "Implementation of an overload needs to be FuncDef or Decorator"
            sem.leave()
            sem.errors.pop_function()
            sem.function_stack.pop()

    def visit_class_def(self, cdef: ClassDef) -> None:
        kind = self.kind_by_scope()
        if kind == LDEF:
            return
        elif kind == GDEF:
            self.sem.check_no_global(cdef.name, cdef)
        cdef.fullname = self.sem.qualified_name(cdef.name)
        info = TypeInfo(SymbolTable(), cdef, self.sem.cur_mod_id)
        info.set_line(cdef.line, cdef.column)
        cdef.info = info
        if kind == GDEF:
            self.sem.globals[cdef.name] = SymbolTableNode(kind, info)
        self.process_nested_classes(cdef)

    def process_nested_classes(self, outer_def: ClassDef) -> None:
        self.sem.enter_class(outer_def.info)
        for node in outer_def.defs.body:
            if isinstance(node, ClassDef):
                node.info = TypeInfo(SymbolTable(), node, self.sem.cur_mod_id)
                if outer_def.fullname:
                    node.info._fullname = outer_def.fullname + '.' + node.info.name()
                else:
                    node.info._fullname = node.info.name()
                node.fullname = node.info._fullname
                symbol = SymbolTableNode(MDEF, node.info)
                outer_def.info.names[node.name] = symbol
                self.process_nested_classes(node)
            elif isinstance(node, (ImportFrom, Import, ImportAll, IfStmt)):
                node.accept(self)
        self.sem.leave_class()

    def visit_import_from(self, node: ImportFrom) -> None:
        # We can't bind module names during the first pass, as the target module might be
        # unprocessed. However, we add dummy unbound imported names to the symbol table so
        # that we at least know that the name refers to a module.
        at_module = self.sem.is_module_scope()
        node.is_top_level = at_module
        if not at_module:
            return
        for name, as_name in node.names:
            imported_name = as_name or name
            if imported_name not in self.sem.globals:
                self.sem.add_symbol(imported_name, SymbolTableNode(UNBOUND_IMPORTED, None), node)

    def visit_import(self, node: Import) -> None:
        node.is_top_level = self.sem.is_module_scope()
        # This is similar to visit_import_from -- see the comment there.
        if not self.sem.is_module_scope():
            return
        for id, as_id in node.ids:
            imported_id = as_id or id
            if imported_id not in self.sem.globals:
                self.sem.add_symbol(imported_id, SymbolTableNode(UNBOUND_IMPORTED, None), node)
            else:
                # If the previous symbol is a variable, this should take precedence.
                self.sem.globals[imported_id] = SymbolTableNode(UNBOUND_IMPORTED, None)

    def visit_import_all(self, node: ImportAll) -> None:
        node.is_top_level = self.sem.is_module_scope()

    def visit_while_stmt(self, s: WhileStmt) -> None:
        if self.sem.is_module_scope():
            s.body.accept(self)
            if s.else_body:
                s.else_body.accept(self)

    def visit_for_stmt(self, s: ForStmt) -> None:
        if self.sem.is_module_scope():
            self.analyze_lvalue(s.index, explicit_type=s.index_type is not None)
            s.body.accept(self)
            if s.else_body:
                s.else_body.accept(self)

    def visit_with_stmt(self, s: WithStmt) -> None:
        if self.sem.is_module_scope():
            for n in s.target:
                if n:
                    self.analyze_lvalue(n, explicit_type=s.target_type is not None)
            s.body.accept(self)

    def visit_decorator(self, d: Decorator) -> None:
        d.var._fullname = self.sem.qualified_name(d.var.name())
        self.sem.add_symbol(d.var.name(), SymbolTableNode(self.kind_by_scope(), d.var), d)

    def visit_if_stmt(self, s: IfStmt) -> None:
        infer_reachability_of_if_statement(s, pyversion=self.pyversion, platform=self.platform)
        for node in s.body:
            node.accept(self)
        if s.else_body:
            s.else_body.accept(self)

    def visit_try_stmt(self, s: TryStmt) -> None:
        if self.sem.is_module_scope():
            self.sem.analyze_try_stmt(s, self, add_global=self.sem.is_module_scope())

    def analyze_lvalue(self, lvalue: Lvalue, explicit_type: bool = False) -> None:
        self.sem.analyze_lvalue(lvalue, add_global=self.sem.is_module_scope(),
                                explicit_type=explicit_type)

    def kind_by_scope(self) -> int:
        if self.sem.is_module_scope():
            return GDEF
        elif self.sem.is_class_scope():
            return MDEF
        elif self.sem.is_func_scope():
            return LDEF
        else:
            assert False, "Couldn't determine scope"
