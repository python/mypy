from typing import NamedTuple, Any, Tuple

_int_type = int

class _UUIDFields(NamedTuple('_UUIDFields',
                             [('time_low', int), ('time_mid', int), ('time_hi_version', int), ('clock_seq_hi_variant', int), ('clock_seq_low', int), ('node', int)])):
    time = ... # type: int
    clock_seq = ... # type: int

class UUID:
    def __init__(self, hex: str = None, bytes: str = None, bytes_le: str = None,
                  fields: Tuple[int, int, int, int, int, int] = None, int: int = None, version: Any = None) -> None: ...
    bytes = ... # type: str
    bytes_le = ... # type: str
    fields = ... # type: _UUIDFields
    hex = ... # type: str
    int = ... # type: _int_type
    urn = ... # type: str
    variant = ... # type: _int_type
    version = ... # type: _int_type

RESERVED_NCS = ... # type: int
RFC_4122 = ... # type: int
RESERVED_MICROSOFT = ... # type: int
RESERVED_FUTURE = ... # type: int

def getnode() -> int: ...
def uuid1(node: int = None, clock_seq: int = None) -> UUID: ...
def uuid3(namespace: UUID, name: str) -> UUID: ...
def uuid4() -> UUID: ...
def uuid5(namespace: UUID, name: str) -> UUID: ...

NAMESPACE_DNS = ... # type: str
NAMESPACE_URL = ... # type: str
NAMESPACE_OID = ... # type: str
NAMESPACE_X500 = ... # type: str
