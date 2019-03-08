from typing import (
    List, Optional, Set, Tuple, Dict, Callable, Union, NamedTuple, TypeVar, Iterator,
)

import mypy.checker
import mypy.types
from mypy.state import strict_optional_set
from mypy.types import (
    Type, AnyType, TypeOfAny, CallableType, UnionType, NoneTyp, Instance, is_optional,
)
from mypy.build import State
from mypy.nodes import (
    ARG_POS, ARG_STAR, ARG_NAMED, ARG_STAR2, ARG_NAMED_OPT, FuncDef, MypyFile, SymbolTable,
    SymbolNode, TypeInfo, Node, Expression, ReturnStmt,
)
from mypy.server.update import FineGrainedBuildManager
from mypy.server.target import module_prefix, split_target
from mypy.plugin import Plugin, ChainedPlugin, FunctionContext, MethodContext
from mypy.traverser import TraverserVisitor

from mypy.join import join_types, join_type_list
from mypy.sametypes import is_same_type

from contextlib import contextmanager

import itertools

Callsite = NamedTuple(
    'Callsite',
    [('path', str),
     ('line', int),
     ('arg_kinds', List[List[int]]),
     ('callee_arg_names', List[Optional[str]]),
     ('arg_names', List[List[Optional[str]]]),
     ('arg_types', List[List[Type]])])


class SuggestionPlugin(Plugin):
    def __init__(self, target: str) -> None:
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
    def __init__(self, typemap: Dict[Expression, Type]) -> None:
        self.typemap = typemap
        self.return_types = []  # type: List[Type]

    def visit_return_stmt(self, o: ReturnStmt) -> None:
        if o.expr is not None:
            self.return_types.append(self.typemap[o.expr])


def get_return_types(typemap: Dict[Expression, Type], func: FuncDef) -> List[Type]:
    finder = ReturnFinder(typemap)
    func.accept(finder)
    return finder.return_types


T = TypeVar('T')


def dedup(old: List[T]) -> List[T]:
    new = []  # type: List[T]
    for x in old:
        if x not in new:
            new.append(x)
    return new


class SuggestionFailure(Exception):
    pass


def is_explicit_any(typ: AnyType) -> bool:
    # Important question: how would we do with source_any stuff? Does that count?
    # Andy actually should explicit anys count at all?? Maybe not!
    return typ.type_of_any == TypeOfAny.explicit
    # return (typ.type_of_any == TypeOfAny.explicit
    #         or (typ.source_any is not None and typ.source_any.type_of_any == TypeOfAny.explicit))


class SuggestionEngine:
    """Engine for finding call sites and suggesting signatures.

    Currently it can only do the former.
    """

    def __init__(self, fgmanager: FineGrainedBuildManager):
        self.fgmanager = fgmanager
        self.manager = fgmanager.manager
        self.plugin = self.manager.plugin
        self.overrides = self.manager.semantic_analyzer.func_type_overrides
        self.graph = fgmanager.graph

    def builtin_type(self, s: str) -> Instance:
        return self.manager.semantic_analyzer.builtin_type(s)

    def suggest(self, function: str) -> str:
        with self.restore_after(function):
            suggestions = self.get_suggestions(function)
        return "\n".join(suggestions)

    def suggest_callsites(self, function: str) -> str:
        with self.restore_after(function):
            mod, _, _, node = self.find_node(function)
            callsites, _ = self.get_callsites(mod, node)

        return '\n'.join(dedup(
            ["%s:%s: %s" % (path, line, self.format_args(arg_kinds, arg_names, arg_types))
             for path, line, arg_kinds, _, arg_names, arg_types in callsites]
        ))

    @contextmanager
    def restore_after(self, target: str) -> Iterator[None]:
        try:
            yield
        finally:
            module = module_prefix(self.graph, target)
            if module:
                self.reload(self.graph[module])

    def get_trivial_type(self, fdef: FuncDef) -> CallableType:
        return CallableType(
            [AnyType(TypeOfAny.unannotated) for a in fdef.arg_kinds],
            fdef.arg_kinds,
            fdef.arg_names,
            AnyType(TypeOfAny.unannotated),
            self.builtin_type('builtins.function'))

    def get_args(self, is_method: bool,
                 base: CallableType, defaults: List[Optional[Type]],
                 callsites: List[Callsite]) -> List[List[Type]]:
        types = []  # type: List[List[Type]]
        for i in range(len(base.arg_kinds)):
            # Make self args Any but this will get overriden somewhere in the checker
            if i == 0 and is_method:
                types.append([AnyType(TypeOfAny.explicit)])
                continue

            all_arg_types = []
            for call in callsites:
                for typ in call.arg_types[i - is_method]:
                    # MAYBE???
                    if not isinstance(typ, AnyType) or is_explicit_any(typ):
                        all_arg_types.append(typ)
            default = defaults[i]
            if default:
                all_arg_types.append(default)

            if all_arg_types:
                types.append(generate_type_combinations(all_arg_types))
            else:
                types.append([AnyType(TypeOfAny.explicit), self.builtin_type('builtins.object')])
        return types

    def get_default_arg_types(self, state: State, fdef: FuncDef) -> List[Optional[Type]]:
        return [state.type_checker().type_map[arg.initializer] if arg.initializer else None
                for arg in fdef.arguments]

    def combine(self, is_method: bool, base: CallableType, defaults: List[Optional[Type]],
                callsites: List[Callsite]) -> List[CallableType]:
        options = self.get_args(is_method, base, defaults, callsites)
        print("TYPE OPTIONS:", options)
        return [base.copy_modified(arg_types=list(x)) for x in itertools.product(*options)]

    def get_callsites(self, mod: str, func: FuncDef) -> Tuple[List[Callsite], List[str]]:
        new_type = self.get_trivial_type(func)

        collector_plugin = SuggestionPlugin(func.fullname())

        self.plugin._plugins.insert(0, collector_plugin)
        try:
            errors = self.try_type(self.graph[mod], func.fullname(), new_type)
        finally:
            self.plugin._plugins.pop(0)

        return collector_plugin.mystery_hits, errors

    def get_suggestions(self, function: str) -> List[str]:
        graph = self.graph
        mod, _, _, node = self.find_node(function)
        callsites, orig_errors = self.get_callsites(mod, node)

        with strict_optional_set(graph[mod].options.strict_optional):
            guesses = self.combine(
                bool(node.info),
                self.get_trivial_type(node),
                self.get_default_arg_types(graph[mod], node),
                callsites)
        errors = {guess: self.try_type(graph[mod], function, guess) for guess in guesses}
        best = min(guesses,
                   key=lambda s: (count_errors(errors[s]), score_callable(s)))

        # Now try to find the return type!
        self.try_type(graph[mod], function, best)
        returns = get_return_types(graph[mod].type_checker().type_map, node)
        with strict_optional_set(graph[mod].options.strict_optional):
            if returns:
                ret_types = generate_type_combinations(returns)
            else:
                ret_types = [NoneTyp()]

        guesses = [best.copy_modified(ret_type=t) for t in ret_types]
        errors = {guess: self.try_type(graph[mod], function, guess) for guess in guesses}
        best = min(guesses,
                   key=lambda s: (count_errors(errors[s]), score_callable(s)))

        print("RETURNS", returns)

        return [str(best)]

    def format_args(self,
                    arg_kinds: List[List[int]],
                    arg_names: List[List[Optional[str]]],
                    arg_types: List[List[Type]]) -> str:
        args = []  # type: List[str]
        for i in range(len(arg_types)):
            for kind, name, typ in zip(arg_kinds[i], arg_names[i], arg_types[i]):
                arg = str(typ)
                arg = arg.replace("*", "")  # Get rid of "inferred" indicators.
                if kind == ARG_STAR:
                    arg = '*' + arg
                elif kind == ARG_STAR2:
                    arg = '**' + arg
                elif kind in (ARG_NAMED, ARG_NAMED_OPT):
                    if name:
                        arg = "%s=%s" % (name, arg)
            args.append(arg)
        return "(%s)" % (", ".join(args))

    def find_node(self, key: str) -> Tuple[str, Optional[str], str, FuncDef]:
        # TODO: Also return OverloadedFuncDef -- currently these are ignored.
        graph = self.fgmanager.graph
        target = split_target(graph, key)
        if not target:
            raise SuggestionFailure("Cannot find %s" % (key,))
        modname, tail = target

        if '.' in tail:
            classname, funcname = tail.split('.')
            return (modname, classname, funcname,
                    self.find_method_node(graph[modname], classname, funcname))
        else:
            funcname = tail
            return (modname, None, funcname,
                    self.find_function_node(graph[modname], funcname))

    def try_type(self, state: State, function: str, typ: Type) -> List[str]:
        overrides = self.manager.semantic_analyzer.func_type_overrides
        overrides[function] = typ
        print("trying:", typ)
        try:
            return self.reload(state)
        finally:
            del overrides[function]

    def reload(self, state: State, check_errors: bool = False) -> List[str]:
        assert state.path is not None
        res = self.fgmanager.update([(state.id, state.path)], [])
        if res:
            print('\n'.join(res))
        if check_errors and res:
            raise SuggestionFailure("Error while trying to load %s" % state.id)
        return res

    def ensure_tree(self, state: State) -> MypyFile:
        if not state.tree or state.tree.is_cache_skeleton:
            self.reload(state, check_errors=True)
        assert state.tree is not None
        return state.tree

    def find_method_node(self, state: State,
                         classname: str, funcname: str) -> FuncDef:
        modname = state.id
        tree = self.ensure_tree(state)
        moduledict = tree.names  # type: SymbolTable
        if classname not in moduledict:
            raise SuggestionFailure("Unknown class %s.%s" % (modname, classname))
        node = moduledict[classname].node  # type: Optional[SymbolNode]
        if not isinstance(node, TypeInfo):
            raise SuggestionFailure("Object %s.%s is not a class" % (modname, classname))
        classdict = node.names  # type: SymbolTable
        if funcname not in classdict:
            raise SuggestionFailure("Unknown method %s.%s.%s" % (modname, classname, funcname))
        node = classdict[funcname].node
        if not isinstance(node, FuncDef):
            raise SuggestionFailure("Object %s.%s.%s is not a function" %
                                    (modname, classname, funcname))
        return node

    def find_function_node(self, state: State, funcname: str) -> FuncDef:
        modname = state.id
        tree = self.ensure_tree(state)
        moduledict = tree.names  # type: SymbolTable
        if funcname not in moduledict:
            raise SuggestionFailure("Unknown function %s.%s" % (modname, funcname))
        node = moduledict[funcname].node
        if not isinstance(node, FuncDef):
            raise SuggestionFailure("Object %s.%s is not a function" % (modname, funcname))
        return node


def generate_type_combinations(types: List[Type]) -> List[Type]:
    joined_type = join_type_list(types)
    union_type = UnionType.make_simplified_union(types)
    if is_same_type(joined_type, union_type):
        return [joined_type]
    else:
        return [joined_type, union_type]


def count_errors(msgs: List[str]) -> int:
    return len([x for x in msgs if ' error: ' in x])


# Lower is better, prefer non-union/non-any types. Don't penalize optionals
def score_type(t: Type) -> int:
    if isinstance(t, AnyType):
        return 2
    if isinstance(t, UnionType):
        if any(isinstance(x, AnyType) for x in t.items):
            return 2
        if not is_optional(t):
            return 1
    return 0


def score_callable(t: CallableType) -> int:
    return sum([score_type(x) for x in t.arg_types])
