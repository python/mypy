"""Mypy parser.

Constructs a parse tree (abstract syntax tree) based on a string
representing a source file. Performs only minimal semantic checks.
"""

import re

from typing import Undefined, List, Tuple, Any, Set, cast

from mypy import lex
from mypy.lex import (
    Token, Eof, Bom, Break, Name, Colon, Dedent, IntLit, StrLit, BytesLit,
    UnicodeLit, FloatLit, Op, Indent, Keyword, Punct, LexError
)
import mypy.types
from mypy.nodes import (
    MypyFile, Import, Node, ImportAll, ImportFrom, FuncDef, OverloadedFuncDef,
    ClassDef, Decorator, Block, Var, VarDef, OperatorAssignmentStmt,
    ExpressionStmt, AssignmentStmt, ReturnStmt, RaiseStmt, AssertStmt,
    YieldStmt, DelStmt, BreakStmt, ContinueStmt, PassStmt, GlobalDecl,
    WhileStmt, ForStmt, IfStmt, TryStmt, WithStmt, CastExpr, ParenExpr,
    TupleExpr, GeneratorExpr, ListComprehension, ListExpr, ConditionalExpr,
    DictExpr, SetExpr, NameExpr, IntExpr, StrExpr, BytesExpr, UnicodeExpr,
    FloatExpr, CallExpr, SuperExpr, MemberExpr, IndexExpr, SliceExpr, OpExpr,
    UnaryExpr, FuncExpr, TypeApplication, PrintStmt, ImportBase, ComparisonExpr
)
from mypy import nodes
from mypy import noderepr
from mypy.errors import Errors, CompileError
from mypy.types import Void, Type, Callable, AnyType, UnboundType
from mypy.parsetype import (
    parse_type, parse_types, parse_signature, TypeParseError
)


precedence = {
    '**': 16,
    '-u': 15, '+u': 15, '~': 15,   # unary operators (-, + and ~)
    '<cast>': 14,
    '*': 13, '/': 13, '//': 13, '%': 13,
    '+': 12, '-': 12,
    '>>': 11, '<<': 11,
    '&': 10,
    '^': 9,
    '|': 8,
    '==': 7, '!=': 7, '<': 7, '>': 7, '<=': 7, '>=': 7, 'is': 7, 'in': 7,
    'not': 6,
    'and': 5,
    'or': 4,
    '<if>': 3,  # conditional expression
    '<for>': 2,  # list comprehension
    ',': 1}


op_assign = set([
    '+=', '-=', '*=', '/=', '//=', '%=', '**=', '|=', '&=', '^=', '>>=',
    '<<='])

op_comp = set([
    '>', '<', '==', '>=', '<=', '<>', '!=', 'is', 'is', 'in', 'not'])

none = Token('')  # Empty token


def parse(s: str, fnam: str = None, errors: Errors = None,
          pyversion: int = 3, custom_typing_module: str = None) -> MypyFile:
    """Parse a source file, without doing any semantic analysis.

    Return the parse tree. If errors is not provided, raise ParseError
    on failure. Otherwise, use the errors object to report parse errors.

    The pyversion argument determines the Python syntax variant (2 for 2.x and
    3 for 3.x).
    """
    parser = Parser(fnam, errors, pyversion, custom_typing_module)
    tree = parser.parse(s)
    tree.path = fnam
    return tree


class Parser:
    tok = Undefined(List[Token])
    ind = 0
    errors = Undefined(Errors)
    raise_on_error = False

    # Are we currently parsing the body of a class definition?
    is_class_body = False
    # All import nodes encountered so far in this parse unit.
    imports = Undefined(List[ImportBase])
    # Names imported from __future__.
    future_options = Undefined(List[str])

    def __init__(self, fnam: str, errors: Errors, pyversion: int,
                 custom_typing_module: str = None) -> None:
        self.raise_on_error = errors is None
        self.pyversion = pyversion
        self.custom_typing_module = custom_typing_module
        if errors is not None:
            self.errors = errors
        else:
            self.errors = Errors()
        if fnam is not None:
            self.errors.set_file(fnam)
        else:
            self.errors.set_file('<input>')

    def parse(self, s: str) -> MypyFile:
        self.tok = lex.lex(s)
        self.ind = 0
        self.imports = []
        self.future_options = []
        file = self.parse_file()
        if self.raise_on_error and self.errors.is_errors():
            self.errors.raise_error()
        return file

    def parse_file(self) -> MypyFile:
        """Parse a mypy source file."""
        is_bom = self.parse_bom()
        defs = self.parse_defs()
        eof = self.expect_type(Eof)
        node = MypyFile(defs, self.imports, is_bom)
        self.set_repr(node, noderepr.MypyFileRepr(eof))
        return node

    # Parse the initial part

    def parse_bom(self) -> bool:
        """Parse the optional byte order mark at the beginning of a file."""
        if isinstance(self.current(), Bom):
            self.expect_type(Bom)
            if isinstance(self.current(), Break):
                self.expect_break()
            return True
        else:
            return False

    def parse_import(self) -> Import:
        import_tok = self.expect('import')
        ids = List[Tuple[str, str]]()
        id_toks = List[List[Token]]()
        commas = List[Token]()
        as_names = List[Tuple[Token, Token]]()
        while True:
            id, components = self.parse_qualified_name()
            if id == self.custom_typing_module:
                id = 'typing'
            id_toks.append(components)
            as_id = id
            if self.current_str() == 'as':
                as_tok = self.expect('as')
                name_tok = self.expect_type(Name)
                as_id = name_tok.string
                as_names.append((as_tok, name_tok))
            else:
                as_names.append(None)
            ids.append((id, as_id))
            if self.current_str() != ',':
                break
            commas.append(self.expect(','))
        br = self.expect_break()
        node = Import(ids)
        self.imports.append(node)
        self.set_repr(node, noderepr.ImportRepr(import_tok, id_toks, as_names,
                                                commas, br))
        return node

    def parse_import_from(self) -> Node:
        from_tok = self.expect('from')
        name, components = self.parse_qualified_name()
        if name == self.custom_typing_module:
            name = 'typing'
        import_tok = self.expect('import')
        name_toks = List[Tuple[List[Token], Token]]()
        lparen = none
        rparen = none
        node = None  # type: ImportBase
        if self.current_str() == '*':
            name_toks.append(([self.skip()], none))
            node = ImportAll(name)
        else:
            is_paren = self.current_str() == '('
            if is_paren:
                lparen = self.expect('(')
            targets = List[Tuple[str, str]]()
            while True:
                id, as_id, toks = self.parse_import_name()
                if '%s.%s' % (name, id) == self.custom_typing_module:
                    if targets or self.current_str() == ',':
                        self.fail('You cannot import any other modules when you '
                                  'import a custom typing module',
                                  toks[0].line)
                    node = Import([('typing', as_id)])
                    self.skip_until_break()
                    break
                targets.append((id, as_id))
                if self.current_str() != ',':
                    name_toks.append((toks, none))
                    break
                name_toks.append((toks, self.expect(',')))
                if is_paren and self.current_str() == ')':
                    break
            if is_paren:
                rparen = self.expect(')')
            if node is None:
                node = ImportFrom(name, targets)
        br = self.expect_break()
        self.imports.append(node)
        # TODO: Fix representation if there is a custom typing module import.
        self.set_repr(node, noderepr.ImportFromRepr(
            from_tok, components, import_tok, lparen, name_toks, rparen, br))
        if name == '__future__':
            self.future_options.extend(target[0] for target in targets)
        return node

    def parse_import_name(self) -> Tuple[str, str, List[Token]]:
        tok = self.expect_type(Name)
        name = tok.string
        tokens = [tok]
        if self.current_str() == 'as':
            tokens.append(self.skip())
            as_name = self.expect_type(Name)
            tokens.append(as_name)
            return name, as_name.string, tokens
        else:
            return name, name, tokens

    def parse_qualified_name(self) -> Tuple[str, List[Token]]:
        """Parse a name with an optional module qualifier.

        Return a tuple with the name as a string and a token array
        containing all the components of the name.
        """
        components = List[Token]()
        tok = self.expect_type(Name)
        n = tok.string
        components.append(tok)
        while self.current_str() == '.':
            components.append(self.expect('.'))
            tok = self.expect_type(Name)
            n += '.' + tok.string
            components.append(tok)
        return n, components

    # Parsing global definitions

    def parse_defs(self) -> List[Node]:
        defs = List[Node]()
        while not self.eof():
            try:
                defn = self.parse_statement()
                if defn is not None:
                    if not self.try_combine_overloads(defn, defs):
                        defs.append(defn)
            except ParseError:
                pass
        return defs

    def parse_class_def(self) -> ClassDef:
        old_is_class_body = self.is_class_body
        self.is_class_body = True

        type_tok = self.expect('class')
        lparen = none
        rparen = none
        metaclass = None  # type: str

        try:
            commas, base_types = List[Token](), List[Type]()
            try:
                name_tok = self.expect_type(Name)
                name = name_tok.string

                self.errors.push_type(name)

                if self.current_str() == '(':
                    lparen = self.skip()
                    while True:
                        if self.current_str() == ')':
                            break
                        if self.current_str() == 'metaclass':
                            metaclass = self.parse_metaclass()
                            break
                        base_types.append(self.parse_super_type())
                        if self.current_str() != ',':
                            break
                        commas.append(self.skip())
                    rparen = self.expect(')')
            except ParseError:
                pass

            defs, _ = self.parse_block()

            node = ClassDef(name, defs, None, base_types, metaclass=metaclass)
            self.set_repr(node, noderepr.TypeDefRepr(type_tok, name_tok,
                                                     lparen, commas, rparen))
            return node
        finally:
            self.errors.pop_type()
            self.is_class_body = old_is_class_body

    def parse_super_type(self) -> Type:
        if (isinstance(self.current(), Name) and self.current_str() != 'void'):
            return self.parse_type()
        else:
            self.parse_error()

    def parse_metaclass(self) -> str:
        self.expect('metaclass')
        self.expect('=')
        return self.parse_qualified_name()[0]

    def parse_decorated_function_or_class(self) -> Node:
        ats = List[Token]()
        brs = List[Token]()
        decorators = List[Node]()
        while self.current_str() == '@':
            ats.append(self.expect('@'))
            decorators.append(self.parse_expression())
            brs.append(self.expect_break())
        if self.current_str() != 'class':
            func = self.parse_function()
            func.is_decorated = True
            var = Var(func.name())
            # Types of decorated functions must always be inferred.
            var.is_ready = False
            var.set_line(decorators[0].line)
            node = Decorator(func, decorators, var)
            self.set_repr(node, noderepr.DecoratorRepr(ats, brs))
            return node
        else:
            cls = self.parse_class_def()
            cls.decorators = decorators
            return cls

    def parse_function(self) -> FuncDef:
        def_tok = self.expect('def')
        is_method = self.is_class_body
        self.is_class_body = False
        try:
            (name, args, init, kinds,
             typ, is_error, toks) = self.parse_function_header()

            body, comment_type = self.parse_block(allow_type=True)
            if comment_type:
                # The function has a # type: ... signature.
                if typ:
                    self.errors.report(
                        def_tok.line, 'Function has duplicate type signatures')
                sig = cast(Callable, comment_type)
                if is_method:
                    self.check_argument_kinds(kinds,
                                              [nodes.ARG_POS] + sig.arg_kinds,
                                              def_tok.line)
                    # Add implicit 'self' argument to signature.
                    typ = Callable(List[Type]([AnyType()]) + sig.arg_types,
                                   kinds,
                                   [arg.name() for arg in args],
                                   sig.ret_type,
                                   None)
                else:
                    self.check_argument_kinds(kinds, sig.arg_kinds,
                                              def_tok.line)
                    typ = Callable(sig.arg_types,
                                   kinds,
                                   [arg.name() for arg in args],
                                   sig.ret_type,
                                   None)

            # If there was a serious error, we really cannot build a parse tree
            # node.
            if is_error:
                return None

            node = FuncDef(name, args, kinds, init, body, typ)
            name_tok, arg_reprs = toks
            node.set_line(name_tok)
            self.set_repr(node, noderepr.FuncRepr(def_tok, name_tok,
                                                  arg_reprs))
            return node
        finally:
            self.errors.pop_function()
            self.is_class_body = is_method

    def check_argument_kinds(self, funckinds: List[int], sigkinds: List[int],
                             line: int) -> None:
        """Check that * and ** arguments are consistent.

        Arguments:
          funckinds: kinds of arguments in function definition
          sigkinds:  kinds of arguments in signature (after # type:)
        """
        for kind, token in [(nodes.ARG_STAR, '*'),
                            (nodes.ARG_STAR2, '**')]:
            if ((kind in funckinds and
                 sigkinds[funckinds.index(kind)] != kind) or
                    (funckinds.count(kind) != sigkinds.count(kind))):
                self.fail(
                    "Inconsistent use of '{}' in function "
                    "signature".format(token), line)

    def parse_function_header(self) -> Tuple[str, List[Var], List[Node],
                                             List[int], Callable, bool,
                                             Tuple[Token, Any]]:
        """Parse function header (a name followed by arguments)

        Returns a 7-tuple with the following items:
          name
          arguments
          initializers
          kinds
          signature (annotation)
          error flag (True if error)
          (name token, representation of arguments)
        """
        name_tok = none

        try:
            name_tok = self.expect_type(Name)
            name = name_tok.string

            self.errors.push_function(name)

            (args, init, kinds, typ, arg_repr) = self.parse_args()
        except ParseError:
            if not isinstance(self.current(), Break):
                self.ind -= 1  # Kludge: go back to the Break token
            # Resynchronise parsing by going back over :, if present.
            if isinstance(self.tok[self.ind - 1], Colon):
                self.ind -= 1
            return (name, [], [], [], None, True, (name_tok, None))

        return (name, args, init, kinds, typ, False, (name_tok, arg_repr))

    def parse_args(self) -> Tuple[List[Var], List[Node], List[int], Callable,
                                  noderepr.FuncArgsRepr]:
        """Parse a function signature (...) [-> t]."""
        lparen = self.expect('(')

        # Parse the argument list (everything within '(' and ')').
        (args, init, kinds,
         has_inits, arg_names,
         commas, asterisk,
         assigns, arg_types) = self.parse_arg_list()

        rparen = self.expect(')')

        if self.current_str() == '->':
            self.skip()
            ret_type = self.parse_type()
        else:
            ret_type = None

        self.verify_argument_kinds(kinds, lparen.line)

        names = []  # type: List[str]
        for arg in args:
            names.append(arg.name())

        annotation = self.build_func_annotation(
            ret_type, arg_types, kinds, names, lparen.line)

        return (args, init, kinds, annotation,
                noderepr.FuncArgsRepr(lparen, rparen, arg_names, commas,
                                      assigns, asterisk))

    def build_func_annotation(self, ret_type: Type, arg_types: List[Type],
                              kinds: List[int], names: List[str],
                              line: int, is_default_ret: bool = False) -> Callable:
        # Are there any type annotations?
        if ((ret_type and not is_default_ret)
                or arg_types != [None] * len(arg_types)):
            # Yes. Construct a type for the function signature.
            return self.construct_function_type(arg_types, kinds, names,
                                                ret_type, line)
        else:
            return None

    def parse_arg_list(
        self, allow_signature: bool = True) -> Tuple[List[Var], List[Node],
                                                     List[int], bool,
                                                     List[Token], List[Token],
                                                     List[Token], List[Token],
                                                     List[Type]]:
        """Parse function definition argument list.

        This includes everything between '(' and ')').

        Return a 9-tuple with these items:
          arguments, initializers, kinds, has inits, arg name tokens,
          comma tokens, asterisk tokens, assignment tokens, argument types
        """
        args = []   # type: List[Var]
        kinds = []  # type: List[int]
        names = []  # type: List[str]
        init = []   # type: List[Node]
        has_inits = False
        arg_types = []  # type: List[Type]

        arg_names = []  # type: List[Token]
        commas = []     # type: List[Token]
        asterisk = []   # type: List[Token]
        assigns = []    # type: List[Token]

        require_named = False
        bare_asterisk_before = -1

        if self.current_str() != ')' and self.current_str() != ':':
            while self.current_str() != ')':
                if self.current_str() == '*' and self.peek().string == ',':
                    if require_named:
                        # can only have one bare star, must be before any
                        # *args or **args
                        self.parse_error()
                    self.expect('*')
                    require_named = True
                    bare_asterisk_before = len(args)
                elif self.current_str() in ['*', '**']:
                    if bare_asterisk_before == len(args):
                        # named arguments must follow bare *
                        self.parse_error()
                    asterisk.append(self.skip())
                    isdict = asterisk[-1].string == '**'
                    name = self.expect_type(Name)
                    arg_names.append(name)
                    names.append(name.string)
                    var_arg = Var(name.string)
                    self.set_repr(var_arg, noderepr.VarRepr(name, none))
                    args.append(var_arg)
                    init.append(None)
                    assigns.append(none)
                    if isdict:
                        kinds.append(nodes.ARG_STAR2)
                    else:
                        kinds.append(nodes.ARG_STAR)
                    arg_types.append(self.parse_arg_type(allow_signature))
                    require_named = True
                else:
                    name = self.expect_type(Name)
                    arg_names.append(name)
                    args.append(Var(name.string))
                    arg_types.append(self.parse_arg_type(allow_signature))

                    if self.current_str() == '=':
                        assigns.append(self.expect('='))
                        init.append(self.parse_expression(precedence[',']))
                        has_inits = True
                        if require_named:
                            kinds.append(nodes.ARG_NAMED)
                        else:
                            kinds.append(nodes.ARG_OPT)
                    else:
                        init.append(None)
                        assigns.append(none)
                        if require_named:
                            # required keyword-only argument
                            kinds.append(nodes.ARG_NAMED)
                        else:
                            kinds.append(nodes.ARG_POS)

                if self.current().string != ',':
                    break
                commas.append(self.expect(','))

        return (args, init, kinds, has_inits, arg_names, commas, asterisk,
                assigns, arg_types)

    def parse_arg_type(self, allow_signature: bool) -> Type:
        if self.current_str() == ':' and allow_signature:
            self.skip()
            return self.parse_type()
        else:
            return None

    def verify_argument_kinds(self, kinds: List[int], line: int) -> None:
        found = Set[int]()
        for i, kind in enumerate(kinds):
            if kind == nodes.ARG_POS and found & set([nodes.ARG_OPT,
                                                      nodes.ARG_STAR,
                                                      nodes.ARG_STAR2]):
                self.fail('Invalid argument list', line)
            elif kind == nodes.ARG_STAR and nodes.ARG_STAR in found:
                self.fail('Invalid argument list', line)
            elif kind == nodes.ARG_STAR2 and i != len(kinds) - 1:
                self.fail('Invalid argument list', line)
            found.add(kind)

    def construct_function_type(self, arg_types: List[Type], kinds: List[int],
                                names: List[str], ret_type: Type,
                                line: int) -> Callable:
        # Complete the type annotation by replacing omitted types with 'Any'.
        arg_types = arg_types[:]
        for i in range(len(arg_types)):
            if arg_types[i] is None:
                arg_types[i] = AnyType()
        if ret_type is None:
            ret_type = AnyType()
        return Callable(arg_types, kinds, names, ret_type, None, None,
                        None, [], line, None)

    # Parsing statements

    def parse_block(self, allow_type: bool = False) -> Tuple[Block, Type]:
        colon = self.expect(':')
        if not isinstance(self.current(), Break):
            # Block immediately after ':'.
            node = Block([self.parse_statement()]).set_line(colon)
            self.set_repr(node, noderepr.BlockRepr(colon, none, none, none))
            return cast(Block, node), None
        else:
            # Indented block.
            br = self.expect_break()
            type = self.parse_type_comment(br, signature=True)
            indent = self.expect_indent()
            stmt = []  # type: List[Node]
            while (not isinstance(self.current(), Dedent) and
                   not isinstance(self.current(), Eof)):
                try:
                    s = self.parse_statement()
                    if s is not None:
                        if not self.try_combine_overloads(s, stmt):
                            stmt.append(s)
                except ParseError:
                    pass
            dedent = none
            if isinstance(self.current(), Dedent):
                dedent = self.skip()
            node = Block(stmt).set_line(colon)
            self.set_repr(node, noderepr.BlockRepr(colon, br, indent, dedent))
            return cast(Block, node), type

    def try_combine_overloads(self, s: Node, stmt: List[Node]) -> bool:
        if isinstance(s, Decorator) and stmt:
            fdef = cast(Decorator, s)
            n = fdef.func.name()
            if (isinstance(stmt[-1], Decorator) and
                    (cast(Decorator, stmt[-1])).func.name() == n):
                stmt[-1] = OverloadedFuncDef([cast(Decorator, stmt[-1]), fdef])
                return True
            elif (isinstance(stmt[-1], OverloadedFuncDef) and
                    (cast(OverloadedFuncDef, stmt[-1])).name() == n):
                (cast(OverloadedFuncDef, stmt[-1])).items.append(fdef)
                return True
        return False

    def parse_statement(self) -> Node:
        stmt = Undefined  # type: Node
        t = self.current()
        ts = self.current_str()
        if ts == 'if':
            stmt = self.parse_if_stmt()
        elif ts == 'def':
            stmt = self.parse_function()
        elif ts == 'while':
            stmt = self.parse_while_stmt()
        elif ts == 'return':
            stmt = self.parse_return_stmt()
        elif ts == 'for':
            stmt = self.parse_for_stmt()
        elif ts == 'try':
            stmt = self.parse_try_stmt()
        elif ts == 'break':
            stmt = self.parse_break_stmt()
        elif ts == 'continue':
            stmt = self.parse_continue_stmt()
        elif ts == 'pass':
            stmt = self.parse_pass_stmt()
        elif ts == 'raise':
            stmt = self.parse_raise_stmt()
        elif ts == 'import':
            stmt = self.parse_import()
        elif ts == 'from':
            stmt = self.parse_import_from()
        elif ts == 'class':
            stmt = self.parse_class_def()
        elif ts == 'global':
            stmt = self.parse_global_decl()
        elif ts == 'assert':
            stmt = self.parse_assert_stmt()
        elif ts == 'yield':
            stmt = self.parse_yield_stmt()
        elif ts == 'del':
            stmt = self.parse_del_stmt()
        elif ts == 'with':
            stmt = self.parse_with_stmt()
        elif ts == '@':
            stmt = self.parse_decorated_function_or_class()
        elif ts == 'print' and (self.pyversion == 2 and
                                'print_function' not in self.future_options):
            stmt = self.parse_print_stmt()
        else:
            stmt = self.parse_expression_or_assignment()
        if stmt is not None:
            stmt.set_line(t)
        return stmt

    def parse_expression_or_assignment(self) -> Node:
        e = self.parse_expression()
        if self.current_str() == '=':
            return self.parse_assignment(e)
        elif self.current_str() in op_assign:
            # Operator assignment statement.
            op = self.current_str()[:-1]
            assign = self.skip()
            r = self.parse_expression()
            br = self.expect_break()
            node = OperatorAssignmentStmt(op, e, r)
            self.set_repr(node,
                          noderepr.OperatorAssignmentStmtRepr(assign, br))
            return node
        else:
            # Expression statement.
            br = self.expect_break()
            expr = ExpressionStmt(e)
            self.set_repr(expr, noderepr.ExpressionStmtRepr(br))
            return expr

    def parse_assignment(self, lv: Any) -> Node:
        """Parse an assignment statement.

        Assume that lvalue has been parsed already, and the current token is =.
        Also parse an optional '# type:' comment.
        """
        assigns = [self.expect('=')]
        lvalues = [lv]

        e = self.parse_expression()
        while self.current_str() == '=':
            lvalues.append(e)
            assigns.append(self.skip())
            e = self.parse_expression()
        br = self.expect_break()

        type = self.parse_type_comment(br, signature=False)
        assignment = AssignmentStmt(lvalues, e, type)
        self.set_repr(assignment, noderepr.AssignmentStmtRepr(assigns, br))
        return assignment

    def parse_return_stmt(self) -> ReturnStmt:
        return_tok = self.expect('return')
        expr = None  # type: Node
        if not isinstance(self.current(), Break):
            expr = self.parse_expression()
        br = self.expect_break()
        node = ReturnStmt(expr)
        self.set_repr(node, noderepr.SimpleStmtRepr(return_tok, br))
        return node

    def parse_raise_stmt(self) -> RaiseStmt:
        raise_tok = self.expect('raise')
        expr = None  # type: Node
        from_expr = None  # type: Node
        from_tok = none
        if not isinstance(self.current(), Break):
            expr = self.parse_expression()
            if self.current_str() == 'from':
                from_tok = self.expect('from')
                from_expr = self.parse_expression()
        br = self.expect_break()
        node = RaiseStmt(expr, from_expr)
        self.set_repr(node, noderepr.RaiseStmtRepr(raise_tok, from_tok, br))
        return node

    def parse_assert_stmt(self) -> AssertStmt:
        assert_tok = self.expect('assert')
        expr = self.parse_expression()
        br = self.expect_break()
        node = AssertStmt(expr)
        self.set_repr(node, noderepr.SimpleStmtRepr(assert_tok, br))
        return node

    def parse_yield_stmt(self) -> YieldStmt:
        yield_tok = self.expect('yield')
        expr = None  # type: Node
        if not isinstance(self.current(), Break):
            expr = self.parse_expression()
        br = self.expect_break()
        node = YieldStmt(expr)
        self.set_repr(node, noderepr.SimpleStmtRepr(yield_tok, br))
        return node

    def parse_del_stmt(self) -> DelStmt:
        del_tok = self.expect('del')
        expr = self.parse_expression()
        br = self.expect_break()
        node = DelStmt(expr)
        self.set_repr(node, noderepr.SimpleStmtRepr(del_tok, br))
        return node

    def parse_break_stmt(self) -> BreakStmt:
        break_tok = self.expect('break')
        br = self.expect_break()
        node = BreakStmt()
        self.set_repr(node, noderepr.SimpleStmtRepr(break_tok, br))
        return node

    def parse_continue_stmt(self) -> ContinueStmt:
        continue_tok = self.expect('continue')
        br = self.expect_break()
        node = ContinueStmt()
        self.set_repr(node, noderepr.SimpleStmtRepr(continue_tok, br))
        return node

    def parse_pass_stmt(self) -> PassStmt:
        pass_tok = self.expect('pass')
        br = self.expect_break()
        node = PassStmt()
        self.set_repr(node, noderepr.SimpleStmtRepr(pass_tok, br))
        return node

    def parse_global_decl(self) -> GlobalDecl:
        global_tok = self.expect('global')
        names = List[str]()
        name_toks = List[Token]()
        commas = List[Token]()
        while True:
            n = self.expect_type(Name)
            names.append(n.string)
            name_toks.append(n)
            if self.current_str() != ',':
                break
            commas.append(self.skip())
        br = self.expect_break()
        node = GlobalDecl(names)
        self.set_repr(node, noderepr.GlobalDeclRepr(global_tok, name_toks,
                                                    commas, br))
        return node

    def parse_while_stmt(self) -> WhileStmt:
        is_error = False
        while_tok = self.expect('while')
        try:
            expr = self.parse_expression()
        except ParseError:
            is_error = True
        body, _ = self.parse_block()
        if self.current_str() == 'else':
            else_tok = self.expect('else')
            else_body, _ = self.parse_block()
        else:
            else_body = None
            else_tok = none
        if is_error is not None:
            node = WhileStmt(expr, body, else_body)
            self.set_repr(node, noderepr.WhileStmtRepr(while_tok, else_tok))
            return node
        else:
            return None

    def parse_for_stmt(self) -> ForStmt:
        for_tok = self.expect('for')
        index, commas = self.parse_for_index_variables()
        in_tok = self.expect('in')
        expr = self.parse_expression()

        body, _ = self.parse_block()

        if self.current_str() == 'else':
            else_tok = self.expect('else')
            else_body, _ = self.parse_block()
        else:
            else_body = None
            else_tok = none

        node = ForStmt(index, expr, body, else_body)
        self.set_repr(node, noderepr.ForStmtRepr(for_tok, commas, in_tok,
                                                 else_tok))
        return node

    def parse_for_index_variables(self) -> Tuple[List[Node], List[Token]]:
        # Parse index variables of a 'for' statement.
        index = List[Node]()
        commas = List[Token]()

        is_paren = self.current_str() == '('
        if is_paren:
            self.skip()

        while True:
            v = self.parse_expression(precedence['in'])  # prevent parsing of for's 'in'
            index.append(v)
            if self.current_str() != ',':
                commas.append(none)
                break
            commas.append(self.skip())

        if is_paren:
            self.expect(')')

        return index, commas

    def parse_if_stmt(self) -> IfStmt:
        is_error = False

        if_tok = self.expect('if')
        expr = List[Node]()
        try:
            expr.append(self.parse_expression())
        except ParseError:
            is_error = True

        body = [self.parse_block()[0]]

        elif_toks = List[Token]()
        while self.current_str() == 'elif':
            elif_toks.append(self.expect('elif'))
            try:
                expr.append(self.parse_expression())
            except ParseError:
                is_error = True
            body.append(self.parse_block()[0])

        if self.current_str() == 'else':
            else_tok = self.expect('else')
            else_body, _ = self.parse_block()
        else:
            else_tok = none
            else_body = None

        if not is_error:
            node = IfStmt(expr, body, else_body)
            self.set_repr(node, noderepr.IfStmtRepr(if_tok, elif_toks,
                                                    else_tok))
            return node
        else:
            return None

    def parse_try_stmt(self) -> Node:
        try_tok = self.expect('try')
        body, _ = self.parse_block()
        is_error = False
        vars = List[NameExpr]()
        types = List[Node]()
        handlers = List[Block]()
        except_toks, name_toks, as_toks, except_brs = (List[Token](),
                                                       List[Token](),
                                                       List[Token](),
                                                       List[Token]())
        while self.current_str() == 'except':
            except_toks.append(self.expect('except'))
            if not isinstance(self.current(), Colon):
                try:
                    t = self.current()
                    types.append(self.parse_expression().set_line(t))
                    if self.current_str() == 'as':
                        as_toks.append(self.expect('as'))
                        vars.append(self.parse_name_expr())
                    else:
                        name_toks.append(none)
                        vars.append(None)
                        as_toks.append(none)
                except ParseError:
                    is_error = True
            else:
                types.append(None)
                vars.append(None)
                as_toks.append(none)
            handlers.append(self.parse_block()[0])
        if not is_error:
            if self.current_str() == 'else':
                else_tok = self.skip()
                else_body, _ = self.parse_block()
            else:
                else_tok = none
                else_body = None
            if self.current_str() == 'finally':
                finally_tok = self.expect('finally')
                finally_body, _ = self.parse_block()
            else:
                finally_tok = none
                finally_body = None
            node = TryStmt(body, vars, types, handlers, else_body,
                           finally_body)
            self.set_repr(node, noderepr.TryStmtRepr(try_tok, except_toks,
                                                     name_toks, as_toks,
                                                     else_tok, finally_tok))
            return node
        else:
            return None

    def parse_with_stmt(self) -> WithStmt:
        with_tok = self.expect('with')
        as_toks = List[Token]()
        commas = List[Token]()
        expr = List[Node]()
        name = List[NameExpr]()
        while True:
            e = self.parse_expression(precedence[','])
            if self.current_str() == 'as':
                as_toks.append(self.expect('as'))
                n = self.parse_name_expr()
            else:
                as_toks.append(none)
                n = None
            expr.append(e)
            name.append(n)
            if self.current_str() != ',':
                break
            commas.append(self.expect(','))
        body, _ = self.parse_block()
        node = WithStmt(expr, name, body)
        self.set_repr(node, noderepr.WithStmtRepr(with_tok, as_toks, commas))
        return node

    def parse_print_stmt(self) -> PrintStmt:
        self.expect('print')
        args = List[Node]()
        while not isinstance(self.current(), Break):
            args.append(self.parse_expression(precedence[',']))
            if self.current_str() == ',':
                comma = True
                self.skip()
            else:
                comma = False
                break
        self.expect_break()
        return PrintStmt(args, newline=not comma)

    # Parsing expressions

    def parse_expression(self, prec: int = 0) -> Node:
        """Parse a subexpression within a specific precedence context."""
        expr = Undefined  # type: Node
        t = self.current()  # Remember token for setting the line number.

        # Parse a "value" expression or unary operator expression and store
        # that in expr.
        s = self.current_str()
        if s == '(':
            # Parerenthesised expression or cast.
            expr = self.parse_parentheses()
        elif s == '[':
            expr = self.parse_list_expr()
        elif s in ['-', '+', 'not', '~']:
            # Unary operation.
            expr = self.parse_unary_expr()
        elif s == 'lambda':
            expr = self.parse_lambda_expr()
        elif s == '{':
            expr = self.parse_dict_or_set_expr()
        else:
            if isinstance(self.current(), Name):
                # Name expression.
                expr = self.parse_name_expr()
            elif isinstance(self.current(), IntLit):
                expr = self.parse_int_expr()
            elif isinstance(self.current(), StrLit):
                expr = self.parse_str_expr()
            elif isinstance(self.current(), BytesLit):
                expr = self.parse_bytes_literal()
            elif isinstance(self.current(), UnicodeLit):
                expr = self.parse_unicode_literal()
            elif isinstance(self.current(), FloatLit):
                expr = self.parse_float_expr()
            else:
                # Invalid expression.
                self.parse_error()

        # Set the line of the expression node, if not specified. This
        # simplifies recording the line number as not every node type needs to
        # deal with it separately.
        if expr.line < 0:
            expr.set_line(t)

        # Parse operations that require a left argument (stored in expr).
        while True:
            t = self.current()
            s = self.current_str()
            if s == '(':
                # Call expression.
                expr = self.parse_call_expr(expr)
            elif s == '.':
                # Member access expression.
                expr = self.parse_member_expr(expr)
            elif s == '[':
                # Indexing expression.
                expr = self.parse_index_expr(expr)
            elif s == ',':
                # The comma operator is used to build tuples. Comma also
                # separates array items and function arguments, but in this
                # case the precedence is too low to build a tuple.
                if precedence[','] > prec:
                    expr = self.parse_tuple_expr(expr)
                else:
                    break
            elif s == 'for':
                if precedence['<for>'] > prec:
                    # List comprehension or generator expression. Parse as
                    # generator expression; it will be converted to list
                    # comprehension if needed elsewhere.
                    expr = self.parse_generator_expr(expr)
                else:
                    break
            elif s == 'if':
                # Conditional expression.
                if precedence['<if>'] > prec:
                    expr = self.parse_conditional_expr(expr)
                else:
                    break
            else:
                # Binary operation or a special case.
                if isinstance(self.current(), Op):
                    op = self.current_str()
                    op_prec = precedence[op]
                    if op == 'not':
                        # Either "not in" or an error.
                        op_prec = precedence['in']
                    if op_prec > prec:
                        if op in op_comp:
                            expr = self.parse_comparison_expr(expr, op_prec)
                        else:
                            expr = self.parse_bin_op_expr(expr, op_prec)
                    else:
                        # The operation cannot be associated with the
                        # current left operand due to the precedence
                        # context; let the caller handle it.
                        break
                else:
                    # Not an operation that accepts a left argument; let the
                    # caller handle the rest.
                    break

            # Set the line of the expression node, if not specified. This
            # simplifies recording the line number as not every node type
            # needs to deal with it separately.
            if expr.line < 0:
                expr.set_line(t)

        return expr

    def parse_parentheses(self) -> Node:
        lparen = self.skip()
        if self.current_str() == ')':
            # Empty tuple ().
            expr = self.parse_empty_tuple_expr(lparen)  # type: Node
        else:
            # Parenthesised expression.
            expr = self.parse_expression(0)
            rparen = self.expect(')')
            expr = ParenExpr(expr)
            self.set_repr(expr, noderepr.ParenExprRepr(lparen, rparen))
        return expr

    def parse_empty_tuple_expr(self, lparen: Any) -> TupleExpr:
        rparen = self.expect(')')
        node = TupleExpr([])
        self.set_repr(node, noderepr.TupleExprRepr(lparen, [], rparen))
        return node

    def parse_list_expr(self) -> Node:
        """Parse list literal or list comprehension."""
        items = List[Node]()
        lbracket = self.expect('[')
        commas = List[Token]()
        while self.current_str() != ']' and not self.eol():
            items.append(self.parse_expression(precedence['<for>']))
            if self.current_str() != ',':
                break
            commas.append(self.expect(','))
        if self.current_str() == 'for' and len(items) == 1:
            items[0] = self.parse_generator_expr(items[0])
        rbracket = self.expect(']')
        if len(items) == 1 and isinstance(items[0], GeneratorExpr):
            list_comp = ListComprehension(cast(GeneratorExpr, items[0]))
            self.set_repr(list_comp, noderepr.ListComprehensionRepr(lbracket,
                                                                    rbracket))
            return list_comp
        else:
            expr = ListExpr(items)
            self.set_repr(expr, noderepr.ListSetExprRepr(lbracket, commas,
                                                         rbracket, none, none))
            return expr

    def parse_generator_expr(self, left_expr: Node) -> GeneratorExpr:
        indices = List[List[Node]]()
        sequences = List[Node]()
        for_toks = List[Token]()
        in_toks = List[Token]()
        if_toklists = List[List[Token]]()
        condlists = List[List[Node]]()
        while self.current_str() == 'for':
            if_toks = List[Token]()
            conds = List[Node]()
            for_toks.append(self.expect('for'))
            index, commas = self.parse_for_index_variables()
            indices.append(index)
            in_toks.append(self.expect('in'))
            sequence = self.parse_expression_list()
            sequences.append(sequence)
            while self.current_str() == 'if':
                if_toks.append(self.skip())
                conds.append(self.parse_expression(precedence['<if>']))
            if_toklists.append(if_toks)
            condlists.append(conds)

        gen = GeneratorExpr(left_expr, indices, sequences, condlists)
        gen.set_line(for_toks[0])
        self.set_repr(gen, noderepr.GeneratorExprRepr(for_toks, commas, in_toks,
                                                      if_toklists))
        return gen

    def parse_expression_list(self) -> Node:
        prec = precedence['<if>']
        expr = self.parse_expression(prec)
        if self.current_str() != ',':
            return expr
        else:
            t = self.current()
            return self.parse_tuple_expr(expr, prec).set_line(t)

    def parse_conditional_expr(self, left_expr: Node) -> ConditionalExpr:
        self.expect('if')
        cond = self.parse_expression(precedence['<if>'])
        self.expect('else')
        else_expr = self.parse_expression(precedence['<if>'])
        return ConditionalExpr(cond, left_expr, else_expr)

    def parse_dict_or_set_expr(self) -> Node:
        items = List[Tuple[Node, Node]]()
        lbrace = self.expect('{')
        colons = List[Token]()
        commas = List[Token]()
        while self.current_str() != '}' and not self.eol():
            key = self.parse_expression(precedence[','])
            if self.current_str() in [',', '}'] and items == []:
                return self.parse_set_expr(key, lbrace)
            elif self.current_str() != ':':
                self.parse_error()
            colons.append(self.expect(':'))
            value = self.parse_expression(precedence[','])
            items.append((key, value))
            if self.current_str() != ',':
                break
            commas.append(self.expect(','))
        rbrace = self.expect('}')
        node = DictExpr(items)
        self.set_repr(node, noderepr.DictExprRepr(lbrace, colons, commas,
                                                  rbrace, none, none, none))
        return node

    def parse_set_expr(self, first: Node, lbrace: Token) -> SetExpr:
        items = [first]
        commas = List[Token]()
        while self.current_str() != '}' and not self.eol():
            commas.append(self.expect(','))
            if self.current_str() == '}':
                break
            items.append(self.parse_expression(precedence[',']))
        rbrace = self.expect('}')
        expr = SetExpr(items)
        self.set_repr(expr, noderepr.ListSetExprRepr(lbrace, commas,
                                                     rbrace, none, none))
        return expr

    def parse_tuple_expr(self, expr: Node,
                         prec: int = precedence[',']) -> TupleExpr:
        items = [expr]
        commas = List[Token]()
        while True:
            commas.append(self.expect(','))
            if (self.current_str() in [')', ']', '='] or
                    isinstance(self.current(), Break)):
                break
            items.append(self.parse_expression(prec))
            if self.current_str() != ',': break
        node = TupleExpr(items)
        self.set_repr(node, noderepr.TupleExprRepr(none, commas, none))
        return node

    def parse_name_expr(self) -> NameExpr:
        tok = self.expect_type(Name)
        node = NameExpr(tok.string)
        node.set_line(tok)
        self.set_repr(node, noderepr.NameExprRepr(tok))
        return node

    def parse_int_expr(self) -> IntExpr:
        tok = self.expect_type(IntLit)
        s = tok.string
        v = 0
        if len(s) > 2 and s[1] in 'xX':
            v = int(s[2:], 16)
        elif len(s) > 2 and s[1] in 'oO':
            v = int(s[2:], 8)
        else:
            v = int(s)
        node = IntExpr(v)
        self.set_repr(node, noderepr.IntExprRepr(tok))
        return node

    def parse_str_expr(self) -> Node:
        # XXX \uxxxx literals
        tok = [self.expect_type(StrLit)]
        value = (cast(StrLit, tok[0])).parsed()
        while isinstance(self.current(), StrLit):
            t = cast(StrLit, self.skip())
            tok.append(t)
            value += t.parsed()
        node = Undefined(Node)
        if self.pyversion == 2 and 'unicode_literals' in self.future_options:
            node = UnicodeExpr(value)
        else:
            node = StrExpr(value)
        self.set_repr(node, noderepr.StrExprRepr(tok))
        return node

    def parse_bytes_literal(self) -> Node:
        # XXX \uxxxx literals
        tok = [self.expect_type(BytesLit)]
        value = (cast(BytesLit, tok[0])).parsed()
        while isinstance(self.current(), BytesLit):
            t = cast(BytesLit, self.skip())
            tok.append(t)
            value += t.parsed()
        if self.pyversion >= 3:
            node = BytesExpr(value)  # type: Node
        else:
            node = StrExpr(value)
        self.set_repr(node, noderepr.StrExprRepr(tok))
        return node

    def parse_unicode_literal(self) -> Node:
        # XXX \uxxxx literals
        tok = [self.expect_type(UnicodeLit)]
        value = (cast(UnicodeLit, tok[0])).parsed()
        while isinstance(self.current(), UnicodeLit):
            t = cast(UnicodeLit, self.skip())
            tok.append(t)
            value += t.parsed()
        if self.pyversion >= 3:
            # Python 3.3 supports u'...' as an alias of '...'.
            node = StrExpr(value)  # type: Node
        else:
            node = UnicodeExpr(value)
        self.set_repr(node, noderepr.StrExprRepr(tok))
        return node

    def parse_float_expr(self) -> FloatExpr:
        tok = self.expect_type(FloatLit)
        node = FloatExpr(float(tok.string))
        self.set_repr(node, noderepr.FloatExprRepr(tok))
        return node

    def parse_call_expr(self, callee: Any) -> CallExpr:
        lparen = self.expect('(')
        (args, kinds, names,
         commas, star, star2, assigns) = self.parse_arg_expr()
        rparen = self.expect(')')
        node = CallExpr(callee, args, kinds, names)
        self.set_repr(node, noderepr.CallExprRepr(lparen, commas, star, star2,
                                                  assigns, rparen))
        return node

    def parse_arg_expr(self) -> Tuple[List[Node], List[int], List[str],
                                      List[Token], Token, Token,
                                      List[List[Token]]]:
        """Parse arguments in a call expression (within '(' and ')').

        Return a tuple with these items:
          argument expressions
          argument kinds
          argument names (for named arguments; None for ordinary args)
          comma tokens
          * token (if any)
          ** token (if any)
          (assignment, name) tokens
        """
        args = []   # type: List[Node]
        kinds = []  # type: List[int]
        names = []  # type: List[str]
        star = none
        star2 = none
        commas = []    # type: List[Token]
        keywords = []  # type: List[List[Token]]
        var_arg = False
        dict_arg = False
        named_args = False
        while self.current_str() != ')' and not self.eol() and not dict_arg:
            if isinstance(self.current(), Name) and self.peek().string == '=':
                # Named argument
                name = self.expect_type(Name)
                assign = self.expect('=')
                kinds.append(nodes.ARG_NAMED)
                names.append(name.string)
                keywords.append([name, assign])
                named_args = True
            elif (self.current_str() == '*' and not var_arg and not dict_arg
                    and not named_args):
                # *args
                var_arg = True
                star = self.expect('*')
                kinds.append(nodes.ARG_STAR)
                names.append(None)
            elif self.current_str() == '**':
                # **kwargs
                star2 = self.expect('**')
                dict_arg = True
                kinds.append(nodes.ARG_STAR2)
                names.append(None)
            elif not var_arg and not named_args:
                # Ordinary argument
                kinds.append(nodes.ARG_POS)
                names.append(None)
            else:
                self.parse_error()
            args.append(self.parse_expression(precedence[',']))
            if self.current_str() != ',':
                break
            commas.append(self.expect(','))
        return args, kinds, names, commas, star, star2, keywords

    def parse_member_expr(self, expr: Any) -> Node:
        dot = self.expect('.')
        name = self.expect_type(Name)
        node = Undefined(Node)
        if (isinstance(expr, CallExpr) and isinstance(expr.callee, NameExpr)
                and expr.callee.name == 'super'):
            # super() expression
            node = SuperExpr(name.string)
            self.set_repr(node,
                          noderepr.SuperExprRepr(expr.callee.repr.id,
                                                 expr.repr.lparen,
                                                 expr.repr.rparen, dot, name))
        else:
            node = MemberExpr(expr, name.string)
            self.set_repr(node, noderepr.MemberExprRepr(dot, name))
        return node

    def parse_index_expr(self, base: Any) -> IndexExpr:
        lbracket = self.expect('[')
        if self.current_str() != ':':
            index = self.parse_expression(0)
        else:
            index = None
        if self.current_str() == ':':
            # Slice.
            colon = self.expect(':')
            if self.current_str() != ']' and self.current_str() != ':':
                end_index = self.parse_expression(0)
            else:
                end_index = None
            colon2 = none
            stride = None  # type: Node
            if self.current_str() == ':':
                colon2 = self.expect(':')
                if self.current_str() != ']':
                    stride = self.parse_expression()
            index = SliceExpr(index, end_index, stride).set_line(colon.line)
            self.set_repr(index, noderepr.SliceExprRepr(colon, colon2))
        rbracket = self.expect(']')
        node = IndexExpr(base, index)
        self.set_repr(node, noderepr.IndexExprRepr(lbracket, rbracket))
        return node

    def parse_bin_op_expr(self, left: Node, prec: int) -> OpExpr:
        op = self.expect_type(Op)
        op_str = op.string
        if op_str == '~':
            self.ind -= 1
            self.parse_error()
        right = self.parse_expression(prec)
        node = OpExpr(op_str, left, right)
        self.set_repr(node, noderepr.OpExprRepr(op))
        return node

    def parse_comparison_expr(self, left: Node, prec: int) -> ComparisonExpr:
        operators = []  # type: List[Tuple[Token, Token]]
        operators_str = []  # type: List[str]
        operands = [left]

        while True:
            op = self.expect_type(Op)
            op2 = none
            op_str = op.string
            if op_str == 'not':
                if self.current_str() == 'in':
                    op_str = 'not in'
                    op2 = self.skip()
                else:
                    self.parse_error()
            elif op_str == 'is' and self.current_str() == 'not':
                op_str = 'is not'
                op2 = self.skip()

            operators_str.append(op_str)
            operators.append( (op, op2) )
            operand = self.parse_expression(prec)
            operands.append(operand)

            # Continue if next token is a comparison operator
            t = self.current()
            s = self.current_str()
            if s not in op_comp:
                break

        node = ComparisonExpr(operators_str, operands)
        self.set_repr(node, noderepr.ComparisonExprRepr(operators))
        return node


    def parse_unary_expr(self) -> UnaryExpr:
        op_tok = self.skip()
        op = op_tok.string
        if op == '-' or op == '+':
            prec = precedence['-u']
        else:
            prec = precedence[op]
        expr = self.parse_expression(prec)
        node = UnaryExpr(op, expr)
        self.set_repr(node, noderepr.UnaryExprRepr(op_tok))
        return node

    def parse_lambda_expr(self) -> FuncExpr:
        is_error = False
        lambda_tok = self.expect('lambda')

        (args, init, kinds, has_inits,
         arg_names, commas, asterisk,
         assigns, arg_types) = self.parse_arg_list(allow_signature=False)

        names = List[str]()
        for arg in args:
            names.append(arg.name())

        # Use 'object' as the placeholder return type; it will be inferred
        # later. We can't use 'Any' since it could make type inference results
        # less precise.
        ret_type = UnboundType('__builtins__.object')
        typ = self.build_func_annotation(ret_type, arg_types, kinds, names,
                                         lambda_tok.line, is_default_ret=True)

        colon = self.expect(':')

        expr = self.parse_expression(precedence[','])

        body = Block([ReturnStmt(expr).set_line(lambda_tok)])
        body.set_line(colon)

        node = FuncExpr(args, kinds, init, body, typ)
        self.set_repr(node,
                      noderepr.FuncExprRepr(
                          lambda_tok, colon,
                          noderepr.FuncArgsRepr(none, none, arg_names, commas,
                                                assigns, asterisk)))
        return node

    # Helper methods

    def skip(self) -> Token:
        self.ind += 1
        return self.tok[self.ind - 1]

    def expect(self, string: str) -> Token:
        if self.current_str() == string:
            self.ind += 1
            return self.tok[self.ind - 1]
        else:
            self.parse_error()

    def expect_indent(self) -> Token:
        if isinstance(self.current(), Indent):
            return self.expect_type(Indent)
        else:
            self.fail('Expected an indented block', self.current().line)
            return none

    def fail(self, msg: str, line: int) -> None:
        self.errors.report(line, msg)

    def expect_type(self, typ: type) -> Token:
        if isinstance(self.current(), typ):
            self.ind += 1
            return self.tok[self.ind - 1]
        else:
            self.parse_error()

    def expect_colon_and_break(self) -> Tuple[Token, Token]:
        return self.expect_type(Colon), self.expect_type(Break)

    def expect_break(self) -> Token:
        return self.expect_type(Break)

    def expect_end(self) -> Tuple[Token, Token]:
        return self.expect('end'), self.expect_type(Break)

    def current(self) -> Token:
        return self.tok[self.ind]

    def current_str(self) -> str:
        return self.current().string

    def peek(self) -> Token:
        return self.tok[self.ind + 1]

    def parse_error(self) -> None:
        self.parse_error_at(self.current())
        raise ParseError()

    def parse_error_at(self, tok: Token, skip: bool = True) -> None:
        msg = ''
        if isinstance(tok, LexError):
            msg = token_repr(tok)
            msg = msg[0].upper() + msg[1:]
        elif isinstance(tok, Indent) or isinstance(tok, Dedent):
            msg = 'Inconsistent indentation'
        else:
            msg = 'Parse error before {}'.format(token_repr(tok))

        self.errors.report(tok.line, msg)

        if skip:
            self.skip_until_next_line()

    def skip_until_break(self) -> None:
        n = 0
        while (not isinstance(self.current(), Break)
               and not isinstance(self.current(), Eof)):
            self.skip()
            n += 1
        if isinstance(self.tok[self.ind - 1], Colon) and n > 1:
            self.ind -= 1

    def skip_until_next_line(self) -> None:
        self.skip_until_break()
        if isinstance(self.current(), Break):
            self.skip()

    def eol(self) -> bool:
        return isinstance(self.current(), Break) or self.eof()

    def eof(self) -> bool:
        return isinstance(self.current(), Eof)

    # Type annotation related functionality

    def parse_type(self) -> Type:
        line = self.current().line
        try:
            typ, self.ind = parse_type(self.tok, self.ind)
        except TypeParseError as e:
            self.parse_error_at(e.token)
            raise ParseError()
        return typ

    annotation_prefix_re = re.compile(r'#\s*type:')

    def parse_type_comment(self, token: Token, signature: bool) -> Type:
        """Parse a '# type: ...' annotation.

        Return None if no annotation found. If signature is True, expect
        a type signature of form (...) -> t.
        """
        whitespace_or_comments = token.rep().strip()
        if self.annotation_prefix_re.match(whitespace_or_comments):
            type_as_str = whitespace_or_comments.split(':', 1)[1].strip()
            tokens = lex.lex(type_as_str, token.line)
            if len(tokens) < 2:
                # Empty annotation (only Eof token)
                self.errors.report(token.line, 'Empty type annotation')
                return None
            try:
                if not signature:
                    type, index = parse_types(tokens, 0)
                else:
                    type, index = parse_signature(tokens)
            except TypeParseError as e:
                self.parse_error_at(e.token, skip=False)
                return None
            if index < len(tokens) - 2:
                self.parse_error_at(tokens[index], skip=False)
                return None
            return type
        else:
            return None

    # Representation management

    def set_repr(self, node: Node, repr: Any) -> None:
        node.repr = repr

    def repr(self, node: Node) -> Any:
        return node.repr

    def paren_repr(self, e: Node) -> Tuple[List[Token], List[Token]]:
        """If e is a ParenExpr, return an array of left-paren tokens
        (more that one if nested parens) and an array of corresponding
        right-paren tokens.  Otherwise, return [], [].
        """
        if isinstance(e, ParenExpr):
            lp, rp = self.paren_repr(e.expr)
            lp.insert(0, self.repr(e).lparen)
            rp.append(self.repr(e).rparen)
            return lp, rp
        else:
            return [], []


class ParseError(Exception): pass


def token_repr(tok: Token) -> str:
    """Return a representation of a token for use in parse error messages."""
    if isinstance(tok, Break):
        return 'end of line'
    elif isinstance(tok, Eof):
        return 'end of file'
    elif isinstance(tok, Keyword) or isinstance(tok, Name):
        return '"{}"'.format(tok.string)
    elif isinstance(tok, IntLit) or isinstance(tok, FloatLit):
        return 'numeric literal'
    elif isinstance(tok, StrLit):
        return 'string literal'
    elif (isinstance(tok, Punct) or isinstance(tok, Op)
          or isinstance(tok, Colon)):
        return tok.string
    elif isinstance(tok, Bom):
        return 'byte order mark'
    elif isinstance(tok, Indent):
        return 'indent'
    elif isinstance(tok, Dedent):
        return 'dedent'
    else:
        if isinstance(tok, LexError):
            t = tok.type
            if t == lex.NUMERIC_LITERAL_ERROR:
                return 'invalid numeric literal'
            elif t == lex.UNTERMINATED_STRING_LITERAL:
                return 'unterminated string literal'
            elif t == lex.INVALID_CHARACTER:
                msg = 'unrecognized character'
                if ord(tok.string) in range(33, 127):
                    msg += ' ' + tok.string
                return msg
            elif t == lex.INVALID_UTF8_SEQUENCE:
                return 'invalid UTF-8 sequence'
            elif t == lex.NON_ASCII_CHARACTER_IN_COMMENT:
                return 'non-ASCII character in comment'
            elif t == lex.NON_ASCII_CHARACTER_IN_STRING:
                return 'non-ASCII character in string'
            elif t == lex.INVALID_DEDENT:
                return 'inconsistent indentation'
        raise ValueError('Unknown token {}'.format(repr(tok)))


def unwrap_parens(node: Node) -> Node:
    """Unwrap any outer parentheses in node.

    If the node is a parenthesised expression, recursively find the first
    non-parenthesised subexpression and return that. Otherwise, return node.
    """
    if isinstance(node, ParenExpr):
        return unwrap_parens(node.expr)
    else:
        return node


if __name__ == '__main__':
    # Parse a file and dump the AST (or display errors).
    import sys
    if len(sys.argv) != 2:
        print('Usage: parse.py FILE')
        sys.exit(2)
    fnam = sys.argv[1]
    s = open(fnam).read()
    errors = Errors()
    try:
        tree = parse(s, fnam)
        print(tree)
    except CompileError as e:
        for msg in e.messages:
            print(msg)
