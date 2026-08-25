"""Semantic analysis of TypedDict definitions."""

from __future__ import annotations

from collections.abc import Collection
from typing import Final, NamedTuple

from mypy import errorcodes as codes, message_registry
from mypy.errorcodes import ErrorCode
from mypy.expandtype import expand_type
from mypy.exprtotype import TypeTranslationError, expr_to_unanalyzed_type
from mypy.messages import MessageBuilder
from mypy.nodes import (
    ARG_NAMED,
    ARG_POS,
    AssignmentStmt,
    CallExpr,
    ClassDef,
    Context,
    DictExpr,
    EllipsisExpr,
    Expression,
    ExpressionStmt,
    IndexExpr,
    NameExpr,
    PassStmt,
    RefExpr,
    Statement,
    StrExpr,
    TempNode,
    TupleExpr,
    TypeAlias,
    TypedDictData,
    TypedDictExpr,
    TypedDictFieldSource,
    TypeInfo,
    inline_base,
)
from mypy.options import Options
from mypy.semanal_shared import (
    SemanticAnalyzerInterface,
    has_placeholder,
    require_bool_literal_argument,
)
from mypy.state import state
from mypy.typeanal import check_for_explicit_any, has_any_from_unimported_type
from mypy.types import (
    TPDICT_NAMES,
    AnyType,
    ReadOnlyType,
    RequiredType,
    Type,
    TypedDictType,
    TypeOfAny,
    TypeVarLikeType,
    get_proper_type,
)

TPDICT_CLASS_ERROR: Final = (
    'Invalid statement in TypedDict definition; expected "field_name: field_type"'
)


class FieldSource(NamedTuple):
    field_type: Type
    is_readonly: bool
    is_required: bool
    base: TypeInfo | None
    ctx: Context


class TypedDictAnalyzer:
    def __init__(
        self, options: Options, api: SemanticAnalyzerInterface, msg: MessageBuilder
    ) -> None:
        self.options = options
        self.api = api
        self.msg = msg

    def analyze_typeddict_classdef(self, defn: ClassDef) -> tuple[bool, TypeInfo | None]:
        """Analyze a class that may define a TypedDict.

        Assume that base classes have been analyzed already.

        Note: Unlike normal classes, we won't create a TypeInfo until
        the whole definition of the TypeDict (including the body and all
        key names and types) is complete.  This is mostly because we
        store the corresponding TypedDictType in the TypeInfo.

        Return (is this a TypedDict, new TypeInfo). Specifics:
         * If we couldn't finish due to incomplete reference anywhere in
           the definition, return (True, None).
         * If this is not a TypedDict, return (False, None).
        """
        possible = False
        for base_expr in defn.base_type_exprs:
            if isinstance(base_expr, CallExpr):
                base_expr = base_expr.callee
            if isinstance(base_expr, IndexExpr):
                base_expr = base_expr.base
            if isinstance(base_expr, RefExpr):
                self.api.accept(base_expr)
                if base_expr.fullname in TPDICT_NAMES or self.is_typeddict(base_expr):
                    possible = True
                    if isinstance(base_expr.node, TypeInfo) and base_expr.node.is_final:
                        err = message_registry.CANNOT_INHERIT_FROM_FINAL
                        self.fail(err.format(base_expr.node.name).value, defn, code=err.code)
        if not possible:
            return False, None
        existing_info = None
        if isinstance(defn.analyzed, TypedDictExpr):
            existing_info = defn.analyzed.info

        is_closed: bool | None = None
        if "closed" in defn.keywords:
            is_closed = require_bool_literal_argument(
                self.api, defn.keywords["closed"], "closed", False
            )

        if (
            len(defn.base_type_exprs) == 1
            and isinstance(defn.base_type_exprs[0], RefExpr)
            and defn.base_type_exprs[0].fullname in TPDICT_NAMES
        ):
            # Building a new TypedDict
            field_sources, statements = self.analyze_typeddict_classdef_fields(defn)
            if field_sources is None:
                return True, None  # Defer
            field_types = {key: source.field_type for (key, source) in field_sources.items()}
            required_keys = {key for (key, source) in field_sources.items() if source.is_required}
            readonly_keys = {key for (key, source) in field_sources.items() if source.is_readonly}
            info = self.build_typeddict_typeinfo(
                defn.name,
                field_types,
                required_keys,
                readonly_keys,
                is_closed or False,
                defn.line,
                existing_info,
            )
            defn.analyzed = TypedDictExpr(info)
            defn.analyzed.line = defn.line
            defn.analyzed.column = defn.column
            defn.defs.body = statements
            return True, info

        # Extending/merging existing TypedDicts
        typeddict_bases: list[Expression] = []
        typeddict_bases_set = set()
        for i, expr in enumerate(defn.base_type_exprs):
            ok, maybe_type_info, _ = self.check_typeddict(expr, inline_base(defn.name, i))
            if ok and maybe_type_info is not None:
                # expr is a CallExpr
                info = maybe_type_info
                typeddict_bases_set.add(info.fullname)
                typeddict_bases.append(expr)
            elif isinstance(expr, RefExpr) and expr.fullname in TPDICT_NAMES:
                if "TypedDict" not in typeddict_bases_set:
                    typeddict_bases_set.add("TypedDict")
                else:
                    self.fail('Duplicate base class "TypedDict"', defn)
            elif (
                isinstance(expr, RefExpr)
                and self.is_typeddict(expr)
                or isinstance(expr, IndexExpr)
                and self.is_typeddict(expr.base)
            ):
                info = self._parse_typeddict_base(expr, defn)
                if info.fullname not in typeddict_bases_set:
                    typeddict_bases_set.add(info.fullname)
                    typeddict_bases.append(expr)
                else:
                    self.fail(f'Duplicate base class "{info.name}"', defn)
            else:
                self.fail("All bases of a new TypedDict must be TypedDict types", defn)

        bases_info: list[tuple[TypeInfo, dict[str, Type]]] = []
        for base in typeddict_bases:
            base_info = self.fetch_keys_and_types_from_base(base, defn)
            if base_info is not None:
                bases_info.append(base_info)
        new_field_sources, new_statements = self.analyze_typeddict_classdef_fields(defn)
        if new_field_sources is None:
            return True, None  # Defer
        field_types, required_keys, readonly_keys, is_closed, field_sources = (
            self.resolve_field_inheritance(bases_info, new_field_sources, is_closed, defn)
        )
        typeddict_data = TypedDictData(True, bases_info, field_sources)
        info = self.build_typeddict_typeinfo(
            defn.name,
            field_types,
            required_keys,
            readonly_keys,
            is_closed,
            defn.line,
            existing_info,
            typeddict_data=typeddict_data,
        )
        defn.analyzed = TypedDictExpr(info)
        defn.analyzed.line = defn.line
        defn.analyzed.column = defn.column
        defn.defs.body = new_statements
        return True, info

    def fetch_keys_and_types_from_base(
        self, base: Expression, ctx: Context
    ) -> tuple[TypeInfo, dict[str, Type]] | None:
        info = self._parse_typeddict_base(base, ctx)
        base_args: list[Type] = []
        if isinstance(base, IndexExpr):
            args = self.analyze_base_args(base, ctx)
            if args is None:
                return None
            base_args = args

        assert info.typeddict_type is not None
        base_typed_dict = info.typeddict_type
        base_items = base_typed_dict.items
        valid_items = base_items.copy()

        # Always fix invalid bases to avoid crashes.
        tvars = info.defn.type_vars
        if len(base_args) != len(tvars):
            any_kind = TypeOfAny.from_omitted_generics
            if base_args:
                self.fail(f'Invalid number of type arguments for "{info.name}"', ctx)
                any_kind = TypeOfAny.from_error
            base_args = [AnyType(any_kind) for _ in tvars]

        with state.strict_optional_set(self.options.strict_optional):
            valid_items = self.map_items_to_base(valid_items, tvars, base_args)

        return info, valid_items

    def field_sources_in_reverse_order(
        self,
        bases: list[tuple[TypeInfo, dict[str, Type]]],
        child_field_sources: dict[str, FieldSource],
        ctx: Context,
    ) -> dict[str, list[FieldSource]]:
        """Find all keys in bases and child, mapping them to a list of sources.

        Iterate bases in reverse order to preserve key ordering for display.
        """
        result: dict[str, list[FieldSource]] = {}
        for base_info, base_fields in reversed(bases):
            assert base_info.typeddict_type is not None
            for field_name, field_type in base_fields.items():
                source = FieldSource(
                    field_type=field_type,
                    is_readonly=field_name in base_info.typeddict_type.readonly_keys,
                    is_required=field_name in base_info.typeddict_type.required_keys,
                    base=base_info,
                    ctx=ctx,
                )
                result.setdefault(field_name, []).append(source)
        for field_name, source in child_field_sources.items():
            result.setdefault(field_name, []).append(source)
        return result

    def primary_source(self, sources: list[FieldSource]) -> FieldSource:
        """Select a primary source from a reverse-ordered list of sources.

        The primary source will be the last in the list, skipping readonly
        base class sources unless they are the only available option.
        """
        if not sources[-1].base:
            return sources[-1]
        mutable_sources = (s for s in reversed(sources) if not s.is_readonly)
        return next(mutable_sources, sources[-1])

    def verify_requiredness_compatibility(
        self,
        field_name: str,
        source: FieldSource,
        is_required: bool,
        primary_source_base: TypeInfo | None,
        ctx: Context,
    ) -> None:
        """Verify requiredness compatibility of the final child type field with a base class source."""
        assert source.base
        if source.is_required and not is_required:
            if primary_source_base is None:
                self.fail(
                    f'Field "{field_name}" is required in base class "{source.base.name}"', ctx
                )
            else:
                self.fail(
                    f'Field "{field_name}" is required in base class "{source.base.name}" but can '
                    f'be deleted in base class "{primary_source_base.name}"',
                    ctx,
                )
        elif not source.is_required and not source.is_readonly and is_required:
            if primary_source_base is None:
                self.fail(
                    f'Field "{field_name}" can be deleted in base class "{source.base.name}"', ctx
                )
            else:
                self.fail(
                    f'Field "{field_name}" is required in base class "{primary_source_base.name}" '
                    f'but can be deleted in base class "{source.base.name}"',
                    ctx,
                )

    def verify_field_against_closed_bases(
        self,
        field_name: str,
        closed_bases: Collection[tuple[TypeInfo, Collection[str]]],
        primary_source_base: TypeInfo | None,
        ctx: Context,
    ) -> None:
        for closed_base_type, closed_base_fields in closed_bases:
            if field_name in closed_base_fields:
                continue

            if primary_source_base:
                self.fail(
                    f'Cannot extend closed base class "{closed_base_type.name}" with field '
                    f'"{field_name}" from base class "{primary_source_base.name}"',
                    ctx,
                )
            else:
                self.fail(
                    f'Cannot extend closed base class "{closed_base_type.name}" with new field '
                    f'"{field_name}"',
                    ctx,
                )

    def resolve_field_inheritance(
        self,
        bases: list[tuple[TypeInfo, dict[str, Type]]],
        child_field_sources: dict[str, FieldSource],
        child_is_closed: bool | None,
        ctx: Context,
    ) -> tuple[dict[str, Type], set[str], set[str], bool, dict[str, TypedDictFieldSource]]:
        """Determine field types, requiredness, readonlyness, and closedness."""
        field_sources = self.field_sources_in_reverse_order(bases, child_field_sources, ctx)
        field_types: dict[str, Type] = {}
        chosen_sources: dict[str, TypedDictFieldSource] = {}
        required_keys: set[str] = set()
        readonly_keys: set[str] = set()
        closed_bases = [
            (base_info, base_fields.keys())
            for (base_info, base_fields) in bases
            if base_info.typeddict_type and base_info.typeddict_type.is_closed
        ]

        if child_is_closed is False and closed_bases:
            for base_info, _ in closed_bases:
                self.fail(
                    f"Open TypedDict class cannot subclass closed TypedDict class "
                    f'"{base_info.name}"',
                    ctx,
                )

        for field_name, sources in field_sources.items():
            primary_source = self.primary_source(sources)
            # If a read-only field is only defined in base classes, joining the types
            # is unlikely to produce a tight enough result. We could check all the
            # candidates from the base classes, but it would be O(n^2) complexity
            # to find out which is a supertype of all the others. Instead, use the
            # first definition we encounter, and let the user provide the correct
            # definition in the subclass if this fails.
            field_types[field_name] = primary_source.field_type
            chosen_sources[field_name] = TypedDictFieldSource(
                base=primary_source.base, ctx=primary_source.ctx
            )

            if primary_source.is_readonly:
                # If the primary source is readonly, all sources are readonly
                is_readonly = True
                is_required = any(source.is_required for source in sources)
            else:
                is_readonly = False
                is_required = primary_source.is_required

            if is_required:
                required_keys.add(field_name)
            if is_readonly:
                readonly_keys.add(field_name)

            for source in sources:
                if source is not primary_source:
                    self.verify_requiredness_compatibility(
                        field_name, source, is_required, primary_source.base, primary_source.ctx
                    )
            self.verify_field_against_closed_bases(
                field_name, closed_bases, primary_source.base, primary_source.ctx
            )

        is_closed = bool(closed_bases) if child_is_closed is None else child_is_closed
        return field_types, required_keys, readonly_keys, is_closed, chosen_sources

    def _parse_typeddict_base(self, base: Expression, ctx: Context) -> TypeInfo:
        if isinstance(base, RefExpr):
            if isinstance(base.node, TypeInfo):
                return base.node
            elif isinstance(base.node, TypeAlias):
                # Only old TypeAlias / plain assignment, PEP695 `type` stmt
                # cannot be used as a base class
                target = get_proper_type(base.node.target)
                assert isinstance(target, TypedDictType)
                return target.fallback.type
            else:
                assert False
        elif isinstance(base, IndexExpr):
            assert isinstance(base.base, RefExpr)
            return self._parse_typeddict_base(base.base, ctx)
        else:
            assert isinstance(base, CallExpr)
            assert isinstance(base.analyzed, TypedDictExpr)
            return base.analyzed.info

    def analyze_base_args(self, base: IndexExpr, ctx: Context) -> list[Type] | None:
        """Analyze arguments of base type expressions as types.

        We need to do this, because normal base class processing happens after
        the TypedDict special-casing (plus we get a custom error message).
        """
        base_args = []
        if isinstance(base.index, TupleExpr):
            args = base.index.items
        else:
            args = [base.index]

        for arg_expr in args:
            try:
                type = expr_to_unanalyzed_type(arg_expr, self.options, self.api.is_stub_file)
            except TypeTranslationError:
                self.fail("Invalid TypedDict type argument", ctx)
                return None
            analyzed = self.api.anal_type(
                type,
                allow_typed_dict_special_forms=True,
                allow_placeholder=not self.api.is_func_scope(),
            )
            if analyzed is None:
                return None
            base_args.append(analyzed)
        return base_args

    def map_items_to_base(
        self, valid_items: dict[str, Type], tvars: list[TypeVarLikeType], base_args: list[Type]
    ) -> dict[str, Type]:
        """Map item types to how they would look in their base with type arguments applied.

        Note it is safe to use expand_type() during semantic analysis, because it should never
        (indirectly) call is_subtype().
        """
        mapped_items = {}
        for key in valid_items:
            type_in_base = valid_items[key]
            if not tvars:
                mapped_items[key] = type_in_base
                continue
            # TODO: simple zip can't be used for variadic types.
            mapped_items[key] = expand_type(
                type_in_base, {t.id: a for (t, a) in zip(tvars, base_args)}
            )
        return mapped_items

    def analyze_typeddict_classdef_fields(
        self, defn: ClassDef
    ) -> tuple[dict[str, FieldSource] | None, list[Statement]]:
        """Analyze fields defined in a TypedDict class definition.

        This doesn't consider inherited fields (if any). Also consider totality,
        if given.

        Return tuple with these items:
         * Dict of key -> field source (or None if found an incomplete reference -> deferral)
         * List of statements from defn.defs.body that are legally allowed to be a
           part of a TypedDict definition
        """
        fields: dict[str, FieldSource] = {}
        statements: list[Statement] = []

        total: bool | None = True
        for key in defn.keywords:
            if key == "total":
                total = require_bool_literal_argument(
                    self.api, defn.keywords["total"], "total", True
                )
                continue
            elif key == "closed":
                continue
            for_function = ' for "__init_subclass__" of "TypedDict"'
            self.msg.unexpected_keyword_argument_for_function(for_function, key, defn)

        for stmt in defn.defs.body:
            if not isinstance(stmt, AssignmentStmt):
                # Still allow pass or ... (for empty TypedDict's) and docstrings
                if isinstance(stmt, PassStmt) or (
                    isinstance(stmt, ExpressionStmt)
                    and isinstance(stmt.expr, (EllipsisExpr, StrExpr))
                ):
                    statements.append(stmt)
                else:
                    defn.removed_statements.append(stmt)
                    self.fail(TPDICT_CLASS_ERROR, stmt)
            elif len(stmt.lvalues) > 1 or not isinstance(stmt.lvalues[0], NameExpr):
                # An assignment, but an invalid one.
                defn.removed_statements.append(stmt)
                self.fail(TPDICT_CLASS_ERROR, stmt)
            else:
                name = stmt.lvalues[0].name
                if name in fields:
                    self.fail(f'Duplicate TypedDict key "{name}"', stmt)
                    continue
                # Append stmt, name, and type in this case...
                statements.append(stmt)

                field_type: Type
                if stmt.unanalyzed_type is None:
                    field_type = AnyType(TypeOfAny.unannotated)
                else:
                    analyzed = self.api.anal_type(
                        stmt.unanalyzed_type,
                        allow_typed_dict_special_forms=True,
                        allow_placeholder=not self.api.is_func_scope(),
                        prohibit_self_type="TypedDict item type",
                        prohibit_special_class_field_types="TypedDict",
                    )
                    if analyzed is None:
                        return None, []  # Need to defer
                    field_type = analyzed
                    if not has_placeholder(analyzed):
                        stmt.type = self.extract_meta_info(analyzed, stmt)[0]

                field_type, required, readonly = self.extract_meta_info(field_type)
                fields[name] = FieldSource(
                    field_type=field_type,
                    is_required=(total or required is True) and required is not False,
                    is_readonly=readonly,
                    base=None,
                    ctx=stmt,
                )

                # ...despite possible minor failures that allow further analysis.
                if stmt.type is None or hasattr(stmt, "new_syntax") and not stmt.new_syntax:
                    self.fail(TPDICT_CLASS_ERROR, stmt)
                elif not isinstance(stmt.rvalue, TempNode):
                    # x: int assigns rvalue to TempNode(AnyType())
                    self.fail("Right hand side values are not supported in TypedDict", stmt)

        return fields, statements

    def extract_meta_info(
        self, typ: Type, context: Context | None = None
    ) -> tuple[Type, bool | None, bool]:
        """Unwrap all metadata types."""
        is_required = None  # default, no modification
        readonly = False  # by default all is mutable

        seen_required = False
        seen_readonly = False
        while isinstance(typ, (RequiredType, ReadOnlyType)):
            if isinstance(typ, RequiredType):
                if context is not None and seen_required:
                    self.fail(
                        '"{}" type cannot be nested'.format(
                            "Required[]" if typ.required else "NotRequired[]"
                        ),
                        context,
                        code=codes.VALID_TYPE,
                    )
                is_required = typ.required
                seen_required = True
                typ = typ.item
            if isinstance(typ, ReadOnlyType):
                if context is not None and seen_readonly:
                    self.fail('"ReadOnly[]" type cannot be nested', context, code=codes.VALID_TYPE)
                readonly = True
                seen_readonly = True
                typ = typ.item
        return typ, is_required, readonly

    def check_typeddict(
        self, node: Expression, name: str
    ) -> tuple[bool, TypeInfo | None, list[TypeVarLikeType]]:
        """Check if a call defines a TypedDict.

        The name argument is the name of the variable to which this is assigned.
        For an inlined base class this is a unique name generated from class name
        base number.

        Return a pair (is it a typed dict, corresponding TypeInfo).

        If the definition is invalid but looks like a TypedDict,
        report errors but return (some) TypeInfo. If some type is not ready,
        return (True, None).
        """
        if not isinstance(node, CallExpr):
            return False, None, []
        call = node
        callee = call.callee
        if not isinstance(callee, RefExpr):
            return False, None, []
        fullname = callee.fullname
        if fullname not in TPDICT_NAMES:
            return False, None, []
        res = self.parse_typeddict_args(call)
        if res is None:
            # This is a valid typed dict, but some type is not ready.
            # The caller should defer this until next iteration.
            return True, None, []
        typename, items, wrapped_types, total, closed, tvar_defs, ok = res
        if not ok:
            # Error. Construct dummy return value.
            info = self.build_typeddict_typeinfo(name, {}, set(), set(), False, call.line, None)
        else:
            if "@" not in name and name != typename:
                self.fail(
                    'First argument "{}" to TypedDict() does not match variable name "{}"'.format(
                        typename, name
                    ),
                    node,
                    code=codes.NAME_MATCH,
                )
            # Unwrap special forms (Required/NotRequired/ReadOnly)
            types: list[Type] = []
            required_keys: set[str] = set()
            readonly_keys: set[str] = set()
            for field, t in zip(items, wrapped_types):
                unwrapped_type, is_required, is_readonly = self.extract_meta_info(t, node)
                types.append(unwrapped_type)
                if is_required is True or (is_required is None and total):
                    required_keys.add(field)
                if is_readonly:
                    readonly_keys.add(field)

            # Perform various validations after unwrapping.
            for t in types:
                check_for_explicit_any(
                    t, self.options, self.api.is_typeshed_stub_file, self.msg, context=call
                )
            if self.options.disallow_any_unimported:
                for t in types:
                    if has_any_from_unimported_type(t):
                        self.msg.unimported_type_becomes_any("Type of a TypedDict key", t, call)

            existing_info = None
            if isinstance(node.analyzed, TypedDictExpr):
                existing_info = node.analyzed.info

            info = self.build_typeddict_typeinfo(
                name,
                dict(zip(items, types)),
                required_keys,
                readonly_keys,
                closed,
                call.line,
                existing_info,
            )
            info.line = node.line
        # Store generated TypeInfo under both names, see semanal_namedtuple for more details.
        self.api.add_symbol(name, info, node)
        if self.api.is_nested_within_func_scope():
            self.api.add_global_symbol(name, node, info)
        call.analyzed = TypedDictExpr(info)
        call.analyzed.set_line(call)
        return True, info, tvar_defs

    def parse_typeddict_args(
        self, call: CallExpr
    ) -> tuple[str, list[str], list[Type], bool, bool, list[TypeVarLikeType], bool] | None:
        """Parse typed dict call expression.

        Return names, types, totality, open/closed, was there an error during parsing.
        If some type is not ready, return None.
        """
        # TODO: Share code with check_argument_count in checkexpr.py?
        args = call.args
        if len(args) < 2:
            return self.fail_typeddict_arg("Too few arguments for TypedDict()", call)
        if len(args) > 4:
            return self.fail_typeddict_arg("Too many arguments for TypedDict()", call)
        if call.arg_kinds[:2] != [ARG_POS, ARG_POS] or any(
            arg_kind != ARG_NAMED for arg_kind in call.arg_kinds[2:]
        ):
            return self.fail_typeddict_arg("Unexpected arguments to TypedDict()", call)
        seen_arg_names = set()
        for arg_name in call.arg_names[2:]:
            if arg_name not in ("total", "closed"):
                return self.fail_typeddict_arg(
                    f'Unexpected keyword argument "{arg_name}" for "TypedDict"', call
                )
            if arg_name in seen_arg_names:
                return self.fail_typeddict_arg(
                    f'Repeated keyword argument "{arg_name}" for "TypedDict"', call
                )
            seen_arg_names.add(arg_name)
        if not isinstance(args[0], StrExpr):
            return self.fail_typeddict_arg(
                "TypedDict() expects a string literal as the first argument", call
            )
        if not isinstance(args[1], DictExpr):
            return self.fail_typeddict_arg(
                "TypedDict() expects a dictionary literal as the second argument", call
            )
        total: bool | None = True
        closed: bool = False
        for arg_name, arg in zip(call.arg_names[2:], call.args[2:]):
            assert arg_name
            value = require_bool_literal_argument(self.api, arg, arg_name)
            if value is None:
                return "", [], [], True, False, [], False
            if arg_name == "closed":
                closed = value
            else:
                total = value
        dictexpr = args[1]
        tvar_defs = self.api.get_and_bind_all_tvars([t for k, t in dictexpr.items])
        res = self.parse_typeddict_fields_with_types(dictexpr.items)
        if res is None:
            # One of the types is not ready, defer.
            return None
        items, types, ok = res
        assert total is not None
        return args[0].value, items, types, total, closed, tvar_defs, ok

    def parse_typeddict_fields_with_types(
        self, dict_items: list[tuple[Expression | None, Expression]]
    ) -> tuple[list[str], list[Type], bool] | None:
        """Parse typed dict items passed as pairs (name expression, type expression).

        Return names, types, was there an error. If some type is not ready, return None.
        """
        seen_keys = set()
        items: list[str] = []
        types: list[Type] = []
        for field_name_expr, field_type_expr in dict_items:
            if isinstance(field_name_expr, StrExpr):
                key = field_name_expr.value
                items.append(key)
                if key in seen_keys:
                    self.fail(f'Duplicate TypedDict key "{key}"', field_name_expr)
                seen_keys.add(key)
            else:
                name_context = field_name_expr or field_type_expr
                self.fail_typeddict_arg("Invalid TypedDict() field name", name_context)
                return [], [], False
            try:
                type = expr_to_unanalyzed_type(
                    field_type_expr, self.options, self.api.is_stub_file
                )
            except TypeTranslationError:
                self.fail_typeddict_arg("Use dict literal for nested TypedDict", field_type_expr)
                return [], [], False
            analyzed = self.api.anal_type(
                type,
                allow_typed_dict_special_forms=True,
                allow_placeholder=not self.api.is_func_scope(),
                prohibit_self_type="TypedDict item type",
                prohibit_special_class_field_types="TypedDict",
            )
            if analyzed is None:
                return None
            types.append(analyzed)
        return items, types, True

    def fail_typeddict_arg(
        self, message: str, context: Context
    ) -> tuple[str, list[str], list[Type], bool, bool, list[TypeVarLikeType], bool]:
        self.fail(message, context)
        return "", [], [], True, False, [], False

    def build_typeddict_typeinfo(
        self,
        name: str,
        item_types: dict[str, Type],
        required_keys: set[str],
        readonly_keys: set[str],
        is_closed: bool,
        line: int,
        existing_info: TypeInfo | None,
        typeddict_data: TypedDictData | None = None,
    ) -> TypeInfo:
        # Prefer typing then typing_extensions if available.
        fallback = (
            self.api.named_type_or_none("typing._TypedDict", [])
            or self.api.named_type_or_none("typing_extensions._TypedDict", [])
            or self.api.named_type_or_none("mypy_extensions._TypedDict", [])
        )
        assert fallback is not None
        info = existing_info or self.api.basic_new_typeinfo(name, fallback, line)
        typeddict_type = TypedDictType(
            item_types, required_keys, readonly_keys, fallback, is_closed=is_closed
        )
        any_placeholder = has_placeholder(typeddict_type)
        if typeddict_data:
            for _, base_fields in typeddict_data.bases:
                for field_type in base_fields.values():
                    if has_placeholder(field_type):
                        any_placeholder = True
        else:
            typeddict_data = TypedDictData(True, [], {})
        if any_placeholder:
            typeddict_data.ready = False
            force_progress = (
                typeddict_type != info.typeddict_type
                or info.typeddict_data is None
                or typeddict_data.bases != info.typeddict_data.bases
            )
            self.api.process_placeholder(
                None, "TypedDict item", info, force_progress=force_progress
            )
        info.update_typeddict_type(typeddict_type)
        info.typeddict_data = typeddict_data
        return info

    # Helpers

    def is_typeddict(self, expr: Expression) -> bool:
        return isinstance(expr, RefExpr) and (
            isinstance(expr.node, TypeInfo)
            and expr.node.typeddict_type is not None
            or isinstance(expr.node, TypeAlias)
            and isinstance(get_proper_type(expr.node.target), TypedDictType)
        )

    def fail(self, msg: str, ctx: Context, *, code: ErrorCode | None = None) -> None:
        self.api.fail(msg, ctx, code=code)

    def note(self, msg: str, ctx: Context) -> None:
        self.api.note(msg, ctx)
