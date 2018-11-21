import re

from typing import List, Optional, Set, Tuple

import mypy.build
import mypy.checker
import mypy.types
from mypy.nodes import (ARG_POS, ARG_STAR, ARG_NAMED, ARG_STAR2, ARG_NAMED_OPT,
                        FuncDef, MypyFile, SymbolTable, SymbolNode, TypeInfo,
                        MysteryTuple)
from mypy.server.update import FineGrainedBuildManager


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

        mystery_hits = []  # type: List[MysteryTuple]
        for modid, modstate in self.fgmanager.graph.items():
            deps = modstate.fine_grained_deps
            if depskey in deps:
                callers = deps[depskey]
                assert modstate.tree is not None
                try:
                    modstate.tree.mystery_target = target
                    modstate.tree.mystery_hits = mystery_hits
                    self.analyze_module(modstate, callers)
                finally:
                    modstate.tree.mystery_target = None
                    modstate.tree.mystery_hits = []

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

    def analyze_module(self, state: mypy.build.State, callers: Set[str]) -> None:
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
        parts = key.split('.')
        tail = []  # type: List[str]
        # Initially <parts> is the whole key and <tail> is empty.
        # It's a hit if <parts> is a known module, and <tail> is
        # either <class>.<method> or just <function>.  Repeatedly
        # investigate <parts>.<tail> and if it's not a hit move the
        # last part from <parts> into <tail>, until <parts> is
        # exhausted.
        while parts:
            modname = '.'.join(parts)
            if modname in graph:
                # Good, <parts> represents a module and <tail> is non-empty.
                if len(tail) == 2:
                    classname, funcname = tail
                    return (modname, classname, funcname,
                            self.find_method_node(graph[modname], classname, funcname))
                if len(tail) == 1:
                    funcname = tail[0]
                    return (modname, None, funcname,
                            self.find_function_node(graph[modname], funcname))
            # Push one part to the right.
            tail.insert(0, parts.pop())
        raise SuggestionFailure("Cannot find %s" % (key,))

    def find_method_node(self, state: mypy.build.State,
                         classname: str, funcname: str) -> FuncDef:
        modname = state.id
        tree = state.tree  # type: Optional[MypyFile]
        assert tree is not None
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

    def find_function_node(self, state: mypy.build.State, funcname: str) -> FuncDef:
        modname = state.id
        tree = state.tree  # type: Optional[MypyFile]
        assert tree is not None
        moduledict = tree.names  # type: SymbolTable
        if funcname not in moduledict:
            raise SuggestionFailure("Unknown function %s.%s" % (modname, funcname))
        node = moduledict[funcname].node
        if not isinstance(node, FuncDef):
            raise SuggestionFailure("Object %s.%s is not a function" % (modname, funcname))
        return node
