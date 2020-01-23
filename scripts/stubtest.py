"""Tests for stubs.

Verify that various things in stubs are consistent with how things behave at runtime.

"""

import argparse
import importlib
import inspect
import subprocess
import sys
import types
import warnings
from functools import singledispatch
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Iterator,
    List,
    Optional,
    TypeVar,
    Union,
)

from typing_extensions import Type

import mypy.build
import mypy.modulefinder
import mypy.types
from mypy import nodes
from mypy.options import Options
from mypy.util import FancyFormatter


class Missing:
    """Marker object for things that are missing (from a stub or the runtime)."""

    def __repr__(self) -> str:
        return "MISSING"


MISSING = Missing()

T = TypeVar("T")
MaybeMissing = Union[T, Missing]

_formatter = FancyFormatter(sys.stdout, sys.stderr, False)


def _style(message: str, **kwargs: Any) -> str:
    """Wrapper around mypy.util for fancy formatting."""
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
        """Represents an error found by stubtest.

        :param object_path: Location of the object with the error, eg, ["module", "Class", "method"]
        :param message: Error message
        :param stub_object: The mypy node representing the stub
        :param runtime_object: Actual object obtained from the runtime
        :param stub_printer: Callable to provide specialised output for a given stub object
        :param runtime_printer: Callable to provide specialised output for a given runtime object

        """
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
        """Whether or not the error is for something missing from the stub."""
        return isinstance(self.stub_object, Missing)

    def get_description(self, concise: bool = False) -> str:
        """Returns a description of the error.

        :param concise: Whether to return a concise, one-line description

        """
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


def test_module(module_name: str) -> Iterator[Error]:
    """Tests a given module's stub against introspecting it at runtime.

    Requires the stub to have been built already, accomplished by a call to ``build_stubs``.

    :param module_name: The module to test

    """
    stub = get_stub(module_name)
    if stub is None:
        yield Error([module_name], "failed to find stubs", MISSING, None)
        return

    try:
        runtime = importlib.import_module(module_name)
    except Exception as e:
        yield Error([module_name], f"failed to import: {e}", stub, MISSING)
        return

    # collections likes to warn us about the things we're doing
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        yield from verify(stub, runtime, [module_name])


@singledispatch
def verify(
    stub: nodes.Node, runtime: MaybeMissing[Any], object_path: List[str]
) -> Iterator[Error]:
    """Entry point for comparing a stub to a runtime object.

    We use single dispatch based on the type of ``stub``.

    :param stub: The mypy node representing a part of the stub
    :param runtime: The runtime object corresponding to ``stub``

    """
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

    # Check things in the stub that are public
    to_check = set(
        m
        for m, o in stub.names.items()
        if o.module_public and (not m.startswith("_") or hasattr(runtime, m))
    )
    # Check all things declared in module's __all__
    to_check.update(getattr(runtime, "__all__", []))
    to_check.difference_update(
        {"__file__", "__doc__", "__name__", "__builtins__", "__package__"}
    )
    # We currently don't check things in the module that aren't in the stub, other than things that
    # are in __all__, to avoid false positives.

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
            next((t.names[entry].node for t in stub.mro if entry in t.names), MISSING),
            getattr(runtime, entry, MISSING),
            object_path + [entry],
        )


def _verify_static_class_methods(
    stub: nodes.FuncItem, runtime: types.FunctionType
) -> Iterator[str]:
    if isinstance(runtime, classmethod) and not stub.is_class:
        yield "runtime is a classmethod but stub is not"
    if not isinstance(runtime, classmethod) and stub.is_class:
        yield "stub is a classmethod but runtime is not"
    if isinstance(runtime, staticmethod) and not stub.is_static:
        yield "runtime is a staticmethod but stub is not"
    if not isinstance(runtime, classmethod) and stub.is_static:
        yield "stub is a staticmethod but runtime is not"


def _verify_arg_name(
    stub_arg: nodes.Argument, runtime_arg: inspect.Parameter, function_name: str
) -> Iterator[str]:
    """Checks whether argument names match."""
    # Ignore exact names for all dunder methods other than __init__
    if function_name != "__init__" and function_name.startswith("__"):
        return

    def strip_prefix(s: str, prefix: str) -> str:
        return s[len(prefix) :] if s.startswith(prefix) else s

    if strip_prefix(stub_arg.variable.name, "__") == runtime_arg.name:
        return

    def names_approx_match(a: str, b: str) -> bool:
        a = a.strip("_")
        b = b.strip("_")
        return a.startswith(b) or b.startswith(a) or len(a) == 1 or len(b) == 1

    # Be more permissive about names matching for positional-only arguments
    if runtime_arg.kind == inspect.Parameter.POSITIONAL_ONLY and names_approx_match(
        stub_arg.variable.name, runtime_arg.name
    ):
        return
    # This comes up with namedtuples, so ignore
    if stub_arg.variable.name == "_self":
        return
    yield (
        f'stub argument "{stub_arg.variable.name}" differs from '
        f'runtime argument "{runtime_arg.name}"'
    )


def _verify_arg_default_value(
    stub_arg: nodes.Argument, runtime_arg: inspect.Parameter
) -> Iterator[str]:
    """Checks whether argument default values are compatible."""
    if runtime_arg.default != inspect.Parameter.empty:
        if stub_arg.kind not in (nodes.ARG_OPT, nodes.ARG_NAMED_OPT):
            yield (
                f'runtime argument "{runtime_arg.name}" has a default value '
                "but stub argument does not"
            )
        else:
            runtime_type = get_mypy_type_of_runtime_value(runtime_arg.default)
            if (
                runtime_type is not None
                and stub_arg.variable.type is not None
                # Avoid false positives for marker objects
                and type(runtime_arg.default) != object
                and not is_subtype_helper(runtime_type, stub_arg.variable.type)
            ):
                yield (
                    f'runtime argument "{runtime_arg.name}" has a default value of type '
                    f"{runtime_type}, which is incompatible with stub argument type "
                    f"{stub_arg.variable.type}"
                )
    else:
        if stub_arg.kind in (nodes.ARG_OPT, nodes.ARG_NAMED_OPT):
            yield (
                f'stub argument "{stub_arg.variable.name}" has a default '
                "value but runtime argument does not"
            )


class Signature(Generic[T]):
    def __init__(self) -> None:
        self.pos: List[T] = []
        self.kwonly: Dict[str, T] = {}
        self.varpos: Optional[T] = None
        self.varkw: Optional[T] = None

    def __str__(self) -> str:
        def get_name(arg: Any) -> str:
            if isinstance(arg, inspect.Parameter):
                return arg.name
            if isinstance(arg, nodes.Argument):
                return arg.variable.name
            raise ValueError

        def get_type(arg: Any) -> Optional[str]:
            if isinstance(arg, inspect.Parameter):
                return None
            if isinstance(arg, nodes.Argument):
                return str(arg.variable.type or arg.type_annotation)
            raise ValueError

        def has_default(arg: Any) -> bool:
            if isinstance(arg, inspect.Parameter):
                return arg.default != inspect.Parameter.empty
            if isinstance(arg, nodes.Argument):
                return arg.kind in (nodes.ARG_OPT, nodes.ARG_NAMED_OPT)
            raise ValueError

        def get_desc(arg: Any) -> str:
            arg_type = get_type(arg)
            return (
                get_name(arg)
                + (f": {arg_type}" if arg_type else "")
                + (" = ..." if has_default(arg) else "")
            )

        ret = "def ("
        ret += ", ".join(
            [get_desc(arg) for arg in self.pos]
            + (
                ["*" + get_name(self.varpos)]
                if self.varpos
                else (["*"] if self.kwonly else [])
            )
            + [get_desc(arg) for arg in self.kwonly.values()]
            + (["**" + get_name(self.varkw)] if self.varkw else [])
        )
        ret += ")"
        return ret

    @staticmethod
    def from_funcitem(stub: nodes.FuncItem) -> "Signature[nodes.Argument]":
        stub_sig: Signature[nodes.Argument] = Signature()
        for stub_arg in stub.arguments:
            if stub_arg.kind in (nodes.ARG_POS, nodes.ARG_OPT):
                stub_sig.pos.append(stub_arg)
            elif stub_arg.kind in (nodes.ARG_NAMED, nodes.ARG_NAMED_OPT):
                stub_sig.kwonly[stub_arg.variable.name] = stub_arg
            elif stub_arg.kind == nodes.ARG_STAR:
                stub_sig.varpos = stub_arg
            elif stub_arg.kind == nodes.ARG_STAR2:
                stub_sig.varkw = stub_arg
            else:
                raise ValueError
        return stub_sig

    @staticmethod
    def from_inspect_signature(
        signature: inspect.Signature,
    ) -> "Signature[inspect.Parameter]":
        runtime_sig: Signature[inspect.Parameter] = Signature()
        for runtime_arg in signature.parameters.values():
            if runtime_arg.kind in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            ):
                runtime_sig.pos.append(runtime_arg)
            elif runtime_arg.kind == inspect.Parameter.KEYWORD_ONLY:
                runtime_sig.kwonly[runtime_arg.name] = runtime_arg
            elif runtime_arg.kind == inspect.Parameter.VAR_POSITIONAL:
                runtime_sig.varpos = runtime_arg
            elif runtime_arg.kind == inspect.Parameter.VAR_KEYWORD:
                runtime_sig.varkw = runtime_arg
            else:
                raise ValueError
        return runtime_sig


def _verify_signature(
    stub: Signature[nodes.Argument],
    runtime: Signature[inspect.Parameter],
    function_name: str,
) -> Iterator[str]:
    # Check positional arguments match up
    for stub_arg, runtime_arg in zip(stub.pos, runtime.pos):
        yield from _verify_arg_name(stub_arg, runtime_arg, function_name)
        yield from _verify_arg_default_value(stub_arg, runtime_arg)
        if (
            runtime_arg.kind == inspect.Parameter.POSITIONAL_ONLY
            and not stub_arg.variable.name.startswith("__")
            and not stub_arg.variable.name.strip("_") == "self"
            and not function_name.startswith("__")  # noisy for dunder methods
        ):
            yield (
                f'stub argument "{stub_arg.variable.name}" should be positional-only '
                f'(rename with a leading double underscore, i.e. "__{runtime_arg.name}")'
            )
        if (
            runtime_arg.kind != inspect.Parameter.POSITIONAL_ONLY
            and stub_arg.variable.name.startswith("__")
        ):
            yield (
                f'stub argument "{stub_arg.variable.name}" is positional or keyword '
                "(remove leading double underscore)"
            )

    # Checks involving *args
    if len(stub.pos) == len(runtime.pos):
        if stub.varpos is None and runtime.varpos is not None:
            yield f'stub does not have *args argument "{runtime.varpos.name}"'
        if stub.varpos is not None and runtime.varpos is None:
            yield (
                f'runtime does not have *args argument "{stub.varpos.variable.name}"'
            )
    elif len(stub.pos) > len(runtime.pos):
        if runtime.varpos is None:
            for stub_arg in stub.pos[len(runtime.pos) :]:
                # If the variable is in runtime.kwonly, it's just mislabelled as not a
                # keyword-only argument; we report the error while checking keyword-only arguments
                if stub_arg.variable.name not in runtime.kwonly:
                    yield f'runtime does not have argument "{stub_arg.variable.name}"'
        # We do not check whether stub takes *args when the runtime does, for cases where the stub
        # just listed out the extra parameters the function takes
    elif len(stub.pos) < len(runtime.pos):
        if stub.varpos is None:
            for runtime_arg in runtime.pos[len(stub.pos) :]:
                yield f'stub does not have argument "{runtime_arg.name}"'
        elif runtime.pos is None:
            yield (
                f'runtime does not have *args argument "{stub.varpos.variable.name}"'
            )

    # Check keyword-only args
    for arg in sorted(set(stub.kwonly) & set(runtime.kwonly)):
        stub_arg, runtime_arg = stub.kwonly[arg], runtime.kwonly[arg]
        yield from _verify_arg_name(stub_arg, runtime_arg, function_name)
        yield from _verify_arg_default_value(stub_arg, runtime_arg)

    # Checks involving **kwargs
    if stub.varkw is None and runtime.varkw is not None:
        # We do not check whether stub takes **kwargs when the runtime does, for cases where the
        # stub just listed out the extra keyword parameters the function takes
        # Also check against positional parameters, to avoid a nitpicky message when an argument
        # isn't marked as keyword-only
        stub_pos_names = set(stub_arg.variable.name for stub_arg in stub.pos)
        if not set(runtime.kwonly).issubset(set(stub.kwonly) | stub_pos_names):
            yield f'stub does not have **kwargs argument "{runtime.varkw.name}"'
    if stub.varkw is not None and runtime.varkw is None:
        yield f'runtime does not have **kwargs argument "{stub.varkw.variable.name}"'
    if runtime.varkw is None or not set(runtime.kwonly).issubset(set(stub.kwonly)):
        for arg in sorted(set(stub.kwonly) - set(runtime.kwonly)):
            yield f'runtime does not have argument "{arg}"'
    if stub.varkw is None or not set(stub.kwonly).issubset(set(runtime.kwonly)):
        for arg in sorted(set(runtime.kwonly) - set(stub.kwonly)):
            if arg in set(stub_arg.variable.name for stub_arg in stub.pos):
                yield f'stub argument "{arg}" is not keyword-only'
            else:
                yield f'stub does not have argument "{arg}"'


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

    for message in _verify_static_class_methods(stub, runtime):
        yield Error(object_path, message, stub, runtime)

    try:
        signature = inspect.signature(runtime)
    except ValueError:
        # inspect.signature throws sometimes
        return

    stub_sig = Signature.from_funcitem(stub)
    runtime_sig = Signature.from_inspect_signature(signature)

    def runtime_printer(s: Any) -> str:
        return "def " + str(inspect.signature(s))

    for message in _verify_signature(stub_sig, runtime_sig, function_name=stub.name):
        yield Error(
            object_path,
            "is inconsistent, " + message,
            stub,
            runtime,
            runtime_printer=runtime_printer,
        )


@verify.register(Missing)
def verify_none(
    stub: Missing, runtime: MaybeMissing[Any], object_path: List[str]
) -> Iterator[Error]:
    if isinstance(runtime, Missing):
        try:
            # We shouldn't really get here since that would involve something not existing both in
            # the stub and the runtime, however, some modules like distutils.command have some
            # weird things going on. Try to see if we can find a runtime object by importing it,
            # otherwise crash.
            runtime = importlib.import_module(".".join(object_path))
        except ModuleNotFoundError:
            assert False
    yield Error(object_path, "is not present in stub", stub, runtime)


@verify.register(nodes.Var)
def verify_var(
    stub: nodes.Var, runtime: MaybeMissing[Any], object_path: List[str]
) -> Iterator[Error]:
    if isinstance(runtime, Missing):
        # Don't always yield an error here, because we often can't find instance variables
        if len(object_path) <= 1:
            yield Error(object_path, "is not present at runtime", stub, runtime)
        return

    runtime_type = get_mypy_type_of_runtime_value(runtime)
    if (
        runtime_type is not None
        and stub.type is not None
        and not is_subtype_helper(runtime_type, stub.type)
    ):
        yield Error(
            object_path,
            f"variable differs from runtime type {runtime_type}",
            stub,
            runtime,
        )


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


def _verify_property(stub: nodes.Decorator, runtime: Any) -> Iterator[str]:
    assert stub.func.is_property
    if isinstance(runtime, property):
        return
    if inspect.isdatadescriptor(runtime):
        # It's enough like a property...
        return
    # Sometimes attributes pretend to be properties, for instance, to express that they
    # are read only. So whitelist if runtime_type matches the return type of stub.
    runtime_type = get_mypy_type_of_runtime_value(runtime)
    func_type = (
        stub.func.type.ret_type
        if isinstance(stub.func.type, mypy.types.CallableType)
        else None
    )
    if (
        runtime_type is not None
        and func_type is not None
        and is_subtype_helper(runtime_type, func_type)
    ):
        return
    yield "is inconsistent, cannot reconcile @property on stub with runtime object"


@verify.register(nodes.Decorator)
def verify_decorator(
    stub: nodes.Decorator, runtime: MaybeMissing[Any], object_path: List[str]
) -> Iterator[Error]:
    if isinstance(runtime, Missing):
        yield Error(object_path, "is not present at runtime", stub, runtime)
        return
    if not stub.decorators:
        # semanal.SemanticAnalyzer.visit_decorator lists the decorators that get removed (note they
        # can still be found in stub.original_decorators).
        if stub.func.is_property:
            for message in _verify_property(stub, runtime):
                yield Error(
                    object_path, message, stub, runtime,
                )
            return

        # For any of those decorators that aren't @property, just delegate to verify_funcitem
        yield from verify(stub.func, runtime, object_path)
        return
    if (
        len(stub.decorators) == 1
        and isinstance(stub.decorators[0], nodes.NameExpr)
        and stub.decorators[0].fullname == "typing.overload"
    ):
        # If the only decorator is @typing.overload, just delegate to the usual verify_funcitem
        yield from verify(stub.func, runtime, object_path)
        return


@verify.register(nodes.TypeAlias)
def verify_typealias(
    stub: nodes.TypeAlias, runtime: MaybeMissing[Any], object_path: List[str]
) -> Iterator[Error]:
    if False:
        yield None


def is_subtype_helper(left: mypy.types.Type, right: mypy.types.Type) -> bool:
    """Checks whether ``left`` is a subtype of ``right``."""
    if (
        isinstance(left, mypy.types.LiteralType)
        and isinstance(left.value, int)
        and left.value in (0, 1)
        and isinstance(right, mypy.types.Instance)
        and right.type.fullname == "builtins.bool"
    ):
        # Pretend Literal[0, 1] is a subtype of bool to avoid unhelpful errors.
        return True
    with mypy.state.strict_optional_set(True):
        return mypy.subtypes.is_subtype(left, right)


def get_mypy_type_of_runtime_value(runtime: Any) -> Optional[mypy.types.Type]:
    """Returns a mypy type object representing the type of ``runtime``.

    Returns None if we can't find something that works.

    """
    if runtime is None:
        return mypy.types.NoneType()
    if isinstance(runtime, property):
        # Give up on properties to avoid issues with things that are typed as attributes.
        return None
    if isinstance(runtime, (types.FunctionType, types.BuiltinFunctionType)):
        # TODO: Construct a mypy.types.CallableType
        return None

    # Try and look up a stub for the runtime object
    stub = get_stub(type(runtime).__module__)
    if stub is None:
        return None
    type_name = type(runtime).__name__
    if type_name not in stub.names:
        return None
    type_info = stub.names[type_name].node
    if not isinstance(type_info, nodes.TypeInfo):
        return None

    anytype = lambda: mypy.types.AnyType(mypy.types.TypeOfAny.unannotated)

    if isinstance(runtime, tuple):
        # Special case tuples so we construct a valid mypy.types.TupleType
        opt_items = [get_mypy_type_of_runtime_value(v) for v in runtime]
        items = [(i if i is not None else anytype()) for i in opt_items]
        fallback = mypy.types.Instance(type_info, [anytype()])
        return mypy.types.TupleType(items, fallback)

    # Technically, Literals are supposed to be only bool, int, str or bytes, but this
    # seems to work fine
    return mypy.types.LiteralType(
        value=runtime,
        fallback=mypy.types.Instance(
            type_info, [anytype() for _ in type_info.type_vars]
        ),
    )


_all_stubs: Dict[str, nodes.MypyFile] = {}


def build_stubs(modules: List[str], options: Options) -> None:
    """Uses mypy to construct stub objects for the given modules.

    This sets global state that ``get_stub`` can access.

    """
    data_dir = mypy.build.default_data_dir()
    search_path = mypy.modulefinder.compute_search_paths([], options, data_dir)
    find_module_cache = mypy.modulefinder.FindModuleCache(search_path)

    sources = []
    # TODO: restore support for automatically recursing into submodules with find_modules_recursive
    for module in modules:
        module_path = find_module_cache.find_module(module)
        if module_path is None:
            # test_module will yield an error later when it can't find stubs
            continue
        sources.append(mypy.modulefinder.BuildSource(module_path, module, None))

    res = mypy.build.build(sources=sources, options=options)
    if res.errors:
        output = [
            _style("error: ", color="red", bold=True),
            " failed mypy build.\n",
        ]
        print("".join(output) + "\n".join(res.errors))
        sys.exit(1)

    global _all_stubs
    _all_stubs = res.files


def get_stub(module: str) -> Optional[nodes.MypyFile]:
    """Returns a stub object for the given module, if we've built one."""
    return _all_stubs.get(module)


def get_typeshed_stdlib_modules(custom_typeshed_dir: Optional[str]) -> List[str]:
    """Returns a list of stdlib modules in typeshed (for current Python version)."""
    # This snippet is based on code in mypy.modulefinder.default_lib_path
    if custom_typeshed_dir:
        typeshed_dir = Path(custom_typeshed_dir)
    else:
        typeshed_dir = Path(mypy.build.default_data_dir())
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


def get_whitelist_entries(whitelist_file: Optional[str]) -> Iterator[str]:
    if not whitelist_file:
        return

    def strip_comments(s: str) -> str:
        try:
            return s[: s.index("#")].strip()
        except ValueError:
            return s.strip()

    with open(whitelist_file) as f:
        for line in f.readlines():
            entry = strip_comments(line)
            if entry:
                yield entry


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
        help="Use file as a whitelist. Whitelists can be created with --generate-whitelist",
    )
    parser.add_argument(
        "--concise", action="store_true", help="Make output concise",
    )
    parser.add_argument(
        "--generate-whitelist",
        action="store_true",
        help="Print a whitelist (to stdout) to be used with --whitelist",
    )
    args = parser.parse_args()

    # Load the whitelist. This is a series of strings corresponding to Error.object_desc
    # Values in the dict will store whether we used the whitelist entry or not.
    whitelist = {entry: False for entry in get_whitelist_entries(args.whitelist)}

    # If we need to generate a whitelist, we store Error.object_desc for each error here.
    generated_whitelist = set()

    modules = args.modules
    if args.check_typeshed:
        assert (
            not args.modules
        ), "Cannot pass both --check-typeshed and a list of modules"
        modules = get_typeshed_stdlib_modules(args.custom_typeshed_dir)
        modules.remove("antigravity")  # it's super annoying

    assert modules, "No modules to check"

    options = Options()
    options.incremental = False
    options.custom_typeshed_dir = args.custom_typeshed_dir

    build_stubs(modules, options)

    exit_code = 0
    for module in modules:
        for error in test_module(module):
            # Filter errors
            if args.ignore_missing_stub and error.is_missing_stub():
                continue
            if error.object_desc in whitelist:
                whitelist[error.object_desc] = True
                continue

            # We have errors, so change exit code, and output whatever necessary
            exit_code = 1
            if args.generate_whitelist:
                generated_whitelist.add(error.object_desc)
                continue
            print(error.get_description(concise=args.concise))

    # Print unused whitelist entries
    for w in whitelist:
        if not whitelist[w]:
            exit_code = 1
            print(f"note: unused whitelist entry {w}")

    # Print the generated whitelist
    if args.generate_whitelist:
        for e in sorted(generated_whitelist):
            print(e)
        exit_code = 0

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
