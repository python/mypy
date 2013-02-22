# TODO these are incomplete

class TarError(Exception): pass

TarFile open(str name, str mode='r', any fileobj=None, int bufsize=10240,
             **kwargs): pass

class TarFile:
    TarInfo getmember(self, str name): pass
    TarInfo[] getmembers(self): pass
    void extractall(self, str path=".", TarInfo[] members=None): pass
    void extract(self, str member, str path="", bool set_attrs=True): pass
    void extract(self, TarInfo member, str path="", bool set_attrs=True): pass
    void add(self, str name, str arcname=None, bool recursive=True,
             func<bool(str)> exclude=None, *,
             func<TarFile(TarFile)> filter=None): pass
    void close(self): pass

class TarInfo:
    str name
    int size
