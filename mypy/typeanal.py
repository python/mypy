"""Semantic analysis of types"""

from collections import OrderedDict
from typing import Callable, List, Optional, Set, Tuple, Iterator, TypeVar, Iterable, Dict

from itertools import chain

from contextlib import contextmanager

import itertools

from mypy.messages import MessageBuilder
from mypy.options import Options
from mypy.types import (
    Type, UnboundType, TypeVarType, TupleType, TypedDictType, UnionType, Instance, AnyType,
    CallableType, NoneTyp, DeletedType, TypeList, TypeVarDef, TypeVisitor, SyntheticTypeVisitor,
    StarType, PartialType, EllipsisType, UninhabitedType, TypeType, get_typ_args, set_typ_args,
    CallableArgument, get_type_vars, TypeQuery, union_items, TypeOfAny, ForwardRef, Overloaded,
    LiteralType, RawExpressionType,
)

from mypy.nodes import (
    UNBOUND_IMPORTED, TypeInfo, Context, SymbolTableNode, Var, Expression,
    IndexExpr, RefExpr, nongen_builtins, check_arg_names, check_arg_kinds, ARG_POS, ARG_NAMED,
    ARG_OPT, ARG_NAMED_OPT, ARG_STAR, ARG_STAR2, TypeVarExpr, FuncDef, CallExpr, NameExpr,
    Decorator, ImportedName, TypeAlias, MypyFile
)
from mypy.tvar_scope import TypeVarScope
from mypy.exprtotype import expr_to_unanalyzed_type, TypeTranslationError
from mypy.plugin import Plugin, TypeAnalyzerPluginInterface, AnalyzeTypeContext
from mypy.semanal_shared import SemanticAnalyzerCoreInterface
from mypy import nodes, message_registry

MYPY = False
if MYPY:
    from typing_extensions import Final

T = TypeVar('T')


type_constructors = {
    'typing.Callable',
    'typing.Optional',
    'typing.Tuple',
    'typing.Type',
    'typing.Union',
    'typing.Literal',
    'typing_extensions.Literal',
}  # type: Final

ARG_KINDS_BY_CONSTRUCTOR = {
    'mypy_extensions.Arg': ARG_POS,
    'mypy_extensions.DefaultArg': ARG_OPT,
    'mypy_extensions.NamedArg': ARG_NAMED,
    'mypy_extensions.DefaultNamedArg': ARG_NAMED_OPT,
    'mypy_extensions.VarArg': ARG_STAR,
    'mypy_extensions.KwArg': ARG_STAR2,
}  # type: Final


def analyze_type_alias(node: Expression,
                       api: SemanticAnalyzerCoreInterface,
                       tvar_scope: TypeVarScope,
                       plugin: Plugin,
                       options: Options,
                       is_typeshed_stub: bool,
                       allow_unnormalized: bool = False,
                       in_dynamic_func: bool = False,
                       global_scope: bool = True) -> Optional[Tuple[Type, Set[str]]]:
    """Analyze r.h.s. of a (potential) type alias definition.

    If `node` is valid as a type alias rvalue, return the resulting type and a set of
    full names of type aliases it depends on (directly or indirectly).
    Return None otherwise. 'node' must have been semantically analyzed.
    """
    # Quickly return None if the expression doesn't look like a type. Note
    # that we don't support straight string literals as type aliases
    # (only string literals within index expressions).
    if isinstance(node, RefExpr):
        # Note that this misses the case where someone tried to use a
        # class-referenced type variable as a type alias.  It's easier to catch
        # that one in checkmember.py
        if isinstance(node.node, TypeVarExpr):
            api.fail('Type variable "{}" is invalid as target for type alias'.format(
                node.fullname), node)
            return None
        if not (isinstance(node.node, TypeInfo) or
                node.fullname in ('typing.Any', 'typing.Tuple', 'typing.Callable') or
                isinstance(node.node, TypeAlias)):
            return None
    elif isinstance(node, IndexExpr):
        base = node.base
        if isinstance(base, RefExpr):
            if not (isinstance(base.node, TypeInfo) or
                    base.fullname in type_constructors or
                    isinstance(base.node, TypeAlias)):
                return None
            # Enums can't be generic, and without this check we may incorrectly interpret indexing
            # an Enum class as creating a type alias.
            if isinstance(base.node, TypeInfo) and base.node.is_enum:
                return None
        else:
            return None
    elif isinstance(node, CallExpr):
        if (isinstance(node.callee, NameExpr) and len(node.args) == 1 and
                isinstance(node.args[0], NameExpr)):
            call = api.lookup_qualified(node.callee.name, node.callee)
            arg = api.lookup_qualified(node.args[0].name, node.args[0])
            if (call is not None and call.node and call.node.fullname() == 'builtins.type' and
                    arg is not None and arg.node and arg.node.fullname() == 'builtins.None'):
                return NoneTyp(), set()
            return None
        return None
    else:
        return None

    # It's a type alias (though it may be an invalid one).
    try:
        type = expr_to_unanalyzed_type(node)
    except TypeTranslationError:
        api.fail('Invalid type alias', node)
        return None
    analyzer = TypeAnalyser(api, tvar_scope, plugin, options, is_typeshed_stub,
                            allow_unnormalized=allow_unnormalized, defining_alias=True)
    analyzer.in_dynamic_func = in_dynamic_func
    analyzer.global_scope = global_scope
    res = type.accept(analyzer)
    return res, analyzer.aliases_used


def no_subscript_builtin_alias(name: str, propose_alt: bool = True) -> str:
    msg = '"{}" is not subscriptable'.format(name.split('.')[-1])
    replacement = nongen_builtins[name]
    if replacement and propose_alt:
        msg += ', use "{}" instead'.format(replacement)
    return msg


class TypeAnalyser(SyntheticTypeVisitor[Type], TypeAnalyzerPluginInterface):
    """Semantic analyzer for types (semantic analysis pass 2).

    Converts unbound types into bound types.
    """

    # Is this called from an untyped function definition?
    in_dynamic_func = False  # type: bool
    # Is this called from global scope?
    global_scope = True  # type: bool

    def __init__(self,
                 api: SemanticAnalyzerCoreInterface,
                 tvar_scope: Optional[TypeVarScope],
                 plugin: Plugin,
                 options: Options,
                 is_typeshed_stub: bool, *,
                 defining_alias: bool = False,
                 allow_tuple_literal: bool = False,
                 allow_unnormalized: bool = False,
                 allow_unbound_tvars: bool = False,
                 report_invalid_types: bool = True,
                 third_pass: bool = False) -> None:
        self.api = api
        self.lookup = api.lookup_qualified
        self.lookup_fqn_func = api.lookup_fully_qualified
        self.fail_func = api.fail
        self.note_func = api.note
        self.tvar_scope = tvar_scope
        # Are we analysing a type alias definition rvalue?
        self.defining_alias = defining_alias
        self.allow_tuple_literal = allow_tuple_literal
        # Positive if we are analyzing arguments of another (outer) type
        self.nesting_level = 0
        # Should we allow unnormalized types like `list[int]`
        # (currently allowed in stubs)?
        self.allow_unnormalized = allow_unnormalized
        # Should we accept unbound type variables (always OK in aliases)?
        self.allow_unbound_tvars = allow_unbound_tvars or defining_alias
        # Should we report an error whenever we encounter a RawExpressionType outside
        # of a Literal context: e.g. whenever we encounter an invalid type? Normally,
        # we want to report an error, but the caller may want to do more specialized
        # error handling.
        self.report_invalid_types = report_invalid_types
        self.plugin = plugin
        self.options = options
        self.is_typeshed_stub = is_typeshed_stub
        self.third_pass = third_pass
        # Names of type aliases encountered while analysing a type will be collected here.
        self.aliases_used = set()  # type: Set[str]

    def visit_unbound_type(self, t: UnboundType) -> Type:
        typ = self.visit_unbound_type_nonoptional(t)
        if t.optional:
            # We don't need to worry about double-wrapping Optionals or
            # wrapping Anys: Union simplification will take care of that.
            return make_optional_type(typ)
        return typ

    def visit_unbound_type_nonoptional(self, t: UnboundType) -> Type:
        sym = self.lookup(t.name, t, suppress_errors=self.third_pass)
        if '.' in t.name:
            # Handle indirect references to imported names.
            #
            # TODO: Do this for module-local references as well and remove ImportedName
            #    type check below.
            sym = self.api.dereference_module_cross_ref(sym)
        if sym is not None:
            node = sym.node
            if isinstance(node, ImportedName):
                # Forward reference to an imported name that hasn't been processed yet.
                # To maintain backward compatibility, these get translated to Any.
                #
                # TODO: Remove this special case.
                return AnyType(TypeOfAny.implementation_artifact)
            if node is None:
                # UNBOUND_IMPORTED can happen if an unknown name was imported.
                if sym.kind != UNBOUND_IMPORTED:
                    self.fail('Internal error (node is None, kind={})'.format(sym.kind), t)
                return AnyType(TypeOfAny.special_form)
            fullname = node.fullname()
            hook = self.plugin.get_type_analyze_hook(fullname)
            if hook is not None:
                return hook(AnalyzeTypeContext(t, t, self))
            if (fullname in nongen_builtins
                    and t.args and
                    not self.allow_unnormalized):
                self.fail(no_subscript_builtin_alias(fullname,
                                                     propose_alt=not self.defining_alias), t)
            if self.tvar_scope is not None:
                tvar_def = self.tvar_scope.get_binding(sym)
            else:
                tvar_def = None
            if isinstance(sym.node, TypeVarExpr) and tvar_def is not None and self.defining_alias:
                self.fail('Can\'t use bound type variable "{}"'
                          ' to define generic alias'.format(t.name), t)
                return AnyType(TypeOfAny.from_error)
            if isinstance(sym.node, TypeVarExpr) and tvar_def is not None:
                if len(t.args) > 0:
                    self.fail('Type variable "{}" used with arguments'.format(t.name), t)
                return TypeVarType(tvar_def, t.line)
            special = self.try_analyze_special_unbound_type(t, fullname)
            if special is not None:
                return special
            if isinstance(node, TypeAlias):
                self.aliases_used.add(fullname)
                all_vars = node.alias_tvars
                target = node.target
                an_args = self.anal_array(t.args)
                return expand_type_alias(target, all_vars, an_args, self.fail, node.no_args, t)
            elif isinstance(node, TypeInfo):
                return self.analyze_unbound_type_with_type_info(t, node)
            else:
                return self.analyze_unbound_type_without_type_info(t, sym)
        else:  # sym is None
            if self.third_pass:
                self.fail('Invalid type "{}"'.format(t.name), t)
                return AnyType(TypeOfAny.from_error)
            return AnyType(TypeOfAny.special_form)

    def try_analyze_special_unbound_type(self, t: UnboundType, fullname: str) -> Optional[Type]:
        """Bind special type that is recognized through magic name such as 'typing.Any'.

        Return the bound type if successful, and return None if the type is a normal type.
        """
        if fullname == 'builtins.None':
            return NoneTyp()
        elif fullname == 'typing.Any' or fullname == 'builtins.Any':
            return AnyType(TypeOfAny.explicit)
        elif fullname in ('typing.Final', 'typing_extensions.Final'):
            self.fail("Final can be only used as an outermost qualifier"
                      " in a variable annotation", t)
            return AnyType(TypeOfAny.from_error)
        elif fullname == 'typing.Tuple':
            if len(t.args) == 0 and not t.empty_tuple_index:
                # Bare 'Tuple' is same as 'tuple'
                if self.options.disallow_any_generics and not self.is_typeshed_stub:
                    self.fail(message_registry.BARE_GENERIC, t)
                return self.named_type('builtins.tuple', line=t.line, column=t.column)
            if len(t.args) == 2 and isinstance(t.args[1], EllipsisType):
                # Tuple[T, ...] (uniform, variable-length tuple)
                instance = self.named_type('builtins.tuple', [self.anal_type(t.args[0])])
                instance.line = t.line
                return instance
            return self.tuple_type(self.anal_array(t.args))
        elif fullname == 'typing.Union':
            items = self.anal_array(t.args)
            return UnionType.make_union(items)
        elif fullname == 'typing.Optional':
            if len(t.args) != 1:
                self.fail('Optional[...] must have exactly one type argument', t)
                return AnyType(TypeOfAny.from_error)
            item = self.anal_type(t.args[0])
            return make_optional_type(item)
        elif fullname == 'typing.Callable':
            return self.analyze_callable_type(t)
        elif fullname == 'typing.Type':
            if len(t.args) == 0:
                any_type = AnyType(TypeOfAny.from_omitted_generics,
                                   line=t.line, column=t.column)
                return TypeType(any_type, line=t.line, column=t.column)
            if len(t.args) != 1:
                self.fail('Type[...] must have exactly one type argument', t)
            item = self.anal_type(t.args[0])
            return TypeType.make_normalized(item, line=t.line)
        elif fullname == 'typing.ClassVar':
            if self.nesting_level > 0:
                self.fail('Invalid type: ClassVar nested inside other type', t)
            if len(t.args) == 0:
                return AnyType(TypeOfAny.from_omitted_generics, line=t.line, column=t.column)
            if len(t.args) != 1:
                self.fail('ClassVar[...] must have at most one type argument', t)
                return AnyType(TypeOfAny.from_error)
            item = self.anal_type(t.args[0])
            if isinstance(item, TypeVarType) or get_type_vars(item):
                self.fail('Invalid type: ClassVar cannot be generic', t)
                return AnyType(TypeOfAny.from_error)
            return item
        elif fullname in ('mypy_extensions.NoReturn', 'typing.NoReturn'):
            return UninhabitedType(is_noreturn=True)
        elif fullname in ('typing_extensions.Literal', 'typing.Literal'):
            return self.analyze_literal_type(t)
        return None

    def analyze_unbound_type_with_type_info(self, t: UnboundType, info: TypeInfo) -> Type:
        """Bind unbound type when were able to find target TypeInfo.

        This handles simple cases like 'int', 'modname.UserClass[str]', etc.
        """
        if len(t.args) > 0 and info.fullname() == 'builtins.tuple':
            fallback = Instance(info, [AnyType(TypeOfAny.special_form)], t.line)
            return TupleType(self.anal_array(t.args), fallback, t.line)
        # Analyze arguments and (usually) construct Instance type. The
        # number of type arguments and their values are
        # checked only later, since we do not always know the
        # valid count at this point. Thus we may construct an
        # Instance with an invalid number of type arguments.
        instance = Instance(info, self.anal_array(t.args), t.line, t.column)
        if not t.args and self.options.disallow_any_generics and not self.defining_alias:
            # We report/patch invalid built-in instances already during second pass.
            # This is done to avoid storing additional state on instances.
            # All other (including user defined) generics will be patched/reported
            # in the third pass.
            if not self.is_typeshed_stub and info.fullname() in nongen_builtins:
                alternative = nongen_builtins[info.fullname()]
                self.fail(message_registry.IMPLICIT_GENERIC_ANY_BUILTIN.format(alternative), t)
                any_type = AnyType(TypeOfAny.from_error, line=t.line)
            else:
                any_type = AnyType(TypeOfAny.from_omitted_generics, line=t.line)
            instance.args = [any_type] * len(info.type_vars)

        tup = info.tuple_type
        if tup is not None:
            # The class has a Tuple[...] base class so it will be
            # represented as a tuple type.
            if t.args:
                self.fail('Generic tuple types not supported', t)
                return AnyType(TypeOfAny.from_error)
            return tup.copy_modified(items=self.anal_array(tup.items),
                                     fallback=instance)
        td = info.typeddict_type
        if td is not None:
            # The class has a TypedDict[...] base class so it will be
            # represented as a typeddict type.
            if t.args:
                self.fail('Generic TypedDict types not supported', t)
                return AnyType(TypeOfAny.from_error)
            # Create a named TypedDictType
            return td.copy_modified(item_types=self.anal_array(list(td.items.values())),
                                    fallback=instance)
        return instance

    def analyze_unbound_type_without_type_info(self, t: UnboundType, sym: SymbolTableNode) -> Type:
        """Figure out what an unbound type that doesn't refer to a TypeInfo node means.

        This is something unusual. We try our best to find out what it is.
        """
        name = sym.fullname
        if name is None:
            assert sym.node is not None
            name = sym.node.name()
        # Option 1:
        # Something with an Any type -- make it an alias for Any in a type
        # context. This is slightly problematic as it allows using the type 'Any'
        # as a base class -- however, this will fail soon at runtime so the problem
        # is pretty minor.
        if isinstance(sym.node, Var) and isinstance(sym.node.type, AnyType):
            return AnyType(TypeOfAny.from_unimported_type,
                           missing_import_name=sym.node.type.missing_import_name)
        # Option 2:
        # Unbound type variable. Currently these may be still valid,
        # for example when defining a generic type alias.
        unbound_tvar = (isinstance(sym.node, TypeVarExpr) and
                        (not self.tvar_scope or self.tvar_scope.get_binding(sym) is None))
        if self.allow_unbound_tvars and unbound_tvar and not self.third_pass:
            return t
        # Option 3:
        # If it is not something clearly bad (like a known function, variable,
        # type variable, or module), and it is still not too late, we try deferring
        # this type using a forward reference wrapper. It will be revisited in
        # the third pass.
        allow_forward_ref = not (self.third_pass or
                                 isinstance(sym.node, (FuncDef, Decorator, MypyFile,
                                                       TypeVarExpr)) or
                                 (isinstance(sym.node, Var) and sym.node.is_ready))
        if allow_forward_ref:
            # We currently can't support subscripted forward refs in functions;
            # see https://github.com/python/mypy/pull/3952#discussion_r139950690
            # for discussion.
            if t.args and not self.global_scope:
                if not self.in_dynamic_func:
                    self.fail('Unsupported forward reference to "{}"'.format(t.name), t)
                return AnyType(TypeOfAny.from_error)
            return ForwardRef(t)
        # None of the above options worked, we give up.
        self.fail('Invalid type "{}"'.format(name), t)
        if self.third_pass and isinstance(sym.node, TypeVarExpr):
            self.note_func("Forward references to type variables are prohibited", t)
            return AnyType(TypeOfAny.from_error)
        # TODO: Would it be better to always return Any instead of UnboundType
        # in case of an error? On one hand, UnboundType has a name so error messages
        # are more detailed, on the other hand, some of them may be bogus.
        return t

    def visit_any(self, t: AnyType) -> Type:
        return t

    def visit_none_type(self, t: NoneTyp) -> Type:
        return t

    def visit_uninhabited_type(self, t: UninhabitedType) -> Type:
        return t

    def visit_deleted_type(self, t: DeletedType) -> Type:
        return t

    def visit_type_list(self, t: TypeList) -> Type:
        self.fail('Invalid type', t)
        return AnyType(TypeOfAny.from_error)

    def visit_callable_argument(self, t: CallableArgument) -> Type:
        self.fail('Invalid type', t)
        return AnyType(TypeOfAny.from_error)

    def visit_instance(self, t: Instance) -> Type:
        return t

    def visit_type_var(self, t: TypeVarType) -> Type:
        return t

    def visit_callable_type(self, t: CallableType, nested: bool = True) -> Type:
        # Every Callable can bind its own type variables, if they're not in the outer scope
        with self.tvar_scope_frame():
            if self.defining_alias:
                variables = t.variables
            else:
                variables = self.bind_function_type_variables(t, t)
            ret = t.copy_modified(arg_types=self.anal_array(t.arg_types, nested=nested),
                                  ret_type=self.anal_type(t.ret_type, nested=nested),
                                  # If the fallback isn't filled in yet,
                                  # its type will be the falsey FakeInfo
                                  fallback=(t.fallback if t.fallback.type
                                            else self.named_type('builtins.function')),
                                  variables=self.anal_var_defs(variables))
        return ret

    def visit_tuple_type(self, t: TupleType) -> Type:
        # Types such as (t1, t2, ...) only allowed in assignment statements. They'll
        # generate errors elsewhere, and Tuple[t1, t2, ...] must be used instead.
        if t.implicit and not self.allow_tuple_literal:
            self.fail('Syntax error in type annotation', t)
            if len(t.items) == 1:
                self.note_func('Suggestion: Is there a spurious trailing comma?', t)
            else:
                self.note_func('Suggestion: Use Tuple[T1, ..., Tn] instead of (T1, ..., Tn)', t)
            return AnyType(TypeOfAny.from_error)
        star_count = sum(1 for item in t.items if isinstance(item, StarType))
        if star_count > 1:
            self.fail('At most one star type allowed in a tuple', t)
            if t.implicit:
                return TupleType([AnyType(TypeOfAny.from_error) for _ in t.items],
                                 self.named_type('builtins.tuple'),
                                 t.line)
            else:
                return AnyType(TypeOfAny.from_error)
        any_type = AnyType(TypeOfAny.special_form)
        # If the fallback isn't filled in yet, its type will be the falsey FakeInfo
        fallback = (t.partial_fallback if t.partial_fallback.type
                    else self.named_type('builtins.tuple', [any_type]))
        return TupleType(self.anal_array(t.items), fallback, t.line)

    def visit_typeddict_type(self, t: TypedDictType) -> Type:
        items = OrderedDict([
            (item_name, self.anal_type(item_type))
            for (item_name, item_type) in t.items.items()
        ])
        return TypedDictType(items, set(t.required_keys), t.fallback)

    def visit_raw_expression_type(self, t: RawExpressionType) -> Type:
        # We should never see a bare Literal. We synthesize these raw literals
        # in the earlier stages of semantic analysis, but those
        # "fake literals" should always be wrapped in an UnboundType
        # corresponding to 'Literal'.
        #
        # Note: if at some point in the distant future, we decide to
        # make signatures like "foo(x: 20) -> None" legal, we can change
        # this method so it generates and returns an actual LiteralType
        # instead.

        if self.report_invalid_types:
            if t.base_type_name in ('builtins.int', 'builtins.bool'):
                # The only time it makes sense to use an int or bool is inside of
                # a literal type.
                msg = "Invalid type: try using Literal[{}] instead?".format(repr(t.literal_value))
            elif t.base_type_name in ('builtins.float', 'builtins.complex'):
                # We special-case warnings for floats and complex numbers.
                msg = "Invalid type: {} literals cannot be used as a type".format(t.simple_name())
            else:
                # And in all other cases, we default to a generic error message.
                # Note: the reason why we use a generic error message for strings
                # but not ints or bools is because whenever we see an out-of-place
                # string, it's unclear if the user meant to construct a literal type
                # or just misspelled a regular type. So we avoid guessing.
                msg = 'Invalid type comment or annotation'

            self.fail(msg, t)
            if t.note is not None:
                self.note_func(t.note, t)

        return AnyType(TypeOfAny.from_error, line=t.line, column=t.column)

    def visit_literal_type(self, t: LiteralType) -> Type:
        return t

    def visit_star_type(self, t: StarType) -> Type:
        return StarType(self.anal_type(t.type), t.line)

    def visit_union_type(self, t: UnionType) -> Type:
        return UnionType(self.anal_array(t.items), t.line)

    def visit_partial_type(self, t: PartialType) -> Type:
        assert False, "Internal error: Unexpected partial type"

    def visit_ellipsis_type(self, t: EllipsisType) -> Type:
        self.fail("Unexpected '...'", t)
        return AnyType(TypeOfAny.from_error)

    def visit_type_type(self, t: TypeType) -> Type:
        return TypeType.make_normalized(self.anal_type(t.item), line=t.line)

    def visit_forwardref_type(self, t: ForwardRef) -> Type:
        return t

    def analyze_callable_type(self, t: UnboundType) -> Type:
        fallback = self.named_type('builtins.function')
        if len(t.args) == 0:
            # Callable (bare). Treat as Callable[..., Any].
            any_type = AnyType(TypeOfAny.from_omitted_generics,
                               line=t.line, column=t.column)
            ret = CallableType([any_type, any_type],
                               [nodes.ARG_STAR, nodes.ARG_STAR2],
                               [None, None],
                               ret_type=any_type,
                               fallback=fallback,
                               is_ellipsis_args=True)
        elif len(t.args) == 2:
            ret_type = t.args[1]
            if isinstance(t.args[0], TypeList):
                # Callable[[ARG, ...], RET] (ordinary callable type)
                analyzed_args = self.analyze_callable_args(t.args[0])
                if analyzed_args is None:
                    return AnyType(TypeOfAny.from_error)
                args, kinds, names = analyzed_args
                ret = CallableType(args,
                                   kinds,
                                   names,
                                   ret_type=ret_type,
                                   fallback=fallback)
            elif isinstance(t.args[0], EllipsisType):
                # Callable[..., RET] (with literal ellipsis; accept arbitrary arguments)
                ret = CallableType([AnyType(TypeOfAny.explicit),
                                    AnyType(TypeOfAny.explicit)],
                                   [nodes.ARG_STAR, nodes.ARG_STAR2],
                                   [None, None],
                                   ret_type=ret_type,
                                   fallback=fallback,
                                   is_ellipsis_args=True)
            else:
                self.fail('The first argument to Callable must be a list of types or "..."', t)
                return AnyType(TypeOfAny.from_error)
        else:
            self.fail('Please use "Callable[[<parameters>], <return type>]" or "Callable"', t)
            return AnyType(TypeOfAny.from_error)
        assert isinstance(ret, CallableType)
        return ret.accept(self)

    def analyze_callable_args(self, arglist: TypeList) -> Optional[Tuple[List[Type],
                                                                         List[int],
                                                                         List[Optional[str]]]]:
        args = []   # type: List[Type]
        kinds = []  # type: List[int]
        names = []  # type: List[Optional[str]]
        for arg in arglist.items:
            if isinstance(arg, CallableArgument):
                args.append(arg.typ)
                names.append(arg.name)
                if arg.constructor is None:
                    return None
                found = self.lookup(arg.constructor, arg)
                if found is None:
                    # Looking it up already put an error message in
                    return None
                elif found.fullname not in ARG_KINDS_BY_CONSTRUCTOR:
                    self.fail('Invalid argument constructor "{}"'.format(
                        found.fullname), arg)
                    return None
                else:
                    assert found.fullname is not None
                    kind = ARG_KINDS_BY_CONSTRUCTOR[found.fullname]
                    kinds.append(kind)
                    if arg.name is not None and kind in {ARG_STAR, ARG_STAR2}:
                        self.fail("{} arguments should not have names".format(
                            arg.constructor), arg)
                        return None
            else:
                args.append(arg)
                kinds.append(ARG_POS)
                names.append(None)
        # Note that arglist below is only used for error context.
        check_arg_names(names, [arglist] * len(args), self.fail, "Callable")
        check_arg_kinds(kinds, [arglist] * len(args), self.fail)
        return args, kinds, names

    def analyze_literal_type(self, t: UnboundType) -> Type:
        if len(t.args) == 0:
            self.fail('Literal[...] must have at least one parameter', t)
            return AnyType(TypeOfAny.from_error)

        output = []  # type: List[Type]
        for i, arg in enumerate(t.args):
            analyzed_types = self.analyze_literal_param(i + 1, arg, t)
            if analyzed_types is None:
                return AnyType(TypeOfAny.from_error)
            else:
                output.extend(analyzed_types)
        return UnionType.make_union(output, line=t.line)

    def analyze_literal_param(self, idx: int, arg: Type, ctx: Context) -> Optional[List[Type]]:
        # This UnboundType was originally defined as a string.
        if isinstance(arg, UnboundType) and arg.original_str_expr is not None:
            assert arg.original_str_fallback is not None
            return [LiteralType(
                value=arg.original_str_expr,
                fallback=self.named_type_with_normalized_str(arg.original_str_fallback),
                line=arg.line,
                column=arg.column,
            )]

        # If arg is an UnboundType that was *not* originally defined as
        # a string, try expanding it in case it's a type alias or something.
        if isinstance(arg, UnboundType):
            arg = self.anal_type(arg)

        # Literal[...] cannot contain Any. Give up and add an error message
        # (if we haven't already).
        if isinstance(arg, AnyType):
            # Note: We can encounter Literals containing 'Any' under three circumstances:
            #
            # 1. If the user attempts use an explicit Any as a parameter
            # 2. If the user is trying to use an enum value imported from a module with
            #    no type hints, giving it an an implicit type of 'Any'
            # 3. If there's some other underlying problem with the parameter.
            #
            # We report an error in only the first two cases. In the third case, we assume
            # some other region of the code has already reported a more relevant error.
            #
            # TODO: Once we start adding support for enums, make sure we reprt a custom
            # error for case 2 as well.
            if arg.type_of_any != TypeOfAny.from_error:
                self.fail('Parameter {} of Literal[...] cannot be of type "Any"'.format(idx), ctx)
            return None
        elif isinstance(arg, RawExpressionType):
            # A raw literal. Convert it directly into a literal if we can.
            if arg.literal_value is None:
                name = arg.simple_name()
                if name in ('float', 'complex'):
                    msg = 'Parameter {} of Literal[...] cannot be of type "{}"'.format(idx, name)
                else:
                    msg = 'Invalid type: Literal[...] cannot contain arbitrary expressions'
                self.fail(msg, ctx)
                # Note: we deliberately ignore arg.note here: the extra info might normally be
                # helpful, but it generally won't make sense in the context of a Literal[...].
                return None

            # Remap bytes and unicode into the appropriate type for the correct Python version
            fallback = self.named_type_with_normalized_str(arg.base_type_name)
            assert isinstance(fallback, Instance)
            return [LiteralType(arg.literal_value, fallback, line=arg.line, column=arg.column)]
        elif isinstance(arg, (NoneTyp, LiteralType)):
            # Types that we can just add directly to the literal/potential union of literals.
            return [arg]
        elif isinstance(arg, Instance) and arg.final_value is not None:
            # Types generated from declarations like "var: Final = 4".
            return [arg.final_value]
        elif isinstance(arg, UnionType):
            out = []
            for union_arg in arg.items:
                union_result = self.analyze_literal_param(idx, union_arg, ctx)
                if union_result is None:
                    return None
                out.extend(union_result)
            return out
        elif isinstance(arg, ForwardRef):
            return [arg]
        else:
            self.fail('Parameter {} of Literal[...] is invalid'.format(idx), ctx)
            return None

    def analyze_type(self, t: Type) -> Type:
        return t.accept(self)

    def fail(self, msg: str, ctx: Context) -> None:
        self.fail_func(msg, ctx)

    @contextmanager
    def tvar_scope_frame(self) -> Iterator[None]:
        old_scope = self.tvar_scope
        if self.tvar_scope:
            self.tvar_scope = self.tvar_scope.method_frame()
        else:
            assert self.third_pass, "Internal error: type variable scope not given"
        yield
        self.tvar_scope = old_scope

    def infer_type_variables(self,
                             type: CallableType) -> List[Tuple[str, TypeVarExpr]]:
        """Return list of unique type variables referred to in a callable."""
        if not self.tvar_scope:
            return []  # We are in third pass, nothing new here
        names = []  # type: List[str]
        tvars = []  # type: List[TypeVarExpr]
        for arg in type.arg_types:
            for name, tvar_expr in arg.accept(TypeVariableQuery(self.lookup, self.tvar_scope)):
                if name not in names:
                    names.append(name)
                    tvars.append(tvar_expr)
        # When finding type variables in the return type of a function, don't
        # look inside Callable types.  Type variables only appearing in
        # functions in the return type belong to those functions, not the
        # function we're currently analyzing.
        for name, tvar_expr in type.ret_type.accept(
                TypeVariableQuery(self.lookup, self.tvar_scope, include_callables=False)):
            if name not in names:
                names.append(name)
                tvars.append(tvar_expr)
        return list(zip(names, tvars))

    def bind_function_type_variables(self,
                                     fun_type: CallableType, defn: Context) -> List[TypeVarDef]:
        """Find the type variables of the function type and bind them in our tvar_scope"""
        if not self.tvar_scope:
            return []  # We are in third pass, nothing new here
        if fun_type.variables:
            for var in fun_type.variables:
                var_node = self.lookup(var.name, var)
                assert var_node, "Binding for function type variable not found within function"
                var_expr = var_node.node
                assert isinstance(var_expr, TypeVarExpr)
                self.tvar_scope.bind_new(var.name, var_expr)
            return fun_type.variables
        typevars = self.infer_type_variables(fun_type)
        # Do not define a new type variable if already defined in scope.
        typevars = [(name, tvar) for name, tvar in typevars
                    if not self.is_defined_type_var(name, defn)]
        defs = []  # type: List[TypeVarDef]
        for name, tvar in typevars:
            if not self.tvar_scope.allow_binding(tvar.fullname()):
                self.fail("Type variable '{}' is bound by an outer class".format(name), defn)
            self.tvar_scope.bind_new(name, tvar)
            binding = self.tvar_scope.get_binding(tvar.fullname())
            assert binding is not None
            defs.append(binding)

        return defs

    def is_defined_type_var(self, tvar: str, context: Context) -> bool:
        if self.tvar_scope is None:
            return False
        tvar_node = self.lookup(tvar, context)
        if not tvar_node:
            return False
        return self.tvar_scope.get_binding(tvar_node) is not None

    def anal_array(self, a: List[Type], nested: bool = True) -> List[Type]:
        res = []  # type: List[Type]
        for t in a:
            res.append(self.anal_type(t, nested))
        return res

    def anal_type(self, t: Type, nested: bool = True) -> Type:
        if nested:
            self.nesting_level += 1
        try:
            return t.accept(self)
        finally:
            if nested:
                self.nesting_level -= 1

    def anal_var_defs(self, var_defs: List[TypeVarDef]) -> List[TypeVarDef]:
        a = []  # type: List[TypeVarDef]
        for vd in var_defs:
            a.append(TypeVarDef(vd.name,
                                vd.fullname,
                                vd.id.raw_id,
                                self.anal_array(vd.values),
                                vd.upper_bound.accept(self),
                                vd.variance,
                                vd.line))
        return a

    def named_type_with_normalized_str(self, fully_qualified_name: str) -> Instance:
        """Does almost the same thing as `named_type`, except that we immediately
        unalias `builtins.bytes` and `builtins.unicode` to `builtins.str` as appropriate.
        """
        python_version = self.options.python_version
        if python_version[0] == 2 and fully_qualified_name == 'builtins.bytes':
            fully_qualified_name = 'builtins.str'
        if python_version[0] >= 3 and fully_qualified_name == 'builtins.unicode':
            fully_qualified_name = 'builtins.str'
        return self.named_type(fully_qualified_name)

    def named_type(self, fully_qualified_name: str,
                   args: Optional[List[Type]] = None,
                   line: int = -1,
                   column: int = -1) -> Instance:
        node = self.lookup_fqn_func(fully_qualified_name)
        assert isinstance(node.node, TypeInfo)
        any_type = AnyType(TypeOfAny.special_form)
        return Instance(node.node, args or [any_type] * len(node.node.defn.type_vars),
                        line=line, column=column)

    def tuple_type(self, items: List[Type]) -> TupleType:
        any_type = AnyType(TypeOfAny.special_form)
        return TupleType(items, fallback=self.named_type('builtins.tuple', [any_type]))


class TypeAnalyserPass3(TypeVisitor[None]):
    """Analyze type argument counts and values of generic types.

    This is semantic analysis pass 3 for types.

    Perform these operations:

     * Report error for invalid type argument counts, such as List[x, y].
     * Make implicit Any type arguments explicit my modifying types
       in-place. For example, modify Foo into Foo[Any] if Foo expects a single
       type argument.
     * If a type variable has a value restriction, ensure that the value is
       valid. For example, reject IO[int] if the type argument must be str
       or bytes.

    We can't do this earlier than the third pass, since type argument counts
    are only determined in pass 2, and we have to support forward references
    to types.
    """

    def __init__(self,
                 api: SemanticAnalyzerCoreInterface,
                 plugin: Plugin,
                 options: Options,
                 is_typeshed_stub: bool,
                 indicator: Dict[str, bool],
                 patches: List[Tuple[int, Callable[[], None]]]) -> None:
        self.api = api
        self.lookup_func = api.lookup_qualified
        self.lookup_fqn_func = api.lookup_fully_qualified
        self.fail = api.fail
        self.note_func = api.note
        self.options = options
        self.plugin = plugin
        self.is_typeshed_stub = is_typeshed_stub
        self.indicator = indicator
        self.patches = patches
        self.aliases_used = set()  # type: Set[str]

    def visit_instance(self, t: Instance) -> None:
        info = t.type
        if info.replaced or info.tuple_type:
            self.indicator['synthetic'] = True
        # Check type argument count.
        if len(t.args) != len(info.type_vars):
            fix_instance(t, self.fail)
        elif info.defn.type_vars:
            # Check type argument values. This is postponed to the end of semantic analysis
            # since we need full MROs and resolved forward references.
            for tvar in info.defn.type_vars:
                if (tvar.values
                        or not isinstance(tvar.upper_bound, Instance)
                        or tvar.upper_bound.type.fullname() != 'builtins.object'):
                    # Some restrictions on type variable. These can only be checked later
                    # after we have final MROs and forward references have been resolved.
                    self.indicator['typevar'] = True
        for arg in t.args:
            arg.accept(self)
        if info.is_newtype:
            for base in info.bases:
                base.accept(self)

    def visit_callable_type(self, t: CallableType) -> None:
        t.ret_type.accept(self)
        for arg_type in t.arg_types:
            arg_type.accept(self)

    def visit_overloaded(self, t: Overloaded) -> None:
        for item in t.items():
            item.accept(self)

    def visit_tuple_type(self, t: TupleType) -> None:
        for item in t.items:
            item.accept(self)

    def visit_typeddict_type(self, t: TypedDictType) -> None:
        for item_type in t.items.values():
            item_type.accept(self)

    def visit_literal_type(self, t: LiteralType) -> None:
        # We've already validated that the LiteralType
        # contains either some literal expr like int, str, or
        # bool in the previous pass -- we were able to do this
        # since we had direct access to the underlying expression
        # at those stages.
        #
        # The only thing we have left to check is to confirm
        # whether LiteralTypes of the form 'Literal[Foo.bar]'
        # contain enum members or not.
        #
        # TODO: implement this.
        pass

    def visit_union_type(self, t: UnionType) -> None:
        for item in t.items:
            item.accept(self)

    def visit_star_type(self, t: StarType) -> None:
        t.type.accept(self)

    # Other kinds of type are trivial, since they are atomic (or invalid).

    def visit_unbound_type(self, t: UnboundType) -> None:
        pass

    def visit_any(self, t: AnyType) -> None:
        pass

    def visit_none_type(self, t: NoneTyp) -> None:
        pass

    def visit_uninhabited_type(self, t: UninhabitedType) -> None:
        pass

    def visit_deleted_type(self, t: DeletedType) -> None:
        pass

    def visit_type_list(self, t: TypeList) -> None:
        self.fail('Invalid type', t)

    def visit_type_var(self, t: TypeVarType) -> None:
        if t.upper_bound:
            t.upper_bound.accept(self)
        if t.values:
            for v in t.values:
                v.accept(self)

    def visit_partial_type(self, t: PartialType) -> None:
        pass

    def visit_type_type(self, t: TypeType) -> None:
        t.item.accept(self)

    def visit_forwardref_type(self, t: ForwardRef) -> None:
        self.indicator['forward'] = True
        # mypyc plays badly with the janky failure to realize
        # t.resolved is changed, so keep it from figuring out that it
        # is None
        if (t.resolved is None) is True:
            resolved = self.anal_type(t.unbound)
            t.resolve(resolved)
            assert t.resolved is not None
            t.resolved.accept(self)

    def anal_type(self, tp: UnboundType) -> Type:
        tpan = TypeAnalyser(self.api,
                            None,
                            self.plugin,
                            self.options,
                            self.is_typeshed_stub,
                            third_pass=True)
        res = tp.accept(tpan)
        self.aliases_used = tpan.aliases_used
        return res


TypeVarList = List[Tuple[str, TypeVarExpr]]


def fix_instance(t: Instance, fail: Callable[[str, Context], None]) -> None:
    """Fix a malformed instance by replacing all type arguments with Any.

    Also emit a suitable error if this is not due to implicit Any's.
    """
    if len(t.args) == 0:
        any_type = AnyType(TypeOfAny.from_omitted_generics,
                           line=t.line, column=t.column)
        t.args = [any_type] * len(t.type.type_vars)
        return
    # Invalid number of type parameters.
    n = len(t.type.type_vars)
    s = '{} type arguments'.format(n)
    if n == 0:
        s = 'no type arguments'
    elif n == 1:
        s = '1 type argument'
    act = str(len(t.args))
    if act == '0':
        act = 'none'
    fail('"{}" expects {}, but {} given'.format(
        t.type.name(), s, act), t)
    # Construct the correct number of type arguments, as
    # otherwise the type checker may crash as it expects
    # things to be right.
    t.args = [AnyType(TypeOfAny.from_error) for _ in t.type.type_vars]
    t.invalid = True


def expand_type_alias(target: Type, alias_tvars: List[str], args: List[Type],
                      fail: Callable[[str, Context], None], no_args: bool, ctx: Context) -> Type:
    """Expand a (generic) type alias target following the rules outlined in TypeAlias docstring.

    Here:
        target: original target type (contains unbound type variables)
        alias_tvars: type variable names
        args: types to be substituted in place of type variables
        fail: error reporter callback
        no_args: whether original definition used a bare generic `A = List`
        ctx: context where expansion happens
    """
    exp_len = len(alias_tvars)
    act_len = len(args)
    if exp_len > 0 and act_len == 0:
        # Interpret bare Alias same as normal generic, i.e., Alias[Any, Any, ...]
        assert alias_tvars is not None
        return set_any_tvars(target, alias_tvars, ctx.line, ctx.column)
    if exp_len == 0 and act_len == 0:
        if no_args:
            assert isinstance(target, Instance)
            return Instance(target.type, [], line=ctx.line, column=ctx.column)
        return target
    if exp_len == 0 and act_len > 0 and isinstance(target, Instance) and no_args:
        tp = Instance(target.type, args)
        tp.line = ctx.line
        tp.column = ctx.column
        return tp
    if act_len != exp_len:
        fail('Bad number of arguments for type alias, expected: %s, given: %s'
             % (exp_len, act_len), ctx)
        return set_any_tvars(target, alias_tvars or [],
                             ctx.line, ctx.column, implicit=False)
    typ = replace_alias_tvars(target, alias_tvars, args, ctx.line, ctx.column)
    # HACK: Implement FlexibleAlias[T, typ] by expanding it to typ here.
    if (isinstance(typ, Instance)
            and typ.type.fullname() == 'mypy_extensions.FlexibleAlias'):
        typ = typ.args[-1]
    return typ


def replace_alias_tvars(tp: Type, vars: List[str], subs: List[Type],
                        newline: int, newcolumn: int) -> Type:
    """Replace type variables in a generic type alias tp with substitutions subs
    resetting context. Length of subs should be already checked.
    """
    typ_args = get_typ_args(tp)
    new_args = typ_args[:]
    for i, arg in enumerate(typ_args):
        if isinstance(arg, (UnboundType, TypeVarType)):
            tvar = arg.name  # type: Optional[str]
        else:
            tvar = None
        if tvar and tvar in vars:
            # Perform actual substitution...
            new_args[i] = subs[vars.index(tvar)]
        else:
            # ...recursively, if needed.
            new_args[i] = replace_alias_tvars(arg, vars, subs, newline, newcolumn)
    return set_typ_args(tp, new_args, newline, newcolumn)


def set_any_tvars(tp: Type, vars: List[str],
                  newline: int, newcolumn: int, implicit: bool = True) -> Type:
    if implicit:
        type_of_any = TypeOfAny.from_omitted_generics
    else:
        type_of_any = TypeOfAny.special_form
    any_type = AnyType(type_of_any, line=newline, column=newcolumn)
    return replace_alias_tvars(tp, vars, [any_type] * len(vars), newline, newcolumn)


def remove_dups(tvars: Iterable[T]) -> List[T]:
    # Get unique elements in order of appearance
    all_tvars = set()  # type: Set[T]
    new_tvars = []  # type: List[T]
    for t in tvars:
        if t not in all_tvars:
            new_tvars.append(t)
            all_tvars.add(t)
    return new_tvars


def flatten_tvars(ll: Iterable[List[T]]) -> List[T]:
    return remove_dups(chain.from_iterable(ll))


class TypeVariableQuery(TypeQuery[TypeVarList]):

    def __init__(self,
                 lookup: Callable[[str, Context], Optional[SymbolTableNode]],
                 scope: 'TypeVarScope',
                 *,
                 include_callables: bool = True,
                 include_bound_tvars: bool = False) -> None:
        self.include_callables = include_callables
        self.lookup = lookup
        self.scope = scope
        self.include_bound_tvars = include_bound_tvars
        super().__init__(flatten_tvars)

    def _seems_like_callable(self, type: UnboundType) -> bool:
        if not type.args:
            return False
        if isinstance(type.args[0], (EllipsisType, TypeList)):
            return True
        return False

    def visit_unbound_type(self, t: UnboundType) -> TypeVarList:
        name = t.name
        node = self.lookup(name, t)
        if node and isinstance(node.node, TypeVarExpr) and (
                self.include_bound_tvars or self.scope.get_binding(node) is None):
            assert isinstance(node.node, TypeVarExpr)
            return [(name, node.node)]
        elif not self.include_callables and self._seems_like_callable(t):
            return []
        elif node and node.fullname in ('typing_extensions.Literal', 'typing.Literal'):
            return []
        else:
            return super().visit_unbound_type(t)

    def visit_callable_type(self, t: CallableType) -> TypeVarList:
        if self.include_callables:
            return super().visit_callable_type(t)
        else:
            return []


def check_for_explicit_any(typ: Optional[Type],
                           options: Options,
                           is_typeshed_stub: bool,
                           msg: MessageBuilder,
                           context: Context) -> None:
    if (options.disallow_any_explicit and
            not is_typeshed_stub and
            typ and
            has_explicit_any(typ)):
        msg.explicit_any(context)


def has_explicit_any(t: Type) -> bool:
    """
    Whether this type is or type it contains is an Any coming from explicit type annotation
    """
    return t.accept(HasExplicitAny())


class HasExplicitAny(TypeQuery[bool]):
    def __init__(self) -> None:
        super().__init__(any)

    def visit_any(self, t: AnyType) -> bool:
        return t.type_of_any == TypeOfAny.explicit

    def visit_typeddict_type(self, t: TypedDictType) -> bool:
        # typeddict is checked during TypedDict declaration, so don't typecheck it here.
        return False


def has_any_from_unimported_type(t: Type) -> bool:
    """Return true if this type is Any because an import was not followed.

    If type t is such Any type or has type arguments that contain such Any type
    this function will return true.
    """
    return t.accept(HasAnyFromUnimportedType())


class HasAnyFromUnimportedType(TypeQuery[bool]):
    def __init__(self) -> None:
        super().__init__(any)

    def visit_any(self, t: AnyType) -> bool:
        return t.type_of_any == TypeOfAny.from_unimported_type

    def visit_typeddict_type(self, t: TypedDictType) -> bool:
        # typeddict is checked during TypedDict declaration, so don't typecheck it here
        return False


def collect_any_types(t: Type) -> List[AnyType]:
    """Return all inner `AnyType`s of type t"""
    return t.accept(CollectAnyTypesQuery())


class CollectAnyTypesQuery(TypeQuery[List[AnyType]]):
    def __init__(self) -> None:
        super().__init__(self.combine_lists_strategy)

    def visit_any(self, t: AnyType) -> List[AnyType]:
        return [t]

    @classmethod
    def combine_lists_strategy(cls, it: Iterable[List[AnyType]]) -> List[AnyType]:
        result = []  # type: List[AnyType]
        for l in it:
            result.extend(l)
        return result


def collect_all_inner_types(t: Type) -> List[Type]:
    """
    Return all types that `t` contains
    """
    return t.accept(CollectAllInnerTypesQuery())


class CollectAllInnerTypesQuery(TypeQuery[List[Type]]):
    def __init__(self) -> None:
        super().__init__(self.combine_lists_strategy)

    def query_types(self, types: Iterable[Type]) -> List[Type]:
        return self.strategy(t.accept(self) for t in types) + list(types)

    @classmethod
    def combine_lists_strategy(cls, it: Iterable[List[Type]]) -> List[Type]:
        return list(itertools.chain.from_iterable(it))


def make_optional_type(t: Type) -> Type:
    """Return the type corresponding to Optional[t].

    Note that we can't use normal union simplification, since this function
    is called during semantic analysis and simplification only works during
    type checking.
    """
    if isinstance(t, NoneTyp):
        return t
    elif isinstance(t, UnionType):
        items = [item for item in union_items(t)
                 if not isinstance(item, NoneTyp)]
        return UnionType(items + [NoneTyp()], t.line, t.column)
    else:
        return UnionType([t, NoneTyp()], t.line, t.column)
