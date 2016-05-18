class C(object):
    def f(self, x):
        # type: (e1) -> r1
        pass

    def g(self):
        # type: () -> function
        def f(x): #gets ignored by pytype but fixer sees it, generates warning (FIXME?)
            return 1
        return f
