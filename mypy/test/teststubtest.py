import contextlib
import inspect
import io
import os
import re
import sys
import tempfile
import textwrap
import unittest
from typing import Any, Callable, Iterator, List, Optional

import mypy.stubtest
from mypy.stubtest import parse_options, test_stubs


@contextlib.contextmanager
def use_tmp_dir() -> Iterator[None]:
    current = os.getcwd()
    with tempfile.TemporaryDirectory() as tmp:
        try:
            os.chdir(tmp)
            yield
        finally:
            os.chdir(current)


TEST_MODULE_NAME = "test_module"


def run_stubtest(stub: str, runtime: str, options: List[str]) -> str:
    with use_tmp_dir():
        with open("{}.pyi".format(TEST_MODULE_NAME), "w") as f:
            f.write(stub)
        with open("{}.py".format(TEST_MODULE_NAME), "w") as f:
            f.write(runtime)

        if sys.path[0] != ".":
            sys.path.insert(0, ".")
        if TEST_MODULE_NAME in sys.modules:
            del sys.modules[TEST_MODULE_NAME]

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            test_stubs(parse_options([TEST_MODULE_NAME] + options))

        return output.getvalue()


class Case:
    def __init__(self, stub: str, runtime: str, error: Optional[str]):
        self.stub = stub
        self.runtime = runtime
        self.error = error


def collect_cases(fn: Callable[..., Iterator[Case]]) -> Callable[..., None]:
    """Repeatedly invoking run_stubtest is slow, so use this decorator to combine cases.

    We could also manually combine cases, but this allows us to keep the contrasting stub and
    runtime definitions next to each other.

    """

    def test(*args: Any, **kwargs: Any) -> None:
        cases = list(fn(*args, **kwargs))
        expected_errors = set(
            "{}.{}".format(TEST_MODULE_NAME, c.error) for c in cases if c.error is not None
        )
        output = run_stubtest(
            stub="\n\n".join(textwrap.dedent(c.stub.lstrip("\n")) for c in cases),
            runtime="\n\n".join(textwrap.dedent(c.runtime.lstrip("\n")) for c in cases),
            options=["--generate-whitelist"],
        )

        actual_errors = set(output.splitlines())
        assert actual_errors == expected_errors, output

    return test


class StubtestUnit(unittest.TestCase):
    @collect_cases
    def test_basic_good(self) -> Iterator[Case]:
        yield Case(
            stub="def f(number: int, text: str) -> None: ...",
            runtime="def f(number, text): pass",
            error=None,
        )
        yield Case(
            stub="""
            class X:
                def f(self, number: int, text: str) -> None: ...
            """,
            runtime="""
            class X:
                def f(self, number, text): pass
            """,
            error=None,
        )

    @collect_cases
    def test_types(self) -> Iterator[Case]:
        yield Case(
            stub="def mistyped_class() -> None: ...",
            runtime="class mistyped_class: pass",
            error="mistyped_class",
        )
        yield Case(
            stub="class mistyped_fn: ...", runtime="def mistyped_fn(): pass", error="mistyped_fn"
        )
        yield Case(
            stub="""
            class X:
                def mistyped_var(self) -> int: ...
            """,
            runtime="""
            class X:
                mistyped_var = 1
            """,
            error="X.mistyped_var",
        )

    @collect_cases
    def test_arg_name(self) -> Iterator[Case]:
        yield Case(
            stub="def bad(number: int, text: str) -> None: ...",
            runtime="def bad(num, text) -> None: pass",
            error="bad",
        )
        if sys.version_info >= (3, 8):
            yield Case(
                stub="def good_posonly(__number: int, text: str) -> None: ...",
                runtime="def good_posonly(num, /, text): pass",
                error=None,
            )
            yield Case(
                stub="def bad_posonly(__number: int, text: str) -> None: ...",
                runtime="def bad_posonly(flag, /, text): pass",
                error="bad_posonly",
            )
        yield Case(
            stub="""
            class BadMethod:
                def f(self, number: int, text: str) -> None: ...
            """,
            runtime="""
            class BadMethod:
                def f(self, n, text): pass
            """,
            error="BadMethod.f",
        )
        yield Case(
            stub="""
            class GoodDunder:
                def __exit__(self, t, v, tb) -> None: ...
            """,
            runtime="""
            class GoodDunder:
                def __exit__(self, exc_type, exc_val, exc_tb): pass
            """,
            error=None,
        )

    @collect_cases
    def test_arg_kind(self) -> Iterator[Case]:
        yield Case(
            stub="def runtime_kwonly(number: int, text: str) -> None: ...",
            runtime="def runtime_kwonly(number, *, text): pass",
            error="runtime_kwonly",
        )
        yield Case(
            stub="def stub_kwonly(number: int, *, text: str) -> None: ...",
            runtime="def stub_kwonly(number, text): pass",
            error="stub_kwonly",
        )
        yield Case(
            stub="def stub_posonly(__number: int, text: str) -> None: ...",
            runtime="def stub_posonly(number, text): pass",
            error="stub_posonly",
        )
        if sys.version_info >= (3, 8):
            yield Case(
                stub="def good_posonly(__number: int, text: str) -> None: ...",
                runtime="def good_posonly(number, /, text): pass",
                error=None,
            )
            yield Case(
                stub="def runtime_posonly(number: int, text: str) -> None: ...",
                runtime="def runtime_posonly(number, /, text): pass",
                error="runtime_posonly",
            )

    @collect_cases
    def test_default_value(self) -> Iterator[Case]:
        yield Case(
            stub="def f1(text: str = ...) -> None: ...",
            runtime="def f1(text = 'asdf'): pass",
            error=None,
        )
        yield Case(
            stub="def f2(text: str = ...) -> None: ...", runtime="def f2(text): pass", error="f2"
        )
        yield Case(
            stub="def f3(text: str) -> None: ...",
            runtime="def f3(text = 'asdf'): pass",
            error="f3",
        )
        yield Case(
            stub="def f4(text: str = ...) -> None: ...",
            runtime="def f4(text = None): pass",
            error="f4",
        )
        yield Case(
            stub="def f5(data: bytes = ...) -> None: ...",
            runtime="def f5(data = 'asdf'): pass",
            error="f5",
        )
        yield Case(
            stub="""
            from typing import TypeVar
            T = TypeVar("T", bound=str)
            def f6(text: T = ...) -> None: ...
            """,
            runtime="def f6(text = None): pass",
            error="f6",
        )

    @collect_cases
    def test_static_class_method(self) -> Iterator[Case]:
        yield Case(
            stub="""
            class Good:
                @classmethod
                def f(cls, number: int, text: str) -> None: ...
            """,
            runtime="""
            class Good:
                @classmethod
                def f(cls, number, text): pass
            """,
            error=None,
        )
        yield Case(
            stub="""
            class Bad1:
                def f(cls, number: int, text: str) -> None: ...
            """,
            runtime="""
            class Bad1:
                @classmethod
                def f(cls, number, text): pass
            """,
            error="Bad1.f",
        )
        yield Case(
            stub="""
            class Bad2:
                @classmethod
                def f(cls, number: int, text: str) -> None: ...
            """,
            runtime="""
            class Bad2:
                @staticmethod
                def f(self, number, text): pass
            """,
            error="Bad2.f",
        )
        yield Case(
            stub="""
            class Bad3:
                @staticmethod
                def f(cls, number: int, text: str) -> None: ...
            """,
            runtime="""
            class Bad3:
                @classmethod
                def f(self, number, text): pass
            """,
            error="Bad3.f",
        )
        yield Case(
            stub="""
            class GoodNew:
                def __new__(cls, *args, **kwargs): ...
            """,
            runtime="""
            class GoodNew:
                def __new__(cls, *args, **kwargs): pass
            """,
            error=None,
        )

    @collect_cases
    def test_arg_mismatch(self) -> Iterator[Case]:
        yield Case(
            stub="def f1(a, *, b, c) -> None: ...", runtime="def f1(a, *, b, c): pass", error=None
        )
        yield Case(
            stub="def f2(a, *, b) -> None: ...", runtime="def f2(a, *, b, c): pass", error="f2"
        )
        yield Case(
            stub="def f3(a, *, b, c) -> None: ...", runtime="def f3(a, *, b): pass", error="f3"
        )
        yield Case(
            stub="def f4(a, *, b, c) -> None: ...", runtime="def f4(a, b, *, c): pass", error="f4"
        )
        yield Case(
            stub="def f5(a, b, *, c) -> None: ...", runtime="def f5(a, *, b, c): pass", error="f5"
        )

    @collect_cases
    def test_varargs_varkwargs(self) -> Iterator[Case]:
        yield Case(
            stub="def f1(*args, **kwargs) -> None: ...",
            runtime="def f1(*args, **kwargs): pass",
            error=None,
        )
        yield Case(
            stub="def f2(*args, **kwargs) -> None: ...",
            runtime="def f2(**kwargs): pass",
            error="f2",
        )
        yield Case(
            stub="def g1(a, b, c, d) -> None: ...", runtime="def g1(a, *args): pass", error=None
        )
        yield Case(
            stub="def g2(a, b, c, d, *args) -> None: ...", runtime="def g2(a): pass", error="g2"
        )
        yield Case(
            stub="def g3(a, b, c, d, *args) -> None: ...",
            runtime="def g3(a, *args): pass",
            error=None,
        )
        yield Case(
            stub="def h1(a) -> None: ...", runtime="def h1(a, b, c, d, *args): pass", error="h1"
        )
        yield Case(
            stub="def h2(a, *args) -> None: ...", runtime="def h2(a, b, c, d): pass", error="h2"
        )
        yield Case(
            stub="def h3(a, *args) -> None: ...",
            runtime="def h3(a, b, c, d, *args): pass",
            error="h3",
        )
        yield Case(
            stub="def j1(a: int, *args) -> None: ...", runtime="def j1(a): pass", error="j1"
        )
        yield Case(
            stub="def j2(a: int) -> None: ...", runtime="def j2(a, *args): pass", error="j2"
        )
        yield Case(
            stub="def j3(a, b, c) -> None: ...", runtime="def j3(a, *args, c): pass", error="j3"
        )
        yield Case(stub="def k1(a, **kwargs) -> None: ...", runtime="def k1(a): pass", error="k1")
        yield Case(
            # In theory an error, but led to worse results in practice
            stub="def k2(a) -> None: ...",
            runtime="def k2(a, **kwargs): pass",
            error=None,
        )
        yield Case(
            stub="def k3(a, b) -> None: ...", runtime="def k3(a, **kwargs): pass", error="k3"
        )
        yield Case(
            stub="def k4(a, *, b) -> None: ...", runtime="def k4(a, **kwargs): pass", error=None
        )
        yield Case(
            stub="def k5(a, *, b) -> None: ...",
            runtime="def k5(a, *, b, c, **kwargs): pass",
            error="k5",
        )

    @collect_cases
    def test_overload(self) -> Iterator[Case]:
        yield Case(
            stub="""
            from typing import overload

            @overload
            def f1(a: int, *, c: int = ...) -> int: ...
            @overload
            def f1(a: int, b: int, c: int = ...) -> str: ...
            """,
            runtime="def f1(a, b = 0, c = 0): pass",
            error=None,
        )
        yield Case(
            stub="""
            @overload
            def f2(a: int, *, c: int = ...) -> int: ...
            @overload
            def f2(a: int, b: int, c: int = ...) -> str: ...
            """,
            runtime="def f2(a, b, c = 0): pass",
            error="f2",
        )
        yield Case(
            stub="""
            @overload
            def f3(a: int) -> int: ...
            @overload
            def f3(a: int, b: str) -> str: ...
            """,
            runtime="def f3(a, b = None): pass",
            error="f3",
        )
        yield Case(
            stub="""
            @overload
            def f4(a: int, *args, b: int, **kwargs) -> int: ...
            @overload
            def f4(a: str, *args, b: int, **kwargs) -> str: ...
            """,
            runtime="def f4(a, *args, b, **kwargs): pass",
            error=None,
        )
        if sys.version_info >= (3, 8):
            yield Case(
                stub="""
                @overload
                def f5(__a: int) -> int: ...
                @overload
                def f5(__b: str) -> str: ...
                """,
                runtime="def f5(x, /): pass",
                error=None,
            )

    @collect_cases
    def test_property(self) -> Iterator[Case]:
        yield Case(
            stub="""
            class Good:
                @property
                def f(self) -> int: ...
            """,
            runtime="""
            class Good:
                @property
                def f(self) -> int: return 1
            """,
            error=None,
        )
        yield Case(
            stub="""
            class Bad:
                @property
                def f(self) -> int: ...
            """,
            runtime="""
            class Bad:
                def f(self) -> int: return 1
            """,
            error="Bad.f",
        )
        yield Case(
            stub="""
            class GoodReadOnly:
                @property
                def f(self) -> int: ...
            """,
            runtime="""
            class GoodReadOnly:
                f = 1
            """,
            error=None,
        )
        yield Case(
            stub="""
            class BadReadOnly:
                @property
                def f(self) -> str: ...
            """,
            runtime="""
            class BadReadOnly:
                f = 1
            """,
            error="BadReadOnly.f",
        )

    @collect_cases
    def test_var(self) -> Iterator[Case]:
        yield Case(stub="x1: int", runtime="x1 = 5", error=None)
        yield Case(stub="x2: str", runtime="x2 = 5", error="x2")
        yield Case("from typing import Tuple", "", None)  # dummy case
        yield Case(
            stub="""
            x3: Tuple[int, int]
            """,
            runtime="x3 = (1, 3)",
            error=None,
        )
        yield Case(
            stub="""
            x4: Tuple[int, int]
            """,
            runtime="x4 = (1, 3, 5)",
            error="x4",
        )
        yield Case(
            stub="""
            class X:
                f: int
            """,
            runtime="""
            class X:
                def __init__(self):
                    self.f = "asdf"
            """,
            error=None,
        )

    @collect_cases
    def test_enum(self) -> Iterator[Case]:
        yield Case(
            stub="""
            import enum
            class X(enum.Enum):
                a: int
                b: str
                c: str
            """,
            runtime="""
            import enum
            class X(enum.Enum):
                a = 1
                b = "asdf"
                c = 2
            """,
            error="X.c",
        )

    @collect_cases
    def test_decorator(self) -> Iterator[Case]:
        yield Case(
            stub="""
            from typing import Any, Callable
            def decorator(f: Callable[[], int]) -> Callable[..., Any]: ...
            @decorator
            def f() -> Any: ...
            """,
            runtime="""
            def decorator(f): return f
            @decorator
            def f(): return 3
            """,
            error=None,
        )

    @collect_cases
    def test_missing(self) -> Iterator[Case]:
        yield Case(stub="x = 5", runtime="", error="x")
        yield Case(stub="def f(): ...", runtime="", error="f")
        yield Case(stub="class X: ...", runtime="", error="X")
        yield Case(
            stub="""
            from typing import overload
            @overload
            def h(x: int): ...
            @overload
            def h(x: str): ...
            """,
            runtime="",
            error="h",
        )
        yield Case("", "__all__ = []", None)  # dummy case
        yield Case(stub="", runtime="__all__ += ['y']\ny = 5", error="y")
        yield Case(stub="", runtime="__all__ += ['g']\ndef g(): pass", error="g")


def remove_color_code(s: str) -> str:
    return re.sub("\\x1b.*?m", "", s)  # this works!


class StubtestMiscUnit(unittest.TestCase):
    def test_output(self) -> None:
        output = run_stubtest(
            stub="def bad(number: int, text: str) -> None: ...",
            runtime="def bad(num, text): pass",
            options=[],
        )
        expected = (
            'error: {0}.bad is inconsistent, stub argument "number" differs from runtime '
            'argument "num"\nStub: at line 1\ndef (number: builtins.int, text: builtins.str)\n'
            "Runtime: at line 1 in file {0}.py\ndef (num, text)\n\n".format(TEST_MODULE_NAME)
        )
        assert remove_color_code(output) == expected

        output = run_stubtest(
            stub="def bad(number: int, text: str) -> None: ...",
            runtime="def bad(num, text): pass",
            options=["--concise"],
        )
        expected = (
            "{}.bad is inconsistent, "
            'stub argument "number" differs from runtime argument "num"\n'.format(TEST_MODULE_NAME)
        )
        assert remove_color_code(output) == expected

    def test_ignore_flags(self) -> None:
        output = run_stubtest(
            stub="", runtime="__all__ = ['f']\ndef f(): pass", options=["--ignore-missing-stub"]
        )
        assert not output

        output = run_stubtest(
            stub="def f(__a): ...", runtime="def f(a): pass", options=["--ignore-positional-only"]
        )
        assert not output

    def test_whitelist(self) -> None:
        # Can't use this as a context because Windows
        whitelist = tempfile.NamedTemporaryFile(mode="w", delete=False)
        try:
            with whitelist:
                whitelist.write("{}.bad\n# a comment".format(TEST_MODULE_NAME))

            output = run_stubtest(
                stub="def bad(number: int, text: str) -> None: ...",
                runtime="def bad(num, text) -> None: pass",
                options=["--whitelist", whitelist.name],
            )
            assert not output

            output = run_stubtest(stub="", runtime="", options=["--whitelist", whitelist.name])
            assert output == "note: unused whitelist entry {}.bad\n".format(TEST_MODULE_NAME)
        finally:
            os.unlink(whitelist.name)

    def test_mypy_build(self) -> None:
        output = run_stubtest(stub="+", runtime="", options=[])
        assert remove_color_code(output) == (
            "error: failed mypy compile.\n{}.pyi:1: "
            "error: invalid syntax\n".format(TEST_MODULE_NAME)
        )

        output = run_stubtest(stub="def f(): ...\ndef f(): ...", runtime="", options=[])
        assert remove_color_code(output) == (
            "error: failed mypy build.\n{}.pyi:2: "
            "error: Name 'f' already defined on line 1\n".format(TEST_MODULE_NAME)
        )

    def test_missing_stubs(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            test_stubs(parse_options(["not_a_module"]))
        assert "error: not_a_module failed to find stubs" in remove_color_code(output.getvalue())

    def test_get_typeshed_stdlib_modules(self) -> None:
        stdlib = mypy.stubtest.get_typeshed_stdlib_modules(None)
        assert "builtins" in stdlib
        assert "os" in stdlib

    def test_signature(self) -> None:
        def f(a: int, b: int, *, c: int, d: int = 0, **kwargs: Any) -> None:
            pass

        assert (
            str(mypy.stubtest.Signature.from_inspect_signature(inspect.signature(f)))
            == "def (a, b, *, c, d = ..., **kwargs)"
        )


class StubtestIntegration(unittest.TestCase):
    def test_typeshed(self) -> None:
        # check we don't crash while checking typeshed
        test_stubs(parse_options(["--check-typeshed"]))
