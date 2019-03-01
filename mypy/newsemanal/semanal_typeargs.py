"""Verify that type arguments like 'int' C[int] are valid.

This must happen after semantic analysis since there can be placeholder
types until the end of semantic analysis, and these break various type
operations, including subtype checks.
"""

from typing import List

from mypy.nodes import TypeInfo, Context, MypyFile, FuncItem, ClassDef, Block, OverloadedFuncDef
from mypy.types import Type, Instance, TypeVarType, AnyType
from mypy.mixedtraverser import MixedTraverserVisitor
from mypy.subtypes import is_subtype
from mypy.sametypes import is_same_type
from mypy.errors import Errors
from mypy.scope import Scope
from mypy import message_registry


class TypeArgumentAnalyzer(MixedTraverserVisitor):
    def __init__(self, errors: Errors) -> None:
        self.errors = errors
        self.scope = Scope()
        # Should we also analyze function definitions, or only module top-levels?
        self.recurse_into_functions = True

    def visit_mypy_file(self, o: MypyFile) -> None:
        self.errors.set_file(o.path, o.fullname(), scope=self.scope)
        self.scope.enter_file(o.fullname())
        super().visit_mypy_file(o)
        self.scope.leave()

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

    def visit_instance(self, t: Instance) -> None:
        # Type argument counts were checked in the main semantic analyzer pass. We assume
        # that the counts are correct here.
        info = t.type
        for (i, arg), tvar in zip(enumerate(t.args), info.defn.type_vars):
            if tvar.values:
                if isinstance(arg, TypeVarType):
                    arg_values = arg.values
                    if not arg_values:
                        self.fail('Type variable "{}" not valid as type '
                                  'argument value for "{}"'.format(
                                      arg.name, info.name()), t)
                        continue
                else:
                    arg_values = [arg]
                self.check_type_var_values(info, arg_values, tvar.name, tvar.values, i + 1, t)
            if not is_subtype(arg, tvar.upper_bound):
                self.fail('Type argument "{}" of "{}" must be '
                          'a subtype of "{}"'.format(
                              arg, info.name(), tvar.upper_bound), t)
        super().visit_instance(t)

    def check_type_var_values(self, type: TypeInfo, actuals: List[Type], arg_name: str,
                              valids: List[Type], arg_number: int, context: Context) -> None:
        for actual in actuals:
            if (not isinstance(actual, AnyType) and
                    not any(is_same_type(actual, value)
                            for value in valids)):
                if len(actuals) > 1 or not isinstance(actual, Instance):
                    self.fail('Invalid type argument value for "{}"'.format(
                        type.name()), context)
                else:
                    class_name = '"{}"'.format(type.name())
                    actual_type_name = '"{}"'.format(actual.type.name())
                    self.fail(message_registry.INCOMPATIBLE_TYPEVAR_VALUE.format(
                        arg_name, class_name, actual_type_name), context)

    def fail(self, msg: str, context: Context) -> None:
        self.errors.report(context.get_line(), context.get_column(), msg)
