from typing import Optional

"""Shared logic between our three mypy parser files."""


MAGIC_METHODS = {
    "__abs__",
    "__add__",
    "__and__",
    "__call__",
    "__cmp__",
    "__complex__",
    "__contains__",
    "__del__",
    "__delattr__",
    "__delitem__",
    "__divmod__",
    "__div__",
    "__divmod__",
    "__enter__",
    "__exit__",
    "__eq__",
    "__floordiv__",
    "__float__",
    "__ge__",
    "__getattr__",
    "__getattribute__",
    "__getitem__",
    "__gt__",
    "__hex__",
    "__iadd__",
    "__iand__",
    "__idiv__",
    "__ifloordiv__",
    "__ilshift__",
    "__imod__",
    "__imul__",
    "__init__",
    "__init_subclass__",
    "__int__",
    "__invert__",
    "__ior__",
    "__ipow__",
    "__irshift__",
    "__isub__",
    "__iter__",
    "__ixor__",
    "__le__",
    "__len__",
    "__long__",
    "__lshift__",
    "__lt__",
    "__mod__",
    "__mul__",
    "__ne__",
    "__neg__",
    "__new__",
    "__nonzero__",
    "__oct__",
    "__or__",
    "__pos__",
    "__pow__",
    "__radd__",
    "__rand__",
    "__rdiv__",
    "__repr__",
    "__reversed__",
    "__rfloordiv__",
    "__rlshift__",
    "__rmod__",
    "__rmul__",
    "__ror__",
    "__rpow__",
    "__rrshift__",
    "__rshift__",
    "__rsub__",
    "__rxor__",
    "__setattr__",
    "__setitem__",
    "__str__",
    "__sub__",
    "__unicode__",
    "__xor__",
}

MAGIC_METHODS_ALLOWING_KWARGS = {
    "__init__",
    "__init_subclass__",
    "__new__",
    "__call__",
}

MAGIC_METHODS_POS_ARGS_ONLY = MAGIC_METHODS - MAGIC_METHODS_ALLOWING_KWARGS


def special_function_elide_names(name: str) -> bool:
    return name in MAGIC_METHODS_POS_ARGS_ONLY


def argument_elide_name(name: Optional[str]) -> bool:
    return name is not None and name.startswith("__")
