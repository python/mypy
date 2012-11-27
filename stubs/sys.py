# Stubs for sys
# Ron Murawski <ron@horizonchess.com>

# based on http://docs.python.org/3.2/library/sys.html

# ----- sys variables -----
str abiflags
str[] argv
str byteorder
Sequence<str> builtin_module_names  # actually a tuple of strings
str copyright
#int dllhandle  # Windows only
bool dont_write_bytecode
any __displayhook__  # contains the original value of displayhook
any __excepthook__  # contains the original value of excepthook
str exec_prefix
str executable
str float_repr_style
int hexversion  # this is a 32-bit int
any last_type
any last_value
any last_traceback
int maxsize
int maxunicode
any[] meta_path
dict<int, any> modules
str[] path
any[] path_hooks # TODO precise type; callable from path to finder
dict<str, any> path_importer_cache # TODO precise type
str platform
str prefix
str ps1
str ps2
TextIO stdin
TextIO stdout
TextIO stderr
TextIO __stdin__
TextIO __stdout__
TextIO __stderr__
tuple<str, str, str> subversion  # deprecated and removed in Python 3.3
int tracebacklimit
str version
int api_version 
any warnoptions
#  Each entry is a tuple of the form (action, message, category, module,
#    lineno)
#str winver  # Windows only
dict<any, any> _xoptions

_flags flags
class _flags:
    int debug
    int division_warning
    int inspect
    int interactive
    int optimize
    int dont_write_bytecode
    int no_user_site
    int no_site
    int ignore_environment
    int verbose
    int bytes_warning
    int quiet
    int hash_randomization

_float_info float_info
class _float_info:
    float epsilon   # DBL_EPSILON
    int dig         # DBL_DIG
    int mant_dig    # DBL_MANT_DIG
    float max       # DBL_MAX
    int max_exp     # DBL_MAX_EXP
    int max_10_exp  # DBL_MAX_10_EXP
    float min       # DBL_MIN
    int min_exp     # DBL_MIN_EXP
    int min_10_exp  # DBL_MIN_10_EXP
    int radix       # FLT_RADIX
    int rounds      # FLT_ROUNDS

_hash_info hash_info
class _hash_info:
    int width    # width in bits used for hash values
    int modulus  # prime modulus P used for numeric hash scheme
    int inf      # hash value returned for a positive infinity
    int nan      # hash value returned for a nan
    int imag     # multiplier used for the imaginary part of a complex number

_int_info int_info
class _int_info:
    int bits_per_digit  # number of bits held in each digit. Python integers 
                        # are stored internally in 
                        # base 2**int_info.bits_per_digit
    int sizeof_digit    # size in bytes of C type used to represent a digit

_version_info version_info
class _version_info:
    int major
    int minor
    int micro
    str releaselevel
    int serial


# ----- sys function stubs -----
object call_tracing(any fn, any args): pass
void _clear_type_cache(): pass
dict<int, any> _current_frames(): pass
void displayhook(int value): pass  # value might be None
void excepthook(type type_, BaseException value, any traceback):
    # TODO traceback type
    pass
tuple<type, any, any> exc_info(): pass # see above
void exit(int arg=0): pass  # arg might be None
int getcheckinterval(): pass  # deprecated
str getdefaultencoding(): pass
#int getdlopenflags(): pass  # Unix only
str getfilesystemencoding(): pass  # cannot return None
#int getrefcount(object): pass  # no ref counts in MyPy!
int getrecursionlimit(): pass
int getsizeof(object obj): pass
int getsizeof(object obj, int default): pass
float getswitchinterval(): pass
any _getframe(): pass
any _getframe(int depth): pass
any getprofile(): pass # TODO return type
any gettrace(): pass # TODO return
#list<int> getwindowsversion(): pass  # Windows only, return type???
str intern(str string): pass
void setcheckinterval(int interval): pass  # deprecated
#setdlopenflags(int n): pass  # Linux only
void setprofile(any profilefunc): pass # TODO type
void setrecursionlimit(int limit): pass
void setswitchinterval(float interval): pass
void settrace(any tracefunc): pass # TODO type
# Trace functions should have three arguments: frame, event, and arg. frame 
# is the current stack frame. event is a string: 'call', 'line', 'return', 
# 'exception', 'c_call', 'c_return', or 'c_exception'. arg depends on the 
# event type.
void settscdump(bool on_flag): pass
