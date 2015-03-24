# Stubs for requests.utils (Python 3)

from typing import Undefined, Any
from . import compat
from . import cookies
from . import structures
from . import exceptions

OrderedDict = compat.OrderedDict
RequestsCookieJar = cookies.RequestsCookieJar
cookiejar_from_dict = cookies.cookiejar_from_dict
CaseInsensitiveDict = structures.CaseInsensitiveDict
InvalidURL = exceptions.InvalidURL

NETRC_FILES = Undefined(Any)
DEFAULT_CA_BUNDLE_PATH = Undefined(Any)

def dict_to_sequence(d): pass
def super_len(o): pass
def get_netrc_auth(url): pass
def guess_filename(obj): pass
def from_key_val_list(value): pass
def to_key_val_list(value): pass
def parse_list_header(value): pass
def parse_dict_header(value): pass
def unquote_header_value(value, is_filename=False): pass
def dict_from_cookiejar(cj): pass
def add_dict_to_cookiejar(cj, cookie_dict): pass
def get_encodings_from_content(content): pass
def get_encoding_from_headers(headers): pass
def stream_decode_response_unicode(iterator, r): pass
def iter_slices(string, slice_length): pass
def get_unicode_from_response(r): pass

UNRESERVED_SET = Undefined(Any)

def unquote_unreserved(uri): pass
def requote_uri(uri): pass
def address_in_network(ip, net): pass
def dotted_netmask(mask): pass
def is_ipv4_address(string_ip): pass
def is_valid_cidr(string_network): pass
def should_bypass_proxies(url): pass
def get_environ_proxies(url): pass
def default_user_agent(name=''): pass
def default_headers(): pass
def parse_header_links(value): pass
def guess_json_utf(data): pass
def prepend_scheme_if_needed(url, new_scheme): pass
def get_auth_from_url(url): pass
def to_native_string(string, encoding=''): pass
def urldefragauth(url): pass
