# Stubs for sys
# Ron Murawski <ron@horizonchess.com>

# based on http://docs.python.org/2.7/library/sys.html

# Partially adapted to Python 2.7 by Jukka Lehtosalo.

from typing import (
    List, Sequence, Any, Dict, Tuple, BinaryIO, overload
)

# ----- sys variables -----
abiflags = ''
argv = None  # type: List[str]
byteorder = ''
builtin_module_names = None  # type: Sequence[str] # actually a tuple of strings
copyright = ''
dllhandle = 0  # Windows only
dont_write_bytecode = False
__displayhook__ = None  # type: Any # contains the original value of displayhook
__excepthook__ = None  # type: Any  # contains the original value of excepthook
exec_prefix = ''
executable = ''
float_repr_style = ''
hexversion = 0  # this is a 32-bit int
last_type = None  # type: Any
last_value = None  # type: Any
last_traceback = None  # type: Any
maxsize = 0
maxunicode = 0
meta_path = None  # type: List[Any]
modules = None  # type: Dict[str, Any]
path = None  # type: List[str]
path_hooks = None  # type: List[Any] # TODO precise type; function, path to finder
path_importer_cache = None  # type: Dict[str, Any] # TODO precise type
platform = ''
prefix = ''
ps1 = ''
ps2 = ''
stdin = None  # type: BinaryIO
stdout = None  # type: BinaryIO
stderr = None  # type: BinaryIO
__stdin__ = None  # type: BinaryIO
__stdout__ = None  # type: BinaryIO
__stderr__ = None  # type: BinaryIO
subversion = None  # type: Tuple[str, str, str]
tracebacklimit = 0
version = ''
api_version = 0
warnoptions = None  # type: Any
#  Each entry is a tuple of the form (action, message, category, module,
#    lineno)
winver = ''  # Windows only
_xoptions = None  # type: Dict[Any, Any]

flags = None  # type: _flags
class _flags:
    debug = 0
    division_warning = 0
    inspect = 0
    interactive = 0
    optimize = 0
    dont_write_bytecode = 0
    no_user_site = 0
    no_site = 0
    ignore_environment = 0
    verbose = 0
    bytes_warning = 0
    quiet = 0
    hash_randomization = 0

float_info = None  # type: _float_info
class _float_info:
    epsilon = 0.0   # DBL_EPSILON
    dig = 0         # DBL_DIG
    mant_dig = 0    # DBL_MANT_DIG
    max = 0.0       # DBL_MAX
    max_exp = 0     # DBL_MAX_EXP
    max_10_exp = 0  # DBL_MAX_10_EXP
    min = 0.0       # DBL_MIN
    min_exp = 0     # DBL_MIN_EXP
    min_10_exp = 0  # DBL_MIN_10_EXP
    radix = 0       # FLT_RADIX
    rounds = 0      # FLT_ROUNDS

hash_info = None  # type: _hash_info
class _hash_info:
    width = 0    # width in bits used for hash values
    modulus = 0  # prime modulus P used for numeric hash scheme
    inf = 0      # hash value returned for a positive infinity
    nan = 0      # hash value returned for a nan
    imag = 0     # multiplier used for the imaginary part of a complex number

int_info = None  # type: _int_info
class _int_info:
    bits_per_digit = 0  # number of bits held in each digit. Python integers
                        # are stored internally in
                        # base 2**int_info.bits_per_digit
    sizeof_digit = 0    # size in bytes of C type used to represent a digit

class _version_info(Tuple[int, int, int, str, int]):
    major = 0
    minor = 0
    micro = 0
    releaselevel = ''
    serial = 0
version_info = None  # type: _version_info

# ----- sys function stubs -----
def call_tracing(fn: Any, args: Any) -> object: ...
def _clear_type_cache() -> None: ...
def _current_frames() -> Dict[int, Any]: ...
def displayhook(value: int) -> None: ...  # value might be None
def excepthook(type_: type, value: BaseException, traceback: Any) -> None:
    # TODO traceback type
    ...
def exc_info() -> Tuple[type, Any, Any]: ... # see above
def exit(arg: int = 0) -> None: ...  # arg might be None
def getcheckinterval() -> int: ...  # deprecated
def getdefaultencoding() -> str: ...
def getdlopenflags() -> int: ...
def getfilesystemencoding() -> str: ...
def getrefcount(object) -> int: ...
def getrecursionlimit() -> int: ...

@overload
def getsizeof(obj: object) -> int: ...
@overload
def getsizeof(obj: object, default: int) -> int: ...

def getswitchinterval() -> float: ...

@overload
def _getframe() -> Any: ...
@overload
def _getframe(depth: int) -> Any: ...

def getprofile() -> Any: ... # TODO return type
def gettrace() -> Any: ... # TODO return
def getwindowsversion() -> Any: ...  # TODO return type
def intern(string: str) -> str: ...
def setcheckinterval(interval: int) -> None: ...  # deprecated
def setdlopenflags(n: int) -> None: ...
def setprofile(profilefunc: Any) -> None: ... # TODO type
def setrecursionlimit(limit: int) -> None: ...
def setswitchinterval(interval: float) -> None: ...
def settrace(tracefunc: Any) -> None: ... # TODO type
# Trace functions should have three arguments: frame, event, and arg. frame
# is the current stack frame. event is a string: 'call', 'line', 'return',
# 'exception', 'c_call', 'c_return', or 'c_exception'. arg depends on the
# event type.
def settscdump(on_flag: bool) -> None: ...
