""" tests cases that require python3 syntax """

import unittest
import pinfer

# Include all of the shared unit tests
from test_pinfer import TestInfer


class TestInfer3(unittest.TestCase):
    def test_infer_keyword_only_args(self):
        # decorators break the parsing
        def f(x, *, y=0): pass
        f = pinfer.infer_signature(f)
        f(1, y='x')
        self.assert_infer_state(
            'def f(x: int, *, y: str = 0) -> None')

        def f(*, x=None, y=None): pass
        f = pinfer.infer_signature(f)
        f(y='x')
        self.assert_infer_state(
            'def f(*, x: None = None, y: str = None) -> None')

    def assert_infer_state(self, expected):
        state = pinfer.format_state()
        self.assertEqual(state, expected)
        pinfer.reset()

if __name__ == '__main__':
    unittest.main()
