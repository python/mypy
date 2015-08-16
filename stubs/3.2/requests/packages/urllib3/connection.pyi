# Stubs for requests.packages.urllib3.connection (Python 3.4)

from typing import Any
from . import packages
from http.client import HTTPConnection as _HTTPConnection
# from httplib import HTTPConnection as _HTTPConnection # python 2
from . import exceptions
from .packages import ssl_match_hostname
from .util import ssl_
from . import util
import http.client

class DummyConnection: ...

import ssl
BaseSSLError = ssl.SSLError
ConnectionError = __builtins__.ConnectionError
HTTPException = http.client.HTTPException

ConnectTimeoutError = exceptions.ConnectTimeoutError
SystemTimeWarning = exceptions.SystemTimeWarning
SecurityWarning = exceptions.SecurityWarning
match_hostname = ssl_match_hostname.match_hostname
resolve_cert_reqs = ssl_.resolve_cert_reqs
resolve_ssl_version = ssl_.resolve_ssl_version
ssl_wrap_socket = ssl_.ssl_wrap_socket
assert_fingerprint = ssl_.assert_fingerprint
connection = util.connection

port_by_scheme = ...  # type: Any
RECENT_DATE = ...  # type: Any

class HTTPConnection(_HTTPConnection):
    default_port = ...  # type: Any
    default_socket_options = ...  # type: Any
    is_verified = ...  # type: Any
    source_address = ...  # type: Any
    socket_options = ...  # type: Any
    def __init__(self, *args, **kw): ...
    def connect(self): ...

class HTTPSConnection(HTTPConnection):
    default_port = ...  # type: Any
    key_file = ...  # type: Any
    cert_file = ...  # type: Any
    def __init__(self, host, port=None, key_file=None, cert_file=None, strict=None, timeout=..., **kw): ...
    sock = ...  # type: Any
    def connect(self): ...

class VerifiedHTTPSConnection(HTTPSConnection):
    cert_reqs = ...  # type: Any
    ca_certs = ...  # type: Any
    ssl_version = ...  # type: Any
    assert_fingerprint = ...  # type: Any
    key_file = ...  # type: Any
    cert_file = ...  # type: Any
    assert_hostname = ...  # type: Any
    def set_cert(self, key_file=None, cert_file=None, cert_reqs=None, ca_certs=None, assert_hostname=None, assert_fingerprint=None): ...
    sock = ...  # type: Any
    auto_open = ...  # type: Any
    is_verified = ...  # type: Any
    def connect(self): ...

UnverifiedHTTPSConnection = ...  # type: Any
