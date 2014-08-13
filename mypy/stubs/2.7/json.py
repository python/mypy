from typing import Any, IO

class JSONDecodeError(object):
    def dumps(self, obj: Any) -> str: pass
    def dump(self, obj: Any, fp: IO[str], *args: Any, **kwds: Any) -> None: pass
    def loads(self, s: str) -> Any: pass
    def load(self, fp: IO[str]) -> Any: pass

def dumps(obj: Any) -> str: pass
def dump(obj: Any, fp: IO[str], *args: Any, **kwds: Any) -> None: pass
def loads(s: str) -> Any: pass
def load(fp: IO[str]) -> Any: pass
