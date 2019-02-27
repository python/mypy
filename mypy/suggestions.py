import re

from typing import List, Optional, Set, Tuple, Dict

import mypy.checker
import mypy.types
from mypy.build import State
from mypy.nodes import (ARG_POS, ARG_STAR, ARG_NAMED, ARG_STAR2, ARG_NAMED_OPT,
                        FuncDef, MypyFile, SymbolTable, SymbolNode, TypeInfo,
                        MysteryTuple)
from mypy.server.update import FineGrainedBuildManager
from mypy.server.target import module_prefix, split_target


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


        mystery_hits = []  # type: List[MysteryTuple]
        for modid, callers in module_deps.items():
            modstate = self.fgmanager.graph[modid]
            tree = self.ensure_tree(modstate)
            try:
                tree.mystery_target = target
                tree.mystery_hits = mystery_hits
                self.analyze_module(modstate, callers)
            finally:
                tree.mystery_target = None
                tree.mystery_hits = []

        return ["%s:%s: %s" % (path, line, self.format_args(arg_kinds, arg_names, arg_types))
                for path, line, arg_kinds, arg_names, arg_types in mystery_hits]

    def format_args(self,
                    arg_kinds: List[int],
                    arg_names: List[Optional[str]],
                    arg_types: List[mypy.types.Type]) -> str:
        args = []  # type: List[str]
        for i, typ in enumerate(arg_types):
            arg = str(typ)
            arg = arg.replace("*", "")  # Get rid of "inferred" indicators.
            if i < len(arg_kinds):
                kind = arg_kinds[i]
            else:
                kind = ARG_POS
            if kind == ARG_STAR:
                arg = '*' + arg
            elif kind == ARG_STAR2:
                arg = '**' + arg
            elif kind in (ARG_NAMED, ARG_NAMED_OPT):
                if i < len(arg_names) and arg_names[i]:
                    arg = "%s=%s" % (arg_names[i], arg)
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
