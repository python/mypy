from typing import List, Optional

from mypy.nodes import (
    ARG_POS, MDEF, Argument, Block, CallExpr, Expression, SYMBOL_FUNCBASE_TYPES,
    FuncDef, PassStmt, RefExpr, SymbolTableNode, Var, StrExpr,
)
from mypy.plugin import ClassDefContext
from mypy.semanal import set_callable_name
from mypy.types import CallableType, Overloaded, Type, TypeVarDef, LiteralType, Instance, UnionType
from mypy.typevars import fill_typevars
from mypy.util import get_unique_redefinition_name


def _get_decorator_bool_argument(
        ctx: ClassDefContext,
        name: str,
        default: bool,
) -> bool:
    """Return the bool argument for the decorator.

    This handles both @decorator(...) and @decorator.
    """
    if isinstance(ctx.reason, CallExpr):
        return _get_bool_argument(ctx, ctx.reason, name, default)
    else:
        return default


def _get_bool_argument(ctx: ClassDefContext, expr: CallExpr,
                       name: str, default: bool) -> bool:
    """Return the boolean value for an argument to a call or the
    default if it's not found.
    """
    attr_value = _get_argument(expr, name)
    if attr_value:
        ret = ctx.api.parse_bool(attr_value)
        if ret is None:
            ctx.api.fail('"{}" argument must be True or False.'.format(name), expr)
            return default
        return ret
    return default


def _get_argument(call: CallExpr, name: str) -> Optional[Expression]:
    """Return the expression for the specific argument."""
    # To do this we use the CallableType of the callee to find the FormalArgument,
    # then walk the actual CallExpr looking for the appropriate argument.
    #
    # Note: I'm not hard-coding the index so that in the future we can support other
    # attrib and class makers.
    if not isinstance(call.callee, RefExpr):
        return None

    callee_type = None
    callee_node = call.callee.node
    if (isinstance(callee_node, (Var, SYMBOL_FUNCBASE_TYPES))
            and callee_node.type):
        callee_node_type = callee_node.type
        if isinstance(callee_node_type, Overloaded):
            # We take the last overload.
            callee_type = callee_node_type.items()[-1]
        elif isinstance(callee_node_type, CallableType):
            callee_type = callee_node_type

    if not callee_type:
        return None

    argument = callee_type.argument_by_name(name)
    if not argument:
        return None
    assert argument.name

    for i, (attr_name, attr_value) in enumerate(zip(call.arg_names, call.args)):
        if argument.pos is not None and not attr_name and i == argument.pos:
            return attr_value
        if attr_name == argument.name:
            return attr_value
    return None


def add_method(
        ctx: ClassDefContext,
        name: str,
        args: List[Argument],
        return_type: Type,
        self_type: Optional[Type] = None,
        tvar_def: Optional[TypeVarDef] = None,
) -> None:
    """Adds a new method to a class.
    """
    info = ctx.cls.info

    # First remove any previously generated methods with the same name
    # to avoid clashes and problems in new semantic analyzer.
    if name in info.names:
        sym = info.names[name]
        if sym.plugin_generated and isinstance(sym.node, FuncDef):
            ctx.cls.defs.body.remove(sym.node)

    self_type = self_type or fill_typevars(info)
    function_type = ctx.api.named_type('__builtins__.function')

    args = [Argument(Var('self'), self_type, None, ARG_POS)] + args
    arg_types, arg_names, arg_kinds = [], [], []
    for arg in args:
        assert arg.type_annotation, 'All arguments must be fully typed.'
        arg_types.append(arg.type_annotation)
        arg_names.append(arg.variable.name())
        arg_kinds.append(arg.kind)

    signature = CallableType(arg_types, arg_kinds, arg_names, return_type, function_type)
    if tvar_def:
        signature.variables = [tvar_def]

    func = FuncDef(name, args, Block([PassStmt()]))
    func.info = info
    func.type = set_callable_name(signature, func)
    func._fullname = info.fullname() + '.' + name
    func.line = info.line

    # NOTE: we would like the plugin generated node to dominate, but we still
    # need to keep any existing definitions so they get semantically analyzed.
    if name in info.names:
        # Get a nice unique name instead.
        r_name = get_unique_redefinition_name(name, info.names)
        info.names[r_name] = info.names[name]

    info.names[name] = SymbolTableNode(MDEF, func, plugin_generated=True)
    info.defn.defs.body.append(func)


def try_getting_str_literals(expr: Expression, typ: Type) -> Optional[List[str]]:
    """If the given expression or type corresponds to a string literal
    or a union of string literals, returns a list of the underlying strings.
    Otherwise, returns None.

    Specifically, this function is guaranteed to return a list with
    one or more strings if one one the following is true:

    1. 'expr' is a StrExpr
    2. 'typ' is a LiteralType containing a string
    3. 'typ' is a UnionType containing only LiteralType of strings
    """
    if isinstance(expr, StrExpr):
        return [expr.value]

    if isinstance(typ, Instance) and typ.last_known_value is not None:
        possible_literals = [typ.last_known_value]  # type: List[Type]
    elif isinstance(typ, UnionType):
        possible_literals = typ.items
    else:
        possible_literals = [typ]

    strings = []
    for lit in possible_literals:
        if isinstance(lit, LiteralType) and lit.fallback.type.fullname() == 'builtins.str':
            val = lit.value
            assert isinstance(val, str)
            strings.append(val)
        else:
            return None
    return strings
