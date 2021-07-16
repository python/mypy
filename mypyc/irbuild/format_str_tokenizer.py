"""Tokenizers for three string formatting methods"""

import re
from typing import List, Tuple

from mypyc.ir.ops import Value, Integer
from mypyc.ir.rtypes import c_pyssize_t_rprimitive
from mypyc.irbuild.builder import IRBuilder
from mypyc.primitives.str_ops import str_build_op


def tokenizer_printf_style(format_str: str) -> Tuple[List[str], List[str]]:
    # printf-style String Formatting:
    # https://docs.python.org/3/library/stdtypes.html#old-string-formatting
    pattern = re.compile(r"""
        (
        %                                # Start sign
        (?:\((?P<key>[^)]*)\))?          # Optional: Mapping key
        (?P<flag>[-+#0 ]+)?              # Optional: Conversion flags
        (?P<width>\d+|\*)?               # Optional: Minimum field width
        (?:\.(?P<precision>\d+|\*))?     # Optional: Precision
        [hlL]?                           # Optional: Length modifier, Ignored
        (?P<type>[diouxXeEfFgGcrsa])     # Conversion type
        | %%)
        """, re.VERBOSE)

    literals = []
    format_op = []
    last_end = 0

    for m in re.finditer(pattern, format_str):
        cur_start = m.start(1)
        format_tmp = m.group(1)
        literals.append(format_str[last_end:cur_start])
        format_op.append(format_tmp)
        last_end = cur_start + len(format_tmp)

    literals.append(format_str[last_end:])

    return literals, format_op


def join_formatted_strings(builder: IRBuilder, literals: List[str],
                           variables: List[Value], line: int) -> Value:

    # The first parameter is the total size of the following PyObject* merged from
    # two lists alternatively.
    result_list: List[Value] = [Integer(0, c_pyssize_t_rprimitive)]
    for a, b in zip(literals, variables):
        if a:
            result_list.append(builder.load_str(a))
        result_list.append(b)
    # The split_braces() always generates one more element
    if literals[-1]:
        result_list.append(builder.load_str(literals[-1]))
    # Special case for empty string and literal string
    if len(result_list) == 1:
        return builder.load_str("")
    if not variables and len(result_list) == 2:
        return result_list[1]

    result_list[0] = Integer(len(result_list) - 1, c_pyssize_t_rprimitive)
    return builder.call_c(str_build_op, result_list, line)
