"""Lexical analyzer test cases"""

import typing

from mypy.myunit import Suite, assert_equal
from mypy.lex import lex


class LexerSuite(Suite):
    def test_empty(self):
        self.assert_lex('', 'Eof()')

    def test_keywords(self):
        self.assert_lex(
            'if else elif def return pass',
            'Keyword(if) Keyword( else) Keyword( elif) Keyword( def) '
            'Keyword( return) Keyword( pass) Break() Eof()')

        self.assert_lex(
            'from import as class global',
            'Keyword(from) Keyword( import) Keyword( as) Keyword( class) '
            'Keyword( global) ...')

    def test_identifiers(self):
        self.assert_lex(
            'i x FooBar FOO_BAR __x var',
            'Name(i) Name( x) Name( FooBar) Name( FOO_BAR) Name( __x) '
            'Name( var) Break() Eof()')

        self.assert_lex(
            'any interface void',
            'Name(any) Name( interface) Name( void) Break() Eof()')

    def test_int_literals(self):
        self.assert_lex(
            '0 00 1 0987654321 10002000300040005000600070008000',
            'IntLit(0) IntLit( 00) IntLit( 1) LexError( 0987654321) '
            'IntLit( 10002000300040005000600070008000) Break() Eof()')

    def test_hex_int_literals(self):
        self.assert_lex('0x0 0xabcedf0189 0xAFe 0X2',
                        'IntLit(0x0) IntLit( 0xabcedf0189) IntLit( 0xAFe) '
                        'IntLit( 0X2) ...')

    def test_oct_int_literals(self):
        self.assert_lex('0o0 0o127 0O1',
                        'IntLit(0o0) IntLit( 0o127) IntLit( 0O1) ...')

    def test_bin_int_literals(self):
        self.assert_lex('0b0 0b110 0B1',
                        'IntLit(0b0) IntLit( 0b110) IntLit( 0B1) ...')

    def test_float_literals(self):
        self.assert_lex('1.2 .1 1.',
                        'FloatLit(1.2) FloatLit( .1) FloatLit( 1.) ...')

        self.assert_lex(
            '1e2 1.2e+3 1.3e-12',
            'FloatLit(1e2) FloatLit( 1.2e+3) FloatLit( 1.3e-12) ...')

        self.assert_lex('1.e2', 'FloatLit(1.e2) ...')

    def test_comments(self):
        self.assert_lex('# foo "" bar' + '\n' + 'x #x',
                        'Name(# foo "" bar\\nx) Break( #x) Eof()')

    def test_empty_lines(self):
        self.assert_lex(r'\n1', r'IntLit(\n1) ...')
        self.assert_lex(r'\n\n1', r'IntLit(\n\n1) ...')
        self.assert_lex(r'1\n\n2', r'IntLit(1) Break(\n\n) IntLit(2) ...')

    def test_line_breaks(self):
        self.assert_lex('1\\r2', 'IntLit(1) Break(\\r) IntLit(2) ...')
        self.assert_lex('1\\r\\n2', 'IntLit(1) Break(\\r\\n) IntLit(2) ...')

    def test_operators(self):
        self.assert_lex('- + < > == != <= >= .',
                        'Op(-) Op( +) Op( <) Op( >) Op( ==) Op( !=) Op( <=) '
                        'Op( >=) Op( .) ...')

        self.assert_lex('* / % // **',
                        'Op(*) Op( /) Op( %) Op( //) Op( **) ...')

        self.assert_lex('& | ^ ~ << >>',
                        'Op(&) Op( |) Op( ^) Op( ~) Op( <<) Op( >>) ...')

        self.assert_lex('in is and or not',
                        'Op(in) Op( is) Op( and) Op( or) Op( not) ...')

    def test_punctuators(self):
        self.assert_lex(': = ,', 'Colon(:) Punct( =) Punct( ,) ...')

        self.assert_lex(
            '+= -= *= %= //=',
            'Punct(+=) Punct( -=) Punct( *=) Punct( %=) Punct( //=) ...')
        self.assert_lex('**=', 'Punct(**=) ...')
        self.assert_lex(
            '&= |= ^= <<= >>=',
            'Punct(&=) Punct( |=) Punct( ^=) Punct( <<=) Punct( >>=) ...')

    def test_basic_indentation(self):
        self.assert_lex(
            'y' + '\n' + '  x',
            'Name(y) Break(\\n) Indent(  ) Name(x) Break() Dedent() Eof()')

        self.assert_lex(
            'y' + '\n' + '  x' + '\n' + 'z',
            'Name(y) Break(\\n) Indent(  ) Name(x) Break(\\n) Dedent() '
            'Name(z) Break() Eof()')

    def test_multiple_indent_levels(self):
        self.assert_lex('y' + '\n' +
                        '  x' + '\n' +
                        '  y' + '\n' +
                        '    z',
                        'Name(y) Break(\\n) ' +
                        'Indent(  ) Name(x) Break(\\n) ' +
                        'Name(  y) Break(\\n) ' +
                        'Indent(    ) Name(z) Break() ' +
                        'Dedent() Dedent() Eof()')

        self.assert_lex('y' + '\n' +
                        '  x' + '\n' +
                        '    z' + '\n' +
                        '  y',
                        'Name(y) Break(\\n) ' +
                        'Indent(  ) Name(x) Break(\\n) ' +
                        'Indent(    ) Name(z) Break(\\n) ' +
                        'Dedent() Name(  y) Break() ' +
                        'Dedent() Eof()')

    def test_tab_indent(self):
        self.assert_lex('y' + '\n' +
                        '\t' + 'x' + '\n' +
                        '        y' + '\n' +
                        ' ' + '\t' + 'z',
                        'Name(y) Break(\\n) ' +
                        'Indent(\\t) Name(x) Break(\\n) ' +
                        'Name(        y) Break(\\n) ' +
                        'Name( \\tz) Break() ' +
                        'Dedent() Eof()')

    def test_comment_after_dedent(self):
        self.assert_lex('y\n'
                        '  x\n'
                        '# Foo\n'
                        'z',
                        r'Name(y) Break(\n) Indent(  ) Name(x) '
                        r'Break(\n# Foo\n) '
                        r'Dedent() Name(z) Break() Eof()')

    def test_parens(self):
        self.assert_lex('( x )', 'Punct(() Name( x) Punct( )) Break() Eof()')
        self.assert_lex(
            '( x' + '\n' + '  y )',
            'Punct(() Name( x) Name(\\n  y) Punct( )) Break() Eof()')

        self.assert_lex('()' + '\n' + ' y',
                        'Punct(() Punct()) Break(\\n) Indent( ) Name(y) '
                        'Break() Dedent() Eof()')

        # [ ... ] and { ... }.
        self.assert_lex(
            '[ x' + '\n' + '  y ]',
            'Punct([) Name( x) Name(\\n  y) Punct( ]) Break() Eof()')
        self.assert_lex(
            '{ x' + '\n' + '  y }',
            'Punct({) Name( x) Name(\\n  y) Punct( }) Break() Eof()')

        # Nested brackets.
        self.assert_lex(
            '({}' + '\n' + ' y)',
            'Punct(() Punct({) Punct(}) Name(\\n y) Punct()) Break() Eof()')

    def test_brackets_and_line_breaks(self):
        # This used to fail.
        self.assert_lex('{}' + '\n' + '1',
                        'Punct({) Punct(}) Break(\\n) IntLit(1) Break() Eof()')

    def test_str_literals(self):
        self.assert_lex("'' 'foo_bar'",
                        "StrLit('') StrLit( 'foo_bar') Break() Eof()")
        self.assert_lex('"" "foo_bar"',
                        'StrLit("") StrLit( "foo_bar") Break() Eof()')

        self.assert_lex('"\\"" 1', 'StrLit("\\"") IntLit( 1) Break() Eof()')
        self.assert_lex("'\\'' 1", "StrLit('\\'') IntLit( 1) Break() Eof()")

        self.assert_lex('"\\\\" 1', 'StrLit("\\\\") IntLit( 1) Break() Eof()')
        self.assert_lex("'\\\\' 1", "StrLit('\\\\') IntLit( 1) Break() Eof()")

    def test_triple_quoted_string_literals(self):
        # Single-line

        self.assert_lex("''''''", "StrLit('''''') ...")
        self.assert_lex("1 '''x''y'''1",
                        "IntLit(1) StrLit( '''x''y''') IntLit(1) ...")

        self.assert_lex('""""""', 'StrLit("""""") ...')
        self.assert_lex('"""x""y"""', 'StrLit("""x""y""") ...')

        # Multiple-line

        self.assert_lex("'''" + '\n' + "'''", "StrLit('''\\n''') ...")
        self.assert_lex("'''x''" + '\n' + "''x'''",
                        "StrLit('''x''\\n''x''') ...")
        self.assert_lex("'''''" + '\n' + "'''''",
                        "StrLit('''''\\n''') StrLit('') ...")
        self.assert_lex("'''x" + '\n' + 'xyz' + '\n' + "''x'''",
                        "StrLit('''x\\nxyz\\n''x''') ...")

        self.assert_lex('"""x' + '\n' + 'y"""', 'StrLit("""x\\ny""") ...')

    def test_unicode_literals(self):
        self.assert_lex("u'' u'foo'",
                        "UnicodeLit(u'') UnicodeLit( u'foo') ...")
        self.assert_lex('u"" u"foo"',
                        'UnicodeLit(u"") UnicodeLit( u"foo") ...')
        self.assert_lex('ur"" ur"foo"',
                        'UnicodeLit(ur"") UnicodeLit( ur"foo") ...')
        self.assert_lex('u"""foo\n"""',
                        r'UnicodeLit(u"""foo\n""") ...')

    def test_unicode_literal_capital_u(self):
        self.assert_lex("U'foo'", "UnicodeLit(U'foo') ...")

    def test_semicolons(self):
        self.assert_lex('a;b', 'Name(a) Break(;) Name(b) ...')
        self.assert_lex('a;', 'Name(a) Break(;) Eof()')

        self.assert_lex(';a', 'Break(;) Name(a) ...')
        self.assert_lex('a;;b', 'Name(a) Break(;) Break(;) Name(b) ...')

    def test_raw_string(self):
        self.assert_lex("r'' r'foo bar'",
                        "StrLit(r'') StrLit( r'foo bar') ...")
        self.assert_lex('r"" r"foo bar"',
                        'StrLit(r"") StrLit( r"foo bar") ...')

        self.assert_lex("r'\\x\\''", "StrLit(r'\\x\\'') ...")
        self.assert_lex('r"\\x\\""', 'StrLit(r"\\x\\"") ...')

        self.assert_lex("r'\\\\' ''", "StrLit(r'\\\\') StrLit( '') ...")
        self.assert_lex('r"\\\\" ""', 'StrLit(r"\\\\") StrLit( "") ...')

        self.assert_lex("r'''" + '\n' + "x'''", "StrLit(r'''\\nx''') ...")

    def test_raw_string_with_capital_r(self):
        self.assert_lex("R'foo'", "StrLit(R'foo') ...")

    def test_escapes_in_triple_quoted_literals(self):
        self.assert_lex(r"'''\''''",
                        r"StrLit('''\'''') ...")
        self.assert_lex(r'"""\""""',
                        r'StrLit("""\"""") ...')
        self.assert_lex(r'"""\\"""',
                        r'StrLit("""\\""") ...')

    def test_escapes_in_triple_quoted_raw_literals(self):
        self.assert_lex(r"r'''\''''",
                        r"StrLit(r'''\'''') ...")
        self.assert_lex(r"r'''\\'''",
                        r"StrLit(r'''\\''') ...")
        self.assert_lex(r'r"""\""""',
                        r'StrLit(r"""\"""") ...')

    def test_bytes(self):
        self.assert_lex("b'\\'' b'foo bar'",
                        "BytesLit(b'\\'') BytesLit( b'foo bar') ...")
        self.assert_lex('b"\\"" b"foo bar"',
                        'BytesLit(b"\\"") BytesLit( b"foo bar") ...')

        self.assert_lex("b'''" + '\n' + " x'''", "BytesLit(b'''\\n x''') ...")

    def test_bytes_with_capital_b(self):
        self.assert_lex("B'foo'", "BytesLit(B'foo') ...")

    def test_raw_bytes(self):
        self.assert_lex("br'x\\x\\''", "BytesLit(br'x\\x\\'') ...")
        self.assert_lex('br"x\\y\\""', 'BytesLit(br"x\\y\\"") ...')

        self.assert_lex('br"""' + '\n' + 'x"""', 'BytesLit(br"""\\nx""") ...')

    def test_raw_bytes_alternative(self):
        self.assert_lex("rb'x\\x\\''", "BytesLit(rb'x\\x\\'') ...")

    def test_backslash(self):
        self.assert_lex('a\\' + '\n' + ' b', 'Name(a) Name(\\\\n b) ...')
        self.assert_lex(
            'a = \\' + '\n' + ' 1' + '\n' + '=',
            'Name(a) Punct( =) IntLit( \\\\n 1) Break(\\n) Punct(=) ...')

    def test_backslash_in_string(self):
        self.assert_lex("'foo\\" + '\n' + "bar'", "StrLit('foo\\\\nbar') ...")
        self.assert_lex("'foo\\" + '\n' + ' zar\\' + '\n' + "  bar'",
                        "StrLit('foo\\\\n zar\\\\n  bar') ...")

        self.assert_lex('"foo\\' + '\n' + 'bar"', 'StrLit("foo\\\\nbar") ...')

    def test_backslash_in_raw_string(self):
        self.assert_lex("r'a\\" + '\n' + "b\\'1",
                        "StrLit(r'a\\\\nb\\') IntLit(1) ...")
        self.assert_lex("r'a\\" + '\n' + '-\\' + '\n' + "b\\'1",
                        "StrLit(r'a\\\\n-\\\\nb\\') IntLit(1) ...")
        self.assert_lex('r"a\\' + '\n' + 'b\\"1',
                        'StrLit(r"a\\\\nb\\") IntLit(1) ...')
        self.assert_lex('r"a\\' + '\n' + '-\\' + '\n' + 'b\\"1',
                        'StrLit(r"a\\\\n-\\\\nb\\") IntLit(1) ...')

    def test_final_dedent(self):
        self.assert_lex(
            '1' + '\n' + ' 1' + '\n',
            'IntLit(1) Break(\\n) Indent( ) IntLit(1) Break(\\n) Dedent() Eof()')

    def test_empty_line(self):
        self.assert_lex('1' + '\n' + ' 1' + '\n' + '\n',
                        r'IntLit(1) Break(\n) Indent( ) IntLit(1) '
                        r'Break(\n\n) Dedent() Eof()')

    def test_comments_and_indents(self):
        self.assert_lex('1' + '\n' + ' #x' + '\n' + ' y',
                        r'IntLit(1) Break(\n #x\n) Indent( ) Name(y) '
                        r'Break() Dedent() Eof()')
        self.assert_lex('1' + '\n' + '#x' + '\n' + ' y',
                        r'IntLit(1) Break(\n#x\n) Indent( ) Name(y) '
                        r'Break() Dedent() Eof()')

    def test_form_feed(self):
        self.assert_lex('\x0c' + '\n' + 'x', 'Name(\x0c\\nx) ...')

    def test_comment_after_linebreak(self):
        self.assert_lex('1\n# foo\n2',
                        'IntLit(1) Break(\\n# foo\\n) IntLit(2) ...')
        self.assert_lex('1\n# foo',
                        'IntLit(1) Break(\\n# foo) Eof()')

    def test_line_numbers(self):
        self.assert_line('a\\nb', [1, 1, 2, 2, 2])

        self.assert_line('(\\nb)', [1, 2, 2])  # Note: omit break and eof tokens

        self.assert_line('a\\n b', [1, 1,      # a, break
                                    2, 2, 2,   # indent, b, break
                                    2, 2])     # dedent, break
        self.assert_line('a\\n b\\nc', [1, 1,       # a, break
                                        2, 2, 2,    # indent, b, break
                                        3, 3])      # dedent, c

        self.assert_line('a\\rb', [1, 1, 2])
        self.assert_line('a\\r\\nb', [1, 1, 2])

        self.assert_line('"""x""" 1', [1, 1])
        self.assert_line('"""x\\ny""" 1', [1, 2])
        self.assert_line('"""x\\r\\ny""" 1', [1, 2])
        self.assert_line('"""x\\ry""" 1', [1, 2])
        self.assert_line('"""x\\n\\ny""" 1', [1, 3])
        self.assert_line('\\n"""x\\ny""" 1', [2, 3])

        self.assert_line('"x" 1', [1, 1])
        self.assert_line('"\\\\n" 1', [1, 2])
        self.assert_line('"\\\\nx\\\\n" 1', [1, 3])

        self.assert_line('r"x" 1', [1, 1])
        self.assert_line('r"\\\\n" 1', [1, 2])
        self.assert_line('r"\\\\nx\\\\n" 1', [1, 3])

    def test_backslash_line(self):
        self.assert_line('a\\\\n 1\\n=', [1, 2, 2, 3])

    def test_invalid_parens(self):
        self.assert_lex('([\\n )\\n1',
                        'Punct(() Punct([) Punct(\\n )) IntLit(\\n1) ...')
        self.assert_lex('])', 'Punct(]) Punct()) ...')
        self.assert_lex('(]\\n )', 'Punct(() Punct(]) Punct(\\n )) ...')
        self.assert_lex('(\\n ])', 'Punct(() Punct(\\n ]) Punct()) ...')

    def test_invalid_indent(self):
        self.assert_lex('x\\n  y\\n z',
                        'Name(x) Break(\\n) Indent(  ) Name(y) ' +
                        'Break(\\n) Dedent() LexError( ) Name(z) ...')

    def test_invalid_backslash(self):
        self.assert_lex('\\ \\nx', 'LexError(\\) Break( \\n) Name(x) ...')
        self.assert_lex('\\ \\nx', 'LexError(\\) Break( \\n) Name(x) ...')

    def test_non_terminated_string_literal(self):
        self.assert_lex("'", 'LexError(\') ...')
        self.assert_lex("'\\na", 'LexError(\') Break(\\n) Name(a) ...')

        self.assert_lex('"', 'LexError(") ...')
        self.assert_lex('"\\na', 'LexError(") Break(\\n) Name(a) ...')

        self.assert_lex("r'", 'LexError(r\') ...')
        self.assert_lex('r"', 'LexError(r") ...')

        self.assert_lex('"""', 'LexError(""") ...')
        self.assert_lex('"""\\n', 'LexError("""\\n) ...')

        self.assert_lex("'''", "LexError(''') ...")
        self.assert_lex("'''\\n", "LexError('''\\n) ...")

        self.assert_lex("'\\", 'LexError(\'\\) ...')
        self.assert_lex("'\\\\n", 'LexError(\'\\\\n) ...')
        self.assert_lex("r'\\", 'LexError(r\'\\) ...')
        self.assert_lex("r'\\\\n", 'LexError(r\'\\\\n) ...')

    def test_invalid_hex_int_literals(self):
        self.assert_lex('0x', 'LexError(  ) ...')
        self.assert_lex('0xax', 'LexError(    ) ...')

    def test_latin1_encoding(self):
        self.assert_lex(b'# coding: latin1\n"\xbb"',
                        'StrLit(# coding: latin1\\n"\xbb") Break() Eof()')

    def test_utf8_encoding(self):
        self.assert_lex('"\xbb"'.encode('utf8'),
                        'StrLit("\xbb") Break() Eof()')
        self.assert_lex(b'"\xbb"',
                        "LexError('utf8' codec can't decode byte 187 in column 2) "
                        'Break() Eof()')
        self.assert_lex(b'\n"abcde\xbc"',
                        "LexError('utf8' codec can't decode byte 188 in column 7) "
                        'Break() Eof()')

    def test_byte_order_mark(self):
        self.assert_lex('\ufeff"\xbb"'.encode('utf8'),
                        'Bom(\ufeff) StrLit("\xbb") Break() Eof()')

    def test_long_comment(self):
        prog = '# pass\n' * 1000
        self.assert_lex(prog, 'Eof(%s)' % repr(prog)[1:-1])

    # TODO
    #   invalid escape sequences in string literals etc.

    def assert_lex(self, src, lexed):
        if isinstance(src, str):
            src = src.replace('\\n', '\n')
            src = src.replace('\\r', '\r')

        if lexed.endswith(' ...'):
            lexed = lexed[:-3] + 'Break() Eof()'

        l = lex(src)[0]
        r = []
        for t in l:
            r.append(str(t))
        act = ' '.join(r)
        if act != lexed:
            print('Actual:  ', act)
            print('Expected:', lexed)
        assert_equal(act, lexed)

    def assert_line(self, s, a):
        s = s.replace('\\n', '\n')
        s = s.replace('\\r', '\r')

        tt = lex(s)[0]
        r = []
        for t in tt:
            r.append(t.line)
        if len(r) == len(a) + 2:
            a = a[:]
            a.append(a[-1])
            a.append(a[-1])
        assert_equal(r, a)
