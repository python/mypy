# Stubs for requests.exceptions (Python 3)

from typing import Undefined, Any
from .packages.urllib3.exceptions import HTTPError as BaseHTTPError

class RequestException(IOError):
    response = Undefined(Any)
    request = Undefined(Any)
    def __init__(self, *args, **kwargs): pass

class HTTPError(RequestException): pass
class ConnectionError(RequestException): pass
class ProxyError(ConnectionError): pass
class SSLError(ConnectionError): pass
class Timeout(RequestException): pass
class ConnectTimeout(ConnectionError, Timeout): pass
class ReadTimeout(Timeout): pass
class URLRequired(RequestException): pass
class TooManyRedirects(RequestException): pass
class MissingSchema(RequestException, ValueError): pass
class InvalidSchema(RequestException, ValueError): pass
class InvalidURL(RequestException, ValueError): pass
class ChunkedEncodingError(RequestException): pass
class ContentDecodingError(RequestException, BaseHTTPError): pass
class StreamConsumedError(RequestException, TypeError): pass
class RetryError(RequestException): pass
