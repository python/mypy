from typing import Dict, Any, Union, Optional

from mypy.nodes import (
    ClassDef, FuncDef, Decorator, OverloadedFuncDef, StrExpr, CallExpr, RefExpr, Expression,
    IntExpr, FloatExpr, ARG_NAMED, ARG_NAMED_OPT, ARG_POS, ARG_OPT
)


def is_trait_decorator(d: Expression) -> bool:
    return isinstance(d, RefExpr) and d.fullname == 'mypy_extensions.trait'


def is_trait(cdef: ClassDef) -> bool:
    return any(is_trait_decorator(d) for d in cdef.decorators)


def is_dataclass_decorator(d: Expression) -> bool:
    return (
        (isinstance(d, RefExpr) and d.fullname == 'dataclasses.dataclass')
        or (
            isinstance(d, CallExpr)
            and isinstance(d.callee, RefExpr)
            and d.callee.fullname == 'dataclasses.dataclass'
        )
    )


def is_dataclass(cdef: ClassDef) -> bool:
    return any(is_dataclass_decorator(d) for d in cdef.decorators)


def get_mypyc_attr_literal(e: Expression) -> Any:
    """Convert an expression from a mypyc_attr decorator to a value.

    Supports a pretty limited range."""
    if isinstance(e, (StrExpr, IntExpr, FloatExpr)):
        return e.value
    elif isinstance(e, RefExpr) and e.fullname == 'builtins.True':
        return True
    elif isinstance(e, RefExpr) and e.fullname == 'builtins.False':
        return False
    elif isinstance(e, RefExpr) and e.fullname == 'builtins.None':
        return None
    return NotImplemented


def get_mypyc_attr_call(d: Expression) -> Optional[CallExpr]:
    """Check if an expression is a call to mypyc_attr and return it if so."""
    if (
        isinstance(d, CallExpr)
        and isinstance(d.callee, RefExpr)
        and d.callee.fullname == 'mypy_extensions.mypyc_attr'
    ):
        return d
    return None


def get_mypyc_attrs(stmt: Union[ClassDef, Decorator]) -> Dict[str, Any]:
    """Collect all the mypyc_attr attributes on a class definition or a function."""
    attrs = {}  # type: Dict[str, Any]
    for dec in stmt.decorators:
        d = get_mypyc_attr_call(dec)
        if d:
            for name, arg in zip(d.arg_names, d.args):
                if name is None:
                    if isinstance(arg, StrExpr):
                        attrs[arg.value] = True
                else:
                    attrs[name] = get_mypyc_attr_literal(arg)

    return attrs


def is_extension_class(cdef: ClassDef) -> bool:
    if any(
        not is_trait_decorator(d)
        and not is_dataclass_decorator(d)
        and not get_mypyc_attr_call(d)
        for d in cdef.decorators
    ):
        return False
    elif (cdef.info.metaclass_type and cdef.info.metaclass_type.type.fullname not in (
            'abc.ABCMeta', 'typing.TypingMeta', 'typing.GenericMeta')):
        return False
    return True


def get_func_def(op: Union[FuncDef, Decorator, OverloadedFuncDef]) -> FuncDef:
    if isinstance(op, OverloadedFuncDef):
        assert op.impl
        op = op.impl
    if isinstance(op, Decorator):
        op = op.func
    return op


def concrete_arg_kind(kind: int) -> int:
    """Find the concrete version of an arg kind that is being passed."""
    if kind == ARG_OPT:
        return ARG_POS
    elif kind == ARG_NAMED_OPT:
        return ARG_NAMED
    else:
        return kind
