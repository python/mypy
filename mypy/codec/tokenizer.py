from __future__ import absolute_import

from . import pytokenize as tokenize


def get_end_pos(start_pos, tvalue):
    row, col = start_pos
    for c in tvalue:
        if c == '\n':
            col = 0
            row += 1
        else:
            col += 1
    return (row, col)


def mypy_untokenize(tokens):
    parts = []
    prev_row = 1
    prev_col = 0

    for token in tokens:
        ttype, tvalue, tstart, tend, tline = token
        row, col = tstart

        row_offset = row - prev_row

        assert row_offset >= 0, 'Unexpected jump in rows on line:%d: %s' % (row, tline)

        # Add whitespace
        if row_offset > 0:
            if ttype == tokenize.ENDMARKER:  # don't add a continuation at the end of a file
                parts.append('\n' * row_offset)
            else:
                parts.append("\\\n" * row_offset)

        if row_offset:
            col_offset = col
        else:
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


def mypy_tokenize(readline):
    return transform_tokens(tokenize.generate_tokens(readline))


def transform_tokens(tokens):
    # state variables
    in_a_def_statement = False  # true if we're between a 'def' and associated ':'
    def_depth = -1  # bracket depth of last def, for reference

    bracket_depth = 0  # bracket nesting depth of current token

    while 1:
        try:
            token = tokens.next()
        except (StopIteration, tokenize.TokenError):
            break

        tvalue = token[1]

        bracket_depth += bracket_delta(token)

        if in_a_def_statement:
            if tvalue == ':' and bracket_depth > def_depth:
                # param type annotation
                newlines, token = scan_until(['=', ',', ')'], tokens)
                tvalue = token[1]
                for tok in newlines:
                    yield tok
                bracket_depth += bracket_delta(token)
            if tvalue == ')' and bracket_depth == def_depth:
                # return type annotation
                # TODO assert next are -> if there's an annotation at all
                yield token
                newlines, token = scan_until([':'], tokens)
                # don't explicitly yield the newlines here, untokenize can handle continuations
                in_a_def_statement = False
        elif tvalue == 'def':
            in_a_def_statement = True
            def_depth = bracket_depth

        yield token


def scan_until(match_list, tokens):
    """Steps through the tokens iterator until it finds a token whose value is in match_list at the
    original bracket depth. Returns the token that matches, plus a list of other tokens that should
    be kept (currently only newlines).
    """
    bracket_depth = 0
    token = tokens.next()
    to_keep = []
    while token[1] not in match_list or bracket_depth != 0:
        bracket_depth += bracket_delta(token)
        if token[0] in (tokenize.NL, tokenize.NEWLINE):
            # keep newlines
            to_keep.append(token)
        token = tokens.next()
    return to_keep, token


def bracket_delta(token):
    """Returns +/-1 if the current token increases/decreases bracket nesting depth, 0 otherwise."""
    if token[0] == tokenize.OP and token[1] in ['{', '(', '[']:
        return 1
    elif token[0] == tokenize.OP and token[1] in ['}', ')', ']']:
        return -1
    else:
        return 0
