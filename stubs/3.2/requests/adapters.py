# Stubs for requests.adapters (Python 3)

from typing import Undefined, Any
from . import models
from .packages.urllib3 import poolmanager
from .packages.urllib3 import response
from .packages.urllib3.util import retry
from . import compat
from . import utils
from . import structures
from .packages.urllib3 import exceptions as urllib3_exceptions
from . import cookies
from . import exceptions
from . import auth

Response = models.Response
PoolManager = poolmanager.PoolManager
proxy_from_url = poolmanager.proxy_from_url
HTTPResponse = response.HTTPResponse
Retry = retry.Retry
DEFAULT_CA_BUNDLE_PATH = utils.DEFAULT_CA_BUNDLE_PATH
get_encoding_from_headers = utils.get_encoding_from_headers
prepend_scheme_if_needed = utils.prepend_scheme_if_needed
get_auth_from_url = utils.get_auth_from_url
urldefragauth = utils.urldefragauth
CaseInsensitiveDict = structures.CaseInsensitiveDict
ConnectTimeoutError = urllib3_exceptions.ConnectTimeoutError
MaxRetryError = urllib3_exceptions.MaxRetryError
ProtocolError = urllib3_exceptions.ProtocolError
ReadTimeoutError = urllib3_exceptions.ReadTimeoutError
ResponseError = urllib3_exceptions.ResponseError
extract_cookies_to_jar = cookies.extract_cookies_to_jar
ConnectionError = exceptions.ConnectionError
ConnectTimeout = exceptions.ConnectTimeout
ReadTimeout = exceptions.ReadTimeout
SSLError = exceptions.SSLError
ProxyError = exceptions.ProxyError
RetryError = exceptions.RetryError

DEFAULT_POOLBLOCK = Undefined(Any)
DEFAULT_POOLSIZE = Undefined(Any)
DEFAULT_RETRIES = Undefined(Any)

class BaseAdapter:
    def __init__(self): pass
    # TODO: "request" parameter not actually supported, added to please mypy.
    def send(self, request=None): pass
    def close(self): pass

class HTTPAdapter(BaseAdapter):
    __attrs__ = Undefined(Any)
    max_retries = Undefined(Any)
    config = Undefined(Any)
    proxy_manager = Undefined(Any)
    def __init__(self, pool_connections=Undefined, pool_maxsize=Undefined, max_retries=Undefined,
                 pool_block=Undefined): pass
    poolmanager = Undefined(Any)
    def init_poolmanager(self, connections, maxsize, block=Undefined, **pool_kwargs): pass
    def proxy_manager_for(self, proxy, **proxy_kwargs): pass
    def cert_verify(self, conn, url, verify, cert): pass
    def build_response(self, req, resp): pass
    def get_connection(self, url, proxies=None): pass
    def close(self): pass
    def request_url(self, request, proxies): pass
    def add_headers(self, request, **kwargs): pass
    def proxy_headers(self, proxy): pass
    # TODO: "request" is not actually optional, modified to please mypy.
    def send(self, request=None, stream=False, timeout=None, verify=True, cert=None,
             proxies=None): pass
