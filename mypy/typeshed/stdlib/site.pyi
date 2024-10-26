import sys
from _typeshed import StrPath
from collections.abc import Iterable

PREFIXES: list[str]
ENABLE_USER_SITE: bool | None
USER_SITE: str | None
USER_BASE: str | None

def main() -> None: ...
def abs_paths() -> None: ...  # undocumented
def addpackage(sitedir: StrPath, name: StrPath, known_paths: set[str] | None) -> set[str] | None: ...  # undocumented
def addsitedir(sitedir: str, known_paths: set[str] | None = None) -> None: ...
def addsitepackages(known_paths: set[str] | None, prefixes: Iterable[str] | None = None) -> set[str] | None: ...  # undocumented
def addusersitepackages(known_paths: set[str] | None) -> set[str] | None: ...  # undocumented
def check_enableusersite() -> bool | None: ...  # undocumented

if sys.version_info >= (3, 13):
    def gethistoryfile() -> str: ...  # undocumented

def enablerlcompleter() -> None: ...  # undocumented

if sys.version_info >= (3, 13):
    def register_readline() -> None: ...  # undocumented

def execsitecustomize() -> None: ...  # undocumented
def execusercustomize() -> None: ...  # undocumented
def getsitepackages(prefixes: Iterable[str] | None = None) -> list[str]: ...
def getuserbase() -> str: ...
def getusersitepackages() -> str: ...
def makepath(*paths: StrPath) -> tuple[str, str]: ...  # undocumented
def removeduppaths() -> set[str]: ...  # undocumented
def setcopyright() -> None: ...  # undocumented
def sethelper() -> None: ...  # undocumented
def setquit() -> None: ...  # undocumented
def venv(known_paths: set[str] | None) -> set[str] | None: ...  # undocumented
