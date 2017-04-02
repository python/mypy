from typing import TypeVar, Optional, List, Any, Generic, Sequence
T = TypeVar('T')

def coroutine(func: T) -> T:
    return func

class bool: ...

class ModuleSpec:
    def __init__(self, name: str, loader: Optional['Loader'], *,
                 origin: str = None, loader_state: Any = None,
                 is_package: bool = None) -> None: ...
    name = ...  # type: str
    loader = ...  # type: Optional[Loader]
    origin = ...  # type: Optional[str]
    submodule_search_locations = ...  # type: Optional[List[str]]
    loader_state = ...  # type: Any
    cached = ...  # type: Optional[str]
    parent = ...  # type: Optional[str]
    has_location = ...  # type: bool

class Loader:
    def load_module(self, fullname: str) -> ModuleType: ...
    def module_repr(self, module: ModuleType) -> str: ...
    def create_module(self, spec: ModuleSpec) -> Optional[ModuleType]: ...
    def exec_module(self, module: ModuleType) -> None: ...

class ModuleType:
    __name__ = ...  # type: str
    __file__ = ...  # type: str
    __loader__ = ...  # type: Optional[Loader]
    __package__ = ...  # type: Optional[str]
    __spec__ = ...  # type: Optional[ModuleSpec]
    def __init__(self, name: str, doc: Optional[str] = ...) -> None: ...
