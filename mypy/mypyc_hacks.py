"""Stuff that we had to move out of its right place because of mypyc limitations."""

# Moved from util.py, because it inherits from Exception
class DecodeError(Exception):
    """Exception raised when a file cannot be decoded due to an unknown encoding type.

    Essentially a wrapper for the LookupError raised by `bytearray.decode`
    """


# Moved from types.py, because it inherits from Enum, which uses a
# metaclass in a nontrivial way.
from enum import Enum


class TypeOfAny(Enum):
    """
    This class describes different types of Any. Each 'Any' can be of only one type at a time.
    """
    # Was this Any type was inferred without a type annotation?
    unannotated = 'unannotated'
    # Does this Any come from an explicit type annotation?
    explicit = 'explicit'
    # Does this come from an unfollowed import? See --disallow-any-unimported option
    from_unimported_type = 'from_unimported_type'
    # Does this Any type come from omitted generics?
    from_omitted_generics = 'from_omitted_generics'
    # Does this Any come from an error?
    from_error = 'from_error'
    # Is this a type that can't be represented in mypy's type system? For instance, type of
    # call to NewType...). Even though these types aren't real Anys, we treat them as such.
    # Also used for variables named '_'.
    special_form = 'special_form'
    # Does this Any come from interaction with another Any?
    from_another_any = 'from_another_any'
    # Does this Any come from an implementation limitation/bug?
    implementation_artifact = 'implementation_artifact'


# Moved from nodes.py, because it inherits from dict
from typing import Dict, List, Any

JsonDict = Dict[str, Any]

MYPY = False
if MYPY:
    from mypy.nodes import SymbolTableNode

class SymbolTable(Dict[str, 'SymbolTableNode']):
    def __str__(self) -> str:
        from mypy.nodes import implicit_module_attrs, SymbolTableNode

        a = []  # type: List[str]
        for key, value in self.items():
            # Filter out the implicit import of builtins.
            if isinstance(value, SymbolTableNode):
                if (value.fullname != 'builtins' and
                        (value.fullname or '').split('.')[-1] not in
                        implicit_module_attrs):
                    a.append('  ' + str(key) + ' : ' + str(value))
            else:
                a.append('  <invalid item>')
        a = sorted(a)
        a.insert(0, 'SymbolTable(')
        a[-1] += ')'
        return '\n'.join(a)

    def copy(self) -> 'SymbolTable':
        return SymbolTable((key, node.copy())
                           for key, node in self.items())

    def serialize(self, fullname: str) -> JsonDict:
        data = {'.class': 'SymbolTable'}  # type: JsonDict
        for key, value in self.items():
            # Skip __builtins__: it's a reference to the builtins
            # module that gets added to every module by
            # SemanticAnalyzerPass2.visit_file(), but it shouldn't be
            # accessed by users of the module.
            if key == '__builtins__' or value.no_serialize:
                continue
            data[key] = value.serialize(fullname, key)
        return data

    @classmethod
    def deserialize(cls, data: JsonDict) -> 'SymbolTable':
        from mypy.nodes import SymbolTableNode

        assert data['.class'] == 'SymbolTable'
        st = SymbolTable()
        for key, value in data.items():
            if key != '.class':
                st[key] = SymbolTableNode.deserialize(value)
        return st
