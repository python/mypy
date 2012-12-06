# Stubs for tempfile
# Ron Murawski <ron@horizonchess.com>

# based on http://docs.python.org/3.3/library/tempfile.html

# global variables
str tempdir
str template

# TODO text files

# function stubs 
IO TemporaryFile(
            str mode='w+b', int buffering=None, str encoding=None, 
            str newline=None, str suffix='', str prefix='tmp', str dir=None):
    pass
IO NamedTemporaryFile(
            str mode='w+b', int buffering=None, str encoding=None, 
            str newline=None, str suffix='', str prefix='tmp', str dir=None, 
            delete=True): 
    pass
IO SpooledTemporaryFile(
            int max_size=0, str mode='w+b', int buffering=None, 
            str encoding=None, str  newline=None, str suffix='', 
            str prefix='tmp', str dir=None): 
    pass

class TemporaryDirectory:
    str name    
    void __init__(self, str suffix='', str prefix='tmp', str dir=None): pass
    void cleanup(self): pass
    void __enter__(self): pass
    void __exit__(self): pass
    
tuple<IO, str> mkstemp(
            str suffix='', str prefix='tmp', str dir=None, bool text=False):
    pass
str mkdtemp(str suffix='', str prefix='tmp', str dir=None): pass
str mktemp(str suffix='', str prefix='tmp', str dir=None): pass
str gettempdir(): pass
str gettempprefix(): pass
