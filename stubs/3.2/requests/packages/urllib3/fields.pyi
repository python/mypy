# Stubs for requests.packages.urllib3.fields (Python 3.4)

from typing import Undefined, Any
from . import packages

def guess_content_type(filename, default=''): pass
def format_header_param(name, value): pass

class RequestField:
    data = Undefined(Any)
    headers = Undefined(Any)
    def __init__(self, name, data, filename=None, headers=None): pass
    @classmethod
    def from_tuples(cls, fieldname, value): pass
    def render_headers(self): pass
    def make_multipart(self, content_disposition=None, content_type=None, content_location=None): pass
