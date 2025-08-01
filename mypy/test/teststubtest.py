from __future__ import annotations

import contextlib
import inspect
import io
import os
import re
import sys
import tempfile
import textwrap
import unittest
from collections.abc import Iterator
from typing import Any, Callable

import mypy.stubtest
from mypy.stubtest import parse_options, test_stubs
from mypy.test.data import root_dir


@contextlib.contextmanager
def use_tmp_dir(mod_name: str) -> Iterator[str]:
    current = os.getcwd()
    current_syspath = sys.path.copy()
    with tempfile.TemporaryDirectory() as tmp:
        try:
            os.chdir(tmp)
            if sys.path[0] != tmp:
                sys.path.insert(0, tmp)
            yield tmp
        finally:
            sys.path = current_syspath.copy()
            if mod_name in sys.modules:
                del sys.modules[mod_name]

            os.chdir(current)


TEST_MODULE_NAME = "test_module"


stubtest_typing_stub = """
Any = object()

class _SpecialForm:
    def __getitem__(self, typeargs: Any) -> object: ...

Callable: _SpecialForm = ...
Generic: _SpecialForm = ...
Protocol: _SpecialForm = ...
Union: _SpecialForm = ...
ClassVar: _SpecialForm = ...

Final = 0
Literal = 0
TypedDict = 0

class TypeVar:
    def __init__(self, name, covariant: bool = ..., contravariant: bool = ...) -> None: ...

class ParamSpec:
    def __init__(self, name: str) -> None: ...

AnyStr = TypeVar("AnyStr", str, bytes)
_T = TypeVar("_T")
_T_co = TypeVar("_T_co", covariant=True)
_K = TypeVar("_K")
_V = TypeVar("_V")
_S = TypeVar("_S", contravariant=True)
_R = TypeVar("_R", covariant=True)

class Coroutine(Generic[_T_co, _S, _R]): ...
class Iterable(Generic[_T_co]): ...
class Iterator(Iterable[_T_co]): ...
class Mapping(Generic[_K, _V]): ...
class Match(Generic[AnyStr]): ...
class Sequence(Iterable[_T_co]): ...
class Tuple(Sequence[_T_co]): ...
class NamedTuple(tuple[Any, ...]): ...
class _TypedDict(Mapping[str, object]):
    __required_keys__: ClassVar[frozenset[str]]
    __optional_keys__: ClassVar[frozenset[str]]
    __total__: ClassVar[bool]
    __readonly_keys__: ClassVar[frozenset[str]]
    __mutable_keys__: ClassVar[frozenset[str]]
def overload(func: _T) -> _T: ...
def type_check_only(func: _T) -> _T: ...
def final(func: _T) -> _T: ...
"""

stubtest_builtins_stub = """
from typing import Generic, Mapping, Sequence, TypeVar, overload

T = TypeVar('T')
T_co = TypeVar('T_co', covariant=True)
KT = TypeVar('KT')
VT = TypeVar('VT')

class object:
    __module__: str
    def __init__(self) -> None: pass
    def __repr__(self) -> str: pass
class type: ...

class tuple(Sequence[T_co], Generic[T_co]):
    def __ge__(self, __other: tuple[T_co, ...]) -> bool: pass

class dict(Mapping[KT, VT]): ...

class frozenset(Generic[T]): ...

class function: pass
class ellipsis: pass

class int: ...
class float: ...
class bool(int): ...
class str: ...
class bytes: ...

class list(Sequence[T]): ...

def property(f: T) -> T: ...
def classmethod(f: T) -> T: ...
def staticmethod(f: T) -> T: ...
"""

stubtest_enum_stub = """
import sys
from typing import Any, TypeVar, Iterator

_T = TypeVar('_T')

class EnumMeta(type):
    def __len__(self) -> int: pass
    def __iter__(self: type[_T]) -> Iterator[_T]: pass
    def __reversed__(self: type[_T]) -> Iterator[_T]: pass
    def __getitem__(self: type[_T], name: str) -> _T: pass

class Enum(metaclass=EnumMeta):
    def __new__(cls: type[_T], value: object) -> _T: pass
    def __repr__(self) -> str: pass
    def __str__(self) -> str: pass
    def __format__(self, format_spec: str) -> str: pass
    def __hash__(self) -> Any: pass
    def __reduce_ex__(self, proto: Any) -> Any: pass
    name: str
    value: Any

class Flag(Enum):
    def __or__(self: _T, other: _T) -> _T: pass
    def __and__(self: _T, other: _T) -> _T: pass
    def __xor__(self: _T, other: _T) -> _T: pass
    def __invert__(self: _T) -> _T: pass
    if sys.version_info >= (3, 11):
        __ror__ = __or__
        __rand__ = __and__
        __rxor__ = __xor__
"""


def run_stubtest_with_stderr(
    stub: str, runtime: str, options: list[str], config_file: str | None = None
) -> tuple[str, str]:
    with use_tmp_dir(TEST_MODULE_NAME) as tmp_dir:
        with open("builtins.pyi", "w") as f:
            f.write(stubtest_builtins_stub)
        with open("typing.pyi", "w") as f:
            f.write(stubtest_typing_stub)
        with open("enum.pyi", "w") as f:
            f.write(stubtest_enum_stub)
        with open(f"{TEST_MODULE_NAME}.pyi", "w") as f:
            f.write(stub)
        with open(f"{TEST_MODULE_NAME}.py", "w") as f:
            f.write(runtime)
        if config_file:
            with open(f"{TEST_MODULE_NAME}_config.ini", "w") as f:
                f.write(config_file)
            options = options + ["--mypy-config-file", f"{TEST_MODULE_NAME}_config.ini"]
        output = io.StringIO()
        outerr = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(outerr):
            test_stubs(parse_options([TEST_MODULE_NAME] + options), use_builtins_fixtures=True)
    filtered_output = remove_color_code(
        output.getvalue()
        # remove cwd as it's not available from outside
        .replace(os.path.realpath(tmp_dir) + os.sep, "").replace(tmp_dir + os.sep, "")
    )
    filtered_outerr = remove_color_code(
        outerr.getvalue()
        # remove cwd as it's not available from outside
        .replace(os.path.realpath(tmp_dir) + os.sep, "").replace(tmp_dir + os.sep, "")
    )
    return filtered_output, filtered_outerr


def run_stubtest(
    stub: str, runtime: str, options: list[str], config_file: str | None = None
) -> str:
    return run_stubtest_with_stderr(stub, runtime, options, config_file)[0]


class Case:
    def __init__(self, stub: str, runtime: str, error: str | None) -> None:
        self.stub = stub
        self.runtime = runtime
        self.error = error


def collect_cases(fn: Callable[..., Iterator[Case]]) -> Callable[..., None]:
    """run_stubtest used to be slow, so we used this decorator to combine cases.

    If you're reading this and bored, feel free to refactor this and make it more like
    other mypy tests.

    """

    def test(*args: Any, **kwargs: Any) -> None:
        cases = list(fn(*args, **kwargs))
        expected_errors = set()
        for c in cases:
            if c.error is None:
                continue
            expected_error = c.error
            if expected_error == "":
                expected_error = TEST_MODULE_NAME
            elif not expected_error.startswith(f"{TEST_MODULE_NAME}."):
                expected_error = f"{TEST_MODULE_NAME}.{expected_error}"
            assert expected_error not in expected_errors, (
                "collect_cases merges cases into a single stubtest invocation; we already "
                "expect an error for {}".format(expected_error)
            )
            expected_errors.add(expected_error)
        output = run_stubtest(
            stub="\n\n".join(textwrap.dedent(c.stub.lstrip("\n")) for c in cases),
            runtime="\n\n".join(textwrap.dedent(c.runtime.lstrip("\n")) for c in cases),
            options=["--generate-allowlist"],
        )

        actual_errors = set(output.splitlines())
        if actual_errors != expected_errors:
            output = run_stubtest(
                stub="\n\n".join(textwrap.dedent(c.stub.lstrip("\n")) for c in cases),
                runtime="\n\n".join(textwrap.dedent(c.runtime.lstrip("\n")) for c in cases),
                options=[],
            )
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
    def test_coroutines(self) -> Iterator[Case]:
        yield Case(stub="def bar() -> int: ...", runtime="async def bar(): return 5", error="bar")
        # Don't error for this one -- we get false positives otherwise
        yield Case(stub="async def foo() -> int: ...", runtime="def foo(): return 5", error=None)
        yield Case(stub="def baz() -> int: ...", runtime="def baz(): return 5", error=None)
        yield Case(
            stub="async def bingo() -> int: ...", runtime="async def bingo(): return 5", error=None
        )

    @collect_cases
    def test_arg_name(self) -> Iterator[Case]:
        yield Case(
            stub="def bad(number: int, text: str) -> None: ...",
            runtime="def bad(num, text) -> None: pass",
            error="bad",
        )
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
        yield Case(
            stub="""def dunder_name(__x: int) -> None: ...""",
            runtime="""def dunder_name(__x: int) -> None: ...""",
            error=None,
        )
        yield Case(
            stub="""def dunder_name_posonly(__x: int, /) -> None: ...""",
            runtime="""def dunder_name_posonly(__x: int) -> None: ...""",
            error=None,
        )
        yield Case(
            stub="""def dunder_name_bad(x: int) -> None: ...""",
            runtime="""def dunder_name_bad(__x: int) -> None: ...""",
            error="dunder_name_bad",
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
        yield Case(
            stub="def stub_posonly_570(number: int, /, text: str) -> None: ...",
            runtime="def stub_posonly_570(number, text): pass",
            error="stub_posonly_570",
        )

    @collect_cases
    def test_private_parameters(self) -> Iterator[Case]:
        # Private parameters can optionally be omitted.
        yield Case(
            stub="def priv_pos_arg_missing() -> None: ...",
            runtime="def priv_pos_arg_missing(_p1=None): pass",
            error=None,
        )
        yield Case(
            stub="def multi_priv_args() -> None: ...",
            runtime="def multi_priv_args(_p='', _q=''): pass",
            error=None,
        )
        yield Case(
            stub="def priv_kwarg_missing() -> None: ...",
            runtime="def priv_kwarg_missing(*, _p2=''): pass",
            error=None,
        )
        # But if they are included, they must be correct.
        yield Case(
            stub="def priv_pos_arg_wrong(_p: int = ...) -> None: ...",
            runtime="def priv_pos_arg_wrong(_p=None): pass",
            error="priv_pos_arg_wrong",
        )
        yield Case(
            stub="def priv_kwarg_wrong(*, _p: int = ...) -> None: ...",
            runtime="def priv_kwarg_wrong(*, _p=None): pass",
            error="priv_kwarg_wrong",
        )
        # Private parameters must have a default and start with exactly one
        # underscore.
        yield Case(
            stub="def pos_arg_no_default() -> None: ...",
            runtime="def pos_arg_no_default(_np): pass",
            error="pos_arg_no_default",
        )
        yield Case(
            stub="def kwarg_no_default() -> None: ...",
            runtime="def kwarg_no_default(*, _np): pass",
            error="kwarg_no_default",
        )
        yield Case(
            stub="def double_underscore_pos_arg() -> None: ...",
            runtime="def double_underscore_pos_arg(__np = None): pass",
            error="double_underscore_pos_arg",
        )
        yield Case(
            stub="def double_underscore_kwarg() -> None: ...",
            runtime="def double_underscore_kwarg(*, __np = None): pass",
            error="double_underscore_kwarg",
        )
        # But spot parameters that are accidentally not marked kw-only and
        # vice-versa.
        yield Case(
            stub="def priv_arg_is_kwonly(_p=...) -> None: ...",
            runtime="def priv_arg_is_kwonly(*, _p=''): pass",
            error="priv_arg_is_kwonly",
        )
        yield Case(
            stub="def priv_arg_is_positional(*, _p=...) -> None: ...",
            runtime="def priv_arg_is_positional(_p=''): pass",
            error="priv_arg_is_positional",
        )
        # Private parameters not at the end of the parameter list must be
        # included so that users can pass the following arguments using
        # positional syntax.
        yield Case(
            stub="def priv_args_not_at_end(*, q='') -> None: ...",
            runtime="def priv_args_not_at_end(_p='', q=''): pass",
            error="priv_args_not_at_end",
        )

    @collect_cases
    def test_default_presence(self) -> Iterator[Case]:
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
            _T = TypeVar("_T", bound=str)
            def f6(text: _T = ...) -> None: ...
            """,
            runtime="def f6(text = None): pass",
            error="f6",
        )

    @collect_cases
    def test_default_value(self) -> Iterator[Case]:
        yield Case(
            stub="def f1(text: str = 'x') -> None: ...",
            runtime="def f1(text = 'y'): pass",
            error="f1",
        )
        yield Case(
            stub='def f2(text: bytes = b"x\'") -> None: ...',
            runtime='def f2(text = b"x\'"): pass',
            error=None,
        )
        yield Case(
            stub='def f3(text: bytes = b"y\'") -> None: ...',
            runtime='def f3(text = b"x\'"): pass',
            error="f3",
        )
        yield Case(
            stub="def f4(text: object = 1) -> None: ...",
            runtime="def f4(text = 1.0): pass",
            error="f4",
        )
        yield Case(
            stub="def f5(text: object = True) -> None: ...",
            runtime="def f5(text = 1): pass",
            error="f5",
        )
        yield Case(
            stub="def f6(text: object = True) -> None: ...",
            runtime="def f6(text = True): pass",
            error=None,
        )
        yield Case(
            stub="def f7(text: object = not True) -> None: ...",
            runtime="def f7(text = False): pass",
            error=None,
        )
        yield Case(
            stub="def f8(text: object = not True) -> None: ...",
            runtime="def f8(text = True): pass",
            error="f8",
        )
        yield Case(
            stub="def f9(text: object = {1: 2}) -> None: ...",
            runtime="def f9(text = {1: 3}): pass",
            error="f9",
        )
        yield Case(
            stub="def f10(text: object = [1, 2]) -> None: ...",
            runtime="def f10(text = [1, 2]): pass",
            error=None,
        )

        # Simulate "<unrepresentable>"
        yield Case(
            stub="def f11() -> None: ...",
            runtime="""
            def f11(text=None) -> None: pass
            f11.__text_signature__ = "(text=<unrepresentable>)"
            """,
            error="f11",
        )

        # Simulate numpy ndarray.__bool__ that raises an error
        yield Case(
            stub="def f12(x=1): ...",
            runtime="""
            class _ndarray:
                def __eq__(self, obj): return self
                def __bool__(self): raise ValueError
            def f12(x=_ndarray()) -> None: pass
            """,
            error="f12",
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
        yield Case(
            stub="def k6(a, *, b, **kwargs) -> None: ...",
            runtime="def k6(a, *, b, c, **kwargs): pass",
            error="k6",
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
        yield Case(
            stub="""
            from typing import final
            from typing_extensions import deprecated
            class Foo:
                @overload
                @final
                def f6(self, __a: int) -> int: ...
                @overload
                @deprecated("evil")
                def f6(self, __b: str) -> str: ...
            """,
            runtime="""
            class Foo:
                def f6(self, x, /): pass
            """,
            error=None,
        )
        yield Case(
            stub="""
            @overload
            def f7(a: int, /) -> int: ...
            @overload
            def f7(b: str, /) -> str: ...
            """,
            runtime="def f7(x, /): pass",
            error=None,
        )
        yield Case(
            stub="""
            @overload
            def f8(a: int, c: int = 0, /) -> int: ...
            @overload
            def f8(b: str, d: int, /) -> str: ...
            """,
            runtime="def f8(x, y, /): pass",
            error="f8",
        )
        yield Case(
            stub="""
            @overload
            def f9(a: int, c: int = 0, /) -> int: ...
            @overload
            def f9(b: str, d: int, /) -> str: ...
            """,
            runtime="def f9(x, y=0, /): pass",
            error=None,
        )
        yield Case(
            stub="""
            class Bar:
                @overload
                def f1(self) -> int: ...
                @overload
                def f1(self, a: int, /) -> int: ...

                @overload
                def f2(self, a: int, /) -> int: ...
                @overload
                def f2(self, a: str, /) -> int: ...
            """,
            runtime="""
            class Bar:
                def f1(self, *a) -> int: ...
                def f2(self, *a) -> int: ...
            """,
            error=None,
        )

    @collect_cases
    def test_property(self) -> Iterator[Case]:
        yield Case(
            stub="""
            class Good:
                @property
                def read_only_attr(self) -> int: ...
                read_only_attr_alias = read_only_attr
            """,
            runtime="""
            class Good:
                @property
                def read_only_attr(self): return 1
                read_only_attr_alias = read_only_attr
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
        yield Case(
            stub="""
            class Y:
                @property
                def read_only_attr(self) -> int: ...
                @read_only_attr.setter
                def read_only_attr(self, val: int) -> None: ...
            """,
            runtime="""
            class Y:
                @property
                def read_only_attr(self): return 5
            """,
            error="Y.read_only_attr",
        )
        yield Case(
            stub="""
            class Z:
                @property
                def read_write_attr(self) -> int: ...
                @read_write_attr.setter
                def read_write_attr(self, val: int) -> None: ...
                read_write_attr_alias = read_write_attr
            """,
            runtime="""
            class Z:
                @property
                def read_write_attr(self): return self._val
                @read_write_attr.setter
                def read_write_attr(self, val): self._val = val
                read_write_attr_alias = read_write_attr
            """,
            error=None,
        )
        yield Case(
            stub="""
            class FineAndDandy:
                @property
                def attr(self) -> int: ...
            """,
            runtime="""
            class _EvilDescriptor:
                def __get__(self, instance, ownerclass=None):
                    if instance is None:
                        raise AttributeError('no')
                    return 42
                def __set__(self, instance, value):
                    raise AttributeError('no')

            class FineAndDandy:
                attr = _EvilDescriptor()
            """,
            error=None,
        )

    @collect_cases
    def test_cached_property(self) -> Iterator[Case]:
        yield Case(
            stub="""
            from functools import cached_property
            class Good:
                @cached_property
                def read_only_attr(self) -> int: ...
                @cached_property
                def read_only_attr2(self) -> int: ...
            """,
            runtime="""
            import functools as ft
            from functools import cached_property
            class Good:
                @cached_property
                def read_only_attr(self): return 1
                @ft.cached_property
                def read_only_attr2(self): return 1
            """,
            error=None,
        )
        yield Case(
            stub="""
            from functools import cached_property
            class Bad:
                @cached_property
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
            from functools import cached_property
            class GoodCachedAttr:
                @cached_property
                def f(self) -> int: ...
            """,
            runtime="""
            class GoodCachedAttr:
                f = 1
            """,
            error=None,
        )
        yield Case(
            stub="""
            from functools import cached_property
            class BadCachedAttr:
                @cached_property
                def f(self) -> str: ...
            """,
            runtime="""
            class BadCachedAttr:
                f = 1
            """,
            error="BadCachedAttr.f",
        )
        yield Case(
            stub="""
            from functools import cached_property
            from typing import final
            class FinalGood:
                @cached_property
                @final
                def attr(self) -> int: ...
            """,
            runtime="""
            from functools import cached_property
            from typing import final
            class FinalGood:
                @cached_property
                @final
                def attr(self):
                    return 1
            """,
            error=None,
        )
        yield Case(
            stub="""
            from functools import cached_property
            class FinalBad:
                @cached_property
                def attr(self) -> int: ...
            """,
            runtime="""
            from functools import cached_property
            from typing_extensions import final
            class FinalBad:
                @cached_property
                @final
                def attr(self):
                    return 1
            """,
            error="FinalBad.attr",
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
        yield Case(stub="x5: int", runtime="def x5(a, b): pass", error="x5")
        yield Case(
            stub="def foo(a: int, b: int) -> None: ...\nx6 = foo",
            runtime="def foo(a, b): pass\ndef x6(c, d): pass",
            error="x6",
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
        yield Case(
            stub="""
            class Y:
                read_only_attr: int
            """,
            runtime="""
            class Y:
                @property
                def read_only_attr(self): return 5
            """,
            error="Y.read_only_attr",
        )
        yield Case(
            stub="""
            class Z:
                read_write_attr: int
            """,
            runtime="""
            class Z:
                @property
                def read_write_attr(self): return self._val
                @read_write_attr.setter
                def read_write_attr(self, val): self._val = val
            """,
            error=None,
        )

    @collect_cases
    def test_type_alias(self) -> Iterator[Case]:
        yield Case(
            stub="""
            import collections.abc
            import re
            import typing
            from typing import Callable, Dict, Generic, Iterable, List, Match, Tuple, TypeVar, Union
            """,
            runtime="""
            import collections.abc
            import re
            from typing import Callable, Dict, Generic, Iterable, List, Match, Tuple, TypeVar, Union
            """,
            error=None,
        )
        yield Case(
            stub="""
            class X:
                def f(self) -> None: ...
            Y = X
            """,
            runtime="""
            class X:
                def f(self) -> None: ...
            class Y: ...
            """,
            error="Y.f",
        )
        yield Case(stub="A = Tuple[int, str]", runtime="A = (int, str)", error="A")
        # Error if an alias isn't present at runtime...
        yield Case(stub="B = str", runtime="", error="B")
        # ... but only if the alias isn't private
        yield Case(stub="_C = int", runtime="", error=None)
        yield Case(
            stub="""
            D = tuple[str, str]
            E = Tuple[int, int, int]
            F = Tuple[str, int]
            """,
            runtime="""
            D = Tuple[str, str]
            E = Tuple[int, int, int]
            F = List[str]
            """,
            error="F",
        )
        yield Case(
            stub="""
            G = str | int
            H = Union[str, bool]
            I = str | int
            """,
            runtime="""
            G = Union[str, int]
            H = Union[str, bool]
            I = str
            """,
            error="I",
        )
        yield Case(
            stub="""
            K = dict[str, str]
            L = Dict[int, int]
            KK = collections.abc.Iterable[str]
            LL = typing.Iterable[str]
            """,
            runtime="""
            K = Dict[str, str]
            L = Dict[int, int]
            KK = Iterable[str]
            LL = Iterable[str]
            """,
            error=None,
        )
        yield Case(
            stub="""
            _T = TypeVar("_T")
            class _Spam(Generic[_T]):
                def foo(self) -> None: ...
            IntFood = _Spam[int]
            """,
            runtime="""
            _T = TypeVar("_T")
            class _Bacon(Generic[_T]):
                def foo(self, arg): pass
            IntFood = _Bacon[int]
            """,
            error="IntFood.foo",
        )
        yield Case(stub="StrList = list[str]", runtime="StrList = ['foo', 'bar']", error="StrList")
        yield Case(
            stub="""
            N = typing.Callable[[str], bool]
            O = collections.abc.Callable[[int], str]
            P = typing.Callable[[str], bool]
            """,
            runtime="""
            N = Callable[[str], bool]
            O = Callable[[int], str]
            P = int
            """,
            error="P",
        )
        yield Case(
            stub="""
            class Foo:
                class Bar: ...
            BarAlias = Foo.Bar
            """,
            runtime="""
            class Foo:
                class Bar: pass
            BarAlias = Foo.Bar
            """,
            error=None,
        )
        yield Case(
            stub="""
            from io import StringIO
            StringIOAlias = StringIO
            """,
            runtime="""
            from _io import StringIO
            StringIOAlias = StringIO
            """,
            error=None,
        )
        yield Case(stub="M = Match[str]", runtime="M = Match[str]", error=None)
        yield Case(
            stub="""
            class Baz:
                def fizz(self) -> None: ...
            BazAlias = Baz
            """,
            runtime="""
            class Baz:
                def fizz(self): pass
            BazAlias = Baz
            Baz.__name__ = Baz.__qualname__ = Baz.__module__ = "New"
            """,
            error=None,
        )
        yield Case(
            stub="""
            class FooBar:
                __module__: None  # type: ignore
                def fizz(self) -> None: ...
            FooBarAlias = FooBar
            """,
            runtime="""
            class FooBar:
                def fizz(self): pass
            FooBarAlias = FooBar
            FooBar.__module__ = None
            """,
            error=None,
        )
        if sys.version_info >= (3, 10):
            yield Case(
                stub="""
                Q = Dict[str, str]
                R = dict[int, int]
                S = Tuple[int, int]
                T = tuple[str, str]
                U = int | str
                V = Union[int, str]
                W = typing.Callable[[str], bool]
                Z = collections.abc.Callable[[str], bool]
                QQ = typing.Iterable[str]
                RR = collections.abc.Iterable[str]
                MM = typing.Match[str]
                MMM = re.Match[str]
                """,
                runtime="""
                Q = dict[str, str]
                R = dict[int, int]
                S = tuple[int, int]
                T = tuple[str, str]
                U = int | str
                V = int | str
                W = collections.abc.Callable[[str], bool]
                Z = collections.abc.Callable[[str], bool]
                QQ = collections.abc.Iterable[str]
                RR = collections.abc.Iterable[str]
                MM = re.Match[str]
                MMM = re.Match[str]
                """,
                error=None,
            )

    @collect_cases
    def test_enum(self) -> Iterator[Case]:
        yield Case(stub="import enum", runtime="import enum", error=None)
        yield Case(
            stub="""
            class X(enum.Enum):
                a = ...
                b = "asdf"
                c = "oops"
            """,
            runtime="""
            class X(enum.Enum):
                a = 1
                b = "asdf"
                c = 2
            """,
            error="X.c",
        )
        yield Case(
            stub="""
            class Flags1(enum.Flag):
                a = ...
                b = 2
            def foo(x: Flags1 = ...) -> None: ...
            """,
            runtime="""
            class Flags1(enum.Flag):
                a = 1
                b = 2
            def foo(x=Flags1.a|Flags1.b): pass
            """,
            error=None,
        )
        yield Case(
            stub="""
            class Flags2(enum.Flag):
                a = ...
                b = 2
            def bar(x: Flags2 | None = None) -> None: ...
            """,
            runtime="""
            class Flags2(enum.Flag):
                a = 1
                b = 2
            def bar(x=Flags2.a|Flags2.b): pass
            """,
            error="bar",
        )
        yield Case(
            stub="""
            class Flags3(enum.Flag):
                a = ...
                b = 2
            def baz(x: Flags3 | None = ...) -> None: ...
            """,
            runtime="""
            class Flags3(enum.Flag):
                a = 1
                b = 2
            def baz(x=Flags3(0)): pass
            """,
            error=None,
        )
        yield Case(
            runtime="""
            import enum
            class SomeObject: ...

            class WeirdEnum(enum.Enum):
                a = SomeObject()
                b = SomeObject()
            """,
            stub="""
            import enum
            class SomeObject: ...
            class WeirdEnum(enum.Enum):
                _value_: SomeObject
                a = ...
                b = ...
            """,
            error=None,
        )
        yield Case(
            stub="""
            class Flags4(enum.Flag):
                a = 1
                b = 2
            def spam(x: Flags4 | None = None) -> None: ...
            """,
            runtime="""
            class Flags4(enum.Flag):
                a = 1
                b = 2
            def spam(x=Flags4(0)): pass
            """,
            error="spam",
        )
        yield Case(
            stub="""
            from typing import Final, Literal
            class BytesEnum(bytes, enum.Enum):
                a = b'foo'
            FOO: Literal[BytesEnum.a]
            BAR: Final = BytesEnum.a
            BAZ: BytesEnum
            EGGS: bytes
            """,
            runtime="""
            class BytesEnum(bytes, enum.Enum):
                a = b'foo'
            FOO = BytesEnum.a
            BAR = BytesEnum.a
            BAZ = BytesEnum.a
            EGGS = BytesEnum.a
            """,
            error=None,
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
    def test_all_at_runtime_not_stub(self) -> Iterator[Case]:
        yield Case(
            stub="Z: int",
            runtime="""
            __all__ = []
            Z = 5""",
            error="__all__",
        )

    @collect_cases
    def test_all_in_stub_not_at_runtime(self) -> Iterator[Case]:
        yield Case(stub="__all__ = ()", runtime="", error="__all__")

    @collect_cases
    def test_all_in_stub_different_to_all_at_runtime(self) -> Iterator[Case]:
        # We *should* emit an error with the module name itself + __all__,
        # if the stub *does* define __all__,
        # but the stub's __all__ is inconsistent with the runtime's __all__
        yield Case(
            stub="""
            __all__ = ['foo']
            foo: str
            """,
            runtime="""
            __all__ = []
            foo = 'foo'
            """,
            error="__all__",
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
        yield Case(stub="", runtime="__all__ = []", error="__all__")  # dummy case
        yield Case(stub="", runtime="__all__ += ['y']\ny = 5", error="y")
        yield Case(stub="", runtime="__all__ += ['g']\ndef g(): pass", error="g")
        # Here we should only check that runtime has B, since the stub explicitly re-exports it
        yield Case(
            stub="from mystery import A, B as B, C as D  # type: ignore", runtime="", error="B"
        )
        yield Case(
            stub="class Y: ...",
            runtime="__all__ += ['Y']\nclass Y:\n  def __or__(self, other): return self|other",
            error="Y.__or__",
        )
        yield Case(
            stub="class Z: ...",
            runtime="__all__ += ['Z']\nclass Z:\n  def __reduce__(self): return (Z,)",
            error=None,
        )
        # __call__ exists on type, so it appears to exist on the class.
        # This checks that we identify it as missing at runtime anyway.
        yield Case(
            stub="""
            class ClassWithMetaclassOverride:
                def __call__(*args, **kwds): ...
            """,
            runtime="class ClassWithMetaclassOverride: ...",
            error="ClassWithMetaclassOverride.__call__",
        )
        # Test that we ignore object.__setattr__ and object.__delattr__ inheritance
        yield Case(
            stub="""
            from typing import Any
            class FakeSetattrClass:
                def __setattr__(self, name: str, value: Any, /) -> None: ...
            """,
            runtime="class FakeSetattrClass: ...",
            error="FakeSetattrClass.__setattr__",
        )
        yield Case(
            stub="""
            class FakeDelattrClass:
                def __delattr__(self, name: str, /) -> None: ...
            """,
            runtime="class FakeDelattrClass: ...",
            error="FakeDelattrClass.__delattr__",
        )

    @collect_cases
    def test_missing_no_runtime_all(self) -> Iterator[Case]:
        yield Case(stub="", runtime="import sys", error=None)
        yield Case(stub="", runtime="def g(): ...", error="g")
        yield Case(stub="", runtime="CONSTANT = 0", error="CONSTANT")
        yield Case(stub="", runtime="import re; constant = re.compile('foo')", error="constant")
        yield Case(stub="", runtime="from json.scanner import NUMBER_RE", error=None)
        yield Case(stub="", runtime="from string import ascii_letters", error=None)

    @collect_cases
    def test_missing_no_runtime_all_terrible(self) -> Iterator[Case]:
        yield Case(
            stub="",
            runtime="""
import sys
import types
import __future__
_m = types.SimpleNamespace()
_m.annotations = __future__.annotations
sys.modules["_terrible_stubtest_test_module"] = _m

from _terrible_stubtest_test_module import *
assert annotations
""",
            error=None,
        )

    @collect_cases
    def test_non_public_1(self) -> Iterator[Case]:
        yield Case(
            stub="__all__: list[str]", runtime="", error=f"{TEST_MODULE_NAME}.__all__"
        )  # dummy case
        yield Case(stub="_f: int", runtime="def _f(): ...", error="_f")

    @collect_cases
    def test_non_public_2(self) -> Iterator[Case]:
        yield Case(stub="__all__: list[str] = ['f']", runtime="__all__ = ['f']", error=None)
        yield Case(stub="f: int", runtime="def f(): ...", error="f")
        yield Case(stub="g: int", runtime="def g(): ...", error="g")

    @collect_cases
    def test_dunders(self) -> Iterator[Case]:
        yield Case(
            stub="class A:\n  def __init__(self, a: int, b: int) -> None: ...",
            runtime="class A:\n  def __init__(self, a, bx): pass",
            error="A.__init__",
        )
        yield Case(
            stub="class B:\n  def __call__(self, c: int, d: int) -> None: ...",
            runtime="class B:\n  def __call__(self, c, dx): pass",
            error="B.__call__",
        )
        yield Case(
            stub=(
                "class C:\n"
                "  def __init_subclass__(\n"
                "    cls, e: int = ..., **kwargs: int\n"
                "  ) -> None: ...\n"
            ),
            runtime="class C:\n  def __init_subclass__(cls, e=1, **kwargs): pass",
            error=None,
        )
        yield Case(
            stub="class D:\n  def __class_getitem__(cls, type: type) -> type: ...",
            runtime="class D:\n  def __class_getitem__(cls, type): ...",
            error=None,
        )

    @collect_cases
    def test_not_subclassable(self) -> Iterator[Case]:
        yield Case(
            stub="class CanBeSubclassed: ...", runtime="class CanBeSubclassed: ...", error=None
        )
        yield Case(
            stub="class CannotBeSubclassed:\n  def __init_subclass__(cls) -> None: ...",
            runtime="class CannotBeSubclassed:\n  def __init_subclass__(cls): raise TypeError",
            error="CannotBeSubclassed",
        )

    @collect_cases
    def test_has_runtime_final_decorator(self) -> Iterator[Case]:
        yield Case(
            stub="from typing_extensions import final",
            runtime="""
            import functools
            from typing_extensions import final
            """,
            error=None,
        )
        yield Case(
            stub="""
            @final
            class A: ...
            """,
            runtime="""
            @final
            class A: ...
            """,
            error=None,
        )
        yield Case(  # Runtime can miss `@final` decorator
            stub="""
            @final
            class B: ...
            """,
            runtime="""
            class B: ...
            """,
            error=None,
        )
        yield Case(  # Stub cannot miss `@final` decorator
            stub="""
            class C: ...
            """,
            runtime="""
            @final
            class C: ...
            """,
            error="C",
        )
        yield Case(
            stub="""
            class D:
                @final
                def foo(self) -> None: ...
                @final
                @staticmethod
                def bar() -> None: ...
                @staticmethod
                @final
                def bar2() -> None: ...
                @final
                @classmethod
                def baz(cls) -> None: ...
                @classmethod
                @final
                def baz2(cls) -> None: ...
                @property
                @final
                def eggs(self) -> int: ...
                @final
                @property
                def eggs2(self) -> int: ...
                @final
                def ham(self, obj: int) -> int: ...
            """,
            runtime="""
            class D:
                @final
                def foo(self): pass
                @final
                @staticmethod
                def bar(): pass
                @staticmethod
                @final
                def bar2(): pass
                @final
                @classmethod
                def baz(cls): pass
                @classmethod
                @final
                def baz2(cls): pass
                @property
                @final
                def eggs(self): return 42
                @final
                @property
                def eggs2(self): pass
                @final
                @functools.lru_cache()
                def ham(self, obj): return obj * 2
            """,
            error=None,
        )
        # Stub methods are allowed to have @final even if the runtime doesn't...
        yield Case(
            stub="""
            class E:
                @final
                def foo(self) -> None: ...
                @final
                @staticmethod
                def bar() -> None: ...
                @staticmethod
                @final
                def bar2() -> None: ...
                @final
                @classmethod
                def baz(cls) -> None: ...
                @classmethod
                @final
                def baz2(cls) -> None: ...
                @property
                @final
                def eggs(self) -> int: ...
                @final
                @property
                def eggs2(self) -> int: ...
                @final
                def ham(self, obj: int) -> int: ...
            """,
            runtime="""
            class E:
                def foo(self): pass
                @staticmethod
                def bar(): pass
                @staticmethod
                def bar2(): pass
                @classmethod
                def baz(cls): pass
                @classmethod
                def baz2(cls): pass
                @property
                def eggs(self): return 42
                @property
                def eggs2(self): return 42
                @functools.lru_cache()
                def ham(self, obj): return obj * 2
            """,
            error=None,
        )
        # ...But if the runtime has @final, the stub must have it as well
        yield Case(
            stub="""
            class F:
                def foo(self) -> None: ...
            """,
            runtime="""
            class F:
                @final
                def foo(self): pass
            """,
            error="F.foo",
        )
        yield Case(
            stub="""
            class G:
                @staticmethod
                def foo() -> None: ...
            """,
            runtime="""
            class G:
                @final
                @staticmethod
                def foo(): pass
            """,
            error="G.foo",
        )
        yield Case(
            stub="""
            class H:
                @staticmethod
                def foo() -> None: ...
            """,
            runtime="""
            class H:
                @staticmethod
                @final
                def foo(): pass
            """,
            error="H.foo",
        )
        yield Case(
            stub="""
            class I:
                @classmethod
                def foo(cls) -> None: ...
            """,
            runtime="""
            class I:
                @final
                @classmethod
                def foo(cls): pass
            """,
            error="I.foo",
        )
        yield Case(
            stub="""
            class J:
                @classmethod
                def foo(cls) -> None: ...
            """,
            runtime="""
            class J:
                @classmethod
                @final
                def foo(cls): pass
            """,
            error="J.foo",
        )
        yield Case(
            stub="""
            class K:
                @property
                def foo(self) -> int: ...
            """,
            runtime="""
            class K:
                @property
                @final
                def foo(self): return 42
            """,
            error="K.foo",
        )
        # This test wouldn't pass,
        # because the runtime can't set __final__ on instances of builtins.property,
        # so stubtest has non way of knowing that the runtime was decorated with @final:
        #
        # yield Case(
        #     stub="""
        #     class K2:
        #         @property
        #         def foo(self) -> int: ...
        #     """,
        #     runtime="""
        #     class K2:
        #         @final
        #         @property
        #         def foo(self): return 42
        #     """,
        #     error="K2.foo",
        # )
        yield Case(
            stub="""
            class L:
                def foo(self, obj: int) -> int: ...
            """,
            runtime="""
            class L:
                @final
                @functools.lru_cache()
                def foo(self, obj): return obj * 2
            """,
            error="L.foo",
        )

    @collect_cases
    def test_name_mangling(self) -> Iterator[Case]:
        yield Case(
            stub="""
            class X:
                def __mangle_good(self, text: str) -> None: ...
                def __mangle_bad(self, number: int) -> None: ...
            """,
            runtime="""
            class X:
                def __mangle_good(self, text): pass
                def __mangle_bad(self, text): pass
            """,
            error="X.__mangle_bad",
        )
        yield Case(
            stub="""
            class Klass:
                class __Mangled1:
                    class __Mangled2:
                        def __mangle_good(self, text: str) -> None: ...
                        def __mangle_bad(self, number: int) -> None: ...
            """,
            runtime="""
            class Klass:
                class __Mangled1:
                    class __Mangled2:
                        def __mangle_good(self, text): pass
                        def __mangle_bad(self, text): pass
            """,
            error="Klass.__Mangled1.__Mangled2.__mangle_bad",
        )
        yield Case(
            stub="""
            class __Dunder__:
                def __mangle_good(self, text: str) -> None: ...
                def __mangle_bad(self, number: int) -> None: ...
            """,
            runtime="""
            class __Dunder__:
                def __mangle_good(self, text): pass
                def __mangle_bad(self, text): pass
            """,
            error="__Dunder__.__mangle_bad",
        )
        yield Case(
            stub="""
            class _Private:
                def __mangle_good(self, text: str) -> None: ...
                def __mangle_bad(self, number: int) -> None: ...
            """,
            runtime="""
            class _Private:
                def __mangle_good(self, text): pass
                def __mangle_bad(self, text): pass
            """,
            error="_Private.__mangle_bad",
        )

    @collect_cases
    def test_mro(self) -> Iterator[Case]:
        yield Case(
            stub="""
            class A:
                def foo(self, x: int) -> None: ...
            class B(A):
                pass
            class C(A):
                pass
            """,
            runtime="""
            class A:
                def foo(self, x: int) -> None: ...
            class B(A):
                def foo(self, x: int) -> None: ...
            class C(A):
                def foo(self, y: int) -> None: ...
            """,
            error="C.foo",
        )
        yield Case(
            stub="""
            class X: ...
            """,
            runtime="""
            class X:
                def __init__(self, x): pass
            """,
            error="X.__init__",
        )

    @collect_cases
    def test_good_literal(self) -> Iterator[Case]:
        yield Case(
            stub=r"""
            from typing import Literal

            import enum
            class Color(enum.Enum):
                RED = ...

            NUM: Literal[1]
            CHAR: Literal['a']
            FLAG: Literal[True]
            NON: Literal[None]
            BYT1: Literal[b'abc']
            BYT2: Literal[b'\x90']
            ENUM: Literal[Color.RED]
            """,
            runtime=r"""
            import enum
            class Color(enum.Enum):
                RED = 3

            NUM = 1
            CHAR = 'a'
            NON = None
            FLAG = True
            BYT1 = b"abc"
            BYT2 = b'\x90'
            ENUM = Color.RED
            """,
            error=None,
        )

    @collect_cases
    def test_bad_literal(self) -> Iterator[Case]:
        yield Case("from typing import Literal", "", None)  # dummy case
        yield Case(
            stub="INT_FLOAT_MISMATCH: Literal[1]",
            runtime="INT_FLOAT_MISMATCH = 1.0",
            error="INT_FLOAT_MISMATCH",
        )
        yield Case(stub="WRONG_INT: Literal[1]", runtime="WRONG_INT = 2", error="WRONG_INT")
        yield Case(stub="WRONG_STR: Literal['a']", runtime="WRONG_STR = 'b'", error="WRONG_STR")
        yield Case(
            stub="BYTES_STR_MISMATCH: Literal[b'value']",
            runtime="BYTES_STR_MISMATCH = 'value'",
            error="BYTES_STR_MISMATCH",
        )
        yield Case(
            stub="STR_BYTES_MISMATCH: Literal['value']",
            runtime="STR_BYTES_MISMATCH = b'value'",
            error="STR_BYTES_MISMATCH",
        )
        yield Case(
            stub="WRONG_BYTES: Literal[b'abc']",
            runtime="WRONG_BYTES = b'xyz'",
            error="WRONG_BYTES",
        )
        yield Case(
            stub="WRONG_BOOL_1: Literal[True]",
            runtime="WRONG_BOOL_1 = False",
            error="WRONG_BOOL_1",
        )
        yield Case(
            stub="WRONG_BOOL_2: Literal[False]",
            runtime="WRONG_BOOL_2 = True",
            error="WRONG_BOOL_2",
        )

    @collect_cases
    def test_special_subtype(self) -> Iterator[Case]:
        yield Case(
            stub="""
            b1: bool
            b2: bool
            b3: bool
            """,
            runtime="""
            b1 = 0
            b2 = 1
            b3 = 2
            """,
            error="b3",
        )
        yield Case(
            stub="""
            from typing import TypedDict

            class _Options(TypedDict):
                a: str
                b: int

            opt1: _Options
            opt2: _Options
            opt3: _Options
            """,
            runtime="""
            opt1 = {"a": "3.", "b": 14}
            opt2 = {"some": "stuff"}  # false negative
            opt3 = 0
            """,
            error="opt3",
        )

    @collect_cases
    def test_runtime_typing_objects(self) -> Iterator[Case]:
        yield Case(
            stub="from typing import Protocol, TypedDict",
            runtime="from typing import Protocol, TypedDict",
            error=None,
        )
        yield Case(
            stub="""
            class X(Protocol):
                bar: int
                def foo(self, x: int, y: bytes = ...) -> str: ...
            """,
            runtime="""
            class X(Protocol):
                bar: int
                def foo(self, x: int, y: bytes = ...) -> str: ...
            """,
            error=None,
        )
        yield Case(
            stub="""
            class Y(TypedDict):
                a: int
            """,
            runtime="""
            class Y(TypedDict):
                a: int
            """,
            error=None,
        )

    @collect_cases
    def test_named_tuple(self) -> Iterator[Case]:
        yield Case(
            stub="from typing import NamedTuple",
            runtime="from typing import NamedTuple",
            error=None,
        )
        yield Case(
            stub="""
            class X1(NamedTuple):
                bar: int
                foo: str = ...
            """,
            runtime="""
            class X1(NamedTuple):
                bar: int
                foo: str = 'a'
            """,
            error=None,
        )
        yield Case(
            stub="""
            class X2(NamedTuple):
                bar: int
                foo: str
            """,
            runtime="""
            class X2(NamedTuple):
                bar: int
                foo: str = 'a'
            """,
            # `__new__` will miss a default value for a `foo` parameter,
            # but we don't generate special errors for `foo` missing `...` part.
            error="X2.__new__",
        )

    @collect_cases
    def test_named_tuple_typing_and_collections(self) -> Iterator[Case]:
        yield Case(
            stub="from typing import NamedTuple",
            runtime="from collections import namedtuple",
            error=None,
        )
        yield Case(
            stub="""
            class X1(NamedTuple):
                bar: int
                foo: str = ...
            """,
            runtime="""
            X1 = namedtuple('X1', ['bar', 'foo'], defaults=['a'])
            """,
            error=None,
        )
        yield Case(
            stub="""
            class X2(NamedTuple):
                bar: int
                foo: str
            """,
            runtime="""
            X2 = namedtuple('X1', ['bar', 'foo'], defaults=['a'])
            """,
            error="X2.__new__",
        )

    @collect_cases
    def test_type_var(self) -> Iterator[Case]:
        yield Case(
            stub="from typing import TypeVar", runtime="from typing import TypeVar", error=None
        )
        yield Case(stub="A = TypeVar('A')", runtime="A = TypeVar('A')", error=None)
        yield Case(stub="B = TypeVar('B')", runtime="B = 5", error="B")
        if sys.version_info >= (3, 10):
            yield Case(
                stub="from typing import ParamSpec",
                runtime="from typing import ParamSpec",
                error=None,
            )
            yield Case(stub="C = ParamSpec('C')", runtime="C = ParamSpec('C')", error=None)

    @collect_cases
    def test_metaclass_match(self) -> Iterator[Case]:
        yield Case(stub="class Meta(type): ...", runtime="class Meta(type): ...", error=None)
        yield Case(stub="class A0: ...", runtime="class A0: ...", error=None)
        yield Case(
            stub="class A1(metaclass=Meta): ...",
            runtime="class A1(metaclass=Meta): ...",
            error=None,
        )
        yield Case(stub="class A2: ...", runtime="class A2(metaclass=Meta): ...", error="A2")
        yield Case(stub="class A3(metaclass=Meta): ...", runtime="class A3: ...", error="A3")

        # Explicit `type` metaclass can always be added in any part:
        yield Case(
            stub="class T1(metaclass=type): ...",
            runtime="class T1(metaclass=type): ...",
            error=None,
        )
        yield Case(stub="class T2: ...", runtime="class T2(metaclass=type): ...", error=None)
        yield Case(stub="class T3(metaclass=type): ...", runtime="class T3: ...", error=None)

        # Explicit check that `_protected` names are also supported:
        yield Case(stub="class _P1(type): ...", runtime="class _P1(type): ...", error=None)
        yield Case(stub="class P2: ...", runtime="class P2(metaclass=_P1): ...", error="P2")

        # With inheritance:
        yield Case(
            stub="""
            class I1(metaclass=Meta): ...
            class S1(I1): ...
            """,
            runtime="""
            class I1(metaclass=Meta): ...
            class S1(I1): ...
            """,
            error=None,
        )
        yield Case(
            stub="""
            class I2(metaclass=Meta): ...
            class S2: ...  # missing inheritance
            """,
            runtime="""
            class I2(metaclass=Meta): ...
            class S2(I2): ...
            """,
            error="S2",
        )

    @collect_cases
    def test_metaclass_abcmeta(self) -> Iterator[Case]:
        # Handling abstract metaclasses is special:
        yield Case(stub="from abc import ABCMeta", runtime="from abc import ABCMeta", error=None)
        yield Case(
            stub="class A1(metaclass=ABCMeta): ...",
            runtime="class A1(metaclass=ABCMeta): ...",
            error=None,
        )
        # Stubs cannot miss abstract metaclass:
        yield Case(stub="class A2: ...", runtime="class A2(metaclass=ABCMeta): ...", error="A2")
        # But, stubs can add extra abstract metaclass, this might be a typing hack:
        yield Case(stub="class A3(metaclass=ABCMeta): ...", runtime="class A3: ...", error=None)

    @collect_cases
    def test_abstract_methods(self) -> Iterator[Case]:
        yield Case(
            stub="""
            from abc import abstractmethod
            from typing import overload
            """,
            runtime="from abc import abstractmethod",
            error=None,
        )
        yield Case(
            stub="""
            class A1:
                def some(self) -> None: ...
            """,
            runtime="""
            class A1:
                @abstractmethod
                def some(self) -> None: ...
            """,
            error="A1.some",
        )
        yield Case(
            stub="""
            class A2:
                @abstractmethod
                def some(self) -> None: ...
            """,
            runtime="""
            class A2:
                @abstractmethod
                def some(self) -> None: ...
            """,
            error=None,
        )
        yield Case(
            stub="""
            class A3:
                @overload
                def some(self, other: int) -> str: ...
                @overload
                def some(self, other: str) -> int: ...
            """,
            runtime="""
            class A3:
                @abstractmethod
                def some(self, other) -> None: ...
            """,
            error="A3.some",
        )
        yield Case(
            stub="""
            class A4:
                @overload
                @abstractmethod
                def some(self, other: int) -> str: ...
                @overload
                @abstractmethod
                def some(self, other: str) -> int: ...
            """,
            runtime="""
            class A4:
                @abstractmethod
                def some(self, other) -> None: ...
            """,
            error=None,
        )
        yield Case(
            stub="""
            class A5:
                @abstractmethod
                @overload
                def some(self, other: int) -> str: ...
                @abstractmethod
                @overload
                def some(self, other: str) -> int: ...
            """,
            runtime="""
            class A5:
                @abstractmethod
                def some(self, other) -> None: ...
            """,
            error=None,
        )
        # Runtime can miss `@abstractmethod`:
        yield Case(
            stub="""
            class A6:
                @abstractmethod
                def some(self) -> None: ...
            """,
            runtime="""
            class A6:
                def some(self) -> None: ...
            """,
            error=None,
        )

    @collect_cases
    def test_abstract_properties(self) -> Iterator[Case]:
        # TODO: test abstract properties with setters
        yield Case(
            stub="from abc import abstractmethod",
            runtime="from abc import abstractmethod",
            error=None,
        )
        # Ensure that `@property` also can be abstract:
        yield Case(
            stub="""
            class AP1:
                @property
                def some(self) -> int: ...
            """,
            runtime="""
            class AP1:
                @property
                @abstractmethod
                def some(self) -> int: ...
            """,
            error="AP1.some",
        )
        yield Case(
            stub="""
            class AP1_2:
                def some(self) -> int: ...  # missing `@property` decorator
            """,
            runtime="""
            class AP1_2:
                @property
                @abstractmethod
                def some(self) -> int: ...
            """,
            error="AP1_2.some",
        )
        yield Case(
            stub="""
            class AP2:
                @property
                @abstractmethod
                def some(self) -> int: ...
            """,
            runtime="""
            class AP2:
                @property
                @abstractmethod
                def some(self) -> int: ...
            """,
            error=None,
        )
        # Runtime can miss `@abstractmethod`:
        yield Case(
            stub="""
            class AP3:
                @property
                @abstractmethod
                def some(self) -> int: ...
            """,
            runtime="""
            class AP3:
                @property
                def some(self) -> int: ...
            """,
            error=None,
        )

    @collect_cases
    def test_type_check_only(self) -> Iterator[Case]:
        yield Case(
            stub="from typing import type_check_only, overload",
            runtime="from typing import overload",
            error=None,
        )
        # You can have public types that are only defined in stubs
        # with `@type_check_only`:
        yield Case(
            stub="""
            @type_check_only
            class A1: ...
            """,
            runtime="",
            error=None,
        )
        # Having `@type_check_only` on a type that exists at runtime is an error
        yield Case(
            stub="""
            @type_check_only
            class A2: ...
            """,
            runtime="class A2: ...",
            error="A2",
        )
        # The same is true for NamedTuples and TypedDicts:
        yield Case(
            stub="from typing import NamedTuple, TypedDict",
            runtime="from typing import NamedTuple, TypedDict",
            error=None,
        )
        yield Case(
            stub="""
            @type_check_only
            class NT1(NamedTuple): ...
            """,
            runtime="class NT1(NamedTuple): ...",
            error="NT1",
        )
        yield Case(
            stub="""
            @type_check_only
            class TD1(TypedDict): ...
            """,
            runtime="class TD1(TypedDict): ...",
            error="TD1",
        )
        # The same is true for functions:
        yield Case(
            stub="""
            @type_check_only
            def func1() -> None: ...
            """,
            runtime="",
            error=None,
        )
        yield Case(
            stub="""
            @type_check_only
            def func2() -> None: ...
            """,
            runtime="def func2() -> None: ...",
            error="func2",
        )
        # A type that exists at runtime is allowed to alias a type marked
        # as '@type_check_only' in the stubs.
        yield Case(
            stub="""
            @type_check_only
            class _X1: ...
            X2 = _X1
            """,
            runtime="class X2: ...",
            error=None,
        )


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
            f'error: {TEST_MODULE_NAME}.bad is inconsistent, stub argument "number" differs '
            'from runtime argument "num"\n'
            f"Stub: in file {TEST_MODULE_NAME}.pyi:1\n"
            "def (number: builtins.int, text: builtins.str)\n"
            f"Runtime: in file {TEST_MODULE_NAME}.py:1\ndef (num, text)\n\n"
            "Found 1 error (checked 1 module)\n"
        )
        assert output == expected

        output = run_stubtest(
            stub="def bad(number: int, text: str) -> None: ...",
            runtime="def bad(num, text): pass",
            options=["--concise"],
        )
        expected = (
            "{}.bad is inconsistent, "
            'stub argument "number" differs from runtime argument "num"\n'.format(TEST_MODULE_NAME)
        )
        assert output == expected

    def test_ignore_flags(self) -> None:
        output = run_stubtest(
            stub="", runtime="__all__ = ['f']\ndef f(): pass", options=["--ignore-missing-stub"]
        )
        assert output == "Success: no issues found in 1 module\n"

        output = run_stubtest(stub="", runtime="def f(): pass", options=["--ignore-missing-stub"])
        assert output == "Success: no issues found in 1 module\n"

        output = run_stubtest(
            stub="def f(__a): ...", runtime="def f(a): pass", options=["--ignore-positional-only"]
        )
        assert output == "Success: no issues found in 1 module\n"

    def test_allowlist(self) -> None:
        # Can't use this as a context because Windows
        allowlist = tempfile.NamedTemporaryFile(mode="w+", delete=False)
        try:
            with allowlist:
                allowlist.write(f"{TEST_MODULE_NAME}.bad  # comment\n# comment")

            output = run_stubtest(
                stub="def bad(number: int, text: str) -> None: ...",
                runtime="def bad(asdf, text): pass",
                options=["--allowlist", allowlist.name],
            )
            assert output == "Success: no issues found in 1 module\n"

            # test unused entry detection
            output = run_stubtest(stub="", runtime="", options=["--allowlist", allowlist.name])
            assert output == (
                f"note: unused allowlist entry {TEST_MODULE_NAME}.bad\n"
                "Found 1 error (checked 1 module)\n"
            )

            output = run_stubtest(
                stub="",
                runtime="",
                options=["--allowlist", allowlist.name, "--ignore-unused-allowlist"],
            )
            assert output == "Success: no issues found in 1 module\n"

            # test regex matching
            with open(allowlist.name, mode="w+") as f:
                f.write(f"{TEST_MODULE_NAME}.b.*\n")
                f.write("(unused_missing)?\n")
                f.write("unused.*\n")

            output = run_stubtest(
                stub=textwrap.dedent(
                    """
                    def good() -> None: ...
                    def bad(number: int) -> None: ...
                    def also_bad(number: int) -> None: ...
                    """.lstrip(
                        "\n"
                    )
                ),
                runtime=textwrap.dedent(
                    """
                    def good(): pass
                    def bad(asdf): pass
                    def also_bad(asdf): pass
                    """.lstrip(
                        "\n"
                    )
                ),
                options=["--allowlist", allowlist.name, "--generate-allowlist"],
            )
            assert output == (
                f"note: unused allowlist entry unused.*\n{TEST_MODULE_NAME}.also_bad\n"
            )
        finally:
            os.unlink(allowlist.name)

    def test_mypy_build(self) -> None:
        output = run_stubtest(stub="+", runtime="", options=[])
        assert output == (
            "error: not checking stubs due to failed mypy compile:\n{}.pyi:1: "
            "error: Invalid syntax  [syntax]\n".format(TEST_MODULE_NAME)
        )

        output = run_stubtest(stub="def f(): ...\ndef f(): ...", runtime="", options=[])
        assert output == (
            "error: not checking stubs due to mypy build errors:\n{}.pyi:2: "
            'error: Name "f" already defined on line 1  [no-redef]\n'.format(TEST_MODULE_NAME)
        )

    def test_missing_stubs(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            test_stubs(parse_options(["not_a_module"]))
        assert remove_color_code(output.getvalue()) == (
            "error: not_a_module failed to find stubs\n"
            "Stub:\nMISSING\nRuntime:\nN/A\n\n"
            "Found 1 error (checked 1 module)\n"
        )

    def test_only_py(self) -> None:
        # in this case, stubtest will check the py against itself
        # this is useful to support packages with a mix of stubs and inline types
        with use_tmp_dir(TEST_MODULE_NAME):
            with open(f"{TEST_MODULE_NAME}.py", "w") as f:
                f.write("a = 1")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                test_stubs(parse_options([TEST_MODULE_NAME]))
            output_str = remove_color_code(output.getvalue())
            assert output_str == "Success: no issues found in 1 module\n"

    def test_get_typeshed_stdlib_modules(self) -> None:
        stdlib = mypy.stubtest.get_typeshed_stdlib_modules(None, (3, 7))
        assert "builtins" in stdlib
        assert "os" in stdlib
        assert "os.path" in stdlib
        assert "asyncio" in stdlib
        assert "graphlib" not in stdlib
        assert "formatter" in stdlib
        assert "contextvars" in stdlib  # 3.7+
        assert "importlib.metadata" not in stdlib

        stdlib = mypy.stubtest.get_typeshed_stdlib_modules(None, (3, 10))
        assert "graphlib" in stdlib
        assert "formatter" not in stdlib
        assert "importlib.metadata" in stdlib

    def test_signature(self) -> None:
        def f(a: int, b: int, *, c: int, d: int = 0, **kwargs: Any) -> None:
            pass

        assert (
            str(mypy.stubtest.Signature.from_inspect_signature(inspect.signature(f)))
            == "def (a, b, *, c, d = ..., **kwargs)"
        )

    def test_builtin_signature_with_unrepresentable_default(self) -> None:
        sig = mypy.stubtest.safe_inspect_signature(bytes.hex)
        assert sig is not None
        assert (
            str(mypy.stubtest.Signature.from_inspect_signature(sig))
            == "def (self, sep = ..., bytes_per_sep = ...)"
        )

    def test_config_file(self) -> None:
        runtime = "temp = 5\n"
        stub = "from decimal import Decimal\ntemp: Decimal\n"
        config_file = f"[mypy]\nplugins={root_dir}/test-data/unit/plugins/decimal_to_int.py\n"
        output = run_stubtest(stub=stub, runtime=runtime, options=[])
        assert output == (
            f"error: {TEST_MODULE_NAME}.temp variable differs from runtime type Literal[5]\n"
            f"Stub: in file {TEST_MODULE_NAME}.pyi:2\n_decimal.Decimal\nRuntime:\n5\n\n"
            "Found 1 error (checked 1 module)\n"
        )
        output = run_stubtest(stub=stub, runtime=runtime, options=[], config_file=config_file)
        assert output == "Success: no issues found in 1 module\n"

    def test_config_file_error_codes(self) -> None:
        runtime = "temp = 5\n"
        stub = "temp = SOME_GLOBAL_CONST"
        output = run_stubtest(stub=stub, runtime=runtime, options=[])
        assert output == (
            "error: not checking stubs due to mypy build errors:\n"
            'test_module.pyi:1: error: Name "SOME_GLOBAL_CONST" is not defined  [name-defined]\n'
        )

        config_file = "[mypy]\ndisable_error_code = name-defined\n"
        output = run_stubtest(stub=stub, runtime=runtime, options=[], config_file=config_file)
        assert output == "Success: no issues found in 1 module\n"

    def test_config_file_error_codes_invalid(self) -> None:
        runtime = "temp = 5\n"
        stub = "temp: int\n"
        config_file = "[mypy]\ndisable_error_code = not-a-valid-name\n"
        output, outerr = run_stubtest_with_stderr(
            stub=stub, runtime=runtime, options=[], config_file=config_file
        )
        assert output == "Success: no issues found in 1 module\n"
        assert outerr == (
            "test_module_config.ini: [mypy]: disable_error_code: "
            "Invalid error code(s): not-a-valid-name\n"
        )

    def test_config_file_wrong_incomplete_feature(self) -> None:
        runtime = "x = 1\n"
        stub = "x: int\n"
        config_file = "[mypy]\nenable_incomplete_feature = Unpack\n"
        output = run_stubtest(stub=stub, runtime=runtime, options=[], config_file=config_file)
        assert output == (
            "warning: Warning: Unpack is already enabled by default\n"
            "Success: no issues found in 1 module\n"
        )

        config_file = "[mypy]\nenable_incomplete_feature = not-a-valid-name\n"
        with self.assertRaises(SystemExit):
            run_stubtest(stub=stub, runtime=runtime, options=[], config_file=config_file)

    def test_no_modules(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            test_stubs(parse_options([]))
        assert remove_color_code(output.getvalue()) == "error: no modules to check\n"

    def test_module_and_typeshed(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            test_stubs(parse_options(["--check-typeshed", "some_module"]))
        assert remove_color_code(output.getvalue()) == (
            "error: cannot pass both --check-typeshed and a list of modules\n"
        )
