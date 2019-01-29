import contextlib
import io
import re
import sys
import os
import tokenize

from typing import (Optional, Tuple, Sequence, MutableSequence, List, MutableMapping, IO,
                    NamedTuple, Any)
from types import ModuleType

MYPY = False
if MYPY:
    from typing_extensions import Final

# Type Alias for Signatures
Sig = Tuple[str, str]


class ArgSig:
    def __init__(self, name: str, type: Optional[str] = None, default: bool = False):
        self.name = name
        self.type = type
        self.default = default

    def __repr__(self) -> str:
        return "ArgSig(name={}, type={}, default={})".format(repr(self.name), repr(self.type),
                                                            repr(self.default))

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, ArgSig):
            return (self.name == other.name and self.type == other.type and
                    self.default == other.default)
        return False


FunctionSig = NamedTuple('FunctionSig', [
    ('name', str),
    ('args', List[ArgSig]),
    ('ret_type', str)
])


STATE_INIT = 1  # type: Final
STATE_FUNCTION_NAME = 2  # type: Final
STATE_ARGUMENT_LIST = 3  # type: Final
STATE_ARGUMENT_TYPE = 4  # type: Final
STATE_ARGUMENT_DEFAULT = 5  # type: Final
STATE_RETURN_VALUE = 6  # type: Final
STATE_OPEN_BRACKET = 7  # type: Final


class DocStringParser:
    def __init__(self, function_name: str) -> None:
        self.function_name = function_name
        self.state = [STATE_INIT]
        self.accumulator = ""
        self.arg_type = None  # type: Optional[str]
        self.arg_name = ""
        self.arg_default = None  # type: Optional[str]
        self.ret_type = "Any"
        self.found = False
        self.args = []  # type: List[ArgSig]
        self.signatures = []  # type: List[FunctionSig]

    def add_token(self, token: tokenize.TokenInfo) -> None:
        if (token.type == tokenize.NAME and token.string == self.function_name and
                self.state[-1] == STATE_INIT):
            self.state.append(STATE_FUNCTION_NAME)

        elif (token.type == tokenize.OP and token.string == '(' and
              self.state[-1] == STATE_FUNCTION_NAME):
            self.state.pop()
            self.accumulator = ""
            self.found = True
            self.state.append(STATE_ARGUMENT_LIST)

        elif self.state[-1] == STATE_FUNCTION_NAME:
            # reset state, function name not followed by '('
            self.state.pop()

        elif (token.type == tokenize.OP and token.string in ('[', '(', '{') and
              self.state[-1] != STATE_INIT):
            self.accumulator += token.string
            self.state.append(STATE_OPEN_BRACKET)

        elif (token.type == tokenize.OP and token.string in (']', ')', '}') and
              self.state[-1] == STATE_OPEN_BRACKET):
            self.accumulator += token.string
            self.state.pop()

        elif (token.type == tokenize.OP and token.string == ':' and
              self.state[-1] == STATE_ARGUMENT_LIST):
            self.arg_name = self.accumulator
            self.accumulator = ""
            self.state.append(STATE_ARGUMENT_TYPE)

        elif (token.type == tokenize.OP and token.string == '=' and
              self.state[-1] in (STATE_ARGUMENT_LIST, STATE_ARGUMENT_TYPE)):
            if self.state[-1] == STATE_ARGUMENT_TYPE:
                self.arg_type = self.accumulator
                self.state.pop()
            else:
                self.arg_name = self.accumulator
            self.accumulator = ""
            self.state.append(STATE_ARGUMENT_DEFAULT)

        elif (token.type == tokenize.OP and token.string in (',', ')') and
              self.state[-1] in (STATE_ARGUMENT_LIST, STATE_ARGUMENT_DEFAULT,
                                 STATE_ARGUMENT_TYPE)):
            if self.state[-1] == STATE_ARGUMENT_DEFAULT:
                self.arg_default = self.accumulator
                self.state.pop()
            elif self.state[-1] == STATE_ARGUMENT_TYPE:
                self.arg_type = self.accumulator
                self.state.pop()
            elif self.state[-1] == STATE_ARGUMENT_LIST:
                self.arg_name = self.accumulator

            if token.string == ')':
                self.state.pop()
            self.args.append(ArgSig(name=self.arg_name, type=self.arg_type,
                                    default=bool(self.arg_default)))
            self.arg_name = ""
            self.arg_type = None
            self.arg_default = None
            self.accumulator = ""

        elif token.type == tokenize.OP and token.string == '->' and self.state[-1] == STATE_INIT:
            self.accumulator = ""
            self.state.append(STATE_RETURN_VALUE)

        # ENDMAKER is necessary for python 3.4 and 3.5
        elif (token.type in (tokenize.NEWLINE, tokenize.ENDMARKER) and
              self.state[-1] in (STATE_INIT, STATE_RETURN_VALUE)):
            if self.state[-1] == STATE_RETURN_VALUE:
                self.ret_type = self.accumulator
                self.accumulator = ""
                self.state.pop()

            if self.found:
                self.signatures.append(FunctionSig(name=self.function_name, args=self.args,
                                                   ret_type=self.ret_type))
                self.found = False
            self.args = []
            self.ret_type = 'Any'
            # leave state as INIT
        else:
            self.accumulator += token.string

    def get_signatures(self) -> List[FunctionSig]:
        def has_arg(name: str, signature: FunctionSig) -> bool:
            return any(x.name == name for x in signature.args)

        def args_kwargs(signature: FunctionSig) -> bool:
            return has_arg('*args', signature) and has_arg('**kwargs', signature)

        # Move functions with (*args, **kwargs) in their signature to last place
        return list(sorted(self.signatures, key=lambda x: 1 if args_kwargs(x) else 0))


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


def build_signature(fixed: Sequence[str],
                    optional: Sequence[str]) -> str:
    args = []  # type: MutableSequence[str]
    args.extend(fixed)
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


def is_c_module(module: ModuleType) -> bool:
    return ('__file__' not in module.__dict__ or
            os.path.splitext(module.__dict__['__file__'])[-1] in ['.so', '.pyd'])


def write_header(file: IO[str], module_name: Optional[str] = None,
                 pyversion: Tuple[int, int] = (3, 5)) -> None:
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


def infer_sig_from_docstring(docstr: str, name: str) -> Optional[List[FunctionSig]]:
    """Concert function signature to list of TypedFunctionSig

    Looks for function signatures of function in docstring. Returns empty list, when no signature
    is found, one signature in typical case, multiple signatures, if docstring specifies multiple
    signatures for overload functions.

    Arguments:
        * docstr: docstring
        * name: name of function for which signatures are to be found
    """
    if not docstr:
        return None

    state = DocStringParser(name)
    with contextlib.suppress(tokenize.TokenError):
        for token in tokenize.tokenize(io.BytesIO(docstr.encode('utf-8')).readline):
            state.add_token(token)
    return state.get_signatures()


def infer_arg_sig_from_docstring(docstr: str) -> List[ArgSig]:
    """Convert signature in form of "(self: TestClass, arg0: str='ada')" to List[TypedArgList]."""
    ret = infer_sig_from_docstring("stub" + docstr, "stub")
    if ret:
        return ret[0].args

    return []


def infer_prop_type_from_docstring(docstr: str) -> Optional[str]:
    if not docstr:
        return None

    # check for Google/Numpy style docstring type annotation
    # the docstring has the format "<type>: <descriptions>"
    # in the type string, we allow the following characters
    # dot: because something classes are annotated using full path,
    # brackets: to allow type hints like List[int]
    # comma/space: things like Tuple[int, int]
    test_str = r'^([a-zA-Z0-9_, \.\[\]]*): '
    m = re.match(test_str, docstr)
    return m.group(1) if m else None
