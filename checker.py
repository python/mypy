from mtypes import Typ, FunctionLike, Any, Callable, Instance
from errors import Errors
from nodes import MypyFile, Node, FuncBase, FuncDef


# Collection of Instance types of basic types (object, type, etc.).
class BasicTypes:
    void __init__(self, Instance object, Instance std_type, Typ tuple,
                  Typ function):
        self.object = object
        self.std_type = std_type
        self.tuple = tuple
        self.function = function


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
