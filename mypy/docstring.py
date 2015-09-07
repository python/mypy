"""Find type annotations from a docstring.

Do not actually try to parse the annotations, just return them as strings.

Also recognize some common non-PEP-484 aliases such as 'a string' for 'str'
and 'list of int' for 'List[int]'.

Based on original implementation by Kyle Consalus.

TODO: Decide whether it makes sense to do the heuristic analysis of aliases and natural
  language type descriptions as it's all kind of ad hoc.
"""

import re
from typing import Optional, List, Tuple, Dict, Sequence
from collections import OrderedDict


_example1 = """Fetches rows from a Bigtable.

    Retrieves rows pertaining to the given keys from the Table instance
    represented by big_table.  Silly things may happen if
    other_silly_variable is not None.

    Args:
        big_table: An open Bigtable Table instance.
        keys (Sequence[str]): A sequence of strings representing the key of each table row
            to fetch.
            but: if the keys are broken, we die.
        other_silly_variable (int): Another optional variable, that has a much
            longer name than the other args, and which does nothing.
        abc0 (Tuple[int, bool]): Hi.
        abc (Tuple[int, bool], optional): Hi.

    Returns:
        Dict[str, int]: Things.

    Raises:
        IOError: An error occurred accessing the bigtable.Table object.
    """


# Regular expression that finds the argument name and type in a line such
# as '   name (type): description'.
PARAM_RE = re.compile(r'^\s*(?P<name>[A-Za-z_][A-Za-z_0-9]*)(\s+\((?P<type>[^)]+)\))?:')

# Type strings with these brackets are rejected.
BRACKET_RE = re.compile(r'\(|\)|\{|\}')

# Support some commonly used type aliases that aren't normally valid in annotations.
# TODO: Optionally reject these (or give a warning if these are used).
translations = {
    'obj': 'Any',
    'boolean': 'bool',
    'string': 'str',
    'integer': 'int',
    'number': 'float',
    'list': 'List[Any]',
    'set': 'Set[Any]',
    'sequence': 'Sequence[Any]',
    'iterable': 'Iterable[Any]',
    'dict': 'Dict[Any, Any]',
    'dictionary': 'Dict[Any, Any]',
    'mapping': 'Mapping[Any, Any]',
}

# Some common types that we should recognize.
known_types = [
    'int', 'str', 'unicode', 'bool', 'float', 'None', 'tuple',
]

known_generic_types = [
    'List', 'Set', 'Dict', 'Iterable', 'Sequence', 'Mapping',
]

# Some natural language patterns that we want to support in docstrings.
known_patterns = [
    ('list of ?', 'List[?]'),
    ('set of ?', 'List[?]'),
    ('sequence of ?', 'Sequence[?]'),
    ('optional ?', 'Optional[?]'),
]


class DocstringTypes(object):
    def __init__(self):
        self.args = OrderedDict()  # type: Dict[str, Optional[str]]
        self.rettype = None  # type: Optional[str]

    def as_type_str(self) -> str:
        return ('(' + ','.join([v or 'Any' for v in self.args.values()]) +
                ') -> ' + (self.rettype or 'Any'))

    def __str__(self):
        return repr({'args': self.args, 'return': self.rettype})


def wsprefix(s: str) -> str:
    return s[:len(s) - len(s.lstrip())]


def scrubtype(typestr: Optional[str], only_known=False) -> Optional[str]:
    if typestr is None:
        return typestr

    # Reject typestrs with parentheses or curly braces.
    if BRACKET_RE.search(typestr):
        return None

    # Reject typestrs whose square brackets don't match & those with commas outside square
    # brackets.
    bracket_level = 0
    for c in typestr:
        if c == '[':
            bracket_level += 1
        elif c == ']':
            bracket_level -= 1
            if bracket_level < 0:  # Square brackets don't match
                return None
        elif c == ',' and bracket_level == 0:  # A comma appears outside brackets
            return None
    if bracket_level > 0:
        return None

    recognized = False
    typestr = typestr.strip()
    for prefix in ('a', 'A', 'an', 'An', 'the', 'The'):
        if typestr.startswith(prefix + ' '):
            typestr = typestr[len(prefix) + 1:]
    if typestr in translations:
        typestr = translations[typestr]
        recognized = True
    if typestr in known_types:
        recognized = True
    if any(typestr.startswith(t + '[') for t in known_generic_types):
        recognized = True
    for pattern, repl in known_patterns:
        pattern = pattern.replace('?', '([a-zA-Z]+)') + '$'
        m = re.match(pattern, typestr)
        if m:
            arg = scrubtype(m.group(1), only_known=only_known)
            if arg:
                typestr = repl.replace('?', arg)
                recognized = True
    if not recognized and only_known:
        # This is potentially a type but not one of the known types.
        return None
    return typestr


def parse_args(lines: List[str]) -> Tuple[Dict[str, str], List[str]]:
    res = OrderedDict()  # type: Dict[str, str]
    indent = wsprefix(lines[0])
    while lines:
        l = lines[0]
        if l.strip() in ('Returns:', 'Raises:'):
            break
        lines = lines[1:]
        if not l or l.isspace():
            break
        if not wsprefix(l) == indent:
            continue
        m = PARAM_RE.match(l)
        if m:
            gd = m.groupdict()
            res[gd['name']] = scrubtype(gd['type'])
    return res, lines


def parse_return(lines: List[str]) -> Tuple[Optional[str], List[str]]:
    res = None  # type: Optional[str]
    while lines and lines[0].strip == '':
        lines = lines[1:]
    if lines:
        l = lines[0]
        lines = lines[1:]
        segs = l.strip().split(':', 1)
        if len(segs) >= 1:
            res = scrubtype(segs[0], only_known=(len(segs) == 1))
    return res, lines


def parse_docstring(pds: str) -> DocstringTypes:
    ds = DocstringTypes()
    lines = pds.splitlines()
    while lines:
        first = lines[0]
        if first.strip() in ('Args:', 'Params:', 'Arguments:'):
            ds.args, lines = parse_args(lines[1:])
            break
        lines = lines[1:]
    while lines:
        first = lines[0]
        if first.strip() == 'Returns:':
            ds.rettype, lines = parse_return(lines[1:])
            break
        lines = lines[1:]
    if not ds.args:
        return None
    return ds


if __name__ == '__main__':
    print(parse_docstring(_example1))
