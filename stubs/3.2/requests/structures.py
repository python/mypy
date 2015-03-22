# Stubs for requests.structures (Python 3)

from typing import Undefined, Any
import collections

class CaseInsensitiveDict(collections.MutableMapping):
    def __init__(self, data=None, **kwargs): pass
    def __setitem__(self, key, value): pass
    def __getitem__(self, key): pass
    def __delitem__(self, key): pass
    def __iter__(self): pass
    def __len__(self): pass
    def lower_items(self): pass
    def __eq__(self, other): pass
    def copy(self): pass

class LookupDict(dict):
    name = Undefined(Any)
    def __init__(self, name=None): pass
    def __getitem__(self, key): pass
    def get(self, key, default=None): pass
