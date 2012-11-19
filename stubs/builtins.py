# Stubs for builtins


class object:
    void __init__(self): pass
    
    bool __eq__(self, object o): pass
    bool __ne__(self, object o): pass
    #bool __lt__(self, object o): pass
    #bool __le__(self, object o): pass
    #bool __gt__(self, object o): pass
    #bool __ge__(self, object o): pass
    
    str __str__(self): pass
    str __repr__(self): pass

    int __hash__(self): pass


# Interfacess


interface int_t:
    int __int__(self)
    
interface float_t:
    float __float__(self)

interface len_t:
    int __len__(self)

interface iterable<t>:
    iterator<t> __iter__(self)

interface iterator<t>(iterable<t>):
    t __next__(self)

interface sequence<t>(len_t, iterable<t>):
    bool __contains__(self, t x)
    t __getitem__(self, int i)
    sequence<t> __getitem__(self, slice s)

interface mapping<kt, vt>(len_t, iterable<kt>):
    vt __getitem__(self, kt k)
    void __setitem__(self, kt k, vt v)
    void __delitem__(self, kt v)
    bool __contains__(self, object o)

    void clear(self)
    mapping<kt, vt> copy(self)
    vt get(self, kt k)
    vt get(self, kt k, vt default)
    vt pop(self, kt k)
    vt pop(self, kt k, vt default)
    tuple<kt, vt> popitem(self)
    vt setdefault(self, kt k)
    vt setdefault(self, kt k, vt default)
    
    # TODO keyword arguments
    void update(self, mapping<kt, vt> m)
    void update(self, iterable<tuple<kt, vt>> m)
    
    # TODO use views for the return values instead
    list<kt> keys(self)
    list<vt> values(self)
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
    list<bytes> readlines(self, int hint=-1)
    int seek(self, int offset, int whence=0)
    bool seekable(self)
    int tell(self)
    # TODO None should not be compatible with int
    int truncate(self, int size=None)
    bool writable(self)
    # TODO buffer objects
    int write(self, bytes s)
    void writelines(self, list<bytes> lines)

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
    list<str> readlines(self, int hint=-1)
    int seek(self, int offset, int whence=0)
    bool seekable(self)
    int tell(self)
    # TODO is None compatible with int?
    int truncate(self, int size=None)
    bool writable(self)
    # TODO buffer objects
    int write(self, str s)
    void writelines(self, list<str> lines)


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
    list<t> __mul__<t>(self, list<t> l): pass
    
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
    

class str(int_t, float_t, sequence<str>):
    # TODO maketrans
    
    void __init__(self, object o): pass
    void __init__(self, bytes o, str encoding=None, str errors='strict'): pass

    str capitalize(self): pass
    str center(self, int width, str fillchar=' '): pass
    int count(self, str x): pass
    bytes encode(self, str encoding='utf-8', str errors='strict'): pass
    bool endswith(self, str suffix): pass
    str expandtabs(self, int tabsize=8): pass
    int find(self, str sub, int start=0): pass
    int find(self, str sub, int start, int end): pass
    # TODO keyword args
    str format(self, any *args): pass
    str format_map(self, mapping<str, any> map): pass
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
    str join(self, iterable<str> iter): pass
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
    list<str> rsplit(self, str sep=None, int maxsplit=-1): pass
    str rstrip(self, str chars=None): pass
    list<str> split(self, str sep=None, int maxsplit=-1): pass
    list<str> splitlines(self, bool keepends=False): pass
    bool startswith(self, str prefix): pass
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

    bool __contains__(self, str s): pass

    iterator<str> __iter__(self): pass

    str __str__(self): return self
    str __repr__(self): pass
    int __int__(self): pass
    float __float__(self): pass
    
    int __hash__(self): pass
    

class bytes(int_t, float_t, sequence<int>):
    void __init__(self, iterable<int> ints): pass
    void __init__(self, str string, str encoding, str errors='strict'): pass
    void __init__(self, int length): pass
    void __init__(self): pass

    # TODO more methods
    bytes strip(self): pass
    bytes upper(self): pass
    bytes lower(self): pass
    # TODO keyword args
    bytes replace(self, bytes old, bytes new, int count=-1): pass
    bytes join(self, iterable<bytes> iter): pass
    list<bytes> split(self, bytes sep=None, int maxsplit=-1): pass
    bool startswith(self, bytes prefix): pass
    bool endswith(self, bytes suffix): pass
    
    int __len__(self): pass
    iterator<int> __iter__(self): pass
    str __str__(self): pass
    str __repr__(self): pass
    int __int__(self): pass
    float __float__(self): pass
    int __hash__(self): pass
    
    int __getitem__(self, int i): pass
    bytes __getitem__(self, slice s): pass
    bytes __add__(self, bytes s): pass    
    bytes __mul__(self, int n): pass
    bool __contains__(self, int i): pass
    # TODO __contains__ with bytes argument
    
    bool __eq__(self, object x): pass
    bool __ne__(self, object x): pass
    # TODO precise types for operands
    bool __lt__(self, object x): pass
    bool __le__(self, object x): pass
    bool __gt__(self, object x): pass
    bool __ge__(self, object x): pass


class bool:
    void __init__(self, object o): pass
    str __str__(self): pass    


class slice:
    int start
    int step
    int stop
    
    void __init__(self, int start, int stop, int step): pass


class tuple:
    pass


class function:
    pass


class list<t>(sequence<t>):
    void __init__(self): pass
    void __init__(self, iterable<t> iter): pass
    
    void append(self, t object): pass
    void extend(self, iterable<t> iter): pass
    t pop(self): pass
    int index(self, t object): pass
    int count(self, t object): pass
    void insert(self, int index, t object): pass
    void remove(self, t object): pass
    void reverse(self): pass
    void sort(self, func<t, any> key=None, bool reverse=False): pass
    
    int __len__(self): pass
    iterator<t> __iter__(self): pass
    str __str__(self): pass
    int __hash__(self): pass
    
    t __getitem__(self, int i): pass
    list<t> __getitem__(self, slice s): pass    
    void __setitem__(self, int i, t o): pass
    void __delitem__(self, int i): pass    
    list<t> __add__(self, list<t> x): pass
    list<t> __mul__(self, int n): pass
    bool __contains__(self, t o): pass


class dict<kt, vt>(mapping<kt, vt>):
    void __init__(self): pass
    void __init__(self, mapping<kt, vt> map): pass
    void __init__(self, iterable<tuple<kt, vt>> iter): pass
    # TODO __init__ keyword args
    
    int __len__(self): pass
    
    vt __getitem__(self, kt k): pass
    void __setitem__(self, kt k, vt v): pass

    void __delitem__(self, kt v): pass

    bool __contains__(self, object o): pass

    iterator<kt> __iter__(self): pass
    
    void clear(self): pass
    dict<kt, vt> copy(self): pass
    vt get(self, kt k): pass
    vt get(self, kt k, vt default): pass
    vt pop(self, kt k): pass
    vt pop(self, kt k, vt default): pass
    tuple<kt, vt> popitem(self): pass
    vt setdefault(self, kt k): pass
    vt setdefault(self, kt k, vt default): pass
    
    void update(self, mapping<kt, vt> m): pass
    void update(self, iterable<tuple<kt, vt>> m): pass

    # TODO use views for the return values instead
    list<kt> keys(self): pass
    list<vt> values(self): pass
    list<tuple<kt, vt>> items(self): pass

    str __str__(self): pass


class set<t>(len_t, iterable<t>):
    void __init__(self): pass
    void __init__(self, iterable<t> iter): pass
    
    void add(self, t element): pass
    void remove(self, t element): pass
    
    int __len__(self): pass
    bool __contains__(self, object o): pass
    iterator<t> __iter__(self): pass    
    str __str__(self): pass


class enumerate<t>(iterator<tuple<int, t>>):
    void __init__(self, iterable<t> iter, int start=0): pass
    iterator<tuple<int, t>> __iter__(self): pass
    tuple<int, t> __next__(self): pass
    # TODO __getattribute__


# TODO frozenset


True = 0 == 0
False = 0 == 1


int abs(int n): pass
float abs(float n): pass
bool all(iterable i): pass
# TODO name clash with 'any' type
#bool any(iterable i): pass
str ascii(object o): pass
str chr(int code): pass
list<str> dir(): pass
list<str> dir(object o): pass
tuple<int, int> divmod(int a, int b): pass
tuple<float, float> divmod(float a, float b): pass
iterator<t> filter<t>(func<t, bool> function, iterable<t> iter): pass
str format(object o, str format_spec=''): pass
any getattr(any o, str name): pass
any getattr(any o, str name, any default): pass
bool hasattr(any o, str name): pass
int hash(object o): pass
# TODO __index__
str hex(int i): pass
int id(object o): pass
str input(str prompt=None): pass
# TODO issubclass
iterator<t> iter<t>(iterable<t> iter): pass
iterator<t> iter<t>(func<t> function, t sentinel): pass
bool isinstance(object o, type t): pass
# TODO support this
#bool isinstance(object o, sequence<type> t): pass
int len(len_t o): pass
# TODO map
# TODO keyword argument key
t max<t>(iterable<t> iter): pass
t max<t>(t arg1, t arg2, t *args): pass
# TODO memoryview
t min<t>(iterable<t> iter): pass
t min<t>(t arg1, t arg2, t *args): pass
t next<t>(iterator<t> i): pass
t next<t>(iterator<t> i, t default): pass
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
void print(object *args): pass
# The return type can be int or float, depending on the value of y.
any pow(int x, int y): pass
any pow(int x, int y, int z): pass
float pow(float x, float y): pass
float pow(float x, float y, float z): pass
# TODO property
# TODO use a range class instead
list<int> range(int hi): pass
list<int> range(int lo, int hi): pass
# TODO support __reversed__ method
iterator<t> reversed<t>(sequence<t> seq): pass
str repr(object o): pass
# Always return a float if ndigits is present.
# TODO support __round__ method
int round(float number): pass
float round(float number, int ndigits): pass
void setattr(any object, str name, any value): pass
list<t> sorted<t>(iterable<t> iiter, func<t, any> key=None,
                  bool reverse=False): pass
list<t> sorted<t>(iterable<t> iter, bool reverse=False): pass
# TODO more general types
int sum(iterable<int> iter, int start=0): pass
float sum(iterable<float> iter, float start=0.0): pass


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
class EnvironmentError(Exception): pass
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

# TODO
#   warnings
#   VMSError
#   WindowsError
