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
    in_a_def_statement = False  # true if we're between a 'def' and a ':'
    def_depth = -1  # bracket depth of last def, for reference

    prev_token = None  # last token seen
    bracket_depth = 0  # bracket nesting depth of current token

    while 1:
        try:
            token = tokens.next()
        except (StopIteration, tokenize.TokenError):
            break

        tvalue, start_line = token[1], token[2][0]

        bracket_depth += bracket_delta(token)

        if in_a_def_statement:
            if tvalue == ':' and bracket_depth > def_depth:
                # param type annotation
                newlines, token = scan_until(['=', ',', ')'], tokens)
                for tok in newlines:
                    yield tok
                bracket_depth += bracket_delta(token)
            elif tvalue == '-' and bracket_depth == def_depth:
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
            elif tvalue == ':' and bracket_depth == def_depth:
                in_a_def_statement = False
        elif tvalue == 'def':
            in_a_def_statement = True
            def_depth = bracket_depth

        # tokenize has this bug where you can get line jumps without a newline token
        # we check and fix for that here by seeing if there was a line jump
        if prev_token:
            prev_ttype, prev_tvalue, prev_tstart, prev_tend, prev_tline = prev_token

            prev_row, prev_col = prev_tend
            cur_row, cur_col = token[2]

            # check for a line jump without a newline token
            if (prev_row < cur_row and prev_ttype not in (tokenize.NEWLINE, tokenize.NL)):

                # tokenize also forgets \ continuations :(
                prev_line = prev_tline.strip()
                if prev_ttype != tokenize.COMMENT and prev_line and prev_line[-1] == '\\':
                    start_pos = (prev_row, prev_col)
                    end_pos = (prev_row, prev_col+1)
                    yield (tokenize.STRING, ' \\', start_pos, end_pos, prev_tline)
                    prev_col += 1

                start_pos = (prev_row, prev_col)
                end_pos = (prev_row, prev_col+1)
                yield (tokenize.NL, '\n', start_pos, end_pos, prev_tline)

        prev_token = token
        yield token

def scan_until(match_list, tokens):
    """Steps through the tokens iterator until it finds a token whose value is in match_list at the
    original bracket depth. Returns the token that matches, plus a list of other tokens that should
    be kept (currently only newlines).
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
