from typing import Optional, MutableMapping, MutableSequence, List, Sequence, Tuple

import re

# Type alias for signatures in format ('func_name', '(arg, opt_arg=False)').
Sig = Tuple[str, str]


def parse_signature(sig: str) -> Optional[Tuple[str,
                                                List[str],
                                                List[str]]]:
    """Split function signature into its name, positional an optional arguments.

    The expected format is "func_name(arg, opt_arg=False)". Return the name of function
    and lists of positional and optional argument names.
    """
    m = re.match(r'([.a-zA-Z0-9_]+)\(([^)]*)\)', sig)
    if not m:
        return None
    name = m.group(1)
    name = name.split('.')[-1]
    arg_string = m.group(2)
    if not arg_string.strip():
        # Simple case -- no arguments.
        return name, [], []

    args = [arg.strip() for arg in arg_string.split(',')]
    positional = []
    optional = []
    i = 0
    while i < len(args):
        # Accept optional arguments as in both formats: x=None and [x].
        if args[i].startswith('[') or '=' in args[i]:
            break
        positional.append(args[i].rstrip('['))
        i += 1
        if args[i - 1].endswith('['):
            break
    while i < len(args):
        arg = args[i]
        arg = arg.strip('[]')
        arg = arg.split('=')[0]
        optional.append(arg)
        i += 1
    return name, positional, optional


def build_signature(positional: Sequence[str],
                    optional: Sequence[str]) -> str:
    """Build function signature from lists of positional and optional argument names."""
    args = []  # type: MutableSequence[str]
    args.extend(positional)
    for arg in optional:
        if arg.startswith('*'):
            args.append(arg)
        else:
            args.append('%s=...' % arg)
    sig = '(%s)' % ', '.join(args)
    # Ad-hoc fixes.
    sig = sig.replace('(self)', '')
    return sig


def parse_all_signatures(lines: Sequence[str]) -> Tuple[List[Sig],
                                                        List[Sig]]:
    """Parse all signatures in a given document.

    Return lists of found signatures for functions and classes.
    """
    sigs = []
    class_sigs = []
    for line in lines:
        line = line.strip()
        m = re.match(r'\.\. *(function|method|class) *:: *[a-zA-Z_]', line)
        if m:
            sig = line.split('::')[1].strip()
            parsed = parse_signature(sig)
            if parsed:
                name, fixed, optional = parsed
                if m.group(1) != 'class':
                    sigs.append((name, build_signature(fixed, optional)))
                else:
                    class_sigs.append((name, build_signature(fixed, optional)))

    return sorted(sigs), sorted(class_sigs)


def find_unique_signatures(sigs: Sequence[Sig]) -> List[Sig]:
    """Remove names with duplicate found signatures."""
    sig_map = {}  # type: MutableMapping[str, List[str]]
    for name, sig in sigs:
        sig_map.setdefault(name, []).append(sig)

    result = []
    for name, name_sigs in sig_map.items():
        if len(set(name_sigs)) == 1:
            result.append((name, name_sigs[0]))
    return sorted(result)


def infer_sig_from_docstring(docstr: str, name: str) -> Optional[Tuple[str, str]]:
    """Look for signature of function with given name in a docstring.

    Signature is any string of the format <function_name>(<signature>) -> <return type>
    or perhaps without the return type.

    In the signature, we allow the following characters:
    * colon/equal: to match default values, like "a: int = 1"
    * comma/space/brackets: for type hints like "a: Tuple[int, float]"
    * dot: for classes annotating using full path, like "a: foo.bar.baz"
    """
    if not docstr:
        return None
    docstr = docstr.lstrip()
    sig_str = r'\([a-zA-Z0-9_=:, \[\]\.]*\)'
    sig_match = r'%s(%s)' % (name, sig_str)

    # First, try to capture return type; we just match until end of line
    m = re.match(sig_match + ' -> ([a-zA-Z].*)$', docstr, re.MULTILINE)
    if m:
        # strip potential white spaces at the right of return type
        return m.group(1), m.group(2).rstrip()

    # If that didn't work, try to not match return type
    m = re.match(sig_match, docstr)
    if m:
        return m.group(1), 'Any'

    # Give up.
    return None


def infer_prop_type_from_docstring(docstr: str) -> Optional[str]:
    """Check for Google/Numpy style docstring type annotation.

    The docstring has the format "<type>: <descriptions>".
    In the type string, we allow the following characters:
    * dot: because sometimes classes are annotated using full path
    * brackets: to allow type hints like List[int]
    * comma/space: things like Tuple[int, int]
    """
    if not docstr:
        return None
    test_str = r'^([a-zA-Z0-9_, \.\[\]]*): '
    m = re.match(test_str, docstr)
    return m.group(1) if m else None
