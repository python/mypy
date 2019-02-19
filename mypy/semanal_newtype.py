"""Semantic analysis of NewType definitions.

This is conceptually part of mypy.semanal (semantic analyzer pass 2).
"""

from typing import Tuple, Optional

from mypy.types import Type, Instance, CallableType, NoneTyp, TupleType, AnyType, TypeOfAny
from mypy.nodes import (
    AssignmentStmt, NewTypeExpr, CallExpr, NameExpr, RefExpr, Context, StrExpr, BytesExpr,
    UnicodeExpr, Block, FuncDef, Argument, TypeInfo, Var, SymbolTableNode, GDEF, MDEF, ARG_POS
)
from mypy.semanal_shared import SemanticAnalyzerInterface
from mypy.options import Options
from mypy.exprtotype import expr_to_unanalyzed_type, TypeTranslationError
from mypy.typeanal import check_for_explicit_any, has_any_from_unimported_type
from mypy.messages import MessageBuilder


class NewTypeAnalyzer:
    def __init__(self,
                 options: Options,
                 api: SemanticAnalyzerInterface,
                 msg: MessageBuilder) -> None:
        self.options = options
        self.api = api
        self.msg = msg

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
            newtype_class_info = self.build_newtype_typeinfo(name, old_type,
                                                             old_type.partial_fallback)
            newtype_class_info.tuple_type = old_type
        elif isinstance(old_type, Instance):
            if old_type.type.is_protocol:
                self.fail("NewType cannot be used with protocol classes", s)
            newtype_class_info = self.build_newtype_typeinfo(name, old_type, old_type)
        else:
            message = "Argument 2 to NewType(...) must be subclassable (got {})"
            self.fail(message.format(self.msg.format(old_type)), s)
            return

        check_for_explicit_any(old_type, self.options, self.api.is_typeshed_stub_file, self.msg,
                               context=s)

        if self.options.disallow_any_unimported and has_any_from_unimported_type(old_type):
            self.msg.unimported_type_becomes_any("Argument 2 to NewType(...)", old_type, s)

        # If so, add it to the symbol table.
        node = self.api.lookup(name, s)
        if node is None:
            self.fail("Could not find {} in current namespace".format(name), s)
            return
        # TODO: why does NewType work in local scopes despite always being of kind GDEF?
        node.kind = GDEF
        call.analyzed.info = node.node = newtype_class_info

    def analyze_newtype_declaration(self,
            s: AssignmentStmt) -> Tuple[Optional[str], Optional[CallExpr]]:
        """Return the NewType call expression if `s` is a newtype declaration or None otherwise."""
        name, call = None, None
        if (len(s.lvalues) == 1
                and isinstance(s.lvalues[0], NameExpr)
                and isinstance(s.rvalue, CallExpr)
                and isinstance(s.rvalue.callee, RefExpr)
                and s.rvalue.callee.fullname == 'typing.NewType'):
            lvalue = s.lvalues[0]
            name = s.lvalues[0].name
            if not lvalue.is_inferred_def:
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
        msg = "Argument 2 to NewType(...) must be a valid type"
        try:
            unanalyzed_type = expr_to_unanalyzed_type(args[1])
        except TypeTranslationError:
            self.fail(msg, context)
            return None

        # We want to use our custom error message (see above), so we suppress
        # the default error message for invalid types here.
        old_type = self.api.anal_type(unanalyzed_type, report_invalid_types=False)

        # The caller of this function assumes that if we return a Type, it's always
        # a valid one. So, we translate AnyTypes created from errors into None.
        if isinstance(old_type, AnyType) and old_type.is_from_error:
            self.fail(msg, context)
            return None

        return None if has_failed else old_type

    def build_newtype_typeinfo(self, name: str, old_type: Type, base_type: Instance) -> TypeInfo:
        info = self.api.basic_new_typeinfo(name, base_type)
        info.is_newtype = True

        # Add __init__ method
        args = [Argument(Var('self'), NoneTyp(), None, ARG_POS),
                self.make_argument('item', old_type)]
        signature = CallableType(
            arg_types=[Instance(info, []), old_type],
            arg_kinds=[arg.kind for arg in args],
            arg_names=['self', 'item'],
            ret_type=NoneTyp(),
            fallback=self.api.named_type('__builtins__.function'),
            name=name)
        init_func = FuncDef('__init__', args, Block([]), typ=signature)
        init_func.info = info
        init_func._fullname = self.api.qualified_name(name) + '.__init__'
        info.names['__init__'] = SymbolTableNode(MDEF, init_func)

        return info

    # Helpers

    def make_argument(self, name: str, type: Type) -> Argument:
        return Argument(Var(name), type, None, ARG_POS)

    def fail(self, msg: str, ctx: Context) -> None:
        self.api.fail(msg, ctx)
