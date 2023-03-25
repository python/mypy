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
from mypy.nodes import Block, ClassDef, Context, FakeInfo, FuncItem, MypyFile
from mypy.options import Options
from mypy.scope import Scope
from mypy.subtypes import is_same_type, is_subtype
from mypy.types import (
    AnyType,
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
    get_proper_type,
    get_proper_types,
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
        # correct aliases.
        if t.alias and len(t.args) != len(t.alias.alias_tvars):
            t.args = [AnyType(TypeOfAny.from_error) for _ in t.alias.alias_tvars]
        assert t.alias is not None, f"Unfixed type alias {t.type_ref}"
        is_error = self.validate_args(t.alias.name, t.args, t.alias.alias_tvars, t)
        if not is_error:
            # If there was already an error for the alias itself, there is no point in checking
            # the expansion, most likely it will result in the same kind of error.
            get_proper_type(t).accept(self)

    def visit_instance(self, t: Instance) -> None:
        # Type argument counts were checked in the main semantic analyzer pass. We assume
        # that the counts are correct here.
        info = t.type
        if isinstance(info, FakeInfo):
            return  # https://github.com/python/mypy/issues/11079
        self.validate_args(info.name, t.args, info.defn.type_vars, t)
        super().visit_instance(t)

    def validate_args(
        self, name: str, args: Sequence[Type], type_vars: list[TypeVarLikeType], ctx: Context
    ) -> bool:
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
                            format_type(arg), name, format_type(tvar.upper_bound)
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
                        f" another ParamSpec, got {format_type(arg)}",
                        ctx,
                    )
        return is_error

    def visit_unpack_type(self, typ: UnpackType) -> None:
        proper_type = get_proper_type(typ.type)
        if isinstance(proper_type, TupleType):
            return
        if isinstance(proper_type, TypeVarTupleType):
            return
        if isinstance(proper_type, Instance) and proper_type.type.fullname == "builtins.tuple":
            return
        if isinstance(proper_type, AnyType) and proper_type.type_of_any == TypeOfAny.from_error:
            return

        # TODO: Infer something when it can't be unpacked to allow rest of
        # typechecking to work.
        self.fail(message_registry.INVALID_UNPACK.format(proper_type), typ)

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
