class MyunitException(Exception): pass


class AssertionFailure(MyunitException): pass


class SkipTestCaseException(MyunitException): pass
