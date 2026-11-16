from unittest import TestCase

from mypy.generic_suggestions import (
    find_dictionary_lookup,
    find_direct_returned_argument,
    find_indexed_returned_argument,
    infer_generic_candidates,
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
from mypy.types import (
    AnyType,
    CallableType,
    Instance,
    TupleType,
    TypeOfAny,
    TypeVarType,
)


def make_function(
    argument_names: list[str],
    returned_name: str | None,
) -> FuncDef:
    variables = [Var(name) for name in argument_names]

    arguments = [
        Argument(variable, None, None, ARG_POS)
        for variable in variables
    ]

    if returned_name is None:
        expression = IntExpr(42)
    else:
        expression = NameExpr(returned_name)
        expression.node = next(
            var for var in variables
            if var.name == returned_name
        )

    return FuncDef(
        "example",
        arguments,
        Block([ReturnStmt(expression)]),
    )

def make_instance(fullname: str) -> Instance:
    module, _, name = fullname.rpartition(".")

    class_def = ClassDef(name, Block([]), None, [])
    class_def.fullname = fullname

    info = TypeInfo(SymbolTable(), class_def, module)
    info.mro = [info]

    return Instance(info, [])


def make_indexed_function(
    names: list[str],
    collection_index: int,
    key_index: int | None = None,
) -> FuncDef:
    func = make_function(
        names, names[collection_index]
    )

    collection = NameExpr(names[collection_index])
    collection.node = func.arguments[
        collection_index
    ].variable

    if key_index is None:
        index = IntExpr(0)
    else:
        index = NameExpr(names[key_index])
        index.node = func.arguments[key_index].variable

    func.body.body = [
        ReturnStmt(IndexExpr(collection, index))
    ]

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

        base = CallableType(
            [any_type],
            [ARG_POS],
            ["value"],
            any_type,
            function_type,
        )

        candidate = make_direct_return_generic(
            base, 0, object_type
        )

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

        func.body.body = [
            ReturnStmt(IndexExpr(expr, IntExpr(0)))
        ]

        assert find_indexed_returned_argument(func) == 0

    def test_make_list_generic(self) -> None:
        any_type = AnyType(TypeOfAny.suggestion_engine)

        base = CallableType(
            [any_type],
            [ARG_POS],
            ["items"],
            any_type,
            make_instance("builtins.function"),
        )

        candidate = make_list_element_generic(
            base,
            0,
            make_instance("builtins.list"),
            make_instance("builtins.object"),
        )

        assert candidate is not None
        assert len(candidate.variables) == 1

        type_var = candidate.variables[0]
        assert isinstance(type_var, TypeVarType)

        list_arg = candidate.arg_types[0]
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

        func.body.body = [
            ReturnStmt(IndexExpr(mapping, key))
        ]

        assert find_dictionary_lookup(func) == (0, 1)

    def test_dictionary_lookup_with_other_return(self) -> None:
        func = make_function(["mapping", "key"], "mapping")

        mapping = NameExpr("mapping")
        mapping.node = func.arguments[0].variable

        key = NameExpr("key")
        key.node = func.arguments[1].variable

        func.body.body = [
            ReturnStmt(IndexExpr(mapping, key)),
            ReturnStmt(IntExpr(42)),
        ]

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
            base,
            0,
            1,
            make_instance("builtins.dict"),
            make_instance("builtins.object"),
        )

        assert candidate is not None
        assert len(candidate.variables) == 2

        key_var, value_var = candidate.variables

        assert isinstance(key_var, TypeVarType)
        assert isinstance(value_var, TypeVarType)

        mapping_type = candidate.arg_types[0]
        assert isinstance(mapping_type, Instance)

        assert mapping_type.type.fullname == "builtins.dict"
        assert mapping_type.args == (key_var, value_var)

        assert candidate.arg_types[1] is key_var
        assert candidate.ret_type is value_var


    def test_make_tuple_generic(self) -> None:
        any_type = AnyType(TypeOfAny.suggestion_engine)

        base = CallableType(
            [any_type],
            [ARG_POS],
            ["items"],
            any_type,
            make_instance("builtins.function"),
        )

        candidate = make_tuple_element_generic(
            base,
            0,
            make_instance("builtins.tuple"),
            make_instance("builtins.object"),
        )

        assert candidate is not None
        assert len(candidate.variables) == 1

        type_var = candidate.variables[0]
        assert isinstance(type_var, TypeVarType)

        tuple_arg = candidate.arg_types[0]
        assert isinstance(tuple_arg, Instance)
        assert tuple_arg.type.fullname == "builtins.tuple"

        assert tuple_arg.args[0] is type_var
        assert candidate.ret_type is type_var

    def test_reject_wrong_collection_type(self) -> None:
        any_type = AnyType(TypeOfAny.suggestion_engine)

        base = CallableType(
            [any_type],
            [ARG_POS],
            ["items"],
            any_type,
            make_instance("builtins.function"),
        )

        candidate = make_tuple_element_generic(
            base,
            0,
            make_instance("builtins.list"),
            make_instance("builtins.object"),
        )

        assert candidate is None


    def test_reassigned_argument(self) -> None:
        func = make_function(["x"], "x")

        target = NameExpr("x")
        target.node = func.arguments[0].variable

        assignment = AssignmentStmt(
            [target], IntExpr(42)
        )

        func.body.body.insert(0, assignment)

        assert find_direct_returned_argument(func) is None

    def test_other_argument_reassigned(self) -> None:
        func = make_function(["x", "y"], "x")

        target = NameExpr("y")
        target.node = func.arguments[1].variable

        assignment = AssignmentStmt(
            [target], IntExpr(42)
        )

        func.body.body.insert(0, assignment)

        assert find_direct_returned_argument(func) == 0

    def test_augmented_assignment(self) -> None:
        func = make_function(["x"], "x")

        target = NameExpr("x")
        target.node = func.arguments[0].variable

        assignment = OperatorAssignmentStmt(
            "+=", target, IntExpr(1)
        )

        func.body.body.insert(0, assignment)

        assert find_direct_returned_argument(func) is None

    def test_infer_generic_identity(self) -> None:
        any_type = AnyType(TypeOfAny.suggestion_engine)

        base = CallableType(
            [any_type],
            [ARG_POS],
            ["value"],
            any_type,
            make_instance("builtins.function"),
        )

        func = make_function(["value"], "value")

        int_type = make_instance("builtins.int")
        str_type = make_instance("builtins.str")

        callsites = [
            [[int_type]],
            [[str_type]],
        ]

        candidates = infer_generic_candidates(
            func,
            base,
            callsites,
            make_instance,
        )

        assert len(candidates) == 1

        candidate = candidates[0]

        assert len(candidate.variables) == 1
        assert candidate.arg_types[0] == candidate.ret_type

    def test_no_generic_for_single_call(self) -> None:
        any_type = AnyType(TypeOfAny.suggestion_engine)

        base = CallableType(
            [any_type],
            [ARG_POS],
            ["value"],
            any_type,
            make_instance("builtins.function"),
        )

        func = make_function(["value"], "value")

        candidates = infer_generic_candidates(
            func,
            base,
            [[[make_instance("builtins.int")]]],
            make_instance,
        )

        assert candidates == []

    def test_infer_list_generic(self) -> None:
        any_type = AnyType(TypeOfAny.suggestion_engine)

        base = CallableType(
            [any_type],
            [ARG_POS],
            ["items"],
            any_type,
            make_instance("builtins.function"),
        )

        func = make_indexed_function(["items"], 0)

        list_type = make_instance("builtins.list")
        int_type = make_instance("builtins.int")
        str_type = make_instance("builtins.str")

        callsites = [
            [[list_type.copy_modified(args=[int_type])]],
            [[list_type.copy_modified(args=[str_type])]],
        ]

        candidates = infer_generic_candidates(
            func, base, callsites, make_instance
        )

        assert len(candidates) == 1

        candidate = candidates[0]
        collection = candidate.arg_types[0]

        assert isinstance(collection, Instance)
        assert collection.type.fullname == "builtins.list"
        assert collection.args[0] is candidate.ret_type

    def test_infer_tuple_generic(self) -> None:
        any_type = AnyType(TypeOfAny.suggestion_engine)

        base = CallableType(
            [any_type],
            [ARG_POS],
            ["items"],
            any_type,
            make_instance("builtins.function"),
        )

        func = make_indexed_function(["items"], 0)

        tuple_type = make_instance("builtins.tuple")
        int_type = make_instance("builtins.int")
        str_type = make_instance("builtins.str")

        callsites = [
            [[TupleType([int_type, int_type], tuple_type)]],
            [[TupleType([str_type, str_type], tuple_type)]],
        ]

        candidates = infer_generic_candidates(
            func, base, callsites, make_instance
        )

        assert len(candidates) == 1

        candidate = candidates[0]
        collection = candidate.arg_types[0]

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

        func = make_indexed_function(
            ["mapping", "key"], 0, 1
        )

        dict_type = make_instance("builtins.dict")
        str_type = make_instance("builtins.str")
        int_type = make_instance("builtins.int")
        bool_type = make_instance("builtins.bool")

        callsites = [
            [
                [dict_type.copy_modified(
                    args=[str_type, int_type]
                )],
                [str_type],
            ],
            [
                [dict_type.copy_modified(
                    args=[int_type, bool_type]
                )],
                [int_type],
            ],
        ]

        candidates = infer_generic_candidates(
            func, base, callsites, make_instance
        )

        assert len(candidates) == 1

        candidate = candidates[0]

        assert len(candidate.variables) == 2
        key_var, value_var = candidate.variables

        mapping = candidate.arg_types[0]

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

        func = make_indexed_function(
            ["mapping", "key"], 0, 1
        )

        dict_type = make_instance("builtins.dict")
        str_type = make_instance("builtins.str")
        int_type = make_instance("builtins.int")

        callsites = [
            [
                [dict_type.copy_modified(
                    args=[str_type, int_type]
                )],
                [int_type],
            ],
            [
                [dict_type.copy_modified(
                    args=[str_type, int_type]
                )],
                [str_type],
            ],
        ]

        candidates = infer_generic_candidates(
            func, base, callsites, make_instance
        )

        assert candidates == []
