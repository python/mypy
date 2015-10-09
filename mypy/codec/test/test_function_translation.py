import codecs
import sys

from unittest import TestCase

from mypy.codec import register

# The test functions that will be translated.
# even indices are input functions, odd indices are expected output
test_function_examples = [
# test a function without annotations
b'''\
def f(x):
    x = {'a': x}
    return x['a']
''',
b'''\
def f(x):
    x = {'a': x}
    return x['a']
''',

# test parameter type annotations
b'''\
def f(x: int, y: str = 'abc'):
    return x
''',
b'''\
def f(x     , y      = 'abc'):
    return x
''',

# test return type annotations
b'''\
def f(x, y) -> str:
    return x
''',
b'''\
def f(x, y)       :
    return x
''',

# test newlines in param list
b'''\
def f(x: int,
                y: str) -> str:
    return x
''',
b'''\
def f(x     ,
                y     )       :
    return x
''',

# test newlines in return type annotation
b'''\
def f(x: int, y: str='abc') -> Tuple[int,
                                str]:
    return x, y
''',
b'''\
def f(x     , y     ='abc')\\
                                    :
    return x, y
''',


# test unrelated continuations
b'''\
x = 1 + \
    2
''',
b'''\
x = 1 + \
    2
''',

]


class TestFunctionTranslation(TestCase):

    def test_all_functions(self):
        for i in range(0, len(test_function_examples), 2):
            func_orig = test_function_examples[i]
            func_py2 = test_function_examples[i + 1].decode('utf-8')
            func_py3 = func_orig.decode('utf-8')
            func_translated = codecs.decode(func_orig, 'mypy')
            if sys.version_info[0] == 2:
                self.assertEqual(func_translated, func_py2)
            else:
                self.assertEqual(func_translated, func_py3)
