"""Mechanisms for inferring function types based on callsites.

Currently works by collecting all argument types at callsites,
synthesizing a list of possible function types from that, trying them
all, and picking the one with the fewest errors that we think is the
"best".

Can return JSON that pyannotate can use to apply the annotations to code.

There are a bunch of TODOs here:
 * Maybe want a way to surface the choices not selected??
 * We can generate an exponential number of type suggestions, and probably want
   a way to not always need to check them all.
 * Our heuristics for what types to try are primitive and not yet
   supported by real practice.
 * More!

Other things:
 * This is super brute force. Could we integrate with the typechecker
   more to understand more about what is going on?
 * Like something with tracking constraints/unification variables?
 * No understanding of type variables at *all*
"""

from typing import (
    List, Optional, Tuple, Dict, Callable, Union, NamedTuple, TypeVar, Iterator,
)

from mypy.state import strict_optional_set
from mypy.types import (
    Type, AnyType, TypeOfAny, CallableType, UnionType, NoneType, Instance, TupleType,
    TypeVarType, FunctionLike,
    TypeStrVisitor, TypeTranslator,
    is_optional,
)
from mypy.build import State, Graph
from mypy.nodes import (
    ARG_STAR, ARG_NAMED, ARG_STAR2, ARG_NAMED_OPT, FuncDef, MypyFile, SymbolTable,
    Decorator, RefExpr,
    SymbolNode, TypeInfo, Expression, ReturnStmt, CallExpr,
    reverse_builtin_aliases,
)
from mypy.server.update import FineGrainedBuildManager
from mypy.util import module_prefix, split_target
from mypy.plugin import Plugin, FunctionContext, MethodContext
from mypy.traverser import TraverserVisitor
from mypy.checkexpr import has_any_type

from mypy.join import join_type_list
from mypy.sametypes import is_same_type

from contextlib import contextmanager

import itertools
import json
import os

Callsite = NamedTuple(
    'Callsite',
    [('path', str),
     ('line', int),
     ('arg_kinds', List[List[int]]),
     ('callee_arg_names', List[Optional[str]]),
     ('arg_names', List[List[Optional[str]]]),
     ('arg_types', List[List[Type]])])


class SuggestionPlugin(Plugin):
    """Plugin that records all calls to a given target."""

    def __init__(self, target: str) -> None:
        if target.endswith(('.__new__', '.__init__')):
            target = target.rsplit('.', 1)[0]

        self.target = target
        # List of call sites found by dmypy suggest:
        # (path, line, <arg kinds>, <arg names>, <arg types>)
        self.mystery_hits = []  # type: List[Callsite]

    def get_function_hook(self, fullname: str
                          ) -> Optional[Callable[[FunctionContext], Type]]:
        if fullname == self.target:
            return self.log
        else:
            return None

    def get_method_hook(self, fullname: str
                        ) -> Optional[Callable[[MethodContext], Type]]:
        if fullname == self.target:
            return self.log
        else:
            return None

    def log(self, ctx: Union[FunctionContext, MethodContext]) -> Type:
        self.mystery_hits.append(Callsite(
            ctx.api.path,
            ctx.context.line,
            ctx.arg_kinds,
            ctx.callee_arg_names,
            ctx.arg_names,
            ctx.arg_types))
        return ctx.default_return_type


# NOTE: We could make this a bunch faster by implementing a StatementVisitor that skips
# traversing into expressions
class ReturnFinder(TraverserVisitor):
    """Visitor for finding all types returned from a function."""
    def __init__(self, typemap: Dict[Expression, Type]) -> None:
        self.typemap = typemap
        self.return_types = []  # type: List[Type]

    def visit_return_stmt(self, o: ReturnStmt) -> None:
        if o.expr is not None and o.expr in self.typemap:
            self.return_types.append(self.typemap[o.expr])


def get_return_types(typemap: Dict[Expression, Type], func: FuncDef) -> List[Type]:
    """Find all the types returned by return statements in func."""
    finder = ReturnFinder(typemap)
    func.accept(finder)
    return finder.return_types


class SuggestionFailure(Exception):
    pass


def is_explicit_any(typ: AnyType) -> bool:
    # Originally I wanted to count as explicit anything derived from an explicit any, but that
    # seemed too strict in some testing.
    # return (typ.type_of_any == TypeOfAny.explicit
    #         or (typ.source_any is not None and typ.source_any.type_of_any == TypeOfAny.explicit))
    # Important question: what should we do with source_any stuff? Does that count?
    # And actually should explicit anys count at all?? Maybe not!
    return typ.type_of_any == TypeOfAny.explicit


def is_implicit_any(typ: Type) -> bool:
    return isinstance(typ, AnyType) and not is_explicit_any(typ)


class SuggestionEngine:
    """Engine for finding call sites and suggesting signatures."""

    def __init__(self, fgmanager: FineGrainedBuildManager,
                 json: bool,
                 no_errors: bool = False,
                 no_any: bool = False,
                 try_text: bool = False) -> None:
        self.fgmanager = fgmanager
        self.manager = fgmanager.manager
        self.plugin = self.manager.plugin
        self.graph = fgmanager.graph

        self.give_json = json
        self.no_errors = no_errors
        self.no_any = no_any
        self.try_text = try_text

        self.max_guesses = 16

    def suggest(self, function: str) -> str:
        """Suggest an inferred type for function."""
        with self.restore_after(function):
            with self.with_export_types():
                suggestion = self.get_suggestion(function)

        if self.give_json:
            return self.json_suggestion(function, suggestion)
        else:
            return suggestion

    def suggest_callsites(self, function: str) -> str:
        """Find a list of call sites of function."""
        with self.restore_after(function):
            _, _, node = self.find_node(function)
            callsites, _ = self.get_callsites(node)

        return '\n'.join(dedup(
            ["%s:%s: %s" % (path, line, self.format_args(arg_kinds, arg_names, arg_types))
             for path, line, arg_kinds, _, arg_names, arg_types in callsites]
        ))

    @contextmanager
    def restore_after(self, target: str) -> Iterator[None]:
        """Context manager that reloads a module after executing the body.

        This should undo any damage done to the module state while mucking around.
        """
        try:
            yield
        finally:
            module = module_prefix(self.graph, target)
            if module:
                self.reload(self.graph[module])

    @contextmanager
    def with_export_types(self) -> Iterator[None]:
        """Context manager that enables the export_types flag in the body.

        This causes type information to be exported into the manager's all_types variable.
        """
        old = self.manager.options.export_types
        self.manager.options.export_types = True
        try:
            yield
        finally:
            self.manager.options.export_types = old

    def get_trivial_type(self, fdef: FuncDef) -> CallableType:
        """Generate a trivial callable type from a func def, with all Anys"""
        return CallableType(
            [AnyType(TypeOfAny.unannotated) for a in fdef.arg_kinds],
            fdef.arg_kinds,
            fdef.arg_names,
            # We call this a special form so that has_any_type doesn't consider it to be a real any
            AnyType(TypeOfAny.special_form),
            self.builtin_type('builtins.function'))

    def get_args(self, is_method: bool,
                 base: CallableType, defaults: List[Optional[Type]],
                 callsites: List[Callsite]) -> List[List[Type]]:
        """Produce a list of type suggestions for each argument type."""
        types = []  # type: List[List[Type]]
        for i in range(len(base.arg_kinds)):
            # Make self args Any but this will get overriden somewhere in the checker
            # We call this a special form so that has_any_type doesn't consider it to be a real any
            if i == 0 and is_method:
                types.append([AnyType(TypeOfAny.special_form)])
                continue

            all_arg_types = []
            for call in callsites:
                for typ in call.arg_types[i - is_method]:
                    # Collect all the types except for implicit anys
                    if not is_implicit_any(typ):
                        all_arg_types.append(typ)
            # Add in any default argument types
            default = defaults[i]
            if default:
                all_arg_types.append(default)

            if all_arg_types:
                types.append(generate_type_combinations(all_arg_types))
            else:
                # If we don't have anything, we'll try Any and object
                # (Actually object usually is bad for downstream consumers...)
                # types.append([AnyType(TypeOfAny.explicit), self.builtin_type('builtins.object')])
                types.append([AnyType(TypeOfAny.explicit)])
        return types

    def get_default_arg_types(self, state: State, fdef: FuncDef) -> List[Optional[Type]]:
        return [self.manager.all_types[arg.initializer] if arg.initializer else None
                for arg in fdef.arguments]

    def add_adjustments(self, typs: List[Type]) -> List[Type]:
        if not self.try_text or self.manager.options.python_version[0] != 2:
            return typs
        translator = StrToText(self.builtin_type)
        return dedup(typs + [tp.accept(translator) for tp in typs])

    def get_guesses(self, is_method: bool, base: CallableType, defaults: List[Optional[Type]],
                    callsites: List[Callsite]) -> List[CallableType]:
        """Compute a list of guesses for a function's type.

        This focuses just on the argument types, and doesn't change the provided return type.
        """
        options = self.get_args(is_method, base, defaults, callsites)
        options = [self.add_adjustments(tps) for tps in options]
        return [base.copy_modified(arg_types=list(x)) for x in itertools.product(*options)]

    def get_callsites(self, func: FuncDef) -> Tuple[List[Callsite], List[str]]:
        """Find all call sites of a function."""
        new_type = self.get_trivial_type(func)

        collector_plugin = SuggestionPlugin(func.fullname())

        self.plugin._plugins.insert(0, collector_plugin)
        try:
            errors = self.try_type(func, new_type)
        finally:
            self.plugin._plugins.pop(0)

        return collector_plugin.mystery_hits, errors

    def filter_options(self, guesses: List[CallableType]) -> List[CallableType]:
        """Apply any configured filters to the possible guesses.

        Currently the only option is disabling Anys."""
        return [
            t for t in guesses
            if not self.no_any or not callable_has_any(t)
        ]

    def find_best(self, func: FuncDef, guesses: List[CallableType]) -> Tuple[CallableType, int]:
        """From a list of possible function types, find the best one.

        For best, we want the fewest errors, then the best "score" from score_callable.
        """
        if not guesses:
            raise SuggestionFailure("No guesses that match criteria!")
        errors = {guess: self.try_type(func, guess) for guess in guesses}
        best = min(guesses,
                   key=lambda s: (count_errors(errors[s]), self.score_callable(s)))
        return best, count_errors(errors[best])

    def get_suggestion(self, function: str) -> str:
        """Compute a suggestion for a function.

        Return the type and whether the first argument should be ignored.
        """
        graph = self.graph
        mod, _, node = self.find_node(function)
        callsites, orig_errors = self.get_callsites(node)

        if self.no_errors and orig_errors:
            raise SuggestionFailure("Function does not typecheck.")

        # FIXME: what about static and class methods?
        is_method = bool(node.info)

        if len(node.arg_names) >= 10:
            raise SuggestionFailure("Too many arguments")

        with strict_optional_set(graph[mod].options.strict_optional):
            guesses = self.get_guesses(
                is_method,
                self.get_trivial_type(node),
                self.get_default_arg_types(graph[mod], node),
                callsites)
        guesses = self.filter_options(guesses)
        if len(guesses) > self.max_guesses:
            raise SuggestionFailure("Too many possibilities!")
        best, _ = self.find_best(node, guesses)

        # Now try to find the return type!
        self.try_type(node, best)
        returns = get_return_types(self.manager.all_types, node)
        with strict_optional_set(graph[mod].options.strict_optional):
            if returns:
                ret_types = generate_type_combinations(returns)
            else:
                ret_types = [NoneType()]

        guesses = [best.copy_modified(ret_type=t) for t in ret_types]
        guesses = self.filter_options(guesses)
        best, errors = self.find_best(node, guesses)

        if self.no_errors and errors:
            raise SuggestionFailure("No annotation without errors")

        return self.format_callable(mod, is_method, best)

    def format_args(self,
                    arg_kinds: List[List[int]],
                    arg_names: List[List[Optional[str]]],
                    arg_types: List[List[Type]]) -> str:
        args = []  # type: List[str]
        for i in range(len(arg_types)):
            for kind, name, typ in zip(arg_kinds[i], arg_names[i], arg_types[i]):
                arg = self.format_type(None, typ)
                if kind == ARG_STAR:
                    arg = '*' + arg
                elif kind == ARG_STAR2:
                    arg = '**' + arg
                elif kind in (ARG_NAMED, ARG_NAMED_OPT):
                    if name:
                        arg = "%s=%s" % (name, arg)
            args.append(arg)
        return "(%s)" % (", ".join(args))

    def find_node(self, key: str) -> Tuple[str, str, FuncDef]:
        """From a target name, return module/target names and the func def."""
        # TODO: Also return OverloadedFuncDef -- currently these are ignored.
        graph = self.fgmanager.graph
        target = split_target(graph, key)
        if not target:
            raise SuggestionFailure("Cannot find module for %s" % (key,))
        modname, tail = target

        tree = self.ensure_loaded(graph[modname])

        # N.B. This is reimplemented from update's lookup_target
        # basically just to produce better error messages.

        names = tree.names  # type: SymbolTable

        # Look through any classes
        components = tail.split('.')
        for i, component in enumerate(components[:-1]):
            if component not in names:
                raise SuggestionFailure("Unknown class %s.%s" %
                                        (modname, '.'.join(components[:i + 1])))
            node = names[component].node  # type: Optional[SymbolNode]
            if not isinstance(node, TypeInfo):
                raise SuggestionFailure("Object %s.%s is not a class" %
                                        (modname, '.'.join(components[:i + 1])))
            names = node.names

        # Look for the actual function/method
        funcname = components[-1]
        if funcname not in names:
            raise SuggestionFailure("Unknown %s %s" %
                                    ("method" if len(components) > 1 else "function", key))
        node = names[funcname].node
        if isinstance(node, Decorator):
            node = self.extract_from_decorator(node)
            if not node:
                raise SuggestionFailure("Object %s is a decorator we can't handle" % key)

        if not isinstance(node, FuncDef):
            raise SuggestionFailure("Object %s is not a function" % key)

        return (modname, tail, node)

    def extract_from_decorator(self, node: Decorator) -> Optional[FuncDef]:
        for dec in node.decorators:
            typ = None
            if (isinstance(dec, RefExpr)
                    and isinstance(dec.node, FuncDef)):
                typ = dec.node.type
            elif (isinstance(dec, CallExpr)
                    and isinstance(dec.callee, RefExpr)
                    and isinstance(dec.callee.node, FuncDef)
                    and isinstance(dec.callee.node.type, CallableType)):
                typ = dec.callee.node.type.ret_type

            if not isinstance(typ, FunctionLike):
                return None
            for ct in typ.items():
                if not (len(ct.arg_types) == 1
                        and isinstance(ct.arg_types[0], TypeVarType)
                        and ct.arg_types[0] == ct.ret_type):
                    return None

        return node.func

    def try_type(self, func: FuncDef, typ: Type) -> List[str]:
        """Recheck a function while assuming it has type typ.

        Return all error messages.
        """
        old = func.unanalyzed_type
        # During reprocessing, unanalyzed_type gets copied to type (by aststrip).
        # We don't modify type because it isn't necessary and it
        # would mess up the snapshotting.
        func.unanalyzed_type = typ
        try:
            res = self.fgmanager.trigger(func.fullname())
            # if res:
            #     print('===', typ)
            #     print('\n'.join(res))
            return res
        finally:
            func.unanalyzed_type = old

    def reload(self, state: State, check_errors: bool = False) -> List[str]:
        """Recheck the module given by state.

        If check_errors is true, raise an exception if there are errors.
        """
        assert state.path is not None
        res = self.fgmanager.update([(state.id, state.path)], [])
        # if res:
        #     print('\n'.join(res))
        if check_errors and res:
            raise SuggestionFailure("Error while trying to load %s" % state.id)
        return res

    def ensure_loaded(self, state: State) -> MypyFile:
        """Make sure that the module represented by state is fully loaded."""
        if not state.tree or state.tree.is_cache_skeleton:
            self.reload(state, check_errors=True)
        assert state.tree is not None
        return state.tree

    def builtin_type(self, s: str) -> Instance:
        if self.manager.options.new_semantic_analyzer:
            return self.manager.new_semantic_analyzer.builtin_type(s)
        else:
            return self.manager.semantic_analyzer.builtin_type(s)

    def json_suggestion(self, function: str, suggestion: str) -> str:
        """Produce a json blob for a suggestion suitable for application by pyannotate."""
        mod, func_name, node = self.find_node(function)

        # pyannotate works with either paths relative to where the
        # module is rooted or with absolute paths. We produce absolute
        # paths because it is simpler.
        path = os.path.abspath(self.graph[mod].xpath)

        obj = {
            'type_comments': [suggestion],
            'line': node.line,
            'path': path,
            'func_name': func_name,
            'samples': 0
        }
        return json.dumps([obj], sort_keys=True)

    def format_callable(self,
                        cur_module: Optional[str], is_method: bool, typ: CallableType) -> str:
        """Format a callable type in a way suitable as an annotation... kind of"""
        start = int(is_method)
        s = "({}) -> {}".format(
            ", ".join([self.format_type(cur_module, t) for t in typ.arg_types[start:]]),
            self.format_type(cur_module, typ.ret_type))
        return s

    def format_type(self, cur_module: Optional[str], typ: Type) -> str:
        return typ.accept(TypeFormatter(cur_module, self.graph))

    def score_type(self, t: Type) -> int:
        """Generate a score for a type that we use to pick which type to use.

        Lower is better, prefer non-union/non-any types. Don't penalize optionals.
        """
        if isinstance(t, AnyType):
            return 20
        if isinstance(t, UnionType):
            if any(isinstance(x, AnyType) for x in t.items):
                return 20
            if not is_optional(t):
                return 10
        if self.try_text and isinstance(t, Instance) and t.type.fullname() == 'builtins.str':
            return 1
        return 0

    def score_callable(self, t: CallableType) -> int:
        return sum([self.score_type(x) for x in t.arg_types])


class TypeFormatter(TypeStrVisitor):
    """Visitor used to format types
    """
    # TODO: Generate valid string representation for callable types.
    # TODO: Probably a bunch more
    def __init__(self, module: Optional[str], graph: Graph) -> None:
        super().__init__()
        self.module = module
        self.graph = graph

    def visit_instance(self, t: Instance) -> str:
        s = t.type.fullname() or t.type.name() or None
        if s is None:
            return '<???>'
        if s in reverse_builtin_aliases:
            s = reverse_builtin_aliases[s]

        mod_obj = split_target(self.graph, s)
        assert mod_obj
        mod, obj = mod_obj

        # If a class is imported into the current module, rewrite the reference
        # to point to the current module. This helps the annotation tool avoid
        # inserting redundant imports when a type has been reexported.
        if self.module:
            parts = obj.split('.')  # need to split the object part if it is a nested class
            tree = self.graph[self.module].tree
            if tree and parts[0] in tree.names:
                mod = self.module

        if (mod, obj) == ('builtins', 'tuple'):
            mod, obj = 'typing', 'Tuple[' + t.args[0].accept(self) + ', ...]'
        elif t.args != []:
            obj += '[{}]'.format(self.list_str(t.args))

        if mod == 'builtins':
            return obj
        else:
            delim = '.' if '.' not in obj else ':'
            return mod + delim + obj

    def visit_tuple_type(self, t: TupleType) -> str:
        if t.partial_fallback and t.partial_fallback.type:
            fallback_name = t.partial_fallback.type.fullname()
            if fallback_name != 'builtins.tuple':
                return t.partial_fallback.accept(self)
        s = self.list_str(t.items)
        return 'Tuple[{}]'.format(s)


class StrToText(TypeTranslator):
    def __init__(self, builtin_type: Callable[[str], Instance]) -> None:
        self.text_type = builtin_type('builtins.unicode')

    def visit_instance(self, t: Instance) -> Type:
        if t.type.fullname() == 'builtins.str':
            return self.text_type
        else:
            return super().visit_instance(t)


def generate_type_combinations(types: List[Type]) -> List[Type]:
    """Generate possible combinations of a list of types.

    mypy essentially supports two different ways to do this: joining the types
    and unioning the types. We try both.
    """
    joined_type = join_type_list(types)
    union_type = UnionType.make_simplified_union(types)
    if is_same_type(joined_type, union_type):
        return [joined_type]
    else:
        return [joined_type, union_type]


def count_errors(msgs: List[str]) -> int:
    return len([x for x in msgs if ' error: ' in x])


def callable_has_any(t: CallableType) -> int:
    # We count a bare None in argument position as Any, since
    # pyannotate turns it into Optional[Any]
    return any(isinstance(at, NoneType) for at in t.arg_types) or has_any_type(t)


T = TypeVar('T')


def dedup(old: List[T]) -> List[T]:
    new = []  # type: List[T]
    for x in old:
        if x not in new:
            new.append(x)
    return new
