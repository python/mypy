from functools import wraps
import sys

from typing import Tuple, Union, TypeVar, Callable, Sequence, Optional, Any, cast, List
from mypy.nodes import (
    MypyFile, Node, ImportBase, Import, ImportAll, ImportFrom, FuncDef, OverloadedFuncDef,
    ClassDef, Decorator, Block, Var, OperatorAssignmentStmt,
    ExpressionStmt, AssignmentStmt, ReturnStmt, RaiseStmt, AssertStmt,
    DelStmt, BreakStmt, ContinueStmt, PassStmt, GlobalDecl,
    WhileStmt, ForStmt, IfStmt, TryStmt, WithStmt,
    TupleExpr, GeneratorExpr, ListComprehension, ListExpr, ConditionalExpr,
    DictExpr, SetExpr, NameExpr, IntExpr, StrExpr, BytesExpr, UnicodeExpr,
    FloatExpr, CallExpr, SuperExpr, MemberExpr, IndexExpr, SliceExpr, OpExpr,
    UnaryExpr, FuncExpr, ComparisonExpr,
    StarExpr, YieldFromExpr, NonlocalDecl, DictionaryComprehension,
    SetComprehension, ComplexExpr, EllipsisExpr, YieldExpr, Argument,
    AwaitExpr,
    ARG_POS, ARG_OPT, ARG_STAR, ARG_NAMED, ARG_STAR2
)
from mypy.types import (
    Type, CallableType, FunctionLike, AnyType, UnboundType, TupleType, TypeList, EllipsisType,
)
from mypy import defaults
from mypy import experiments
from mypy.errors import Errors

try:
    from typed_ast import ast35
except ImportError:
    if sys.version_info.minor > 2:
        print('You must install the typed_ast package before you can run mypy'
              ' with `--fast-parser`.\n'
              'You can do this with `python3 -m pip install typed-ast`.',
              file=sys.stderr)
    else:
        print('The typed_ast package required by --fast-parser is only compatible with'
              ' Python 3.3 and greater.')
    sys.exit(1)

T = TypeVar('T', bound=Union[ast35.expr, ast35.stmt])
U = TypeVar('U', bound=Node)
V = TypeVar('V')

TYPE_COMMENT_SYNTAX_ERROR = 'syntax error in type comment'
TYPE_COMMENT_AST_ERROR = 'invalid type comment'


def parse(source: Union[str, bytes], fnam: str = None, errors: Errors = None,
          pyversion: Tuple[int, int] = defaults.PYTHON3_VERSION,
          custom_typing_module: str = None) -> MypyFile:
    """Parse a source file, without doing any semantic analysis.

    Return the parse tree. If errors is not provided, raise ParseError
    on failure. Otherwise, use the errors object to report parse errors.

    The pyversion (major, minor) argument determines the Python syntax variant.
    """
    is_stub_file = bool(fnam) and fnam.endswith('.pyi')
    try:
        assert pyversion[0] >= 3 or is_stub_file
        ast = ast35.parse(source, fnam, 'exec')

        tree = ASTConverter(pyversion=pyversion,
                            is_stub=is_stub_file,
                            custom_typing_module=custom_typing_module,
                            ).visit(ast)
        tree.path = fnam
        tree.is_stub = is_stub_file
        return tree
    except (SyntaxError, TypeCommentParseError) as e:
        if errors:
            errors.set_file('<input>' if fnam is None else fnam)
            errors.report(e.lineno, e.msg)
        else:
            raise

    return MypyFile([],
                    [],
                    False,
                    set(),
                    weak_opts=set())


def parse_type_comment(type_comment: str, line: int) -> Type:
    try:
        typ = ast35.parse(type_comment, '<type_comment>', 'eval')
    except SyntaxError:
        raise TypeCommentParseError(TYPE_COMMENT_SYNTAX_ERROR, line)
    else:
        assert isinstance(typ, ast35.Expression)
        return TypeConverter(line=line).visit(typ.body)


def with_line(f: Callable[['ASTConverter', T], U]) -> Callable[['ASTConverter', T], U]:
    @wraps(f)
    def wrapper(self: 'ASTConverter', ast: T) -> U:
        node = f(self, ast)
        node.set_line(ast.lineno)
        return node
    return wrapper


def find(f: Callable[[V], bool], seq: Sequence[V]) -> V:
    for item in seq:
        if f(item):
            return item
    return None


class ASTConverter(ast35.NodeTransformer):
    def __init__(self,
                 pyversion: Tuple[int, int],
                 is_stub: bool,
                 custom_typing_module: str = None) -> None:
        self.class_nesting = 0
        self.imports = []  # type: List[ImportBase]

        self.pyversion = pyversion
        self.is_stub = is_stub
        self.custom_typing_module = custom_typing_module

    def generic_visit(self, node: ast35.AST) -> None:
        raise RuntimeError('AST node not implemented: ' + str(type(node)))

    def visit_NoneType(self, n: Any) -> Optional[Node]:
        return None

    def visit_list(self, l: Sequence[ast35.AST]) -> List[Node]:
        return [self.visit(e) for e in l]

    op_map = {
        ast35.Add: '+',
        ast35.Sub: '-',
        ast35.Mult: '*',
        ast35.MatMult: '@',
        ast35.Div: '/',
        ast35.Mod: '%',
        ast35.Pow: '**',
        ast35.LShift: '<<',
        ast35.RShift: '>>',
        ast35.BitOr: '|',
        ast35.BitXor: '^',
        ast35.BitAnd: '&',
        ast35.FloorDiv: '//'
    }

    def from_operator(self, op: ast35.operator) -> str:
        op_name = ASTConverter.op_map.get(type(op))
        if op_name is None:
            raise RuntimeError('Unknown operator ' + str(type(op)))
        elif op_name == '@':
            raise RuntimeError('mypy does not support the MatMult operator')
        else:
            return op_name

    comp_op_map = {
        ast35.Gt: '>',
        ast35.Lt: '<',
        ast35.Eq: '==',
        ast35.GtE: '>=',
        ast35.LtE: '<=',
        ast35.NotEq: '!=',
        ast35.Is: 'is',
        ast35.IsNot: 'is not',
        ast35.In: 'in',
        ast35.NotIn: 'not in'
    }

    def from_comp_operator(self, op: ast35.cmpop) -> str:
        op_name = ASTConverter.comp_op_map.get(type(op))
        if op_name is None:
            raise RuntimeError('Unknown comparison operator ' + str(type(op)))
        else:
            return op_name

    def as_block(self, stmts: List[ast35.stmt], lineno: int) -> Block:
        b = None
        if stmts:
            b = Block(self.fix_function_overloads(self.visit_list(stmts)))
            b.set_line(lineno)
        return b

    def fix_function_overloads(self, stmts: List[Node]) -> List[Node]:
        ret = []  # type: List[Node]
        current_overload = []
        current_overload_name = None
        # mypy doesn't actually check that the decorator is literally @overload
        for stmt in stmts:
            if isinstance(stmt, Decorator) and stmt.name() == current_overload_name:
                current_overload.append(stmt)
            else:
                if len(current_overload) == 1:
                    ret.append(current_overload[0])
                elif len(current_overload) > 1:
                    ret.append(OverloadedFuncDef(current_overload))

                if isinstance(stmt, Decorator):
                    current_overload = [stmt]
                    current_overload_name = stmt.name()
                else:
                    current_overload = []
                    current_overload_name = None
                    ret.append(stmt)

        if len(current_overload) == 1:
            ret.append(current_overload[0])
        elif len(current_overload) > 1:
            ret.append(OverloadedFuncDef(current_overload))
        return ret

    def in_class(self) -> bool:
        return self.class_nesting > 0

    def translate_module_id(self, id: str) -> str:
        """Return the actual, internal module id for a source text id.

        For example, translate '__builtin__' in Python 2 to 'builtins'.
        """
        if id == self.custom_typing_module:
            return 'typing'
        elif id == '__builtin__' and self.pyversion[0] == 2:
            # HACK: __builtin__ in Python 2 is aliases to builtins. However, the implementation
            #   is named __builtin__.py (there is another layer of translation elsewhere).
            return 'builtins'
        return id

    def visit_Module(self, mod: ast35.Module) -> Node:
        body = self.fix_function_overloads(self.visit_list(mod.body))

        return MypyFile(body,
                        self.imports,
                        False,
                        {ti.lineno for ti in mod.type_ignores},
                        weak_opts=set())

    # --- stmt ---
    # FunctionDef(identifier name, arguments args,
    #             stmt* body, expr* decorator_list, expr? returns, string? type_comment)
    # arguments = (arg* args, arg? vararg, arg* kwonlyargs, expr* kw_defaults,
    #              arg? kwarg, expr* defaults)
    @with_line
    def visit_FunctionDef(self, n: ast35.FunctionDef) -> Node:
        return self.do_func_def(n)

    # AsyncFunctionDef(identifier name, arguments args,
    #                  stmt* body, expr* decorator_list, expr? returns, string? type_comment)
    @with_line
    def visit_AsyncFunctionDef(self, n: ast35.AsyncFunctionDef) -> Node:
        return self.do_func_def(n, is_coroutine=True)

    def do_func_def(self, n: Union[ast35.FunctionDef, ast35.AsyncFunctionDef],
                    is_coroutine: bool = False) -> Node:
        """Helper shared between visit_FunctionDef and visit_AsyncFunctionDef."""
        args = self.transform_args(n.args, n.lineno)

        arg_kinds = [arg.kind for arg in args]
        arg_names = [arg.variable.name() for arg in args]
        arg_types = None  # type: List[Type]
        if n.type_comment is not None:
            try:
                func_type_ast = ast35.parse(n.type_comment, '<func_type>', 'func_type')
            except SyntaxError:
                raise TypeCommentParseError(TYPE_COMMENT_SYNTAX_ERROR, n.lineno)
            assert isinstance(func_type_ast, ast35.FunctionType)
            # for ellipsis arg
            if (len(func_type_ast.argtypes) == 1 and
                    isinstance(func_type_ast.argtypes[0], ast35.Ellipsis)):
                arg_types = [a.type_annotation if a.type_annotation is not None else AnyType()
                             for a in args]
            else:
                arg_types = [a if a is not None else AnyType() for
                            a in TypeConverter(line=n.lineno).visit_list(func_type_ast.argtypes)]
            return_type = TypeConverter(line=n.lineno).visit(func_type_ast.returns)

            # add implicit self type
            if self.in_class() and len(arg_types) < len(args):
                arg_types.insert(0, AnyType())
        else:
            arg_types = [a.type_annotation for a in args]
            return_type = TypeConverter(line=n.lineno).visit(n.returns)

        for arg, arg_type in zip(args, arg_types):
            self.set_type_optional(arg_type, arg.initializer)

        if isinstance(return_type, UnboundType):
            return_type.is_ret_type = True

        func_type = None
        if any(arg_types) or return_type:
            func_type = CallableType([a if a is not None else AnyType() for a in arg_types],
                                     arg_kinds,
                                     arg_names,
                                     return_type if return_type is not None else AnyType(),
                                     None)

        func_def = FuncDef(n.name,
                       args,
                       self.as_block(n.body, n.lineno),
                       func_type)
        if is_coroutine:
            # A coroutine is also a generator, mostly for internal reasons.
            func_def.is_generator = func_def.is_coroutine = True
        if func_type is not None:
            func_type.definition = func_def
            func_type.line = n.lineno

        if n.decorator_list:
            var = Var(func_def.name())
            var.is_ready = False
            var.set_line(n.decorator_list[0].lineno)

            func_def.is_decorated = True
            func_def.set_line(n.lineno + len(n.decorator_list))
            func_def.body.set_line(func_def.get_line())
            return Decorator(func_def, self.visit_list(n.decorator_list), var)
        else:
            return func_def

    def set_type_optional(self, type: Type, initializer: Node) -> None:
        if not experiments.STRICT_OPTIONAL:
            return
        # Indicate that type should be wrapped in an Optional if arg is initialized to None.
        optional = isinstance(initializer, NameExpr) and initializer.name == 'None'
        if isinstance(type, UnboundType):
            type.optional = optional

    def transform_args(self, args: ast35.arguments, line: int) -> List[Argument]:
        def make_argument(arg: ast35.arg, default: Optional[ast35.expr], kind: int) -> Argument:
            arg_type = TypeConverter(line=line).visit(arg.annotation)
            return Argument(Var(arg.arg), arg_type, self.visit(default), kind)

        new_args = []
        num_no_defaults = len(args.args) - len(args.defaults)
        # positional arguments without defaults
        for a in args.args[:num_no_defaults]:
            new_args.append(make_argument(a, None, ARG_POS))

        # positional arguments with defaults
        for a, d in zip(args.args[num_no_defaults:], args.defaults):
            new_args.append(make_argument(a, d, ARG_OPT))

        # *arg
        if args.vararg is not None:
            new_args.append(make_argument(args.vararg, None, ARG_STAR))

        num_no_kw_defaults = len(args.kwonlyargs) - len(args.kw_defaults)
        # keyword-only arguments without defaults
        for a in args.kwonlyargs[:num_no_kw_defaults]:
            new_args.append(make_argument(a, None, ARG_NAMED))

        # keyword-only arguments with defaults
        for a, d in zip(args.kwonlyargs[num_no_kw_defaults:], args.kw_defaults):
            new_args.append(make_argument(a, d, ARG_NAMED))

        # **kwarg
        if args.kwarg is not None:
            new_args.append(make_argument(args.kwarg, None, ARG_STAR2))

        return new_args

    def stringify_name(self, n: ast35.AST) -> str:
        if isinstance(n, ast35.Name):
            return n.id
        elif isinstance(n, ast35.Attribute):
            return "{}.{}".format(self.stringify_name(n.value), n.attr)
        else:
            assert False, "can't stringify " + str(type(n))

    # ClassDef(identifier name,
    #  expr* bases,
    #  keyword* keywords,
    #  stmt* body,
    #  expr* decorator_list)
    @with_line
    def visit_ClassDef(self, n: ast35.ClassDef) -> Node:
        self.class_nesting += 1
        metaclass_arg = find(lambda x: x.arg == 'metaclass', n.keywords)
        metaclass = None
        if metaclass_arg:
            metaclass = self.stringify_name(metaclass_arg.value)

        cdef = ClassDef(n.name,
                        self.as_block(n.body, n.lineno),
                        None,
                        self.visit_list(n.bases),
                        metaclass=metaclass)
        cdef.decorators = self.visit_list(n.decorator_list)
        self.class_nesting -= 1
        return cdef

    # Return(expr? value)
    @with_line
    def visit_Return(self, n: ast35.Return) -> Node:
        return ReturnStmt(self.visit(n.value))

    # Delete(expr* targets)
    @with_line
    def visit_Delete(self, n: ast35.Delete) -> Node:
        if len(n.targets) > 1:
            tup = TupleExpr(self.visit_list(n.targets))
            tup.set_line(n.lineno)
            return DelStmt(tup)
        else:
            return DelStmt(self.visit(n.targets[0]))

    # Assign(expr* targets, expr value, string? type_comment)
    @with_line
    def visit_Assign(self, n: ast35.Assign) -> Node:
        typ = None
        if n.type_comment:
            typ = parse_type_comment(n.type_comment, n.lineno)

        return AssignmentStmt(self.visit_list(n.targets),
                              self.visit(n.value),
                              type=typ)

    # AugAssign(expr target, operator op, expr value)
    @with_line
    def visit_AugAssign(self, n: ast35.AugAssign) -> Node:
        return OperatorAssignmentStmt(self.from_operator(n.op),
                              self.visit(n.target),
                              self.visit(n.value))

    # For(expr target, expr iter, stmt* body, stmt* orelse, string? type_comment)
    @with_line
    def visit_For(self, n: ast35.For) -> Node:
        return ForStmt(self.visit(n.target),
                       self.visit(n.iter),
                       self.as_block(n.body, n.lineno),
                       self.as_block(n.orelse, n.lineno))

    # AsyncFor(expr target, expr iter, stmt* body, stmt* orelse)
    @with_line
    def visit_AsyncFor(self, n: ast35.AsyncFor) -> Node:
        r = ForStmt(self.visit(n.target),
                    self.visit(n.iter),
                    self.as_block(n.body, n.lineno),
                    self.as_block(n.orelse, n.lineno))
        r.is_async = True
        return r

    # While(expr test, stmt* body, stmt* orelse)
    @with_line
    def visit_While(self, n: ast35.While) -> Node:
        return WhileStmt(self.visit(n.test),
                         self.as_block(n.body, n.lineno),
                         self.as_block(n.orelse, n.lineno))

    # If(expr test, stmt* body, stmt* orelse)
    @with_line
    def visit_If(self, n: ast35.If) -> Node:
        return IfStmt([self.visit(n.test)],
                      [self.as_block(n.body, n.lineno)],
                      self.as_block(n.orelse, n.lineno))

    # With(withitem* items, stmt* body, string? type_comment)
    @with_line
    def visit_With(self, n: ast35.With) -> Node:
        return WithStmt([self.visit(i.context_expr) for i in n.items],
                        [self.visit(i.optional_vars) for i in n.items],
                        self.as_block(n.body, n.lineno))

    # AsyncWith(withitem* items, stmt* body)
    @with_line
    def visit_AsyncWith(self, n: ast35.AsyncWith) -> Node:
        r = WithStmt([self.visit(i.context_expr) for i in n.items],
                     [self.visit(i.optional_vars) for i in n.items],
                     self.as_block(n.body, n.lineno))
        r.is_async = True
        return r

    # Raise(expr? exc, expr? cause)
    @with_line
    def visit_Raise(self, n: ast35.Raise) -> Node:
        return RaiseStmt(self.visit(n.exc), self.visit(n.cause))

    # Try(stmt* body, excepthandler* handlers, stmt* orelse, stmt* finalbody)
    @with_line
    def visit_Try(self, n: ast35.Try) -> Node:
        vs = [NameExpr(h.name) if h.name is not None else None for h in n.handlers]
        types = [self.visit(h.type) for h in n.handlers]
        handlers = [self.as_block(h.body, h.lineno) for h in n.handlers]

        return TryStmt(self.as_block(n.body, n.lineno),
                       vs,
                       types,
                       handlers,
                       self.as_block(n.orelse, n.lineno),
                       self.as_block(n.finalbody, n.lineno))

    # Assert(expr test, expr? msg)
    @with_line
    def visit_Assert(self, n: ast35.Assert) -> Node:
        return AssertStmt(self.visit(n.test))

    # Import(alias* names)
    @with_line
    def visit_Import(self, n: ast35.Import) -> Node:
        i = Import([(self.translate_module_id(a.name), a.asname) for a in n.names])
        self.imports.append(i)
        return i

    # ImportFrom(identifier? module, alias* names, int? level)
    @with_line
    def visit_ImportFrom(self, n: ast35.ImportFrom) -> Node:
        i = None  # type: ImportBase
        if len(n.names) == 1 and n.names[0].name == '*':
            i = ImportAll(n.module, n.level)
        else:
            i = ImportFrom(self.translate_module_id(n.module) if n.module is not None else '',
                           n.level,
                           [(a.name, a.asname) for a in n.names])
        self.imports.append(i)
        return i

    # Global(identifier* names)
    @with_line
    def visit_Global(self, n: ast35.Global) -> Node:
        return GlobalDecl(n.names)

    # Nonlocal(identifier* names)
    @with_line
    def visit_Nonlocal(self, n: ast35.Nonlocal) -> Node:
        return NonlocalDecl(n.names)

    # Expr(expr value)
    @with_line
    def visit_Expr(self, n: ast35.Expr) -> Node:
        value = self.visit(n.value)
        return ExpressionStmt(value)

    # Pass
    @with_line
    def visit_Pass(self, n: ast35.Pass) -> Node:
        return PassStmt()

    # Break
    @with_line
    def visit_Break(self, n: ast35.Break) -> Node:
        return BreakStmt()

    # Continue
    @with_line
    def visit_Continue(self, n: ast35.Continue) -> Node:
        return ContinueStmt()

    # --- expr ---
    # BoolOp(boolop op, expr* values)
    @with_line
    def visit_BoolOp(self, n: ast35.BoolOp) -> Node:
        # mypy translates (1 and 2 and 3) as (1 and (2 and 3))
        assert len(n.values) >= 2
        op = None
        if isinstance(n.op, ast35.And):
            op = 'and'
        elif isinstance(n.op, ast35.Or):
            op = 'or'
        else:
            raise RuntimeError('unknown BoolOp ' + str(type(n)))

        # potentially inefficient!
        def group(vals: List[Node]) -> Node:
            if len(vals) == 2:
                return OpExpr(op, vals[0], vals[1])
            else:
                return OpExpr(op, vals[0], group(vals[1:]))

        return group(self.visit_list(n.values))

    # BinOp(expr left, operator op, expr right)
    @with_line
    def visit_BinOp(self, n: ast35.BinOp) -> Node:
        op = self.from_operator(n.op)

        if op is None:
            raise RuntimeError('cannot translate BinOp ' + str(type(n.op)))

        return OpExpr(op, self.visit(n.left), self.visit(n.right))

    # UnaryOp(unaryop op, expr operand)
    @with_line
    def visit_UnaryOp(self, n: ast35.UnaryOp) -> Node:
        op = None
        if isinstance(n.op, ast35.Invert):
            op = '~'
        elif isinstance(n.op, ast35.Not):
            op = 'not'
        elif isinstance(n.op, ast35.UAdd):
            op = '+'
        elif isinstance(n.op, ast35.USub):
            op = '-'

        if op is None:
            raise RuntimeError('cannot translate UnaryOp ' + str(type(n.op)))

        return UnaryExpr(op, self.visit(n.operand))

    # Lambda(arguments args, expr body)
    @with_line
    def visit_Lambda(self, n: ast35.Lambda) -> Node:
        body = ast35.Return(n.body)
        body.lineno = n.lineno

        return FuncExpr(self.transform_args(n.args, n.lineno),
                        self.as_block([body], n.lineno))

    # IfExp(expr test, expr body, expr orelse)
    @with_line
    def visit_IfExp(self, n: ast35.IfExp) -> Node:
        return ConditionalExpr(self.visit(n.test),
                               self.visit(n.body),
                               self.visit(n.orelse))

    # Dict(expr* keys, expr* values)
    @with_line
    def visit_Dict(self, n: ast35.Dict) -> Node:
        return DictExpr(list(zip(self.visit_list(n.keys), self.visit_list(n.values))))

    # Set(expr* elts)
    @with_line
    def visit_Set(self, n: ast35.Set) -> Node:
        return SetExpr(self.visit_list(n.elts))

    # ListComp(expr elt, comprehension* generators)
    @with_line
    def visit_ListComp(self, n: ast35.ListComp) -> Node:
        return ListComprehension(self.visit_GeneratorExp(cast(ast35.GeneratorExp, n)))

    # SetComp(expr elt, comprehension* generators)
    @with_line
    def visit_SetComp(self, n: ast35.SetComp) -> Node:
        return SetComprehension(self.visit_GeneratorExp(cast(ast35.GeneratorExp, n)))

    # DictComp(expr key, expr value, comprehension* generators)
    @with_line
    def visit_DictComp(self, n: ast35.DictComp) -> Node:
        targets = [self.visit(c.target) for c in n.generators]
        iters = [self.visit(c.iter) for c in n.generators]
        ifs_list = [self.visit_list(c.ifs) for c in n.generators]
        return DictionaryComprehension(self.visit(n.key),
                                       self.visit(n.value),
                                       targets,
                                       iters,
                                       ifs_list)

    # GeneratorExp(expr elt, comprehension* generators)
    @with_line
    def visit_GeneratorExp(self, n: ast35.GeneratorExp) -> GeneratorExpr:
        targets = [self.visit(c.target) for c in n.generators]
        iters = [self.visit(c.iter) for c in n.generators]
        ifs_list = [self.visit_list(c.ifs) for c in n.generators]
        return GeneratorExpr(self.visit(n.elt),
                             targets,
                             iters,
                             ifs_list)

    # Await(expr value)
    @with_line
    def visit_Await(self, n: ast35.Await) -> Node:
        v = self.visit(n.value)
        return AwaitExpr(v)

    # Yield(expr? value)
    @with_line
    def visit_Yield(self, n: ast35.Yield) -> Node:
        return YieldExpr(self.visit(n.value))

    # YieldFrom(expr value)
    @with_line
    def visit_YieldFrom(self, n: ast35.YieldFrom) -> Node:
        return YieldFromExpr(self.visit(n.value))

    # Compare(expr left, cmpop* ops, expr* comparators)
    @with_line
    def visit_Compare(self, n: ast35.Compare) -> Node:
        operators = [self.from_comp_operator(o) for o in n.ops]
        operands = self.visit_list([n.left] + n.comparators)
        return ComparisonExpr(operators, operands)

    # Call(expr func, expr* args, keyword* keywords)
    # keyword = (identifier? arg, expr value)
    @with_line
    def visit_Call(self, n: ast35.Call) -> Node:
        def is_star2arg(k: ast35.keyword) -> bool:
            return k.arg is None

        arg_types = self.visit_list(
            [a.value if isinstance(a, ast35.Starred) else a for a in n.args] +
            [k.value for k in n.keywords])
        arg_kinds = ([ARG_STAR if isinstance(a, ast35.Starred) else ARG_POS for a in n.args] +
                     [ARG_STAR2 if is_star2arg(k) else ARG_NAMED for k in n.keywords])
        return CallExpr(self.visit(n.func),
                        arg_types,
                        arg_kinds,
                        cast("List[str]", [None for _ in n.args]) + [k.arg for k in n.keywords])

    # Num(object n) -- a number as a PyObject.
    @with_line
    def visit_Num(self, n: ast35.Num) -> Node:
        if isinstance(n.n, int):
            return IntExpr(n.n)
        elif isinstance(n.n, float):
            return FloatExpr(n.n)
        elif isinstance(n.n, complex):
            return ComplexExpr(n.n)

        raise RuntimeError('num not implemented for ' + str(type(n.n)))

    # Str(string s)
    @with_line
    def visit_Str(self, n: ast35.Str) -> Node:
        if self.pyversion[0] >= 3 or self.is_stub:
            # Hack: assume all string literals in Python 2 stubs are normal
            # strs (i.e. not unicode).  All stubs are parsed with the Python 3
            # parser, which causes unprefixed string literals to be interpreted
            # as unicode instead of bytes.  This hack is generally okay,
            # because mypy considers str literals to be compatible with
            # unicode.
            return StrExpr(n.s)
        else:
            return UnicodeExpr(n.s)

    # Bytes(bytes s)
    @with_line
    def visit_Bytes(self, n: ast35.Bytes) -> Node:
        # The following line is a bit hacky, but is the best way to maintain
        # compatibility with how mypy currently parses the contents of bytes literals.
        contents = str(n.s)[2:-1]

        if self.pyversion[0] >= 3:
            return BytesExpr(contents)
        else:
            return StrExpr(contents)

    # NameConstant(singleton value)
    def visit_NameConstant(self, n: ast35.NameConstant) -> Node:
        return NameExpr(str(n.value))

    # Ellipsis
    @with_line
    def visit_Ellipsis(self, n: ast35.Ellipsis) -> Node:
        return EllipsisExpr()

    # Attribute(expr value, identifier attr, expr_context ctx)
    @with_line
    def visit_Attribute(self, n: ast35.Attribute) -> Node:
        if (isinstance(n.value, ast35.Call) and
                isinstance(n.value.func, ast35.Name) and
                n.value.func.id == 'super'):
            return SuperExpr(n.attr)

        return MemberExpr(self.visit(n.value), n.attr)

    # Subscript(expr value, slice slice, expr_context ctx)
    @with_line
    def visit_Subscript(self, n: ast35.Subscript) -> Node:
        return IndexExpr(self.visit(n.value), self.visit(n.slice))

    # Starred(expr value, expr_context ctx)
    @with_line
    def visit_Starred(self, n: ast35.Starred) -> Node:
        return StarExpr(self.visit(n.value))

    # Name(identifier id, expr_context ctx)
    @with_line
    def visit_Name(self, n: ast35.Name) -> Node:
        return NameExpr(n.id)

    # List(expr* elts, expr_context ctx)
    @with_line
    def visit_List(self, n: ast35.List) -> Node:
        return ListExpr([self.visit(e) for e in n.elts])

    # Tuple(expr* elts, expr_context ctx)
    @with_line
    def visit_Tuple(self, n: ast35.Tuple) -> Node:
        return TupleExpr([self.visit(e) for e in n.elts])

    # --- slice ---

    # Slice(expr? lower, expr? upper, expr? step)
    def visit_Slice(self, n: ast35.Slice) -> Node:
        return SliceExpr(self.visit(n.lower),
                         self.visit(n.upper),
                         self.visit(n.step))

    # ExtSlice(slice* dims)
    def visit_ExtSlice(self, n: ast35.ExtSlice) -> Node:
        return TupleExpr(self.visit_list(n.dims))

    # Index(expr value)
    def visit_Index(self, n: ast35.Index) -> Node:
        return self.visit(n.value)


class TypeConverter(ast35.NodeTransformer):
    def __init__(self, line: int = -1) -> None:
        self.line = line

    def visit_raw_str(self, s: str) -> Type:
        # An escape hatch that allows the AST walker in fastparse2 to
        # directly hook into the Python 3.5 type converter in some cases
        # without needing to create an intermediary `ast35.Str` object.
        return parse_type_comment(s.strip(), line=self.line)

    def generic_visit(self, node: ast35.AST) -> None:
        raise TypeCommentParseError(TYPE_COMMENT_AST_ERROR, self.line)

    def visit_NoneType(self, n: Any) -> Type:
        return None

    def visit_list(self, l: Sequence[ast35.AST]) -> List[Type]:
        return [self.visit(e) for e in l]

    def visit_Name(self, n: ast35.Name) -> Type:
        return UnboundType(n.id, line=self.line)

    def visit_NameConstant(self, n: ast35.NameConstant) -> Type:
        return UnboundType(str(n.value))

    # Str(string s)
    def visit_Str(self, n: ast35.Str) -> Type:
        return parse_type_comment(n.s.strip(), line=self.line)

    # Subscript(expr value, slice slice, expr_context ctx)
    def visit_Subscript(self, n: ast35.Subscript) -> Type:
        assert isinstance(n.slice, ast35.Index)

        value = self.visit(n.value)

        assert isinstance(value, UnboundType)
        assert not value.args

        if isinstance(n.slice.value, ast35.Tuple):
            params = self.visit_list(n.slice.value.elts)
        else:
            params = [self.visit(n.slice.value)]

        return UnboundType(value.name, params, line=self.line)

    def visit_Tuple(self, n: ast35.Tuple) -> Type:
        return TupleType(self.visit_list(n.elts), None, implicit=True, line=self.line)

    # Attribute(expr value, identifier attr, expr_context ctx)
    def visit_Attribute(self, n: ast35.Attribute) -> Type:
        before_dot = self.visit(n.value)

        assert isinstance(before_dot, UnboundType)
        assert not before_dot.args

        return UnboundType("{}.{}".format(before_dot.name, n.attr), line=self.line)

    # Ellipsis
    def visit_Ellipsis(self, n: ast35.Ellipsis) -> Type:
        return EllipsisType(line=self.line)

    # List(expr* elts, expr_context ctx)
    def visit_List(self, n: ast35.List) -> Type:
        return TypeList(self.visit_list(n.elts), line=self.line)


class TypeCommentParseError(Exception):
    def __init__(self, msg: str, lineno: int) -> None:
        self.msg = msg
        self.lineno = lineno
