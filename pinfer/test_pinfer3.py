""" tests cases that require python3 syntax """

import unittest
import pinfer

# Include all of the shared unit tests
from test_pinfer import TestInfer

class TestInfer3(unittest.TestCase):
    def test_infer_keyword_only_args(self):
        @pinfer.infer_signature
        def f(x, *, y=0): pass
        f(1, y='x')
        self.assert_infer_state(
            'def f(x: int, *, y: str) -> None')
        
        @pinfer.infer_signature
        def f(*, x=None, y=None): pass
        f(y='x')
        self.assert_infer_state(
            'def f(*, x: None, y: str) -> None')

    def assert_infer_state(self, expected):
        state = pinfer.format_state()
        self.assertEqual(state, expected)
        pinfer.reset()

if __name__ == '__main__':
    unittest.main()
