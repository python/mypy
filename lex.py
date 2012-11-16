import re
from re import Match, Pattern

from util import short_type


class Token:
    """Base class for all tokens"""
    str pre = '' # Space, comments etc. before token
    str string   # Token string
    int line     # Token line number
    
    void __init__(self, str string, str pre=''):
        self.string = string
        self.pre = pre
    
    str __repr__(self):
        t = short_type(self)
        return t + '(' + self.fix(self.pre) + self.fix(self.string) + ')'
    
    str rep(self):
        return self.pre + self.string
    
    str fix(self, str s):
        return s.replace('\n', '\\n').replace('\t', '\\t').replace('\r', '\\r')


# Token classes

class Break(Token):
    """Statement break (line break or semicolon)"""

class Indent(Token):
    """Increase block indent level."""

class Dedent(Token):
    """Decrease block indent level."""

class Eof(Token):
    """End of file"""

class Keyword(Token):
    """Reserved word (other than keyword operators; they use Op)"""

class Name(Token):
    """An alphanumeric identifier"""

class IntLit(Token):
    """Integer literal"""

str_prefix_re = re.compile('[rRbB]*')
escape_re = re.compile(
    "\\\\([abfnrtv'\"]|x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|[0-7]{1,3})")

escape_map = {'a': '\u0007',
              'b': '\u0008',
              'f': '\u000c',
              'n': '\u000a',
              'r': '\u000d',
              't': '\u0009',
              'v': '\u000b',
              '"': '"',
              "'": "'"}

class StrLit(Token):
    """String literal"""
    str parsed(self):
        """Return the parsed contents of the literal."""
        prefix = str_prefix_re.match(self.string).group(0).lower()
        s = self.string[len(prefix):]
        if s.startswith("'''") or s.startswith('"""'):
            return s[3:-3]
        elif 'r' in prefix:
            return s[1:-1].replace('\\' + s[0], s[0])
        else:
            return self.replace_escapes(s[1:-1], prefix)
    
    str replace_escapes(self, str s, str prefix):
        return escape_re.sub(lambda m: escape_repl(m, prefix), s)

str escape_repl(Match m, str prefix):
    seq = m.group(1)
    if len(seq) == 1 and seq in escape_map:
        return escape_map[seq]
    elif seq.startswith('x'):
        return chr(int(seq[1:], 16))
    elif seq.startswith('u'):
        if 'b' not in prefix:
            return chr(int(seq[1:], 16))
        else:
            return '\\' + seq
    else:
        # Octal sequence.
        ord = int(seq, 8)
        if 'b' in prefix:
            # Make sure code is no larger than 255 for bytes literals.
            ord = ord % 256
        return chr(ord)

class FloatLit(Token):
    """Float literal"""
    pass

class Punct(Token):
    """Punctuator (e.g. comma or paranthesis)"""
    pass

class Colon(Token):
    pass

class Op(Token):
    """Operator (e.g. '+' or 'and')"""
    pass

class Bom(Token):
    """Byte order mark (at the start of a file)"""
    pass

class LexError(Token):
    """Lexer error token"""
    int type # One of the error types below
    
    void __init__(self, str string, int type):
        super().__init__(string)
        self.type = type


# Lexer error types
NUMERIC_LITERAL_ERROR = 0
UNTERMINATED_STRING_LITERAL = 1
INVALID_CHARACTER = 2
NON_ASCII_CHARACTER_IN_COMMENT = 3
NON_ASCII_CHARACTER_IN_STRING = 4
INVALID_UTF8_SEQUENCE = 5
INVALID_BACKSLASH = 6
INVALID_DEDENT = 7

# Encoding contexts
STR_CONTEXT = 1
COMMENT_CONTEXT = 2


list<Token> lex(str s):
    """Analyze s and return an array of token objects, the last of
    which is always Eof.
    """
    l = Lexer()
    l.lex(s)
    return l.tok


# Reserved words (not including operators)
set<str> keywords = set([
    'any', 'as', 'assert', 'break', 'class', 'continue', 'def', 'del', 'elif',
    'else', 'except', 'finally', 'from', 'for', 'global', 'if', 'import',
    'interface', 'lambda', 'pass', 'raise', 'return', 'try', 'while', 'with',
    'yield'])

# Alphabetical operators (reserved words)
set<str> alpha_operators = set(['in', 'is', 'not', 'and', 'or'])

# String literal prefixes
set<str> str_prefixes = set(['r', 'b', 'br'])  

# List of regular expressions that match non-alphabetical operators
list<Pattern> operators = [re.compile('[-+*/<>.%&|^~]'),
                           re.compile('==|!=|<=|>=|\\*\\*|//|<<|>>')]

# List of regular expressions that match punctuator tokens
list<Pattern> punctuators = [re.compile('[=,()@]'),
                             re.compile('\\['),
                             re.compile(']'),
                             re.compile('([-+*/%&|^]|\\*\\*|//|<<|>>)=')]


# Source file encodings
DEFAULT_ENCODING = 0
ASCII_ENCODING = 1
LATIN1_ENCODING = 2
UTF8_ENCODING = 3


class Lexer:
    """Lexical analyzer"""
    int i
    str s
    int line
    str pre = ''
    int enc = DEFAULT_ENCODING
    
    list<Token> tok
    list<func<void>> map
    
    list<int> indents
    # Open ('s, ['s and {'s without matching closing bracket.
    list<str> open_brackets
    
    void __init__(self):
        self.map = [self.unknown_character] * 256
        self.tok = []
        self.indents = [0]
        self.open_brackets = []
        for seq, method in [('ABCDEFGHIJKLMNOPQRSTUVWXYZ', self.lex_name),
                            ('abcdefghijklmnopqrstuvwxyz_', self.lex_name),
                            ('0123456789', self.lex_number),
                            ('.', self.lex_number_or_dot),
                            (' ' + '\t' + '\u000c', self.lex_space),
                            ('"', self.lex_str_double),
                            ("'", self.lex_str_single),
                            ('\r' + '\n', self.lex_break),
                            (';', self.lex_semicolon),
                            (':', self.lex_colon),
                            ('#', self.lex_comment),
                            ('\\', self.lex_backslash),
                            ('([{', self.lex_open_bracket),
                            (')]}', self.lex_close_bracket),
                            ('-+*/<>%&|^~=!,@', self.lex_misc)]:
            for c in seq:
                self.map[ord(c)] = method
    
    void lex(self, str s):
        """Lexically analyze a string, storing the tokens at the tok array."""
        self.s = s
        self.i = 0
        self.line = 1    
        
        if s.startswith('\u00ef\u00bb\u00bf'):
            self.add_token(Bom(s[0:3]))
        self.lex_indent()
        
        map = self.map
        while self.i < len(s):
            c = ord(s[self.i])
            map[c]()
        
        # Append a break if there is no statement/block terminator at the end
        # of input.
        if len(self.tok) > 0 and (not isinstance(self.tok[-1], Break) and
                                  not isinstance(self.tok[-1], Dedent)):
            self.add_token(Break(''))
        self.lex_indent()
        self.add_token(Eof(''))
    
    void lex_number_or_dot(self):
        """Analyse a token starting with a dot (either the member
        access operator or a Float literal).
        """
        if self.is_at_number():
            self.lex_number()
        else:
            self.lex_misc()
    
    Pattern number_exp = re.compile('[0-9]|\\.[0-9]')  # Used by isAtNumber
    
    bool is_at_number(self):
        """Is the current location at a numeric literal?"""
        return self.match(self.number_exp) != ''
    
    # Regexps used by lexNumber
    Pattern number_exp1 = re.compile('0[xXoO][0-9a-fA-F]+|[0-9]+')
    Pattern number_exp2 = re.compile(
        '[0-9]*\\.[0-9]*([eE][-+]?[0-9]+)?|[0-9]+[eE][-+]?[0-9]+')
    Pattern name_char_exp = re.compile('[a-zA-Z0-9_]')
    
    void lex_number(self):
        """Analyse an Int or Float literal. Assume that the current
        location points to one of them.
        """
        s1 = self.match(self.number_exp1)
        s2 = self.match(self.number_exp2)
        
        maxlen = max(len(s1), len(s2))
        if self.name_char_exp.match(
                    self.s[self.i + maxlen:self.i + maxlen + 1]) is not None:
            s3 = self.match(re.compile('[0-9][0-9a-zA-Z_]*'))
            maxlen = max(maxlen, len(s3))
            self.add_token(LexError(' ' * maxlen, NUMERIC_LITERAL_ERROR))
        elif len(s1) > len(s2):
            # Integer literal.
            self.add_token(IntLit(s1))
        else:
            # Float literal.
            self.add_token(FloatLit(s2))
    
    Pattern name_exp = re.compile('[a-zA-Z_][a-zA-Z0-9_]*') # Used by lexName
    
    void lex_name(self):
        """Analyse a name (an identifier, a keyword or an alphabetical
        operator).  This also deals with prefixed string literals such
        as r'...'.
        """
        s = self.match(self.name_exp)
        if s in keywords:
            self.add_token(Keyword(s))
        elif s in alpha_operators:
            self.add_token(Op(s))
        elif s in str_prefixes and self.match(re.compile('[a-z]+[\'"]')) != '':
            self.lex_prefixed_str(s)
        else:
            self.add_token(Name(s))
    
    # Regexps representing components of string literals
    
    Pattern str_exp_single = re.compile(
        "[a-z]*'([^'\\\\\\r\\n]|\\\\[^\\r\\n])*('|\\\\(\\n|\\r\\n?))")
    Pattern str_exp_single_multi = re.compile(
        "([^'\\\\\\r\\n]|\\\\[^\\r\\n])*('|\\\\(\\n|\\r\\n?))")
    Pattern str_exp_raw_single = re.compile(
        "[a-z]*'([^'\\r\\n\\\\]|\\\\'|\\\\[^\\n\\r])*('|\\\\(\\n|\\r\\n?))")
    Pattern str_exp_raw_single_multi = re.compile(
        "([^'\\r\\n]|'')*('|\\\\(\\n|\\r\\n?))")
    
    Pattern str_exp_single3 = re.compile("[a-z]*'''")
    Pattern str_exp_single3end = re.compile("[^\\n\\r]*?'''")
    
    Pattern str_exp_double = re.compile(
        '[a-z]*"([^"\\\\\\r\\n]|\\\\[^\\r\\n])*("|\\\\(\\n|\\r\\n?))')
    Pattern str_exp_double_multi = re.compile(
        '([^"\\\\\\r\\n]|\\\\[^\\r\\n])*("|\\\\(\\n|\\r\\n?))')  
    Pattern str_exp_raw_double = re.compile(
        '[a-z]*"([^"\\r\\n\\\\]|\\\\"|\\\\[^\\n\\r])*("|\\\\(\\n|\\r\\n?))')
    Pattern str_exp_raw_double_multi = re.compile(
        '([^"\\r\\n]|"")*("|\\\\(\\n|\\r\\n?))')
    
    Pattern str_exp_double3 = re.compile('[a-z]*"""')
    Pattern str_exp_double3end = re.compile('[^\\n\\r]*?"""')
    
    void lex_str_single(self):
        """Analyse single-quoted string literal"""
        self.lex_str(self.str_exp_single, self.str_exp_single_multi,
                     self.str_exp_single3, self.str_exp_single3end)
    
    void lex_str_double(self):
        """Analyse double-quoted string literal"""
        self.lex_str(self.str_exp_double, self.str_exp_double_multi,
                     self.str_exp_double3, self.str_exp_double3end)
    
    void lex_prefixed_str(self, str prefix):
        """Analyse a string literal with a prefix, such as r'...'."""
        s = self.match(re.compile('[a-z]+[\'"]'))
        if s.endswith("'"):
            re1 = self.str_exp_single
            re2 = self.str_exp_single_multi
            if 'r' in prefix:
                re1 = self.str_exp_raw_single
                re2 = self.str_exp_raw_single_multi
            self.lex_str(re1, re2, self.str_exp_single3,
                         self.str_exp_single3end, prefix)
        else:
            re1 = self.str_exp_double
            re2 = self.str_exp_double_multi
            if 'r' in prefix:
                re1 = self.str_exp_raw_double
                re2 = self.str_exp_raw_double_multi
            self.lex_str(re1, re2, self.str_exp_double3,
                         self.str_exp_double3end, prefix)
    
    void lex_str(self, Pattern regex, Pattern re2, Pattern re3, Pattern re3end,
                 str prefix=''):
        """Analyse a string literal described by regexps. Assume that
        the current location is at the beginning of the literal. The
        arguments re3 and re3end describe the corresponding
        triple-quoted literals.
        """
        s3 = self.match(re3)
        if s3 != '':
            # Triple-quoted string literal.
            self.lex_triple_quoted_str(re3end, prefix)
        else:
            # Single or double quoted string literal.
            s = self.match(regex)
            if s != '':
                if s.endswith('\n') or s.endswith('\r'):
                    self.lex_multiline_literal(re2, s)
                else:
                    self.verify_encoding(s, STR_CONTEXT)
                    self.add_token(StrLit(s))
            else:
                # Unterminated string literal.
                s = self.match(re.compile('[^\\n\\r]*'))
                self.add_token(LexError(s, UNTERMINATED_STRING_LITERAL))
    
    void lex_triple_quoted_str(self, Pattern re3end, str prefix):
        line = self.line
        ss = self.s[self.i:self.i + len(prefix) + 3]
        self.i += len(prefix) + 3
        while True:
            m = re3end.match(self.s, self.i)
            if m is not None:
                break
            m = re.match('[^\\n\\r]*(\\n|\\r\\n?)', self.s[self.i:])
            if m is None:
                self.add_special_token(
                    LexError(ss, UNTERMINATED_STRING_LITERAL), line, 0)
                return 
            s = m.group(0)
            ss += s
            self.line += 1
            self.i += len(s)
        self.add_special_token(StrLit(ss + m.group(0)), line, len(m.group(0)))
    
    def lex_multiline_literal(self, re_end, prefix):
        line = self.line
        self.i += len(prefix)
        ss = prefix
        while True:
            m = self.match(re_end)
            if m == '':
                self.add_special_token(
                    LexError(ss, UNTERMINATED_STRING_LITERAL), line, 0)
                return 
            ss += m
            self.line += 1
            self.i += len(m)        
            if not m.endswith('\n') and not m.endswith('\r'): break
        self.add_special_token(StrLit(ss), line, 0)
    
    Pattern comment_exp = re.compile('#[^\\n\\r]*')
    
    void lex_comment(self):
        """Analyse a comment."""
        s = self.match(self.comment_exp)
        self.verify_encoding(s, COMMENT_CONTEXT)
        self.add_pre(s)
    
    Pattern backslash_exp = re.compile('\\\\(\\n|\\r\\n?)')
    
    void lex_backslash(self):
        s = self.match(self.backslash_exp)
        if s != '':
            self.add_pre(s)
            self.line += 1
        else:
            self.add_token(LexError('\\', INVALID_BACKSLASH))
    
    Pattern space_exp = re.compile('[ \\t\u000c]*')
    Pattern indent_exp = re.compile('[ \\t]*[#\\n\\r]?')
    
    void lex_space(self):
        """Analyse a run of whitespace characters."""
        s = self.match(self.space_exp)
        self.add_pre(s)
    
    str comment_or_newline = '#' + '\n' + '\r'
    
    void lex_indent(self):
        s = self.match(self.indent_exp)
        if s != '' and s[-1] in self.comment_or_newline:
            self.add_pre(s[:-1])
            if s[-1] == '#':
                self.lex_comment()
            else:
                self.lex_break()
            self.lex_indent()
            return 
        indent = self.calc_indent(s)
        if indent == self.indents[-1]:
            self.add_pre(s)
        elif indent > self.indents[-1]:
            self.indents.append(indent)
            self.add_token(Indent(s))
        else:
            pre = self.pre
            self.pre = ''
            while indent < self.indents[-1]:
                self.add_token(Dedent(''))
                self.indents.pop()
            self.pre = pre
            self.add_pre(s)
            if indent != self.indents[-1]:
                self.add_token(LexError('', INVALID_DEDENT))
    
    int calc_indent(self, str s):
        indent = 0
        for ch in s:
            if ch == ' ':
                indent += 1
            else:
                indent += 8 - indent % 8
        return indent
    
    Pattern break_exp = re.compile('\\r\\n|\\r|\\n|;')
    
    void lex_break(self):
        """Analyse a line break."""
        s = self.match(self.break_exp)
        if self.ignore_break():
            self.add_pre(s)
            self.line += 1
        else:
            self.add_token(Break(s))
            self.line += 1
            self.lex_indent()
    
    void lex_semicolon(self):
        self.add_token(Break(';'))
    
    void lex_colon(self):
        self.add_token(Colon(':'))
    
    Pattern open_bracket_exp = re.compile('[[({]')
    
    void lex_open_bracket(self):
        s = self.match(self.open_bracket_exp)
        self.open_brackets.append(s)
        self.add_token(Punct(s))
    
    Pattern close_bracket_exp = re.compile('[])}]')
    
    dict<str, str> open_bracket = {')': '(', ']': '[', '}': '{'}
    
    void lex_close_bracket(self):
        s = self.match(self.close_bracket_exp)
        if (self.open_brackets != []
                and self.open_bracket[s] == self.open_brackets[-1]):
            self.open_brackets.pop()
        self.add_token(Punct(s))
    
    void lex_misc(self):
        """Analyse a non-alphabetical operator or a punctuator."""
        s = ''
        any t = None
        for re_list, type in [(operators, Op), (punctuators, Punct)]:
            for re in re_list:
                s2 = self.match(re)
                if len(s2) > len(s):
                    t = type
                    s = s2
        if s == '':
            # Could not match any token; report an invalid character. This is
            # reached at least if the current character is '!' not followed by
            # '='.
            self.add_token(LexError(self.s[self.i], INVALID_CHARACTER))
        else:
            self.add_token(t(s))
    
    void unknown_character(self):
        """Report an unknown character as a lexical analysis error."""
        self.add_token(LexError(self.s[self.i], INVALID_CHARACTER))
    
    
    # Utility methods
    
    
    str match(self, Pattern pattern):
        """If the argument regexp is matched at the current location,
        return the matched string; otherwise return the empty string.
        """
        m = pattern.match(self.s, self.i)
        if m is not None:
            return m.group(0)
        else:
            return ''
    
    void add_pre(self, str s):
        """Record string representing whitespace or comment after the previous.
        The accumulated whitespace/comments will be associated with the next
        token and then it will be cleared.
        """
        self.pre += s
        self.i += len(s)
    
    void add_token(self, Token tok):
        """Store a token. Update its line number and record preceding
        whitespace characters and comments.
        """
        if (tok.string == '' and not isinstance(tok, Eof)
                and not isinstance(tok, Break)
                and not isinstance(tok, LexError)
                and not isinstance(tok, Dedent)):
            raise ValueError('Empty token')
        tok.pre = self.pre
        tok.line = self.line
        self.tok.append(tok)
        self.i += len(tok.string)
        self.pre = ''
    
    void add_special_token(self, Token tok, int line, int skip):
        if (tok.string == '' and not isinstance(tok, Eof)
                and not isinstance(tok, Break)
                and not isinstance(tok, LexError)
                and not isinstance(tok, Dedent)):
            raise ValueError('Empty token')
        tok.pre = self.pre
        tok.line = line
        self.tok.append(tok)
        self.i += skip
        self.pre = ''
    
    bool ignore_break(self):
        """If the next token is a break, can we ignore it?"""
        if len(self.open_brackets) > 0 or len(self.tok) == 0:
            return True
        else:
            t = self.tok[-1]
            return isinstance(t, Break) or isinstance(t, Dedent)
    
    void verify_encoding(self, str string, int context):
        """Verify that a token (represented by a string) is encoded correctly
        according to the file encoding.
        """
        str codec = None
        if self.enc == ASCII_ENCODING:
            codec = 'ascii'
        elif self.enc in [UTF8_ENCODING, DEFAULT_ENCODING]:
            codec = 'utf8'
        if codec is not None:
            try:
                pass # FIX string.decode(codec)
            except UnicodeDecodeError:
                type = INVALID_UTF8_SEQUENCE
                if self.enc == ASCII_ENCODING:
                    if context == STR_CONTEXT:
                        type = NON_ASCII_CHARACTER_IN_STRING
                    else:
                        type = NON_ASCII_CHARACTER_IN_COMMENT
                self.add_token(LexError('', type))
