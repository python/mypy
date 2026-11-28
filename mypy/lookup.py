"""
This is a module for various lookup functions:
functions that will find a semantic node by its name.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Final

from mypy.mro import calculate_mro
from mypy.nodes import GDEF, Block, ClassDef, MypyFile, SymbolTable, SymbolTableNode, TypeInfo
from mypy.types import Instance

# TODO: gradually move existing lookup functions to this module.

# Special cased classes from the 'types' module that are needed for basic functionality.
CORE_TYPES_CLASSES: Final = ["FunctionType"]


def make_placeholder_types_info(
    name: str, obj_type: Callable[[], Instance] | None = None
) -> TypeInfo:
    """Create a placeholder TypeInfo for a core class of the 'types' module.

    The placeholders will be replaced by the real definitions if the 'types'
    module is loaded, but they are needed to make the core classes resolvable
    even when it isn't (e.g. in tests using minimal builtins fixtures).
    """
    cdef = ClassDef(name, Block([]))  # Dummy ClassDef, will be replaced later
    info = TypeInfo(SymbolTable(), cdef, "types")
    info._fullname = f"types.{name}"
    calculate_mro(info, obj_type)
    return info


def lookup_core_types_class(fullname: str, modules: dict[str, MypyFile]) -> SymbolTableNode | None:
    """Return a placeholder symbol for a missing core class of the 'types' module.

    The 'types' module may not be loaded (e.g. in tests using minimal builtins
    fixtures), but core classes such as 'types.FunctionType' must be resolvable
    for basic functionality.
    """
    module, _, name = fullname.rpartition(".")
    if module != "types" or name not in CORE_TYPES_CLASSES:
        return None
    mod = modules.get(module)
    if mod is not None and name in mod.names:
        return None
    obj_type: Callable[[], Instance] | None = None
    builtins = modules.get("builtins")
    if builtins is not None:
        sym = builtins.names.get("object")
        if sym is not None and isinstance(sym.node, TypeInfo):
            object_info = sym.node
            obj_type = lambda: Instance(object_info, [])
    return SymbolTableNode(GDEF, make_placeholder_types_info(name, obj_type))


def lookup_fully_qualified(
    name: str, modules: dict[str, MypyFile], *, raise_on_missing: bool = False
) -> SymbolTableNode | None:
    """Find a symbol using it fully qualified name.

    The algorithm has two steps: first we try splitting the name on '.' to find
    the module, then iteratively look for each next chunk after a '.' (e.g. for
    nested classes).

    This function should *not* be used to find a module. Those should be looked
    in the modules dictionary.
    """
    # 1. Exclude the names of ad hoc instance intersections from step 2.
    i = name.find("<subclass ")
    head = name if i == -1 else name[:i]
    rest = []
    # 2. Find a module tree in modules dictionary.
    while True:
        if "." not in head:
            if raise_on_missing:
                assert "." in head, f"Cannot find module for {name}"
            return None
        # TODO: this logic is not correct as it confuses a submodule and a local symbol.
        # A potential solution may be to use format like pkg.mod:Cls.method for fullname,
        # but this is a relatively big change.
        head, tail = head.rsplit(".", maxsplit=1)
        rest.append(tail)
        mod = modules.get(head)
        if mod is not None:
            break
    names = mod.names
    # 3. Find the symbol in the module tree.
    if not rest:
        # Looks like a module, don't use this to avoid confusions.
        if raise_on_missing:
            assert rest, f"Cannot find {name}, got a module symbol"
        return None
    if i != -1:
        rest[0] += name[i:]
    while True:
        key = rest.pop()
        if key not in names:
            if raise_on_missing:
                assert key in names, f"Cannot find component {key!r} for {name!r}"
            return None
        stnode = names[key]
        if not rest:
            return stnode
        node = stnode.node
        # In fine-grained mode, could be a cross-reference to a deleted module
        # or a Var made up for a missing module.
        if not isinstance(node, TypeInfo):
            if raise_on_missing:
                assert node, f"Cannot find {name}"
            return None
        names = node.names


def lookup_stdlib_typeinfo(fullname: str, modules: dict[str, MypyFile]) -> TypeInfo:
    """Find TypeInfo for a standard library type.

    This fast path assumes that the type exists at module top-level, use this
    function only for common types like `builtins.object` or `typing.Iterable`.
    """
    module, name = fullname.rsplit(".", maxsplit=1)
    sym = modules[module].names[name]
    assert isinstance(sym.node, TypeInfo)
    return sym.node
