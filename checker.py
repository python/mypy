from mtypes import Typ, FunctionLike, Any, Callable
from errors import Errors
from nodes import MypyFile, Node, FuncBase, FuncDef

class TypeChecker:
    dict<Node, Typ> type_map  # Types of type checked nodes

    void __init__(self, Errors errors, dict<str, MypyFile> modules):
        pass

FunctionLike function_type(FuncBase func):
    if func.typ:
        return (FunctionLike)func.typ.typ
    else:
        # Implicit type signature with dynamic types.
        
        # Overloaded functions always have a signature, so func must be an
        # ordinary function.
        fdef = (FuncDef)func
        
        name = func.name()
        if name:
            name = '"{}"'.format(name)
        return Callable(<Typ> [Any()] * len(fdef.args), fdef.min_args, False, Any(), False, name)     
