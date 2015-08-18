# Stubs for requests.adapters (Python 3)

from typing import Any
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

DEFAULT_POOLBLOCK = ...  # type: Any
DEFAULT_POOLSIZE = ...  # type: Any
DEFAULT_RETRIES = ...  # type: Any

class BaseAdapter:
    def __init__(self): ...
    # TODO: "request" parameter not actually supported, added to please mypy.
    def send(self, request=None): ...
    def close(self): ...

class HTTPAdapter(BaseAdapter):
    __attrs__ = ...  # type: Any
    max_retries = ...  # type: Any
    config = ...  # type: Any
    proxy_manager = ...  # type: Any
    def __init__(self, pool_connections=..., pool_maxsize=..., max_retries=...,
                 pool_block=...): ...
    poolmanager = ...  # type: Any
    def init_poolmanager(self, connections, maxsize, block=..., **pool_kwargs): ...
    def proxy_manager_for(self, proxy, **proxy_kwargs): ...
    def cert_verify(self, conn, url, verify, cert): ...
    def build_response(self, req, resp): ...
    def get_connection(self, url, proxies=None): ...
    def close(self): ...
    def request_url(self, request, proxies): ...
    def add_headers(self, request, **kwargs): ...
    def proxy_headers(self, proxy): ...
    # TODO: "request" is not actually optional, modified to please mypy.
    def send(self, request=None, stream=False, timeout=None, verify=True, cert=None,
             proxies=None): ...
