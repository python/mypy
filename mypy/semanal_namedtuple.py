"""Semantic analysis of named tuple definitions.

This is conceptually part of mypy.semanal (semantic analyzer pass 2).
"""

from typing import Tuple, List, Dict, Mapping, Optional, Union, cast

from mypy.types import (
    Type, TupleType, NoneTyp, AnyType, TypeOfAny, TypeVarType, TypeVarDef, CallableType, TypeType
)
from mypy.semanal_shared import SemanticAnalyzerInterface, set_callable_name, PRIORITY_FALLBACKS
from mypy.nodes import (
    Var, EllipsisExpr, Argument, StrExpr, BytesExpr, UnicodeExpr, ExpressionStmt, NameExpr,
    AssignmentStmt, PassStmt, Decorator, FuncBase, ClassDef, Expression, RefExpr, TypeInfo,
    NamedTupleExpr, CallExpr, Context, TupleExpr, ListExpr, SymbolTableNode, FuncDef, Block,
    TempNode, ARG_POS, ARG_NAMED_OPT, ARG_OPT, MDEF, GDEF
)
from mypy.options import Options
from mypy.exprtotype import expr_to_unanalyzed_type, TypeTranslationError
from mypy import join

MYPY = False
if MYPY:
    from typing_extensions import Final

# Matches "_prohibited" in typing.py, but adds __annotations__, which works at runtime but can't
# easily be supported in a static checker.
NAMEDTUPLE_PROHIBITED_NAMES = ('__new__', '__init__', '__slots__', '__getnewargs__',
                               '_fields', '_field_defaults', '_field_types',
                               '_make', '_replace', '_asdict', '_source',
                               '__annotations__')  # type: Final

NAMEDTUP_CLASS_ERROR = ('Invalid statement in NamedTuple definition; '
                        'expected "field_name: field_type [= default]"')  # type: Final


class NamedTupleAnalyzer:
    def __init__(self, options: Options, api: SemanticAnalyzerInterface) -> None:
        self.options = options
        self.api = api

    def analyze_namedtuple_classdef(self, defn: ClassDef) -> Optional[TypeInfo]:
        # special case for NamedTuple
        for base_expr in defn.base_type_exprs:
            if isinstance(base_expr, RefExpr):
                self.api.accept(base_expr)
                if base_expr.fullname == 'typing.NamedTuple':
                    node = self.api.lookup(defn.name, defn)
                    if node is not None:
                        node.kind = GDEF  # TODO in process_namedtuple_definition also applies here
                        items, types, default_items = self.check_namedtuple_classdef(defn)
                        info = self.build_namedtuple_typeinfo(
                            defn.name, items, types, default_items)
                        node.node = info
                        defn.info.replaced = info
                        defn.info = info
                        defn.analyzed = NamedTupleExpr(info, is_typed=True)
                        defn.analyzed.line = defn.line
                        defn.analyzed.column = defn.column
                        return info
        return None

    def check_namedtuple_classdef(
            self, defn: ClassDef) -> Tuple[List[str], List[Type], Dict[str, Expression]]:
        if self.options.python_version < (3, 6):
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
                if (isinstance(stmt, PassStmt) or
                    (isinstance(stmt, ExpressionStmt) and
                        isinstance(stmt.expr, EllipsisExpr))):
                    continue
                # Also allow methods, including decorated ones.
                if isinstance(stmt, (Decorator, FuncBase)):
                    continue
                # And docstrings.
                if (isinstance(stmt, ExpressionStmt) and
                        isinstance(stmt.expr, StrExpr)):
                    continue
                self.fail(NAMEDTUP_CLASS_ERROR, stmt)
            elif len(stmt.lvalues) > 1 or not isinstance(stmt.lvalues[0], NameExpr):
                # An assignment, but an invalid one.
                self.fail(NAMEDTUP_CLASS_ERROR, stmt)
            else:
                # Append name and type in this case...
                name = stmt.lvalues[0].name
                items.append(name)
                types.append(AnyType(TypeOfAny.unannotated)
                             if stmt.type is None
                             else self.api.anal_type(stmt.type))
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

    def process_namedtuple_definition(self, s: AssignmentStmt, is_func_scope: bool) -> None:
        """Check if s defines a namedtuple; if yes, store the definition in symbol table."""
        if len(s.lvalues) != 1 or not isinstance(s.lvalues[0], NameExpr):
            return
        lvalue = s.lvalues[0]
        name = lvalue.name
        named_tuple = self.check_namedtuple(s.rvalue, name, is_func_scope)
        if named_tuple is None:
            return
        # Yes, it's a valid namedtuple definition. Add it to the symbol table.
        node = self.api.lookup(name, s)
        assert node is not None
        node.kind = GDEF   # TODO locally defined namedtuple
        node.node = named_tuple

    def check_namedtuple(self,
                         node: Expression,
                         var_name: Optional[str],
                         is_func_scope: bool) -> Optional[TypeInfo]:
        """Check if a call defines a namedtuple.

        The optional var_name argument is the name of the variable to
        which this is assigned, if any.

        If it does, return the corresponding TypeInfo. Return None otherwise.

        If the definition is invalid but looks like a namedtuple,
        report errors but return (some) TypeInfo.
        """
        if not isinstance(node, CallExpr):
            return None
        call = node
        callee = call.callee
        if not isinstance(callee, RefExpr):
            return None
        fullname = callee.fullname
        if fullname == 'collections.namedtuple':
            is_typed = False
        elif fullname == 'typing.NamedTuple':
            is_typed = True
        else:
            return None
        items, types, defaults, ok = self.parse_namedtuple_args(call, fullname)
        if not ok:
            # Error. Construct dummy return value.
            if var_name:
                name = var_name
            else:
                name = 'namedtuple@' + str(call.line)
            info = self.build_namedtuple_typeinfo(name, [], [], {})
            self.store_namedtuple_info(info, name, call, is_typed)
            return info
        name = cast(Union[StrExpr, BytesExpr, UnicodeExpr], call.args[0]).value
        if name != var_name or is_func_scope:
            # Give it a unique name derived from the line number.
            name += '@' + str(call.line)
        if len(defaults) > 0:
            default_items = {
                arg_name: default
                for arg_name, default in zip(items[-len(defaults):], defaults)
            }
        else:
            default_items = {}
        info = self.build_namedtuple_typeinfo(name, items, types, default_items)
        # Store it as a global just in case it would remain anonymous.
        # (Or in the nearest class if there is one.)
        self.store_namedtuple_info(info, name, call, is_typed)
        return info

    def store_namedtuple_info(self, info: TypeInfo, name: str,
                              call: CallExpr, is_typed: bool) -> None:
        stnode = SymbolTableNode(GDEF, info)
        self.api.add_symbol_table_node(name, stnode)
        call.analyzed = NamedTupleExpr(info, is_typed=is_typed)
        call.analyzed.set_line(call.line, call.column)

    def parse_namedtuple_args(self, call: CallExpr, fullname: str
                              ) -> Tuple[List[str], List[Type], List[Expression], bool]:
        """Parse a namedtuple() call into data needed to construct a type.

        Returns a 4-tuple:
        - List of argument names
        - List of argument types
        - Number of arguments that have a default value
        - Whether the definition typechecked.

        """
        # TODO: Share code with check_argument_count in checkexpr.py?
        args = call.args
        if len(args) < 2:
            return self.fail_namedtuple_arg("Too few arguments for namedtuple()", call)
        defaults = []  # type: List[Expression]
        if len(args) > 2:
            # Typed namedtuple doesn't support additional arguments.
            if fullname == 'typing.NamedTuple':
                return self.fail_namedtuple_arg("Too many arguments for NamedTuple()", call)
            for i, arg_name in enumerate(call.arg_names[2:], 2):
                if arg_name == 'defaults':
                    arg = args[i]
                    # We don't care what the values are, as long as the argument is an iterable
                    # and we can count how many defaults there are.
                    if isinstance(arg, (ListExpr, TupleExpr)):
                        defaults = list(arg.items)
                    else:
                        self.fail(
                            "List or tuple literal expected as the defaults argument to "
                            "namedtuple()",
                            arg
                        )
                    break
        if call.arg_kinds[:2] != [ARG_POS, ARG_POS]:
            return self.fail_namedtuple_arg("Unexpected arguments to namedtuple()", call)
        if not isinstance(args[0], (StrExpr, BytesExpr, UnicodeExpr)):
            return self.fail_namedtuple_arg(
                "namedtuple() expects a string literal as the first argument", call)
        types = []  # type: List[Type]
        ok = True
        if not isinstance(args[1], (ListExpr, TupleExpr)):
            if (fullname == 'collections.namedtuple'
                    and isinstance(args[1], (StrExpr, BytesExpr, UnicodeExpr))):
                str_expr = args[1]
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
                items = [cast(Union[StrExpr, BytesExpr, UnicodeExpr], item).value
                         for item in listexpr.items]
            else:
                # The fields argument contains (name, type) tuples.
                items, types, _, ok = self.parse_namedtuple_fields_with_types(listexpr.items, call)
        if not types:
            types = [AnyType(TypeOfAny.unannotated) for _ in items]
        underscore = [item for item in items if item.startswith('_')]
        if underscore:
            self.fail("namedtuple() field names cannot start with an underscore: "
                      + ', '.join(underscore), call)
        if len(defaults) > len(items):
            self.fail("Too many defaults given in call to namedtuple()", call)
            defaults = defaults[:len(items)]
        return items, types, defaults, ok

    def parse_namedtuple_fields_with_types(self, nodes: List[Expression], context: Context
                                           ) -> Tuple[List[str], List[Type], List[Expression],
                                                      bool]:
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
                types.append(self.api.anal_type(type))
            else:
                return self.fail_namedtuple_arg("Tuple expected as NamedTuple() field", item)
        return items, types, [], True

    def fail_namedtuple_arg(self, message: str, context: Context
                            ) -> Tuple[List[str], List[Type], List[Expression], bool]:
        self.fail(message, context)
        return [], [], [], False

    def build_namedtuple_typeinfo(self, name: str, items: List[str], types: List[Type],
                                  default_items: Mapping[str, Expression]) -> TypeInfo:
        strtype = self.api.named_type('__builtins__.str')
        implicit_any = AnyType(TypeOfAny.special_form)
        basetuple_type = self.api.named_type('__builtins__.tuple', [implicit_any])
        dictype = (self.api.named_type_or_none('builtins.dict', [strtype, implicit_any])
                   or self.api.named_type('__builtins__.object'))
        # Actual signature should return OrderedDict[str, Union[types]]
        ordereddictype = (self.api.named_type_or_none('builtins.dict', [strtype, implicit_any])
                          or self.api.named_type('__builtins__.object'))
        fallback = self.api.named_type('__builtins__.tuple', [implicit_any])
        # Note: actual signature should accept an invariant version of Iterable[UnionType[types]].
        # but it can't be expressed. 'new' and 'len' should be callable types.
        iterable_type = self.api.named_type_or_none('typing.Iterable', [implicit_any])
        function_type = self.api.named_type('__builtins__.function')

        info = self.api.basic_new_typeinfo(name, fallback)
        info.is_named_tuple = True
        info.tuple_type = TupleType(types, fallback)

        def patch() -> None:
            # Calculate the correct value type for the fallback tuple.
            assert info.tuple_type, "TupleType type deleted before calling the patch"
            fallback.args[0] = join.join_type_list(list(info.tuple_type.items))

        # We can't calculate the complete fallback type until after semantic
        # analysis, since otherwise MROs might be incomplete. Postpone a callback
        # function that patches the fallback.
        self.api.schedule_patch(PRIORITY_FALLBACKS, patch)

        def add_field(var: Var, is_initialized_in_class: bool = False,
                      is_property: bool = False) -> None:
            var.info = info
            var.is_initialized_in_class = is_initialized_in_class
            var.is_property = is_property
            var._fullname = '%s.%s' % (info.fullname(), var.name())
            info.names[var.name()] = SymbolTableNode(MDEF, var)

        vars = [Var(item, typ) for item, typ in zip(items, types)]
        for var in vars:
            add_field(var, is_property=True)

        tuple_of_strings = TupleType([strtype for _ in items], basetuple_type)
        add_field(Var('_fields', tuple_of_strings), is_initialized_in_class=True)
        add_field(Var('_field_types', dictype), is_initialized_in_class=True)
        add_field(Var('_field_defaults', dictype), is_initialized_in_class=True)
        add_field(Var('_source', strtype), is_initialized_in_class=True)
        add_field(Var('__annotations__', ordereddictype), is_initialized_in_class=True)
        add_field(Var('__doc__', strtype), is_initialized_in_class=True)

        tvd = TypeVarDef('NT', 'NT', -1, [], info.tuple_type)
        selftype = TypeVarType(tvd)

        def add_method(funcname: str,
                       ret: Type,
                       args: List[Argument],
                       name: Optional[str] = None,
                       is_classmethod: bool = False,
                       is_new: bool = False,
                       ) -> None:
            if is_classmethod or is_new:
                first = [Argument(Var('cls'), TypeType.make_normalized(selftype), None, ARG_POS)]
            else:
                first = [Argument(Var('self'), selftype, None, ARG_POS)]
            args = first + args

            types = [arg.type_annotation for arg in args]
            items = [arg.variable.name() for arg in args]
            arg_kinds = [arg.kind for arg in args]
            assert None not in types
            signature = CallableType(cast(List[Type], types), arg_kinds, items, ret,
                                     function_type)
            signature.variables = [tvd]
            func = FuncDef(funcname, args, Block([]))
            func.info = info
            func.is_class = is_classmethod
            func.type = set_callable_name(signature, func)
            func._fullname = info.fullname() + '.' + funcname
            if is_classmethod:
                v = Var(funcname, func.type)
                v.is_classmethod = True
                v.info = info
                v._fullname = func._fullname
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

        add_method('__new__', ret=selftype, name=info.name(),
                   args=[make_init_arg(var) for var in vars],
                   is_new=True)
        add_method('_asdict', args=[], ret=ordereddictype)
        special_form_any = AnyType(TypeOfAny.special_form)
        add_method('_make', ret=selftype, is_classmethod=True,
                   args=[Argument(Var('iterable', iterable_type), iterable_type, None, ARG_POS),
                         Argument(Var('new'), special_form_any, EllipsisExpr(), ARG_NAMED_OPT),
                         Argument(Var('len'), special_form_any, EllipsisExpr(), ARG_NAMED_OPT)])
        return info

    # Helpers

    def fail(self, msg: str, ctx: Context) -> None:
        self.api.fail(msg, ctx)
