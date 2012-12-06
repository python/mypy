# Stubs for builtins


class object:
    void __init__(self): pass
    
    bool __eq__(self, object o): pass
    bool __ne__(self, object o): pass
    
    str __str__(self): pass
    str __repr__(self): pass

    int __hash__(self): pass


# Interfacess


# TODO Hashable, Container, Set etc.


interface int_t: # TODO rename
    int __int__(self)
    
interface float_t: # TODO rename
    float __float__(self)

interface Sized:
    int __len__(self)

interface Iterable<t>:
    Iterator<t> __iter__(self)

interface Iterator<t>(Iterable<t>):
    t __next__(self)

interface Sequence<t>(Sized, Iterable<t>):
    bool __contains__(self, object x)
    t __getitem__(self, int i)
    Sequence<t> __getitem__(self, slice s)

interface Mapping<kt, vt>(Sized, Iterable<kt>):
    vt __getitem__(self, kt k)
    void __setitem__(self, kt k, vt v)
    void __delitem__(self, kt v)
    bool __contains__(self, object o)

    void clear(self)
    Mapping<kt, vt> copy(self)
    vt get(self, kt k)
    vt get(self, kt k, vt default)
    vt pop(self, kt k)
    vt pop(self, kt k, vt default)
    tuple<kt, vt> popitem(self)
    vt setdefault(self, kt k)
    vt setdefault(self, kt k, vt default)
    
    # TODO keyword arguments
    void update(self, Mapping<kt, vt> m)
    void update(self, Iterable<tuple<kt, vt>> m)
    
    # TODO use views for the return values instead
    kt[] keys(self)
    vt[] values(self)
    list<tuple<kt, vt>> items(self)

interface IO:    
    # TODO __enter__ etc.
    # TODO iteration
    # TODO mode
    # TODO name
    # TODO detach
    # TODO readinto
    # TODO read1?
    # TODO peek?
    void close(self)
    bool closed(self)
    int fileno(self)
    void flush(self)
    bool isatty(self)
    # TODO what if n is None?
    bytes read(self, int n=-1)
    bool readable(self)
    bytes readline(self, int limit=-1)
    bytes[] readlines(self, int hint=-1)
    int seek(self, int offset, int whence=0)
    bool seekable(self)
    int tell(self)
    # TODO None should not be compatible with int
    int truncate(self, int size=None)
    bool writable(self)
    # TODO buffer objects
    int write(self, bytes s)
    void writelines(self, bytes[] lines)

    void __enter__(self): pass
    void __exit__(self): pass

interface TextIO:
    # TODO __enter__ etc.
    # TODO iteration
    # TODO buffer?
    # TODO str encoding
    # TODO str errors
    # TODO line_buffering
    # TODO mode
    # TODO name
    # TODO any newlines
    # TODO detach(self)
    void close(self)
    bool closed(self)
    int fileno(self)
    void flush(self)
    bool isatty(self)
    # TODO what if n is None?
    str read(self, int n=-1)
    bool readable(self)
    str readline(self, int limit=-1)
    str[] readlines(self, int hint=-1)
    int seek(self, int offset, int whence=0)
    bool seekable(self)
    int tell(self)
    # TODO is None compatible with int?
    int truncate(self, int size=None)
    bool writable(self)
    # TODO buffer objects
    int write(self, str s)
    void writelines(self, str[] lines)

    void __enter__(self): pass
    void __exit__(self): pass


# Classes


class type:
    void __init__(self, object o): pass


class int(int_t, float_t):
    void __init__(self, int_t x): pass
    void __init__(self, str string, int base): pass

    # Operators
    
    int __add__(self, int x): pass
    float __add__(self, float x): pass
    
    int __sub__(self, int x): pass
    float __sub__(self, float x): pass
    
    int __mul__(self, int x): pass
    float __mul__(self, float x): pass
    str __mul__<t>(self, str s): pass
    t[] __mul__<t>(self, t[] l): pass
    
    int __floordiv__(self, int x): pass
    float __floordiv__(self, float x): pass
    
    int __truediv__(self, int x): pass
    float __truediv__(self, float x): pass
    
    int __mod__(self, int x): pass
    float __mod__(self, float x): pass

    # Return type can be int or float, depending on the value of x.
    any __pow__(self, int x): pass
    float __pow__(self, float x): pass

    int __and__(self, int n): pass
    int __or__(self, int n): pass
    int __xor__(self, int n): pass
    int __lshift__(self, int n): pass
    int __rshift__(self, int n): pass

    int __neg__(self): pass
    int __invert__(self): pass

    bool __eq__(self, object x): pass
    bool __ne__(self, object x): pass
    # TODO precise types for operand
    bool __lt__(self, object x): pass
    bool __le__(self, object x): pass
    bool __gt__(self, object x): pass
    bool __ge__(self, object x): pass

    # Conversions

    str __str__(self): pass
    float __float__(self): pass
    int __int__(self): return self
    
    int __hash__(self): pass

    
class float(float_t, int_t):
    void __init__(self, float_t x): pass

    # Operators
    
    float __add__(self, float x): pass
    float __sub__(self, float x): pass
    float __mul__(self, float x): pass
    float __floordiv__(self, float x): pass
    float __truediv__(self, float x): pass
    float __mod__(self, float x): pass
    float __pow__(self, float x): pass
    
    bool __eq__(self, object x): pass
    bool __ne__(self, object x): pass
    # TODO precise types for operand
    bool __lt__(self, object x): pass
    bool __le__(self, object x): pass
    bool __gt__(self, object x): pass
    bool __ge__(self, object x): pass

    float __neg__(self): pass

    # Conversions

    str __str__(self): pass
    int __int__(self): pass
    float __float__(self): return self
    
    int __hash__(self): pass
    

class str(int_t, float_t, Sequence<str>):
    # TODO maketrans
    
    void __init__(self, object o): pass
    void __init__(self, bytes o, str encoding=None, str errors='strict'): pass

    str capitalize(self): pass
    str center(self, int width, str fillchar=' '): pass
    int count(self, str x): pass
    bytes encode(self, str encoding='utf-8', str errors='strict'): pass
    # TODO tuple suffix; None value for int
    bool endswith(self, str suffix, int start=0, int end=None): pass
    str expandtabs(self, int tabsize=8): pass
    int find(self, str sub, int start=0): pass
    int find(self, str sub, int start, int end): pass
    # TODO keyword args
    str format(self, any *args): pass
    str format_map(self, Mapping<str, any> map): pass
    int index(self, str sub, int start=0): pass
    int index(self, str sub, int start, int end): pass
    bool isalnum(self): pass
    bool isalpha(self): pass
    bool isdecimal(self): pass
    bool isdigit(self): pass
    bool isidentifier(self): pass
    bool islower(self): pass
    bool isnumeric(self): pass
    bool isprintable(self): pass
    bool isspace(self): pass
    bool istitle(self): pass
    bool isupper(self): pass
    str join(self, Iterable<str> iterable): pass
    str ljust(self, int width, str fillchar=' '): pass
    str lower(self): pass
    str lstrip(self, str chars=None): pass
    tuple<str, str, str> partition(self, str sep): pass
    str replace(self, str old, str new, int count=-1): pass
    int rfind(self, str sub, int start=0): pass
    int rfind(self, str sub, int start, int end): pass
    int rindex(self, str sub, int start=0): pass
    int rindex(self, str sub, int start, int end): pass
    str rjust(self, int width, str fillchar=' '): pass
    tuple<str, str, str> rpartition(self, str sep): pass
    str[] rsplit(self, str sep=None, int maxsplit=-1): pass
    str rstrip(self, str chars=None): pass
    str[] split(self, str sep=None, int maxsplit=-1): pass
    str[] splitlines(self, bool keepends=False): pass
    # TODO tuple prefix; None value for int
    bool startswith(self, str prefix, int start=0, int end=None): pass
    str strip(self): pass
    str swapcase(self): pass
    str title(self): pass
    str translate(self, dict<int, any> table): pass
    str upper(self): pass
    str zfill(self, int width): pass
    
    int __len__(self): pass
    
    str __getitem__(self, int i): pass
    str __getitem__(self, slice s): pass

    str __add__(self, str s): pass
    
    str __mul__(self, int n): pass
    str __mod__(self, any *args): pass
    
    bool __eq__(self, object x): pass
    bool __ne__(self, object x): pass
    # TODO precise types for operands
    bool __lt__(self, object x): pass
    bool __le__(self, object x): pass
    bool __gt__(self, object x): pass
    bool __ge__(self, object x): pass

    bool __contains__(self, object s): pass

    Iterator<str> __iter__(self): pass

    str __str__(self): return self
    str __repr__(self): pass
    int __int__(self): pass
    float __float__(self): pass
    
    int __hash__(self): pass
    

class bytes(int_t, float_t, Sequence<int>):
    # TODO fromhex
    # TODO maketrans
    
    void __init__(self, Iterable<int> ints): pass
    void __init__(self, str string, str encoding, str errors='strict'): pass
    void __init__(self, int length): pass
    void __init__(self): pass

    bytes capitalize(self): pass
    bytes center(self, int width, bytes fillchar=b' '): pass
    int count(self, bytes x): pass
    str decode(self, str encoding='utf-8', str errors='strict'): pass
    bool endswith(self, bytes suffix): pass
    bytes expandtabs(self, int tabsize=8): pass
    int find(self, bytes sub, int start=0): pass
    int find(self, bytes sub, int start, int end): pass
    int index(self, bytes sub, int start=0): pass
    int index(self, bytes sub, int start, int end): pass
    bool isalnum(self): pass
    bool isalpha(self): pass
    bool isdigit(self): pass
    bool islower(self): pass
    bool isspace(self): pass
    bool istitle(self): pass
    bool isupper(self): pass
    bytes join(self, Iterable<bytes> iterable): pass
    bytes ljust(self, int width, bytes fillchar=b' '): pass
    bytes lower(self): pass
    bytes lstrip(self, bytes chars=None): pass
    tuple<bytes, bytes, bytes> partition(self, bytes sep): pass
    bytes replace(self, bytes old, bytes new, int count=-1): pass
    int rfind(self, bytes sub, int start=0): pass
    int rfind(self, bytes sub, int start, int end): pass
    int rindex(self, bytes sub, int start=0): pass
    int rindex(self, bytes sub, int start, int end): pass
    bytes rjust(self, int width, bytes fillchar=b' '): pass
    tuple<bytes, bytes, bytes> rpartition(self, bytes sep): pass
    bytes[] rsplit(self, bytes sep=None, int maxsplit=-1): pass
    bytes rstrip(self, bytes chars=None): pass
    bytes[] split(self, bytes sep=None, int maxsplit=-1): pass
    bytes[] splitlines(self, bool keepends=False): pass
    bool startswith(self, bytes prefix): pass
    bytes strip(self): pass
    bytes swapcase(self): pass
    bytes title(self): pass
    bytes translate(self, dict<int, any> table): pass
    bytes upper(self): pass
    bytes zfill(self, int width): pass
    
    int __len__(self): pass
    Iterator<int> __iter__(self): pass
    str __str__(self): pass
    str __repr__(self): pass
    int __int__(self): pass
    float __float__(self): pass
    int __hash__(self): pass
    
    int __getitem__(self, int i): pass
    bytes __getitem__(self, slice s): pass
    bytes __add__(self, bytes s): pass    
    bytes __mul__(self, int n): pass
    bool __contains__(self, object o): pass
    
    bool __eq__(self, object x): pass
    bool __ne__(self, object x): pass
    # TODO precise types for operands
    bool __lt__(self, object x): pass
    bool __le__(self, object x): pass
    bool __gt__(self, object x): pass
    bool __ge__(self, object x): pass


class bytearray(bytes):
    void append(self, int i): pass
    void extend(self, Iterable<int> iterable): pass
    int pop(self): pass
    void insert(self, int index, int object): pass
    void remove(self, int object): pass
    void reverse(self): pass

    bytearray capitalize(self): pass
    bytearray center(self, int width, bytes fillchar=b' '): pass
    bytearray expandtabs(self, int tabsize=8): pass
    bytearray join(self, Iterable<bytes> iterable): pass
    bytearray ljust(self, int width, bytes fillchar=b' '): pass
    bytearray lower(self): pass
    bytearray lstrip(self, bytes chars=None): pass
    tuple<bytearray, bytearray, bytearray> partition(self, bytes sep): pass
    bytearray replace(self, bytes old, bytes new, int count=-1): pass
    bytearray rjust(self, int width, bytes fillchar=b' '): pass
    tuple<bytearray, bytearray, bytearray> rpartition(self, bytes sep): pass
    # rpslit, split, splitlines return bytes[]
    bytearray rstrip(self, bytes chars=None): pass
    bytearray strip(self): pass
    bytearray swapcase(self): pass
    bytearray title(self): pass
    bytearray translate(self, dict<int, any> table): pass
    bytearray upper(self): pass
    bytearray zfill(self, int width): pass

    int __getitem__(self, int i): pass
    bytearray __getitem__(self, slice s): pass
    bytearray __add__(self, bytes s): pass    
    bytearray __mul__(self, int n): pass
    void __setitem__(self, int i, int x): pass
    void __setitem__(self, slice s, Sequence<int> x): pass
    void __delitem__(self, int i): pass
    void __delitem__(self, slice s): pass


class bool:
    void __init__(self, object o): pass
    str __str__(self): pass    


class slice:
    int start
    int step
    int stop
    
    void __init__(self, int start, int stop, int step): pass


class tuple:
    void __init__(self): pass
    void __init__(self, Iterable<any> iterable): pass


class function:
    pass


class list<t>(Sequence<t>):
    void __init__(self): pass
    void __init__(self, Iterable<t> iterable): pass
    
    void append(self, t object): pass
    void extend(self, Iterable<t> iterable): pass
    t pop(self): pass
    int index(self, t object): pass
    int count(self, t object): pass
    void insert(self, int index, t object): pass
    void remove(self, t object): pass
    void reverse(self): pass
    void sort(self, *, func<any(t)> key=None, bool reverse=False): pass
    
    int __len__(self): pass
    Iterator<t> __iter__(self): pass
    str __str__(self): pass
    int __hash__(self): pass
    
    t __getitem__(self, int i): pass
    t[] __getitem__(self, slice s): pass    
    void __setitem__(self, int i, t o): pass
    void __setitem__(self, slice s, Sequence<t> o): pass
    void __delitem__(self, int i): pass
    void __delitem__(self, slice s): pass
    t[] __add__(self, t[] x): pass
    t[] __mul__(self, int n): pass
    bool __contains__(self, object o): pass


class dict<kt, vt>(Mapping<kt, vt>):
    void __init__(self): pass
    void __init__(self, Mapping<kt, vt> map): pass
    void __init__(self, Iterable<tuple<kt, vt>> iterable): pass
    # TODO __init__ keyword args
    
    int __len__(self): pass
    
    vt __getitem__(self, kt k): pass
    void __setitem__(self, kt k, vt v): pass

    void __delitem__(self, kt v): pass

    bool __contains__(self, object o): pass

    Iterator<kt> __iter__(self): pass
    
    void clear(self): pass
    dict<kt, vt> copy(self): pass
    vt get(self, kt k): pass
    vt get(self, kt k, vt default): pass
    vt pop(self, kt k): pass
    vt pop(self, kt k, vt default): pass
    tuple<kt, vt> popitem(self): pass
    vt setdefault(self, kt k): pass
    vt setdefault(self, kt k, vt default): pass
    
    void update(self, Mapping<kt, vt> m): pass
    void update(self, Iterable<tuple<kt, vt>> m): pass

    # TODO use views for the return values instead
    kt[] keys(self): pass
    vt[] values(self): pass
    list<tuple<kt, vt>> items(self): pass

    str __str__(self): pass


class set<t>(Sized, Iterable<t>):
    void __init__(self): pass
    void __init__(self, Iterable<t> iterable): pass
    
    void add(self, t element): pass
    void remove(self, t element): pass
    
    int __len__(self): pass
    bool __contains__(self, object o): pass
    Iterator<t> __iter__(self): pass    
    str __str__(self): pass

    set<t> __and__(self, set<t> s): pass
    set<t> __or__(self, set<t> s): pass
    set<t> __sub__(self, set<t> s): pass
    # TODO more set operations


class frozenset<t>(Sized, Iterable<t>):
    void __init__(self): pass
    void __init__(self, Iterable<t> iterable): pass
    
    int __len__(self): pass
    bool __contains__(self, object o): pass
    Iterator<t> __iter__(self): pass    
    str __str__(self): pass

    # TODO more set operations


class enumerate<t>(Iterator<tuple<int, t>>):
    void __init__(self, Iterable<t> iterable, int start=0): pass
    Iterator<tuple<int, t>> __iter__(self): pass
    tuple<int, t> __next__(self): pass
    # TODO __getattribute__


class range(Sized, Iterable<int>):
    void __init__(self, int stop): pass
    void __init__(self, int start, int stop, int step=1): pass
    
    int count(self, int value): pass
    # None with int
    int index(self, int value, int start=0, int stop=None): pass
    
    int __len__(self): pass
    bool __contains__(self, object o): pass
    Iterator<int> __iter__(self): pass
    int __getitem__(self, int i): pass
    range __getitem__(self, slice s): pass
    str __repr__(self): pass
    # TODO __reversed__


True = 0 == 0
False = 0 == 1

class _NotImplementedType: pass # TODO name of the class
_NotImplementedType NotImplemented


int abs(int n): pass
float abs(float n): pass
bool all(Iterable i): pass
# TODO name clash with 'any' type
#bool any(Iterable i): pass
str ascii(object o): pass
str chr(int code): pass
str[] dir(): pass
str[] dir(object o): pass
tuple<int, int> divmod(int a, int b): pass
tuple<float, float> divmod(float a, float b): pass
Iterator<t> filter<t>(func<any(t)> function, Iterable<t> iterable): pass
str format(object o, str format_spec=''): pass
any getattr(any o, str name): pass
any getattr(any o, str name, any default): pass
bool hasattr(any o, str name): pass
int hash(object o): pass
# TODO __index__
str hex(int i): pass
int id(object o): pass
str input(str prompt=None): pass
Iterator<t> iterable<t>(Iterable<t> iterable): pass
Iterator<t> iterable<t>(func<t()> function, t sentinel): pass
bool isinstance(object o, type t): pass
# TODO perhaps support this
#bool isinstance(object o, Sequence<type> t): pass
bool issubclass(type cls, type classinfo): pass
# TODO perhaps support this
#bool issubclass(type cld, Sequence<type> classinfo): pass
int len(Sized o): pass
# TODO more than two iterables
Iterator<s> map<t1, s>(func<s(t1)> func, Iterable<t1> iter1): pass
Iterator<s> map<t1, t2, s>(func<s(t1, t2)> func,
                         Iterable<t1> iter1,
                         Iterable<t2> iter2): pass
# TODO keyword argument key
t max<t>(Iterable<t> iterable): pass
t max<t>(t arg1, t arg2, t *args): pass
# TODO memoryview
t min<t>(Iterable<t> iterable): pass
t min<t>(t arg1, t arg2, t *args): pass
t next<t>(Iterator<t> i): pass
t next<t>(Iterator<t> i, t default): pass
# TODO __index__
str oct(int i): pass
# TODO return type
any open(str file, str mode='r', str encoding=None, str errors=None,
         str newline=None, bool closefd=True): pass
any open(bytes file, str mode='r', str encoding=None, str errors=None,
         str newline=None, bool closefd=True): pass
any open(int file, str mode='r', str encoding=None, str errors=None,
         str newline=None, bool closefd=True): pass
int ord(str c): pass
int ord(bytes c): pass
void print(object *values, *, str sep=' ', str end='\n',
           TextIO file=None): pass # Actual default for file is sys.stdout
# The return type can be int or float, depending on the value of y.
any pow(int x, int y): pass
any pow(int x, int y, int z): pass
float pow(float x, float y): pass
float pow(float x, float y, float z): pass
# TODO property
# TODO support __reversed__ method
Iterator<t> reversed<t>(Sequence<t> seq): pass
str repr(object o): pass
# Always return a float if ndigits is present.
# TODO support __round__ method
int round(float number): pass
float round(float number, int ndigits): pass
void setattr(any object, str name, any value): pass
t[] sorted<t>(Iterable<t> iterable, *, func<any(t)> key=None,
              bool reverse=False): pass
t sum<t>(Iterable<t> iterable, t start=None): pass
# TODO more than two iterables
Iterator<tuple<t1>> zip<t1>(Iterable<t1> iter1): pass
Iterator<tuple<t1, t2>> zip<t1, t2>(Iterable<t1> iter1,
                                    Iterable<t2> iter2): pass


# Exceptions


class BaseException:
    any args
    
    void __init__(self, any *args): pass

class GeneratorExit(BaseException): pass
class KeyboardInterrupt(BaseException): pass
class SystemExit(BaseException): pass

# Base classes
class Exception(BaseException): pass
class ArithmeticError(Exception): pass
class EnvironmentError(Exception):
    int errno
    str strerror
    str filename # TODO can this be bytes?
class LookupError(Exception): pass
class RuntimeError(Exception): pass
class ValueError(Exception): pass

class AssertionError(Exception): pass
class AttributeError(Exception): pass
class EOFError(Exception): pass
class FloatingPointError(ArithmeticError): pass
class IOError(EnvironmentError): pass
class ImportError(Exception): pass
class IndexError(LookupError): pass
class KeyError(LookupError): pass
class MemoryError(Exception): pass
class NameError(Exception): pass
class NotImplementedError(RuntimeError): pass
class OSError(EnvironmentError): pass
class OverflowError(ArithmeticError): pass
class ReferenceError(Exception): pass
class StopIteration(Exception): pass
class SyntaxError(Exception): pass
class IndentationError(SyntaxError): pass
class TabError(IndentationError): pass
class SystemError(Exception): pass
class TypeError(Exception): pass
class UnboundLocalError(NameError): pass
class UnicodeError(ValueError): pass
class UnicodeDecodeError(UnicodeError): pass
class UnicodeEncodeError(UnicodeError): pass
class UnicodeTranslateError(UnicodeError): pass
class ZeroDivisionError(ArithmeticError): pass

class Warning(Exception): pass
class UserWarning(Warning): pass
class DeprecationWarning(Warning): pass
class SyntaxWarning(Warning): pass
class RuntimeWarning(Warning): pass
class FutureWarning(Warning): pass
class PendingDeprecationWarning(Warning): pass
class ImportWarning(Warning): pass
class UnicodeWarning(Warning): pass
class BytesWarning(Warning): pass
class ResourceWarning(Warning): pass

# TODO
#   VMSError
#   WindowsError
