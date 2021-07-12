"""Tokenizers for three string formatting methods"""

import re
from typing import List, Tuple


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


assert tokenizer_printf_style("I'm %s, id years old") == \
    (["I'm ", ', id years old'], ['%s'])
assert tokenizer_printf_style("Test: %i%%, Test: %02d, Test: %.2f") == \
    (['Test: ', '', ', Test: ', ', Test: ', ''], ['%i', '%%', '%02d', '%.2f'])
