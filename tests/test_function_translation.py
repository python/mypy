import codecs

from unittest import TestCase

from py3annot.codec import register

class TestFunctionTranslation(TestCase):
    def test_no_annotations(self):
        func = '''def f(x):
    x = {'a': x}
    return x['a']'''

        func_translated = codecs.decode(func, 'py3annot')

        self.assertEqual(func, func_translated)

    def test_param_annotations(self):
        func = \
            '''def f(x: int, y: str = 'abc'):
    return x'''
        func_expected = \
            '''def f(x     , y      = 'abc'):
    return x'''

        func_translated = codecs.decode(func, 'py3annot')

        self.assertEqual(func_expected, func_translated)

    def test_return_annotations(self):
        func = \
            '''def f(x, y) -> str:
    return x'''
        func_expected = \
            '''def f(x, y)       :
    return x'''

        func_translated = codecs.decode(func, 'py3annot')

        self.assertEqual(func_expected, func_translated)

    def test_newline_in_param_list(self):
        func = \
            '''def f(x: int,
                y: str) -> str:
    return x'''
        func_expected = \
            '''def f(x     ,
                y     )       :
    return x'''

        func_translated = codecs.decode(func, 'py3annot')

        self.assertEqual(func_expected, func_translated)
