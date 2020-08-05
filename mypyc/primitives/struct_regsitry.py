"""Struct registries for C backend"""

from typing import List, Dict, Tuple
from mypyc.ir.rtypes import RType, StructInfo, RStruct, c_pyssize_t_rprimitive, pointer_rprimitive

struct_infos = {}  # type: Dict[str, StructInfo]
struct_types = {}  # type: Dict[str, RStruct]


def c_struct(name: str,
             names: List[str],
             types: List[RType]) -> StructInfo:
    """Define a known C struct for generating IR to manipulate it

    name: The name of the C struct
    types: type of each field
    names: name of each field
           TODO: the names list can be empty in the future when we merge Tuple as part of Struct
    """
    info = StructInfo(name, names, types)
    struct_infos[name] = info
    typ = RStruct(info)
    struct_types[name] = typ


c_struct(
    name='PyVarObject',
    names=['ob_refcnt', 'ob_type', 'ob_size'],
    types=[c_pyssize_t_rprimitive, pointer_rprimitive, c_pyssize_t_rprimitive])
