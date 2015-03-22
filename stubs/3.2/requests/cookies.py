# Stubs for requests.cookies (Python 3)

from typing import Undefined, Any, MutableMapping
#import cookielib
from http import cookiejar as cookielib
import collections
from . import compat

#cookielib = compat.cookielib

class MockRequest:
    type = Undefined(Any)
    def __init__(self, request): pass
    def get_type(self): pass
    def get_host(self): pass
    def get_origin_req_host(self): pass
    def get_full_url(self): pass
    def is_unverifiable(self): pass
    def has_header(self, name): pass
    def get_header(self, name, default=None): pass
    def add_header(self, key, val): pass
    def add_unredirected_header(self, name, value): pass
    def get_new_headers(self): pass
    @property
    def unverifiable(self): pass
    @property
    def origin_req_host(self): pass
    @property
    def host(self): pass

class MockResponse:
    def __init__(self, headers): pass
    def info(self): pass
    def getheaders(self, name): pass

def extract_cookies_to_jar(jar, request, response): pass
def get_cookie_header(jar, request): pass
def remove_cookie_by_name(cookiejar, name, domain=None, path=None): pass

class CookieConflictError(RuntimeError): pass

class RequestsCookieJar(cookielib.CookieJar, MutableMapping):
    def get(self, name, default=None, domain=None, path=None): pass
    def set(self, name, value, **kwargs): pass
    def iterkeys(self): pass
    def keys(self): pass
    def itervalues(self): pass
    def values(self): pass
    def iteritems(self): pass
    def items(self): pass
    def list_domains(self): pass
    def list_paths(self): pass
    def multiple_domains(self): pass
    def get_dict(self, domain=None, path=None): pass
    def __getitem__(self, name): pass
    def __setitem__(self, name, value): pass
    def __delitem__(self, name): pass
    def set_cookie(self, cookie, *args, **kwargs): pass
    def update(self, other): pass
    def copy(self): pass

def create_cookie(name, value, **kwargs): pass
def morsel_to_cookie(morsel): pass
def cookiejar_from_dict(cookie_dict, cookiejar=None, overwrite=True): pass
def merge_cookies(cookiejar, cookies): pass
