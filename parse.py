"""Mypy parser. Constructs a parse tree based on a string representing a
source file. Performs only minimal semantic checks."""

import lex
from lex import (Token, Eof, Bom, Break, Name, Colon, Dedent, IntLit,
                 StrLit, BytesLit, FloatLit, Op, Indent, Keyword, Name, Punct,
                 LexError)
from nodes import (
    MypyFile, Import, Node, ImportAll, ImportFrom, FuncDef, OverloadedFuncDef,
    TypeDef, Decorator, Annotation, Block, Var, VarDef, OperatorAssignmentStmt,
    ExpressionStmt, AssignmentStmt, ReturnStmt, RaiseStmt, AssertStmt,
    YieldStmt, DelStmt, BreakStmt, ContinueStmt, PassStmt, GlobalDecl,
    WhileStmt, ForStmt, IfStmt, TryStmt, WithStmt, CastExpr, ParenExpr,
    TupleExpr, GeneratorExpr, ListComprehension, ListExpr, ConditionalExpr,
    DictExpr, SetExpr, NameExpr, IntExpr, StrExpr, BytesExpr, FloatExpr,
    CallExpr, SuperExpr, MemberExpr, IndexExpr, SliceExpr, OpExpr, UnaryExpr,
    FuncExpr, TypeApplication
)
import nodes
import noderepr
from errors import Errors
from mtypes import Void, Typ, TypeVars, Callable, Any
from parsetype import (parse_type, parse_type_variables, parse_type_args,
                       TypeParseError)


int HIGHEST_PREC = 14

precedence = {
    '**': 15,
    '-u': 14, '+u': 14, '~': 14,
    '<cast>': 13,
    '*': 12, '/': 12, '//': 12, '%': 12,
    '+': 11, '-': 11,
    '>>': 10, '<<': 10,
    '&': 9,
    '^': 8,
    '|': 7,
    '==': 6, '!=': 6, '<': 6, '>': 6, '<=': 6, '>=': 6, 'is': 6, 'in': 6,
    'not': 5,
    'and': 4,
    'or': 3,
    '<if>': 2, # conditional expression
    '<for>': 2, # list comprehension
    ',': 1}


op_assign = set([
    '+=', '-=', '*=', '/=', '//=', '%=', '**=', '|=', '&=', '^=', '>>=',
    '<<='])


none = Token('') # Empty token


MypyFile parse(str s, str fnam=None, Errors errors=None):
    """Parse a source file, without doing any semantic
    analysis. Return the parse tree (MypyFile object).
    
    If errors is not provided, raise ParseError on failure. Otherwise, use
    the errors object to report parse errors.
    """
    parser = Parser(fnam, errors)
    tree = parser.parse(s)
    tree.path = fnam
    return tree


class Parser:
    Token[] tok
    int ind
    Errors errors
    bool raise_on_error
    
    # Are we currently parsing a function definition?
    bool is_function = False
    # Are we currently parsing a type definition?
    bool is_type = False
    
    void __init__(self, str fnam, Errors errors):
        self.raise_on_error = errors is None
        if errors is not None:
            self.errors = errors
        else:
            self.errors = Errors()
        if fnam is not None:
            self.errors.set_file(fnam)
        else:
            self.errors.set_file('<input>')
    
    MypyFile parse(self, str s):
        self.tok = lex.lex(s)
        self.ind = 0
        file = self.parse_file()
        if self.raise_on_error and self.errors.is_errors():
            self.errors.raise_error()
        return file
    
    MypyFile parse_file(self):
        """Parse a mypy source file."""
        is_bom = self.parse_bom()
        defs = self.parse_defs()
        eof = self.expect_type(Eof)
        node = MypyFile(defs, is_bom)
        self.set_repr(node, noderepr.MypyFileRepr(eof))
        return node
    
    # Parse the initial part
    
    bool parse_bom(self):
        """Parse the optional byte order mark at the beginning of a file."""
        if isinstance(self.current(), Bom):
            self.expect_type(Bom)
            if isinstance(self.current(), Break):
                self.expect_break()
            return True
        else:
            return False
    
    Import parse_import(self):
        import_tok = self.expect('import')
        list<tuple<str, str>> ids = []
        Token[][] id_toks = []
        Token[] commas = []
        list<tuple<Token, Token>> as_names = []
        while True:
            id, components = self.parse_qualified_name()
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
        self.set_repr(node, noderepr.ImportRepr(import_tok, id_toks, as_names,
                                                commas, br))
        return node
    
    Node parse_import_from(self):
        from_tok = self.expect('from')
        name, components = self.parse_qualified_name()
        import_tok = self.expect('import')
        name_toks = <tuple<Token[], Token>> []
        lparen = none
        rparen = none
        Node node
        if self.current_str() == '*':
            name_toks.append(([self.skip()], none))
            node = ImportAll(name)
        else:
            is_paren = self.current_str() == '('
            if is_paren:
                lparen = self.expect('(')
            targets = <tuple<str, str>> []
            while True:
                id, as_id, toks = self.parse_import_name()
                targets.append((id, as_id))
                if self.current_str() != ',':
                    name_toks.append((toks, none))
                    break
                name_toks.append((toks, self.expect(',')))
                if is_paren and self.current_str() == ')':
                    break
            if is_paren:
                rparen = self.expect(')')
            node = ImportFrom(name, targets)
        br = self.expect_break()
        self.set_repr(node, noderepr.ImportFromRepr(
            from_tok, components,import_tok, lparen, name_toks, rparen, br))
        return node
    
    tuple<str, str, Token[]> parse_import_name(self):
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
    
    tuple<str, Token[]> parse_qualified_name(self):
        """Parse a name with an optional module qualifier. Return a
        tuple with the name as a string and a token array containing
        all the components of the name.
        """
        components = <Token> []
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
    
    Node[] parse_defs(self):
        defs = <Node> []
        while not self.eof():
            try:
                defn = self.parse_statement()
                if defn is not None:
                    if isinstance(defn, FuncDef) and defs != []:
                        fdef = (FuncDef)defn
                        n = fdef.name()
                        if (isinstance(defs[-1], FuncDef) and
                                ((FuncDef)defs[-1]).name() == n):
                            defs[-1] = OverloadedFuncDef([(FuncDef)defs[-1],
                                                          fdef])
                        elif (isinstance(defs[-1], OverloadedFuncDef) and
                                  ((OverloadedFuncDef)defs[-1]).name() == n):
                            ((OverloadedFuncDef)defs[-1]).items.append(fdef)
                        else:
                            defs.append(defn)
                    else:
                        defs.append(defn)
            except ParseError:
                pass
        return defs
    
    def parse_type_def(self, is_interface):
        self.is_type = True
        
        # Skip "class" or "interface".
        type_tok = self.skip()
        lparen = none
        rparen = none
        
        try:
            type_vars, commas, base_types = None, [], []
            try:
                name_tok = self.expect_type(Name)
                name = name_tok.string
                
                self.errors.set_type(name, is_interface)
                
                if self.current_str() == '<':
                    try:
                        type_vars, self.ind = parse_type_variables(
                            self.tok, self.ind, False)
                    except TypeParseError as e:
                        self.parse_error_at(e.token)
                
                if self.current_str() == '(':
                    lparen = self.skip()
                    while True:
                        base_types.append(self.parse_super_type())
                        if self.current_str() != ',':
                            break
                        commas.append(self.skip())
                    rparen = self.expect(')')
            except ParseError:
                pass
            
            defs = self.parse_block(is_interface)
            
            node = TypeDef(name, defs, type_vars, base_types, is_interface)
            self.set_repr(node, noderepr.TypeDefRepr(type_tok, name_tok,
                                                     lparen, commas, rparen))
            return node
        finally:
            self.errors.set_type(None, False)
            self.is_type = False
    
    def parse_super_type(self):
        if (isinstance(self.current(), Name) and self.current_str() != 'void'):
            return self.parse_type().typ
        else:
            self.parse_error()
    
    FuncDef parse_function(self, bool is_in_interface=False):
        if self.current_str() == 'def':
            def_tok = self.skip()
            return self.parse_function_at_name(None, def_tok, is_in_interface)
        else:
            t = self.parse_type()
            return self.parse_function_at_name(t, None, is_in_interface)
    
    Node parse_function_or_var(self):
        typ = self.parse_type()
        if self.peek().string in ['(', '<'] or isinstance(typ, Void):
            return self.parse_function_at_name(typ, None)
        else:
            return self.parse_var_def(typ.typ)
    
    Node parse_decorated_function(self):
        at = self.expect('@')
        decorator = self.parse_expression()
        br = self.expect_break()
        Node target
        if self.current_str() == '@':
            target = self.parse_decorated_function()
        else:
            target = self.parse_function()
        node = Decorator(target, decorator)
        self.set_repr(node, noderepr.DecoratorRepr(at, br))
        return node
    
    FuncDef parse_function_at_name(self, Annotation ret_type, Token def_tok,
                                   bool is_in_interface=False):
        self.is_function = True
        try:
            (name, args, init, kinds,
             typ, is_error, toks) = self.parse_function_header(ret_type)
            
            if is_in_interface and isinstance(self.current(), Break):
                body = Block([])
                br = self.expect_break()
                self.set_repr(body, noderepr.BlockRepr(none, br, none, none))
            else:
                body = self.parse_block()
            
            # If there was a serious error, we really cannot build a parse tree
            # node.
            if is_error:
                return None
            
            node = FuncDef(name, args, kinds, init, body, typ)
            name_tok, arg_reprs = toks
            self.set_repr(node, noderepr.FuncRepr(def_tok, name_tok,
                                                  arg_reprs))
            return node
        finally:
            self.errors.set_function(None)
            self.is_function = False
    
    tuple<str, Var[], Node[], int[], Annotation, bool, tuple<Token, any>> \
              parse_function_header(self, Annotation ret_type):
        """Parse function header (a name followed by arguments)

        Returns a 9-tuple with the following items:
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
            
            self.errors.set_function(name)
            
            (args, init, kinds, typ, arg_repr) = self.parse_args(ret_type)
        except ParseError:
            if not isinstance(self.current(), Break):
                self.ind -= 1 # Kludge: go back to the Break token
            # Resynchronise parsing by going back over :, if present.
            if isinstance(self.tok[self.ind - 1], Colon):
                self.ind -= 1
            return (name, [], [], [], None, True, (name_tok, None))
        
        return (name, args, init, kinds, typ, False, (name_tok, arg_repr))
    
    tuple<Var[], Node[], int[], Annotation, \
          noderepr.FuncArgsRepr> parse_args(self, Annotation ret_type):
        """Parse a function type signature.

        It is potentially prefixed with type variable specification within
        <...>.
        """        
        type_vars = self.parse_type_vars()
        
        lparen = self.expect('(')
        
        # Parse the argument list (everything within '(' and ')').
        (args, init, kinds,
         has_inits, arg_names,
         commas, asterisk,
         assigns, arg_types) = self.parse_arg_list()
        
        rparen = self.expect(')')

        self.verify_argument_kinds(kinds, lparen.line)
        
        names = <str> []
        for arg in args:
            names.append(arg.name())
        
        annotation = self.build_func_annotation(
            ret_type, arg_types, kinds, names, type_vars, lparen.line)
        
        return (args, init, kinds, annotation,
                noderepr.FuncArgsRepr(lparen, rparen, arg_names, commas,
                                      assigns, asterisk))
    
    Annotation build_func_annotation(self, Annotation ret_type,
                                     Typ[] arg_types, int[] kinds,
                                     str[] names, TypeVars type_vars,
                                     int line):
        # Are there any type annotations?
        if (ret_type or arg_types != [None] * len(arg_types)
                or type_vars.items):
            # Yes. Construct a type for the function signature.
            Typ ret = None
            if ret_type is not None:
                ret = ret_type.typ
            typ = self.construct_function_type(arg_types, kinds, names,
                                               ret, type_vars, line)
            annotation = Annotation(typ, line)
            self.set_repr(annotation, noderepr.AnnotationRepr())
            return annotation
        else:
            return None
    
    tuple<Var[], Node[], int[], bool, Token[], Token[], Token[], Token[], \
                     Typ[]> parse_arg_list(self):
        """Parse function definition argument list.

        This includes everything between '(' and ')').

        Return a 9-tuple with these items:
          arguments, initializers, kinds, has inits, arg name tokens,
          comma tokens, asterisk tokens, assignment tokens, argument types
        """
        args = <Var> []
        kinds = <int> []
        names = <str> []
        init = <Node> []
        has_inits = False
        arg_types = <Typ> []        
        
        arg_names = <Token> []
        commas = <Token> []
        asterisk = <Token> []
        assigns = <Token> []
        
        require_named = False
        
        if self.current_str() != ')' and self.current_str() != ':':
            while self.current_str() != ')':
                Typ arg_type = None
                if self.is_at_sig_type():
                    arg_type = self.parse_type().typ
                arg_types.append(arg_type)
                
                if self.current_str() == '*' and self.peek().string == ',':
                    self.expect('*')
                    require_named = True
                    arg_types.pop()
                elif self.current_str() in ['*', '**']:
                    asterisk.append(self.skip())
                    isdict = asterisk[-1].string == '**'
                    name = self.expect_type(Name)
                    arg_names.append(name)
                    names.append(name.string)
                    var_arg = Var(name.string)
                    self.set_repr(var_arg, noderepr.VarRepr(name, none))
                    args.append(var_arg)
                    init.append(None)
                    if isdict:
                        kinds.append(nodes.ARG_STAR2)
                    else:
                        kinds.append(nodes.ARG_STAR)
                else:
                    name = self.expect_type(Name)
                    arg_names.append(name)
                    args.append(Var(name.string))
                    
                    if self.current_str() == '=':
                        assigns.append(self.expect('='))
                        init.append(self.parse_expression(precedence[',']))
                        has_inits = True
                        if require_named:
                            kinds.append(nodes.ARG_NAMED)
                        else:
                            kinds.append(nodes.ARG_OPT)
                    else:
                        if require_named:
                            self.parse_error()
                        init.append(None)
                        assigns.append(none)
                        kinds.append(nodes.ARG_POS)
                
                if self.current().string != ',':
                    break
                commas.append(self.expect(','))
        
        return (args, init, kinds, has_inits, arg_names, commas, asterisk,
                assigns, arg_types)

    void verify_argument_kinds(self, int[] kinds, int line):
        set<int> found = set()
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
    
    Callable construct_function_type(self, Typ[] arg_types, int[] kinds,
                                     str[] names, Typ ret_type,
                                     TypeVars type_vars, int line):
        # Complete the type annotation by replacing omitted types with
        # dynamic/void.
        arg_types = arg_types[:]
        for i in range(len(arg_types)):
            if arg_types[i] is None:
                arg_types[i] = Any()
        if ret_type is None:
            ret_type = Any()
        return Callable(arg_types, kinds, names, ret_type, False, None,
                        type_vars, [], line, None)
    
    # Parsing statements
    
    VarDef parse_var_def(self, Typ typ):
        """Parse variable definition with explicit types."""
        n = self.parse_var_list(typ)
        Node init = None
        assign_token = none
        if self.current_str() == '=':
            assign_token = self.expect('=')
            init = self.parse_expression(0)
        for nn, t in n:
            nn.is_init = init is not None
        br = self.expect_break()
        
        node = VarDef(n, self.is_at_top_level(), init)
        self.set_repr(node, noderepr.VarDefRepr(assign_token, br))
        return node
    
    tuple<Var, Typ>[] parse_var_list(self, Typ first_type):
        """Parse a comma-separated list of variable names, potentially
        prefixed by type declarations.
        """
        tok = self.expect_type(Name)
        n = [(Var(tok.string), first_type)]
        r = [noderepr.VarRepr(tok, none)]
        while self.current_str() == ',':
            tok = self.expect(',')
            r[-1] = noderepr.VarRepr(r[-1].name, tok)
            
            Typ t = None
            if self.is_at_type():
                t = self.parse_type().typ
            tok = self.expect_type(Name)
            n.append((Var(tok.string), t))
            r.append(noderepr.VarRepr(tok, none))
        for i in range(len(n)):
            self.set_repr(n[i][0], r[i])
        return n
    
    # Parsing statements
    
    Block parse_block(self, bool interface_body=False):
        colon = self.expect(':')
        if not isinstance(self.current(), Break):
            # Block immediately after ':'.
            node = Block([self.parse_statement()]).set_line(colon)
            self.set_repr(node, noderepr.BlockRepr(colon, none, none, none))
            return (Block)node
        else:
            # Indented block.
            br = self.expect_break()
            indent = self.expect_indent()
            stmt = <Node> []
            # Always allow a doc string at the beginning of a block.
            if (isinstance(self.current(), StrLit) and
                    isinstance(self.peek(), Break)):
                stmt.append(self.parse_statement())
            while (not isinstance(self.current(), Dedent) and
                   not isinstance(self.current(), Eof)):
                try:
                    Node s
                    if interface_body:
                        t = self.current()
                        s = self.parse_interface_body_def()
                        s.set_line(t)
                    else:
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
            return (Block)node

    bool try_combine_overloads(self, Node s, Node[] stmt):
        if isinstance(s, FuncDef) and stmt:
            fdef = (FuncDef)s
            n = fdef.name()
            if (isinstance(stmt[-1], FuncDef) and
                    ((FuncDef)stmt[-1]).name() == n):
                stmt[-1] = OverloadedFuncDef([(FuncDef)stmt[-1], fdef])
                return True
            elif (isinstance(stmt[-1], OverloadedFuncDef) and
                      ((OverloadedFuncDef)stmt[-1]).name() == n):
                ((OverloadedFuncDef)stmt[-1]).items.append(fdef)
                return True
        return False
    
    Node parse_interface_body_def(self):
        if self.current_str() == 'pass':
            return self.parse_pass_stmt()
        else:
            return self.parse_function(True)
    
    Node parse_statement(self):
        Node stmt
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
            stmt = self.parse_type_def(False)
        elif ts == 'interface':
            stmt = self.parse_type_def(True)
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
            stmt = self.parse_decorated_function()
        else:
            if self.is_at_type():
                stmt = self.parse_function_or_var()
            else:
                stmt = self.parse_expression_or_assignment()
        if stmt is not None:
            stmt.set_line(t)
        return stmt
    
    Node parse_expression_or_assignment(self):
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
    
    AssignmentStmt parse_assignment(self, any lv):
        """Parse an assignment statement. Assume that lvalue has been parsed
        already, and the current token is =.
        """
        assigns = [self.expect('=')]
        lvalues = [lv]
        
        e = self.parse_expression()
        while self.current_str() == '=':
            lvalues.append(e)
            assigns.append(self.skip())
            e = self.parse_expression()
        
        br = self.expect_break()
        
        node = AssignmentStmt(lvalues, e)
        self.set_repr(node, noderepr.AssignmentStmtRepr(assigns, br))
        return node
    
    ReturnStmt parse_return_stmt(self):
        return_tok = self.expect('return')
        Node expr = None
        if not isinstance(self.current(), Break):
            expr = self.parse_expression()
        br = self.expect_break()
        node = ReturnStmt(expr)
        self.set_repr(node, noderepr.SimpleStmtRepr(return_tok, br))
        return node
    
    RaiseStmt parse_raise_stmt(self):
        raise_tok = self.expect('raise')
        Node expr = None
        Node from_expr = None
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
    
    AssertStmt parse_assert_stmt(self):
        assert_tok = self.expect('assert')
        expr = self.parse_expression()
        br = self.expect_break()
        node = AssertStmt(expr)
        self.set_repr(node, noderepr.SimpleStmtRepr(assert_tok, br))
        return node
    
    YieldStmt parse_yield_stmt(self):
        yield_tok = self.expect('yield')
        Node expr = None
        if not isinstance(self.current(), Break):
            expr = self.parse_expression()
        br = self.expect_break()
        node = YieldStmt(expr)
        self.set_repr(node, noderepr.SimpleStmtRepr(yield_tok, br))
        return node
    
    DelStmt parse_del_stmt(self):
        del_tok = self.expect('del')
        expr = self.parse_expression()
        br = self.expect_break()
        node = DelStmt(expr)
        self.set_repr(node, noderepr.SimpleStmtRepr(del_tok, br))
        return node
    
    BreakStmt parse_break_stmt(self):
        break_tok = self.expect('break')
        br = self.expect_break()
        node = BreakStmt()
        self.set_repr(node, noderepr.SimpleStmtRepr(break_tok, br))
        return node
    
    ContinueStmt parse_continue_stmt(self):
        continue_tok = self.expect('continue')
        br = self.expect_break()
        node = ContinueStmt()
        self.set_repr(node, noderepr.SimpleStmtRepr(continue_tok, br))
        return node
    
    PassStmt parse_pass_stmt(self):
        pass_tok = self.expect('pass')
        br = self.expect_break()
        node = PassStmt()
        self.set_repr(node, noderepr.SimpleStmtRepr(pass_tok, br))
        return node
    
    GlobalDecl parse_global_decl(self):
        global_tok = self.expect('global')
        str[] names = []
        Token[] name_toks = []
        Token[] commas = []    
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
    
    WhileStmt parse_while_stmt(self):
        is_error = False
        while_tok = self.expect('while')
        Node expr
        try:
            expr = self.parse_expression()
        except ParseError:
            is_error = True
        body = self.parse_block()
        Block else_body = None
        else_tok = none
        if self.current_str() == 'else':
            else_tok = self.expect('else')
            else_body = self.parse_block()
        if is_error is not None:
            node = WhileStmt(expr, body, else_body)
            self.set_repr(node, noderepr.WhileStmtRepr(while_tok, else_tok))
            return node
        else:
            return None
    
    ForStmt parse_for_stmt(self):
        for_tok = self.expect('for')
        index, types, commas = self.parse_for_index_variables()
        in_tok = self.expect('in')
        expr = self.parse_expression()
        
        body = self.parse_block()
        
        Block else_body = None
        else_tok = none
        if self.current_str() == 'else':
            else_tok = self.expect('else')
            else_body = self.parse_block()
        
        node = ForStmt(index, expr, body, else_body, types)
        self.set_repr(node, noderepr.ForStmtRepr(for_tok, commas, in_tok,
                                                 else_tok))
        return node
    
    tuple<NameExpr[], Annotation[], Token[]> \
                              parse_for_index_variables(self):
        # Parse index variables of a 'for' statement.
        index = <NameExpr> []
        types = <Annotation> []
        commas = <Token> []
        
        is_paren = self.current_str() == '('
        if is_paren:
            self.skip()
        
        while True:
            Annotation ann = None
            if self.is_at_type():
                ann = self.parse_type()
            v = self.parse_name_expr()
            index.append(v)
            types.append(ann)
            if self.current_str() != ',':
                commas.append(none)
                break
            commas.append(self.skip())
        
        if is_paren:
            self.expect(')')
        
        return index, types, commas
    
    IfStmt parse_if_stmt(self):
        is_error = False
        
        if_tok = self.expect('if')
        Node[] expr = []
        try:
            expr.append(self.parse_expression())
        except ParseError:
            is_error = True
        
        body = [self.parse_block()]
        
        Token[] elif_toks = []
        while self.current_str() == 'elif':
            elif_toks.append(self.expect('elif'))
            try:
                expr.append(self.parse_expression())
            except ParseError:
                is_error = True
            body.append(self.parse_block())
        
        Block else_body = None
        else_tok, else_colon, else_br = none, none, none
        if self.current_str() == 'else':
            else_tok = self.expect('else')
            else_body = self.parse_block()
        
        if not is_error:
            node = IfStmt(expr, body, else_body)
            self.set_repr(node, noderepr.IfStmtRepr(if_tok, elif_toks,
                                                    else_tok))
            return node
        else:
            return None
    
    Node parse_try_stmt(self):
        try_tok = self.expect('try')
        body = self.parse_block()
        is_error = False
        Var[] vars = []
        Node[] types = []
        Block[] handlers = []
        except_toks, name_toks, as_toks, except_brs = (<Token> [], <Token> [],
                                                       <Token> [], <Token> [])
        while self.current_str() == 'except':
            except_toks.append(self.expect('except'))
            if not isinstance(self.current(), Colon):
                try:
                    t = self.current()
                    types.append(self.parse_expression().set_line(t))
                    if self.current_str() == 'as':
                        as_toks.append(self.expect('as'))
                        vars.append(self.parse_var())
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
            handlers.append(self.parse_block())
        if not is_error:
            Block else_body = None
            else_tok = none
            if self.current_str() == 'else':
                else_tok = self.skip()
                else_body = self.parse_block()
            Block finally_body = None
            finally_tok = none
            if self.current_str() == 'finally':
                finally_tok = self.expect('finally')
                finally_body = self.parse_block()
            node = TryStmt(body, vars, types, handlers, else_body,
                           finally_body)
            self.set_repr(node, noderepr.TryStmtRepr(try_tok, except_toks,
                                                     name_toks, as_toks,
                                                     else_tok, finally_tok))
            return node
        else:
            return None
    
    Var parse_var(self):
        t = self.current()
        v = Var(self.expect_type(Name).string).set_line(t)
        self.set_repr(v, noderepr.VarRepr(t, none))
        return (Var)v
    
    WithStmt parse_with_stmt(self):
        with_tok = self.expect('with')
        Token[] as_toks = []
        Token[] commas = []
        Node[] expr = []
        Var[] name = []
        while True:
            e = self.parse_expression(precedence[','])
            Var v = None
            if self.current_str() == 'as':
                as_toks.append(self.expect('as'))
                v = self.parse_var()
            else:
                as_toks.append(none)
            expr.append(e)
            name.append(v)
            if self.current_str() != ',':
                break
            commas.append(self.expect(','))
        body = self.parse_block()
        node = WithStmt(expr, name, body)
        self.set_repr(node, noderepr.WithStmtRepr(with_tok, as_toks, commas))
        return node
    
    # Parsing expressions
    
    Node parse_expression(self, int prec=0):
        """Parse a subexpression within a specific precedence context."""
        Node expr
        t = self.current() # Remember token for setting the line number.
        
        # Parse a "value" expression or unary operator expression and store
        # that in expr.
        _x = self.current_str()
        if _x == '(':
            # Parerenthesised expression or cast.
            expr = self.parse_parentheses()
        elif _x == '[':
            expr = self.parse_list_expr()
        elif _x in ['-', '+', 'not', '~']:
            # Unary operation.
            expr = self.parse_unary_expr()
        elif _x == 'lambda':
            expr = self.parse_lambda_expr()
        elif _x == '{':
            expr = self.parse_dict_or_set_expr()
        elif _x == '<':
            expr = self.parse_literal_with_prefix_type()
        else:
            if isinstance(self.current(), Name):
                # Name expression.
                expr = self.parse_name_expr()
            elif isinstance(self.current(), IntLit):
                # Integer literal.
                expr = self.parse_int_expr()
            elif isinstance(self.current(), StrLit):
                # String literal.
                expr = self.parse_str_expr()
            elif isinstance(self.current(), BytesLit):
                # Bytes literal.
                expr = self.parse_bytes_expr()
            elif isinstance(self.current(), FloatLit):
                # Float literal.
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
            _x = self.current_str()
            if _x == '(':
                # Call expression.
                expr = self.parse_call_expr(expr)
            elif _x == '.':
                # Member access expression.
                expr = self.parse_member_expr(expr)
            elif _x == '[':
                # Indexing expression.
                expr = self.parse_index_expr(expr)
            elif _x == ',':
                # The comma operator is used to build tuples. Comma also
                # separates array items and function arguments, but in this
                # case the precedence is too low to build a tuple.
                if precedence[','] > prec:
                    expr = self.parse_tuple_expr(expr)
                else:
                    break
            elif _x == 'for':
                if precedence['<for>'] > prec:
                    # List comprehension or generator expression. Parse as
                    # generator expression; it will be converted to list
                    # comprehension if needed elsewhere.
                    expr = self.parse_generator_expr(expr)
                else:
                    break                              
            elif _x == 'if':
                # Conditional expression.
                if precedence['<if>'] > prec:
                    expr = self.parse_conditional_expr(expr)
                else:
                    break
            else:
                # Binary operation, type application or a special case.
                if isinstance(self.current(), Op):
                    op = self.current_str()
                    if op == '<' and self.is_at_type_application():
                        expr = self.parse_type_application(expr)
                    else:
                        # Binary operation.
                        op_prec = precedence[op]
                        if op == 'not':
                            # Either "not in" or an error.
                            op_prec = precedence['in']
                        if op_prec > prec:
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
    
    Node parse_parentheses(self):
        Node expr
        lparen = self.skip()
        if self.is_at_cast():
            # Cast.
            typ = self.parse_type()
            rparen = self.expect(')')
            expr = self.parse_expression(precedence['<cast>'])
            expr = CastExpr(expr, typ.typ)
            self.set_repr(expr, noderepr.CastExprRepr(lparen, rparen))
        elif self.current_str() == ')':
            # Empty tuple ().
            expr = self.parse_empty_tuple_expr(lparen)
        else:
            # Parenthesised expression.
            expr = self.parse_expression(0)
            rparen = self.expect(')')
            expr = ParenExpr(expr)
            self.set_repr(expr, noderepr.ParenExprRepr(lparen, rparen))
        return expr
    
    TupleExpr parse_empty_tuple_expr(self, any lparen):
        rparen = self.expect(')')
        node = TupleExpr([])
        self.set_repr(node, noderepr.TupleExprRepr(lparen, [], rparen))
        return node
    
    Node parse_list_expr(self):
        """Parse list literal or list comprehension."""
        Node[] items = []
        lbracket = self.expect('[')
        Token[] commas = []
        while self.current_str() != ']' and not self.eol():
            items.append(self.parse_expression(precedence['<for>']))
            if self.current_str() != ',':
                break
            commas.append(self.expect(','))
        if self.current_str() == 'for' and len(items) == 1:
            items[0] = self.parse_generator_expr(items[0])            
        rbracket = self.expect(']')
        if len(items) == 1 and isinstance(items[0], GeneratorExpr):
             list_comp = ListComprehension((GeneratorExpr)items[0])
             self.set_repr(list_comp, noderepr.ListComprehensionRepr(lbracket,
                                                                     rbracket))
             return list_comp
        else:
            expr = ListExpr(items)
            self.set_repr(expr, noderepr.ListExprRepr(lbracket, commas,
                                                      rbracket, none, none))
            return expr
    
    GeneratorExpr parse_generator_expr(self, Node left_expr):
        for_tok = self.expect('for')
        index, types, commas = self.parse_for_index_variables()
        in_tok = self.expect('in')
        right_expr = self.parse_expression_list()
        Node cond = None
        if_tok = none
        if self.current_str() == 'if':
            if_tok = self.skip()
            cond = self.parse_expression()
        gen = GeneratorExpr(left_expr, index, types, right_expr, cond)
        gen.set_line(for_tok)
        self.set_repr(gen, noderepr.GeneratorExprRepr(for_tok, commas, in_tok,
                                                      if_tok))
        return gen
    
    Node parse_expression_list(self):
        prec = precedence['<if>']
        expr = self.parse_expression(prec)
        if self.current_str() != ',':
            return expr
        else:
            t = self.current()
            return self.parse_tuple_expr(expr, prec).set_line(t)
    
    ConditionalExpr parse_conditional_expr(self, Node left_expr):
        self.expect('if')
        cond = self.parse_expression()
        self.expect('else')
        else_expr = self.parse_expression()
        return ConditionalExpr(left_expr, cond, else_expr)
    
    Node parse_dict_or_set_expr(self):
        list<tuple<Node, Node>> items = []
        lbrace = self.expect('{')
        Token[] colons = []
        Token[] commas = []
        while self.current_str() != '}' and not self.eol():
            key = self.parse_expression(precedence[','])
            if self.current_str() in [',', '}'] and items == []:
                return self.parse_set_expr(key)
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
    
    SetExpr parse_set_expr(self, Node first):
        items = [first]
        while self.current_str() != '}' and not self.eol():
            self.expect(',')
            if self.current_str() == '}':
                break
            items.append(self.parse_expression(precedence[',']))
        self.expect('}')
        return SetExpr(items)
    
    TupleExpr parse_tuple_expr(self, Node expr, int prec=precedence[',']):
        items = [expr]
        Token[] commas = []
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
    
    Node parse_literal_with_prefix_type(self):
        (types, langle,
         rangle, commas) = self.parse_type_list_in_angle_brackets()
        e = self.parse_expression(precedence['**'])
        if isinstance(e, ListExpr):
            if len(types) != 1:
                self.fail('Expected a single type before list literal', e.line)
            else:
                ((ListExpr)e).typ = types[0]
                e.repr = noderepr.ListExprRepr(e.repr.lbracket, e.repr.commas,
                                               e.repr.rbracket, langle, rangle)
        elif (isinstance(e, ParenExpr) and
                  isinstance(((ParenExpr)e).expr, TupleExpr)):
            t = (TupleExpr)((ParenExpr)e).expr
            if len(types) != len(t.items):
                self.fail('Wrong number of types for a tuple literal', e.line)
            else:
                t.types = types
        elif isinstance(e, DictExpr):
            if len(types) != 2:
                self.fail('Expected two types before dictionary literal',
                          e.line)
            else:
                ((DictExpr)e).key_type = types[0]
                ((DictExpr)e).value_type = types[1]
                e.repr = noderepr.DictExprRepr(e.repr.lbrace, e.repr.colons,
                                               e.repr.commas, e.repr.rbrace,
                                               langle, commas[0], rangle)
        else:
            self.fail(
                'Expected a list, dictionary or non-empty tuple after <...>',
                e.line)
        return e
    
    NameExpr parse_name_expr(self):
        tok = self.expect_type(Name)
        node = NameExpr(tok.string)
        self.set_repr(node, noderepr.NameExprRepr(tok))
        return node
    
    IntExpr parse_int_expr(self):
        tok = self.expect_type(IntLit)
        s = tok.string
        int v
        if len(s) > 2 and s[1] in 'xX':
            v = int(s[2:], 16)
        elif len(s) > 2 and s[1] in 'oO':
            v = int(s[2:], 8)
        else:
            v = int(s)
        node = IntExpr(v)
        self.set_repr(node, noderepr.IntExprRepr(tok))
        return node
    
    StrExpr parse_str_expr(self):
        # XXX \uxxxx literals
        tok = [self.expect_type(StrLit)]
        value = ((StrLit)tok[0]).parsed()
        while isinstance(self.current(), StrLit):
            t = (StrLit)self.skip()
            tok.append(t)
            value += t.parsed()
        node = StrExpr(value)
        self.set_repr(node, noderepr.StrExprRepr(tok))
        return node
    
    BytesExpr parse_bytes_expr(self):
        # XXX \uxxxx literals
        tok = [self.expect_type(BytesLit)]
        value = ((BytesLit)tok[0]).parsed()
        while isinstance(self.current(), BytesLit):
            t = (BytesLit)self.skip()
            tok.append(t)
            value += t.parsed()
        node = BytesExpr(value)
        self.set_repr(node, noderepr.StrExprRepr(tok))
        return node
    
    FloatExpr parse_float_expr(self):
        tok = self.expect_type(FloatLit)
        node = FloatExpr(float(tok.string))
        self.set_repr(node, noderepr.FloatExprRepr(tok))
        return node
    
    CallExpr parse_call_expr(self, any callee):
        lparen = self.expect('(')
        (args, kinds, names,
         commas, star, star2, assigns) = self.parse_arg_expr()
        rparen = self.expect(')')
        node = CallExpr(callee, args, kinds, names)
        self.set_repr(node, noderepr.CallExprRepr(lparen, commas, star, star2,
                                                  assigns, rparen))
        return node
    
    tuple<Node[], int[], str[], Token[], Token, Token, Token[][]> \
                      parse_arg_expr(self):
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
        args = <Node> []
        kinds = <int> []
        names = <str> []
        star = none
        star2 = none
        commas = <Token> []
        keywords = <Token[]> []
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
    
    Node parse_member_expr(self, any expr):
        dot = self.expect('.')
        name = self.expect_type(Name)
        Node node
        if (isinstance(expr, CallExpr) and isinstance(expr.callee, NameExpr)
                and expr.callee.name == 'super'):
            node = SuperExpr(name.string)
            self.set_repr(node,
                          noderepr.SuperExprRepr(expr.callee.repr.id,
                                                 expr.repr.lparen,
                                                 expr.repr.rparen, dot, name))
        else:
            node = MemberExpr(expr, name.string)
            self.set_repr(node, noderepr.MemberExprRepr(dot, name))
        return node
    
    IndexExpr parse_index_expr(self, any base):
        lbracket = self.expect('[')
        Node index = None
        if self.current_str() != ':':
            index = self.parse_expression(0)
        if self.current_str() == ':':
            # Slice.
            colon = self.expect(':')
            colon2 = none
            Node end_index = None
            Node stride = None
            if self.current_str() != ']' and self.current_str() != ':':
                end_index = self.parse_expression(0)
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
    
    OpExpr parse_bin_op_expr(self, Node left, int prec):
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
        elif op_str == '~':
            self.ind -= 1
            self.parse_error()
        right = self.parse_expression(prec)
        node = OpExpr(op_str, left, right)
        self.set_repr(node, noderepr.OpExprRepr(op, op2))
        return node
    
    UnaryExpr parse_unary_expr(self):
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
    
    FuncExpr parse_lambda_expr(self):
        is_error = False
        lambda_tok = self.expect('lambda')
        
        (args, init, kinds, has_inits,
         arg_names, commas, asterisk,
         assigns, arg_types) = self.parse_arg_list()

        names = <str> []
        for arg in args:
            names.append(arg.name())
        
        typ = self.build_func_annotation(None, arg_types, kinds, names,
                                         TypeVars([]), lambda_tok.line)
        
        colon = self.expect(':')
        
        expr = self.parse_expression(precedence[','])
        
        body = Block([ExpressionStmt(expr)])
        body.set_line(colon)
        
        node = FuncExpr(args, kinds, init, body, typ)
        self.set_repr(node,
                      noderepr.FuncExprRepr(
                          lambda_tok, colon,
                          noderepr.FuncArgsRepr(none, none, arg_names, commas,
                                                assigns, asterisk)))
        return node
    
    TypeApplication parse_type_application(self, any expr):
        try:
            (types, langle,
             rangle, commas) = self.parse_type_list_in_angle_brackets()
            node = TypeApplication(expr, types)
            self.set_repr(node, noderepr.TypeApplicationRepr(langle, commas,
                                                             rangle))
            return node
        except TypeParseError as e:
            self.parse_error_at(e.token)
    
    tuple<Typ[], Token, \
          Token, Token[]> parse_type_list_in_angle_brackets(self):
        types, langle, rangle, commas, i = parse_type_args(self.tok, self.ind)
        self.ind = i
        return types, langle, rangle, commas
    
    # Helper methods
    
    Token skip(self):
        self.ind += 1
        return self.tok[self.ind - 1]
    
    Token expect(self, str string):
        if self.current_str() == string:
            self.ind += 1
            return self.tok[self.ind - 1]
        else:
            self.parse_error()
    
    Token expect_indent(self):
        if isinstance(self.current(), Indent):
            return self.expect_type(Indent)
        else:
            self.fail('Expected an indented block', self.current().line)
            return none
    
    void fail(self, str msg, int line):
        self.errors.report(line, msg)
    
    Token expect_type(self, type typ):
        if isinstance(self.current(), typ):
            self.ind += 1
            return self.tok[self.ind - 1]
        else:
            self.parse_error()
    
    tuple<Token, Token> expect_colon_and_break(self):
        return self.expect_type(Colon), self.expect_type(Break)
    
    Token expect_break(self):
        return self.expect_type(Break)
    
    tuple<Token, Token> expect_end(self):
        return self.expect('end'), self.expect_type(Break)
    
    Token current(self):
        return self.tok[self.ind]
    
    str current_str(self):
        return self.current().string
    
    Token peek(self):
        return self.tok[self.ind + 1]
    
    void parse_error(self):
        self.parse_error_at(self.current())
    
    void parse_error_at(self, Token tok, bool skip=True):
        str msg
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
        
        raise ParseError()
    
    void skip_until_break(self):
        n = 0
        while (not isinstance(self.current(), Break)
               and not isinstance(self.current(), Eof)):
            self.skip()
            n += 1
        if isinstance(self.tok[self.ind - 1], Colon) and n > 1:
            self.ind -= 1
    
    void skip_until_next_line(self):
        self.skip_until_break()
        if isinstance(self.current(), Break):
            self.skip()
    
    bool eol(self):
        return isinstance(self.current(), Break) or self.eof()
    
    bool eof(self):
        return isinstance(self.current(), Eof)
    
    # Type annotation related functionality
    
    Annotation parse_type(self):
        Typ typ
        line = self.current().line
        try:
            typ, self.ind = parse_type(self.tok, self.ind)
        except TypeParseError as e:
            self.parse_error_at(e.token)
        return Annotation(typ, line)
    
    TypeVars parse_type_vars(self):
        """Note: For type variables of generic functions only."""
        TypeVars type_vars
        if self.current_str() == '<':
            try:
                type_vars, self.ind = parse_type_variables(self.tok, self.ind,
                                                           True)
            except TypeParseError as e:
                self.parse_error_at(e.token)
        else:
            type_vars = TypeVars([])
        return type_vars
    
    # Representation management
    
    void set_repr(self, Node node, any repr):
        node.repr = repr
    
    any repr(self, Node node):
        return node.repr
    
    tuple<Token[], Token[]> paren_repr(self, Node e):
        """If e is a ParenExpr, return an array of left-paren tokens
        (more that one if nested parens) and an array of corresponding
        right-paren tokens.  Otherwise, return [], [].
        """
        if isinstance(e, ParenExpr):
            lp, rp = self.paren_repr(((ParenExpr)e).expr)
            lp.insert(0, self.repr(e).lparen)
            rp.append(self.repr(e).rparen)
            return lp, rp
        else:
            return [], []

    # Helpers
    
    bool is_at_top_level(self):
        """Are we currently parsing at the top level of a file
        (i.e. not within a class or a function)?
        """
        return not self.is_function and not self.is_type
    
    bool is_at_type(self):
        i, j = self.try_scan_type(self.ind)
        if j > 0:
            self.ind = i - 1 # Token before >>; report error at >>.
            self.parse_error()
        else:
            return i >= 0 and isinstance(self.tok[i], Name)
    
    bool is_at_sig_type(self):
        i, j = self.try_scan_type(self.ind)
        if j == 0 and i >= 0 and (isinstance(self.tok[i], Name)
                                  or self.tok[i].string in ['*', '**']):
            return True
        else:
            return self.is_at_type()
    
    bool is_at_cast(self):
        i, j = self.try_scan_type(self.ind)
        if i < 0 or j > 0 or self.tok[i].string != ')':
            return False
        else:
            t = self.tok[i + 1]
            return (isinstance(t, Name) or isinstance(t, IntLit)
                    or isinstance(t, StrLit) or isinstance(t, FloatLit)
                    or t.string in ['(', '[', '{', 'lambda'])
    
    bool is_at_type_application(self):
        if self.current_str() != '<':
            return False
        i = self.ind + 1
        while True:
            int j
            i, j = self.try_scan_type(i)
            if i < 0 or j == 1:
                return False
            if self.tok[i].string != ',':
                break
            i += 1
        return self.tok[i].string == '>' and self.tok[i + 1].string == '('
    
    tuple<int, int> try_scan_type(self, int i):
        """Return the index of next token after type starting at token
        index i as the first integer. The second integer is 1 if the
        first > has been consumed from >>, 0 otherwise. Return -1 as
        the first integer if could not parse a type.
        """
        if isinstance(self.tok[i], Name):
            while (self.tok[i + 1].string == '.'
                   and isinstance(self.tok[i + 2], Name)):
                i += 2
            if self.tok[i + 1].string == '<':
                i += 2
                while True:
                    j, gt = self.try_scan_type(i)
                    if j < 0:
                        return -1, 0
                    if gt > 0:
                        # There was an unconsumed < of a << token; use that.
                        return self.try_scan_list_type(j)
                    elif self.tok[j].string == '>':
                        return self.try_scan_list_type(j + 1)
                    elif self.tok[j].string == '>>':
                        return j + 1, 1
                    elif self.tok[j].string != ',':
                        return -1, 0
                    i = j + 1
            else:
                return self.try_scan_list_type(i + 1)
        elif self.tok[i].string == 'any':
            return self.try_scan_list_type(i + 1)
        else:
            return -1, 0

    tuple<int, int> try_scan_list_type(self, int i):
        if self.tok[i].string == '[':
            while True:
                if (self.tok[i].string == '[' and
                        self.tok[i + 1].string == ']'):
                    i += 2
                    if self.tok[i].string != '[':
                        return i, 0
                else:
                    return -1, 0
        else:
            return i, 0


class ParseError(Exception): pass


str token_repr(Token tok):
    """Return a representation of a token that can be used in a parse error
    message.
    """
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
            _x = ((LexError)tok).type
            if _x == lex.NUMERIC_LITERAL_ERROR:
                return 'invalid numeric literal'
            elif _x == lex.UNTERMINATED_STRING_LITERAL:
                return 'unterminated string literal'
            elif _x == lex.INVALID_CHARACTER:
                msg = 'unrecognized character'
                if ord(tok.string) in range(33, 127):
                    msg += ' ' + tok.string
                return msg
            elif _x == lex.INVALID_UTF8_SEQUENCE:
                return 'invalid UTF-8 sequence'
            elif _x == lex.NON_ASCII_CHARACTER_IN_COMMENT:
                return 'non-ASCII character in comment'
            elif _x == lex.NON_ASCII_CHARACTER_IN_STRING:
                return 'non-ASCII character in string'
            elif _x == lex.INVALID_DEDENT:
                return 'inconsistent indentation'
        raise ValueError('Unknown token {}'.format(repr(tok)))


Node unwrap_parens(Node node):
    """If the node is a parenthesised expression, recursively find the first
    non-parenthesised subexpression and return that. Otherwise, return node.
    """
    if isinstance(node, ParenExpr):
        return unwrap_parens(((ParenExpr)node).expr)
    else:
        return node
