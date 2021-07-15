import unittest

from mypyc.irbuild.format_str_tokenizer import tokenizer_printf_style


class TestStringFormatting(unittest.TestCase):
    def test_tokenizer_printf_style(self) -> None:
        assert tokenizer_printf_style("I'm %s, id years old") == \
               (["I'm ", ', id years old'], ['%s'])
        assert tokenizer_printf_style("Test: %i%%, Test: %02d, Test: %.2f") == \
               (['Test: ', '', ', Test: ', ', Test: ', ''], ['%i', '%%', '%02d', '%.2f'])
