"""Verify properties of type arguments, like 'int' in C[int] being valid.

This must happen after semantic analysis since there can be placeholder
types until the end of semantic analysis, and these break various type
operations, including subtype checks.
"""

from __future__ import annotations

from typing import Sequence

from mypy import errorcodes as codes, message_registry
from mypy.errorcodes import ErrorCode
from mypy.errors import Errors
from mypy.messages import format_type
from mypy.mixedtraverser import MixedTraverserVisitor
from mypy.nodes import ARG_STAR, Block, ClassDef, Context, FakeInfo, FuncItem, MypyFile
from mypy.options import Options
from mypy.scope import Scope
from mypy.subtypes import is_same_type, is_subtype
from mypy.typeanal import fix_type_var_tuple_argument, set_any_tvars
from mypy.types import (
    AnyType,
    CallableType,
    Instance,
    Parameters,
    ParamSpecType,
    TupleType,
    Type,
    TypeAliasType,
    TypeOfAny,
    TypeVarLikeType,
    TypeVarTupleType,
    TypeVarType,
    UnboundType,
    UnpackType,
    flatten_nested_tuples,
    get_proper_type,
    get_proper_types,
    split_with_prefix_and_suffix,
)


class TypeArgumentAnalyzer(MixedTraverserVisitor):
    def __init__(self, errors: Errors, options: Options, is_typeshed_file: bool) -> None:
        super().__init__()
        self.errors = errors
        self.options = options
        self.is_typeshed_file = is_typeshed_file
        self.scope = Scope()
        # Should we also analyze function definitions, or only module top-levels?
        self.recurse_into_functions = True
        # Keep track of the type aliases already visited. This is needed to avoid
        # infinite recursion on types like A = Union[int, List[A]].
        self.seen_aliases: set[TypeAliasType] = set()

    def visit_mypy_file(self, o: MypyFile) -> None:
        self.errors.set_file(o.path, o.fullname, scope=self.scope, options=self.options)
        with self.scope.module_scope(o.fullname):
            super().visit_mypy_file(o)

    def visit_func(self, defn: FuncItem) -> None:
        if not self.recurse_into_functions:
            return
        with self.scope.function_scope(defn):
            super().visit_func(defn)

    def visit_class_def(self, defn: ClassDef) -> None:
        with self.scope.class_scope(defn.info):
            super().visit_class_def(defn)

    def visit_block(self, o: Block) -> None:
        if not o.is_unreachable:
            super().visit_block(o)

    def visit_type_alias_type(self, t: TypeAliasType) -> None:
        super().visit_type_alias_type(t)
        if t in self.seen_aliases:
            # Avoid infinite recursion on recursive type aliases.
            # Note: it is fine to skip the aliases we have already seen in non-recursive
            # types, since errors there have already been reported.
            return
        self.seen_aliases.add(t)
        # Some recursive aliases may produce spurious args. In principle this is not very
        # important, as we would simply ignore them when expanding, but it is better to keep
        # correct aliases. Also, variadic aliases are better to check when fully analyzed,
        # so we do this here.
        assert t.alias is not None, f"Unfixed type alias {t.type_ref}"
        if t.alias.tvar_tuple_index is not None:
            correct = len(t.args) >= len(t.alias.alias_tvars) - 1
            if any(
                isinstance(a, UnpackType) and isinstance(get_proper_type(a.type), Instance)
                for a in t.args
            ):
                correct = True
        else:
            correct = len(t.args) == len(t.alias.alias_tvars)
        if not correct:
            if t.alias.tvar_tuple_index is not None:
                exp_len = f"at least {len(t.alias.alias_tvars) - 1}"
            else:
                exp_len = f"{len(t.alias.alias_tvars)}"
            self.fail(
                "Bad number of arguments for type alias,"
                f" expected: {exp_len}, given: {len(t.args)}",
                t,
                code=codes.TYPE_ARG,
            )
            t.args = set_any_tvars(
                t.alias, t.line, t.column, self.options, from_error=True, fail=self.fail
            ).args
        is_error = self.validate_args(t.alias.name, t.args, t.alias.alias_tvars, t)
        if not is_error:
            # If there was already an error for the alias itself, there is no point in checking
            # the expansion, most likely it will result in the same kind of error.
            get_proper_type(t).accept(self)

    def visit_tuple_type(self, t: TupleType) -> None:
        t.items = flatten_nested_tuples(t.items)
        # We could also normalize Tuple[*tuple[X, ...]] -> tuple[X, ...] like in
        # expand_type() but we can't do this here since it is not a translator visitor,
        # and we need to return an Instance instead of TupleType.
        super().visit_tuple_type(t)

    def visit_callable_type(self, t: CallableType) -> None:
        super().visit_callable_type(t)
        # Normalize trivial unpack in var args as *args: *tuple[X, ...] -> *args: X
        if t.is_var_arg:
            star_index = t.arg_kinds.index(ARG_STAR)
            star_type = t.arg_types[star_index]
            if isinstance(star_type, UnpackType):
                p_type = get_proper_type(star_type.type)
                if isinstance(p_type, Instance):
                    assert p_type.type.fullname == "builtins.tuple"
                    t.arg_types[star_index] = p_type.args[0]

    def visit_instance(self, t: Instance) -> None:
        # Type argument counts were checked in the main semantic analyzer pass. We assume
        # that the counts are correct here.
        info = t.type
        if isinstance(info, FakeInfo):
            return  # https://github.com/python/mypy/issues/11079
        t.args = tuple(flatten_nested_tuples(t.args))
        if t.type.has_type_var_tuple_type:
            # Regular Instances are already validated in typeanal.py.
            # TODO: do something with partial overlap (probably just reject).
            # also in other places where split_with_prefix_and_suffix() is used.
            correct = len(t.args) >= len(t.type.type_vars) - 1
            if any(
                isinstance(a, UnpackType) and isinstance(get_proper_type(a.type), Instance)
                for a in t.args
            ):
                correct = True
            if not correct:
                exp_len = f"at least {len(t.type.type_vars) - 1}"
                self.fail(
                    f"Bad number of arguments, expected: {exp_len}, given: {len(t.args)}",
                    t,
                    code=codes.TYPE_ARG,
                )
                any_type = AnyType(TypeOfAny.from_error)
                t.args = (any_type,) * len(t.type.type_vars)
                fix_type_var_tuple_argument(any_type, t)
        self.validate_args(info.name, t.args, info.defn.type_vars, t)
        super().visit_instance(t)

    def validate_args(
        self, name: str, args: Sequence[Type], type_vars: list[TypeVarLikeType], ctx: Context
    ) -> bool:
        if any(isinstance(v, TypeVarTupleType) for v in type_vars):
            prefix = next(i for (i, v) in enumerate(type_vars) if isinstance(v, TypeVarTupleType))
            tvt = type_vars[prefix]
            assert isinstance(tvt, TypeVarTupleType)
            start, middle, end = split_with_prefix_and_suffix(
                tuple(args), prefix, len(type_vars) - prefix - 1
            )
            args = list(start) + [TupleType(list(middle), tvt.tuple_fallback)] + list(end)

        is_error = False
        for (i, arg), tvar in zip(enumerate(args), type_vars):
            if isinstance(tvar, TypeVarType):
                if isinstance(arg, ParamSpecType):
                    # TODO: Better message
                    is_error = True
                    self.fail(f'Invalid location for ParamSpec "{arg.name}"', ctx)
                    self.note(
                        "You can use ParamSpec as the first argument to Callable, e.g., "
                        "'Callable[{}, int]'".format(arg.name),
                        ctx,
                    )
                    continue
                if tvar.values:
                    if isinstance(arg, TypeVarType):
                        if self.in_type_alias_expr:
                            # Type aliases are allowed to use unconstrained type variables
                            # error will be checked at substitution point.
                            continue
                        arg_values = arg.values
                        if not arg_values:
                            is_error = True
                            self.fail(
                                message_registry.INVALID_TYPEVAR_AS_TYPEARG.format(arg.name, name),
                                ctx,
                                code=codes.TYPE_VAR,
                            )
                            continue
                    else:
                        arg_values = [arg]
                    if self.check_type_var_values(name, arg_values, tvar.name, tvar.values, ctx):
                        is_error = True
                if not is_subtype(arg, tvar.upper_bound):
                    if self.in_type_alias_expr and isinstance(arg, TypeVarType):
                        # Type aliases are allowed to use unconstrained type variables
                        # error will be checked at substitution point.
                        continue
                    is_error = True
                    self.fail(
                        message_registry.INVALID_TYPEVAR_ARG_BOUND.format(
                            format_type(arg, self.options),
                            name,
                            format_type(tvar.upper_bound, self.options),
                        ),
                        ctx,
                        code=codes.TYPE_VAR,
                    )
            elif isinstance(tvar, ParamSpecType):
                if not isinstance(
                    get_proper_type(arg), (ParamSpecType, Parameters, AnyType, UnboundType)
                ):
                    self.fail(
                        "Can only replace ParamSpec with a parameter types list or"
                        f" another ParamSpec, got {format_type(arg, self.options)}",
                        ctx,
                    )
        return is_error

    def visit_unpack_type(self, typ: UnpackType) -> None:
        super().visit_unpack_type(typ)
        proper_type = get_proper_type(typ.type)
        if isinstance(proper_type, TupleType):
            return
        if isinstance(proper_type, TypeVarTupleType):
            return
        if isinstance(proper_type, Instance) and proper_type.type.fullname == "builtins.tuple":
            return
        if isinstance(proper_type, AnyType) and proper_type.type_of_any == TypeOfAny.from_error:
            return
        if not isinstance(proper_type, UnboundType):
            # Avoid extra errors if there were some errors already.
            self.fail(
                message_registry.INVALID_UNPACK.format(format_type(proper_type, self.options)), typ
            )
        typ.type = AnyType(TypeOfAny.from_error)

    def check_type_var_values(
        self, name: str, actuals: list[Type], arg_name: str, valids: list[Type], context: Context
    ) -> bool:
        is_error = False
        for actual in get_proper_types(actuals):
            # We skip UnboundType here, since they may appear in defn.bases,
            # the error will be caught when visiting info.bases, that have bound type
            # variables.
            if not isinstance(actual, (AnyType, UnboundType)) and not any(
                is_same_type(actual, value) for value in valids
            ):
                is_error = True
                if len(actuals) > 1 or not isinstance(actual, Instance):
                    self.fail(
                        message_registry.INVALID_TYPEVAR_ARG_VALUE.format(name),
                        context,
                        code=codes.TYPE_VAR,
                    )
                else:
                    class_name = f'"{name}"'
                    actual_type_name = f'"{actual.type.name}"'
                    self.fail(
                        message_registry.INCOMPATIBLE_TYPEVAR_VALUE.format(
                            arg_name, class_name, actual_type_name
                        ),
                        context,
                        code=codes.TYPE_VAR,
                    )
        return is_error

    def fail(self, msg: str, context: Context, *, code: ErrorCode | None = None) -> None:
        self.errors.report(context.line, context.column, msg, code=code)

    def note(self, msg: str, context: Context, *, code: ErrorCode | None = None) -> None:
        self.errors.report(context.line, context.column, msg, severity="note", code=code)
