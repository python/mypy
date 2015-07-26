# Stubs for uuid

from typing import Tuple

Int = __builtins__.int
Bytes = __builtins__.bytes
FieldsType = Tuple[Int, Int, Int, Int, Int, Int]

class UUID:
    def __init__(self, hex: str=None, bytes: Bytes=None, bytes_le: Bytes=None, fields: FieldsType=None, int: Int=None, version: Int=None) -> None: pass

    @property
    def bytes(self) -> Bytes: pass

    @property
    def bytes_le(self) -> Bytes: pass

    @property
    def clock_seq(self) -> Int: pass

    @property
    def clock_seq_hi_variant(self) -> Int: pass

    @property
    def clock_seq_low(self) -> Int: pass

    @property
    def fields(self) -> FieldsType: pass

    @property
    def hex(self) -> str: pass

    @property
    def int(self) -> Int: pass

    @property
    def node(self) -> Int: pass

    @property
    def time(self) -> Int: pass

    @property
    def time_hi_version(self) -> Int: pass

    @property
    def time_low(self) -> Int: pass

    @property
    def time_mid(self) -> Int: pass

    @property
    def urn(self) -> str: pass

    @property
    def variant(self) -> str: pass

    @property
    def version(self) -> str: pass

def getnode() -> Int: pass
def uuid1(node: Int=None, clock_seq: Int=None) -> UUID: pass
def uuid3(namespace: UUID, name: str) -> UUID: pass
def uuid4() -> UUID: pass
def uuid5(namespace: UUID, name: str) -> UUID: pass

NAMESPACE_DNS = ... # type: UUID
NAMESPACE_URL = ... # type: UUID
NAMESPACE_OID = ... # type: UUID
NAMESPACE_X500 = ... # type: UUID
RESERVED_NCS = ... # type: str
RFC_4122 = ... # type: str
RESERVED_MICROSOFT = ... # type: str
RESERVED_FUTURE = ... # type: str
