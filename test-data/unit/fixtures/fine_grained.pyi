# Small stub for fine-grained incremental checking test cases
#
# TODO: Migrate to regular stubs once fine-grained incremental is robust
#       enough to handle them.

class Any: pass

class object:
    def __init__(self) -> None: pass

class type:
    def __init__(self, x: Any) -> None: pass

class int:
    def __add__(self, other: 'int') -> 'int': pass
class str:
    def __add__(self, other: 'str') -> 'str': pass

class float: pass
class bytes: pass
class tuple: pass
class function: pass
class ellipsis: pass
class module: pass
