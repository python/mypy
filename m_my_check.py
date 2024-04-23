from typing import Optional, reveal_type


# def refine_types(a: Optional[int], b: Optional[str], c: Optional[float]) -> str:
#     if None in [a, b, c]:
#         return "One or more are None"
#     else:
#         reveal_type(a)  # N: Revealed type is 'builtins.int'
#         reveal_type(b)  # N: Revealed type is 'builtins.str'
#         reveal_type(c)  # N: Revealed type is 'builtins.float'
#         return f"{a}, {b}, {c}"
#
#
# a: Optional[int] = 5
# b: Optional[str] = "hello"
# c: Optional[float] = None
#
# result = refine_types(a, b, c)
# reveal_type(result)  # N: Revealed type is 'builtins.str'


# def refine_complex(a: Optional[int], b: Optional[float], c: Optional[str]) -> str:
#     # Test with complex conditions mixed with `None in`
#     if None not in [a, b, c] and b + 3 != 5.5:
#         reveal_type(a)  # N: Revealed type is 'builtins.int'
#         reveal_type(b)  # N: Revealed type is 'builtins.float'
#         reveal_type(c)  # N: Revealed type is 'builtins.str'
#         return f"{a}, {b}, {c}"
#     reveal_type(a)  # N: Revealed type is 'Union[builtins.int, None]'
#     reveal_type(b)  # N: Revealed type is 'Union[builtins.float, None]'
#     reveal_type(c)  # N: Revealed type is 'Union[builtins.str, None]'
#     return "All are valid"
#
#
# a: Optional[int] = 5
# b: Optional[float] = 10.3
# c: Optional[str] = "cCCCc"
#
# result_complex = refine_complex(a, b, c)
# reveal_type(result_complex)  # N: Revealed type is 'builtins.str'


def check_failure(a: Optional[int], b: Optional[float], c: Optional[str]) -> str:
    if None in [a, b, c]:
        print(a + 3)            # E: Unsupported operand types for + ("None" and "int")  [operator]
        print(b.is_integer())   # E: Item "None" of "float | None" has no attribute "is_integer"  [union-attr]
        print(c.upper())        # E: Item "None" of "str | None" has no attribute "upper"  [union-attr]
        return "None is present"
    else:
        print(a + 3)
        print(b.is_integer())
        print(c.upper())
        return "All are valid"
