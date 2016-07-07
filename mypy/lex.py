"""Lexical analyzer for mypy.

Translate a string that represents a file or a compilation unit to a list of
tokens.

This module can be run as a script (lex.py FILE).
"""

import re

from mypy.util import short_type, find_python_encoding
from mypy import defaults
from typing import List, Callable, Dict, Any, Match, Pattern, Set, Union, Tuple


class Token:
    """Base class for all tokens."""

    def __init__(self, string: str, pre: str = '') -> None:
        """Initialize a token.

        Arguments:
          string: Token string in program text
          pre:    Space, comments etc. before token
        """

        self.string = string
        self.pre = pre
        self.line = 0

    def __repr__(self) -> str:
        """The representation is of form 'Keyword(  if)'."""
        t = short_type(self)
        return t + '(' + self.fix(self.pre) + self.fix(self.string) + ')'

    def rep(self) -> str:
        return self.pre + self.string

    def fix(self, s: str) -> str:
        """Replace common non-printable chars with escape sequences.

        Do not use repr() since we don't want do duplicate backslashes.
        """
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
    """Reserved word (other than keyword operators; they use Op).

    Examples: if, class, while, def.
    """


class Name(Token):
    """An alphanumeric identifier"""


class IntLit(Token):
    """Integer literal"""


class StrLit(Token):
    """String literal"""

    def parsed(self) -> str:
        """Return the parsed contents of the literal."""
        return _parse_str_literal(self.string)


class BytesLit(Token):
    """Bytes literal"""

    def parsed(self) -> str:
        """Return the parsed contents of the literal."""
        return _parse_str_literal(self.string)


class UnicodeLit(Token):
    """Unicode literal (Python 2.x)"""

    def parsed(self) -> str:
        """Return the parsed contents of the literal."""
        return _parse_str_literal(self.string)


class FloatLit(Token):
    """Float literal"""


class ComplexLit(Token):
    """Complex literal"""


class Punct(Token):
    """Punctuator (e.g. comma, '(' or '=')"""


class Colon(Token):
    pass


class EllipsisToken(Token):
    pass


class Op(Token):
    """Operator (e.g. '+' or 'in')"""


class Bom(Token):
    """Byte order mark (at the start of a file)"""


class LexError(Token):
    """Lexer error token"""

    def __init__(self, string: str, type: int, message: str = None) -> None:
        """Initialize token.

        The type argument is one of the error types below.
        """
        super().__init__(string)
        self.type = type
        self.message = message

    def __str__(self) -> str:
        if self.message:
            return 'LexError(%s)' % self.message
        else:
            return super().__str__()


# Lexer error types
NUMERIC_LITERAL_ERROR = 0
UNTERMINATED_STRING_LITERAL = 1
INVALID_CHARACTER = 2
DECODE_ERROR = 3
INVALID_BACKSLASH = 4
INVALID_DEDENT = 5


def lex(string: Union[str, bytes], first_line: int = 1,
        pyversion: Tuple[int, int] = defaults.PYTHON3_VERSION,
        is_stub_file: bool = False) -> Tuple[List[Token], Set[int]]:
    """Analyze string, and return an array of token objects and the lines to ignore.

    The last token is always Eof. The intention is to ignore any
    semantic and type check errors on the ignored lines.
    """
    l = Lexer(pyversion, is_stub_file=is_stub_file)
    l.lex(string, first_line)
    return l.tok, l.ignored_lines


# Reserved words (not including operators)
keywords_common = set([
    'as', 'assert', 'break', 'class', 'continue', 'def', 'del', 'elif',
    'else', 'except', 'finally', 'from', 'for', 'global', 'if', 'import',
    'lambda', 'pass', 'raise', 'return', 'try', 'while', 'with',
    'yield'])

# Reserved words specific for Python version 2
# TODO (jukka): 'print' should be here, but it breaks the parsing of Python 2
#               builtins, since they also define the function 'print'.
keywords2 = set([])  # type: Set[str]

# Reserved words specific for Python version 3
keywords3 = set(['nonlocal'])

# Alphabetical operators (reserved words)
alpha_operators = set(['in', 'is', 'not', 'and', 'or'])

# String literal prefixes
str_prefixes = set(['r', 'b', 'br', 'rb', 'u', 'ur', 'R', 'B', 'U'])

# List of regular expressions that match non-alphabetical operators
operators = [re.compile('[-+*/<>.%&|^~]'),
             re.compile('==|!=|<=|>=|\\*\\*|//|<<|>>|<>')]

# List of regular expressions that match punctuator tokens
punctuators = [re.compile('[=,()@`]|(->)'),
               re.compile('\\['),
               re.compile(']'),
               re.compile('([-+*/%&|^]|\\*\\*|//|<<|>>)=')]


# Map single-character string escape sequences to corresponding characters.
escape_map = {'a': '\x07',
              'b': '\x08',
              'f': '\x0c',
              'n': '\x0a',
              'r': '\x0d',
              't': '\x09',
              'v': '\x0b',
              '"': '"',
              "'": "'"}


# Matches the optional prefix of a string literal, e.g. the 'r' in r"foo".
str_prefix_re = re.compile('[rRbBuU]*')

# Matches an escape sequence in a string, e.g. \n or \x4F.
escape_re = re.compile(
    "\\\\([abfnrtv'\"]|x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|[0-7]{1,3})")


def _parse_str_literal(string: str) -> str:
    """Translate escape sequences in str literal to the corresponding chars.

    For example, \t is translated to the tab character (ascii 9).

    Return the translated contents of the literal.  Also handle raw and
    triple-quoted string literals.
    """

    prefix = str_prefix_re.match(string).group(0).lower()
    s = string[len(prefix):]
    if s.startswith("'''") or s.startswith('"""'):
        return s[3:-3]
    elif 'r' in prefix or 'R' in prefix:
        return s[1:-1].replace('\\' + s[0], s[0])
    else:
        return escape_re.sub(lambda m: escape_repl(m, prefix), s[1:-1])


def escape_repl(m: Match[str], prefix: str) -> str:
    """Translate a string escape sequence, e.g. \t -> the tab character.

    Assume that the Match object is from escape_re.
    """

    seq = m.group(1)
    if len(seq) == 1 and seq in escape_map:
        # Single-character escape sequence, e.g. \n.
        return escape_map[seq]
    elif seq.startswith('x'):
        # Hexadecimal sequence \xNN.
        return chr(int(seq[1:], 16))
    elif seq.startswith('u'):
        # Unicode sequence \uNNNN.
        if 'b' not in prefix and 'B' not in prefix:
            return chr(int(seq[1:], 16))
        else:
            return '\\' + seq
    else:
        # Octal sequence.
        ord = int(seq, 8)
        if 'b' in prefix and 'B' in prefix:
            # Make sure code is no larger than 255 for bytes literals.
            ord = ord % 256
        return chr(ord)


class Lexer:
    """Lexical analyzer."""

    i = 0      # Current string index (into s)
    s = ''     # The string being analyzed
    line = 0   # Current line number
    pre_whitespace = ''     # Whitespace and comments before the next token
    enc = ''                # Encoding

    # Generated tokens
    tok = None  # type: List[Token]

    # Table from byte character value to lexer method. E.g. entry at ord('0')
    # contains the method lex_number().
    map = None  # type: Dict[str, Callable[[], None]]

    # Indent levels of currently open blocks, in spaces.
    indents = None  # type: List[int]

    # Open ('s, ['s and {'s without matching closing bracket; used for ignoring
    # newlines within parentheses/brackets.
    open_brackets = None  # type: List[str]

    pyversion = defaults.PYTHON3_VERSION

    # Ignore errors on these lines (defined using '# type: ignore').
    ignored_lines = None  # type: Set[int]

    def __init__(self, pyversion: Tuple[int, int] = defaults.PYTHON3_VERSION,
                 is_stub_file: bool = False) -> None:
        self.map = {}
        self.tok = []
        self.indents = [0]
        self.open_brackets = []
        self.pyversion = pyversion
        self.is_stub_file = is_stub_file
        self.ignored_lines = set()
        # Fill in the map from valid character codes to relevant lexer methods.
        extra_misc = '' if pyversion[0] >= 3 else '`'
        for seq, method in [('ABCDEFGHIJKLMNOPQRSTUVWXYZ', self.lex_name),
                            ('abcdefghijklmnopqrstuvwxyz_', self.lex_name),
                            ('0123456789', self.lex_number),
                            ('.', self.lex_number_or_dot),
                            (' ' + '\t' + '\x0c', self.lex_space),
                            ('"', self.lex_str_double),
                            ("'", self.lex_str_single),
                            ('\r' + '\n', self.lex_break),
                            (';', self.lex_semicolon),
                            (':', self.lex_colon),
                            ('#', self.lex_comment),
                            ('\\', self.lex_backslash),
                            ('([{', self.lex_open_bracket),
                            (')]}', self.lex_close_bracket),
                            ('-+*/<>%&|^~=!,@' + extra_misc, self.lex_misc)]:
            for c in seq:
                self.map[c] = method
        if pyversion[0] == 2:
            self.keywords = keywords_common | keywords2
            # Decimal/hex/octal/binary literal or integer complex literal
            self.number_exp1 = re.compile('(0[xXoObB][0-9a-fA-F]+|[0-9]+)[lL]?')

        if pyversion[0] == 3:
            self.keywords = keywords_common | keywords3
            self.number_exp1 = re.compile('0[xXoObB][0-9a-fA-F]+|[0-9]+')

    def lex(self, text: Union[str, bytes], first_line: int) -> None:
        """Lexically analyze a string, storing the tokens at the tok list."""
        self.i = 0
        self.line = first_line

        if isinstance(text, bytes):
            if text.startswith(b'\xef\xbb\xbf'):
                self.enc = 'utf8'
                bom = True
            else:
                self.enc, enc_line = find_python_encoding(text, self.pyversion)
                bom = False
            try:
                decoded_text = text.decode(self.enc)
            except UnicodeDecodeError as err:
                self.report_unicode_decode_error(err, text)
                return
            except LookupError:
                self.report_unknown_encoding(enc_line)
                return
            text = decoded_text
            if bom:
                self.add_token(Bom(text[0]))
        self.s = text

        # Parse initial indent; otherwise first-line indent would not generate
        # an error.
        self.lex_indent()

        # Use some local variables as a simple optimization.
        map = self.map
        default = self.unknown_character

        # Lex the file. Repeatedly call the lexer method for the current char.
        while self.i < len(text):
            # Get the character code of the next character to lex.
            c = text[self.i]
            # Dispatch to the relevant lexer method. This will consume some
            # characters in the text, add a token to self.tok and increment
            # self.i.
            map.get(c, default)()

        # Append a break if there is no statement/block terminator at the end
        # of input.
        if len(self.tok) > 0 and (not isinstance(self.tok[-1], Break) and
                                  not isinstance(self.tok[-1], Dedent)):
            self.add_token(Break(''))

        # Attach any dangling comments/whitespace to a final Break token.
        if self.tok and isinstance(self.tok[-1], Break):
            self.tok[-1].string += self.pre_whitespace
            self.pre_whitespace = ''

        # Close remaining open blocks with Dedent tokens.
        self.lex_indent()

        self.add_token(Eof(''))

    def report_unicode_decode_error(self, exc: UnicodeDecodeError, text: bytes) -> None:
        lines = text.splitlines()
        for line in lines:
            try:
                line.decode(self.enc)
            except UnicodeDecodeError as new_exc:
                exc = new_exc
                break
            self.line += 1
        else:
            self.line = 1
        self.add_token(
            LexError('', DECODE_ERROR,
                     "%r codec can't decode byte %d in column %d" % (
                         self.enc, line[exc.start], exc.start + 1)))
        self.add_token(Break(''))
        self.add_token(Eof(''))

    def report_unknown_encoding(self, encoding_line: int) -> None:
        self.line = encoding_line
        self.add_token(
            LexError('', DECODE_ERROR,
                     "Unknown encoding %r" % self.enc))
        self.add_token(Break(''))
        self.add_token(Eof(''))

    def lex_number_or_dot(self) -> None:
        """Analyse a token starting with a dot.

        It can be the member access operator, a float literal such as '.123',
        or an ellipsis (for Python 3 and for all stub files).
        """
        if self.is_at_number():
            self.lex_number()
        elif self.is_at_ellipsis():
            # '...' is valid in Python 2 as a token but it's use is limited to indexing.
            # Example: Tuple[int, ...] is valid in Python 2.
            self.lex_ellipsis()
        else:
            self.lex_misc()

    number_exp = re.compile(r'[0-9]|\.[0-9]')

    def is_at_number(self) -> bool:
        """Is the current location at a numeric literal?"""
        return self.match(self.number_exp) != ''

    ellipsis_exp = re.compile(r'\.\.\.')

    def is_at_ellipsis(self) -> bool:
        """Is the current location at a ellipsis '...'"""
        return self.match(self.ellipsis_exp) != ''

    # Regexps used by lex_number

    # NOTE: number_exp1 depends on Python version and is defined in __init__.

    # Float literal, e.g. '1.23' or '12e+34' or '1.2j'
    number_exp2 = re.compile(
        r'[0-9]*\.[0-9]*([eE][-+]?[0-9]+)?|[0-9]+[eE][-+]?[0-9]+')

    # Complex literal, e.g. '3j' or '1.5e2J'
    number_complex = re.compile(
        r'([0-9]*\.[0-9]*([eE][-+]?[0-9]+)?|[0-9]+([eE][-+]?[0-9]+)?)[jJ]')

    # These characters must not appear after a number literal.
    name_char_exp = re.compile('[a-zA-Z0-9_]')
    octal_int = re.compile('0+[1-9]')

    def lex_number(self) -> None:
        """Analyse an int or float literal.

        Assume that the current location points to one of them.
        """
        s1 = self.match(self.number_exp1)
        s2 = self.match(self.number_exp2)
        sc = self.match(self.number_complex)

        maxlen = max(len(s1), len(s2), len(sc))
        if self.name_char_exp.match(
                self.s[self.i + maxlen:self.i + maxlen + 1]) is not None:
            # Error: alphanumeric character after number literal.
            s3 = self.match(re.compile('[0-9][0-9a-zA-Z_]*'))
            maxlen = max(maxlen, len(s3))
            self.add_token(LexError(' ' * maxlen, NUMERIC_LITERAL_ERROR))
        elif len(s1) == maxlen:
            # Integer literal.
            if self.pyversion[0] >= 3 and self.octal_int.match(s1):
                # Python 2 style octal literal such as 0377 not supported in Python 3.
                self.add_token(LexError(s1, NUMERIC_LITERAL_ERROR))
            else:
                self.add_token(IntLit(s1))
        elif len(s2) == maxlen:
            # Float literal.
            self.add_token(FloatLit(s2))
        else:
            # Complex literal.
            self.add_token(ComplexLit(sc))

    def lex_ellipsis(self) -> None:
        self.add_token(EllipsisToken('...'))

    name_exp = re.compile('[a-zA-Z_][a-zA-Z0-9_]*')

    def lex_name(self) -> None:
        """Analyse a name.

        A name can be an identifier, a keyword or an alphabetical operator.
        Also deal with prefixed string literals such as r'...'.
        """
        s = self.match(self.name_exp)
        if s in self.keywords:
            self.add_token(Keyword(s))
        elif s in alpha_operators:
            self.add_token(Op(s))
        elif s in str_prefixes and self.match(re.compile('[a-zA-Z]+[\'"]')) != '':
            self.lex_prefixed_str(s)
        else:
            self.add_token(Name(s))

    # Regexps representing components of string literals

    # Initial part of a single-quoted literal, e.g. b'foo' or b'foo\\\n
    str_exp_single = re.compile(
        r"[a-zA-Z]*'([^'\\\r\n]|\\[^\r\n])*('|\\(\n|\r\n?))")
    # Non-initial part of a multiline single-quoted literal, e.g. foo'
    str_exp_single_multi = re.compile(
        r"([^'\\\r\n]|\\[^\r\n])*('|\\(\n|\r\n?))")
    # Initial part of a single-quoted raw literal, e.g. r'foo' or r'foo\\\n
    str_exp_raw_single = re.compile(
        r"[a-zA-Z]*'([^'\r\n\\]|\\'|\\[^\n\r])*('|\\(\n|\r\n?))")
    # Non-initial part of a raw multiline single-quoted literal, e.g. foo'
    str_exp_raw_single_multi = re.compile(
        r"([^'\r\n]|'')*('|\\(\n|\r\n?))")

    # Start of a ''' literal, e.g. b'''
    str_exp_single3 = re.compile("[a-z]*'''")
    # End of a ''' literal, e.g. foo'''
    str_exp_single3end = re.compile(r"([^\n\r\\]|\\[^\n\r])*?'''")

    # The following are similar to above (but use double quotes).

    str_exp_double = re.compile(
        r'[a-z]*"([^"\\\r\n]|\\[^\r\n])*("|\\(\n|\r\n?))')
    str_exp_double_multi = re.compile(
        r'([^"\\\r\n]|\\[^\r\n])*("|\\(\n|\r\n?))')
    str_exp_raw_double = re.compile(
        r'[a-z]*"([^"\r\n\\]|\\"|\\[^\n\r])*("|\\(\n|\r\n?))')
    str_exp_raw_double_multi = re.compile(
        r'([^"\r\n]|"")*("|\\(\n|\r\n?))')

    str_exp_double3 = re.compile('[a-z]*"""')
    str_exp_double3end = re.compile(r'([^\n\r\\]|\\[^\n\r])*?"""')

    def lex_str_single(self) -> None:
        """Analyse single-quoted string literal"""
        self.lex_str(self.str_exp_single, self.str_exp_single_multi,
                     self.str_exp_single3, self.str_exp_single3end)

    def lex_str_double(self) -> None:
        """Analyse double-quoted string literal"""
        self.lex_str(self.str_exp_double, self.str_exp_double_multi,
                     self.str_exp_double3, self.str_exp_double3end)

    def lex_prefixed_str(self, prefix: str) -> None:
        """Analyse a string literal with a prefix, such as r'...'."""
        s = self.match(re.compile('[a-zA-Z]+[\'"]'))
        if s.endswith("'"):
            re1 = self.str_exp_single
            re2 = self.str_exp_single_multi
            if 'r' in prefix or 'R' in prefix:
                re1 = self.str_exp_raw_single
                re2 = self.str_exp_raw_single_multi
            self.lex_str(re1, re2, self.str_exp_single3,
                         self.str_exp_single3end, prefix)
        else:
            re1 = self.str_exp_double
            re2 = self.str_exp_double_multi
            if 'r' in prefix or 'R' in prefix:
                re1 = self.str_exp_raw_double
                re2 = self.str_exp_raw_double_multi
            self.lex_str(re1, re2, self.str_exp_double3,
                         self.str_exp_double3end, prefix)

    def lex_str(self, regex: Pattern[str], re2: Pattern[str],
                re3: Pattern[str], re3end: Pattern[str],
                prefix: str = '') -> None:
        """Analyse a string literal described by regexps.

        Assume that the current location is at the beginning of the
        literal. The arguments re3 and re3end describe the
        corresponding triple-quoted literals.
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
                    self.lex_multiline_string_literal(re2, s)
                else:
                    if 'b' in prefix or 'B' in prefix:
                        self.add_token(BytesLit(s))
                    elif 'u' in prefix or 'U' in prefix:
                        self.add_token(UnicodeLit(s))
                    else:
                        self.add_token(StrLit(s))
            else:
                # Unterminated string literal.
                s = self.match(re.compile('[^\\n\\r]*'))
                self.add_token(LexError(s, UNTERMINATED_STRING_LITERAL))

    def lex_triple_quoted_str(self, re3end: Pattern[str], prefix: str) -> None:
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
        lit = None  # type: Token
        if 'b' in prefix or 'B' in prefix:
            lit = BytesLit(ss + m.group(0))
        elif 'u' in prefix or 'U' in prefix:
            lit = UnicodeLit(ss + m.group(0))
        else:
            lit = StrLit(ss + m.group(0))
        self.add_special_token(lit, line, len(m.group(0)))

    def lex_multiline_string_literal(self, re_end: Pattern[str],
                                     prefix: str) -> None:
        """Analyze multiline single/double-quoted string literal.

        Use explicit \ for line continuation.
        """
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
        self.add_special_token(StrLit(ss), line, 0)  # TODO bytes

    comment_exp = re.compile(r'#[^\n\r]*')

    def lex_comment(self) -> None:
        """Analyze a comment."""
        s = self.match(self.comment_exp)
        self.add_pre_whitespace(s)

    backslash_exp = re.compile(r'\\(\n|\r\n?)')

    def lex_backslash(self) -> None:
        s = self.match(self.backslash_exp)
        if s != '':
            self.add_pre_whitespace(s)
            self.line += 1
        else:
            self.add_token(LexError('\\', INVALID_BACKSLASH))

    space_exp = re.compile(r'[ \t\x0c]*')
    indent_exp = re.compile(r'[ \t]*[#\n\r]?')

    def lex_space(self) -> None:
        """Analyze a run of whitespace characters (within a line, not indents).

        Only store them in self.pre_whitespace.
        """
        s = self.match(self.space_exp)
        self.add_pre_whitespace(s)

    comment_or_newline = '#' + '\n' + '\r'  # type: str

    def lex_indent(self) -> None:
        """Analyze whitespace chars at the beginning of a line (indents)."""
        s = self.match(self.indent_exp)
        while True:
            s = self.match(self.indent_exp)
            if s == '' or s[-1] not in self.comment_or_newline:
                break
            # Empty line (whitespace only or comment only).
            self.add_pre_whitespace(s[:-1])
            if s[-1] == '#':
                self.lex_comment()
            else:
                self.lex_break()
        indent = self.calc_indent(s)
        if indent == self.indents[-1]:
            # No change in indent: just whitespace.
            self.add_pre_whitespace(s)
        elif indent > self.indents[-1]:
            # An increased indent (new block).
            self.indents.append(indent)
            self.add_token(Indent(s))
        else:
            # Decreased indent (end of one or more blocks).
            pre = self.pre_whitespace
            self.pre_whitespace = ''
            while indent < self.indents[-1]:
                self.add_token(Dedent(''))
                self.indents.pop()
            self.pre_whitespace = pre
            self.add_pre_whitespace(s)
            if indent != self.indents[-1]:
                # Error: indent level does not match a previous indent level.
                self.add_token(LexError('', INVALID_DEDENT))

    def calc_indent(self, s: str) -> int:
        indent = 0
        for ch in s:
            if ch == ' ':
                indent += 1
            else:
                # Tab: 8 spaces (rounded to a multiple of 8).
                indent += 8 - indent % 8
        return indent

    break_exp = re.compile(r'\r\n|\r|\n|;')

    def lex_break(self) -> None:
        """Analyse a line break."""
        s = self.match(self.break_exp)
        last_tok = self.tok[-1] if self.tok else None
        if isinstance(last_tok, Break):
            was_semicolon = last_tok.string == ';'
            last_tok.string += self.pre_whitespace + s
            self.i += len(s)
            self.line += 1
            self.pre_whitespace = ''
            if was_semicolon:
                self.lex_indent()
        elif self.ignore_break():
            self.add_pre_whitespace(s)
            self.line += 1
        else:
            self.add_token(Break(s))
            self.line += 1
            self.lex_indent()

    def lex_semicolon(self) -> None:
        self.add_token(Break(';'))

    def lex_colon(self) -> None:
        self.add_token(Colon(':'))

    open_bracket_exp = re.compile('[[({]')

    def lex_open_bracket(self) -> None:
        s = self.match(self.open_bracket_exp)
        self.open_brackets.append(s)
        self.add_token(Punct(s))

    close_bracket_exp = re.compile('[])}]')

    open_bracket = {')': '(', ']': '[', '}': '{'}

    def lex_close_bracket(self) -> None:
        s = self.match(self.close_bracket_exp)
        if (self.open_brackets != []
                and self.open_bracket[s] == self.open_brackets[-1]):
            self.open_brackets.pop()
        self.add_token(Punct(s))

    def lex_misc(self) -> None:
        """Analyze a non-alphabetical operator or a punctuator."""
        s = ''
        t = None  # type: Any
        for re_list, type in [(operators, Op), (punctuators, Punct)]:
            for regexp in re_list:
                s2 = self.match(regexp)
                if len(s2) > len(s):
                    t = type
                    s = s2
        if s == '':
            # Could not match any token; report an invalid character. This is
            # reached at least if the current character is '!' not followed by
            # '='.
            self.add_token(LexError(self.s[self.i], INVALID_CHARACTER))
        else:
            if s == '<>':
                if self.pyversion[0] == 2:
                    s = '!='
                else:
                    self.add_token(Op('<'))
                    s = '>'
            self.add_token(t(s))

    def unknown_character(self) -> None:
        """Report an unknown character as a lexical analysis error."""
        self.add_token(LexError(self.s[self.i], INVALID_CHARACTER))

    # Utility methods

    def match(self, pattern: Pattern[str]) -> str:
        """Try to match a regular expression at current location.

        If the argument regexp is matched at the current location,
        return the matched string; otherwise return the empty string.
        """
        m = pattern.match(self.s, self.i)
        if m is not None:
            return m.group(0)
        else:
            return ''

    def add_pre_whitespace(self, s: str) -> None:
        """Record whitespace and comments before the next token.

        The accumulated whitespace/comments will be stored in the next token
        and then it will be cleared.

        This is needed for pretty-printing the original source code while
        preserving comments, indentation, whitespace etc.
        """
        self.pre_whitespace += s
        self.i += len(s)

    type_ignore_exp = re.compile(r'[ \t]*#[ \t]*type:[ \t]*ignore\b')

    def add_token(self, tok: Token) -> None:
        """Store a token.

        Update its line number and record preceding whitespace
        characters and comments.
        """
        if (tok.string == '' and not isinstance(tok, Eof)
                and not isinstance(tok, Break)
                and not isinstance(tok, LexError)
                and not isinstance(tok, Dedent)):
            raise ValueError('Empty token')
        tok.pre = self.pre_whitespace
        if self.type_ignore_exp.match(tok.pre):
            delta = 0
            if '\n' in tok.pre or '\r' in tok.pre:
                delta += 1
            self.ignored_lines.add(self.line - delta)
        tok.line = self.line
        self.tok.append(tok)
        self.i += len(tok.string)
        self.pre_whitespace = ''

    def add_special_token(self, tok: Token, line: int, skip: int) -> None:
        """Like add_token, but caller sets the number of chars to skip."""
        if (tok.string == '' and not isinstance(tok, Eof)
                and not isinstance(tok, Break)
                and not isinstance(tok, LexError)
                and not isinstance(tok, Dedent)):
            raise ValueError('Empty token')
        tok.pre = self.pre_whitespace
        tok.line = line
        self.tok.append(tok)
        self.i += skip
        self.pre_whitespace = ''

    def ignore_break(self) -> bool:
        """If the next token is a break, can we ignore it?"""
        if len(self.open_brackets) > 0 or len(self.tok) == 0:
            # Ignore break after open ( [ or { or at the beginning of file.
            return True
        else:
            # Ignore break after another break or dedent.
            t = self.tok[-1]
            return isinstance(t, Break) or isinstance(t, Dedent)


if __name__ == '__main__':
    # Lexically analyze a file and dump the tokens to stdout.
    import sys
    if len(sys.argv) != 2:
        print('Usage: lex.py FILE', file=sys.stderr)
        sys.exit(2)
    fnam = sys.argv[1]
    s = open(fnam, 'rb').read()
    for t in lex(s):
        print(t)
