"""Mypy parser.

Constructs a parse tree (abstract syntax tree) based on a string
representing a source file. Performs only minimal semantic checks.
"""

import re

from typing import List, Tuple, Any, Set, cast, Union, Optional

from mypy import lex
from mypy.lex import (
    Token, Eof, Bom, Break, Name, Colon, Dedent, IntLit, StrLit, BytesLit,
    UnicodeLit, FloatLit, Op, Indent, Keyword, Punct, LexError, ComplexLit,
    EllipsisToken
)
import mypy.types
from mypy.nodes import (
    MypyFile, Import, Node, ImportAll, ImportFrom, FuncDef, OverloadedFuncDef,
    ClassDef, Decorator, Block, Var, OperatorAssignmentStmt,
    ExpressionStmt, AssignmentStmt, ReturnStmt, RaiseStmt, AssertStmt,
    DelStmt, BreakStmt, ContinueStmt, PassStmt, GlobalDecl,
    WhileStmt, ForStmt, IfStmt, TryStmt, WithStmt,
    TupleExpr, GeneratorExpr, ListComprehension, ListExpr, ConditionalExpr,
    DictExpr, SetExpr, NameExpr, IntExpr, StrExpr, BytesExpr, UnicodeExpr,
    FloatExpr, CallExpr, SuperExpr, MemberExpr, IndexExpr, SliceExpr, OpExpr,
    UnaryExpr, FuncExpr, PrintStmt, ImportBase, ComparisonExpr,
    StarExpr, YieldFromExpr, NonlocalDecl, DictionaryComprehension,
    SetComprehension, ComplexExpr, EllipsisExpr, YieldExpr, ExecStmt, Argument,
    BackquoteExpr
)
from mypy import defaults
from mypy import nodes
from mypy.errors import Errors, CompileError
from mypy.types import Type, CallableType, AnyType, UnboundType
from mypy.parsetype import (
    parse_type, parse_types, parse_signature, TypeParseError, parse_str_as_signature
)
from mypy.options import Options

from mypy import experiments


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
    '*u': 7,  # unary * for star expressions
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


def parse(source: Union[str, bytes],
          fnam: str,
          errors: Errors,
          options: Options) -> MypyFile:
    """Parse a source file, without doing any semantic analysis.

    Return the parse tree. If errors is not provided, raise ParseError
    on failure. Otherwise, use the errors object to report parse errors.

    The python_version (major, minor) option determines the Python syntax variant.
    """
    is_stub_file = bool(fnam) and fnam.endswith('.pyi')
    if options.fast_parser:
        if options.python_version[0] >= 3 or is_stub_file:
            import mypy.fastparse
            return mypy.fastparse.parse(source,
                                        fnam=fnam,
                                        errors=errors,
                                        pyversion=options.python_version,
                                        custom_typing_module=options.custom_typing_module)
        else:
            import mypy.fastparse2
            return mypy.fastparse2.parse(source,
                                         fnam=fnam,
                                         errors=errors,
                                         pyversion=options.python_version,
                                         custom_typing_module=options.custom_typing_module)

    parser = Parser(fnam,
                    errors,
                    options.python_version,
                    options.custom_typing_module,
                    is_stub_file=is_stub_file)
    tree = parser.parse(source)
    tree.path = fnam
    tree.is_stub = is_stub_file
    return tree


class Parser:
    """Mypy parser that parses a string into an AST.

    Parses type annotations in addition to basic Python syntax. It supports both Python 2 and 3
    (though Python 2 support is incomplete).

    The AST classes are defined in mypy.nodes and mypy.types.
    """

    tok = None  # type: List[Token]
    ind = 0
    errors = None  # type: Errors
    # If True, raise an exception on any parse error. Otherwise, errors are reported via 'errors'.
    raise_on_error = False

    # Are we currently parsing the body of a class definition?
    is_class_body = False
    # All import nodes encountered so far in this parse unit.
    imports = None  # type: List[ImportBase]
    # Names imported from __future__.
    future_options = None  # type: List[str]
    # Lines to ignore (using # type: ignore).
    ignored_lines = None  # type: Set[int]

    def __init__(self, fnam: str, errors: Errors, pyversion: Tuple[int, int],
                 custom_typing_module: str = None, is_stub_file: bool = False) -> None:
        self.raise_on_error = errors is None
        self.pyversion = pyversion
        self.custom_typing_module = custom_typing_module
        self.is_stub_file = is_stub_file
        if errors is not None:
            self.errors = errors
        else:
            self.errors = Errors()
        if fnam is not None:
            self.errors.set_file(fnam)
        else:
            self.errors.set_file('<input>')

    def parse(self, s: Union[str, bytes]) -> MypyFile:
        self.tok, self.ignored_lines = lex.lex(s, pyversion=self.pyversion,
                                               is_stub_file=self.is_stub_file)
        self.ind = 0
        self.imports = []
        self.future_options = []
        file = self.parse_file()
        if self.raise_on_error and self.errors.is_errors():
            self.errors.raise_error()
        return file

    def weak_opts(self) -> Set[str]:
        """Do weak typing if any of the first ten tokens is a comment saying so.

        The comment can be one of:
        # mypy: weak=global
        # mypy: weak=local
        # mypy: weak      <- defaults to local
        """
        regexp = re.compile(r'^[\s]*# *mypy: *weak(=?)([^\s]*)', re.M)
        for t in self.tok[:10]:
            for s in [t.string, t.pre]:
                m = regexp.search(s)
                if m:
                    opts = set(x for x in m.group(2).split(',') if x)
                    if not opts:
                        opts.add('local')
                    return opts
        return set()

    def parse_file(self) -> MypyFile:
        """Parse a mypy source file."""
        is_bom = self.parse_bom()
        defs = self.parse_defs()
        weak_opts = self.weak_opts()
        self.expect_type(Eof)
        node = MypyFile(defs, self.imports, is_bom, self.ignored_lines,
                        weak_opts=weak_opts)
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
        self.expect('import')
        ids = []
        while True:
            id = self.parse_qualified_name()
            translated = self.translate_module_id(id)
            as_id = None
            if self.current_str() == 'as':
                self.expect('as')
                name_tok = self.expect_type(Name)
                as_id = name_tok.string
            elif translated != id:
                as_id = id
            ids.append((translated, as_id))
            if self.current_str() != ',':
                break
            self.expect(',')
        node = Import(ids)
        self.imports.append(node)
        return node

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

    def parse_import_from(self) -> Node:
        self.expect('from')

        # Build the list of beginning relative tokens.
        relative = 0
        while self.current_str() in (".", "..."):
            relative += len(self.current_str())
            self.skip()

        # Parse qualified name to actually import from.
        if self.current_str() == "import":
            # Empty/default values.
            name = ""
        else:
            name = self.parse_qualified_name()

        name = self.translate_module_id(name)

        # Parse import list
        self.expect('import')
        node = None  # type: ImportBase
        if self.current_str() == '*':
            if name == '__future__':
                self.parse_error()
            # An import all from a module node:
            self.skip()
            node = ImportAll(name, relative)
        else:
            is_paren = self.current_str() == '('
            if is_paren:
                self.expect('(')
            targets = []  # type: List[Tuple[str, str]]
            while True:
                id, as_id = self.parse_import_name()
                if '%s.%s' % (name, id) == self.custom_typing_module:
                    if targets or self.current_str() == ',':
                        self.fail('You cannot import any other modules when you '
                                  'import a custom typing module',
                                  self.current().line)
                    node = Import([('typing', as_id)])
                    self.skip_until_break()
                    break
                targets.append((id, as_id))
                if self.current_str() != ',':
                    break
                self.expect(',')
                if is_paren and self.current_str() == ')':
                    break
            if is_paren:
                self.expect(')')
            if node is None:
                node = ImportFrom(name, relative, targets)
        self.imports.append(node)
        if name == '__future__':
            self.future_options.extend(target[0] for target in targets)
        return node

    def parse_import_name(self) -> Tuple[str, Optional[str]]:
        tok = self.expect_type(Name)
        name = tok.string
        if self.current_str() == 'as':
            self.skip()
            as_name = self.expect_type(Name)
            return name, as_name.string
        else:
            return name, None

    def parse_qualified_name(self) -> str:
        """Parse a name with an optional module qualifier.

        Return a tuple with the name as a string and a token array
        containing all the components of the name.
        """
        tok = self.expect_type(Name)
        n = tok.string
        while self.current_str() == '.':
            self.expect('.')
            tok = self.expect_type(Name)
            n += '.' + tok.string
        return n

    # Parsing global definitions

    def parse_defs(self) -> List[Node]:
        defs = []  # type: List[Node]
        while not self.eof():
            try:
                defn, is_simple = self.parse_statement()
                if is_simple:
                    self.expect_break()
                if defn is not None:
                    if not self.try_combine_overloads(defn, defs):
                        defs.append(defn)
            except ParseError:
                pass
        return defs

    def parse_class_def(self) -> ClassDef:
        old_is_class_body = self.is_class_body
        self.is_class_body = True

        self.expect('class')
        metaclass = None

        try:
            base_types = []  # type: List[Node]
            try:
                name_tok = self.expect_type(Name)
                name = name_tok.string

                self.errors.push_type(name)

                if self.current_str() == '(':
                    self.skip()
                    while True:
                        if self.current_str() == ')':
                            break
                        if self.peek().string == '=':
                            metaclass = self.parse_class_keywords()
                            break
                        base_types.append(self.parse_super_type())
                        if self.current_str() != ',':
                            break
                        self.skip()
                    self.expect(')')
            except ParseError:
                pass

            defs, _ = self.parse_block()

            node = ClassDef(name, defs, None, base_types, metaclass=metaclass)
            return node
        finally:
            self.errors.pop_type()
            self.is_class_body = old_is_class_body

    def parse_class_keywords(self) -> Optional[str]:
        """Parse the class keyword arguments, keeping the metaclass but
        ignoring all others.  Returns None if the metaclass isn't found.
        """
        metaclass = None
        while True:
            key = self.expect_type(Name)
            self.expect('=')
            if key.string == 'metaclass':
                metaclass = self.parse_qualified_name()
            else:
                # skip the class value
                self.parse_expression(precedence[','])
            if self.current_str() != ',':
                break
            self.skip()
            if self.current_str() == ')':
                break
        return metaclass

    def parse_super_type(self) -> Node:
        return self.parse_expression(precedence[','])

    def parse_decorated_function_or_class(self) -> Node:
        decorators = []
        no_type_checks = False
        while self.current_str() == '@':
            self.expect('@')
            d_exp = self.parse_expression()
            if self.is_no_type_check_decorator(d_exp):
                no_type_checks = True
            decorators.append(d_exp)
            self.expect_break()
        if self.current_str() != 'class':
            func = self.parse_function(no_type_checks)
            func.is_decorated = True
            var = Var(func.name())
            # Types of decorated functions must always be inferred.
            var.is_ready = False
            var.set_line(decorators[0].line)
            node = Decorator(func, decorators, var)
            return node
        else:
            cls = self.parse_class_def()
            cls.decorators = decorators
            return cls

    def is_no_type_check_decorator(self, expr: Node) -> bool:
        if isinstance(expr, NameExpr):
            return expr.name == 'no_type_check'
        elif isinstance(expr, MemberExpr):
            if isinstance(expr.expr, NameExpr):
                return expr.expr.name == 'typing' and expr.name == 'no_type_check'
        else:
            return False

    def parse_function(self, no_type_checks: bool=False) -> FuncDef:
        def_tok = self.expect('def')
        is_method = self.is_class_body
        self.is_class_body = False
        try:
            (name, args, typ, is_error, extra_stmts) = self.parse_function_header(no_type_checks)

            arg_kinds = [arg.kind for arg in args]
            arg_names = [arg.variable.name() for arg in args]

            body, comment_type = self.parse_block(allow_type=True)
            # Potentially insert extra assignment statements to the beginning of the
            # body, used to decompose Python 2 tuple arguments.
            body.body[:0] = extra_stmts
            if comment_type:
                # The function has a # type: ... signature.
                if typ:
                    self.errors.report(
                        def_tok.line, 'Function has duplicate type signatures')
                sig = cast(CallableType, comment_type)
                if sig.is_ellipsis_args:
                    # When we encounter an ellipsis, fill in the arg_types with
                    # a bunch of AnyTypes, emulating Callable[..., T]
                    arg_types = [AnyType()] * len(arg_kinds)  # type: List[Type]
                    typ = CallableType(
                        arg_types,
                        arg_kinds,
                        arg_names,
                        sig.ret_type,
                        None,
                        line=def_tok.line)
                elif is_method and len(sig.arg_kinds) < len(arg_kinds):
                    self.check_argument_kinds(arg_kinds,
                                              [nodes.ARG_POS] + sig.arg_kinds,
                                              def_tok.line)
                    # Add implicit 'self' argument to signature.
                    first_arg = [AnyType()]  # type: List[Type]
                    typ = CallableType(
                        first_arg + sig.arg_types,
                        arg_kinds,
                        arg_names,
                        sig.ret_type,
                        None,
                        line=def_tok.line)
                else:
                    self.check_argument_kinds(arg_kinds, sig.arg_kinds,
                                              def_tok.line)
                    typ = CallableType(
                        sig.arg_types,
                        arg_kinds,
                        arg_names,
                        sig.ret_type,
                        None,
                        line=def_tok.line)

            # If there was a serious error, we really cannot build a parse tree
            # node.
            if is_error:
                return None

            if typ:
                for arg, arg_type in zip(args, typ.arg_types):
                    self.set_type_optional(arg_type, arg.initializer)

            if typ and isinstance(typ.ret_type, UnboundType):
                typ.ret_type.is_ret_type = True

            node = FuncDef(name, args, body, typ)
            node.set_line(def_tok)
            if typ is not None:
                typ.definition = node
            return node
        finally:
            self.errors.pop_function()
            self.is_class_body = is_method

    def check_argument_kinds(self, funckinds: List[int], sigkinds: List[int],
                             line: int) -> None:
        """Check that arguments are consistent.

        This verifies that they have the same number and the kinds correspond.

        Arguments:
          funckinds: kinds of arguments in function definition
          sigkinds:  kinds of arguments in signature (after # type:)
        """
        if len(funckinds) != len(sigkinds):
            if len(funckinds) > len(sigkinds):
                self.fail("Type signature has too few arguments", line)
            else:
                self.fail("Type signature has too many arguments", line)
            return
        for kind, token in [(nodes.ARG_STAR, '*'),
                            (nodes.ARG_STAR2, '**')]:
            if ((funckinds.count(kind) != sigkinds.count(kind)) or
                    (kind in funckinds and sigkinds.index(kind) != funckinds.index(kind))):
                self.fail(
                    "Inconsistent use of '{}' in function "
                    "signature".format(token), line)

    def parse_function_header(
            self, no_type_checks: bool=False) -> Tuple[str,
                                                       List[Argument],
                                                       CallableType,
                                                       bool,
                                                       List[AssignmentStmt]]:
        """Parse function header (a name followed by arguments)

        Return a 5-tuple with the following items:
          name
          arguments
          signature (annotation)
          error flag (True if error)
          extra statements needed to decompose arguments (usually empty)

        See parse_arg_list for an explanation of the final tuple item.
        """
        name = ''

        try:
            name_tok = self.expect_type(Name)
            name = name_tok.string

            self.errors.push_function(name)

            args, typ, extra_stmts = self.parse_args(no_type_checks)
        except ParseError:
            if not isinstance(self.current(), Break):
                self.ind -= 1  # Kludge: go back to the Break token
            # Resynchronise parsing by going back over :, if present.
            if isinstance(self.tok[self.ind - 1], Colon):
                self.ind -= 1
            return (name, [], None, True, [])

        return (name, args, typ, False, extra_stmts)

    def parse_args(self, no_type_checks: bool=False) -> Tuple[List[Argument],
                                                              CallableType,
                                                              List[AssignmentStmt]]:
        """Parse a function signature (...) [-> t].

        See parse_arg_list for an explanation of the final tuple item.
        """
        lparen = self.expect('(')

        # Parse the argument list (everything within '(' and ')').
        args, extra_stmts = self.parse_arg_list(no_type_checks=no_type_checks)

        self.expect(')')

        if self.current_str() == '->':
            self.skip()
            if no_type_checks:
                self.parse_expression()
                ret_type = None
            else:
                ret_type = self.parse_type()
        else:
            ret_type = None

        arg_kinds = [arg.kind for arg in args]
        self.verify_argument_kinds(arg_kinds, lparen.line)

        annotation = self.build_func_annotation(
            ret_type, args, lparen.line)

        return args, annotation, extra_stmts

    def build_func_annotation(self, ret_type: Type, args: List[Argument],
            line: int, is_default_ret: bool = False) -> CallableType:
        arg_types = [arg.type_annotation for arg in args]
        # Are there any type annotations?
        if ((ret_type and not is_default_ret)
                or arg_types != [None] * len(arg_types)):
            # Yes. Construct a type for the function signature.
            return self.construct_function_type(args, ret_type, line)
        else:
            return None

    def parse_arg_list(self, allow_signature: bool = True,
            no_type_checks: bool=False) -> Tuple[List[Argument],
                                                 List[AssignmentStmt]]:
        """Parse function definition argument list.

        This includes everything between '(' and ')' (but not the
        parentheses).

        Return tuple (arguments,
                      extra statements for decomposing arguments).

        The final argument is only used for Python 2 argument lists with
        tuples; they contain destructuring assignment statements used to
        decompose tuple arguments. For example, consider a header like this:

        . def f((x, y))

        The actual (sole) argument will be __tuple_arg_1 (a generated
        name), whereas the extra statement list will contain a single
        assignment statement corresponding to this assignment:

          x, y = __tuple_arg_1
        """
        args = []  # type: List[Argument]
        extra_stmts = []
        # This is for checking duplicate argument names.
        arg_names = []  # type: List[str]
        has_tuple_arg = False

        require_named = False
        bare_asterisk_before = -1

        if self.current_str() != ')' and self.current_str() != ':':
            while self.current_str() != ')':
                if self.current_str() == '*' and self.peek().string == ',':
                    self.expect('*')
                    require_named = True
                    bare_asterisk_before = len(args)
                elif self.current_str() in ['*', '**']:
                    if bare_asterisk_before == len(args):
                        # named arguments must follow bare *
                        self.parse_error()

                    arg = self.parse_asterisk_arg(
                        allow_signature,
                        no_type_checks,
                    )
                    args.append(arg)
                    require_named = True
                elif self.current_str() == '(':
                    arg, extra_stmt, names = self.parse_tuple_arg(len(args))
                    args.append(arg)
                    if extra_stmt is not None:
                        extra_stmts.append(extra_stmt)
                        has_tuple_arg = True
                    arg_names.extend(names)
                else:
                    arg, require_named = self.parse_normal_arg(
                        require_named,
                        allow_signature,
                        no_type_checks,
                    )
                    args.append(arg)
                    arg_names.append(arg.variable.name())

                if self.current().string != ',':
                    break

                self.expect(',')

        # Non-tuple argument dupes will be checked elsewhere. Avoid
        # generating duplicate errors.
        if has_tuple_arg:
            self.check_duplicate_argument_names(arg_names)

        return args, extra_stmts

    def check_duplicate_argument_names(self, names: List[str]) -> None:
        found = set()  # type: Set[str]
        for name in names:
            if name in found:
                self.fail('Duplicate argument name "{}"'.format(name),
                          self.current().line)
            found.add(name)

    def parse_asterisk_arg(self,
            allow_signature: bool,
            no_type_checks: bool) -> Argument:
        asterisk = self.skip()
        name = self.expect_type(Name)
        variable = Var(name.string)
        if asterisk.string == '*':
            kind = nodes.ARG_STAR
        else:
            kind = nodes.ARG_STAR2

        type = None
        if no_type_checks:
            self.parse_parameter_annotation()
        else:
            type = self.parse_arg_type(allow_signature)

        return Argument(variable, type, None, kind)

    def parse_tuple_arg(self, index: int) -> Tuple[Argument, AssignmentStmt, List[str]]:
        """Parse a single Python 2 tuple argument.

        Example: def f(x, (y, z)): ...

        The tuple arguments gets transformed into an assignment in the
        function body (the second return value).

        Return tuple (argument, decomposing assignment, list of names defined).

        Special case: if the argument is just (x) then it's not a tuple;
        we indicate this by returning (argument, None, ['x']).
        However, if the argument is (x,) then it *is* a (singleton) tuple.
        """
        line = self.current().line
        # Generate a new argument name that is very unlikely to clash with anything.
        arg_name = '__tuple_arg_{}'.format(index + 1)
        if self.pyversion[0] >= 3:
            self.fail('Tuples in argument lists only supported in Python 2 mode', line)
        paren_arg = self.parse_parentheses()
        self.verify_tuple_arg(paren_arg)
        if isinstance(paren_arg, NameExpr):
            # This isn't a tuple. Revert to a normal argument.
            arg_name = paren_arg.name
            decompose = None
        else:
            rvalue = NameExpr(arg_name)
            rvalue.set_line(line)
            decompose = AssignmentStmt([paren_arg], rvalue)
            decompose.set_line(line)
        kind = nodes.ARG_POS
        initializer = None
        if self.current_str() == '=':
            self.expect('=')
            initializer = self.parse_expression(precedence[','])
            kind = nodes.ARG_OPT
        var = Var(arg_name)
        arg_names = self.find_tuple_arg_argument_names(paren_arg)
        return Argument(var, None, initializer, kind), decompose, arg_names

    def verify_tuple_arg(self, paren_arg: Node) -> None:
        if isinstance(paren_arg, TupleExpr):
            if not paren_arg.items:
                self.fail('Empty tuple not valid as an argument', paren_arg.line)
            for item in paren_arg.items:
                self.verify_tuple_arg(item)
        elif not isinstance(paren_arg, NameExpr):
            self.fail('Invalid item in tuple argument', paren_arg.line)

    def find_tuple_arg_argument_names(self, node: Node) -> List[str]:
        result = []  # type: List[str]
        if isinstance(node, TupleExpr):
            for item in node.items:
                result.extend(self.find_tuple_arg_argument_names(item))
        elif isinstance(node, NameExpr):
            result.append(node.name)
        return result

    def parse_normal_arg(self, require_named: bool,
            allow_signature: bool,
            no_type_checks: bool) -> Tuple[Argument, bool]:
        name = self.expect_type(Name)
        variable = Var(name.string)

        type = None
        if no_type_checks:
            self.parse_parameter_annotation()
        else:
            type = self.parse_arg_type(allow_signature)

        initializer = None  # type: Node
        if self.current_str() == '=':
            self.expect('=')
            initializer = self.parse_expression(precedence[','])
            if require_named:
                kind = nodes.ARG_NAMED
            else:
                kind = nodes.ARG_OPT
        else:
            if require_named:
                kind = nodes.ARG_NAMED
            else:
                kind = nodes.ARG_POS

        return Argument(variable, type, initializer, kind), require_named

    def set_type_optional(self, type: Type, initializer: Node) -> None:
        if not experiments.STRICT_OPTIONAL:
            return
        # Indicate that type should be wrapped in an Optional if arg is initialized to None.
        optional = isinstance(initializer, NameExpr) and initializer.name == 'None'
        if isinstance(type, UnboundType):
            type.optional = optional

    def parse_parameter_annotation(self) -> Node:
        if self.current_str() == ':':
            self.skip()
            return self.parse_expression(precedence[','])

    def parse_arg_type(self, allow_signature: bool) -> Type:
        if self.current_str() == ':' and allow_signature:
            self.skip()
            return self.parse_type()
        else:
            return None

    def verify_argument_kinds(self, kinds: List[int], line: int) -> None:
        found = set()  # type: Set[int]
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

    def construct_function_type(self, args: List[Argument], ret_type: Type,
                                line: int) -> CallableType:
        # Complete the type annotation by replacing omitted types with 'Any'.
        arg_types = [arg.type_annotation for arg in args]
        for i in range(len(arg_types)):
            if arg_types[i] is None:
                arg_types[i] = AnyType(implicit=True)
        if ret_type is None:
            ret_type = AnyType(implicit=True)
        arg_kinds = [arg.kind for arg in args]
        arg_names = [arg.variable.name() for arg in args]
        return CallableType(arg_types, arg_kinds, arg_names, ret_type, None, name=None,
                        variables=None, line=line)

    # Parsing statements

    def parse_block(self, allow_type: bool = False) -> Tuple[Block, Type]:
        colon = self.expect(':')
        if not isinstance(self.current(), Break):
            # Block immediately after ':'.
            nodes = []
            while True:
                ind = self.ind
                stmt, is_simple = self.parse_statement()
                if not is_simple:
                    self.parse_error_at(self.tok[ind])
                    break
                nodes.append(stmt)
                brk = self.expect_break()
                if brk.string != ';':
                    break
            node = Block(nodes)
            node.set_line(colon)
            return node, None
        else:
            # Indented block.
            brk = self.expect_break()
            type = self.parse_type_comment(brk, signature=True)
            self.expect_indent()
            stmt_list = []  # type: List[Node]
            while (not isinstance(self.current(), Dedent) and
                   not isinstance(self.current(), Eof)):
                try:
                    stmt, is_simple = self.parse_statement()
                    if is_simple:
                        self.expect_break()
                    if stmt is not None:
                        if not self.try_combine_overloads(stmt, stmt_list):
                            stmt_list.append(stmt)
                except ParseError:
                    pass
            if isinstance(self.current(), Dedent):
                self.skip()
            node = Block(stmt_list)
            node.set_line(colon)
            return node, type

    def try_combine_overloads(self, s: Node, stmt: List[Node]) -> bool:
        if isinstance(s, Decorator) and stmt:
            fdef = s
            n = fdef.func.name()
            if isinstance(stmt[-1], Decorator) and stmt[-1].func.name() == n:
                stmt[-1] = OverloadedFuncDef([stmt[-1], fdef])
                return True
            elif isinstance(stmt[-1], OverloadedFuncDef) and stmt[-1].name() == n:
                stmt[-1].items.append(fdef)
                return True
        return False

    def parse_statement(self) -> Tuple[Node, bool]:
        stmt = None  # type: Node
        t = self.current()
        ts = self.current_str()
        is_simple = True  # Is this a non-block statement?
        if ts == 'if':
            stmt = self.parse_if_stmt()
            is_simple = False
        elif ts == 'def':
            stmt = self.parse_function()
            is_simple = False
        elif ts == 'while':
            stmt = self.parse_while_stmt()
            is_simple = False
        elif ts == 'return':
            stmt = self.parse_return_stmt()
        elif ts == 'for':
            stmt = self.parse_for_stmt()
            is_simple = False
        elif ts == 'try':
            stmt = self.parse_try_stmt()
            is_simple = False
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
            is_simple = False
        elif ts == 'global':
            stmt = self.parse_global_decl()
        elif ts == 'nonlocal' and self.pyversion[0] >= 3:
            stmt = self.parse_nonlocal_decl()
        elif ts == 'assert':
            stmt = self.parse_assert_stmt()
        elif ts == 'del':
            stmt = self.parse_del_stmt()
        elif ts == 'with':
            stmt = self.parse_with_stmt()
            is_simple = False
        elif ts == '@':
            stmt = self.parse_decorated_function_or_class()
            is_simple = False
        elif ts == 'print' and (self.pyversion[0] == 2 and
                                'print_function' not in self.future_options):
            stmt = self.parse_print_stmt()
        elif ts == 'exec' and self.pyversion[0] == 2:
            stmt = self.parse_exec_stmt()
        else:
            stmt = self.parse_expression_or_assignment()
        if ts == 'async' and self.current_str() == 'def':
            self.parse_error_at(self.current(),
                                reason='Use --fast-parser to parse code using "async def"')
            raise ParseError()
        if stmt is not None:
            stmt.set_line(t)
        return stmt, is_simple

    def parse_expression_or_assignment(self) -> Node:
        expr = self.parse_expression(star_expr_allowed=True)
        if self.current_str() == '=':
            return self.parse_assignment(expr)
        elif self.current_str() in op_assign:
            # Operator assignment statement.
            op = self.current_str()[:-1]
            self.skip()
            rvalue = self.parse_expression()
            return OperatorAssignmentStmt(op, expr, rvalue)
        else:
            # Expression statement.
            return ExpressionStmt(expr)

    def parse_assignment(self, lvalue: Any) -> Node:
        """Parse an assignment statement.

        Assume that lvalue has been parsed already, and the current token is '='.
        Also parse an optional '# type:' comment.
        """
        self.expect('=')
        lvalues = [lvalue]
        expr = self.parse_expression(star_expr_allowed=True)
        while self.current_str() == '=':
            self.skip()
            lvalues.append(expr)
            expr = self.parse_expression(star_expr_allowed=True)
        cur = self.current()
        if isinstance(cur, Break):
            type = self.parse_type_comment(cur, signature=False)
        else:
            type = None
        return AssignmentStmt(lvalues, expr, type)

    def parse_return_stmt(self) -> ReturnStmt:
        self.expect('return')
        expr = None
        current = self.current()
        if current.string == 'yield':
            self.parse_error()
        if not isinstance(current, Break):
            expr = self.parse_expression()
        node = ReturnStmt(expr)
        return node

    def parse_raise_stmt(self) -> RaiseStmt:
        self.expect('raise')
        expr = None
        from_expr = None
        if not isinstance(self.current(), Break):
            expr = self.parse_expression()
            if self.current_str() == 'from':
                self.expect('from')
                from_expr = self.parse_expression()
        node = RaiseStmt(expr, from_expr)
        return node

    def parse_assert_stmt(self) -> AssertStmt:
        self.expect('assert')
        expr = self.parse_expression()
        node = AssertStmt(expr)
        return node

    def parse_yield_or_yield_from_expr(self) -> Union[YieldFromExpr, YieldExpr]:
        self.expect("yield")
        expr = None
        node = YieldExpr(expr)  # type: Union[YieldFromExpr, YieldExpr]
        if not isinstance(self.current(), Break):
            if self.current_str() == "from":
                self.expect("from")
                expr = self.parse_expression()  # when yield from is assigned to a variable
                node = YieldFromExpr(expr)
            else:
                if self.current_str() == ')':
                    node = YieldExpr(None)
                else:
                    expr = self.parse_expression()
                    node = YieldExpr(expr)
        return node

    def parse_ellipsis(self) -> EllipsisExpr:
        self.expect('...')
        node = EllipsisExpr()
        return node

    def parse_del_stmt(self) -> DelStmt:
        self.expect('del')
        expr = self.parse_expression()
        node = DelStmt(expr)
        return node

    def parse_break_stmt(self) -> BreakStmt:
        self.expect('break')
        node = BreakStmt()
        return node

    def parse_continue_stmt(self) -> ContinueStmt:
        self.expect('continue')
        node = ContinueStmt()
        return node

    def parse_pass_stmt(self) -> PassStmt:
        self.expect('pass')
        node = PassStmt()
        return node

    def parse_global_decl(self) -> GlobalDecl:
        self.expect('global')
        names = self.parse_identifier_list()
        node = GlobalDecl(names)
        return node

    def parse_nonlocal_decl(self) -> NonlocalDecl:
        self.expect('nonlocal')
        names = self.parse_identifier_list()
        node = NonlocalDecl(names)
        return node

    def parse_identifier_list(self) -> List[str]:
        names = []
        while True:
            n = self.expect_type(Name)
            names.append(n.string)
            if self.current_str() != ',':
                break
            self.skip()
        return names

    def parse_while_stmt(self) -> WhileStmt:
        is_error = False
        self.expect('while')
        try:
            expr = self.parse_expression()
        except ParseError:
            is_error = True
        body, _ = self.parse_block()
        if self.current_str() == 'else':
            self.expect('else')
            else_body, _ = self.parse_block()
        else:
            else_body = None
        if is_error is not None:
            node = WhileStmt(expr, body, else_body)
            return node
        else:
            return None

    def parse_for_stmt(self) -> ForStmt:
        self.expect('for')
        index = self.parse_for_index_variables()
        self.expect('in')
        expr = self.parse_expression()

        body, _ = self.parse_block()

        if self.current_str() == 'else':
            self.expect('else')
            else_body, _ = self.parse_block()
        else:
            else_body = None

        node = ForStmt(index, expr, body, else_body)
        return node

    def parse_for_index_variables(self) -> Node:
        # Parse index variables of a 'for' statement.
        index_items = []
        force_tuple = False

        while True:
            v = self.parse_expression(precedence['in'],
                                      star_expr_allowed=True)  # Prevent parsing of for stmt 'in'
            index_items.append(v)
            if self.current_str() != ',':
                break
            self.skip()
            if self.current_str() == 'in':
                force_tuple = True
                break

        if len(index_items) == 1 and not force_tuple:
            index = index_items[0]
        else:
            index = TupleExpr(index_items)
            index.set_line(index_items[0].get_line())

        return index

    def parse_if_stmt(self) -> IfStmt:
        is_error = False

        self.expect('if')
        expr = []
        try:
            expr.append(self.parse_expression())
        except ParseError:
            is_error = True

        body = [self.parse_block()[0]]

        while self.current_str() == 'elif':
            self.expect('elif')
            try:
                expr.append(self.parse_expression())
            except ParseError:
                is_error = True
            body.append(self.parse_block()[0])

        if self.current_str() == 'else':
            self.expect('else')
            else_body, _ = self.parse_block()
        else:
            else_body = None

        if not is_error:
            node = IfStmt(expr, body, else_body)
            return node
        else:
            return None

    def parse_try_stmt(self) -> Node:
        self.expect('try')
        body, _ = self.parse_block()
        is_error = False
        vars = []  # type: List[NameExpr]
        types = []  # type: List[Node]
        handlers = []  # type: List[Block]
        while self.current_str() == 'except':
            self.expect('except')
            if not isinstance(self.current(), Colon):
                try:
                    t = self.current()
                    types.append(self.parse_expression(precedence[',']).set_line(t))
                    if self.current_str() == 'as':
                        self.expect('as')
                        vars.append(self.parse_name_expr())
                    elif self.pyversion[0] == 2 and self.current_str() == ',':
                        self.expect(',')
                        vars.append(self.parse_name_expr())
                    else:
                        vars.append(None)
                except ParseError:
                    is_error = True
            else:
                types.append(None)
                vars.append(None)
            handlers.append(self.parse_block()[0])
        if not is_error:
            if self.current_str() == 'else':
                self.skip()
                else_body, _ = self.parse_block()
            else:
                else_body = None
            if self.current_str() == 'finally':
                self.expect('finally')
                finally_body, _ = self.parse_block()
            else:
                finally_body = None
            node = TryStmt(body, vars, types, handlers, else_body,
                           finally_body)
            return node
        else:
            return None

    def parse_with_stmt(self) -> WithStmt:
        self.expect('with')
        exprs = []
        targets = []
        while True:
            expr = self.parse_expression(precedence[','])
            if self.current_str() == 'as':
                self.expect('as')
                target = self.parse_expression(precedence[','])
            else:
                target = None
            exprs.append(expr)
            targets.append(target)
            if self.current_str() != ',':
                break
            self.expect(',')
        body, _ = self.parse_block()
        return WithStmt(exprs, targets, body)

    def parse_print_stmt(self) -> PrintStmt:
        self.expect('print')
        args = []
        target = None
        if self.current_str() == '>>':
            self.skip()
            target = self.parse_expression(precedence[','])
            if self.current_str() == ',':
                self.skip()
                if isinstance(self.current(), Break):
                    self.parse_error()
            else:
                if not isinstance(self.current(), Break):
                    self.parse_error()
        comma = False
        while not isinstance(self.current(), Break):
            args.append(self.parse_expression(precedence[',']))
            if self.current_str() == ',':
                comma = True
                self.skip()
            else:
                comma = False
                break
        return PrintStmt(args, newline=not comma, target=target)

    def parse_exec_stmt(self) -> ExecStmt:
        self.expect('exec')
        expr = self.parse_expression(precedence['in'])
        variables1 = None
        variables2 = None
        if self.current_str() == 'in':
            self.skip()
            variables1 = self.parse_expression(precedence[','])
            if self.current_str() == ',':
                self.skip()
                variables2 = self.parse_expression(precedence[','])
        return ExecStmt(expr, variables1, variables2)

    # Parsing expressions

    def parse_expression(self, prec: int = 0, star_expr_allowed: bool = False) -> Node:
        """Parse a subexpression within a specific precedence context."""
        expr = None  # type: Node
        current = self.current()  # Remember token for setting the line number.

        # Parse a "value" expression or unary operator expression and store
        # that in expr.
        s = self.current_str()
        if s == '(':
            # Parenthesised expression or cast.
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
        elif s == '*' and star_expr_allowed:
            expr = self.parse_star_expr()
        elif s == '`' and self.pyversion[0] == 2:
            expr = self.parse_backquote_expr()
        else:
            if isinstance(current, Name):
                # Name expression.
                expr = self.parse_name_expr()
            elif isinstance(current, IntLit):
                expr = self.parse_int_expr()
            elif isinstance(current, StrLit):
                expr = self.parse_str_expr()
            elif isinstance(current, BytesLit):
                expr = self.parse_bytes_literal()
            elif isinstance(current, UnicodeLit):
                expr = self.parse_unicode_literal()
            elif isinstance(current, FloatLit):
                expr = self.parse_float_expr()
            elif isinstance(current, ComplexLit):
                expr = self.parse_complex_expr()
            elif isinstance(current, Keyword) and s == "yield":
                # The expression yield from and yield to assign
                expr = self.parse_yield_or_yield_from_expr()
            elif isinstance(current, EllipsisToken) and (self.pyversion[0] >= 3
                                                         or self.is_stub_file):
                expr = self.parse_ellipsis()
            else:
                # Invalid expression.
                self.parse_error()

        # Set the line of the expression node, if not specified. This
        # simplifies recording the line number as not every node type needs to
        # deal with it separately.
        if expr.line < 0:
            expr.set_line(current)

        # Parse operations that require a left argument (stored in expr).
        while True:
            current = self.current()
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
                if isinstance(current, Op):
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
                expr.set_line(current)

        return expr

    def parse_parentheses(self) -> Node:
        self.skip()
        if self.current_str() == ')':
            # Empty tuple ().
            expr = self.parse_empty_tuple_expr()  # type: Node
        else:
            # Parenthesised expression.
            expr = self.parse_expression(0, star_expr_allowed=True)
            self.expect(')')
        return expr

    def parse_star_expr(self) -> Node:
        star = self.expect('*')
        expr = self.parse_expression(precedence['*u'])
        expr = StarExpr(expr)
        if expr.line < 0:
            expr.set_line(star)
        return expr

    def parse_empty_tuple_expr(self) -> TupleExpr:
        self.expect(')')
        node = TupleExpr([])
        return node

    def parse_list_expr(self) -> Node:
        """Parse list literal or list comprehension."""
        items = []
        self.expect('[')
        while self.current_str() != ']' and not self.eol():
            items.append(self.parse_expression(precedence['<for>'], star_expr_allowed=True))
            if self.current_str() != ',':
                break
            self.expect(',')
        if self.current_str() == 'for' and len(items) == 1:
            items[0] = self.parse_generator_expr(items[0])
        self.expect(']')
        if len(items) == 1 and isinstance(items[0], GeneratorExpr):
            return ListComprehension(items[0])
        else:
            expr = ListExpr(items)
            return expr

    def parse_generator_expr(self, left_expr: Node) -> GeneratorExpr:
        tok = self.current()
        indices, sequences, condlists = self.parse_comp_for()

        gen = GeneratorExpr(left_expr, indices, sequences, condlists)
        gen.set_line(tok)
        return gen

    def parse_comp_for(self) -> Tuple[List[Node], List[Node], List[List[Node]]]:
        indices = []
        sequences = []
        condlists = []  # type: List[List[Node]]
        while self.current_str() == 'for':
            conds = []
            self.expect('for')
            index = self.parse_for_index_variables()
            indices.append(index)
            self.expect('in')
            if self.pyversion[0] >= 3:
                sequence = self.parse_expression(precedence['<if>'])
            else:
                sequence = self.parse_expression_list()
            sequences.append(sequence)
            while self.current_str() == 'if':
                self.skip()
                conds.append(self.parse_expression(precedence['<if>']))
            condlists.append(conds)

        return indices, sequences, condlists

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
        items = []  # type: List[Tuple[Node, Node]]
        self.expect('{')
        while self.current_str() != '}' and not self.eol():
            key = self.parse_expression(precedence['<for>'])
            if self.current_str() in [',', '}'] and items == []:
                return self.parse_set_expr(key)
            elif self.current_str() == 'for' and items == []:
                return self.parse_set_comprehension(key)
            elif self.current_str() != ':':
                self.parse_error()
            colon = self.expect(':')
            value = self.parse_expression(precedence['<for>'])
            if self.current_str() == 'for' and items == []:
                return self.parse_dict_comprehension(key, value, colon)
            items.append((key, value))
            if self.current_str() != ',':
                break
            self.expect(',')
        self.expect('}')
        node = DictExpr(items)
        return node

    def parse_set_expr(self, first: Node) -> SetExpr:
        items = [first]
        while self.current_str() != '}' and not self.eol():
            self.expect(',')
            if self.current_str() == '}':
                break
            items.append(self.parse_expression(precedence[',']))
        self.expect('}')
        expr = SetExpr(items)
        return expr

    def parse_set_comprehension(self, expr: Node) -> SetComprehension:
        gen = self.parse_generator_expr(expr)
        self.expect('}')
        set_comp = SetComprehension(gen)
        return set_comp

    def parse_dict_comprehension(self, key: Node, value: Node,
                                 colon: Token) -> DictionaryComprehension:
        indices, sequences, condlists = self.parse_comp_for()
        dic = DictionaryComprehension(key, value, indices, sequences, condlists)
        dic.set_line(colon)
        self.expect('}')
        return dic

    def parse_tuple_expr(self, expr: Node,
                         prec: int = precedence[',']) -> TupleExpr:
        items = [expr]
        while True:
            self.expect(',')
            if (self.current_str() in [')', ']', '=', ':'] or
                    isinstance(self.current(), Break)):
                break
            items.append(self.parse_expression(prec, star_expr_allowed=True))
            if self.current_str() != ',': break
        node = TupleExpr(items)
        return node

    def parse_backquote_expr(self) -> BackquoteExpr:
        self.expect('`')
        expr = self.parse_expression()
        self.expect('`')
        return BackquoteExpr(expr)

    def parse_name_expr(self) -> NameExpr:
        tok = self.expect_type(Name)
        node = NameExpr(tok.string)
        node.set_line(tok)
        return node

    octal_int = re.compile('0+[1-9]')

    def parse_int_expr(self) -> IntExpr:
        tok = self.expect_type(IntLit)
        string = tok.string.rstrip('lL')  # Strip L prefix (Python 2 long literals)
        if self.octal_int.match(string):
            value = int(string, 8)
        else:
            value = int(string, 0)
        node = IntExpr(value)
        return node

    def parse_str_expr(self) -> Node:
        # XXX \uxxxx literals
        token = self.expect_type(StrLit)
        value = cast(StrLit, token).parsed()
        is_unicode = False
        while isinstance(self.current(), (StrLit, UnicodeLit)):
            token = self.skip()
            if isinstance(token, StrLit):
                value += token.parsed()
            elif isinstance(token, UnicodeLit):
                value += token.parsed()
                is_unicode = True
        if is_unicode or (self.pyversion[0] == 2 and 'unicode_literals' in self.future_options):
            node = UnicodeExpr(value)  # type: Node
        else:
            node = StrExpr(value)
        return node

    def parse_bytes_literal(self) -> Node:
        # XXX \uxxxx literals
        tok = [self.expect_type(BytesLit)]
        value = (cast(BytesLit, tok[0])).parsed()
        while isinstance(self.current(), BytesLit):
            t = cast(BytesLit, self.skip())
            value += t.parsed()
        if self.pyversion[0] >= 3:
            node = BytesExpr(value)  # type: Node
        else:
            node = StrExpr(value)
        return node

    def parse_unicode_literal(self) -> Node:
        # XXX \uxxxx literals
        token = self.expect_type(UnicodeLit)
        value = cast(UnicodeLit, token).parsed()
        while isinstance(self.current(), (UnicodeLit, StrLit)):
            token = cast(Union[UnicodeLit, StrLit], self.skip())
            value += token.parsed()
        if self.pyversion[0] >= 3:
            # Python 3.3 supports u'...' as an alias of '...'.
            node = StrExpr(value)  # type: Node
        else:
            node = UnicodeExpr(value)
        return node

    def parse_float_expr(self) -> FloatExpr:
        tok = self.expect_type(FloatLit)
        node = FloatExpr(float(tok.string))
        return node

    def parse_complex_expr(self) -> ComplexExpr:
        tok = self.expect_type(ComplexLit)
        node = ComplexExpr(complex(tok.string))
        return node

    def parse_call_expr(self, callee: Any) -> CallExpr:
        self.expect('(')
        args, kinds, names = self.parse_arg_expr()
        self.expect(')')
        node = CallExpr(callee, args, kinds, names)
        return node

    def parse_arg_expr(self) -> Tuple[List[Node], List[int], List[str]]:
        """Parse arguments in a call expression (within '(' and ')').

        Return a tuple with these items:
          argument expressions
          argument kinds
          argument names (for named arguments; None for ordinary args)
        """
        args = []   # type: List[Node]
        kinds = []  # type: List[int]
        names = []  # type: List[str]
        var_arg = False
        dict_arg = False
        named_args = False
        while self.current_str() != ')' and not self.eol() and not dict_arg:
            if isinstance(self.current(), Name) and self.peek().string == '=':
                # Named argument
                name = self.expect_type(Name)
                self.expect('=')
                kinds.append(nodes.ARG_NAMED)
                names.append(name.string)
                named_args = True
            elif (self.current_str() == '*' and not var_arg and not dict_arg):
                # *args
                var_arg = True
                self.expect('*')
                kinds.append(nodes.ARG_STAR)
                names.append(None)
            elif self.current_str() == '**':
                # **kwargs
                self.expect('**')
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
            self.expect(',')
        return args, kinds, names

    def parse_member_expr(self, expr: Any) -> Node:
        self.expect('.')
        name = self.expect_type(Name)
        if (isinstance(expr, CallExpr) and isinstance(expr.callee, NameExpr)
                and expr.callee.name == 'super'):
            # super() expression
            node = SuperExpr(name.string)  # type: Node
        else:
            node = MemberExpr(expr, name.string)
        return node

    def parse_index_expr(self, base: Any) -> IndexExpr:
        self.expect('[')
        index = self.parse_slice_item()
        if self.current_str() == ',':
            # Extended slicing such as x[1:, :2].
            items = [index]
            while self.current_str() == ',':
                self.skip()
                if self.current_str() == ']' or isinstance(self.current(), Break):
                    break
                items.append(self.parse_slice_item())
            index = TupleExpr(items)
            index.set_line(items[0].line)
        self.expect(']')
        node = IndexExpr(base, index)
        return node

    def parse_slice_item(self) -> Node:
        if self.current_str() != ':':
            if self.current_str() == '...':
                # Ellipsis is valid here even in Python 2 (but not elsewhere).
                ellipsis = EllipsisExpr()
                token = self.skip()
                ellipsis.set_line(token)
                return ellipsis
            else:
                item = self.parse_expression(precedence[','])
        else:
            item = None
        if self.current_str() == ':':
            # Slice.
            index = item
            colon = self.expect(':')
            if self.current_str() not in (']', ':', ','):
                end_index = self.parse_expression(precedence[','])
            else:
                end_index = None
            stride = None
            if self.current_str() == ':':
                self.expect(':')
                if self.current_str() not in (']', ','):
                    stride = self.parse_expression(precedence[','])
            item = SliceExpr(index, end_index, stride).set_line(colon.line)
        return item

    def parse_bin_op_expr(self, left: Node, prec: int) -> OpExpr:
        op = self.expect_type(Op)
        op_str = op.string
        if op_str == '~':
            self.ind -= 1
            self.parse_error()
        right = self.parse_expression(prec)
        node = OpExpr(op_str, left, right)
        return node

    def parse_comparison_expr(self, left: Node, prec: int) -> ComparisonExpr:
        operators_str = []
        operands = [left]

        while True:
            op = self.expect_type(Op)
            op_str = op.string
            if op_str == 'not':
                if self.current_str() == 'in':
                    op_str = 'not in'
                    self.skip()
                else:
                    self.parse_error()
            elif op_str == 'is' and self.current_str() == 'not':
                op_str = 'is not'
                self.skip()

            operators_str.append(op_str)
            operand = self.parse_expression(prec)
            operands.append(operand)

            # Continue if next token is a comparison operator
            self.current()
            s = self.current_str()
            if s not in op_comp:
                break

        node = ComparisonExpr(operators_str, operands)
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
        return node

    def parse_lambda_expr(self) -> FuncExpr:
        lambda_tok = self.expect('lambda')

        args, extra_stmts = self.parse_arg_list(allow_signature=False)

        # Use 'object' as the placeholder return type; it will be inferred
        # later. We can't use 'Any' since it could make type inference results
        # less precise.
        ret_type = UnboundType('__builtins__.object')
        typ = self.build_func_annotation(ret_type, args,
                                         lambda_tok.line, is_default_ret=True)

        colon = self.expect(':')

        expr = self.parse_expression(precedence[','])

        nodes = [ReturnStmt(expr).set_line(lambda_tok)]
        # Potentially insert extra assignment statements to the beginning of the
        # body, used to decompose Python 2 tuple arguments.
        nodes[:0] = extra_stmts
        body = Block(nodes)
        body.set_line(colon)

        return FuncExpr(args, body, typ)

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
        current = self.current()
        if isinstance(current, typ):
            self.ind += 1
            return current
        else:
            self.parse_error()

    def expect_colon_and_break(self) -> Tuple[Token, Token]:
        return self.expect_type(Colon), self.expect_type(Break)

    def expect_break(self) -> Token:
        return self.expect_type(Break)

    def current(self) -> Token:
        return self.tok[self.ind]

    def current_str(self) -> str:
        return self.current().string

    def peek(self) -> Token:
        return self.tok[self.ind + 1]

    def parse_error(self) -> None:
        self.parse_error_at(self.current())
        raise ParseError()

    def parse_error_at(self, tok: Token, skip: bool = True, reason: Optional[str] = None) -> None:
        msg = ''
        if isinstance(tok, LexError):
            msg = token_repr(tok)
            msg = msg[0].upper() + msg[1:]
        elif isinstance(tok, Indent) or isinstance(tok, Dedent):
            msg = 'Inconsistent indentation'
        else:
            formatted_reason = ": {}".format(reason) if reason else ""
            msg = 'Parse error before {}{}'.format(token_repr(tok), formatted_reason)

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
        try:
            typ, self.ind = parse_type(self.tok, self.ind)
        except TypeParseError as e:
            self.parse_error_at(e.token, reason=e.message)
            raise ParseError()
        return typ

    annotation_prefix_re = re.compile(r'#\s*type:')
    ignore_prefix_re = re.compile(r'ignore\b')

    def parse_type_comment(self, token: Token, signature: bool) -> Type:
        """Parse a '# type: ...' annotation.

        Return None if no annotation found. If signature is True, expect
        a type signature of form (...) -> t.
        """
        whitespace_or_comments = token.rep().strip()
        if self.annotation_prefix_re.match(whitespace_or_comments):
            type_as_str = whitespace_or_comments.split(':', 1)[1].strip()
            if self.ignore_prefix_re.match(type_as_str):
                # Actually a "# type: ignore" annotation -> not a type.
                return None
            tokens = lex.lex(type_as_str, token.line)[0]
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
                self.parse_error_at(e.token, skip=False, reason=e.message)
                return None
            if index < len(tokens) - 2:
                self.parse_error_at(tokens[index], skip=False)
                return None
            return type
        else:
            return None


class ParseError(Exception): pass


def token_repr(tok: Token) -> str:
    """Return a representation of a token for use in parse error messages."""
    if isinstance(tok, Break):
        return 'end of line'
    elif isinstance(tok, Eof):
        return 'end of file'
    elif isinstance(tok, Keyword) or isinstance(tok, Name):
        return '"{}"'.format(tok.string)
    elif isinstance(tok, IntLit) or isinstance(tok, FloatLit) or isinstance(tok, ComplexLit):
        return 'numeric literal'
    elif isinstance(tok, StrLit) or isinstance(tok, UnicodeLit):
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
    elif isinstance(tok, EllipsisToken):
        return '...'
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
            elif t == lex.INVALID_DEDENT:
                return 'inconsistent indentation'
            elif t == lex.DECODE_ERROR:
                return tok.message
        raise ValueError('Unknown token {}'.format(repr(tok)))


if __name__ == '__main__':
    # Parse a file and dump the AST (or display errors).
    import sys

    def usage() -> None:
        print('Usage: parse.py [--py2] [--quiet] FILE [...]', file=sys.stderr)
        sys.exit(2)

    args = sys.argv[1:]
    pyversion = defaults.PYTHON3_VERSION
    quiet = False
    while args and args[0].startswith('--'):
        if args[0] == '--py2':
            pyversion = defaults.PYTHON2_VERSION
        elif args[0] == '--quiet':
            quiet = True
        else:
            usage()
        args = args[1:]
    if len(args) < 1:
        usage()
    status = 0
    for fnam in args:
        s = open(fnam, 'rb').read()
        errors = Errors()
        try:
            options = Options()
            options.python_version = pyversion
            tree = parse(s, fnam, None, options=options)
            if not quiet:
                print(tree)
        except CompileError as e:
            for msg in e.messages:
                sys.stderr.write('%s\n' % msg)
            status = 1
    sys.exit(status)
