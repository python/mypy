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
    return transform_tokens(tokenize.generate_tokens(readline))

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

        bracket_depth += bracket_delta(token)

        if start_line > cur_line and tvalue.strip():  # first non-whitespace token on a new line
            cur_line = start_line
            first_token_value_from_line = tvalue
            line_root_depth = bracket_depth

        if first_token_value_from_line == 'def':
            if tvalue == ':' and bracket_depth > line_root_depth:
                # param type annotation
                newlines, token = scan_until(['=', ',', ')'], tokens)
                for tok in newlines:
                    yield tok
                bracket_depth += bracket_delta(token)
            if tvalue == '-' and bracket_depth == line_root_depth:
                prev_token = token
                token = tokens.next()
                if token[1] == '>' and token[2] == prev_token[3]:  # -> adjacent (not - >, etc.)
                    # return type annotation
                    newlines, token = scan_until([':'], tokens)
                    for tok in newlines:
                        yield tok
                else:
                    yield prev_token
                bracket_depth += bracket_delta(token)

        prev_token = token
        yield token

def scan_until(match_list, tokens):
    """Steps through the tokens iterator until it finds a token whose value is in match_list at the
    original bracket depth.
    Returns a list of tokens that should be kept. If a token in the match list is found, it will be
    the last token in the returned list and previous elements can only be newlines. However, if no
    matching token is found then 
    """
    bracket_depth = 0
    token = tokens.next()
    to_rewind = []
    while token[1] not in match_list or bracket_depth != 0:
        bracket_depth += bracket_delta(token)
        if token[0] in (tokenize.NL, tokenize.NEWLINE):
            # keep newlines
            to_rewind.append(token)
        token = tokens.next()
    return to_rewind, token

def bracket_delta(token):
    """Returns +/-1 if the current token increases/decreases bracket nesting depth, 0 otherwise."""
    if token[0] == tokenize.OP and token[1] in ['{', '(', '[']:
        return 1
    elif token[0] == tokenize.OP and token[1] in ['}', ')', ']']:
        return -1
    else:
        return 0
