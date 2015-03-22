# Stubs for enum (Python 3.4)
#
# TODO: This isn't really working yet.

class Enum:
    def __hash__(self): pass
    def name(self): pass
    def value(self): pass

class IntEnum(int, Enum): pass

def unique(enumeration): pass
