"""Information about Python operators"""

from typing_extensions import Final


# Map from binary operator id to related method name (in Python 3).
op_methods = {
    '+': '__add__',
    '-': '__sub__',
    '*': '__mul__',
    '/': '__truediv__',
    '%': '__mod__',
    'divmod': '__divmod__',
    '//': '__floordiv__',
    '**': '__pow__',
    '@': '__matmul__',
    '&': '__and__',
    '|': '__or__',
    '^': '__xor__',
    '<<': '__lshift__',
    '>>': '__rshift__',
    '==': '__eq__',
    '!=': '__ne__',
    '<': '__lt__',
    '>=': '__ge__',
    '>': '__gt__',
    '<=': '__le__',
    'in': '__contains__',
}  # type: Final

op_methods_to_symbols = {v: k for (k, v) in op_methods.items()}  # type: Final
op_methods_to_symbols['__div__'] = '/'

comparison_fallback_method = '__cmp__'  # type: Final
ops_falling_back_to_cmp = {'__ne__', '__eq__',
                           '__lt__', '__le__',
                           '__gt__', '__ge__'}  # type: Final


ops_with_inplace_method = {
    '+', '-', '*', '/', '%', '//', '**', '@', '&', '|', '^', '<<', '>>'}  # type: Final

inplace_operator_methods = set(
    '__i' + op_methods[op][2:] for op in ops_with_inplace_method)  # type: Final

reverse_op_methods = {
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
}  # type: Final

reverse_op_method_names = set(reverse_op_methods.values())  # type: Final

# Suppose we have some class A. When we do A() + A(), Python will only check
# the output of A().__add__(A()) and skip calling the __radd__ method entirely.
# This shortcut is used only for the following methods:
op_methods_that_shortcut = {
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
}  # type: Final

normal_from_reverse_op = dict((m, n) for n, m in reverse_op_methods.items())  # type: Final
reverse_op_method_set = set(reverse_op_methods.values())  # type: Final

unary_op_methods = {
    '-': '__neg__',
    '+': '__pos__',
    '~': '__invert__',
}  # type: Final
