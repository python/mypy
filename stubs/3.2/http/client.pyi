# Stubs for http.client (Python 3.4)

from typing import Any, Dict
import email.message
import io

responses = ...  # type: Dict[int, str]

class HTTPMessage(email.message.Message):
    def getallmatchingheaders(self, name): pass

class HTTPResponse(io.RawIOBase):
    fp = ...  # type: Any
    debuglevel = ...  # type: Any
    headers = ...  # type: Any
    version = ...  # type: Any
    status = ...  # type: Any
    reason = ...  # type: Any
    chunked = ...  # type: Any
    chunk_left = ...  # type: Any
    length = ...  # type: Any
    will_close = ...  # type: Any
    def __init__(self, sock, debuglevel=0, method=None, url=None): pass
    code = ...  # type: Any
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
    response_class = ...  # type: Any
    default_port = ...  # type: Any
    auto_open = ...  # type: Any
    debuglevel = ...  # type: Any
    mss = ...  # type: Any
    timeout = ...  # type: Any
    source_address = ...  # type: Any
    sock = ...  # type: Any
    def __init__(self, host, port=None, timeout=..., source_address=None): pass
    def set_tunnel(self, host, port=None, headers=None): pass
    def set_debuglevel(self, level): pass
    def connect(self): pass
    def close(self): pass
    def send(self, data): pass
    def putrequest(self, method, url, skip_host=0, skip_accept_encoding=0): pass
    def putheader(self, header, *values): pass
    def endheaders(self, message_body=None): pass
    def request(self, method, url, body=None, headers=...): pass
    def getresponse(self): pass

class HTTPSConnection(HTTPConnection):
    default_port = ...  # type: Any
    key_file = ...  # type: Any
    cert_file = ...  # type: Any
    def __init__(self, host, port=None, key_file=None, cert_file=None, timeout=...,
                 source_address=None, *, context=None, check_hostname=None): pass
    sock = ...  # type: Any
    def connect(self): pass

class HTTPException(Exception): pass
class NotConnected(HTTPException): pass
class InvalidURL(HTTPException): pass

class UnknownProtocol(HTTPException):
    args = ...  # type: Any
    version = ...  # type: Any
    def __init__(self, version): pass

class UnknownTransferEncoding(HTTPException): pass
class UnimplementedFileMode(HTTPException): pass

class IncompleteRead(HTTPException):
    args = ...  # type: Any
    partial = ...  # type: Any
    expected = ...  # type: Any
    def __init__(self, partial, expected=None): pass

class ImproperConnectionState(HTTPException): pass
class CannotSendRequest(ImproperConnectionState): pass
class CannotSendHeader(ImproperConnectionState): pass
class ResponseNotReady(ImproperConnectionState): pass

class BadStatusLine(HTTPException):
    args = ...  # type: Any
    line = ...  # type: Any
    def __init__(self, line): pass

class LineTooLong(HTTPException):
    def __init__(self, line_type): pass

error = HTTPException
