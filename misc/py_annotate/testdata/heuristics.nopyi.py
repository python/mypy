from typing import Any
# If not annotate_pep484, info in pyi files is augmented with heuristics to decide if un-annotated
# arguments are "Any" or "" (like "self")

class B(object):
    def __init__(self):
        # type: () -> None
        pass

    def f(self, x):
        # type: (Any) -> None
        pass

class C(object):
    def __init__(self, x):
        # type: (Any) -> None
        pass

    @staticmethod
    def f2():
        # type: () -> None
        pass

    @staticmethod
    def f3(x, y):
        # type: (Any, Any) -> None
        pass

    @classmethod
    def f4(cls):
        # type: () -> None
        pass
