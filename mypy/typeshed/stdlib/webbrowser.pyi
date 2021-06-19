import sys
from typing import Callable, List, Optional, Sequence, Union

class Error(Exception): ...

if sys.version_info >= (3, 7):
    def register(
        name: str, klass: Optional[Callable[[], BaseBrowser]], instance: Optional[BaseBrowser] = ..., *, preferred: bool = ...
    ) -> None: ...

else:
    def register(
        name: str, klass: Optional[Callable[[], BaseBrowser]], instance: Optional[BaseBrowser] = ..., update_tryorder: int = ...
    ) -> None: ...

def get(using: Optional[str] = ...) -> BaseBrowser: ...
def open(url: str, new: int = ..., autoraise: bool = ...) -> bool: ...
def open_new(url: str) -> bool: ...
def open_new_tab(url: str) -> bool: ...

class BaseBrowser:
    args: List[str]
    name: str
    basename: str
    def __init__(self, name: str = ...) -> None: ...
    def open(self, url: str, new: int = ..., autoraise: bool = ...) -> bool: ...
    def open_new(self, url: str) -> bool: ...
    def open_new_tab(self, url: str) -> bool: ...

class GenericBrowser(BaseBrowser):
    args: List[str]
    name: str
    basename: str
    def __init__(self, name: Union[str, Sequence[str]]) -> None: ...
    def open(self, url: str, new: int = ..., autoraise: bool = ...) -> bool: ...

class BackgroundBrowser(GenericBrowser):
    def open(self, url: str, new: int = ..., autoraise: bool = ...) -> bool: ...

class UnixBrowser(BaseBrowser):
    raise_opts: Optional[List[str]]
    background: bool
    redirect_stdout: bool
    remote_args: List[str]
    remote_action: str
    remote_action_newwin: str
    remote_action_newtab: str
    def open(self, url: str, new: int = ..., autoraise: bool = ...) -> bool: ...

class Mozilla(UnixBrowser):
    remote_args: List[str]
    remote_action: str
    remote_action_newwin: str
    remote_action_newtab: str
    background: bool

class Galeon(UnixBrowser):
    raise_opts: List[str]
    remote_args: List[str]
    remote_action: str
    remote_action_newwin: str
    background: bool

class Chrome(UnixBrowser):
    remote_args: List[str]
    remote_action: str
    remote_action_newwin: str
    remote_action_newtab: str
    background: bool

class Opera(UnixBrowser):
    remote_args: List[str]
    remote_action: str
    remote_action_newwin: str
    remote_action_newtab: str
    background: bool

class Elinks(UnixBrowser):
    remote_args: List[str]
    remote_action: str
    remote_action_newwin: str
    remote_action_newtab: str
    background: bool
    redirect_stdout: bool

class Konqueror(BaseBrowser):
    def open(self, url: str, new: int = ..., autoraise: bool = ...) -> bool: ...

class Grail(BaseBrowser):
    def open(self, url: str, new: int = ..., autoraise: bool = ...) -> bool: ...

if sys.platform == "win32":
    class WindowsDefault(BaseBrowser):
        def open(self, url: str, new: int = ..., autoraise: bool = ...) -> bool: ...

if sys.platform == "darwin":
    class MacOSX(BaseBrowser):
        name: str
        def __init__(self, name: str) -> None: ...
        def open(self, url: str, new: int = ..., autoraise: bool = ...) -> bool: ...
    class MacOSXOSAScript(BaseBrowser):
        def __init__(self, name: str) -> None: ...
        def open(self, url: str, new: int = ..., autoraise: bool = ...) -> bool: ...
