from typing import List, Optional, Set, Tuple, Dict, Callable, Union, NamedTuple, TypeVar

import mypy.checker
import mypy.types
from mypy.types import Type
from mypy.build import State
from mypy.nodes import (ARG_POS, ARG_STAR, ARG_NAMED, ARG_STAR2, ARG_NAMED_OPT,
                        FuncDef, MypyFile, SymbolTable, SymbolNode, TypeInfo)
from mypy.server.update import FineGrainedBuildManager
from mypy.server.target import module_prefix, split_target
from mypy.plugin import Plugin, ChainedPlugin, FunctionContext, MethodContext

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


T = TypeVar('T')

def dedup(old: List[T]) -> List[T]:
    new = []  # type: List[T]
    for x in old:
        if x not in new:
            new.append(x)
    return new


class SuggestionFailure(Exception):
    pass


class SuggestionEngine:
    """Engine for finding call sites and suggesting signatures.

    Currently it can only do the former.
    """

    def __init__(self, fgmanager: FineGrainedBuildManager):
        self.fgmanager = fgmanager

    def suggest(self, function: str) -> str:
        suggestions = self.get_suggestions(function)
        return "\n".join(suggestions)

    def get_suggestions(self, function: str) -> List[str]:
        modname, classname, funcname, node = self.find_node(function)
        if classname:
            target = '%s.%s.%s' % (modname, classname, funcname)
        else:
            target = '%s.%s' % (modname, funcname)
        depskey = '<%s>' % target

        deps = self.fgmanager.deps.get(depskey, set())

        module_deps = {}  # type: Dict[str, Set[str]]
        for dep in deps:
            prefix = module_prefix(self.fgmanager.graph, dep)
            if prefix is not None:
                module_deps.setdefault(prefix, set()).add(dep)


        plugin = self.fgmanager.manager.plugin
        collector_plugin = SuggestionPlugin(function)

        for modid, callers in module_deps.items():
            modstate = self.fgmanager.graph[modid]
            plugin._plugins.insert(0, collector_plugin)
            try:
                tree = self.ensure_tree(modstate)
                self.analyze_module(modstate, callers)
            finally:
                plugin._plugins.pop(0)

        # print()
        # print("COLLECTED:", collector_plugin.mystery_hits)

        return dedup(
            ["%s:%s: %s" % (path, line, self.format_args(arg_kinds, arg_names, arg_types))
             for path, line, arg_kinds, _, arg_names, arg_types in collector_plugin.mystery_hits]
        )

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

    def analyze_module(self, state: State, callers: Set[str]) -> None:
        deferred_set = set()
        for caller in callers:
            try:
                modname, classname, funcname, node = self.find_node(caller)
            except SuggestionFailure:
                continue
            deferred_set.add(mypy.checker.FineGrainedDeferredNode(node, classname, None))
        for deferred_node in deferred_set:
            state.type_checker().check_second_pass([deferred_node])

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

    def ensure_tree(self, state: State) -> MypyFile:
        if not state.tree or state.tree.is_cache_skeleton:
            assert state.path is not None
            res = self.fgmanager.update([(state.id, state.path)], [])
            if res:
                raise SuggestionFailure("Error while trying to load %s" % state.id)
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
