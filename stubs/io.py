# Stubs for io

# Based on http://docs.python.org/3.2/library/io.html

# Only a small subset of functionality is included (see below).
# TODO IOBase
# TODO RawIOBase
# TODO BufferedIOBase
# TODO FileIO
# TODO BufferedReader
# TODO BufferedWriter
# TODO BufferedRandom
# TODO BufferedRWPair
# TODO TextIOBase
# TODO TextIOWrapper
# TODO IncrementalNewlineDecoder

class BytesIO(IO):
    void __init__(self, bytes initial_bytes=b''): pass
    # TODO getbuffer
    # TODO see comments in IO for missing functionality
    void close(self): pass
    bool closed(self): pass
    int fileno(self): pass
    void flush(self): pass
    bool isatty(self): pass
    bytes read(self, int n=-1): pass
    bool readable(self): pass
    bytes readline(self, int limit=-1): pass
    bytes[] readlines(self, int hint=-1): pass
    int seek(self, int offset, int whence=0): pass
    bool seekable(self): pass
    int tell(self): pass
    int truncate(self, int size=None): pass
    bool writable(self): pass
    int write(self, bytes s): pass
    void writelines(self, bytes[] lines): pass
    bytes getvalue(self): pass
    str read1(self): pass

    void __enter__(self): pass
    void __exit__(self): pass

class StringIO(TextIO):
    void __init__(self, str initial_value='', str newline=None): pass
    # TODO see comments in IO for missing functionality
    void close(self): pass
    bool closed(self): pass
    int fileno(self): pass
    void flush(self): pass
    bool isatty(self): pass
    str read(self, int n=-1): pass
    bool readable(self): pass
    str readline(self, int limit=-1): pass
    str[] readlines(self, int hint=-1): pass
    int seek(self, int offset, int whence=0): pass
    bool seekable(self): pass
    int tell(self): pass
    int truncate(self, int size=None): pass
    bool writable(self): pass
    int write(self, str s): pass
    void writelines(self, str[] lines): pass
    str getvalue(self): pass

    void __enter__(self): pass
    void __exit__(self): pass
