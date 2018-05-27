from collections import OrderedDict
from typing import Dict, List, Optional, Set, Tuple, cast

from mypy.nodes import (
    ARG_OPT, ARG_POS, MDEF, Argument, AssignmentStmt, Block, CallExpr, Context,
    Decorator, Expression, JsonDict, NameExpr, SymbolTableNode, TempNode,
    TypeInfo, Var
)
from mypy.plugin import ClassDefContext
from mypy.plugins.common import _add_method, _get_decorator_bool_argument
from mypy.types import CallableType, NoneTyp, Type, TypeVarDef, TypeVarType
from mypy.typevars import fill_typevars

# The set of decorators that generate dataclasses.
dataclass_makers = {
    'dataclass',
    'dataclasses.dataclass',
}


class DataclassAttribute:
    def __init__(
            self,
            name: str,
            is_in_init: bool,
            has_default: bool,
            line: int, column: int,
    ) -> None:
        self.name = name
        self.is_in_init = is_in_init
        self.has_default = has_default
        self.line = line
        self.column = column

    def to_argument(self, info: TypeInfo) -> Argument:
        return Argument(
            variable=self.to_var(info),
            type_annotation=info[self.name].type,
            initializer=None,
            kind=ARG_OPT if self.has_default else ARG_POS,
        )

    def to_var(self, info: TypeInfo) -> Var:
        return Var(self.name, info[self.name].type)

    def serialize(self) -> JsonDict:
        return {
            'name': self.name,
            'is_in_init': self.is_in_init,
            'has_default': self.has_default,
            'line': self.line,
            'column': self.column,
        }

    @classmethod
    def deserialize(cls, data: JsonDict) -> 'DataclassAttribute':
        return cls(**data)


class DataclassTransformer:
    def __init__(self, ctx: ClassDefContext) -> None:
        self._ctx = ctx

    def transform(self) -> None:
        """Apply all the necessary transformations to the underlying
        dataclass so as to ensure it is fully type checked according
        to the rules in PEP 557.
        """
        ctx = self._ctx
        info = self._ctx.cls.info
        attributes = self.collect_attributes()
        decorator_arguments = {
            'init': _get_decorator_bool_argument(self._ctx, 'init', True),
            'eq': _get_decorator_bool_argument(self._ctx, 'eq', True),
            'order': _get_decorator_bool_argument(self._ctx, 'order', False),
            'frozen': _get_decorator_bool_argument(self._ctx, 'frozen', False),
        }

        if decorator_arguments['init']:
            _add_method(
                ctx,
                '__init__',
                args=[attr.to_argument(info) for attr in attributes if attr.is_in_init],
                return_type=NoneTyp(),
            )
            for stmt in self._ctx.cls.defs.body:
                # Fix up the types of classmethods since, by default,
                # they will be based on the parent class' init.
                if isinstance(stmt, Decorator) and stmt.func.is_class:
                    func_type = stmt.func.type
                    if isinstance(func_type, CallableType):
                        func_type.arg_types[0] = self._ctx.api.class_type(self._ctx.cls.info)

        # Add an eq method, but only if the class doesn't already have one.
        if decorator_arguments['eq'] and info.get('__eq__') is None:
            cmp_tvar_def = TypeVarDef('T', 'T', 1, [], ctx.api.named_type('__builtins__.object'))
            cmp_other_type = TypeVarType(cmp_tvar_def)
            cmp_return_type = ctx.api.named_type('__builtins__.bool')

            for method_name in ['__eq__', '__ne__']:
                _add_method(
                    ctx,
                    method_name,
                    args=[Argument(Var('other', cmp_other_type), cmp_other_type, None, ARG_POS)],
                    return_type=cmp_return_type,
                    self_type=cmp_other_type,
                    tvar_def=cmp_tvar_def,
                )

        # Add <,>,<=,>=, but only if the class has an eq method.
        if decorator_arguments['order']:
            if not decorator_arguments['eq']:
                ctx.api.fail('eq must be True if order is True', ctx.cls)

            order_tvar_def = TypeVarDef('T', 'T', 1, [], ctx.api.named_type('__builtins__.object'))
            order_other_type = TypeVarType(order_tvar_def)
            order_return_type = ctx.api.named_type('__builtins__.bool')
            order_args = [
                Argument(Var('other', order_other_type), order_other_type, None, ARG_POS)
            ]

            for method_name in ['__lt__', '__gt__', '__le__', '__ge__']:
                existing_method = info.get(method_name)
                if existing_method is not None:
                    assert existing_method.node
                    ctx.api.fail(
                        'You may not have a custom %s method when order=True' % method_name,
                        existing_method.node,
                    )

                _add_method(
                    ctx,
                    method_name,
                    args=order_args,
                    return_type=order_return_type,
                    self_type=order_other_type,
                    tvar_def=order_tvar_def,
                )

        if decorator_arguments['frozen']:
            self._freeze(attributes)

        info.metadata['dataclass'] = {
            'attributes': OrderedDict((attr.name, attr.serialize()) for attr in attributes),
            'frozen': decorator_arguments['frozen'],
        }

    def collect_attributes(self) -> List[DataclassAttribute]:
        """Collect all attributes declared in the dataclass and its parents.

        All assignments of the form

          a: SomeType
          b: SomeOtherType = ...

        are collected.
        """
        # First, collect attributes belonging to the current class.
        ctx = self._ctx
        cls = self._ctx.cls
        attrs = []  # type: List[DataclassAttribute]
        known_attrs = set()  # type: Set[str]
        for stmt in cls.defs.body:
            # Any assignment that doesn't use the new type declaration
            # syntax can be ignored out of hand.
            if not (isinstance(stmt, AssignmentStmt) and stmt.new_syntax):
                continue

            # a: int, b: str = 1, 'foo' is not supported syntax so we
            # don't have to worry about it.
            lhs = stmt.lvalues[0]
            if not isinstance(lhs, NameExpr):
                continue

            node = cls.info.names[lhs.name].node
            assert isinstance(node, Var)

            # x: ClassVar[int] is ignored by dataclasses.
            if node.is_classvar:
                continue

            # Treat the assignment as an instance-level assignment
            # even though it looks like a class-level assignment.
            node.is_initialized_in_class = False

            has_field_call, field_args = _collect_field_args(stmt.rvalue)

            try:
                # parse_bool returns an optional bool, so we corece it
                # to a bool here in order to appease the type checker.
                is_in_init = bool(ctx.api.parse_bool(field_args['init']))
            except KeyError:
                is_in_init = True

            has_default = False
            # Ensure that something like x: int = field() is rejected
            # after an attribute with a default.
            if has_field_call:
                has_default = 'default' in field_args or 'default_factory' in field_args

            # All other assignments are already type checked.
            elif not isinstance(stmt.rvalue, TempNode):
                has_default = True

            known_attrs.add(lhs.name)
            attrs.append(DataclassAttribute(
                name=lhs.name,
                is_in_init=is_in_init,
                has_default=has_default,
                line=stmt.line,
                column=stmt.column,
            ))

        # Next, collect attributes belonging to any class in the MRO
        # as long as those attributes weren't already collected.  This
        # makes it possible to overwrite attributes in subclasses.
        super_attrs = []
        for info in cls.info.mro[1:-1]:
            if 'dataclass' not in info.metadata:
                continue

            for name, data in info.metadata['dataclass']['attributes'].items():
                if name not in known_attrs:
                    attr = DataclassAttribute.deserialize(data)
                    known_attrs.add(name)
                    super_attrs.append(attr)

        all_attrs = super_attrs + attrs

        # Ensure that arguments without a default don't follow
        # arguments that have a default.
        found_default = False
        for attr in all_attrs:
            # If we find any attribute that is_in_init but that
            # doesn't have a default after one that does have one,
            # then that's an error.
            if found_default and attr.is_in_init and not attr.has_default:
                ctx.api.fail(
                    'Attributes without a default cannot follow attributes with one',
                    Context(line=attr.line, column=attr.column),
                )

            found_default = found_default or attr.has_default

        return all_attrs

    def _freeze(self, attributes: List[DataclassAttribute]) -> None:
        """Converts all attributes to @property methods in order to
        emulate frozen classes.
        """
        info = self._ctx.cls.info
        for attr in attributes:
            try:
                node = info.names[attr.name].node
                assert isinstance(node, Var)
                node.is_property = True
            except KeyError:
                var = attr.to_var(info)
                var.info = info
                var.is_property = True
                var._fullname = info.fullname() + '.' + var.name()
                info.names[var.name()] = SymbolTableNode(MDEF, var)


def dataclass_class_maker_callback(ctx: ClassDefContext) -> None:
    """Hooks into the class typechecking process to add support for dataclasses.
    """
    transformer = DataclassTransformer(ctx)
    transformer.transform()


def _collect_field_args(expr: Expression) -> Tuple[bool, Dict[str, Expression]]:
    """Returns a tuple where the first value represents whether or not
    the expression is a call to dataclass.field and the second is a
    dictionary of the keyword arguments that field() was called with.
    """
    if (
            isinstance(expr, CallExpr) and
            isinstance(expr.callee, NameExpr) and
            expr.callee.fullname == 'dataclasses.field'
    ):
        # field() only takes keyword arguments.
        args = {}
        for name, arg in zip(expr.arg_names, expr.args):
            assert name is not None
            args[name] = arg
        return True, args
    return False, {}
