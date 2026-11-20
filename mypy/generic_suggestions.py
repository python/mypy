"""Helpers for detecting generic type relationships."""

from collections.abc import Callable, Sequence

from mypy.erasetype import remove_instance_last_known_values
from mypy.nodes import (
    ARG_OPT,
    ARG_POS,
    AssignmentExpr,
    AssignmentStmt,
    CallExpr,
    DelStmt,
    Expression,
    ForStmt,
    FuncDef,
    IndexExpr,
    IntExpr,
    ListExpr,
    NameExpr,
    OperatorAssignmentStmt,
    ReturnStmt,
    StarExpr,
    TupleExpr,
    Var,
    WithStmt,
)
from mypy.traverser import TraverserVisitor
from mypy.types import (
    AnyType,
    CallableType,
    Instance,
    TupleType,
    Type,
    TypeOfAny,
    TypeVarId,
    TypeVarType,
    get_proper_type,
)


class ReturnedArgumentFinder(TraverserVisitor):
    """Find arguments returned directly by a function."""

    def __init__(self, func: FuncDef) -> None:
        self.arguments = [arg.variable for arg in func.arguments]
        self.returned: list[int | None] = []

    def visit_return_stmt(self, stmt: ReturnStmt) -> None:
        expr = stmt.expr

        if isinstance(expr, NameExpr):
            for i, arg in enumerate(self.arguments):
                if expr.node is arg:
                    self.returned.append(i)
                    return

        self.returned.append(None)

    def visit_func_def(self, node: FuncDef) -> None:
        # Ignore returns inside nested functions.
        pass


def find_direct_returned_argument(func: FuncDef) -> int | None:
    """Return the index of an argument returned directly."""

    finder = ReturnedArgumentFinder(func)
    func.body.accept(finder)

    if not finder.returned:
        return None

    first = finder.returned[0]

    if first is None:
        return None

    if any(index != first for index in finder.returned):
        return None

    if is_argument_reassigned(func, first):
        return None

    return first


def make_direct_return_generic(
    base: CallableType, returned_arg: int, object_type: Instance
) -> CallableType | None:
    """Build a generic candidate linking an argument to the return type."""

    if base.variables:
        return None

    if not 0 <= returned_arg < len(base.arg_types):
        return None

    if not isinstance(get_proper_type(base.arg_types[returned_arg]), AnyType):
        return None

    if not isinstance(get_proper_type(base.ret_type), AnyType):
        return None

    type_var = TypeVarType(
        "T",
        "T",
        TypeVarId(-1, namespace="dmypy_suggest"),
        [],
        object_type,
        AnyType(TypeOfAny.from_omitted_generics),
    )

    new_arg_types = base.arg_types.copy()
    new_arg_types[returned_arg] = type_var

    return base.copy_modified(arg_types=new_arg_types, ret_type=type_var, variables=[type_var])


class IndexedReturnFinder(ReturnedArgumentFinder):
    """Find arguments whose elements are returned directly."""

    def visit_return_stmt(self, stmt: ReturnStmt) -> None:
        expr = stmt.expr

        if (
            isinstance(expr, IndexExpr)
            and isinstance(expr.base, NameExpr)
            and isinstance(expr.index, IntExpr)
        ):
            for i, arg in enumerate(self.arguments):
                if expr.base.node is arg:
                    self.returned.append(i)
                    return

        self.returned.append(None)


def find_indexed_returned_argument(func: FuncDef) -> int | None:
    """Find an argument returned through integer indexing."""

    finder = IndexedReturnFinder(func)
    func.body.accept(finder)

    if not finder.returned:
        return None

    first = finder.returned[0]

    if first is None:
        return None

    if any(index != first for index in finder.returned):
        return None

    if is_argument_reassigned(func, first):
        return None

    return first


def make_collection_element_generic(
    base: CallableType, indexed_arg: int, collection_type: Instance, object_type: Instance
) -> CallableType | None:
    """Build a generic candidate for list[T] or tuple[T, ...]."""

    if base.variables:
        return None

    if not 0 <= indexed_arg < len(base.arg_types):
        return None

    if collection_type.type.fullname not in ("builtins.list", "builtins.tuple"):
        return None

    if not isinstance(get_proper_type(base.arg_types[indexed_arg]), AnyType):
        return None

    if not isinstance(get_proper_type(base.ret_type), AnyType):
        return None

    type_var = TypeVarType(
        "T",
        "T",
        TypeVarId(-1, namespace="dmypy_suggest"),
        [],
        object_type,
        AnyType(TypeOfAny.from_omitted_generics),
    )

    new_arg_types = base.arg_types.copy()
    new_arg_types[indexed_arg] = collection_type.copy_modified(args=[type_var])

    return base.copy_modified(arg_types=new_arg_types, ret_type=type_var, variables=[type_var])


def make_list_element_generic(
    base: CallableType, indexed_arg: int, list_type: Instance, object_type: Instance
) -> CallableType | None:
    if list_type.type.fullname != "builtins.list":
        return None

    return make_collection_element_generic(base, indexed_arg, list_type, object_type)


def make_tuple_element_generic(
    base: CallableType, indexed_arg: int, tuple_type: Instance, object_type: Instance
) -> CallableType | None:
    if tuple_type.type.fullname != "builtins.tuple":
        return None

    return make_collection_element_generic(base, indexed_arg, tuple_type, object_type)


class DictionaryLookupFinder(TraverserVisitor):
    """Find returns of the form mapping[key]."""

    def __init__(self, func: FuncDef) -> None:
        self.arguments = [arg.variable for arg in func.arguments]
        self.lookups: list[tuple[int, int] | None] = []

    def visit_return_stmt(self, stmt: ReturnStmt) -> None:
        expr = stmt.expr

        if (
            not isinstance(expr, IndexExpr)
            or not isinstance(expr.base, NameExpr)
            or not isinstance(expr.index, NameExpr)
        ):
            self.lookups.append(None)
            return

        mapping_index = next(
            (i for i, arg in enumerate(self.arguments) if expr.base.node is arg), None
        )

        key_index = next(
            (i for i, arg in enumerate(self.arguments) if expr.index.node is arg), None
        )

        if mapping_index is None or key_index is None or mapping_index == key_index:
            self.lookups.append(None)
            return

        self.lookups.append((mapping_index, key_index))

    def visit_func_def(self, node: FuncDef) -> None:
        # Ignore nested functions.
        pass


def find_dictionary_lookup(func: FuncDef) -> tuple[int, int] | None:
    """Find arguments used in direct mapping[key] returns."""

    finder = DictionaryLookupFinder(func)
    func.body.accept(finder)

    if not finder.lookups:
        return None

    first = finder.lookups[0]

    if first is None:
        return None

    if any(lookup != first for lookup in finder.lookups):
        return None

    if is_argument_reassigned(func, first[0]) or is_argument_reassigned(func, first[1]):
        return None

    return first


def make_dictionary_generic(
    base: CallableType,
    mapping_index: int,
    key_index: int,
    dict_type: Instance,
    object_type: Instance,
) -> CallableType | None:
    """Build a candidate with dict[K, V], K -> V."""

    if base.variables:
        return None

    if mapping_index == key_index:
        return None

    if not (0 <= mapping_index < len(base.arg_types) and 0 <= key_index < len(base.arg_types)):
        return None

    if dict_type.type.fullname != "builtins.dict":
        return None

    if not all(
        isinstance(get_proper_type(tp), AnyType)
        for tp in (base.arg_types[mapping_index], base.arg_types[key_index], base.ret_type)
    ):
        return None

    default = AnyType(TypeOfAny.from_omitted_generics)

    key_var = TypeVarType(
        "K", "K", TypeVarId(-1, namespace="dmypy_suggest"), [], object_type, default
    )

    value_var = TypeVarType(
        "V", "V", TypeVarId(-2, namespace="dmypy_suggest"), [], object_type, default
    )

    new_arg_types = base.arg_types.copy()

    new_arg_types[mapping_index] = dict_type.copy_modified(args=[key_var, value_var])
    new_arg_types[key_index] = key_var

    return base.copy_modified(
        arg_types=new_arg_types, ret_type=value_var, variables=[key_var, value_var]
    )


class CallbackApplicationFinder(TraverserVisitor):
    """Find returns of the form callback(arg)."""

    def __init__(self, func: FuncDef) -> None:
        self.arguments = [arg.variable for arg in func.arguments]
        self.applications: list[tuple[int, int] | None] = []

    def visit_return_stmt(self, stmt: ReturnStmt) -> None:
        expr = stmt.expr

        if (
            not isinstance(expr, CallExpr)
            or not isinstance(expr.callee, NameExpr)
            or len(expr.args) != 1
            or expr.arg_kinds != [ARG_POS]
            or not isinstance(expr.args[0], NameExpr)
        ):
            self.applications.append(None)
            return

        callback_index = next(
            (i for i, arg in enumerate(self.arguments) if expr.callee.node is arg), None
        )

        arg_index = next(
            (i for i, arg in enumerate(self.arguments) if expr.args[0].node is arg), None
        )

        if callback_index is None or arg_index is None or callback_index == arg_index:
            self.applications.append(None)
            return

        self.applications.append((callback_index, arg_index))

    def visit_func_def(self, node: FuncDef) -> None:
        # Ignore nested functions.
        pass


def find_callback_application(func: FuncDef) -> tuple[int, int] | None:
    """Find arguments used in direct callback(arg) returns."""

    finder = CallbackApplicationFinder(func)
    func.body.accept(finder)

    if not finder.applications:
        return None

    first = finder.applications[0]

    if first is None:
        return None

    if any(app != first for app in finder.applications):
        return None

    if is_argument_reassigned(func, first[0]) or is_argument_reassigned(func, first[1]):
        return None

    return first


def make_callback_generic(
    base: CallableType,
    callback_index: int,
    arg_index: int,
    object_type: Instance,
    function_type: Instance | None = None,
) -> CallableType | None:
    """Build a candidate with Callable[[T], R], T -> R."""

    if base.variables:
        return None

    if callback_index == arg_index:
        return None

    if not (0 <= callback_index < len(base.arg_types) and 0 <= arg_index < len(base.arg_types)):
        return None

    if function_type is None:
        function_type = base.fallback

    if function_type.type.fullname != "builtins.function":
        return None

    if not all(
        isinstance(get_proper_type(tp), AnyType)
        for tp in (base.arg_types[callback_index], base.arg_types[arg_index], base.ret_type)
    ):
        return None

    default = AnyType(TypeOfAny.from_omitted_generics)

    arg_var = TypeVarType(
        "T", "T", TypeVarId(-1, namespace="dmypy_suggest"), [], object_type, default
    )

    ret_var = TypeVarType(
        "R", "R", TypeVarId(-2, namespace="dmypy_suggest"), [], object_type, default
    )

    callback_type = CallableType([arg_var], [ARG_POS], [None], ret_var, function_type)

    new_arg_types = base.arg_types.copy()
    new_arg_types[callback_index] = callback_type
    new_arg_types[arg_index] = arg_var

    return base.copy_modified(
        arg_types=new_arg_types, ret_type=ret_var, variables=[arg_var, ret_var]
    )


class ArgumentReassignmentFinder(TraverserVisitor):
    """Detect whether a function argument is reassigned."""

    def __init__(self, variable: Var) -> None:
        self.variable = variable
        self.reassigned = False

    def check_target(self, target: Expression) -> None:
        if isinstance(target, NameExpr):
            if target.node is self.variable:
                self.reassigned = True

        elif isinstance(target, (TupleExpr, ListExpr)):
            for item in target.items:
                self.check_target(item)

        elif isinstance(target, StarExpr):
            self.check_target(target.expr)

    def visit_assignment_stmt(self, stmt: AssignmentStmt) -> None:
        for target in stmt.lvalues:
            self.check_target(target)
        super().visit_assignment_stmt(stmt)

    def visit_operator_assignment_stmt(self, stmt: OperatorAssignmentStmt) -> None:
        self.check_target(stmt.lvalue)
        super().visit_operator_assignment_stmt(stmt)

    def visit_assignment_expr(self, expr: AssignmentExpr) -> None:
        self.check_target(expr.target)
        super().visit_assignment_expr(expr)

    def visit_for_stmt(self, stmt: ForStmt) -> None:
        self.check_target(stmt.index)
        super().visit_for_stmt(stmt)

    def visit_with_stmt(self, stmt: WithStmt) -> None:
        for target in stmt.target:
            if target is not None:
                self.check_target(target)
        super().visit_with_stmt(stmt)

    def visit_del_stmt(self, stmt: DelStmt) -> None:
        self.check_target(stmt.expr)
        super().visit_del_stmt(stmt)

    def visit_func_def(self, node: FuncDef) -> None:
        # Do not traverse nested functions.
        pass


def is_argument_reassigned(func: FuncDef, index: int) -> bool:
    """Check whether an argument is rebound in the function body."""

    if not 0 <= index < len(func.arguments):
        return True

    variable = func.arguments[index].variable
    finder = ArgumentReassignmentFinder(variable)

    func.body.accept(finder)
    return finder.reassigned


def infer_generic_candidates(
    func: FuncDef,
    base: CallableType,
    callsite_arg_types: Sequence[Sequence[Sequence[Type]]],
    named_type: Callable[[str], Instance],
    min_calls: int = 2,
) -> list[CallableType]:
    """Generate generic candidates from a function and its call sites.

    Currently supports ordinary functions with one actual argument
    per formal parameter at each call site.

    Candidates must be validated by SuggestionEngine.try_type().
    """

    if len(base.arg_types) != len(func.arguments):
        return []

    if min_calls < 2 or len(callsite_arg_types) < min_calls:
        return []

    observed: list[list[Type]] = [[] for _ in base.arg_types]

    for call in callsite_arg_types:
        if len(call) != len(observed):
            return []

        for i, actual_types in enumerate(call):
            if len(actual_types) != 1:
                return []

            typ = get_proper_type(remove_instance_last_known_values(actual_types[0]))

            if isinstance(typ, AnyType):
                return []

            observed[i].append(typ)

    def varies(types: Sequence[Type]) -> bool:
        return any(t != types[0] for t in types[1:])

    object_type = named_type("builtins.object")

    direct = find_direct_returned_argument(func)

    if direct is not None and varies(observed[direct]):
        candidate = make_direct_return_generic(base, direct, object_type)
        return [candidate] if candidate is not None else []

    indexed = find_indexed_returned_argument(func)

    if indexed is not None and varies(observed[indexed]):
        types = [get_proper_type(t) for t in observed[indexed]]

        if all(isinstance(t, Instance) and t.type.fullname == "builtins.list" for t in types):
            candidate = make_list_element_generic(
                base, indexed, named_type("builtins.list"), object_type
            )
            return [candidate] if candidate is not None else []

        def tuple_element_type(t: Type) -> Type | None:
            t = get_proper_type(t)

            if isinstance(t, TupleType):
                if bool(t.items) and all(item == t.items[0] for item in t.items):
                    return get_proper_type(t.items[0])
                return None

            if (
                isinstance(t, Instance)
                and t.type.fullname == "builtins.tuple"
                and len(t.args) == 1
            ):
                return get_proper_type(t.args[0])

            return None

        element_types = [tuple_element_type(t) for t in types]

        if all(elem is not None for elem in element_types) and varies(
            [elem for elem in element_types if elem is not None]
        ):
            candidate = make_tuple_element_generic(
                base, indexed, named_type("builtins.tuple"), object_type
            )
            return [candidate] if candidate is not None else []

    lookup = find_dictionary_lookup(func)

    if lookup is not None:
        mapping_index, key_index = lookup

        mappings = [get_proper_type(t) for t in observed[mapping_index]]

        if all(
            isinstance(t, Instance) and t.type.fullname == "builtins.dict" and len(t.args) == 2
            for t in mappings
        ):
            matching_keys = all(
                get_proper_type(mapping.args[0]) == get_proper_type(key_type)
                for mapping, key_type in zip(mappings, observed[key_index])
                if isinstance(mapping, Instance)
            )

            if matching_keys and varies(observed[mapping_index]):
                candidate = make_dictionary_generic(
                    base, mapping_index, key_index, named_type("builtins.dict"), object_type
                )
                return [candidate] if candidate is not None else []

    callback = find_callback_application(func)

    if callback is not None:
        callback_index, arg_index = callback

        callbacks = [get_proper_type(t) for t in observed[callback_index]]

        if all(
            isinstance(t, CallableType)
            and not t.is_ellipsis_args
            and len(t.arg_types) == 1
            and t.arg_kinds[0] in (ARG_POS, ARG_OPT)
            and not isinstance(get_proper_type(t.arg_types[0]), AnyType)
            and not isinstance(get_proper_type(t.ret_type), AnyType)
            for t in callbacks
        ):
            matching_args = all(
                get_proper_type(cb.arg_types[0]) == get_proper_type(arg_type)
                for cb, arg_type in zip(callbacks, observed[arg_index])
                if isinstance(cb, CallableType)
            )

            cb_arg_types = [
                get_proper_type(cb.arg_types[0])
                for cb in callbacks
                if isinstance(cb, CallableType)
            ]
            cb_ret_types = [
                get_proper_type(cb.ret_type) for cb in callbacks if isinstance(cb, CallableType)
            ]

            if matching_args and (varies(cb_arg_types) or varies(cb_ret_types)):
                candidate = make_callback_generic(
                    base, callback_index, arg_index, object_type, named_type("builtins.function")
                )
                return [candidate] if candidate is not None else []

    return []
