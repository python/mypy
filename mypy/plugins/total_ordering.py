from mypy.nodes import (Argument, TypeVarExpr, SymbolTableNode, Var, ARG_POS, MDEF)
from mypy.plugin import ClassDefContext
from mypy.plugins.common import add_method
from mypy.types import (TypeVarDef, TypeVarType)

total_ordering_fullname = "functools.total_ordering"


SELF_TVAR_NAME = '_AT'  # type: Final


def _validate_total_ordering(ctx: ClassDefContext) -> None:
    names = set(ctx.cls.info.names)
    if '__eq__' not in names:
        ctx.api.fail("Classes with total_ordering must define __eq__", ctx.cls)
    if not ('__lt__' in names or '__le__' in names or
            '__gt__' in names or '__ge__' in names):
        ctx.api.fail("Classes with total_ordering must define one of __{lt, gt, le, ge}__", ctx.cls)


def _create_typevar_on_class(ctx: ClassDefContext) -> TypeVarType:
    object_type = ctx.api.named_type('__builtins__.object')
    tvar_name = SELF_TVAR_NAME
    tvar_fullname = ctx.cls.info.fullname() + '.' + SELF_TVAR_NAME

    tvd = TypeVarDef(tvar_name, tvar_fullname, -1, [], object_type)
    tvd_type = TypeVarType(tvd)

    self_tvar_expr = TypeVarExpr(tvar_name, tvar_fullname, [], object_type)
    ctx.cls.info.names[tvar_name] = SymbolTableNode(MDEF, self_tvar_expr)

    return tvd, tvd_type


def total_ordering_callback(ctx: ClassDefContext) -> None:
    """Generate the missing ordering methods for this class."""
    _validate_total_ordering(ctx)

    bool_type = ctx.api.named_type('__builtins__.bool')
    tvd, tvd_type = _create_typevar_on_class(ctx)

    args = [Argument(Var('other', tvd_type), tvd_type, None, ARG_POS)]

    existing_names = set(ctx.cls.info.names)
    for method in ('__lt__', '__le__', '__gt__', '__ge__'):
        if method not in existing_names:
            add_method(ctx, method, args, bool_type, self_type=tvd_type, tvar_def=tvd)
