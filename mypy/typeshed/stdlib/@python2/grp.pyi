import sys
from typing import NamedTuple

if sys.platform != "win32":
    class struct_group(NamedTuple):
        gr_name: str
        gr_passwd: str | None
        gr_gid: int
        gr_mem: list[str]
    def getgrall() -> list[struct_group]: ...
    def getgrgid(id: int) -> struct_group: ...
    def getgrnam(name: str) -> struct_group: ...
