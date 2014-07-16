import codecs

from unittest import TestCase

from py3annot.codec import register

# The test functions that will be translated.
# even indices are input functions, odd indices are expected output
test_function_examples = [
# test a function without annotations
'''\
def f(x):
    x = {'a': x}
    return x['a']
''',
'''\
def f(x):
    x = {'a': x}
    return x['a']
''',

# test parameter type annotations
'''\
def f(x: int, y: str = 'abc'):
    return x
''',
'''\
def f(x     , y      = 'abc'):
    return x
''',

# test return type annotations
'''\
def f(x, y) -> str:
    return x
''',
'''\
def f(x, y)       :
    return x
''',

# test newlines in param list
'''\
def f(x: int,
                y: str) -> str:
    return x
''',
'''\
def f(x     ,
                y     )       :
    return x
''',

# test newlines in return type annotation
'''\
def f(x: int, y: str='abc') -> Tuple[int,
                                str]:
    return x, y
''',
'''\
def f(x     , y     ='abc')\\
                                    :
    return x, y
''',


# test unrelated continuations
'''\
x = 1 + \
    2
''',
'''\
x = 1 + \
    2
''',

]

class TestFunctionTranslation(TestCase):

    def test_all_functions(self):
        for i in range(0, len(test_function_examples), 2):
            func_translated = codecs.decode(test_function_examples[i], 'py3annot')
            #print repr(func_translated)
            #print repr(test_function_examples[i+1])
            self.assertEqual(func_translated, test_function_examples[i+1])
