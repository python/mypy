"""Information about Python operators"""

import enum
from typing_extensions import Final


@enum.unique
class BinOp(str, enum.Enum):
    """Represents all possible operators in Python.

    Copies the same names as ``ast`` module does.

    Note, that some operators cannot be used in some Python versions.
    For example, ``@`` does not exist in Python2.
    """

    # boolops:
    And = 'and'
    Or = 'or'

    # operators:
    Add = '+'
    BitAnd = '&'
    BitOr = '|'
    BitXor = '^'
    Div = '/'
    DivMod = 'divmod'
    FloorDiv = '//'
    LShift = '<<'
    Mod = '%'
    Mul = '*'
    MatMult = '@'
    Pow = '**'
    RShift = '>>'
    Sub = '-'

    # cmpops:
    Eq = '=='
    Gt = '>'
    GtE = '>='
    In = 'in'
    Is = 'is'
    IsNot = 'is not'
    Lt = '<'
    LtE = '<='
    NotEq = '!='
    NotIn = 'not in'

    def is_numeric_compare(self) -> bool:
        return self in {BinOp.Eq, BinOp.NotEq, BinOp.LtE, BinOp.Lt, BinOp.GtE, BinOp.Gt}

    def is_boolean(self) -> bool:
        return self in {BinOp.And, BinOp.Or}

    def is_equality(self) -> bool:
        return self in {BinOp.Eq, BinOp.NotEq}


# Map reverse binary numberic operators, if possible:
reverse_op: Final = {
    BinOp.Eq: BinOp.Eq,
    BinOp.NotEq: BinOp.NotEq,
    BinOp.Lt: BinOp.Gt,
    BinOp.Gt: BinOp.Lt,
    BinOp.LtE: BinOp.GtE,
    BinOp.GtE: BinOp.LtE,
}


# Map from binary operator id to related method name (in Python 3).
op_methods: Final = {
    BinOp.Add: '__add__',
    BinOp.Sub: '__sub__',
    BinOp.Mul: '__mul__',
    BinOp.Div: '__truediv__',
    BinOp.Mod: '__mod__',
    BinOp.DivMod: '__divmod__',
    BinOp.FloorDiv: '__floordiv__',
    BinOp.Pow: '__pow__',
    BinOp.MatMult: '__matmul__',
    BinOp.BitAnd: '__and__',
    BinOp.BitOr: '__or__',
    BinOp.BitXor: '__xor__',
    BinOp.LShift: '__lshift__',
    BinOp.RShift: '__rshift__',
    BinOp.Eq: '__eq__',
    BinOp.NotEq: '__ne__',
    BinOp.Lt: '__lt__',
    BinOp.LtE: '__le__',
    BinOp.Gt: '__gt__',
    BinOp.GtE: '__ge__',
    BinOp.In: '__contains__',
}

op_methods_to_symbols: Final = {v: k.value for (k, v) in op_methods.items()}
op_methods_to_symbols['__div__'] = '/'

comparison_fallback_method: Final = "__cmp__"
ops_falling_back_to_cmp: Final = {"__ne__", "__eq__", "__lt__", "__le__", "__gt__", "__ge__"}


ops_with_inplace_method: Final = {
    BinOp.Add,
    BinOp.Sub,
    BinOp.Mul,
    BinOp.Div,
    BinOp.Mod,
    BinOp.FloorDiv,
    BinOp.Pow,
    BinOp.MatMult,
    BinOp.BitAnd,
    BinOp.BitOr,
    BinOp.BitXor,
    BinOp.LShift,
    BinOp.RShift,
}

inplace_operator_methods: Final = set("__i" + op_methods[op][2:] for op in ops_with_inplace_method)

reverse_op_methods: Final = {
    '__add__': '__radd__',
    '__sub__': '__rsub__',
    '__mul__': '__rmul__',
    '__truediv__': '__rtruediv__',
    '__mod__': '__rmod__',
    '__divmod__': '__rdivmod__',
    '__floordiv__': '__rfloordiv__',
    '__pow__': '__rpow__',
    '__matmul__': '__rmatmul__',
    '__and__': '__rand__',
    '__or__': '__ror__',
    '__xor__': '__rxor__',
    '__lshift__': '__rlshift__',
    '__rshift__': '__rrshift__',
    '__eq__': '__eq__',
    '__ne__': '__ne__',
    '__lt__': '__gt__',
    '__ge__': '__le__',
    '__gt__': '__lt__',
    '__le__': '__ge__',
}

reverse_op_method_names: Final = set(reverse_op_methods.values())

# Suppose we have some class A. When we do A() + A(), Python will only check
# the output of A().__add__(A()) and skip calling the __radd__ method entirely.
# This shortcut is used only for the following methods:
op_methods_that_shortcut: Final = {
    '__add__',
    '__sub__',
    '__mul__',
    '__div__',
    '__truediv__',
    '__mod__',
    '__divmod__',
    '__floordiv__',
    '__pow__',
    '__matmul__',
    '__and__',
    '__or__',
    '__xor__',
    '__lshift__',
    '__rshift__',
}

normal_from_reverse_op: Final = dict((m, n) for n, m in reverse_op_methods.items())
reverse_op_method_set: Final = set(reverse_op_methods.values())

unary_op_methods: Final = {
    '-': '__neg__',
    '+': '__pos__',
    '~': '__invert__',
}
