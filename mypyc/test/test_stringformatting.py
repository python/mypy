import unittest
from typing import List

from mypyc.irbuild.format_str_tokenizer import tokenizer_printf_style


class TestStringFormatting(unittest.TestCase):

    def test_tokenizer_printf_style(self) -> None:

        def tokenizer_printf_style_helper(format_str: str,
                                          literals: List[str], conversion: List[str]) -> bool:
            l, specs = tokenizer_printf_style(format_str)
            return literals == l and conversion == [x.whole_seq for x in specs]

        assert tokenizer_printf_style_helper(
            "I'm %s, id years old",
            ["I'm ", ', id years old'],
            ['%s'])
        assert tokenizer_printf_style_helper(
            "Test: %i%%, Test: %02d, Test: %.2f",
            ['Test: ', '', ', Test: ', ', Test: ', ''],
            ['%i', '%%', '%02d', '%.2f'])
        assert tokenizer_printf_style_helper(
            "ioasdfyuia%i%%%20s%d%sdafafadfa%s%d%x%E%.2f",
            ['ioasdfyuia', '', '', '', '', 'dafafadfa', '', '', '', '', ''],
            ['%i', '%%', '%20s', '%d', '%s', '%s', '%d', '%x', '%E', '%.2f'])
        assert tokenizer_printf_style_helper(
            "Special: %#20.2f%d, test: ",
            ['Special: ', '', ', test: '],
            ['%#20.2f', '%d'])
