# Stubs for requests.packages.urllib3.connection (Python 3.4)

from typing import Undefined, Any
from . import packages
from http.client import HTTPConnection as _HTTPConnection
# from httplib import HTTPConnection as _HTTPConnection # python 2
from . import exceptions
from .packages import ssl_match_hostname
from .util import ssl_
from . import util
import http.client

class DummyConnection: pass

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

port_by_scheme = Undefined(Any)
RECENT_DATE = Undefined(Any)

class HTTPConnection(_HTTPConnection):
    default_port = Undefined(Any)
    default_socket_options = Undefined(Any)
    is_verified = Undefined(Any)
    source_address = Undefined(Any)
    socket_options = Undefined(Any)
    def __init__(self, *args, **kw): pass
    def connect(self): pass

class HTTPSConnection(HTTPConnection):
    default_port = Undefined(Any)
    key_file = Undefined(Any)
    cert_file = Undefined(Any)
    def __init__(self, host, port=None, key_file=None, cert_file=None, strict=None, timeout=Undefined, **kw): pass
    sock = Undefined(Any)
    def connect(self): pass

class VerifiedHTTPSConnection(HTTPSConnection):
    cert_reqs = Undefined(Any)
    ca_certs = Undefined(Any)
    ssl_version = Undefined(Any)
    assert_fingerprint = Undefined(Any)
    key_file = Undefined(Any)
    cert_file = Undefined(Any)
    assert_hostname = Undefined(Any)
    def set_cert(self, key_file=None, cert_file=None, cert_reqs=None, ca_certs=None, assert_hostname=None, assert_fingerprint=None): pass
    sock = Undefined(Any)
    auto_open = Undefined(Any)
    is_verified = Undefined(Any)
    def connect(self): pass

UnverifiedHTTPSConnection = Undefined(Any)
