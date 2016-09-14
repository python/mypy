"""Base visitor that implements an identity AST transform.

Subclass TransformVisitor to perform non-trivial transformations.
"""

from typing import List, Dict, cast

from mypy.nodes import (
    MypyFile, Import, Node, ImportAll, ImportFrom, FuncItem, FuncDef,
    OverloadedFuncDef, ClassDef, Decorator, Block, Var,
    OperatorAssignmentStmt, ExpressionStmt, AssignmentStmt, ReturnStmt,
    RaiseStmt, AssertStmt, DelStmt, BreakStmt, ContinueStmt,
    PassStmt, GlobalDecl, WhileStmt, ForStmt, IfStmt, TryStmt, WithStmt,
    CastExpr, RevealTypeExpr, TupleExpr, GeneratorExpr, ListComprehension, ListExpr,
    ConditionalExpr, DictExpr, SetExpr, NameExpr, IntExpr, StrExpr, BytesExpr,
    UnicodeExpr, FloatExpr, CallExpr, SuperExpr, MemberExpr, IndexExpr,
    SliceExpr, OpExpr, UnaryExpr, FuncExpr, TypeApplication, PrintStmt,
    SymbolTable, RefExpr, TypeVarExpr, NewTypeExpr, PromoteExpr,
    ComparisonExpr, TempNode, StarExpr,
    YieldFromExpr, NamedTupleExpr, NonlocalDecl, SetComprehension,
    DictionaryComprehension, ComplexExpr, TypeAliasExpr, EllipsisExpr,
    YieldExpr, ExecStmt, Argument, BackquoteExpr, AwaitExpr,
)
from mypy.types import Type, FunctionLike, Instance
from mypy.traverser import TraverserVisitor
from mypy.visitor import NodeVisitor


class TransformVisitor(NodeVisitor[Node]):
    """Transform a semantically analyzed AST (or subtree) to an identical copy.

    Use the node() method to transform an AST node.

    Subclass to perform a non-identity transform.

    Notes:

     * Do not duplicate TypeInfo nodes. This would generally not be desirable.
     * Only update some name binding cross-references, but only those that
       refer to Var or FuncDef nodes, not those targeting ClassDef or TypeInfo
       nodes.
     * Types are not transformed, but you can override type() to also perform
       type transformation.

    TODO nested classes and functions have not been tested well enough
    """

    def __init__(self) -> None:
        # There may be multiple references to a Var node. Keep track of
        # Var translations using a dictionary.
        self.var_map = {}  # type: Dict[Var, Var]
        # These are uninitialized placeholder nodes used temporarily for nested
        # functions while we are transforming a top-level function. This maps an
        # untransformed node to a placeholder (which will later become the
        # transformed node).
        self.func_placeholder_map = {}  # type: Dict[FuncDef, FuncDef]

    def visit_mypy_file(self, node: MypyFile) -> Node:
        # NOTE: The 'names' and 'imports' instance variables will be empty!
        new = MypyFile(self.nodes(node.defs), [], node.is_bom,
                       ignored_lines=set(node.ignored_lines))
        new._name = node._name
        new._fullname = node._fullname
        new.path = node.path
        new.names = SymbolTable()
        return new

    def visit_import(self, node: Import) -> Node:
        return Import(node.ids[:])

    def visit_import_from(self, node: ImportFrom) -> Node:
        return ImportFrom(node.id, node.relative, node.names[:])

    def visit_import_all(self, node: ImportAll) -> Node:
        return ImportAll(node.id, node.relative)

    def copy_argument(self, argument: Argument) -> Argument:
        init_stmt = None  # type: AssignmentStmt

        if argument.initialization_statement:
            init_lvalue = cast(
                NameExpr,
                self.node(argument.initialization_statement.lvalues[0]),
            )
            init_lvalue.set_line(argument.line)
            init_stmt = AssignmentStmt(
                [init_lvalue],
                self.node(argument.initialization_statement.rvalue),
                self.optional_type(argument.initialization_statement.type),
            )

        arg = Argument(
            self.visit_var(argument.variable),
            argument.type_annotation,
            argument.initializer,
            argument.kind,
            init_stmt,
        )

        # Refresh lines of the inner things
        arg.set_line(argument.line)

        return arg

    def visit_func_def(self, node: FuncDef) -> FuncDef:
        # Note that a FuncDef must be transformed to a FuncDef.

        # These contortions are needed to handle the case of recursive
        # references inside the function being transformed.
        # Set up placholder nodes for references within this function
        # to other functions defined inside it.
        # Don't create an entry for this function itself though,
        # since we want self-references to point to the original
        # function if this is the top-level node we are transforming.
        init = FuncMapInitializer(self)
        for stmt in node.body.body:
            stmt.accept(init)

        new = FuncDef(node.name(),
                      [self.copy_argument(arg) for arg in node.arguments],
                      self.block(node.body),
                      cast(FunctionLike, self.optional_type(node.type)))

        self.copy_function_attributes(new, node)

        new._fullname = node._fullname
        new.is_decorated = node.is_decorated
        new.is_conditional = node.is_conditional
        new.is_abstract = node.is_abstract
        new.is_static = node.is_static
        new.is_class = node.is_class
        new.is_property = node.is_property
        new.original_def = node.original_def

        if node in self.func_placeholder_map:
            # There is a placeholder definition for this function. Replace
            # the attributes of the placeholder with those form the transformed
            # function. We know that the classes will be identical (otherwise
            # this wouldn't work).
            result = self.func_placeholder_map[node]
            result.__dict__ = new.__dict__
            return result
        else:
            return new

    def visit_func_expr(self, node: FuncExpr) -> Node:
        new = FuncExpr([self.copy_argument(arg) for arg in node.arguments],
                       self.block(node.body),
                       cast(FunctionLike, self.optional_type(node.type)))
        self.copy_function_attributes(new, node)
        return new

    def copy_function_attributes(self, new: FuncItem,
                                 original: FuncItem) -> None:
        new.info = original.info
        new.min_args = original.min_args
        new.max_pos = original.max_pos
        new.is_overload = original.is_overload
        new.is_generator = original.is_generator
        new.line = original.line

    def duplicate_inits(self,
                        inits: List[AssignmentStmt]) -> List[AssignmentStmt]:
        result = []  # type: List[AssignmentStmt]
        for init in inits:
            if init:
                result.append(self.duplicate_assignment(init))
            else:
                result.append(None)
        return result

    def visit_overloaded_func_def(self, node: OverloadedFuncDef) -> Node:
        items = [self.visit_decorator(decorator)
                 for decorator in node.items]
        for newitem, olditem in zip(items, node.items):
            newitem.line = olditem.line
        new = OverloadedFuncDef(items)
        new._fullname = node._fullname
        new.type = self.type(node.type)
        new.info = node.info
        return new

    def visit_class_def(self, node: ClassDef) -> Node:
        new = ClassDef(node.name,
                       self.block(node.defs),
                       node.type_vars,
                       self.nodes(node.base_type_exprs),
                       node.metaclass)
        new.fullname = node.fullname
        new.info = node.info
        new.decorators = [decorator.accept(self)
                          for decorator in node.decorators]
        new.is_builtinclass = node.is_builtinclass
        return new

    def visit_global_decl(self, node: GlobalDecl) -> Node:
        return GlobalDecl(node.names[:])

    def visit_nonlocal_decl(self, node: NonlocalDecl) -> Node:
        return NonlocalDecl(node.names[:])

    def visit_block(self, node: Block) -> Block:
        return Block(self.nodes(node.body))

    def visit_decorator(self, node: Decorator) -> Decorator:
        # Note that a Decorator must be transformed to a Decorator.
        func = self.visit_func_def(node.func)
        func.line = node.func.line
        new = Decorator(func, self.nodes(node.decorators),
                        self.visit_var(node.var))
        new.is_overload = node.is_overload
        return new

    def visit_var(self, node: Var) -> Var:
        # Note that a Var must be transformed to a Var.
        if node in self.var_map:
            return self.var_map[node]
        new = Var(node.name(), self.optional_type(node.type))
        new.line = node.line
        new._fullname = node._fullname
        new.info = node.info
        new.is_self = node.is_self
        new.is_ready = node.is_ready
        new.is_initialized_in_class = node.is_initialized_in_class
        new.is_staticmethod = node.is_staticmethod
        new.is_classmethod = node.is_classmethod
        new.is_property = node.is_property
        new.set_line(node.line)
        self.var_map[node] = new
        return new

    def visit_expression_stmt(self, node: ExpressionStmt) -> Node:
        return ExpressionStmt(self.node(node.expr))

    def visit_assignment_stmt(self, node: AssignmentStmt) -> Node:
        return self.duplicate_assignment(node)

    def duplicate_assignment(self, node: AssignmentStmt) -> AssignmentStmt:
        new = AssignmentStmt(self.nodes(node.lvalues),
                             self.node(node.rvalue),
                             self.optional_type(node.type))
        new.line = node.line
        return new

    def visit_operator_assignment_stmt(self,
                                       node: OperatorAssignmentStmt) -> Node:
        return OperatorAssignmentStmt(node.op,
                                      self.node(node.lvalue),
                                      self.node(node.rvalue))

    def visit_while_stmt(self, node: WhileStmt) -> Node:
        return WhileStmt(self.node(node.expr),
                         self.block(node.body),
                         self.optional_block(node.else_body))

    def visit_for_stmt(self, node: ForStmt) -> Node:
        return ForStmt(self.node(node.index),
                       self.node(node.expr),
                       self.block(node.body),
                       self.optional_block(node.else_body))

    def visit_return_stmt(self, node: ReturnStmt) -> Node:
        return ReturnStmt(self.optional_node(node.expr))

    def visit_assert_stmt(self, node: AssertStmt) -> Node:
        return AssertStmt(self.node(node.expr))

    def visit_del_stmt(self, node: DelStmt) -> Node:
        return DelStmt(self.node(node.expr))

    def visit_if_stmt(self, node: IfStmt) -> Node:
        return IfStmt(self.nodes(node.expr),
                      self.blocks(node.body),
                      self.optional_block(node.else_body))

    def visit_break_stmt(self, node: BreakStmt) -> Node:
        return BreakStmt()

    def visit_continue_stmt(self, node: ContinueStmt) -> Node:
        return ContinueStmt()

    def visit_pass_stmt(self, node: PassStmt) -> Node:
        return PassStmt()

    def visit_raise_stmt(self, node: RaiseStmt) -> Node:
        return RaiseStmt(self.optional_node(node.expr),
                         self.optional_node(node.from_expr))

    def visit_try_stmt(self, node: TryStmt) -> Node:
        return TryStmt(self.block(node.body),
                       self.optional_names(node.vars),
                       self.optional_nodes(node.types),
                       self.blocks(node.handlers),
                       self.optional_block(node.else_body),
                       self.optional_block(node.finally_body))

    def visit_with_stmt(self, node: WithStmt) -> Node:
        return WithStmt(self.nodes(node.expr),
                        self.optional_nodes(node.target),
                        self.block(node.body))

    def visit_print_stmt(self, node: PrintStmt) -> Node:
        return PrintStmt(self.nodes(node.args),
                         node.newline,
                         self.optional_node(node.target))

    def visit_exec_stmt(self, node: ExecStmt) -> Node:
        return ExecStmt(self.node(node.expr),
                        self.optional_node(node.variables1),
                        self.optional_node(node.variables2))

    def visit_star_expr(self, node: StarExpr) -> Node:
        return StarExpr(node.expr)

    def visit_int_expr(self, node: IntExpr) -> Node:
        return IntExpr(node.value)

    def visit_str_expr(self, node: StrExpr) -> Node:
        return StrExpr(node.value)

    def visit_bytes_expr(self, node: BytesExpr) -> Node:
        return BytesExpr(node.value)

    def visit_unicode_expr(self, node: UnicodeExpr) -> Node:
        return UnicodeExpr(node.value)

    def visit_float_expr(self, node: FloatExpr) -> Node:
        return FloatExpr(node.value)

    def visit_complex_expr(self, node: ComplexExpr) -> Node:
        return ComplexExpr(node.value)

    def visit_ellipsis(self, node: EllipsisExpr) -> Node:
        return EllipsisExpr()

    def visit_name_expr(self, node: NameExpr) -> Node:
        return self.duplicate_name(node)

    def duplicate_name(self, node: NameExpr) -> NameExpr:
        # This method is used when the transform result must be a NameExpr.
        # visit_name_expr() is used when there is no such restriction.
        new = NameExpr(node.name)
        self.copy_ref(new, node)
        return new

    def visit_member_expr(self, node: MemberExpr) -> Node:
        member = MemberExpr(self.node(node.expr),
                            node.name)
        if node.def_var:
            member.def_var = self.visit_var(node.def_var)
        self.copy_ref(member, node)
        return member

    def copy_ref(self, new: RefExpr, original: RefExpr) -> None:
        new.kind = original.kind
        new.fullname = original.fullname
        target = original.node
        if isinstance(target, Var):
            target = self.visit_var(target)
        elif isinstance(target, FuncDef):
            # Use a placeholder node for the function if it exists.
            target = self.func_placeholder_map.get(target, target)
        new.node = target
        new.is_def = original.is_def

    def visit_yield_from_expr(self, node: YieldFromExpr) -> Node:
        return YieldFromExpr(self.node(node.expr))

    def visit_yield_expr(self, node: YieldExpr) -> Node:
        return YieldExpr(self.node(node.expr))

    def visit_await_expr(self, node: AwaitExpr) -> Node:
        return AwaitExpr(self.node(node.expr))

    def visit_call_expr(self, node: CallExpr) -> Node:
        return CallExpr(self.node(node.callee),
                        self.nodes(node.args),
                        node.arg_kinds[:],
                        node.arg_names[:],
                        self.optional_node(node.analyzed))

    def visit_op_expr(self, node: OpExpr) -> Node:
        new = OpExpr(node.op, self.node(node.left), self.node(node.right))
        new.method_type = self.optional_type(node.method_type)
        return new

    def visit_comparison_expr(self, node: ComparisonExpr) -> Node:
        new = ComparisonExpr(node.operators, self.nodes(node.operands))
        new.method_types = [self.optional_type(t) for t in node.method_types]
        return new

    def visit_cast_expr(self, node: CastExpr) -> Node:
        return CastExpr(self.node(node.expr),
                        self.type(node.type))

    def visit_reveal_type_expr(self, node: RevealTypeExpr) -> Node:
        return RevealTypeExpr(self.node(node.expr))

    def visit_super_expr(self, node: SuperExpr) -> Node:
        new = SuperExpr(node.name)
        new.info = node.info
        return new

    def visit_unary_expr(self, node: UnaryExpr) -> Node:
        new = UnaryExpr(node.op, self.node(node.expr))
        new.method_type = self.optional_type(node.method_type)
        return new

    def visit_list_expr(self, node: ListExpr) -> Node:
        return ListExpr(self.nodes(node.items))

    def visit_dict_expr(self, node: DictExpr) -> Node:
        return DictExpr([(self.node(key), self.node(value))
                         for key, value in node.items])

    def visit_tuple_expr(self, node: TupleExpr) -> Node:
        return TupleExpr(self.nodes(node.items))

    def visit_set_expr(self, node: SetExpr) -> Node:
        return SetExpr(self.nodes(node.items))

    def visit_index_expr(self, node: IndexExpr) -> Node:
        new = IndexExpr(self.node(node.base), self.node(node.index))
        if node.method_type:
            new.method_type = self.type(node.method_type)
        if node.analyzed:
            if isinstance(node.analyzed, TypeApplication):
                new.analyzed = self.visit_type_application(node.analyzed)
            else:
                new.analyzed = self.visit_type_alias_expr(node.analyzed)
            new.analyzed.set_line(node.analyzed.line)
        return new

    def visit_type_application(self, node: TypeApplication) -> TypeApplication:
        return TypeApplication(self.node(node.expr),
                               self.types(node.types))

    def visit_list_comprehension(self, node: ListComprehension) -> Node:
        generator = self.duplicate_generator(node.generator)
        generator.set_line(node.generator.line)
        return ListComprehension(generator)

    def visit_set_comprehension(self, node: SetComprehension) -> Node:
        generator = self.duplicate_generator(node.generator)
        generator.set_line(node.generator.line)
        return SetComprehension(generator)

    def visit_dictionary_comprehension(self, node: DictionaryComprehension) -> Node:
        return DictionaryComprehension(self.node(node.key), self.node(node.value),
                             [self.node(index) for index in node.indices],
                             [self.node(s) for s in node.sequences],
                             [[self.node(cond) for cond in conditions]
                              for conditions in node.condlists])

    def visit_generator_expr(self, node: GeneratorExpr) -> Node:
        return self.duplicate_generator(node)

    def duplicate_generator(self, node: GeneratorExpr) -> GeneratorExpr:
        return GeneratorExpr(self.node(node.left_expr),
                             [self.node(index) for index in node.indices],
                             [self.node(s) for s in node.sequences],
                             [[self.node(cond) for cond in conditions]
                              for conditions in node.condlists])

    def visit_slice_expr(self, node: SliceExpr) -> Node:
        return SliceExpr(self.optional_node(node.begin_index),
                         self.optional_node(node.end_index),
                         self.optional_node(node.stride))

    def visit_conditional_expr(self, node: ConditionalExpr) -> Node:
        return ConditionalExpr(self.node(node.cond),
                               self.node(node.if_expr),
                               self.node(node.else_expr))

    def visit_backquote_expr(self, node: BackquoteExpr) -> Node:
        return BackquoteExpr(self.node(node.expr))

    def visit_type_var_expr(self, node: TypeVarExpr) -> Node:
        return TypeVarExpr(node.name(), node.fullname(),
                           self.types(node.values),
                           self.type(node.upper_bound), variance=node.variance)

    def visit_type_alias_expr(self, node: TypeAliasExpr) -> TypeAliasExpr:
        return TypeAliasExpr(node.type)

    def visit_newtype_expr(self, node: NewTypeExpr) -> NewTypeExpr:
        return NewTypeExpr(node.info)

    def visit_namedtuple_expr(self, node: NamedTupleExpr) -> Node:
        return NamedTupleExpr(node.info)

    def visit__promote_expr(self, node: PromoteExpr) -> Node:
        return PromoteExpr(node.type)

    def visit_temp_node(self, node: TempNode) -> Node:
        return TempNode(self.type(node.type))

    def node(self, node: Node) -> Node:
        new = node.accept(self)
        new.set_line(node.line)
        return new

    # Helpers
    #
    # All the node helpers also propagate line numbers.

    def optional_node(self, node: Node) -> Node:
        if node:
            return self.node(node)
        else:
            return None

    def block(self, block: Block) -> Block:
        new = self.visit_block(block)
        new.line = block.line
        return new

    def optional_block(self, block: Block) -> Block:
        if block:
            return self.block(block)
        else:
            return None

    def nodes(self, nodes: List[Node]) -> List[Node]:
        return [self.node(node) for node in nodes]

    def optional_nodes(self, nodes: List[Node]) -> List[Node]:
        return [self.optional_node(node) for node in nodes]

    def blocks(self, blocks: List[Block]) -> List[Block]:
        return [self.block(block) for block in blocks]

    def names(self, names: List[NameExpr]) -> List[NameExpr]:
        return [self.duplicate_name(name) for name in names]

    def optional_names(self, names: List[NameExpr]) -> List[NameExpr]:
        result = []  # type: List[NameExpr]
        for name in names:
            if name:
                result.append(self.duplicate_name(name))
            else:
                result.append(None)
        return result

    def type(self, type: Type) -> Type:
        # Override this method to transform types.
        return type

    def optional_type(self, type: Type) -> Type:
        if type:
            return self.type(type)
        else:
            return None

    def types(self, types: List[Type]) -> List[Type]:
        return [self.type(type) for type in types]

    def optional_types(self, types: List[Type]) -> List[Type]:
        return [self.optional_type(type) for type in types]


class FuncMapInitializer(TraverserVisitor):
    """This traverser creates mappings from nested FuncDefs to placeholder FuncDefs.

    The placholders will later be replaced with transformed nodes.
    """

    def __init__(self, transformer: TransformVisitor) -> None:
        self.transformer = transformer

    def visit_func_def(self, node: FuncDef) -> None:
        if node not in self.transformer.func_placeholder_map:
            # Haven't seen this FuncDef before, so create a placeholder node.
            self.transformer.func_placeholder_map[node] = FuncDef(
                node.name(), node.arguments, node.body, None)
        super().visit_func_def(node)
