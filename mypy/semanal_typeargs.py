"""Verify properties of type arguments, like 'int' in C[int] being valid.

This must happen after semantic analysis since there can be placeholder
types until the end of semantic analysis, and these break various type
operations, including subtype checks.
"""

from __future__ import annotations

from mypy import errorcodes as codes, message_registry
from mypy.errorcodes import ErrorCode
from mypy.errors import Errors
from mypy.messages import format_type
from mypy.mixedtraverser import MixedTraverserVisitor
from mypy.nodes import Block, ClassDef, Context, FakeInfo, FuncItem, MypyFile, TypeInfo
from mypy.options import Options
from mypy.scope import Scope
from mypy.subtypes import is_same_type, is_subtype
from mypy.types import (
    AnyType,
    Instance,
    ParamSpecType,
    TupleType,
    Type,
    TypeAliasType,
    TypeOfAny,
    TypeVarTupleType,
    TypeVarType,
    UnboundType,
    UnpackType,
    get_proper_type,
    get_proper_types,
)


class TypeArgumentAnalyzer(MixedTraverserVisitor):
    def __init__(self, errors: Errors, options: Options, is_typeshed_file: bool) -> None:
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
        get_proper_type(t).accept(self)

    def visit_instance(self, t: Instance) -> None:
        # Type argument counts were checked in the main semantic analyzer pass. We assume
        # that the counts are correct here.
        info = t.type
        if isinstance(info, FakeInfo):
            return  # https://github.com/python/mypy/issues/11079
        for (i, arg), tvar in zip(enumerate(t.args), info.defn.type_vars):
            if isinstance(tvar, TypeVarType):
                if isinstance(arg, ParamSpecType):
                    # TODO: Better message
                    self.fail(f'Invalid location for ParamSpec "{arg.name}"', t)
                    continue
                if tvar.values:
                    if isinstance(arg, TypeVarType):
                        arg_values = arg.values
                        if not arg_values:
                            self.fail(
                                message_registry.INVALID_TYPEVAR_AS_TYPEARG.format(
                                    arg.name, info.name
                                ),
                                t,
                                code=codes.TYPE_VAR,
                            )
                            continue
                    else:
                        arg_values = [arg]
                    self.check_type_var_values(info, arg_values, tvar.name, tvar.values, i + 1, t)
                if not is_subtype(arg, tvar.upper_bound):
                    self.fail(
                        message_registry.INVALID_TYPEVAR_ARG_BOUND.format(
                            format_type(arg), info.name, format_type(tvar.upper_bound)
                        ),
                        t,
                        code=codes.TYPE_VAR,
                    )
        super().visit_instance(t)

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
        self,
        type: TypeInfo,
        actuals: list[Type],
        arg_name: str,
        valids: list[Type],
        arg_number: int,
        context: Context,
    ) -> None:
        for actual in get_proper_types(actuals):
            # TODO: bind type variables in class bases/alias targets
            # so we can safely check this, currently we miss some errors.
            if not isinstance(actual, (AnyType, UnboundType)) and not any(
                is_same_type(actual, value) for value in valids
            ):
                if len(actuals) > 1 or not isinstance(actual, Instance):
                    self.fail(
                        message_registry.INVALID_TYPEVAR_ARG_VALUE.format(type.name),
                        context,
                        code=codes.TYPE_VAR,
                    )
                else:
                    class_name = f'"{type.name}"'
                    actual_type_name = f'"{actual.type.name}"'
                    self.fail(
                        message_registry.INCOMPATIBLE_TYPEVAR_VALUE.format(
                            arg_name, class_name, actual_type_name
                        ),
                        context,
                        code=codes.TYPE_VAR,
                    )

    def fail(self, msg: str, context: Context, *, code: ErrorCode | None = None) -> None:
        self.errors.report(context.get_line(), context.get_column(), msg, code=code)
