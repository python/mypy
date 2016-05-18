from typing import Any
class C(object):
    def f(self, x):
        # type: (Any) -> None
        pass

    def g(self):
        # type: () -> Any
        def f(x): #gets ignored by pytype but fixer sees it, generates warning (FIXME?)
            # type: (Any) -> Any
            return 1
        return f
