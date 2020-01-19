"""Tests for stubs.

Verify that various things in stubs are consistent with how things behave at runtime.

"""

import argparse
import importlib
import inspect
import subprocess
import sys
import types
from functools import singledispatch
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, TypeVar, Union

from typing_extensions import Type

import mypy.build
import mypy.modulefinder
import mypy.types
from mypy import nodes
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

    def get_description(self, concise: bool = False) -> str:
        if concise:
            return _style(self.object_desc, bold=True) + " " + self.message

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

    if not stubs:
        yield Error([module_name], "failed to find stubs", MISSING, None)

    for mod, stub in stubs.items():
        try:
            runtime = importlib.import_module(mod)
        except Exception as e:
            yield Error([mod], f"failed to import: {e}", stub, MISSING)
            continue
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
    if (
        not isinstance(runtime, (types.FunctionType, types.BuiltinFunctionType))
        and not isinstance(runtime, (types.MethodType, types.BuiltinMethodType))
        and not inspect.ismethoddescriptor(runtime)
    ):
        yield Error(object_path, "is not a function", stub, runtime)
        return

    try:
        signature = inspect.signature(runtime)
    except ValueError:
        # inspect.signature throws sometimes
        return

    def runtime_printer(s: Any) -> str:
        return "def " + str(inspect.signature(s))

    def make_error(message: str) -> Error:
        return Error(
            object_path,
            "is inconsistent, " + message,
            stub,
            runtime,
            runtime_printer=runtime_printer,
        )

    stub_args_pos = []
    stub_args_kwonly = {}
    stub_args_varpos = None
    stub_args_varkw = None

    for stub_arg in stub.arguments:
        if stub_arg.kind in (nodes.ARG_POS, nodes.ARG_OPT):
            stub_args_pos.append(stub_arg)
        elif stub_arg.kind in (nodes.ARG_NAMED, nodes.ARG_NAMED_OPT):
            stub_args_kwonly[stub_arg.variable.name] = stub_arg
        elif stub_arg.kind == nodes.ARG_STAR:
            stub_args_varpos = stub_arg
        elif stub_arg.kind == nodes.ARG_STAR2:
            stub_args_varkw = stub_arg
        else:
            assert False

    runtime_args_pos = []
    runtime_args_kwonly = {}
    runtime_args_varpos = None
    runtime_args_varkw = None

    for runtime_arg in signature.parameters.values():
        if runtime_arg.kind in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        ):
            runtime_args_pos.append(runtime_arg)
        elif runtime_arg.kind == inspect.Parameter.KEYWORD_ONLY:
            runtime_args_kwonly[runtime_arg.name] = runtime_arg
        elif runtime_arg.kind == inspect.Parameter.VAR_POSITIONAL:
            runtime_args_varpos = runtime_arg
        elif runtime_arg.kind == inspect.Parameter.VAR_KEYWORD:
            runtime_args_varkw = runtime_arg
        else:
            assert False

    def verify_arg_name(
        stub_arg: nodes.Argument, runtime_arg: inspect.Parameter
    ) -> Iterator[Error]:
        # Ignore exact names for all dunder methods other than __init__
        if stub.name != "__init__" and stub.name.startswith("__"):
            return
        if stub_arg.variable.name.replace("_", "") != runtime_arg.name.replace("_", ""):
            yield make_error(
                f'stub argument "{stub_arg.variable.name}" differs from '
                f'runtime argument "{runtime_arg.name}"'
            )

    def verify_arg_default_value(
        stub_arg: nodes.Argument, runtime_arg: inspect.Parameter
    ) -> Iterator[Error]:
        if runtime_arg.default != inspect.Parameter.empty:
            # TODO: Check that the default value is compatible with the stub type
            if stub_arg.kind not in (nodes.ARG_OPT, nodes.ARG_NAMED_OPT):
                yield make_error(
                    f'runtime argument "{runtime_arg.name}" has a default value '
                    "but stub argument does not"
                )
        else:
            if stub_arg.kind in (nodes.ARG_OPT, nodes.ARG_NAMED_OPT):
                yield make_error(
                    f'stub argument "{stub_arg.variable.name}" has a default '
                    "value but runtime argument does not"
                )

    # Check positional arguments match up
    for stub_arg, runtime_arg in zip(stub_args_pos, runtime_args_pos):
        yield from verify_arg_name(stub_arg, runtime_arg)
        yield from verify_arg_default_value(stub_arg, runtime_arg)
        if (
            runtime_arg.kind == inspect.Parameter.POSITIONAL_ONLY
            and not stub_arg.variable.name.startswith("__")
            and not stub_arg.variable.name.strip("_") == "self"
            and not stub.name.startswith("__")  # noisy for dunder methods
        ):
            yield make_error(
                f'stub argument "{stub_arg.variable.name}" should be '
                "positional-only (rename with a leading double underscore)"
            )

    # Checks involving *args
    if len(stub_args_pos) == len(runtime_args_pos):
        if stub_args_varpos is None and runtime_args_varpos is not None:
            yield make_error(
                f'stub does not have *args argument "{runtime_args_varpos.name}"'
            )
        if stub_args_varpos is not None and runtime_args_varpos is None:
            yield make_error(
                f'runtime does not have *args argument "{stub_args_varpos.variable.name}"'
            )
    elif len(stub_args_pos) > len(runtime_args_pos):
        if runtime_args_varpos is None:
            for stub_arg in stub_args_pos[len(runtime_args_pos) :]:
                # If the variable is in runtime_args_kwonly, it's just mislabelled as not a
                # keyword-only argument; we report the error while checking keyword-only arguments
                if stub_arg.variable.name not in runtime_args_kwonly:
                    yield make_error(
                        f'runtime does not have argument "{stub_arg.variable.name}"'
                    )
        # We do not check whether stub takes *args when the runtime does, for cases where the stub
        # just listed out the extra parameters the function takes
    elif len(stub_args_pos) < len(runtime_args_pos):
        if stub_args_varpos is None:
            for runtime_arg in runtime_args_pos[len(stub_args_pos) :]:
                yield make_error(f'stub does not have argument "{runtime_arg.name}"')
        elif runtime_args_pos is None:
            yield make_error(
                f'runtime does not have *args argument "{stub_args_varpos.variable.name}"'
            )

    # Check keyword-only args
    for arg in set(stub_args_kwonly) & set(runtime_args_kwonly):
        stub_arg, runtime_arg = stub_args_kwonly[arg], runtime_args_kwonly[arg]
        yield from verify_arg_name(stub_arg, runtime_arg)
        yield from verify_arg_default_value(stub_arg, runtime_arg)

    # Checks involving **kwargs
    if stub_args_varkw is None and runtime_args_varkw is not None:
        # We do not check whether stub takes **kwargs when the runtime does, for cases where the
        # stub just listed out the extra keyword parameters the function takes
        # Also check against positional parameters, to avoid a nitpicky message when an argument
        # isn't marked as keyword-only
        stub_pos_names = set(stub_arg.variable.name for stub_arg in stub_args_pos)
        if not set(runtime_args_kwonly).issubset(
            set(stub_args_kwonly) | stub_pos_names
        ):
            yield make_error(
                f'stub does not have **kwargs argument "{runtime_args_varkw.name}"'
            )
    if stub_args_varkw is not None and runtime_args_varkw is None:
        yield make_error(
            f'runtime does not have **kwargs argument "{stub_args_varkw.variable.name}"'
        )
    if runtime_args_varkw is None or not set(runtime_args_kwonly).issubset(
        set(stub_args_kwonly)
    ):
        for arg in set(stub_args_kwonly) - set(runtime_args_kwonly):
            yield make_error(f'runtime does not have argument "{arg}"')
    if stub_args_varkw is None or not set(stub_args_kwonly).issubset(
        set(runtime_args_kwonly)
    ):
        for arg in set(runtime_args_kwonly) - set(stub_args_kwonly):
            if arg in set(stub_arg.variable.name for stub_arg in stub_args_pos):
                yield make_error(f'stub argument "{arg}" is not keyword-only')
            else:
                yield make_error(f'stub does not have argument "{arg}"')


@verify.register(Missing)
def verify_none(
    stub: Missing, runtime: MaybeMissing[Any], object_path: List[str]
) -> Iterator[Error]:
    yield Error(object_path, "is not present in stub", stub, runtime)
    assert not isinstance(runtime, Missing)


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
    # TODO: Overloads can be pretty deceitful, so maybe be more permissive when dealing with them
    # For a motivating example, look at RawConfigParser.items and RawConfigParser.get
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
        output = [
            _style("error: ", color="red", bold=True),
            _style(module_name, bold=True),
            " failed mypy build.\n",
        ]
        print("".join(output) + "\n".join(res.errors))
        sys.exit(1)
    return res.files


def get_typeshed_stdlib_modules(
    data_dir: str, custom_typeshed_dir: Optional[str]
) -> List[str]:
    # This snippet is based on code in mypy.modulefinder.default_lib_path
    if custom_typeshed_dir:
        typeshed_dir = Path(custom_typeshed_dir)
    else:
        typeshed_dir = Path(data_dir)
        if (typeshed_dir / "stubs-auto").exists():
            typeshed_dir /= "stubs-auto"
        typeshed_dir /= "typeshed"

    versions = ["2and3", "3"]
    for minor in range(sys.version_info.minor + 1):
        versions.append(f"3.{minor}")

    modules = []
    for version in versions:
        base = typeshed_dir / "stdlib" / version
        if base.exists():
            output = subprocess.check_output(
                ["find", base, "-type", "f"], encoding="utf-8"
            )
            paths = [Path(p) for p in output.splitlines()]
            for path in paths:
                if path.stem == "__init__":
                    path = path.parent
                modules.append(
                    ".".join(path.relative_to(base).parts[:-1] + (path.stem,))
                )
    return sorted(modules)


def main() -> int:
    assert sys.version_info >= (3, 6), "This script requires at least Python 3.6"

    parser = argparse.ArgumentParser()
    parser.add_argument("modules", nargs="*", help="Modules to test")
    parser.add_argument(
        "--check-typeshed",
        action="store_true",
        help="Check all stdlib modules in typeshed",
    )
    parser.add_argument(
        "--custom-typeshed-dir", metavar="DIR", help="Use the custom typeshed in DIR"
    )
    parser.add_argument(
        "--ignore-missing-stub",
        action="store_true",
        help="Ignore errors for stub missing things that are present at runtime",
    )
    parser.add_argument(
        "--whitelist",
        help="Use file as a whitelist. Whitelists can be created with --output-whitelist",
    )
    parser.add_argument(
        "--concise", action="store_true", help="Make output concise",
    )
    parser.add_argument(
        "--output-whitelist",
        action="store_true",
        help="Print a whitelist (to stdout) to be used with --whitelist",
    )
    args = parser.parse_args()

    options = Options()
    options.incremental = False
    options.custom_typeshed_dir = args.custom_typeshed_dir

    data_dir = mypy.build.default_data_dir()
    search_path = mypy.modulefinder.compute_search_paths([], options, data_dir)
    find_module_cache = FindModuleCache(search_path)

    whitelist = set()
    if args.whitelist:
        with open(args.whitelist) as f:
            whitelist = set(l.strip() for l in f.readlines())

    modules = args.modules
    if args.check_typeshed:
        assert (
            not args.modules
        ), "Cannot pass both --check-typeshed and a list of modules"
        modules = get_typeshed_stdlib_modules(data_dir, args.custom_typeshed_dir)
        # TODO: See if there's a more efficient way to get mypy to build all the stubs, rather than
        # just one by one

    assert modules, "No modules to check"

    exit_code = 0
    for module in modules:
        for error in test_module(module, options, find_module_cache):
            if args.ignore_missing_stub and error.is_missing_stub():
                continue
            if error.object_desc in whitelist:
                continue
            if args.output_whitelist:
                print(error.object_desc)
                continue
            exit_code = 1
            print(error.get_description(concise=args.concise))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
