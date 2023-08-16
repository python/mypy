"""Semantic analysis of TypedDict definitions."""

from __future__ import annotations

from typing import Final

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
    TypedDictExpr,
    TypeInfo,
)
from mypy.options import Options
from mypy.semanal_shared import (
    SemanticAnalyzerInterface,
    has_placeholder,
    require_bool_literal_argument,
)
from mypy.typeanal import check_for_explicit_any, has_any_from_unimported_type
from mypy.types import (
    TPDICT_NAMES,
    AnyType,
    RequiredType,
    Type,
    TypedDictType,
    TypeOfAny,
    TypeVarLikeType,
)

TPDICT_CLASS_ERROR: Final = (
    "Invalid statement in TypedDict definition; " 'expected "field_name: field_type"'
)


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
        if (
            len(defn.base_type_exprs) == 1
            and isinstance(defn.base_type_exprs[0], RefExpr)
            and defn.base_type_exprs[0].fullname in TPDICT_NAMES
        ):
            # Building a new TypedDict
            fields, types, statements, required_keys = self.analyze_typeddict_classdef_fields(defn)
            if fields is None:
                return True, None  # Defer
            info = self.build_typeddict_typeinfo(
                defn.name, fields, types, required_keys, defn.line, existing_info
            )
            defn.analyzed = TypedDictExpr(info)
            defn.analyzed.line = defn.line
            defn.analyzed.column = defn.column
            defn.defs.body = statements
            return True, info

        # Extending/merging existing TypedDicts
        typeddict_bases: list[Expression] = []
        typeddict_bases_set = set()
        for expr in defn.base_type_exprs:
            if isinstance(expr, RefExpr) and expr.fullname in TPDICT_NAMES:
                if "TypedDict" not in typeddict_bases_set:
                    typeddict_bases_set.add("TypedDict")
                else:
                    self.fail('Duplicate base class "TypedDict"', defn)
            elif isinstance(expr, RefExpr) and self.is_typeddict(expr):
                assert expr.fullname
                if expr.fullname not in typeddict_bases_set:
                    typeddict_bases_set.add(expr.fullname)
                    typeddict_bases.append(expr)
                else:
                    assert isinstance(expr.node, TypeInfo)
                    self.fail(f'Duplicate base class "{expr.node.name}"', defn)
            elif isinstance(expr, IndexExpr) and self.is_typeddict(expr.base):
                assert isinstance(expr.base, RefExpr)
                assert expr.base.fullname
                if expr.base.fullname not in typeddict_bases_set:
                    typeddict_bases_set.add(expr.base.fullname)
                    typeddict_bases.append(expr)
                else:
                    assert isinstance(expr.base.node, TypeInfo)
                    self.fail(f'Duplicate base class "{expr.base.node.name}"', defn)
            else:
                self.fail("All bases of a new TypedDict must be TypedDict types", defn)

        keys: list[str] = []
        types = []
        required_keys = set()
        # Iterate over bases in reverse order so that leftmost base class' keys take precedence
        for base in reversed(typeddict_bases):
            self.add_keys_and_types_from_base(base, keys, types, required_keys, defn)
        (
            new_keys,
            new_types,
            new_statements,
            new_required_keys,
        ) = self.analyze_typeddict_classdef_fields(defn, keys)
        if new_keys is None:
            return True, None  # Defer
        keys.extend(new_keys)
        types.extend(new_types)
        required_keys.update(new_required_keys)
        info = self.build_typeddict_typeinfo(
            defn.name, keys, types, required_keys, defn.line, existing_info
        )
        defn.analyzed = TypedDictExpr(info)
        defn.analyzed.line = defn.line
        defn.analyzed.column = defn.column
        defn.defs.body = new_statements
        return True, info

    def add_keys_and_types_from_base(
        self,
        base: Expression,
        keys: list[str],
        types: list[Type],
        required_keys: set[str],
        ctx: Context,
    ) -> None:
        if isinstance(base, RefExpr):
            assert isinstance(base.node, TypeInfo)
            info = base.node
            base_args: list[Type] = []
        else:
            assert isinstance(base, IndexExpr)
            assert isinstance(base.base, RefExpr)
            assert isinstance(base.base.node, TypeInfo)
            info = base.base.node
            args = self.analyze_base_args(base, ctx)
            if args is None:
                return
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

        valid_items = self.map_items_to_base(valid_items, tvars, base_args)
        for key in base_items:
            if key in keys:
                self.fail(f'Overwriting TypedDict field "{key}" while merging', ctx)
        keys.extend(valid_items.keys())
        types.extend(valid_items.values())
        required_keys.update(base_typed_dict.required_keys)

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
                allow_required=True,
                allow_placeholder=not self.options.disable_recursive_aliases
                and not self.api.is_func_scope(),
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
            mapped_items[key] = expand_type(
                type_in_base, {t.id: a for (t, a) in zip(tvars, base_args)}
            )
        return mapped_items

    def analyze_typeddict_classdef_fields(
        self, defn: ClassDef, oldfields: list[str] | None = None
    ) -> tuple[list[str] | None, list[Type], list[Statement], set[str]]:
        """Analyze fields defined in a TypedDict class definition.

        This doesn't consider inherited fields (if any). Also consider totality,
        if given.

        Return tuple with these items:
         * List of keys (or None if found an incomplete reference --> deferral)
         * List of types for each key
         * List of statements from defn.defs.body that are legally allowed to be a
           part of a TypedDict definition
         * Set of required keys
        """
        fields: list[str] = []
        types: list[Type] = []
        statements: list[Statement] = []
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
                if name in (oldfields or []):
                    self.fail(f'Overwriting TypedDict field "{name}" while extending', stmt)
                if name in fields:
                    self.fail(f'Duplicate TypedDict key "{name}"', stmt)
                    continue
                # Append stmt, name, and type in this case...
                fields.append(name)
                statements.append(stmt)
                if stmt.type is None:
                    types.append(AnyType(TypeOfAny.unannotated))
                else:
                    analyzed = self.api.anal_type(
                        stmt.type,
                        allow_required=True,
                        allow_placeholder=not self.options.disable_recursive_aliases
                        and not self.api.is_func_scope(),
                        prohibit_self_type="TypedDict item type",
                    )
                    if analyzed is None:
                        return None, [], [], set()  # Need to defer
                    types.append(analyzed)
                # ...despite possible minor failures that allow further analysis.
                if stmt.type is None or hasattr(stmt, "new_syntax") and not stmt.new_syntax:
                    self.fail(TPDICT_CLASS_ERROR, stmt)
                elif not isinstance(stmt.rvalue, TempNode):
                    # x: int assigns rvalue to TempNode(AnyType())
                    self.fail("Right hand side values are not supported in TypedDict", stmt)
        total: bool | None = True
        if "total" in defn.keywords:
            total = require_bool_literal_argument(self.api, defn.keywords["total"], "total", True)
        required_keys = {
            field
            for (field, t) in zip(fields, types)
            if (total or (isinstance(t, RequiredType) and t.required))
            and not (isinstance(t, RequiredType) and not t.required)
        }
        types = [  # unwrap Required[T] to just T
            t.item if isinstance(t, RequiredType) else t for t in types
        ]

        return fields, types, statements, required_keys

    def check_typeddict(
        self, node: Expression, var_name: str | None, is_func_scope: bool
    ) -> tuple[bool, TypeInfo | None, list[TypeVarLikeType]]:
        """Check if a call defines a TypedDict.

        The optional var_name argument is the name of the variable to
        which this is assigned, if any.

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
        name, items, types, total, tvar_defs, ok = res
        if not ok:
            # Error. Construct dummy return value.
            info = self.build_typeddict_typeinfo("TypedDict", [], [], set(), call.line, None)
        else:
            if var_name is not None and name != var_name:
                self.fail(
                    'First argument "{}" to TypedDict() does not match variable name "{}"'.format(
                        name, var_name
                    ),
                    node,
                    code=codes.NAME_MATCH,
                )
            if name != var_name or is_func_scope:
                # Give it a unique name derived from the line number.
                name += "@" + str(call.line)
            required_keys = {
                field
                for (field, t) in zip(items, types)
                if (total or (isinstance(t, RequiredType) and t.required))
                and not (isinstance(t, RequiredType) and not t.required)
            }
            types = [  # unwrap Required[T] to just T
                t.item if isinstance(t, RequiredType) else t for t in types
            ]
            existing_info = None
            if isinstance(node.analyzed, TypedDictExpr):
                existing_info = node.analyzed.info
            info = self.build_typeddict_typeinfo(
                name, items, types, required_keys, call.line, existing_info
            )
            info.line = node.line
            # Store generated TypeInfo under both names, see semanal_namedtuple for more details.
            if name != var_name or is_func_scope:
                self.api.add_symbol_skip_local(name, info)
        if var_name:
            self.api.add_symbol(var_name, info, node)
        call.analyzed = TypedDictExpr(info)
        call.analyzed.set_line(call)
        return True, info, tvar_defs

    def parse_typeddict_args(
        self, call: CallExpr
    ) -> tuple[str, list[str], list[Type], bool, list[TypeVarLikeType], bool] | None:
        """Parse typed dict call expression.

        Return names, types, totality, was there an error during parsing.
        If some type is not ready, return None.
        """
        # TODO: Share code with check_argument_count in checkexpr.py?
        args = call.args
        if len(args) < 2:
            return self.fail_typeddict_arg("Too few arguments for TypedDict()", call)
        if len(args) > 3:
            return self.fail_typeddict_arg("Too many arguments for TypedDict()", call)
        # TODO: Support keyword arguments
        if call.arg_kinds not in ([ARG_POS, ARG_POS], [ARG_POS, ARG_POS, ARG_NAMED]):
            return self.fail_typeddict_arg("Unexpected arguments to TypedDict()", call)
        if len(args) == 3 and call.arg_names[2] != "total":
            return self.fail_typeddict_arg(
                f'Unexpected keyword argument "{call.arg_names[2]}" for "TypedDict"', call
            )
        if not isinstance(args[0], StrExpr):
            return self.fail_typeddict_arg(
                "TypedDict() expects a string literal as the first argument", call
            )
        if not isinstance(args[1], DictExpr):
            return self.fail_typeddict_arg(
                "TypedDict() expects a dictionary literal as the second argument", call
            )
        total: bool | None = True
        if len(args) == 3:
            total = require_bool_literal_argument(self.api, call.args[2], "total")
            if total is None:
                return "", [], [], True, [], False
        dictexpr = args[1]
        tvar_defs = self.api.get_and_bind_all_tvars([t for k, t in dictexpr.items])
        res = self.parse_typeddict_fields_with_types(dictexpr.items, call)
        if res is None:
            # One of the types is not ready, defer.
            return None
        items, types, ok = res
        for t in types:
            check_for_explicit_any(
                t, self.options, self.api.is_typeshed_stub_file, self.msg, context=call
            )

        if self.options.disallow_any_unimported:
            for t in types:
                if has_any_from_unimported_type(t):
                    self.msg.unimported_type_becomes_any("Type of a TypedDict key", t, dictexpr)
        assert total is not None
        return args[0].value, items, types, total, tvar_defs, ok

    def parse_typeddict_fields_with_types(
        self, dict_items: list[tuple[Expression | None, Expression]], context: Context
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
                if (
                    isinstance(field_type_expr, CallExpr)
                    and isinstance(field_type_expr.callee, RefExpr)
                    and field_type_expr.callee.fullname in TPDICT_NAMES
                ):
                    self.fail_typeddict_arg(
                        "Inline TypedDict types not supported; use assignment to define TypedDict",
                        field_type_expr,
                    )
                else:
                    self.fail_typeddict_arg("Invalid field type", field_type_expr)
                return [], [], False
            analyzed = self.api.anal_type(
                type,
                allow_required=True,
                allow_placeholder=not self.options.disable_recursive_aliases
                and not self.api.is_func_scope(),
                prohibit_self_type="TypedDict item type",
            )
            if analyzed is None:
                return None
            types.append(analyzed)
        return items, types, True

    def fail_typeddict_arg(
        self, message: str, context: Context
    ) -> tuple[str, list[str], list[Type], bool, list[TypeVarLikeType], bool]:
        self.fail(message, context)
        return "", [], [], True, [], False

    def build_typeddict_typeinfo(
        self,
        name: str,
        items: list[str],
        types: list[Type],
        required_keys: set[str],
        line: int,
        existing_info: TypeInfo | None,
    ) -> TypeInfo:
        # Prefer typing then typing_extensions if available.
        fallback = (
            self.api.named_type_or_none("typing._TypedDict", [])
            or self.api.named_type_or_none("typing_extensions._TypedDict", [])
            or self.api.named_type_or_none("mypy_extensions._TypedDict", [])
        )
        assert fallback is not None
        info = existing_info or self.api.basic_new_typeinfo(name, fallback, line)
        typeddict_type = TypedDictType(dict(zip(items, types)), required_keys, fallback)
        if info.special_alias and has_placeholder(info.special_alias.target):
            self.api.process_placeholder(
                None, "TypedDict item", info, force_progress=typeddict_type != info.typeddict_type
            )
        info.update_typeddict_type(typeddict_type)
        return info

    # Helpers

    def is_typeddict(self, expr: Expression) -> bool:
        return (
            isinstance(expr, RefExpr)
            and isinstance(expr.node, TypeInfo)
            and expr.node.typeddict_type is not None
        )

    def fail(self, msg: str, ctx: Context, *, code: ErrorCode | None = None) -> None:
        self.api.fail(msg, ctx, code=code)

    def note(self, msg: str, ctx: Context) -> None:
        self.api.note(msg, ctx)
