"""Struct registries for C backend"""

from typing import List, NamedTuple
from mypyc.ir.rtypes import RType

CStructDescription = NamedTuple(
    'CStructDescription', [('name', str),
                           ('names', List[str]),
                           ('types', List[RType])])


def c_struct(name: str,
             names: List[str],
             types: List[RType]) -> CStructDescription:
    """Define a known C struct for generating IR to manipulate it

    name: The name of the C struct
    types: type of each field
    names: name of each field
           TODO: the names list can be empty in the future when we merge Tuple as part of Struct
    """
    return CStructDescription(name, names, types)

# TODO: create PyVarObject, to do which we probably need PyObject
