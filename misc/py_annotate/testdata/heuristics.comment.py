from typing import Any
# If not annotate_pep484, info in pyi files is augmented with heuristics to decide if un-annotated
# arguments are "Any" or "" (like "self")

class B(object):
    def __init__(self):
        pass

    def f(self, x):
        # type: (e1) -> None
        pass

class C(object):
    def __init__(self, x):
        # type: (e2) -> None
        pass

    @staticmethod
    def f2():
        pass

    @staticmethod
    def f3(x, y):
        # type: (Any, e3) -> None
        pass

    @classmethod
    def f4(cls):
        pass
