"""Semantic analysis of TypedDict definitions.

This is conceptually part of mypy.semanal (semantic analyzer pass 2).
"""

from collections import OrderedDict
from typing import Optional, List, Set, Tuple, cast

from mypy.types import Type, AnyType, TypeOfAny, TypedDictType
from mypy.nodes import (
    CallExpr, TypedDictExpr, Expression, NameExpr, Context, StrExpr, BytesExpr, UnicodeExpr,
    ClassDef, RefExpr, TypeInfo, AssignmentStmt, PassStmt, ExpressionStmt, EllipsisExpr, TempNode,
    SymbolTableNode, DictExpr, GDEF, ARG_POS, ARG_NAMED
)
from mypy.semanal_shared import SemanticAnalyzerInterface
from mypy.exprtotype import expr_to_unanalyzed_type, TypeTranslationError
from mypy.options import Options
from mypy.typeanal import check_for_explicit_any, has_any_from_unimported_type
from mypy.messages import MessageBuilder

MYPY = False
if MYPY:
    from typing_extensions import Final

TPDICT_CLASS_ERROR = ('Invalid statement in TypedDict definition; '
                      'expected "field_name: field_type"')  # type: Final


class TypedDictAnalyzer:
    def __init__(self,
                 options: Options,
                 api: SemanticAnalyzerInterface,
                 msg: MessageBuilder) -> None:
        self.options = options
        self.api = api
        self.msg = msg

    def analyze_typeddict_classdef(self, defn: ClassDef) -> bool:
        # special case for TypedDict
        possible = False
        for base_expr in defn.base_type_exprs:
            if isinstance(base_expr, RefExpr):
                self.api.accept(base_expr)
                if (base_expr.fullname == 'mypy_extensions.TypedDict' or
                        self.is_typeddict(base_expr)):
                    possible = True
        if possible:
            node = self.api.lookup(defn.name, defn)
            if node is not None:
                node.kind = GDEF  # TODO in process_namedtuple_definition also applies here
                if (len(defn.base_type_exprs) == 1 and
                        isinstance(defn.base_type_exprs[0], RefExpr) and
                        defn.base_type_exprs[0].fullname == 'mypy_extensions.TypedDict'):
                    # Building a new TypedDict
                    fields, types, required_keys = self.check_typeddict_classdef(defn)
                    info = self.build_typeddict_typeinfo(defn.name, fields, types, required_keys)
                    defn.info.replaced = info
                    defn.info = info
                    node.node = info
                    defn.analyzed = TypedDictExpr(info)
                    defn.analyzed.line = defn.line
                    defn.analyzed.column = defn.column
                    return True
                # Extending/merging existing TypedDicts
                if any(not isinstance(expr, RefExpr) or
                       expr.fullname != 'mypy_extensions.TypedDict' and
                       not self.is_typeddict(expr) for expr in defn.base_type_exprs):
                    self.fail("All bases of a new TypedDict must be TypedDict types", defn)
                typeddict_bases = list(filter(self.is_typeddict, defn.base_type_exprs))
                keys = []  # type: List[str]
                types = []
                required_keys = set()
                for base in typeddict_bases:
                    assert isinstance(base, RefExpr)
                    assert isinstance(base.node, TypeInfo)
                    assert isinstance(base.node.typeddict_type, TypedDictType)
                    base_typed_dict = base.node.typeddict_type
                    base_items = base_typed_dict.items
                    valid_items = base_items.copy()
                    for key in base_items:
                        if key in keys:
                            self.fail('Cannot overwrite TypedDict field "{}" while merging'
                                      .format(key), defn)
                            valid_items.pop(key)
                    keys.extend(valid_items.keys())
                    types.extend(valid_items.values())
                    required_keys.update(base_typed_dict.required_keys)
                new_keys, new_types, new_required_keys = self.check_typeddict_classdef(defn, keys)
                keys.extend(new_keys)
                types.extend(new_types)
                required_keys.update(new_required_keys)
                info = self.build_typeddict_typeinfo(defn.name, keys, types, required_keys)
                defn.info.replaced = info
                defn.info = info
                node.node = info
                defn.analyzed = TypedDictExpr(info)
                defn.analyzed.line = defn.line
                defn.analyzed.column = defn.column
                return True
        return False

    def check_typeddict_classdef(self, defn: ClassDef,
                                 oldfields: Optional[List[str]] = None) -> Tuple[List[str],
                                                                                 List[Type],
                                                                                 Set[str]]:
        if self.options.python_version < (3, 6):
            self.fail('TypedDict class syntax is only supported in Python 3.6', defn)
            return [], [], set()
        fields = []  # type: List[str]
        types = []  # type: List[Type]
        for stmt in defn.defs.body:
            if not isinstance(stmt, AssignmentStmt):
                # Still allow pass or ... (for empty TypedDict's).
                if (not isinstance(stmt, PassStmt) and
                    not (isinstance(stmt, ExpressionStmt) and
                         isinstance(stmt.expr, (EllipsisExpr, StrExpr)))):
                    self.fail(TPDICT_CLASS_ERROR, stmt)
            elif len(stmt.lvalues) > 1 or not isinstance(stmt.lvalues[0], NameExpr):
                # An assignment, but an invalid one.
                self.fail(TPDICT_CLASS_ERROR, stmt)
            else:
                name = stmt.lvalues[0].name
                if name in (oldfields or []):
                    self.fail('Cannot overwrite TypedDict field "{}" while extending'
                              .format(name), stmt)
                    continue
                if name in fields:
                    self.fail('Duplicate TypedDict field "{}"'.format(name), stmt)
                    continue
                # Append name and type in this case...
                fields.append(name)
                types.append(AnyType(TypeOfAny.unannotated)
                             if stmt.type is None
                             else self.api.anal_type(stmt.type))
                # ...despite possible minor failures that allow further analyzis.
                if stmt.type is None or hasattr(stmt, 'new_syntax') and not stmt.new_syntax:
                    self.fail(TPDICT_CLASS_ERROR, stmt)
                elif not isinstance(stmt.rvalue, TempNode):
                    # x: int assigns rvalue to TempNode(AnyType())
                    self.fail('Right hand side values are not supported in TypedDict', stmt)
        total = True  # type: Optional[bool]
        if 'total' in defn.keywords:
            total = self.api.parse_bool(defn.keywords['total'])
            if total is None:
                self.fail('Value of "total" must be True or False', defn)
                total = True
        required_keys = set(fields) if total else set()
        return fields, types, required_keys

    def process_typeddict_definition(self, s: AssignmentStmt, is_func_scope: bool) -> None:
        """Check if s defines a TypedDict; if yes, store the definition in symbol table."""
        if len(s.lvalues) != 1 or not isinstance(s.lvalues[0], NameExpr):
            return
        lvalue = s.lvalues[0]
        name = lvalue.name
        typed_dict = self.check_typeddict(s.rvalue, name, is_func_scope)
        if typed_dict is None:
            return
        # Yes, it's a valid TypedDict definition. Add it to the symbol table.
        node = self.api.lookup(name, s)
        if node:
            node.kind = GDEF   # TODO locally defined TypedDict
            node.node = typed_dict

    def check_typeddict(self,
                        node: Expression,
                        var_name: Optional[str],
                        is_func_scope: bool) -> Optional[TypeInfo]:
        """Check if a call defines a TypedDict.

        The optional var_name argument is the name of the variable to
        which this is assigned, if any.

        If it does, return the corresponding TypeInfo. Return None otherwise.

        If the definition is invalid but looks like a TypedDict,
        report errors but return (some) TypeInfo.
        """
        if not isinstance(node, CallExpr):
            return None
        call = node
        callee = call.callee
        if not isinstance(callee, RefExpr):
            return None
        fullname = callee.fullname
        if fullname != 'mypy_extensions.TypedDict':
            return None
        items, types, total, ok = self.parse_typeddict_args(call)
        if not ok:
            # Error. Construct dummy return value.
            info = self.build_typeddict_typeinfo('TypedDict', [], [], set())
        else:
            name = cast(StrExpr, call.args[0]).value
            if var_name is not None and name != var_name:
                self.fail(
                    "First argument '{}' to TypedDict() does not match variable name '{}'".format(
                        name, var_name), node)
            if name != var_name or is_func_scope:
                # Give it a unique name derived from the line number.
                name += '@' + str(call.line)
            required_keys = set(items) if total else set()
            info = self.build_typeddict_typeinfo(name, items, types, required_keys)
            # Store it as a global just in case it would remain anonymous.
            # (Or in the nearest class if there is one.)
            stnode = SymbolTableNode(GDEF, info)
            self.api.add_symbol_table_node(name, stnode)
        call.analyzed = TypedDictExpr(info)
        call.analyzed.set_line(call.line, call.column)
        return info

    def parse_typeddict_args(self, call: CallExpr) -> Tuple[List[str], List[Type], bool, bool]:
        # TODO: Share code with check_argument_count in checkexpr.py?
        args = call.args
        if len(args) < 2:
            return self.fail_typeddict_arg("Too few arguments for TypedDict()", call)
        if len(args) > 3:
            return self.fail_typeddict_arg("Too many arguments for TypedDict()", call)
        # TODO: Support keyword arguments
        if call.arg_kinds not in ([ARG_POS, ARG_POS], [ARG_POS, ARG_POS, ARG_NAMED]):
            return self.fail_typeddict_arg("Unexpected arguments to TypedDict()", call)
        if len(args) == 3 and call.arg_names[2] != 'total':
            return self.fail_typeddict_arg(
                'Unexpected keyword argument "{}" for "TypedDict"'.format(call.arg_names[2]), call)
        if not isinstance(args[0], (StrExpr, BytesExpr, UnicodeExpr)):
            return self.fail_typeddict_arg(
                "TypedDict() expects a string literal as the first argument", call)
        if not isinstance(args[1], DictExpr):
            return self.fail_typeddict_arg(
                "TypedDict() expects a dictionary literal as the second argument", call)
        total = True  # type: Optional[bool]
        if len(args) == 3:
            total = self.api.parse_bool(call.args[2])
            if total is None:
                return self.fail_typeddict_arg(
                    'TypedDict() "total" argument must be True or False', call)
        dictexpr = args[1]
        items, types, ok = self.parse_typeddict_fields_with_types(dictexpr.items, call)
        for t in types:
            check_for_explicit_any(t, self.options, self.api.is_typeshed_stub_file, self.msg,
                                   context=call)

        if self.options.disallow_any_unimported:
            for t in types:
                if has_any_from_unimported_type(t):
                    self.msg.unimported_type_becomes_any("Type of a TypedDict key", t, dictexpr)
        assert total is not None
        return items, types, total, ok

    def parse_typeddict_fields_with_types(
            self,
            dict_items: List[Tuple[Optional[Expression], Expression]],
            context: Context) -> Tuple[List[str], List[Type], bool]:
        items = []  # type: List[str]
        types = []  # type: List[Type]
        for (field_name_expr, field_type_expr) in dict_items:
            if isinstance(field_name_expr, (StrExpr, BytesExpr, UnicodeExpr)):
                items.append(field_name_expr.value)
            else:
                name_context = field_name_expr or field_type_expr
                self.fail_typeddict_arg("Invalid TypedDict() field name", name_context)
                return [], [], False
            try:
                type = expr_to_unanalyzed_type(field_type_expr)
            except TypeTranslationError:
                self.fail_typeddict_arg('Invalid field type', field_type_expr)
                return [], [], False
            types.append(self.api.anal_type(type))
        return items, types, True

    def fail_typeddict_arg(self, message: str,
                           context: Context) -> Tuple[List[str], List[Type], bool, bool]:
        self.fail(message, context)
        return [], [], True, False

    def build_typeddict_typeinfo(self, name: str, items: List[str],
                                 types: List[Type],
                                 required_keys: Set[str]) -> TypeInfo:
        fallback = self.api.named_type_or_none('mypy_extensions._TypedDict', [])
        assert fallback is not None
        info = self.api.basic_new_typeinfo(name, fallback)
        info.typeddict_type = TypedDictType(OrderedDict(zip(items, types)), required_keys,
                                            fallback)
        return info

    # Helpers

    def is_typeddict(self, expr: Expression) -> bool:
        return (isinstance(expr, RefExpr) and isinstance(expr.node, TypeInfo) and
                expr.node.typeddict_type is not None)

    def fail(self, msg: str, ctx: Context) -> None:
        self.api.fail(msg, ctx)
