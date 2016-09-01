from typing import Generic, TypeVar

namedtuple = object()
KT = TypeVar('KT')
KV = TypeVar('KV')

class OrderedDict(Generic[KT, KV]):
    pass
