import os
import tempfile
from unittest import TestCase

from mypy.dmypy_server import Server
from mypy.dmypy_util import DEFAULT_STATUS_FILE
from mypy.find_sources import create_source_list
from mypy.generic_suggestions import (
    find_callback_application,
    find_dictionary_lookup,
    find_direct_returned_argument,
    find_indexed_returned_argument,
    infer_generic_candidates,
    make_callback_generic,
    make_dictionary_generic,
    make_direct_return_generic,
    make_list_element_generic,
    make_tuple_element_generic,
)
from mypy.nodes import (
    ARG_POS,
    Argument,
    AssignmentStmt,
    Block,
    CallExpr,
    ClassDef,
    FuncDef,
    IndexExpr,
    IntExpr,
    NameExpr,
    OperatorAssignmentStmt,
    ReturnStmt,
    SymbolTable,
    TypeInfo,
    Var,
)
from mypy.options import Options
from mypy.suggestions import has_new_errors
from mypy.types import (
    AnyType,
    CallableType,
    Instance,
    TupleType,
    Type,
    TypeOfAny,
    TypeVarType,
    get_proper_type,
)


def make_function(argument_names: list[str], returned_name: str | None) -> FuncDef:
    variables = [Var(name) for name in argument_names]

    arguments = [Argument(variable, None, None, ARG_POS) for variable in variables]

    if returned_name is None:
        expression = IntExpr(42)
    else:
        expression = NameExpr(returned_name)
        expression.node = next(var for var in variables if var.name == returned_name)

    return FuncDef("example", arguments, Block([ReturnStmt(expression)]))


def make_instance(fullname: str) -> Instance:
    module, _, name = fullname.rpartition(".")

    class_def = ClassDef(name, Block([]), None, [])
    class_def.fullname = fullname

    info = TypeInfo(SymbolTable(), class_def, module)
    info.mro = [info]

    return Instance(info, [])


def make_indexed_function(
    names: list[str], collection_index: int, key_index: int | None = None
) -> FuncDef:
    func = make_function(names, names[collection_index])

    collection = NameExpr(names[collection_index])
    collection.node = func.arguments[collection_index].variable

    if key_index is None:
        index = IntExpr(0)
    else:
        index = NameExpr(names[key_index])
        index.node = func.arguments[key_index].variable

    func.body.body = [ReturnStmt(IndexExpr(collection, index))]

    return func


def make_callback_function(names: list[str], callback_index: int, arg_index: int) -> FuncDef:
    func = make_function(names, names[callback_index])

    callee = NameExpr(names[callback_index])
    callee.node = func.arguments[callback_index].variable

    arg = NameExpr(names[arg_index])
    arg.node = func.arguments[arg_index].variable

    func.body.body = [ReturnStmt(CallExpr(callee, [arg], [ARG_POS], [None]))]

    return func


class GenericSuggestionsTests(TestCase):
    def test_identity(self) -> None:
        func = make_function(["x"], "x")
        assert find_direct_returned_argument(func) == 0

    def test_first_argument(self) -> None:
        func = make_function(["x", "y"], "x")
        assert find_direct_returned_argument(func) == 0

    def test_second_argument(self) -> None:
        func = make_function(["x", "y"], "y")
        assert find_direct_returned_argument(func) == 1

    def test_constant_return(self) -> None:
        func = make_function(["x"], None)
        assert find_direct_returned_argument(func) is None

    def test_multiple_same_returns(self) -> None:
        func = make_function(["x", "y"], "x")

        expr = NameExpr("x")
        expr.node = func.arguments[0].variable
        func.body.body.append(ReturnStmt(expr))

        assert find_direct_returned_argument(func) == 0

    def test_multiple_different_returns(self) -> None:
        func = make_function(["x", "y"], "x")

        expr = NameExpr("y")
        expr.node = func.arguments[1].variable
        func.body.body.append(ReturnStmt(expr))

        assert find_direct_returned_argument(func) is None

    def test_no_return(self) -> None:
        func = make_function(["x"], "x")
        func.body.body.clear()

        assert find_direct_returned_argument(func) is None

    def test_make_generic_identity(self) -> None:
        object_type = make_instance("builtins.object")
        function_type = make_instance("builtins.function")

        any_type = AnyType(TypeOfAny.suggestion_engine)

        base = CallableType([any_type], [ARG_POS], ["value"], any_type, function_type)

        candidate = make_direct_return_generic(base, 0, object_type)

        assert candidate is not None
        assert len(candidate.variables) == 1

        type_var = candidate.variables[0]
        assert isinstance(type_var, TypeVarType)
        assert type_var.name == "T"

        assert candidate.arg_types[0] is type_var
        assert candidate.ret_type is type_var

    def test_indexed_return(self) -> None:
        func = make_function(["items"], "items")

        expr = NameExpr("items")
        expr.node = func.arguments[0].variable

        func.body.body = [ReturnStmt(IndexExpr(expr, IntExpr(0)))]

        assert find_indexed_returned_argument(func) == 0

    def test_make_list_generic(self) -> None:
        any_type = AnyType(TypeOfAny.suggestion_engine)

        base = CallableType(
            [any_type], [ARG_POS], ["items"], any_type, make_instance("builtins.function")
        )

        candidate = make_list_element_generic(
            base, 0, make_instance("builtins.list"), make_instance("builtins.object")
        )

        assert candidate is not None
        assert len(candidate.variables) == 1

        type_var = candidate.variables[0]
        assert isinstance(type_var, TypeVarType)

        list_arg = get_proper_type(candidate.arg_types[0])
        assert isinstance(list_arg, Instance)
        assert list_arg.type.fullname == "builtins.list"

        assert list_arg.args[0] is type_var
        assert candidate.ret_type is type_var

    def test_dictionary_lookup(self) -> None:
        func = make_function(["mapping", "key"], "mapping")

        mapping = NameExpr("mapping")
        mapping.node = func.arguments[0].variable

        key = NameExpr("key")
        key.node = func.arguments[1].variable

        func.body.body = [ReturnStmt(IndexExpr(mapping, key))]

        assert find_dictionary_lookup(func) == (0, 1)

    def test_dictionary_lookup_with_other_return(self) -> None:
        func = make_function(["mapping", "key"], "mapping")

        mapping = NameExpr("mapping")
        mapping.node = func.arguments[0].variable

        key = NameExpr("key")
        key.node = func.arguments[1].variable

        func.body.body = [ReturnStmt(IndexExpr(mapping, key)), ReturnStmt(IntExpr(42))]

        assert find_dictionary_lookup(func) is None

    def test_make_dictionary_generic(self) -> None:
        any_type = AnyType(TypeOfAny.suggestion_engine)

        base = CallableType(
            [any_type, any_type],
            [ARG_POS, ARG_POS],
            ["mapping", "key"],
            any_type,
            make_instance("builtins.function"),
        )

        candidate = make_dictionary_generic(
            base, 0, 1, make_instance("builtins.dict"), make_instance("builtins.object")
        )

        assert candidate is not None
        assert len(candidate.variables) == 2

        key_var, value_var = candidate.variables

        assert isinstance(key_var, TypeVarType)
        assert isinstance(value_var, TypeVarType)

        mapping_type = get_proper_type(candidate.arg_types[0])
        assert isinstance(mapping_type, Instance)

        assert mapping_type.type.fullname == "builtins.dict"
        assert mapping_type.args == (key_var, value_var)

        assert candidate.arg_types[1] is key_var
        assert candidate.ret_type is value_var

    def test_make_tuple_generic(self) -> None:
        any_type = AnyType(TypeOfAny.suggestion_engine)

        base = CallableType(
            [any_type], [ARG_POS], ["items"], any_type, make_instance("builtins.function")
        )

        candidate = make_tuple_element_generic(
            base, 0, make_instance("builtins.tuple"), make_instance("builtins.object")
        )

        assert candidate is not None
        assert len(candidate.variables) == 1

        type_var = candidate.variables[0]
        assert isinstance(type_var, TypeVarType)

        tuple_arg = get_proper_type(candidate.arg_types[0])
        assert isinstance(tuple_arg, Instance)
        assert tuple_arg.type.fullname == "builtins.tuple"

        assert tuple_arg.args[0] is type_var
        assert candidate.ret_type is type_var

    def test_reject_wrong_collection_type(self) -> None:
        any_type = AnyType(TypeOfAny.suggestion_engine)

        base = CallableType(
            [any_type], [ARG_POS], ["items"], any_type, make_instance("builtins.function")
        )

        candidate = make_tuple_element_generic(
            base, 0, make_instance("builtins.list"), make_instance("builtins.object")
        )

        assert candidate is None

    def test_reassigned_argument(self) -> None:
        func = make_function(["x"], "x")

        target = NameExpr("x")
        target.node = func.arguments[0].variable

        assignment = AssignmentStmt([target], IntExpr(42))

        func.body.body.insert(0, assignment)

        assert find_direct_returned_argument(func) is None

    def test_other_argument_reassigned(self) -> None:
        func = make_function(["x", "y"], "x")

        target = NameExpr("y")
        target.node = func.arguments[1].variable

        assignment = AssignmentStmt([target], IntExpr(42))

        func.body.body.insert(0, assignment)

        assert find_direct_returned_argument(func) == 0

    def test_augmented_assignment(self) -> None:
        func = make_function(["x"], "x")

        target = NameExpr("x")
        target.node = func.arguments[0].variable

        assignment = OperatorAssignmentStmt("+=", target, IntExpr(1))

        func.body.body.insert(0, assignment)

        assert find_direct_returned_argument(func) is None

    def test_infer_generic_identity(self) -> None:
        any_type = AnyType(TypeOfAny.suggestion_engine)

        base = CallableType(
            [any_type], [ARG_POS], ["value"], any_type, make_instance("builtins.function")
        )

        func = make_function(["value"], "value")

        int_type = make_instance("builtins.int")
        str_type = make_instance("builtins.str")

        callsites = [[[int_type]], [[str_type]]]

        candidates = infer_generic_candidates(func, base, callsites, make_instance)

        assert len(candidates) == 1

        candidate = candidates[0]

        assert len(candidate.variables) == 1
        assert candidate.arg_types[0] == candidate.ret_type

    def test_no_generic_for_single_call(self) -> None:
        any_type = AnyType(TypeOfAny.suggestion_engine)

        base = CallableType(
            [any_type], [ARG_POS], ["value"], any_type, make_instance("builtins.function")
        )

        func = make_function(["value"], "value")

        candidates = infer_generic_candidates(
            func, base, [[[make_instance("builtins.int")]]], make_instance
        )

        assert candidates == []

    def test_infer_list_generic(self) -> None:
        any_type = AnyType(TypeOfAny.suggestion_engine)

        base = CallableType(
            [any_type], [ARG_POS], ["items"], any_type, make_instance("builtins.function")
        )

        func = make_indexed_function(["items"], 0)

        list_type = make_instance("builtins.list")
        int_type = make_instance("builtins.int")
        str_type = make_instance("builtins.str")

        callsites = [
            [[list_type.copy_modified(args=[int_type])]],
            [[list_type.copy_modified(args=[str_type])]],
        ]

        candidates = infer_generic_candidates(func, base, callsites, make_instance)

        assert len(candidates) == 1

        candidate = candidates[0]
        collection = get_proper_type(candidate.arg_types[0])

        assert isinstance(collection, Instance)
        assert collection.type.fullname == "builtins.list"
        assert collection.args[0] is candidate.ret_type

    def test_infer_tuple_generic(self) -> None:
        any_type = AnyType(TypeOfAny.suggestion_engine)

        base = CallableType(
            [any_type], [ARG_POS], ["items"], any_type, make_instance("builtins.function")
        )

        func = make_indexed_function(["items"], 0)

        tuple_type = make_instance("builtins.tuple")
        int_type = make_instance("builtins.int")
        str_type = make_instance("builtins.str")

        callsites = [
            [[TupleType([int_type, int_type], tuple_type)]],
            [[TupleType([str_type, str_type], tuple_type)]],
        ]

        candidates = infer_generic_candidates(func, base, callsites, make_instance)

        assert len(candidates) == 1

        candidate = candidates[0]
        collection = get_proper_type(candidate.arg_types[0])

        assert isinstance(collection, Instance)
        assert collection.type.fullname == "builtins.tuple"
        assert collection.args[0] is candidate.ret_type

    def test_infer_dictionary_generic(self) -> None:
        any_type = AnyType(TypeOfAny.suggestion_engine)

        base = CallableType(
            [any_type, any_type],
            [ARG_POS, ARG_POS],
            ["mapping", "key"],
            any_type,
            make_instance("builtins.function"),
        )

        func = make_indexed_function(["mapping", "key"], 0, 1)

        dict_type = make_instance("builtins.dict")
        str_type = make_instance("builtins.str")
        int_type = make_instance("builtins.int")
        bool_type = make_instance("builtins.bool")

        callsites = [
            [[dict_type.copy_modified(args=[str_type, int_type])], [str_type]],
            [[dict_type.copy_modified(args=[int_type, bool_type])], [int_type]],
        ]

        candidates = infer_generic_candidates(func, base, callsites, make_instance)

        assert len(candidates) == 1

        candidate = candidates[0]

        assert len(candidate.variables) == 2
        key_var, value_var = candidate.variables

        mapping = get_proper_type(candidate.arg_types[0])

        assert isinstance(mapping, Instance)
        assert mapping.args == (key_var, value_var)
        assert candidate.arg_types[1] is key_var
        assert candidate.ret_type is value_var

    def test_reject_mismatched_dictionary_key(self) -> None:
        any_type = AnyType(TypeOfAny.suggestion_engine)

        base = CallableType(
            [any_type, any_type],
            [ARG_POS, ARG_POS],
            ["mapping", "key"],
            any_type,
            make_instance("builtins.function"),
        )

        func = make_indexed_function(["mapping", "key"], 0, 1)

        dict_type = make_instance("builtins.dict")
        str_type = make_instance("builtins.str")
        int_type = make_instance("builtins.int")

        callsites = [
            [[dict_type.copy_modified(args=[str_type, int_type])], [int_type]],
            [[dict_type.copy_modified(args=[str_type, int_type])], [str_type]],
        ]

        candidates = infer_generic_candidates(func, base, callsites, make_instance)

        assert candidates == []

    def test_callback_application(self) -> None:
        func = make_callback_function(["f", "x"], 0, 1)
        assert find_callback_application(func) == (0, 1)

    def test_callback_application_reversed_params(self) -> None:
        func = make_callback_function(["x", "f"], 1, 0)
        assert find_callback_application(func) == (1, 0)

    def test_make_callback_generic(self) -> None:
        any_type = AnyType(TypeOfAny.suggestion_engine)
        function_type = make_instance("builtins.function")

        base = CallableType(
            [any_type, any_type], [ARG_POS, ARG_POS], ["f", "x"], any_type, function_type
        )

        candidate = make_callback_generic(
            base, 0, 1, make_instance("builtins.object"), function_type
        )

        assert candidate is not None
        assert len(candidate.variables) == 2

        arg_var, ret_var = candidate.variables
        assert isinstance(arg_var, TypeVarType)
        assert isinstance(ret_var, TypeVarType)
        assert arg_var.name == "T"
        assert ret_var.name == "R"

        cb_type = get_proper_type(candidate.arg_types[0])
        assert isinstance(cb_type, CallableType)
        assert cb_type.arg_types == [arg_var]
        assert cb_type.ret_type is ret_var
        assert candidate.arg_types[1] is arg_var
        assert candidate.ret_type is ret_var

    def test_infer_callback_generic(self) -> None:
        any_type = AnyType(TypeOfAny.suggestion_engine)
        function_type = make_instance("builtins.function")

        base = CallableType(
            [any_type, any_type], [ARG_POS, ARG_POS], ["f", "x"], any_type, function_type
        )

        func = make_callback_function(["f", "x"], 0, 1)

        int_type = make_instance("builtins.int")
        str_type = make_instance("builtins.str")
        bool_type = make_instance("builtins.bool")

        cb1 = CallableType([int_type], [ARG_POS], [None], str_type, function_type)
        cb2 = CallableType([str_type], [ARG_POS], [None], bool_type, function_type)

        callsites: list[list[list[Type]]] = [[[cb1], [int_type]], [[cb2], [str_type]]]

        candidates = infer_generic_candidates(func, base, callsites, make_instance)

        assert len(candidates) == 1
        candidate = candidates[0]
        assert len(candidate.variables) == 2
        arg_var, ret_var = candidate.variables
        cb_arg = get_proper_type(candidate.arg_types[0])
        assert isinstance(cb_arg, CallableType)
        assert cb_arg.arg_types == [arg_var]
        assert cb_arg.ret_type is ret_var
        assert candidate.arg_types[1] is arg_var
        assert candidate.ret_type is ret_var

    def test_reject_mismatched_callback_arg(self) -> None:
        any_type = AnyType(TypeOfAny.suggestion_engine)
        function_type = make_instance("builtins.function")

        base = CallableType(
            [any_type, any_type], [ARG_POS, ARG_POS], ["f", "x"], any_type, function_type
        )

        func = make_callback_function(["f", "x"], 0, 1)

        int_type = make_instance("builtins.int")
        str_type = make_instance("builtins.str")

        cb1 = CallableType([int_type], [ARG_POS], [None], str_type, function_type)
        cb2 = CallableType([str_type], [ARG_POS], [None], int_type, function_type)

        callsites: list[list[list[Type]]] = [[[cb1], [str_type]], [[cb2], [int_type]]]

        candidates = infer_generic_candidates(func, base, callsites, make_instance)

        assert candidates == []

    def test_infer_generic_min_calls(self) -> None:
        any_type = AnyType(TypeOfAny.suggestion_engine)

        base = CallableType(
            [any_type], [ARG_POS], ["value"], any_type, make_instance("builtins.function")
        )

        func = make_function(["value"], "value")

        int_type = make_instance("builtins.int")
        str_type = make_instance("builtins.str")
        bool_type = make_instance("builtins.bool")

        two_calls = [[[int_type]], [[str_type]]]
        three_calls = [[[int_type]], [[str_type]], [[bool_type]]]

        assert infer_generic_candidates(func, base, two_calls, make_instance, min_calls=3) == []
        assert (
            len(infer_generic_candidates(func, base, three_calls, make_instance, min_calls=3)) == 1
        )

    def test_no_new_errors(self) -> None:
        original = ["foo.py:5: error: Error A"]
        proposed = ["foo.py:5: error: Error A"]

        assert not has_new_errors(original, proposed)

    def test_reject_different_error(self) -> None:
        original = ["foo.py:5: error: Error A"]
        proposed = ["foo.py:8: error: Error B"]

        assert has_new_errors(original, proposed)

    def test_allow_removed_errors(self) -> None:
        original = ["foo.py:5: error: Error A"]
        proposed: list[str] = []

        assert not has_new_errors(original, proposed)

    def test_reject_additional_error(self) -> None:
        original = ["foo.py:5: error: Error A"]
        proposed = ["foo.py:5: error: Error A", "foo.py:8: error: Error B"]

        assert has_new_errors(original, proposed)


class DmypySuggestGenericIntegrationTests(TestCase):
    """End-to-end integration tests running dmypy suggest on real Python files."""

    tmpdir: tempfile.TemporaryDirectory[str]
    server: Server

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmpdir = tempfile.TemporaryDirectory()
        mod_path = os.path.join(cls.tmpdir.name, "sample.py")
        source = """
def identity(value):
    return value

def first_list(items):
    return items[0]

def first_tuple(items):
    return items[0]

def lookup(mapping, key):
    return mapping[key]

def apply(f, x):
    return f(x)

def to_str(n: int) -> str:
    return str(n)

def str_len(s: str) -> int:
    return len(s)

def add_self(x):
    y = x + x
    return x

def same_type_identity(value):
    return value

def single_call_identity(value):
    return value

class Box:
    def echo(self, item):
        return item

a_id: int = identity(1)
b_id: str = identity(value="hello")

a_list: int = first_list([1, 2, 3])
b_list: str = first_list(["a", "b"])

a_tuple: int = first_tuple((1, 2))
b_tuple: str = first_tuple(("a", "b"))

a_dict: int = lookup({"x": 1}, "x")
b_dict: str = lookup({10: "ten"}, 10)

a_cb: str = apply(to_str, 42)
b_cb: int = apply(str_len, "abc")

add_self(1)
add_self("abc")

same_type_identity(1)
same_type_identity(2)

single_call_identity(1)

box = Box()
a_box: int = box.echo(1)
b_box: str = box.echo("hello")
"""
        with open(mod_path, "w", encoding="utf-8") as f:
            f.write(source)

        options = Options()
        options.incremental = True
        options.fine_grained_incremental = True
        options.local_partial_types = True
        options.show_traceback = True
        options.error_summary = False

        status_file = os.path.join(cls.tmpdir.name, DEFAULT_STATUS_FILE)
        cls.server = Server(options, status_file)
        sources = create_source_list([mod_path], options)
        cls.server.check(sources, export_types=False, is_tty=False, terminal_width=-1)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmpdir.cleanup()

    def suggest(
        self,
        target: str,
        *,
        generic_min_calls: int | None = None,
        json: bool = False,
        no_errors: bool = False,
        no_any: bool = False,
    ) -> str:
        res = self.server.cmd_suggest(
            f"sample.{target}",
            callsites=False,
            json=json,
            no_errors=no_errors,
            no_any=no_any,
            flex_any=None,
            use_fixme=None,
            max_guesses=None,
            generic_min_calls=generic_min_calls,
        )
        assert "out" in res, f"Unexpected error: {res}"
        out = res["out"]
        assert isinstance(out, str)
        return out.strip()

    def test_dmypy_suggest_identity_generic(self) -> None:
        assert self.suggest("identity", no_errors=True) == "[T](T) -> T"

    def test_dmypy_suggest_list_generic(self) -> None:
        assert self.suggest("first_list", no_errors=True) == "[T](list[T]) -> T"

    def test_dmypy_suggest_tuple_generic(self) -> None:
        assert self.suggest("first_tuple", no_errors=True) == "[T](tuple[T, ...]) -> T"

    def test_dmypy_suggest_dict_generic(self) -> None:
        assert self.suggest("lookup", no_errors=True) == "[K, V](dict[K, V], K) -> V"

    def test_dmypy_suggest_callback_generic(self) -> None:
        assert self.suggest("apply", no_errors=True) == "[T, R](Callable[[T], R], T) -> R"

    def test_dmypy_suggest_method_generic(self) -> None:
        assert self.suggest("Box.echo", no_errors=True) == "[T](T) -> T"

    def test_dmypy_suggest_min_calls_option(self) -> None:
        assert self.suggest("identity", generic_min_calls=3) == "(object) -> object"
        assert self.suggest("identity", generic_min_calls=2) == "[T](T) -> T"

    def test_dmypy_suggest_rejects_generic_when_body_constrains_type(self) -> None:
        assert self.suggest("add_self") == "(object) -> object"

    def test_dmypy_suggest_rejects_generic_for_same_type_calls(self) -> None:
        assert self.suggest("same_type_identity") == "(int) -> int"

    def test_dmypy_suggest_rejects_generic_for_single_call(self) -> None:
        assert self.suggest("single_call_identity") == "(int) -> int"
