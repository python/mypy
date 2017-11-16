"""Compare two versions of a module symbol table.

The goal is to find which AST nodes have externally visible changes, so
that we can fire triggers and re-type-check other parts of the program
that are stale because of the changes.

Only look at detail at definitions at the current module.
"""

from typing import Set, List, TypeVar

from mypy.nodes import SymbolTable, SymbolTableNode, FuncBase, TypeInfo, Var
from mypy.types import (
    Type, TypeVisitor, UnboundType, TypeList, AnyType, NoneTyp, UninhabitedType,
    ErasedType, DeletedType, Instance, TypeVarType, CallableType, TupleType, TypedDictType,
    UnionType, Overloaded, PartialType, TypeType
)


def compare_symbol_tables(name_prefix: str, table1: SymbolTable, table2: SymbolTable) -> Set[str]:
    """Return names that are different in two versions of a symbol table.

    Return a set of fully-qualified names (e.g., 'mod.func' or 'mod.Class.method').
    """
    # Find names only defined only in one version.
    names1 = {'%s.%s' % (name_prefix, name) for name in table1}
    names2 = {'%s.%s' % (name_prefix, name) for name in table2}
    triggers = names1 ^ names2

    # Look for names defined in both versions that are different.
    for name in set(table1.keys()) & set(table2.keys()):
        if not is_similar_node_shallow(table1[name], table2[name]):
            triggers.add('%s.%s' % (name_prefix, name))
        else:
            # Nodes are the same when using shallow comparison. Now look into contents of
            # classes to find changed items.
            node1 = table1[name].node
            node2 = table2[name].node

            if node1 and node1.fullname() and get_prefix(node1.fullname()) != name_prefix:
                # Only look inside things defined in the current module.
                # TODO: This probably doesn't work generally...
                continue

            if isinstance(node1, TypeInfo) and isinstance(node2, TypeInfo):
                # TODO: Only do this is the class is defined in this module.
                prefix = '%s.%s' % (name_prefix, node1.name())
                triggers |= compare_symbol_tables(prefix, node1.names, node2.names)

    return triggers


def is_similar_node_shallow(n: SymbolTableNode, m: SymbolTableNode) -> bool:
    # TODO:
    #   cross_ref
    #   tvar_def
    #   type_override
    if (n.kind != m.kind
            or n.module_public != m.module_public):
        return False
    if type(n.node) != type(m.node):  # noqa
        return False
    if n.node and m.node and n.node.fullname() != m.node.fullname():
        return False
    if isinstance(n.node, FuncBase) and isinstance(m.node, FuncBase):
        # TODO: info
        return (n.node.is_property == m.node.is_property and
                is_identical_type(n.node.type, m.node.type))
    if isinstance(n.node, TypeInfo) and isinstance(m.node, TypeInfo):
        # TODO:
        #   type_vars
        #   bases
        #   _promote
        #   tuple_type
        #   typeddict_type
        nn = n.node
        mn = m.node
        return (nn.is_abstract == mn.is_abstract and
                nn.is_enum == mn.is_enum and
                nn.fallback_to_any == mn.fallback_to_any and
                nn.is_named_tuple == mn.is_named_tuple and
                nn.is_newtype == mn.is_newtype and
                is_same_mro(nn.mro, mn.mro))
    if isinstance(n.node, Var) and isinstance(m.node, Var):
        if n.node.type is None and m.node.type is None:
            return True
        return (n.node.type is not None and m.node.type is not None and
                is_identical_type(n.node.type, m.node.type))
    return True


def is_same_mro(mro1: List[TypeInfo], mro2: List[TypeInfo]) -> bool:
    return (len(mro1) == len(mro2)
            and all(x.fullname() == y.fullname() for x, y in zip(mro1, mro2)))


def get_prefix(id: str) -> str:
    """Drop the final component of a qualified name (e.g. ('x.y' -> 'x')."""
    return id.rsplit('.', 1)[0]


def is_identical_type(t: Type, s: Type) -> bool:
    return t.accept(IdenticalTypeVisitor(s))


TT = TypeVar('TT', bound=Type)


def is_identical_types(a: List[TT], b: List[TT]) -> bool:
    return len(a) == len(b) and all(is_identical_type(t, s) for t, s in zip(a, b))


class IdenticalTypeVisitor(TypeVisitor[bool]):
    """Visitor for checking whether two types are identical.

    This may be conservative -- it's okay for two types to be considered
    different even if they are actually the same. The results are only
    used to improve performance, not relied on for correctness.

    Differences from mypy.sametypes:

    * Types with the same name but different AST nodes are considered
      identical.

    * If one of the types is not valid for whatever reason, they are
      considered different.

    * Sometimes require types to be structurally identical, even if they
      are semantically the same type.
    """

    def __init__(self, right: Type) -> None:
        self.right = right

    # visit_x(left) means: is left (which is an instance of X) the same type as
    # right?

    def visit_unbound_type(self, left: UnboundType) -> bool:
        return False

    def visit_any(self, left: AnyType) -> bool:
        return isinstance(self.right, AnyType)

    def visit_none_type(self, left: NoneTyp) -> bool:
        return isinstance(self.right, NoneTyp)

    def visit_uninhabited_type(self, t: UninhabitedType) -> bool:
        return isinstance(self.right, UninhabitedType)

    def visit_erased_type(self, left: ErasedType) -> bool:
        return False

    def visit_deleted_type(self, left: DeletedType) -> bool:
        return isinstance(self.right, DeletedType)

    def visit_instance(self, left: Instance) -> bool:
        return (isinstance(self.right, Instance) and
                left.type.fullname() == self.right.type.fullname() and
                is_identical_types(left.args, self.right.args))

    def visit_type_var(self, left: TypeVarType) -> bool:
        return (isinstance(self.right, TypeVarType) and
                left.id == self.right.id)

    def visit_callable_type(self, left: CallableType) -> bool:
        # FIX generics
        if isinstance(self.right, CallableType):
            cright = self.right
            return (is_identical_type(left.ret_type, cright.ret_type) and
                    is_identical_types(left.arg_types, cright.arg_types) and
                    left.arg_names == cright.arg_names and
                    left.arg_kinds == cright.arg_kinds and
                    left.is_type_obj() == cright.is_type_obj() and
                    left.is_ellipsis_args == cright.is_ellipsis_args)
        return False

    def visit_tuple_type(self, left: TupleType) -> bool:
        if isinstance(self.right, TupleType):
            return is_identical_types(left.items, self.right.items)
        return False

    def visit_typeddict_type(self, left: TypedDictType) -> bool:
        if isinstance(self.right, TypedDictType):
            if left.items.keys() != self.right.items.keys():
                return False
            for (_, left_item_type, right_item_type) in left.zip(self.right):
                if not is_identical_type(left_item_type, right_item_type):
                    return False
            return True
        return False

    def visit_union_type(self, left: UnionType) -> bool:
        if isinstance(self.right, UnionType):
            # Require structurally identical types.
            return is_identical_types(left.items, self.right.items)
        return False

    def visit_overloaded(self, left: Overloaded) -> bool:
        if isinstance(self.right, Overloaded):
            return is_identical_types(left.items(), self.right.items())
        return False

    def visit_partial_type(self, left: PartialType) -> bool:
        # A partial type is not fully defined, so the result is indeterminate. We shouldn't
        # get here.
        raise RuntimeError

    def visit_type_type(self, left: TypeType) -> bool:
        if isinstance(self.right, TypeType):
            return is_identical_type(left.item, self.right.item)
        return False
