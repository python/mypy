# TODO these are incomplete

from typing import Any, List, overload, Function

class TarError(Exception): pass

class TarInfo:
    name = ''
    size = 0
    uid = 0
    gid = 0

class TarFile:
    def getmember(self, name: str) -> TarInfo: pass
    def getmembers(self) -> List[TarInfo]: pass
    def getnames(self) -> List[str]: pass
    def extractall(self, path: str = ".",
                   members: List[TarInfo] = None) -> None: pass

    @overload
    def extract(self, member: str, path: str = "",
                set_attrs: bool = True) -> None: pass
    @overload
    def extract(self, member: TarInfo, path: str = "",
                set_attrs: bool = True) -> None: pass

    def add(self, name: str, arcname: str = None, recursive: bool = True,
            exclude: Function[[str], bool] = None, *,
            filter: 'Function[[TarFile], TarFile]' = None) -> None: pass
    def close(self) -> None: pass

def open(name: str, mode: str = 'r', fileobj: Any = None, bufsize: int = 10240,
         **kwargs) -> TarFile: pass
