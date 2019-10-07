# builtins stub with object.__init_subclass__ and __class_getitem__

class object:
    def __init_subclass__(cls) -> None: pass

    def __class_getitem__(cls, item) -> None: pass

class type: pass

class int: pass
class bool: pass
class str: pass
class function: pass
