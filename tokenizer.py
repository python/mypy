import pytokenize as tokenize
import re
from StringIO import StringIO
from pytokenize import Untokenizer

def get_end_pos(start_pos, tvalue):
    row, col = start_pos
    for c in tvalue:
        if c == '\n':
            col = 0
            row += 1
        else:
            col += 1
    return (row, col)

class RewindableTokenStream(object):
    """
    A token stream, with the ability to rewind and restart tokenization while maintaining correct
    token position information.

    Invariants:
        - zero_row and zero_col are the correct values to adjust the line and possibly column of the
        tokens being produced by _tokens.
        - Tokens in unshift_buffer have locations with absolute position (relative to the beginning
          of the file, not relative to where we last restarted tokenization).
    """

    def __init__(self, readline):
        self.orig_readline = readline
        self.unshift_buffer = []
        self.rewound_buffer = None
        self._tokens = tokenize.generate_tokens(self._readline)
        self.zero_row, self.zero_col = (0, 0)
        self.stop_readline = False

    def _dumpstate(self):
        print "tokenizer state:"
        print "  zero:", (self.zero_row, self.zero_col)
        print "  rewound_buffer:", self.rewound_buffer
        print "  unshift_buffer:", self.unshift_buffer

    def _readline(self):
        if self.stop_readline:
            return ""
        if self.rewound_buffer:
            line = self.rewound_buffer.readline()
            if line:
                return line
            else:
                self.rewound_buffer = None  # fallthrough to orig_readline
        return self.orig_readline()

    def _flush(self):
        self.stop_readline = True
        tokens = list(tok for tok in self)
        self.stop_readline = False
        return tokens

    def _adjust_position(self, pos):
        row, col = pos
        if row == 1:  # rows are 1-indexed
            col += self.zero_col
        row += self.zero_row
        return (row, col)

    def rewind_and_retokenize(self, rewind_token):
        """Rewind the given token (which is expected to be the last token read from this stream, or
        the end of such token); then restart tokenization."""
        ttype, tvalue, (row, col), tend, tline = rewind_token
        tokens = [rewind_token] + self._flush()
        self.zero_row, self.zero_col = (row - 1, col)  # rows are 1-indexed, cols are 0-indexed
        self.rewound_buffer = StringIO(Untokenizer().untokenize(tokens))
        self.unshift_buffer = []
        self._tokens = tokenize.generate_tokens(self._readline)

    def next(self):
        if self.unshift_buffer:
            token = self.unshift_buffer.pop(0)
        else:
            ttype, tvalue, tstart, tend, tline = self._tokens.next()
            tstart = self._adjust_position(tstart)
            tend = self._adjust_position(tend)
            token = (ttype, tvalue, tstart, tend, tline)
        return token

    def __iter__(self):
        return self

    def unshift(self, token):
        """Rewind the given token, without retokenizing. It will be the next token read from the
        stream."""
        self.unshift_buffer[:0] = [token]

def py3annot_untokenize(tokens):
    parts = []
    prev_row = 1
    prev_col = 0

    for token in tokens:
        ttype, tvalue, tstart, tend, tline = token
        row, col = tstart

        assert row == prev_row, 'Unexpected jump in rows on line:%d: %s' % (row, tline)

        # Add whitespace
        col_offset = col - prev_col
        assert col_offset >= 0
        if col_offset > 0:
            parts.append(" " * col_offset)

        parts.append(tvalue)
        prev_row, prev_col = tend

        if ttype in (tokenize.NL, tokenize.NEWLINE):
            prev_row += 1
            prev_col = 0

    return ''.join(parts)

def py3annot_tokenize(readline):
    return transform_tokens(RewindableTokenStream(readline))

def transform_tokens(tokens):
    first_token_value_from_line = None  # value of first non-whitespace token on cur line
    line_root_depth = -1  # bracket nesting depth of current line
    cur_line = 0  # index of current line

    prev_token = None  # last token seen
    bracket_depth = 0  # bracket nesting depth of current token

    while 1:
        try:
            token = tokens.next()
        except (StopIteration, tokenize.TokenError):
            break

        tvalue, start_line = token[1], token[2][0]

        bracket_depth += update_bracket_depth(token)

        if start_line > cur_line and tvalue.strip():  # first non-whitespace token on a new line
            cur_line = start_line
            first_token_value_from_line = tvalue
            line_root_depth = bracket_depth

        if first_token_value_from_line == 'def':
            if tvalue == ':' and bracket_depth > line_root_depth:  # param type annotation
                token = scan_until(['=', ',', ')'], tokens)
                bracket_depth += update_bracket_depth(token)
            if tvalue == '-' and bracket_depth == line_root_depth:
                prev_token = token
                token = tokens.next()
                if token[1] == '>':  # return type annotation
                    token = scan_until([':'], tokens)
                else:
                    yield prev_token
                bracket_depth += update_bracket_depth(token)

        prev_token = token
        yield token

def scan_until(match_list, tokens):
    """Steps through the tokens iterator until it finds a token whose value is in match_list at the
    original bracket depth."""
    bracket_depth = 0
    token = tokens.next()
    while token[1] not in match_list or bracket_depth != 0:
        if token[0] == tokenize.OP and token[1] in ['{', '(', '[']:
            bracket_depth += 1
        if token[0] == tokenize.OP and token[1] in ['}', ')', ']']:
            bracket_depth -= 1
        token = tokens.next()

    return token

def update_bracket_depth(token):
    """Returns +/-1 if the current token increases/decreases bracket nesting depth, 0 otherwise."""
    if token[0] == tokenize.OP and token[1] in ['{', '(', '[']:
        return 1
    elif token[0] == tokenize.OP and token[1] in ['}', ')', ']']:
        return -1
    else:
        return 0
