# Stubs for urllib.request

# NOTE: These are incomplete!

from typing import Any

class BaseHandler(): pass
class HTTPRedirectHandler(BaseHandler): pass
class OpenerDirector(): pass

# TODO args should be types that extend BaseHandler (types, not instances)
def build_opener(*args: Any) -> OpenerDirector: pass
def install_opener(opener: OpenerDirector) -> None: pass
