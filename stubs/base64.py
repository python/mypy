# Stubs for base64

# Based on http://docs.python.org/3.2/library/base64.html

bytes b64encode(bytes s, bytes altchars=None): pass
bytes b64decode(bytes s, bytes altchars=None, bool validate=False): pass
bytes standard_b64encode(bytes s): pass
bytes standard_b64decode(bytes s): pass
bytes urlsafe_b64encode(bytes s): pass
bytes urlsafe_b64decode(bytes s): pass
bytes b32encode(bytes s): pass
bytes b32decode(bytes s, bool casefold=False, bytes map01=None): pass
bytes b16encode(bytes s): pass
bytes b16decode(bytes s, bool casefold=False): pass

void decode(IO input, IO output): pass
bytes decodebytes(bytes s): pass
bytes decodestring(bytes s): pass
void encode(IO input, IO output): pass
bytes encodebytes(bytes s): pass
bytes encodestring(bytes s): pass
