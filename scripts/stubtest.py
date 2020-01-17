"""Tests for stubs.

Verify that various things in stubs are consistent with how things behave at runtime.

"""

import argparse
import importlib
import inspect
import sys
import types
from functools import singledispatch
from typing import Any, Callable, Dict, Iterator, List, Optional, TypeVar, Union

from typing_extensions import Type

import mypy.build
import mypy.modulefinder
import mypy.types
from mypy import nodes
from mypy.errors import CompileError
from mypy.modulefinder import FindModuleCache
from mypy.options import Options
from mypy.util import FancyFormatter


class Missing:
    def __repr__(self) -> str:
        return "MISSING"


MISSING = Missing()

T = TypeVar("T")
MaybeMissing = Union[T, Missing]

_formatter = FancyFormatter(sys.stdout, sys.stderr, False)


def _style(message: str, **kwargs: Any) -> str:
    kwargs.setdefault("color", "none")
    return _formatter.style(message, **kwargs)


class Error:
    def __init__(
        self,
        object_path: List[str],
        message: str,
        stub_object: MaybeMissing[nodes.Node],
        runtime_object: MaybeMissing[Any],
        stub_printer: Optional[Callable[[nodes.Node], str]] = None,
        runtime_printer: Optional[Callable[[Any], str]] = None,
    ) -> None:
        self.object_desc = ".".join(object_path)
        self.message = message
        self.stub_object = stub_object
        self.runtime_object = runtime_object
        if stub_printer is None:
            stub_printer = lambda stub: str(getattr(stub, "type", stub))
        self.stub_printer = lambda s: s if isinstance(s, Missing) else stub_printer(s)
        if runtime_printer is None:
            runtime_printer = lambda runtime: str(runtime)
        self.runtime_printer = (
            lambda s: s if isinstance(s, Missing) else runtime_printer(s)
        )

    def is_missing_stub(self) -> bool:
        return isinstance(self.stub_object, Missing)

    def __str__(self) -> str:
        stub_line = None
        stub_file = None
        if not isinstance(self.stub_object, Missing):
            stub_line = self.stub_object.line
        # TODO: Find a way of getting the stub file

        stub_loc_str = ""
        if stub_line:
            stub_loc_str += f" at line {stub_line}"
        if stub_file:
            stub_loc_str += f" in file {stub_file}"

        runtime_line = None
        runtime_file = None
        if not isinstance(self.runtime_object, Missing):
            try:
                runtime_line = inspect.getsourcelines(self.runtime_object)[1]
            except (OSError, TypeError):
                pass
            try:
                runtime_file = inspect.getsourcefile(self.runtime_object)
            except TypeError:
                pass

        runtime_loc_str = ""
        if runtime_line:
            runtime_loc_str += f" at line {runtime_line}"
        if runtime_file:
            runtime_loc_str += f" in file {runtime_file}"

        output = [
            _style("error: ", color="red", bold=True),
            _style(self.object_desc, bold=True),
            f" {self.message}\n",
            "Stub:",
            _style(stub_loc_str, dim=True),
            "\n",
            _style(f"{self.stub_printer(self.stub_object)}\n", color="blue", dim=True),
            "Runtime:",
            _style(runtime_loc_str, dim=True),
            "\n",
            _style(
                f"{self.runtime_printer(self.runtime_object)}\n", color="blue", dim=True
            ),
        ]
        return "".join(output)


def test_module(
    module_name: str, options: Options, find_module_cache: FindModuleCache
) -> Iterator[Error]:
    stubs = {
        mod: stub
        for mod, stub in build_stubs(module_name, options, find_module_cache).items()
        if (mod == module_name or mod.startswith(module_name + "."))
    }

    for mod, stub in stubs.items():
        runtime = importlib.import_module(mod)
        yield from verify(stub, runtime, [mod])


@singledispatch
def verify(
    stub: nodes.Node, runtime: MaybeMissing[Any], object_path: List[str]
) -> Iterator[Error]:
    yield Error(object_path, "is an unknown mypy node", stub, runtime)


@verify.register(nodes.MypyFile)
def verify_mypyfile(
    stub: nodes.MypyFile,
    runtime: MaybeMissing[types.ModuleType],
    object_path: List[str],
) -> Iterator[Error]:
    if isinstance(runtime, Missing):
        yield Error(object_path, "is not present at runtime", stub, runtime)
        return
    if not isinstance(runtime, types.ModuleType):
        yield Error(object_path, "is not a module", stub, runtime)
        return

    # Check all things in the stub
    to_check = set(m for m, o in stub.names.items() if o.module_public)
    # Check all things declared in module's __all__
    to_check.update(getattr(runtime, "__all__", []))
    to_check.difference_update(
        {"__file__", "__doc__", "__name__", "__builtins__", "__package__"}
    )
    # We currently don't check things in the module that aren't in the stub, other than things that
    # are in __all__ to avoid false positives.

    for entry in sorted(to_check):
        yield from verify(
            stub.names[entry].node if entry in stub.names else MISSING,
            getattr(runtime, entry, MISSING),
            object_path + [entry],
        )


@verify.register(nodes.TypeInfo)
def verify_typeinfo(
    stub: nodes.TypeInfo, runtime: MaybeMissing[Type[Any]], object_path: List[str]
) -> Iterator[Error]:
    if isinstance(runtime, Missing):
        yield Error(object_path, "is not present at runtime", stub, runtime)
        return
    if not isinstance(runtime, type):
        yield Error(object_path, "is not a type", stub, runtime)
        return

    to_check = set(stub.names)
    to_check.update(m for m in vars(runtime) if not m.startswith("_"))

    for entry in sorted(to_check):
        yield from verify(
            stub.names[entry].node if entry in stub.names else MISSING,
            getattr(runtime, entry, MISSING),
            object_path + [entry],
        )


@verify.register(nodes.FuncItem)
def verify_funcitem(
    stub: nodes.FuncItem,
    runtime: MaybeMissing[types.FunctionType],
    object_path: List[str],
) -> Iterator[Error]:
    if isinstance(runtime, Missing):
        yield Error(object_path, "is not present at runtime", stub, runtime)
        return
    if not isinstance(
        runtime, (types.FunctionType, types.BuiltinFunctionType)
    ) and not inspect.ismethoddescriptor(runtime):
        yield Error(object_path, "is not a function", stub, runtime)
        return

    try:
        signature = inspect.signature(runtime)
    except ValueError:
        # inspect.signature throws sometimes
        return

    def runtime_printer(s: Any) -> str:
        return "def " + str(inspect.signature(s))

    i, j = 0, 0
    stub_args = stub.arguments
    runtime_args = list(signature.parameters.values())
    while i < len(stub_args) or j < len(runtime_args):
        if i >= len(stub_args):
            # Ignore the error if the stub doesn't take **kwargs, for cases where the stub
            # just listed out the keyword parameters the function takes
            if runtime_args[j].kind != inspect.Parameter.VAR_KEYWORD:
                yield Error(
                    object_path,
                    f'is inconsistent, stub does not have argument "{runtime_args[j].name}"',
                    stub,
                    runtime,
                    runtime_printer=runtime_printer,
                )
            j += 1
            continue
        if j >= len(runtime_args):
            yield Error(
                object_path,
                f"is inconsistent, runtime does not have argument {stub_args[i].variable.name}",
                stub,
                runtime,
                runtime_printer=runtime_printer,
            )
            i += 1
            continue

        # TODO: maybe don't check by name for positional-only args
        # TODO: stricter checking of positional-only, keyword-only
        # TODO: check type compatibility of default args
        # TODO: overloads are sometimes pretty deceitful, so handle that better

        # Allow *args and **kwargs to soak up extra args and kwargs
        stub_arg, runtime_arg = stub_args[i], runtime_args[j]
        if (stub_arg.kind == mypy.nodes.ARG_STAR) and (
            runtime_arg.kind != inspect.Parameter.VAR_POSITIONAL
        ):
            j += 1
            continue
        if (stub_arg.kind != mypy.nodes.ARG_STAR) and (
            runtime_arg.kind == inspect.Parameter.VAR_POSITIONAL
        ):
            i += 1
            continue

        if (stub_arg.kind == mypy.nodes.ARG_STAR2) and (
            runtime_arg.kind != inspect.Parameter.VAR_KEYWORD
        ):
            j += 1
            continue
        if (stub_arg.kind != mypy.nodes.ARG_STAR2) and (
            runtime_arg.kind == inspect.Parameter.VAR_KEYWORD
        ):
            i += 1
            continue

        # Ignore exact names for all dunder methods other than __init__
        is_dunder_method = stub.name != "__init__" and stub.name.startswith("__")
        if (
            stub_arg.variable.name.replace("_", "") != runtime_arg.name.replace("_", "")
            and not is_dunder_method
        ):
            yield Error(
                object_path,
                f'is inconsistent, stub argument "{stub_arg.variable.name}" differs from '
                f'runtime argument "{runtime_arg.name}"',
                stub,
                runtime,
                runtime_printer=runtime_printer,
            )
        i += 1
        j += 1


@verify.register(Missing)
def verify_none(
    stub: Missing, runtime: MaybeMissing[Any], object_path: List[str]
) -> Iterator[Error]:
    yield Error(object_path, "is not present in stub", stub, runtime)
    if isinstance(runtime, Missing):
        raise RuntimeError


@verify.register(nodes.Var)
def verify_var(
    stub: nodes.Var, runtime: MaybeMissing[Any], object_path: List[str]
) -> Iterator[Error]:
    if isinstance(runtime, Missing):
        # Don't always yield an error here, because we often can't find instance variables
        if len(object_path) <= 1:
            yield Error(object_path, "is not present at runtime", stub, runtime)
        return
    # TODO: Make this better
    if isinstance(stub, mypy.types.Instance):
        if stub.type.type.name != runtime.__name__:
            yield Error(object_path, "var_mismatch", stub, runtime)


@verify.register(nodes.OverloadedFuncDef)
def verify_overloadedfuncdef(
    stub: nodes.OverloadedFuncDef, runtime: MaybeMissing[Any], object_path: List[str]
) -> Iterator[Error]:
    for func in stub.items:
        yield from verify(func, runtime, object_path)


@verify.register(nodes.TypeVarExpr)
def verify_typevarexpr(
    stub: nodes.TypeVarExpr, runtime: MaybeMissing[Any], object_path: List[str]
) -> Iterator[Error]:
    if False:
        yield None


@verify.register(nodes.Decorator)
def verify_decorator(
    stub: nodes.Decorator, runtime: MaybeMissing[Any], object_path: List[str]
) -> Iterator[Error]:
    if (
        len(stub.decorators) == 1
        and isinstance(stub.decorators[0], nodes.NameExpr)
        and stub.decorators[0].fullname == "typing.overload"
    ):
        yield from verify(stub.func, runtime, object_path)


@verify.register(nodes.TypeAlias)
def verify_typealias(
    stub: nodes.TypeAlias, runtime: MaybeMissing[Any], object_path: List[str]
) -> Iterator[Error]:
    if False:
        yield None


def build_stubs(
    module_name: str, options: Options, find_module_cache: FindModuleCache
) -> Dict[str, nodes.MypyFile]:
    sources = find_module_cache.find_modules_recursive(module_name)

    res = mypy.build.build(sources=sources, options=options)
    if res.errors:
        raise CompileError

    return res.files


def main() -> Iterator[Error]:
    parser = argparse.ArgumentParser()
    parser.add_argument("modules", nargs="+", help="Modules to test")
    parser.add_argument(
        "--ignore-missing-stub",
        action="store_true",
        help="Ignore errors for stub missing things that are present at runtime",
    )
    parser.add_argument(
        "--custom-typeshed-dir", metavar="DIR", help="Use the custom typeshed in DIR"
    )
    args = parser.parse_args()

    options = Options()
    options.incremental = False
    options.custom_typeshed_dir = args.custom_typeshed_dir

    data_dir = mypy.build.default_data_dir()
    search_path = mypy.modulefinder.compute_search_paths([], options, data_dir)
    find_module_cache = FindModuleCache(search_path)

    for module in args.modules:
        for error in test_module(module, options, find_module_cache):
            if not args.ignore_missing_stub or not error.is_missing_stub():
                yield error


if __name__ == "__main__":
    for err in main():
        print(err)
