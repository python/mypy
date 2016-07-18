import re
import sys

from typing import Any, Optional, Tuple, Sequence, MutableSequence, List, MutableMapping


# Type Alias for Signatures
Sig = Tuple[str, str]


def parse_signature(sig: str) -> Optional[Tuple[str,
                                                List[str],
                                                List[str]]]:
    m = re.match(r'([.a-zA-Z0-9_]+)\(([^)]*)\)', sig)
    if not m:
        return None
    name = m.group(1)
    name = name.split('.')[-1]
    arg_string = m.group(2)
    if not arg_string.strip():
        return (name, [], [])
    args = [arg.strip() for arg in arg_string.split(',')]
    fixed = []
    optional = []
    i = 0
    while i < len(args):
        if args[i].startswith('[') or '=' in args[i]:
            break
        fixed.append(args[i].rstrip('['))
        i += 1
        if args[i - 1].endswith('['):
            break
    while i < len(args):
        arg = args[i]
        arg = arg.strip('[]')
        arg = arg.split('=')[0]
        optional.append(arg)
        i += 1
    return (name, fixed, optional)


def build_signature(fixed: MutableSequence[str],
                    optional: MutableSequence[str]) -> str:
    args = fixed
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
    sig_map = {}  # type: MutableMapping[str, List[str]]
    for name, sig in sigs:
        sig_map.setdefault(name, []).append(sig)
    result = []
    for name, name_sigs in sig_map.items():
        if len(set(name_sigs)) == 1:
            result.append((name, name_sigs[0]))
    return sorted(result)


def is_c_module(module):
    return '__file__' not in module.__dict__ or module.__dict__['__file__'].endswith('.so')


def write_header(file, module_name, pyversion=(3, 5)):
    if module_name:
        if pyversion[0] >= 3:
            version = '%d.%d' % (sys.version_info.major,
                                 sys.version_info.minor)
        else:
            version = '2'
        file.write('# Stubs for %s (Python %s)\n' % (module_name, version))
    file.write(
        '#\n'
        '# NOTE: This dynamically typed stub was automatically generated by stubgen.\n\n')


def infer_sig_from_docstring(docstr, name):
    if not docstr:
        return None
    docstr = docstr.lstrip()
    m = re.match(r'%s(\([a-zA-Z0-9_=, ]*\))' % name, docstr)
    if m:
        return m.group(1)
    else:
        return None
