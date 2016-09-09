"""
This file is nearly identical to `fastparse.py`, except that it works with a Python 2
AST instead of a Python 3 AST.

Previously, how we handled Python 2 code was by first obtaining the Python 2 AST via
typed_ast, converting it into a Python 3 AST by using typed_ast.conversion, then
running it through mypy.fastparse.

While this worked, it did add some overhead, especially in larger Python 2 codebases.
This module allows us to skip the conversion step, saving us some time.

The reason why this file is not easily merged with mypy.fastparse despite the large amount
of redundancy is because the Python 2 AST and the Python 3 AST nodes belong to two completely
different class heirarchies, which made it difficult to write a shared visitor between the
two in a typesafe way.
"""
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
    AwaitExpr, Expression,
    ARG_POS, ARG_OPT, ARG_STAR, ARG_NAMED, ARG_STAR2
)
from mypy.types import (
    Type, CallableType, FunctionLike, AnyType, UnboundType, TupleType, TypeList, EllipsisType,
)
from mypy import defaults
from mypy import experiments
from mypy.errors import Errors
from mypy.fastparse import TypeConverter

try:
    from typed_ast import ast27
    from typed_ast import ast35
    from typed_ast import conversions
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

T = TypeVar('T', bound=Union[ast27.expr, ast27.stmt])
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
        assert pyversion[0] < 3 and not is_stub_file
        ast = ast27.parse(source, fnam, 'exec')
        tree = ASTConverter(pyversion=pyversion,
                            is_stub=is_stub_file,
                            custom_typing_module=custom_typing_module,
                            ).visit(ast)
        assert isinstance(tree, MypyFile)
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


class ASTConverter(ast27.NodeTransformer):
    def __init__(self,
                 pyversion: Tuple[int, int],
                 is_stub: bool,
                 custom_typing_module: str = None) -> None:
        self.class_nesting = 0
        self.imports = []  # type: List[ImportBase]

        self.pyversion = pyversion
        self.is_stub = is_stub
        self.custom_typing_module = custom_typing_module

    def generic_visit(self, node: ast27.AST) -> None:
        raise RuntimeError('AST node not implemented: ' + str(type(node)))

    def visit_NoneType(self, n: Any) -> Optional[Node]:
        return None

    def visit_list(self, l: Sequence[ast27.AST]) -> List[Node]:
        return [self.visit(e) for e in l]

    op_map = {
        ast27.Add: '+',
        ast27.Sub: '-',
        ast27.Mult: '*',
        ast27.Div: '/',
        ast27.Mod: '%',
        ast27.Pow: '**',
        ast27.LShift: '<<',
        ast27.RShift: '>>',
        ast27.BitOr: '|',
        ast27.BitXor: '^',
        ast27.BitAnd: '&',
        ast27.FloorDiv: '//'
    }

    def from_operator(self, op: ast27.operator) -> str:
        op_name = ASTConverter.op_map.get(type(op))
        if op_name is None:
            raise RuntimeError('Unknown operator ' + str(type(op)))
        elif op_name == '@':
            raise RuntimeError('mypy does not support the MatMult operator')
        else:
            return op_name

    comp_op_map = {
        ast27.Gt: '>',
        ast27.Lt: '<',
        ast27.Eq: '==',
        ast27.GtE: '>=',
        ast27.LtE: '<=',
        ast27.NotEq: '!=',
        ast27.Is: 'is',
        ast27.IsNot: 'is not',
        ast27.In: 'in',
        ast27.NotIn: 'not in'
    }

    def from_comp_operator(self, op: ast27.cmpop) -> str:
        op_name = ASTConverter.comp_op_map.get(type(op))
        if op_name is None:
            raise RuntimeError('Unknown comparison operator ' + str(type(op)))
        else:
            return op_name

    def as_block(self, stmts: List[ast27.stmt], lineno: int) -> Block:
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

    def visit_Module(self, mod: ast27.Module) -> Node:
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
    def visit_FunctionDef(self, n: ast27.FunctionDef) -> Node:
        converter = TypeConverter(line=n.lineno)
        args = self.transform_args(n.args, n.lineno)

        arg_kinds = [arg.kind for arg in args]
        arg_names = [arg.variable.name() for arg in args]
        arg_types = None  # type: List[Type]
        if n.type_comment is not None and len(n.type_comment) > 0:
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
                            a in converter.visit_list(func_type_ast.argtypes)]
            return_type = converter.visit(func_type_ast.returns)

            # add implicit self type
            if self.in_class() and len(arg_types) < len(args):
                arg_types.insert(0, AnyType())
        else:
            arg_types = [a.type_annotation for a in args]
            return_type = converter.visit(None)

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

    def transform_args(self, n: ast27.arguments, line: int) -> List[Argument]:
        # TODO: remove the cast once https://github.com/python/typeshed/pull/522
        # is accepted and synced
        type_comments = cast(List[str], n.type_comments)  # type: ignore
        converter = TypeConverter(line=line)

        def convert_arg(arg: ast27.expr) -> Var:
            if isinstance(arg, ast27.Name):
                v = arg.id
            elif isinstance(arg, ast27.Tuple):
                # TODO: An `arg` object may be a Tuple instead of just an identifier in the
                # case of Python 2 function definitions/lambdas that use the tuple unpacking
                # syntax. The `typed_ast.conversions` module ended up just simply passing the
                # the arg object unmodified (instead of converting it into more args, etc).
                # This isn't typesafe, since we will no longer be always passing in a string
                # to `Var`, but we'll do the same here for consistency.
                v = arg  # type: ignore
            else:
                raise RuntimeError("'{}' is not a valid argument.".format(ast27.dump(arg)))
            return Var(v)

        def get_type(i: int) -> Optional[Type]:
            if i < len(type_comments) and type_comments[i] is not None:
                return converter.visit_raw_str(type_comments[i])
            return None

        args = [(convert_arg(arg), get_type(i)) for i, arg in enumerate(n.args)]
        defaults = self.visit_list(n.defaults)

        new_args = []  # type: List[Argument]
        num_no_defaults = len(args) - len(defaults)
        # positional arguments without defaults
        for a, annotation in args[:num_no_defaults]:
            new_args.append(Argument(a, annotation, None, ARG_POS))

        # positional arguments with defaults
        for (a, annotation), d in zip(args[num_no_defaults:], defaults):
            new_args.append(Argument(a, annotation, d, ARG_OPT))

        # *arg
        if n.vararg is not None:
            new_args.append(Argument(Var(n.vararg), get_type(len(args)), None, ARG_STAR))

        # **kwarg
        if n.kwarg is not None:
            typ = get_type(len(args) + (0 if n.vararg is None else 1))
            new_args.append(Argument(Var(n.kwarg), typ, None, ARG_STAR2))

        return new_args

    def stringify_name(self, n: ast27.AST) -> str:
        if isinstance(n, ast27.Name):
            return n.id
        elif isinstance(n, ast27.Attribute):
            return "{}.{}".format(self.stringify_name(n.value), n.attr)
        else:
            assert False, "can't stringify " + str(type(n))

    # ClassDef(identifier name,
    #  expr* bases,
    #  keyword* keywords,
    #  stmt* body,
    #  expr* decorator_list)
    @with_line
    def visit_ClassDef(self, n: ast27.ClassDef) -> Node:
        self.class_nesting += 1

        cdef = ClassDef(n.name,
                        self.as_block(n.body, n.lineno),
                        None,
                        self.visit_list(n.bases),
                        metaclass=None)
        cdef.decorators = self.visit_list(n.decorator_list)
        self.class_nesting -= 1
        return cdef

    # Return(expr? value)
    @with_line
    def visit_Return(self, n: ast27.Return) -> Node:
        return ReturnStmt(self.visit(n.value))

    # Delete(expr* targets)
    @with_line
    def visit_Delete(self, n: ast27.Delete) -> Node:
        if len(n.targets) > 1:
            tup = TupleExpr(self.visit_list(n.targets))
            tup.set_line(n.lineno)
            return DelStmt(tup)
        else:
            return DelStmt(self.visit(n.targets[0]))

    # Assign(expr* targets, expr value, string? type_comment)
    @with_line
    def visit_Assign(self, n: ast27.Assign) -> Node:
        typ = None
        if n.type_comment:
            typ = parse_type_comment(n.type_comment, n.lineno)

        return AssignmentStmt(self.visit_list(n.targets),
                              self.visit(n.value),
                              type=typ)

    # AugAssign(expr target, operator op, expr value)
    @with_line
    def visit_AugAssign(self, n: ast27.AugAssign) -> Node:
        return OperatorAssignmentStmt(self.from_operator(n.op),
                              self.visit(n.target),
                              self.visit(n.value))

    # For(expr target, expr iter, stmt* body, stmt* orelse, string? type_comment)
    @with_line
    def visit_For(self, n: ast27.For) -> Node:
        return ForStmt(self.visit(n.target),
                       self.visit(n.iter),
                       self.as_block(n.body, n.lineno),
                       self.as_block(n.orelse, n.lineno))

    # While(expr test, stmt* body, stmt* orelse)
    @with_line
    def visit_While(self, n: ast27.While) -> Node:
        return WhileStmt(self.visit(n.test),
                         self.as_block(n.body, n.lineno),
                         self.as_block(n.orelse, n.lineno))

    # If(expr test, stmt* body, stmt* orelse)
    @with_line
    def visit_If(self, n: ast27.If) -> Node:
        return IfStmt([self.visit(n.test)],
                      [self.as_block(n.body, n.lineno)],
                      self.as_block(n.orelse, n.lineno))

    # With(withitem* items, stmt* body, string? type_comment)
    @with_line
    def visit_With(self, n: ast27.With) -> Node:
        return WithStmt([self.visit(n.context_expr)],
                        [self.visit(n.optional_vars)],
                        self.as_block(n.body, n.lineno))

    @with_line
    def visit_Raise(self, n: ast27.Raise) -> Node:
        e = None
        if n.type is not None:
            e = n.type

            if n.inst is not None and not (isinstance(n.inst, ast27.Name) and n.inst.id == "None"):
                if isinstance(n.inst, ast27.Tuple):
                    args = n.inst.elts
                else:
                    args = [n.inst]
                e = ast27.Call(e, args, [], None, None, lineno=e.lineno, col_offset=-1)

        return RaiseStmt(self.visit(e), None)

    # TryExcept(stmt* body, excepthandler* handlers, stmt* orelse)
    @with_line
    def visit_TryExcept(self, n: ast27.TryExcept) -> Node:
        return self.try_handler(n.body, n.handlers, n.orelse, [], n.lineno)

    @with_line
    def visit_TryFinally(self, n: ast27.TryFinally) -> Node:
        if len(n.body) == 1 and isinstance(n.body[0], ast27.TryExcept):
            return self.try_handler([n.body[0]], [], [], n.finalbody, n.lineno)
        else:
            return self.try_handler(n.body, [], [], n.finalbody, n.lineno)

    def try_handler(self,
                    body: List[ast27.stmt],
                    handlers: List[ast27.ExceptHandler],
                    orelse: List[ast27.stmt],
                    finalbody: List[ast27.stmt],
                    lineno: int) -> Node:
        def produce_name(item: ast27.ExceptHandler) -> Optional[NameExpr]:
            if item.name is None:
                return None
            elif isinstance(item.name, ast27.Name):
                return NameExpr(item.name.id)
            else:
                raise RuntimeError("'{}' has non-Name name.".format(ast27.dump(item)))

        vs = [produce_name(h) for h in handlers]
        types = [self.visit(h.type) for h in handlers]
        handlers_ = [self.as_block(h.body, h.lineno) for h in handlers]

        return TryStmt(self.as_block(body, lineno),
                       vs,
                       types,
                       handlers_,
                       self.as_block(orelse, lineno),
                       self.as_block(finalbody, lineno))

    @with_line
    def visit_Print(self, n: ast27.Print) -> Node:
        keywords = []
        if n.dest is not None:
            keywords.append(ast27.keyword("file", n.dest))

        if not n.nl:
            keywords.append(ast27.keyword("end", ast27.Str(" ", lineno=n.lineno, col_offset=-1)))

        # TODO: Rather then desugaring Print into an intermediary ast27.Call object, it might
        # be more efficient to just directly create a mypy.node.CallExpr object.
        call = ast27.Call(
            ast27.Name("print", ast27.Load(), lineno=n.lineno, col_offset=-1),
            n.values, keywords, None, None,
            lineno=n.lineno, col_offset=-1)
        return self.visit(ast27.Expr(call, lineno=n.lineno, col_offset=-1))

    @with_line
    def visit_Exec(self, n: ast27.Exec) -> Node:
        new_globals = n.globals
        new_locals = n.locals

        if new_globals is None:
            new_globals = ast27.Name("None", ast27.Load(), lineno=-1, col_offset=-1)
        if new_locals is None:
            new_locals = ast27.Name("None", ast27.Load(), lineno=-1, col_offset=-1)

        # TODO: Comment in visit_Print also applies here
        return self.visit(ast27.Expr(
            ast27.Call(
                ast27.Name("exec", ast27.Load(), lineno=n.lineno, col_offset=-1),
                [n.body, new_globals, new_locals],
                [], None, None,
                lineno=n.lineno, col_offset=-1),
            lineno=n.lineno, col_offset=-1))

    @with_line
    def visit_Repr(self, n: ast27.Repr) -> Node:
        # TODO: Comment in visit_Print also applies here
        return self.visit(ast27.Call(
            ast27.Name("repr", ast27.Load(), lineno=n.lineno, col_offset=-1),
            n.value,
            [], None, None,
            lineno=n.lineno, col_offset=-1))

    # Assert(expr test, expr? msg)
    @with_line
    def visit_Assert(self, n: ast27.Assert) -> Node:
        return AssertStmt(self.visit(n.test))

    # Import(alias* names)
    @with_line
    def visit_Import(self, n: ast27.Import) -> Node:
        i = Import([(self.translate_module_id(a.name), a.asname) for a in n.names])
        self.imports.append(i)
        return i

    # ImportFrom(identifier? module, alias* names, int? level)
    @with_line
    def visit_ImportFrom(self, n: ast27.ImportFrom) -> Node:
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
    def visit_Global(self, n: ast27.Global) -> Node:
        return GlobalDecl(n.names)

    # Expr(expr value)
    @with_line
    def visit_Expr(self, n: ast27.Expr) -> Node:
        value = self.visit(n.value)
        return ExpressionStmt(value)

    # Pass
    @with_line
    def visit_Pass(self, n: ast27.Pass) -> Node:
        return PassStmt()

    # Break
    @with_line
    def visit_Break(self, n: ast27.Break) -> Node:
        return BreakStmt()

    # Continue
    @with_line
    def visit_Continue(self, n: ast27.Continue) -> Node:
        return ContinueStmt()

    # --- expr ---
    # BoolOp(boolop op, expr* values)
    @with_line
    def visit_BoolOp(self, n: ast27.BoolOp) -> Node:
        # mypy translates (1 and 2 and 3) as (1 and (2 and 3))
        assert len(n.values) >= 2
        op = None
        if isinstance(n.op, ast27.And):
            op = 'and'
        elif isinstance(n.op, ast27.Or):
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
    def visit_BinOp(self, n: ast27.BinOp) -> Node:
        op = self.from_operator(n.op)

        if op is None:
            raise RuntimeError('cannot translate BinOp ' + str(type(n.op)))

        return OpExpr(op, self.visit(n.left), self.visit(n.right))

    # UnaryOp(unaryop op, expr operand)
    @with_line
    def visit_UnaryOp(self, n: ast27.UnaryOp) -> Node:
        op = None
        if isinstance(n.op, ast27.Invert):
            op = '~'
        elif isinstance(n.op, ast27.Not):
            op = 'not'
        elif isinstance(n.op, ast27.UAdd):
            op = '+'
        elif isinstance(n.op, ast27.USub):
            op = '-'

        if op is None:
            raise RuntimeError('cannot translate UnaryOp ' + str(type(n.op)))

        return UnaryExpr(op, self.visit(n.operand))

    # Lambda(arguments args, expr body)
    @with_line
    def visit_Lambda(self, n: ast27.Lambda) -> Node:
        body = ast27.Return(n.body)
        body.lineno = n.lineno

        return FuncExpr(self.transform_args(n.args, n.lineno),
                        self.as_block([body], n.lineno))

    # IfExp(expr test, expr body, expr orelse)
    @with_line
    def visit_IfExp(self, n: ast27.IfExp) -> Node:
        return ConditionalExpr(self.visit(n.test),
                               self.visit(n.body),
                               self.visit(n.orelse))

    # Dict(expr* keys, expr* values)
    @with_line
    def visit_Dict(self, n: ast27.Dict) -> Node:
        return DictExpr(list(zip(self.visit_list(n.keys), self.visit_list(n.values))))

    # Set(expr* elts)
    @with_line
    def visit_Set(self, n: ast27.Set) -> Node:
        return SetExpr(self.visit_list(n.elts))

    # ListComp(expr elt, comprehension* generators)
    @with_line
    def visit_ListComp(self, n: ast27.ListComp) -> Node:
        return ListComprehension(self.visit_GeneratorExp(cast(ast27.GeneratorExp, n)))

    # SetComp(expr elt, comprehension* generators)
    @with_line
    def visit_SetComp(self, n: ast27.SetComp) -> Node:
        return SetComprehension(self.visit_GeneratorExp(cast(ast27.GeneratorExp, n)))

    # DictComp(expr key, expr value, comprehension* generators)
    @with_line
    def visit_DictComp(self, n: ast27.DictComp) -> Node:
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
    def visit_GeneratorExp(self, n: ast27.GeneratorExp) -> GeneratorExpr:
        targets = [self.visit(c.target) for c in n.generators]
        iters = [self.visit(c.iter) for c in n.generators]
        ifs_list = [self.visit_list(c.ifs) for c in n.generators]
        return GeneratorExpr(self.visit(n.elt),
                             targets,
                             iters,
                             ifs_list)

    # Yield(expr? value)
    @with_line
    def visit_Yield(self, n: ast27.Yield) -> Node:
        return YieldExpr(self.visit(n.value))

    # Compare(expr left, cmpop* ops, expr* comparators)
    @with_line
    def visit_Compare(self, n: ast27.Compare) -> Node:
        operators = [self.from_comp_operator(o) for o in n.ops]
        operands = self.visit_list([n.left] + n.comparators)
        return ComparisonExpr(operators, operands)

    # Call(expr func, expr* args, keyword* keywords)
    # keyword = (identifier? arg, expr value)
    @with_line
    def visit_Call(self, n: ast27.Call) -> Node:
        arg_types = []  # type: List[ast27.expr]
        arg_kinds = []  # type: List[int]
        signature = []  # type: List[Optional[str]]

        arg_types.extend(n.args)
        arg_kinds.extend(ARG_POS for a in n.args)
        signature.extend(None for a in n.args)

        if n.starargs is not None:
            arg_types.append(n.starargs)
            arg_kinds.append(ARG_STAR)
            signature.append(None)

        arg_types.extend(k.value for k in n.keywords)
        arg_kinds.extend(ARG_NAMED for k in n.keywords)
        signature.extend(k.arg for k in n.keywords)

        if n.kwargs is not None:
            arg_types.append(n.kwargs)
            arg_kinds.append(ARG_STAR2)
            signature.append(None)

        return CallExpr(self.visit(n.func),
                        self.visit_list(arg_types),
                        arg_kinds,
                        cast("List[str]", signature))

    # Num(object n) -- a number as a PyObject.
    @with_line
    def visit_Num(self, new: ast27.Num) -> Node:
        value = new.n
        is_inverse = False
        if new.n < 0:
            value = -new.n
            is_inverse = True

        expr = None  # type: Expression
        if isinstance(value, int):
            expr = IntExpr(value)
        elif isinstance(value, float):
            expr = FloatExpr(value)
        elif isinstance(value, complex):
            expr = ComplexExpr(value)
        else:
            raise RuntimeError('num not implemented for ' + str(type(new.n)))

        if is_inverse:
            expr = UnaryExpr('-', expr)

        return expr

    # Str(string s)
    @with_line
    def visit_Str(self, s: ast27.Str) -> Node:
        # Hack: assume all string literals in Python 2 stubs are normal
        # strs (i.e. not unicode).  All stubs are parsed with the Python 3
        # parser, which causes unprefixed string literals to be interpreted
        # as unicode instead of bytes.  This hack is generally okay,
        # because mypy considers str literals to be compatible with
        # unicode.
        if isinstance(s.s, bytes):
            n = s.s
            # The following line is a bit hacky, but is the best way to maintain
            # compatibility with how mypy currently parses the contents of bytes literals.
            contents = str(n)[2:-1]

            if self.pyversion[0] >= 3:
                return BytesExpr(contents)
            else:
                return StrExpr(contents)
        else:
            if self.pyversion[0] >= 3 or self.is_stub:
                return StrExpr(s.s)
            else:
                return UnicodeExpr(s.s)

    # Ellipsis
    def visit_Ellipsis(self, n: ast27.Ellipsis) -> Node:
        return EllipsisExpr()

    # Attribute(expr value, identifier attr, expr_context ctx)
    @with_line
    def visit_Attribute(self, n: ast27.Attribute) -> Node:
        if (isinstance(n.value, ast27.Call) and
                isinstance(n.value.func, ast27.Name) and
                n.value.func.id == 'super'):
            return SuperExpr(n.attr)

        return MemberExpr(self.visit(n.value), n.attr)

    # Subscript(expr value, slice slice, expr_context ctx)
    @with_line
    def visit_Subscript(self, n: ast27.Subscript) -> Node:
        return IndexExpr(self.visit(n.value), self.visit(n.slice))

    # Name(identifier id, expr_context ctx)
    @with_line
    def visit_Name(self, n: ast27.Name) -> Node:
        return NameExpr(n.id)

    # List(expr* elts, expr_context ctx)
    @with_line
    def visit_List(self, n: ast27.List) -> Node:
        return ListExpr([self.visit(e) for e in n.elts])

    # Tuple(expr* elts, expr_context ctx)
    @with_line
    def visit_Tuple(self, n: ast27.Tuple) -> Node:
        return TupleExpr([self.visit(e) for e in n.elts])

    # --- slice ---

    # Slice(expr? lower, expr? upper, expr? step)
    def visit_Slice(self, n: ast27.Slice) -> Node:
        return SliceExpr(self.visit(n.lower),
                         self.visit(n.upper),
                         self.visit(n.step))

    # ExtSlice(slice* dims)
    def visit_ExtSlice(self, n: ast27.ExtSlice) -> Node:
        return TupleExpr(self.visit_list(n.dims))

    # Index(expr value)
    def visit_Index(self, n: ast27.Index) -> Node:
        return self.visit(n.value)


class TypeCommentParseError(Exception):
    def __init__(self, msg: str, lineno: int) -> None:
        self.msg = msg
        self.lineno = lineno
