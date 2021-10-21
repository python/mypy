"""
This is a module for various lookup functions:
functions that will find a semantic node by its name.
"""
from mypy.messages import SUGGESTED_TEST_FIXTURES
from mypy.nodes import MypyFile, SymbolTable, SymbolTableNode, TypeInfo, TypeAlias
from typing import Dict, Optional, cast


# TODO: gradually move existing lookup functions to this module.


def lookup_symbol_table(name: str, symbol_table: SymbolTable) -> SymbolTableNode:
    """Look up a definition from the symbol table with the given name.

    The name should not contain dots.
    """
    if name in symbol_table:
        return symbol_table[name]
    else:
        b = symbol_table.get('__builtins__', None)
        if b:
            table = cast(MypyFile, b.node).names
            if name in table:
                return table[name]
        raise KeyError('Failed lookup: {}'.format(name))


def lookup_qualified(name: str, global_symtable: SymbolTable,
                     modules: Dict[str, MypyFile]) -> SymbolTableNode:
    if '.' not in name:
        return lookup_symbol_table(name, global_symtable)
    else:
        parts = name.split('.')
        n = modules[parts[0]]
        for i in range(1, len(parts) - 1):
            sym = n.names.get(parts[i])
            assert sym is not None, "Internal error: attempted lookup of unknown name"
            n = cast(MypyFile, sym.node)
        last = parts[-1]
        if last in n.names:
            return n.names[last]
        elif len(parts) == 2 and parts[0] == 'builtins':
            fullname = 'builtins.' + last
            if fullname in SUGGESTED_TEST_FIXTURES:
                suggestion = ", e.g. add '[builtins fixtures/{}]' to your test".format(
                    SUGGESTED_TEST_FIXTURES[fullname])
            else:
                suggestion = ''
            raise KeyError("Could not find builtin symbol '{}' (If you are running a "
                           "test case, use a fixture that "
                           "defines this symbol{})".format(last, suggestion))
        else:
            msg = "Failed qualified lookup: '{}' (fullname = '{}')."
            raise KeyError(msg.format(last, name))


def lookup_typeinfo(fullname: str, global_symtable: SymbolTable,
                    modules: Dict[str, MypyFile]) -> TypeInfo:
    # Assume that the name refers to a class.
    sym = lookup_qualified(fullname, global_symtable, modules)
    node = sym.node
    if isinstance(node, TypeAlias):
        assert isinstance(node.target, Instance)  # type: ignore
        node = node.target.type
    assert isinstance(node, TypeInfo)
    return node


def lookup_fully_qualified(name: str, modules: Dict[str, MypyFile], *,
                           raise_on_missing: bool = False) -> Optional[SymbolTableNode]:
    """Find a symbol using it fully qualified name.

    The algorithm has two steps: first we try splitting the name on '.' to find
    the module, then iteratively look for each next chunk after a '.' (e.g. for
    nested classes).

    This function should *not* be used to find a module. Those should be looked
    in the modules dictionary.
    """
    head = name
    rest = []
    # 1. Find a module tree in modules dictionary.
    while True:
        if '.' not in head:
            if raise_on_missing:
                assert '.' in head, "Cannot find module for %s" % (name,)
            return None
        head, tail = head.rsplit('.', maxsplit=1)
        rest.append(tail)
        mod = modules.get(head)
        if mod is not None:
            break
    names = mod.names
    # 2. Find the symbol in the module tree.
    if not rest:
        # Looks like a module, don't use this to avoid confusions.
        if raise_on_missing:
            assert rest, "Cannot find %s, got a module symbol" % (name,)
        return None
    while True:
        key = rest.pop()
        if key not in names:
            if raise_on_missing:
                assert key in names, "Cannot find component %r for %r" % (key, name)
            return None
        stnode = names[key]
        if not rest:
            return stnode
        node = stnode.node
        # In fine-grained mode, could be a cross-reference to a deleted module
        # or a Var made up for a missing module.
        if not isinstance(node, TypeInfo):
            if raise_on_missing:
                assert node, "Cannot find %s" % (name,)
            return None
        names = node.names
