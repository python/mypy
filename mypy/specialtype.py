"""Special case semantic analysis for type-expressions, such as namedtuple.

This module is used only by the SemanticAnalyzer, and is tightly coupled with it.
"""

from collections import OrderedDict

from typing import List, Dict, Tuple, cast, Optional, Callable, TYPE_CHECKING

from mypy.exprtotype import expr_to_unanalyzed_type, TypeTranslationError
from mypy.nodes import (
    TypeInfo, AssignmentStmt, FuncDef, ClassDef, Var, GDEF, Expression,
    Block, NameExpr, TupleExpr, ListExpr, ExpressionStmt, PassStmt,
    DictExpr, CallExpr, RefExpr, Context, SymbolTable, UNBOUND_TVAR,
    MDEF, Decorator, TypeVarExpr, NewTypeExpr, StrExpr, BytesExpr,
    ARG_POS, ARG_NAMED, ARG_NAMED_OPT, NamedTupleExpr, TypedDictExpr, Argument,
    UnicodeExpr, EllipsisExpr, TempNode, EnumCallExpr,
    COVARIANT, CONTRAVARIANT, INVARIANT, ARG_OPT, SymbolTableNode
)
from mypy.types import (
    NoneTyp, CallableType, Instance, Type, TypeVarType, AnyType,
    TypeVarDef, TupleType, UnboundType, TypedDictType, TypeType,
)
from mypy import join
if TYPE_CHECKING:
    import mypy.semanal


class Special:
    """Handling of special-cased types.

    Special-cased types include:
    * NamedTuple
    * TypedDict
    * NewType
    Also handles analysis of special constructs:
    * Enum (functional style)
    * TypeVar

    The interface consists of
    * process_declarations()
    * analyze_*
    """

    def __init__(self, semanalyzer: 'mypy.semanal.SemanticAnalyzer') -> None:
        self.semanalyzer = semanalyzer
        # Delegations:
        self.fail = semanalyzer.fail
        self.lookup = semanalyzer.lookup
        self.lookup_qualified = semanalyzer.lookup_qualified
        self.named_type = semanalyzer.named_type
        self.named_type_or_none = semanalyzer.named_type_or_none
        self.object_type = semanalyzer.object_type
        self.str_type = semanalyzer.str_type

    def process_declaration(self, s: AssignmentStmt) -> None:
        self.process_newtype_declaration(s)
        self.process_typevar_declaration(s)
        self.process_namedtuple_definition(s)
        self.process_typeddict_definition(s)
        self.process_enum_call(s)

    def analyze_namedtuple_classdef(self, defn: ClassDef) -> bool:
        for base_expr in defn.base_type_exprs:
            if isinstance(base_expr, RefExpr):
                base_expr.accept(self.semanalyzer)
                if base_expr.fullname == 'typing.NamedTuple':
                    node = self.lookup(defn.name, defn)
                    if node is not None:
                        node.kind = GDEF  # TODO in process_namedtuple_definition also applies here
                        items, types, default_items = self.check_namedtuple_classdef(defn)
                        node.node = self.build_namedtuple_typeinfo(
                            defn.name, items, types, default_items)
                        return True
        return False

    def check_namedtuple_classdef(
            self, defn: ClassDef) -> Tuple[List[str], List[Type], Dict[str, Expression]]:
        NAMEDTUP_CLASS_ERROR = ('Invalid statement in NamedTuple definition; '
                                'expected "field_name: field_type"')
        if self.semanalyzer.options.python_version < (3, 6):
            self.fail('NamedTuple class syntax is only supported in Python 3.6', defn)
            return [], [], {}
        if len(defn.base_type_exprs) > 1:
            self.fail('NamedTuple should be a single base', defn)
        items = []  # type: List[str]
        types = []  # type: List[Type]
        default_items = {}  # type: Dict[str, Expression]
        for stmt in defn.defs.body:
            if not isinstance(stmt, AssignmentStmt):
                # Still allow pass or ... (for empty namedtuples).
                if (not isinstance(stmt, PassStmt) and
                    not (isinstance(stmt, ExpressionStmt) and
                         isinstance(stmt.expr, EllipsisExpr))):
                    self.fail(NAMEDTUP_CLASS_ERROR, stmt)
            elif len(stmt.lvalues) > 1 or not isinstance(stmt.lvalues[0], NameExpr):
                # An assignment, but an invalid one.
                self.fail(NAMEDTUP_CLASS_ERROR, stmt)
            else:
                # Append name and type in this case...
                name = stmt.lvalues[0].name
                items.append(name)
                types.append(AnyType() if stmt.type is None
                             else self.semanalyzer.anal_type(stmt.type))
                # ...despite possible minor failures that allow further analyzis.
                if name.startswith('_'):
                    self.fail('NamedTuple field name cannot start with an underscore: {}'
                              .format(name), stmt)
                if stmt.type is None or hasattr(stmt, 'new_syntax') and not stmt.new_syntax:
                    self.fail(NAMEDTUP_CLASS_ERROR, stmt)
                elif isinstance(stmt.rvalue, TempNode):
                    # x: int assigns rvalue to TempNode(AnyType())
                    if default_items:
                        self.fail('Non-default NamedTuple fields cannot follow default fields',
                                  stmt)
                else:
                    default_items[name] = stmt.rvalue
        return items, types, default_items

    def analyze_typeddict_classdef(self, defn: ClassDef) -> bool:
        # special case for TypedDict
        possible = False
        for base_expr in defn.base_type_exprs:
            if isinstance(base_expr, RefExpr):
                base_expr.accept(self.semanalyzer)
                if (base_expr.fullname == 'mypy_extensions.TypedDict' or
                        is_typeddict(base_expr)):
                    possible = True
        if possible:
            node = self.lookup(defn.name, defn)
            if node is not None:
                node.kind = GDEF  # TODO in process_namedtuple_definition also applies here
                if (len(defn.base_type_exprs) == 1 and
                        isinstance(defn.base_type_exprs[0], RefExpr) and
                        defn.base_type_exprs[0].fullname == 'mypy_extensions.TypedDict'):
                    # Building a new TypedDict
                    fields, types = self.check_typeddict_classdef(defn)
                    node.node = self.build_typeddict_typeinfo(defn.name, fields, types)
                    return True
                # Extending/merging existing TypedDicts
                if any(not isinstance(expr, RefExpr) or
                       expr.fullname != 'mypy_extensions.TypedDict' and
                       not is_typeddict(expr) for expr in defn.base_type_exprs):
                    self.fail("All bases of a new TypedDict must be TypedDict types", defn)
                typeddict_bases = list(filter(is_typeddict, defn.base_type_exprs))
                newfields = []  # type: List[str]
                newtypes = []  # type: List[Type]
                tpdict = None  # type: OrderedDict[str, Type]
                for base in typeddict_bases:
                    assert isinstance(base, RefExpr)
                    assert isinstance(base.node, TypeInfo)
                    assert isinstance(base.node.typeddict_type, TypedDictType)
                    tpdict = base.node.typeddict_type.items
                    newdict = tpdict.copy()
                    for key in tpdict:
                        if key in newfields:
                            self.fail('Cannot overwrite TypedDict field "{}" while merging'
                                      .format(key), defn)
                            newdict.pop(key)
                    newfields.extend(newdict.keys())
                    newtypes.extend(newdict.values())
                fields, types = self.check_typeddict_classdef(defn, newfields)
                newfields.extend(fields)
                newtypes.extend(types)
                node.node = self.build_typeddict_typeinfo(defn.name, newfields, newtypes)
                return True
        return False

    def check_typeddict_classdef(self, defn: ClassDef,
                                 oldfields: List[str] = None) -> Tuple[List[str], List[Type]]:
        TPDICT_CLASS_ERROR = ('Invalid statement in TypedDict definition; '
                              'expected "field_name: field_type"')
        if self.semanalyzer.options.python_version < (3, 6):
            self.fail('TypedDict class syntax is only supported in Python 3.6', defn)
            return [], []
        fields = []  # type: List[str]
        types = []  # type: List[Type]
        for stmt in defn.defs.body:
            if not isinstance(stmt, AssignmentStmt):
                # Still allow pass or ... (for empty TypedDict's).
                if (not isinstance(stmt, PassStmt) and
                    not (isinstance(stmt, ExpressionStmt) and
                         isinstance(stmt.expr, EllipsisExpr))):
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
                types.append(AnyType() if stmt.type is None
                             else self.semanalyzer.anal_type(stmt.type))
                # ...despite possible minor failures that allow further analyzis.
                if stmt.type is None or hasattr(stmt, 'new_syntax') and not stmt.new_syntax:
                    self.fail(TPDICT_CLASS_ERROR, stmt)
                elif not isinstance(stmt.rvalue, TempNode):
                    # x: int assigns rvalue to TempNode(AnyType())
                    self.fail('Right hand side values are not supported in TypedDict', stmt)
        return fields, types

    def process_newtype_declaration(self, s: AssignmentStmt) -> None:
        """Check if s declares a NewType; if yes, store it in symbol table."""
        # Extract and check all information from newtype declaration
        name, call = self.analyze_newtype_declaration(s)
        if name is None or call is None:
            return

        old_type = self.check_newtype_args(name, call, s)
        call.analyzed = NewTypeExpr(name, old_type, line=call.line)
        if old_type is None:
            return

        # Create the corresponding class definition if the aliased type is subtypeable
        if isinstance(old_type, TupleType):
            newtype_class_info = self.build_newtype_typeinfo(name, old_type, old_type.fallback)
            newtype_class_info.tuple_type = old_type
        elif isinstance(old_type, Instance):
            newtype_class_info = self.build_newtype_typeinfo(name, old_type, old_type)
        else:
            message = "Argument 2 to NewType(...) must be subclassable (got {})"
            self.fail(message.format(old_type), s)
            return

        # If so, add it to the symbol table.
        node = self.lookup(name, s)
        if node is None:
            self.fail("Could not find {} in current namespace".format(name), s)
            return
        # TODO: why does NewType work in local scopes despite always being of kind GDEF?
        node.kind = GDEF
        call.analyzed.info = node.node = newtype_class_info

    def analyze_newtype_declaration(self, s: AssignmentStmt
                                    ) -> Tuple[Optional[str], Optional[CallExpr]]:
        """Return the NewType call expression if `s` is a newtype declaration or None otherwise."""
        name, call = None, None
        if (len(s.lvalues) == 1
                and isinstance(s.lvalues[0], NameExpr)
                and isinstance(s.rvalue, CallExpr)
                and isinstance(s.rvalue.callee, RefExpr)
                and s.rvalue.callee.fullname == 'typing.NewType'):
            lvalue = s.lvalues[0]
            name = s.lvalues[0].name
            if not lvalue.is_def:
                if s.type:
                    self.fail("Cannot declare the type of a NewType declaration", s)
                else:
                    self.fail("Cannot redefine '%s' as a NewType" % name, s)

            # This dummy NewTypeExpr marks the call as sufficiently analyzed; it will be
            # overwritten later with a fully complete NewTypeExpr if there are no other
            # errors with the NewType() call.
            call = s.rvalue

        return name, call

    def check_newtype_args(self, name: str, call: CallExpr, context: Context) -> Optional[Type]:
        has_failed = False
        args, arg_kinds = call.args, call.arg_kinds
        if len(args) != 2 or arg_kinds[0] != ARG_POS or arg_kinds[1] != ARG_POS:
            self.fail("NewType(...) expects exactly two positional arguments", context)
            return None

        # Check first argument
        if not isinstance(args[0], (StrExpr, BytesExpr, UnicodeExpr)):
            self.fail("Argument 1 to NewType(...) must be a string literal", context)
            has_failed = True
        elif args[0].value != name:
            msg = "String argument 1 '{}' to NewType(...) does not match variable name '{}'"
            self.fail(msg.format(args[0].value, name), context)
            has_failed = True

        # Check second argument
        try:
            unanalyzed_type = expr_to_unanalyzed_type(args[1])
        except TypeTranslationError:
            self.fail("Argument 2 to NewType(...) must be a valid type", context)
            return None
        old_type = self.semanalyzer.anal_type(unanalyzed_type)

        if isinstance(old_type, Instance) and old_type.type.is_newtype:
            self.fail("Argument 2 to NewType(...) cannot be another NewType", context)
            has_failed = True

        return None if has_failed else old_type

    def build_newtype_typeinfo(self, name: str, old_type: Type, base_type: Instance) -> TypeInfo:
        info = self.basic_new_typeinfo(name, base_type)
        info.is_newtype = True

        # Add __init__ method
        args = [Argument(Var('cls'), NoneTyp(), None, ARG_POS),
                Argument(Var('item'), old_type, None, ARG_POS)]
        signature = CallableType(
            arg_types=[cast(Type, None), old_type],
            arg_kinds=[arg.kind for arg in args],
            arg_names=['self', 'item'],
            ret_type=old_type,
            fallback=self.named_type('__builtins__.function'),
            name=name)
        init_func = FuncDef('__init__', args, Block([]), typ=signature)
        init_func.info = info
        info.names['__init__'] = SymbolTableNode(MDEF, init_func)

        return info

    def analyze_typevar_declaration(self, t: Type) -> Optional[List[Tuple[str, TypeVarExpr]]]:
        if not isinstance(t, UnboundType):
            return None
        unbound = t
        sym = self.lookup_qualified(unbound.name, unbound)
        if sym is None or sym.node is None:
            return None
        if sym.node.fullname() == 'typing.Generic':
            tvars = []  # type: List[Tuple[str, TypeVarExpr]]
            for arg in unbound.args:
                tvar = self.semanalyzer.analyze_unbound_tvar(arg)
                if tvar:
                    tvars.append(tvar)
                else:
                    self.fail('Free type variable expected in %s[...]' %
                              sym.node.name(), t)
            return tvars
        return None

    def analyze_types(self, items: List[Expression]) -> List[Type]:
        result = []  # type: List[Type]
        for node in items:
            try:
                result.append(self.semanalyzer.anal_type(expr_to_unanalyzed_type(node)))
            except TypeTranslationError:
                self.fail('Type expected', node)
                result.append(AnyType())
        return result

    def process_typevar_declaration(self, s: AssignmentStmt) -> None:
        """Check if s declares a TypeVar; it yes, store it in symbol table."""
        if len(s.lvalues) != 1 or not isinstance(s.lvalues[0], NameExpr):
            return None
        lvalue = s.lvalues[0]
        call, calleename, name = self.get_call(s.rvalue, lvalue.name, fresh=False)
        if calleename != 'typing.TypeVar':
            return None
        if not lvalue.is_def:
            if s.type:
                self.fail("Cannot declare the type of a type variable", s)
            else:
                self.fail("Cannot redefine '%s' as a type variable" % name, s)
            return

        if not self.check_typevar_name(call, name, s):
            return

        # Constraining types
        n_values = call.arg_kinds[1:].count(ARG_POS)
        values = self.analyze_types(call.args[1:1 + n_values])

        res = self.process_typevar_parameters(call.args[1 + n_values:],
                                              call.arg_names[1 + n_values:],
                                              call.arg_kinds[1 + n_values:],
                                              n_values,
                                              s)
        if res is None:
            return
        variance, upper_bound = res

        # Yes, it's a valid type variable definition! Add it to the symbol table.
        node = self.lookup(name, s)
        node.kind = UNBOUND_TVAR
        TypeVar = TypeVarExpr(name, node.fullname, values, upper_bound, variance)
        TypeVar.line = call.line
        call.analyzed = TypeVar
        node.node = TypeVar

    def check_typevar_name(self, call: CallExpr, name: str, context: Context) -> bool:
        if len(call.args) < 1:
            self.fail("Too few arguments for TypeVar()", context)
            return False
        if (not isinstance(call.args[0], (StrExpr, BytesExpr, UnicodeExpr))
                or not call.arg_kinds[0] == ARG_POS):
            self.fail("TypeVar() expects a string literal as first argument", context)
            return False
        elif call.args[0].value != name:
            msg = "String argument 1 '{}' to TypeVar(...) does not match variable name '{}'"
            self.fail(msg.format(call.args[0].value, name), context)
            return False
        return True

    def process_typevar_parameters(self,
                                   args: List[Expression],
                                   names: List[Optional[str]],
                                   kinds: List[int],
                                   num_values: int,
                                   context: Context) -> Optional[Tuple[int, Type]]:
        has_values = (num_values > 0)
        covariant = False
        contravariant = False
        upper_bound = self.object_type()  # type: Type
        for param_value, param_name, param_kind in zip(args, names, kinds):
            if not param_kind == ARG_NAMED:
                self.fail("Unexpected argument to TypeVar()", context)
                return None
            if param_name == 'covariant':
                if isinstance(param_value, NameExpr):
                    if param_value.name == 'True':
                        covariant = True
                    else:
                        self.fail("TypeVar 'covariant' may only be 'True'", context)
                        return None
                else:
                    self.fail("TypeVar 'covariant' may only be 'True'", context)
                    return None
            elif param_name == 'contravariant':
                if isinstance(param_value, NameExpr):
                    if param_value.name == 'True':
                        contravariant = True
                    else:
                        self.fail("TypeVar 'contravariant' may only be 'True'", context)
                        return None
                else:
                    self.fail("TypeVar 'contravariant' may only be 'True'", context)
                    return None
            elif param_name == 'bound':
                if has_values:
                    self.fail("TypeVar cannot have both values and an upper bound", context)
                    return None
                try:
                    upper_bound = self.semanalyzer.expr_to_analyzed_type(param_value)
                except TypeTranslationError:
                    self.fail("TypeVar 'bound' must be a type", param_value)
                    return None
            elif param_name == 'values':
                # Probably using obsolete syntax with values=(...). Explain the current syntax.
                self.fail("TypeVar 'values' argument not supported", context)
                self.fail("Use TypeVar('T', t, ...) instead of TypeVar('T', values=(t, ...))",
                          context)
                return None
            else:
                self.fail("Unexpected argument to TypeVar(): {}".format(param_name), context)
                return None

        if covariant and contravariant:
            self.fail("TypeVar cannot be both covariant and contravariant", context)
            return None
        elif num_values == 1:
            self.fail("TypeVar cannot have only a single constraint", context)
            return None
        elif covariant:
            variance = COVARIANT
        elif contravariant:
            variance = CONTRAVARIANT
        else:
            variance = INVARIANT
        return (variance, upper_bound)

    def process_call(self, s: AssignmentStmt,
                     check: Callable[[Expression, str], TypeInfo]) -> None:
        """Check if s defines a legal node; if yes, store the definition in symbol table."""
        if len(s.lvalues) != 1 or not isinstance(s.lvalues[0], NameExpr):
            return
        lvalue = s.lvalues[0]
        name = lvalue.name
        info = check(s.rvalue, name)
        if info is None:
            return
        # Yes, it's a valid definition. Add it to the symbol table.
        node = self.lookup(name, s)
        node.kind = GDEF   # TODO locally defined type
        node.node = info

    def process_namedtuple_definition(self, s: AssignmentStmt) -> None:
        self.process_call(s, self.check_namedtuple)

    def process_enum_call(self, s: AssignmentStmt) -> None:
        self.process_call(s, self.check_enum_call)

    def check_namedtuple(self, expr: Expression, var_name: str = None) -> Optional[TypeInfo]:
        """Check if a call defines a namedtuple.

        The optional var_name argument is the name of the variable to
        which this is assigned, if any.

        If it does, return the corresponding TypeInfo. Return None otherwise.

        If the definition is invalid but looks like a namedtuple,
        report errors but return (some) TypeInfo.
        """

        call, calleename, name = self.get_call(expr, var_name)
        if calleename not in ('collections.namedtuple', 'typing.NamedTuple'):
            return None
        items, types, ok = self.parse_namedtuple_args(call, calleename)
        info = self.build_namedtuple_typeinfo(name, items, types)
        if ok:
            self.semanalyzer.store_info(info, name)
            call.analyzed = NamedTupleExpr(info)
            call.analyzed.set_line(call.line, call.column)
        return info

    def parse_namedtuple_args(self, call: CallExpr,
                              fullname: str) -> Tuple[List[str], List[Type], bool]:
        # TODO: Share code with check_argument_count in checkexpr.py?
        args = call.args
        if len(args) < 2:
            return self.fail_namedtuple_arg("Too few arguments for namedtuple()", call)
        if len(args) > 2:
            # FIX incorrect. There are two additional parameters
            return self.fail_namedtuple_arg("Too many arguments for namedtuple()", call)
        if call.arg_kinds != [ARG_POS, ARG_POS]:
            return self.fail_namedtuple_arg("Unexpected arguments to namedtuple()", call)
        if not isinstance(args[0], (StrExpr, BytesExpr, UnicodeExpr)):
            return self.fail_namedtuple_arg(
                "namedtuple() expects a string literal as the first argument", call)
        types = []  # type: List[Type]
        ok = True
        if not isinstance(args[1], (ListExpr, TupleExpr)):
            if (fullname == 'collections.namedtuple'
                    and isinstance(args[1], (StrExpr, BytesExpr, UnicodeExpr))):
                str_expr = cast(StrExpr, args[1])
                items = str_expr.value.replace(',', ' ').split()
            else:
                return self.fail_namedtuple_arg(
                    "List or tuple literal expected as the second argument to namedtuple()", call)
        else:
            listexpr = args[1]
            if fullname == 'collections.namedtuple':
                # The fields argument contains just names, with implicit Any types.
                if any(not isinstance(item, (StrExpr, BytesExpr, UnicodeExpr))
                       for item in listexpr.items):
                    return self.fail_namedtuple_arg("String literal expected as namedtuple() item",
                                                    call)
                items = [cast(StrExpr, item).value for item in listexpr.items]
            else:
                # The fields argument contains (name, type) tuples.
                items, types, ok = self.parse_namedtuple_fields_with_types(listexpr.items)
        if not types:
            types = [AnyType() for _ in items]
        underscore = [item for item in items if item.startswith('_')]
        if underscore:
            self.fail("namedtuple() field names cannot start with an underscore: "
                      + ', '.join(underscore), call)
        return items, types, ok

    def parse_namedtuple_fields_with_types(self, nodes: List[Expression]
                                           ) -> Tuple[List[str], List[Type], bool]:
        items = []  # type: List[str]
        types = []  # type: List[Type]
        for item in nodes:
            if isinstance(item, TupleExpr):
                if len(item.items) != 2:
                    return self.fail_namedtuple_arg("Invalid NamedTuple field definition",
                                                    item)
                name, type_node = item.items
                if isinstance(name, (StrExpr, BytesExpr, UnicodeExpr)):
                    items.append(name.value)
                else:
                    return self.fail_namedtuple_arg("Invalid NamedTuple() field name", item)
                try:
                    type = expr_to_unanalyzed_type(type_node)
                except TypeTranslationError:
                    return self.fail_namedtuple_arg('Invalid field type', type_node)
                types.append(self.semanalyzer.anal_type(type))
            else:
                return self.fail_namedtuple_arg("Tuple expected as NamedTuple() field", item)
        return items, types, True

    def fail_namedtuple_arg(self, message: str,
                            context: Context) -> Tuple[List[str], List[Type], bool]:
        self.fail(message, context)
        return [], [], False

    def basic_new_typeinfo(self, name: str, basetype_or_fallback: Instance) -> TypeInfo:
        class_def = ClassDef(name, Block([]))
        class_def.fullname = self.semanalyzer.qualified_name(name)

        info = TypeInfo(SymbolTable(), class_def, self.semanalyzer.cur_mod_id)
        info.mro = [info] + basetype_or_fallback.type.mro
        info.bases = [basetype_or_fallback]
        return info

    def analyze_callexpr_as_type(self, call: CallExpr) -> Optional[Type]:
        info = self.check_namedtuple(call)
        if info is None:
            # Some form of namedtuple is the only valid type that looks like a call
            # expression. This isn't a valid type.
            return None
        fallback = Instance(info, [])
        return TupleType(info.tuple_type.items, fallback=fallback)

    def build_namedtuple_typeinfo(self, name: str, items: List[str], types: List[Type],
                                  default_items: Dict[str, Expression] = None) -> TypeInfo:
        default_items = default_items or {}
        strtype = self.str_type()
        object_type = self.object_type()
        basetuple_type = self.named_type('__builtins__.tuple', [AnyType()])
        dictype = (self.named_type_or_none('builtins.dict', [strtype, AnyType()])
                   or object_type)
        # Actual signature should return OrderedDict[str, Union[types]]
        ordereddictype = (self.named_type_or_none('builtins.dict', [strtype, AnyType()])
                          or object_type)
        fallback = self.named_type('__builtins__.tuple', types)
        # Note: actual signature should accept an invariant version of Iterable[UnionType[types]].
        # but it can't be expressed. 'new' and 'len' should be callable types.
        iterable_type = self.named_type_or_none('typing.Iterable', [AnyType()])
        function_type = self.named_type('__builtins__.function')

        info = self.basic_new_typeinfo(name, fallback)
        info.is_named_tuple = True
        info.tuple_type = TupleType(types, fallback)

        def add_field(var: Var, is_initialized_in_class: bool = False,
                      is_property: bool = False) -> None:
            var.info = info
            var.is_initialized_in_class = is_initialized_in_class
            var.is_property = is_property
            info.names[var.name()] = SymbolTableNode(MDEF, var)

        vars = [Var(item, typ) for item, typ in zip(items, types)]
        for var in vars:
            add_field(var, is_property=True)

        tuple_of_strings = TupleType([strtype for _ in items], basetuple_type)
        add_field(Var('_fields', tuple_of_strings), is_initialized_in_class=True)
        add_field(Var('_field_types', dictype), is_initialized_in_class=True)
        add_field(Var('_field_defaults', dictype), is_initialized_in_class=True)
        add_field(Var('_source', strtype), is_initialized_in_class=True)

        tvd = TypeVarDef('NT', 1, [], info.tuple_type)
        selftype = TypeVarType(tvd)

        def add_method(funcname: str,
                       ret: Type,
                       args: List[Argument],
                       name: str = None,
                       is_classmethod: bool = False,
                       ) -> None:
            if is_classmethod:
                first = [Argument(Var('cls'), TypeType(selftype), None, ARG_POS)]
            else:
                first = [Argument(Var('self'), selftype, None, ARG_POS)]
            args = first + args

            types = [arg.type_annotation for arg in args]
            items = [arg.variable.name() for arg in args]
            arg_kinds = [arg.kind for arg in args]
            signature = CallableType(types, arg_kinds, items, ret, function_type,
                                     name=name or info.name() + '.' + funcname)
            signature.variables = [tvd]
            func = FuncDef(funcname, args, Block([]), typ=signature)
            func.info = info
            func.is_class = is_classmethod
            if is_classmethod:
                v = Var(funcname, signature)
                v.is_classmethod = True
                v.info = info
                dec = Decorator(func, [NameExpr('classmethod')], v)
                info.names[funcname] = SymbolTableNode(MDEF, dec)
            else:
                info.names[funcname] = SymbolTableNode(MDEF, func)

        add_method('_replace', ret=selftype,
                   args=[Argument(var, var.type, EllipsisExpr(), ARG_NAMED_OPT) for var in vars])

        def make_init_arg(var: Var) -> Argument:
            default = default_items.get(var.name(), None)
            kind = ARG_POS if default is None else ARG_OPT
            return Argument(var, var.type, default, kind)

        add_method('__init__', ret=NoneTyp(), name=info.name(),
                   args=[make_init_arg(var) for var in vars])
        add_method('_asdict', args=[], ret=ordereddictype)
        add_method('_make', ret=selftype, is_classmethod=True,
                   args=[Argument(Var('iterable', iterable_type), iterable_type, None, ARG_POS),
                         Argument(Var('new'), AnyType(), EllipsisExpr(), ARG_NAMED_OPT),
                         Argument(Var('len'), AnyType(), EllipsisExpr(), ARG_NAMED_OPT)])
        return info

    def process_typeddict_definition(self, s: AssignmentStmt) -> None:
        """Check if s defines a TypedDict; if yes, store the definition in symbol table."""
        if len(s.lvalues) != 1 or not isinstance(s.lvalues[0], NameExpr):
            return
        lvalue = s.lvalues[0]
        name = lvalue.name
        typed_dict = self.check_typeddict(s.rvalue, name)
        if typed_dict is None:
            return
        # Yes, it's a valid TypedDict definition. Add it to the symbol table.
        node = self.lookup(name, s)
        if node:
            node.kind = GDEF   # TODO locally defined TypedDict
            node.node = typed_dict

    def check_typeddict(self, node: Expression, var_name: str = None) -> Optional[TypeInfo]:
        """Check if a call defines a TypedDict.

        The optional var_name argument is the name of the variable to
        which this is assigned, if any.

        If it does, return the corresponding TypeInfo. Return None otherwise.

        If the definition is invalid but looks like a TypedDict,
        report errors but return (some) TypeInfo.
        """
        call, calleename, name = self.get_call(node, var_name)
        if calleename != 'mypy_extensions.TypedDict':
            return None
        items, types, ok = self.parse_typeddict_args(call)
        info = self.build_typeddict_typeinfo(name, items, types)
        if ok:
            self.semanalyzer.store_info(info, name)
            call.analyzed = TypedDictExpr(info)
            call.analyzed.set_line(call.line, call.column)
        return info

    def get_call(self, expr: Expression, var_name: str, *,
                 fresh: bool = True) -> Tuple[CallExpr, str, str]:
        (call, calleename, name) = None, '', ''
        if isinstance(expr, CallExpr):
            call = expr
            callee = call.callee
            if isinstance(callee, RefExpr):
                calleename = callee.fullname
                if len(call.args) > 0:
                    name = getattr(call.args[0], 'value', var_name)
                    if isinstance(name, str) and fresh:
                        if name != var_name or self.semanalyzer.is_func_scope():
                            # Give it a unique name derived from the line number.
                            name += '@' + str(call.line)
                    else:
                        name = var_name
        return (call, calleename, name)

    def parse_typeddict_args(self, call: CallExpr) -> Tuple[List[str], List[Type], bool]:
        # TODO: Share code with check_argument_count in checkexpr.py?
        args = call.args
        if len(args) < 2:
            return self.fail_typeddict_arg("Too few arguments for TypedDict()", call)
        if len(args) > 2:
            return self.fail_typeddict_arg("Too many arguments for TypedDict()", call)
        # TODO: Support keyword arguments
        if call.arg_kinds != [ARG_POS, ARG_POS]:
            return self.fail_typeddict_arg("Unexpected arguments to TypedDict()", call)
        if not isinstance(args[0], (StrExpr, BytesExpr, UnicodeExpr)):
            return self.fail_typeddict_arg(
                "TypedDict() expects a string literal as the first argument", call)
        if not isinstance(args[1], DictExpr):
            return self.fail_typeddict_arg(
                "TypedDict() expects a dictionary literal as the second argument", call)
        dictexpr = args[1]
        items, types, ok = self.parse_typeddict_fields_with_types(dictexpr.items)
        return items, types, ok

    def parse_typeddict_fields_with_types(self, dict_items: List[Tuple[Expression, Expression]],
                                          ) -> Tuple[List[str], List[Type], bool]:
        items = []  # type: List[str]
        types = []  # type: List[Type]
        for (field_name_expr, field_type_expr) in dict_items:
            if isinstance(field_name_expr, (StrExpr, BytesExpr, UnicodeExpr)):
                items.append(field_name_expr.value)
            else:
                return self.fail_typeddict_arg("Invalid TypedDict() field name", field_name_expr)
            try:
                type = expr_to_unanalyzed_type(field_type_expr)
            except TypeTranslationError:
                return self.fail_typeddict_arg('Invalid field type', field_type_expr)
            types.append(self.semanalyzer.anal_type(type))
        return items, types, True

    def fail_typeddict_arg(self, message: str,
                           context: Context) -> Tuple[List[str], List[Type], bool]:
        self.fail(message, context)
        return [], [], False

    def build_typeddict_typeinfo(self, name: str, items: List[str],
                                 types: List[Type]) -> TypeInfo:
        mapping_value_type = join.join_type_list(types)
        fallback = (self.named_type_or_none('typing.Mapping',
                                            [self.str_type(), mapping_value_type])
                    or self.object_type())

        info = self.basic_new_typeinfo(name, fallback)
        info.typeddict_type = TypedDictType(OrderedDict(zip(items, types)), fallback)

        return info

    def check_enum_call(self, node: Expression, var_name: str = None) -> Optional[TypeInfo]:
        """Check if a call defines an Enum.

        Example:

          A = enum.Enum('A', 'foo bar')

        is equivalent to:

          class A(enum.Enum):
              foo = 1
              bar = 2
        """
        call, calleename, name = self.get_call(node, var_name)
        if calleename not in ('enum.Enum', 'enum.IntEnum', 'enum.Flag', 'enum.IntFlag'):
            return None
        items, values, ok = self.parse_enum_call_args(call, calleename.split('.')[-1])
        info = self.build_enum_call_typeinfo(name, items, calleename)
        if ok:
            self.semanalyzer.store_info(info, name)
            call.analyzed = EnumCallExpr(info, items, values)
            call.analyzed.set_line(call.line, call.column)
        return info

    def build_enum_call_typeinfo(self, name: str, items: List[str], fullname: str) -> TypeInfo:
        base = self.named_type_or_none(fullname)
        assert base is not None
        info = self.basic_new_typeinfo(name, base)
        info.is_enum = True
        for item in items:
            var = Var(item)
            var.info = info
            var.is_property = True
            info.names[item] = SymbolTableNode(MDEF, var)
        return info

    def parse_enum_call_args(self, call: CallExpr,
                             class_name: str) -> Tuple[List[str],
                                                       List[Optional[Expression]], bool]:
        args = call.args
        if len(args) < 2:
            return self.fail_enum_call_arg("Too few arguments for %s()" % class_name, call)
        if len(args) > 2:
            return self.fail_enum_call_arg("Too many arguments for %s()" % class_name, call)
        if call.arg_kinds != [ARG_POS, ARG_POS]:
            return self.fail_enum_call_arg("Unexpected arguments to %s()" % class_name, call)
        if not isinstance(args[0], (StrExpr, UnicodeExpr)):
            return self.fail_enum_call_arg(
                "%s() expects a string literal as the first argument" % class_name, call)
        items = []
        values = []  # type: List[Optional[Expression]]
        if isinstance(args[1], (StrExpr, UnicodeExpr)):
            fields = args[1].value
            for field in fields.replace(',', ' ').split():
                items.append(field)
        elif isinstance(args[1], (TupleExpr, ListExpr)):
            seq_items = args[1].items
            if all(isinstance(seq_item, (StrExpr, UnicodeExpr)) for seq_item in seq_items):
                items = [cast(StrExpr, seq_item).value for seq_item in seq_items]
            elif all(isinstance(seq_item, (TupleExpr, ListExpr))
                     and len(seq_item.items) == 2
                     and isinstance(seq_item.items[0], (StrExpr, UnicodeExpr))
                     for seq_item in seq_items):
                for seq_item in seq_items:
                    assert isinstance(seq_item, (TupleExpr, ListExpr))
                    name, value = seq_item.items
                    assert isinstance(name, (StrExpr, UnicodeExpr))
                    items.append(name.value)
                    values.append(value)
            else:
                return self.fail_enum_call_arg(
                    "%s() with tuple or list expects strings or (name, value) pairs" %
                    class_name,
                    call)
        elif isinstance(args[1], DictExpr):
            for key, value in args[1].items:
                if not isinstance(key, (StrExpr, UnicodeExpr)):
                    return self.fail_enum_call_arg(
                        "%s() with dict literal requires string literals" % class_name, call)
                items.append(key.value)
                values.append(value)
        else:
            # TODO: Allow dict(x=1, y=2) as a substitute for {'x': 1, 'y': 2}?
            return self.fail_enum_call_arg(
                "%s() expects a string, tuple, list or dict literal as the second argument" %
                class_name,
                call)
        if len(items) == 0:
            return self.fail_enum_call_arg("%s() needs at least one item" % class_name, call)
        if not values:
            values = [None] * len(items)
        assert len(items) == len(values)
        return items, values, True

    def fail_enum_call_arg(self, message: str,
                           context: Context) -> Tuple[List[str],
                                                      List[Optional[Expression]], bool]:
        self.fail(message, context)
        return [], [], False


def is_typeddict(expr: Expression) -> bool:
    return (isinstance(expr, RefExpr) and isinstance(expr.node, TypeInfo) and
            expr.node.typeddict_type is not None)
