from types import RuntimeTypeVar, OBJECT_VAR
from nodes import TypeInfo, Node, MemberExpr, IndexExpr, IntExpr


# Return a type expression that maps from runtime type variable slots
# to the type variable in the given class with the given index.
#
# For example, assume class A<T, S> ... and class B<U> is A<X, Y<U>> ...:
#
#   GetTvarAccessExpression(<B>, 1) ==
#     RuntimeTypeVar(<self.__tv2.args[0]>)  (with <...> represented as nodes)
RuntimeTypeVar get_tvar_access_expression(TypeInfo typ, int tvindex, any alt, any is_java):
    # First get the description of how to get from supertype type variables to
    # a subtype type variable.
    mapping = get_tvar_access_path(typ, tvindex)
    
    # The type checker should have noticed if there is no mapping. Be defensive
    # and make sure there is one.
    if mapping is None:
        raise RuntimeError('Could not find a typevar mapping')
    
    # Build the expression for getting at the subtype type variable
    # progressively.
    
    # First read the value of a supertype runtime type variable slot.
    Node s = self_expr()
    if alt == OBJECT_VAR:
        o = '__o'
        if is_java:
            o = '__o_{}'.format(typ.name)
        s = MemberExpr(s, o)
    Node expr = MemberExpr(s, tvar_slot_name(mapping[0] - 1, alt))
    
    # Then, optionally look into arguments based on the description.
    for i in mapping[1:]:
        expr = MemberExpr(expr, 'args')
        expr = IndexExpr(expr, IntExpr(i - 1))
    
    # Than add a final wrapper so that we have a valid type.
    return RuntimeTypeVar(expr)
