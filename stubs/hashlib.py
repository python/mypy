# Stubs for hashlib

# NOTE: These are incomplete!

interface Hash:
    void update(self, bytes arg)
    bytes digest(self)
    str hexdigest(self)
    Hash copy(self)

Hash md5(bytes arg=None): pass
Hash sha1(bytes arg=None): pass
Hash sha224(bytes arg=None): pass
Hash sha256(bytes arg=None): pass
Hash sha384(bytes arg=None): pass
Hash sha512(bytes arg=None): pass

Hash new(str name, bytes data=None): pass
