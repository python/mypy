# Stubs for http.client (Python 3.4)

from typing import Undefined, Any, Dict
import email.message
import io

responses = Undefined(Dict[int, str])

class HTTPMessage(email.message.Message):
    def getallmatchingheaders(self, name): pass

class HTTPResponse(io.RawIOBase):
    fp = Undefined(Any)
    debuglevel = Undefined(Any)
    headers = Undefined(Any)
    version = Undefined(Any)
    status = Undefined(Any)
    reason = Undefined(Any)
    chunked = Undefined(Any)
    chunk_left = Undefined(Any)
    length = Undefined(Any)
    will_close = Undefined(Any)
    def __init__(self, sock, debuglevel=0, method=None, url=None): pass
    code = Undefined(Any)
    def begin(self): pass
    def close(self): pass
    def flush(self): pass
    def readable(self): pass
    def isclosed(self): pass
    def read(self, amt=None): pass
    def readinto(self, b): pass
    def fileno(self): pass
    def getheader(self, name, default=None): pass
    def getheaders(self): pass
    def __iter__(self): pass
    def info(self): pass
    def geturl(self): pass
    def getcode(self): pass

class HTTPConnection:
    response_class = Undefined(Any)
    default_port = Undefined(Any)
    auto_open = Undefined(Any)
    debuglevel = Undefined(Any)
    mss = Undefined(Any)
    timeout = Undefined(Any)
    source_address = Undefined(Any)
    sock = Undefined(Any)
    def __init__(self, host, port=None, timeout=Undefined, source_address=None): pass
    def set_tunnel(self, host, port=None, headers=None): pass
    def set_debuglevel(self, level): pass
    def connect(self): pass
    def close(self): pass
    def send(self, data): pass
    def putrequest(self, method, url, skip_host=0, skip_accept_encoding=0): pass
    def putheader(self, header, *values): pass
    def endheaders(self, message_body=None): pass
    def request(self, method, url, body=None, headers=Undefined): pass
    def getresponse(self): pass

class HTTPSConnection(HTTPConnection):
    default_port = Undefined(Any)
    key_file = Undefined(Any)
    cert_file = Undefined(Any)
    def __init__(self, host, port=None, key_file=None, cert_file=None, timeout=Undefined,
                 source_address=None, *, context=None, check_hostname=None): pass
    sock = Undefined(Any)
    def connect(self): pass

class HTTPException(Exception): pass
class NotConnected(HTTPException): pass
class InvalidURL(HTTPException): pass

class UnknownProtocol(HTTPException):
    args = Undefined(Any)
    version = Undefined(Any)
    def __init__(self, version): pass

class UnknownTransferEncoding(HTTPException): pass
class UnimplementedFileMode(HTTPException): pass

class IncompleteRead(HTTPException):
    args = Undefined(Any)
    partial = Undefined(Any)
    expected = Undefined(Any)
    def __init__(self, partial, expected=None): pass

class ImproperConnectionState(HTTPException): pass
class CannotSendRequest(ImproperConnectionState): pass
class CannotSendHeader(ImproperConnectionState): pass
class ResponseNotReady(ImproperConnectionState): pass

class BadStatusLine(HTTPException):
    args = Undefined(Any)
    line = Undefined(Any)
    def __init__(self, line): pass

class LineTooLong(HTTPException):
    def __init__(self, line_type): pass

error = HTTPException
