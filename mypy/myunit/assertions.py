def fail(msg: str = None) -> None:
    from mypy.myunit.errors import AssertionFailure
    raise AssertionFailure(msg)


def assert_true(b: bool, msg: str = None) -> None:
    if not b:
        fail(msg)


def assert_false(b: bool, msg: str = None) -> None:
    if b:
        fail(msg)


def _good_repr(obj: object) -> str:
    if isinstance(obj, str):
        if obj.count('\n') > 1:
            bits = ["'''\\"]
            for line in obj.split('\n'):
                # force repr to use ' not ", then cut it off
                bits.append(repr('"' + line)[2:-1])
            bits[-1] += "'''"
            return '\n'.join(bits)
    return repr(obj)


def assert_equal(a: object, b: object, fmt: str = '{} != {}') -> None:
    if a != b:
        fail(fmt.format(_good_repr(a), _good_repr(b)))
