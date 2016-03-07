"""Tokenization help for Python programs.

generate_tokens(readline) is a generator that breaks a stream of
text into Python tokens.  It accepts a readline-like method which is called
repeatedly to get the next line of input (or "" for EOF).  It generates
5-tuples with these members:

    the token type (see token.py)
    the token (a string)
    the starting (row, column) indices of the token (a 2-tuple of ints)
    the ending (row, column) indices of the token (a 2-tuple of ints)
    the original line (string)

It is designed to match the working of the Python tokenizer exactly, except
that it produces COMMENT tokens for comments and gives type OP for all
operators

Older entry points
    tokenize_loop(readline, tokeneater)
    tokenize(readline, tokeneater=printtoken)
are the same, except instead of generating tokens, tokeneater is a callback
function to which the 5 fields described above are passed as 5 arguments,
each time a new token is found.


This file was taken from the python 2.7.4 library and modified for use by
the Pyxl decoder. Changes made:
    - When it encounters an unexpected EOF, the tokenizer does not raise an
      exception, and instead yields an errortoken if appropriate.
    - When it encounters an unexpected dedent, the tokenizer does not
      raise an exception.
    - The Untokenizer class was heavily modified.


PYTHON SOFTWARE FOUNDATION LICENSE VERSION 2
--------------------------------------------

1. This LICENSE AGREEMENT is between the Python Software Foundation
("PSF"), and the Individual or Organization ("Licensee") accessing and
otherwise using this software ("Python") in source or binary form and
its associated documentation.

2. Subject to the terms and conditions of this License Agreement, PSF hereby
grants Licensee a nonexclusive, royalty-free, world-wide license to reproduce,
analyze, test, perform and/or display publicly, prepare derivative works,
distribute, and otherwise use Python alone or in any derivative version,
provided, however, that PSF's License Agreement and PSF's notice of copyright,
i.e., "Copyright (c) 2001, 2002, 2003, 2004, 2005, 2006, 2007, 2008, 2009, 2010,
2011, 2012, 2013 Python Software Foundation; All Rights Reserved" are retained
in Python alone or in any derivative version prepared by Licensee.

3. In the event Licensee prepares a derivative work that is based on
or incorporates Python or any part thereof, and wants to make
the derivative work available to others as provided herein, then
Licensee hereby agrees to include in any such work a brief summary of
the changes made to Python.

4. PSF is making Python available to Licensee on an "AS IS"
basis.  PSF MAKES NO REPRESENTATIONS OR WARRANTIES, EXPRESS OR
IMPLIED.  BY WAY OF EXAMPLE, BUT NOT LIMITATION, PSF MAKES NO AND
DISCLAIMS ANY REPRESENTATION OR WARRANTY OF MERCHANTABILITY OR FITNESS
FOR ANY PARTICULAR PURPOSE OR THAT THE USE OF PYTHON WILL NOT
INFRINGE ANY THIRD PARTY RIGHTS.

5. PSF SHALL NOT BE LIABLE TO LICENSEE OR ANY OTHER USERS OF PYTHON
FOR ANY INCIDENTAL, SPECIAL, OR CONSEQUENTIAL DAMAGES OR LOSS AS
A RESULT OF MODIFYING, DISTRIBUTING, OR OTHERWISE USING PYTHON,
OR ANY DERIVATIVE THEREOF, EVEN IF ADVISED OF THE POSSIBILITY THEREOF.

6. This License Agreement will automatically terminate upon a material
breach of its terms and conditions.

7. Nothing in this License Agreement shall be deemed to create any
relationship of agency, partnership, or joint venture between PSF and
Licensee.  This License Agreement does not grant permission to use PSF
trademarks or trade name in a trademark sense to endorse or promote
products or services of Licensee, or any third party.

8. By copying, installing or otherwise using Python, Licensee
agrees to be bound by the terms and conditions of this License
Agreement.
"""

from __future__ import print_function

__author__ = 'Ka-Ping Yee <ping@lfw.org>'
__credits__ = ('GvR, ESR, Tim Peters, Thomas Wouters, Fred Drake, '
               'Skip Montanaro, Raymond Hettinger')

if False:
    from typing import List, Dict

import string
import re
from token import *

import token
x = None # type: str
__all__ = [x for x in dir(token) if not x.startswith("_")]
__all__ += ["COMMENT", "tokenize", "generate_tokens", "NL", "untokenize"]
del x
del token

COMMENT = N_TOKENS
tok_name[COMMENT] = 'COMMENT'
NL = N_TOKENS + 1
tok_name[NL] = 'NL'
N_TOKENS += 2


def group(*choices): return '(' + '|'.join(choices) + ')'


def any(*choices): return group(*choices) + '*'


def maybe(*choices): return group(*choices) + '?'

Whitespace = r'[ \f\t]*'
Comment = r'#[^\r\n]*'
Ignore = Whitespace + any(r'\\\r?\n' + Whitespace) + maybe(Comment)
Name = r'[a-zA-Z_]\w*'

Hexnumber = r'0[xX][\da-fA-F]+[lL]?'
Octnumber = r'(0[oO][0-7]+)|(0[0-7]*)[lL]?'
Binnumber = r'0[bB][01]+[lL]?'
Decnumber = r'[1-9]\d*[lL]?'
Intnumber = group(Hexnumber, Binnumber, Octnumber, Decnumber)
Exponent = r'[eE][-+]?\d+'
Pointfloat = group(r'\d+\.\d*', r'\.\d+') + maybe(Exponent)
Expfloat = r'\d+' + Exponent
Floatnumber = group(Pointfloat, Expfloat)
Imagnumber = group(r'\d+[jJ]', Floatnumber + r'[jJ]')
Number = group(Imagnumber, Floatnumber, Intnumber)

# Tail end of ' string.
Single = r"[^'\\]*(?:\\.[^'\\]*)*'"
# Tail end of " string.
Double = r'[^"\\]*(?:\\.[^"\\]*)*"'
# Tail end of ''' string.
Single3 = r"[^'\\]*(?:(?:\\.|'(?!''))[^'\\]*)*'''"
# Tail end of """ string.
Double3 = r'[^"\\]*(?:(?:\\.|"(?!""))[^"\\]*)*"""'
Triple = group("[uUbB]?[rR]?'''", '[uUbB]?[rR]?"""')
# Single-line ' or " string.
String = group(r"[uUbB]?[rR]?'[^\n'\\]*(?:\\.[^\n'\\]*)*'",
               r'[uUbB]?[rR]?"[^\n"\\]*(?:\\.[^\n"\\]*)*"')

# Because of leftmost-then-longest match semantics, be sure to put the
# longest operators first (e.g., if = came before ==, == would get
# recognized as two instances of =).
Operator = group(r"\*\*=?", r">>=?", r"<<=?", r"<>", r"!=",
                 r"//=?",
                 r"[+\-*/%&|^=<>]=?",
                 r"~")

Bracket = '[][(){}]'
Special = group(r'\r?\n', r'[:;.,`@]')
Funny = group(Operator, Bracket, Special)

PlainToken = group(Number, Funny, String, Name)
Token = Ignore + PlainToken

# First (or only) line of ' or " string.
ContStr = group(r"[uUbB]?[rR]?'[^\n'\\]*(?:\\.[^\n'\\]*)*" +
                group("'", r'\\\r?\n'),
                r'[uUbB]?[rR]?"[^\n"\\]*(?:\\.[^\n"\\]*)*' +
                group('"', r'\\\r?\n'))
PseudoExtras = group(r'\\\r?\n|\Z', Comment, Triple)
PseudoToken = Whitespace + group(PseudoExtras, Number, Funny, ContStr, Name)

tokenprog, pseudoprog, single3prog, double3prog = map(
    re.compile, (Token, PseudoToken, Single3, Double3))
endprogs = {"'": re.compile(Single), '"': re.compile(Double),
            "'''": single3prog, '"""': double3prog,
            "r'''": single3prog, 'r"""': double3prog,
            "u'''": single3prog, 'u"""': double3prog,
            "ur'''": single3prog, 'ur"""': double3prog,
            "R'''": single3prog, 'R"""': double3prog,
            "U'''": single3prog, 'U"""': double3prog,
            "uR'''": single3prog, 'uR"""': double3prog,
            "Ur'''": single3prog, 'Ur"""': double3prog,
            "UR'''": single3prog, 'UR"""': double3prog,
            "b'''": single3prog, 'b"""': double3prog,
            "br'''": single3prog, 'br"""': double3prog,
            "B'''": single3prog, 'B"""': double3prog,
            "bR'''": single3prog, 'bR"""': double3prog,
            "Br'''": single3prog, 'Br"""': double3prog,
            "BR'''": single3prog, 'BR"""': double3prog,
            'r': None, 'R': None, 'u': None, 'U': None,
            'b': None, 'B': None}

triple_quoted = {} # type: Dict[str, str]
for t in ("'''", '"""',
          "r'''", 'r"""', "R'''", 'R"""',
          "u'''", 'u"""', "U'''", 'U"""',
          "ur'''", 'ur"""', "Ur'''", 'Ur"""',
          "uR'''", 'uR"""', "UR'''", 'UR"""',
          "b'''", 'b"""', "B'''", 'B"""',
          "br'''", 'br"""', "Br'''", 'Br"""',
          "bR'''", 'bR"""', "BR'''", 'BR"""'):
    triple_quoted[t] = t
single_quoted = {} # type: Dict[str, str]
for t in ("'", '"',
          "r'", 'r"', "R'", 'R"',
          "u'", 'u"', "U'", 'U"',
          "ur'", 'ur"', "Ur'", 'Ur"',
          "uR'", 'uR"', "UR'", 'UR"',
          "b'", 'b"', "B'", 'B"',
          "br'", 'br"', "Br'", 'Br"',
          "bR'", 'bR"', "BR'", 'BR"'):
    single_quoted[t] = t

tabsize = 8


class TokenError(Exception): pass


class StopTokenizing(Exception): pass


def printtoken(type, token, srow_scol, erow_ecol, line):  # for testing
    srow, scol = srow_scol
    erow, ecol = erow_ecol
    print("%d,%d-%d,%d:\t%s\t%s" %
          (srow, scol, erow, ecol, tok_name[type], repr(token)))


def tokenize(readline, tokeneater=printtoken):
    """
    The tokenize() function accepts two parameters: one representing the
    input stream, and one providing an output mechanism for tokenize().

    The first parameter, readline, must be a callable object which provides
    the same interface as the readline() method of built-in file objects.
    Each call to the function should return one line of input as a string.

    The second parameter, tokeneater, must also be a callable object. It is
    called once for each token, with five arguments, corresponding to the
    tuples generated by generate_tokens().
    """
    try:
        tokenize_loop(readline, tokeneater)
    except StopTokenizing:
        pass


# backwards compatible interface
def tokenize_loop(readline, tokeneater):
    for token_info in generate_tokens(readline):
        tokeneater(*token_info)


class Untokenizer:

    # PYXL MODIFICATION: This entire class.

    def __init__(self, row=None, col=None):
        self.tokens = []
        self.prev_row = row
        self.prev_col = col

    def add_whitespace(self, start):
        row, col = start
        assert row >= self.prev_row, "row (%r) should be >= prev_row (%r)" % (row, self.prev_row)
        row_offset = row - self.prev_row
        if row_offset:
            self.tokens.append("\n" * row_offset)
        col_offset = col - self.prev_col
        if col_offset:
            self.tokens.append(" " * col_offset)

    def feed(self, t):
        assert len(t) == 5
        tok_type, token, start, end, line = t
        if (self.prev_row is None):
            self.prev_row, self.prev_col = start
        self.add_whitespace(start)
        self.tokens.append(token)
        self.prev_row, self.prev_col = end
        if tok_type in (NEWLINE, NL):
            self.prev_row += 1
            self.prev_col = 0

    def finish(self):
        return "".join(self.tokens)

    def untokenize(self, iterable):
        for t in iterable:
            self.feed(t)
        return self.finish()


def untokenize(iterable):
    """Transform tokens back into Python source code.

    Each element returned by the iterable must be a token sequence
    with at least two elements, a token number and token value.  If
    only two tokens are passed, the resulting output is poor.

    Round-trip invariant for full input:
        Untokenized source will match input source exactly

    Round-trip invariant for limited intput:
        # Output text will tokenize the back to the input
        t1 = [tok[:2] for tok in generate_tokens(f.readline)]
        newcode = untokenize(t1)
        readline = iter(newcode.splitlines(1)).next
        t2 = [tok[:2] for tok in generate_tokens(readline)]
        assert t1 == t2
    """
    ut = Untokenizer()
    return ut.untokenize(iterable)


def generate_tokens(readline):
    """
    The generate_tokens() generator requires one argment, readline, which
    must be a callable object which provides the same interface as the
    readline() method of built-in file objects. Each call to the function
    should return one line of input as a string.  Alternately, readline
    can be a callable function terminating with StopIteration:
        readline = open(myfile).next    # Example of alternate readline

    The generator produces 5-tuples with these members: the token type; the
    token string; a 2-tuple (srow, scol) of ints specifying the row and
    column where the token begins in the source; a 2-tuple (erow, ecol) of
    ints specifying the row and column where the token ends in the source;
    and the line on which the token was found. The line passed is the
    logical line; continuation lines are included.
    """
    lnum = parenlev = continued = 0
    namechars, numchars = string.ascii_letters + '_', '0123456789'
    contstr, needcont = '', 0
    contline = None
    indents = [0]

    if 0:
        # type hints for mypy
        strstart = (0, 0)
        endprog = re.compile('')
    while 1:                                   # loop over lines in stream
        try:
            line = readline()
        except StopIteration:
            line = ''
        lnum += 1
        pos, max = 0, len(line)

        if contstr:                            # continued string
            if not line:
                # PYXL MODIFICATION: instead of raising an error here, we
                # return the remainder of the file as an errortoken.
                yield (ERRORTOKEN, contstr,
                       strstart, (lnum, 0), contline + line)
                contstr, needcont = '', 0
                contline = None
                return
            endmatch = endprog.match(line)
            if endmatch:
                pos = end = endmatch.end(0)
                yield (STRING, contstr + line[:end],
                       strstart, (lnum, end), contline + line)
                contstr, needcont = '', 0
                contline = None
            elif needcont and line[-2:] != '\\\n' and line[-3:] != '\\\r\n':
                yield (ERRORTOKEN, contstr + line,
                       strstart, (lnum, len(line)), contline)
                contstr = ''
                contline = None
                continue
            else:
                contstr = contstr + line
                contline = contline + line
                continue

        elif parenlev == 0 and not continued:  # new statement
            if not line: break
            column = 0
            while pos < max:                   # measure leading whitespace
                if line[pos] == ' ':
                    column += 1
                elif line[pos] == '\t':
                    column = (column // tabsize + 1) * tabsize
                elif line[pos] == '\f':
                    column = 0
                else:
                    break
                pos += 1
            if pos == max:
                break

            if line[pos] in '#\r\n':           # skip comments or blank lines
                if line[pos] == '#':
                    comment_token = line[pos:].rstrip('\r\n')
                    nl_pos = pos + len(comment_token)
                    yield (COMMENT, comment_token,
                           (lnum, pos), (lnum, pos + len(comment_token)), line)
                    yield (NL, line[nl_pos:],
                           (lnum, nl_pos), (lnum, len(line)), line)
                else:
                    yield ((NL, COMMENT)[line[pos] == '#'], line[pos:],
                           (lnum, pos), (lnum, len(line)), line)
                continue

            if column > indents[-1]:           # count indents or dedents
                indents.append(column)
                yield (INDENT, line[:pos], (lnum, 0), (lnum, pos), line)
            while column < indents[-1]:
                if column not in indents:
                    # PYXL MODIFICATION: instead of raising an error here, we
                    # emit an empty dedent token, which has no effect on
                    # the decoded file.
                    pass
                indents = indents[:-1]
                yield (DEDENT, '', (lnum, pos), (lnum, pos), line)

        else:                                  # continued statement
            if not line:
                # PYXL MODIFICATION: instead of raising an error here, we
                # return as if successful.
                return
            continued = 0

        while pos < max:
            pseudomatch = pseudoprog.match(line, pos)
            if pseudomatch:                                # scan for tokens
                start, end = pseudomatch.span(1)
                spos, epos, pos = (lnum, start), (lnum, end), end
                if start == end:
                    continue
                token, initial = line[start:end], line[start]

                if initial in numchars or \
                   (initial == '.' and token != '.'):      # ordinary number
                    yield (NUMBER, token, spos, epos, line)
                elif initial in '\r\n':
                    yield (NL if parenlev > 0 else NEWLINE,
                           token, spos, epos, line)
                elif initial == '#':
                    assert not token.endswith("\n")
                    yield (COMMENT, token, spos, epos, line)
                elif token in triple_quoted:
                    endprog = endprogs[token]
                    endmatch = endprog.match(line, pos)
                    if endmatch:                           # all on one line
                        pos = endmatch.end(0)
                        token = line[start:pos]
                        yield (STRING, token, spos, (lnum, pos), line)
                    else:
                        strstart = (lnum, start)           # multiple lines
                        contstr = line[start:]
                        contline = line
                        break
                elif initial in single_quoted or \
                    token[:2] in single_quoted or \
                        token[:3] in single_quoted:
                    if token[-1] == '\n':                  # continued string
                        strstart = (lnum, start)
                        endprog = (endprogs[initial] or endprogs[token[1]] or
                                   endprogs[token[2]])
                        contstr, needcont = line[start:], 1
                        contline = line
                        break
                    else:                                  # ordinary string
                        yield (STRING, token, spos, epos, line)
                elif initial in namechars:                 # ordinary name
                    yield (NAME, token, spos, epos, line)
                elif initial == '\\':                      # continued stmt
                    continued = 1
                else:
                    if initial in '([{':
                        parenlev += 1
                    elif initial in ')]}':
                        parenlev -= 1
                    yield (OP, token, spos, epos, line)
            else:
                yield (ERRORTOKEN, line[pos],
                       (lnum, pos), (lnum, pos + 1), line)
                pos += 1

    for indent in indents[1:]:                 # pop remaining indent levels
        yield (DEDENT, '', (lnum, 0), (lnum, 0), '')
    yield (ENDMARKER, '', (lnum, 0), (lnum, 0), '')

if __name__ == '__main__':                     # testing
    import sys
    if len(sys.argv) > 1:
        tokenize(open(sys.argv[1]).readline)
    else:
        tokenize(sys.stdin.readline)
