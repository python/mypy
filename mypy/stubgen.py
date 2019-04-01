"""Generator of dynamically typed draft stubs for arbitrary modules.

The logic of this script can be split in three steps:
* parsing options and finding sources:
  - use runtime imports be default (to find also C modules)
  - or use mypy's mechanisms, if importing is prohibited
* (optionally) semantically analysing the sources using mypy (as a single set)
* emitting the stubs text:
  - for Python modules: from ASTs using StubGenerator
  - for C modules using runtime introspection and (optionally) Sphinx docs

During first and third steps some problematic files can be skipped, but any
blocking error during second step will cause the whole program to stop.

Basic usage:

  $ stubgen foo.py bar.py some_directory
  => Generate out/foo.pyi, out/bar.pyi, and stubs for some_directory (recursively).

  $ stubgen -m urllib.parse
  => Generate out/urllib/parse.pyi.

  $ stubgen -p urllib
  => Generate stubs for whole urlib package (recursively).

For Python 2 mode, use --py2:

  $ stubgen --py2 -m textwrap

For C modules, you can get more precise function signatures by parsing .rst (Sphinx)
documentation for extra information. For this, use the --doc-dir option:

  $ stubgen --doc-dir <DIR>/Python-3.4.2/Doc/library -m curses

Note: The generated stubs should be verified manually.

TODO:
 - support stubs for C modules in Python 2 mode
 - detect 'if PY2 / is_py2' etc. and either preserve those or only include Python 2 or 3 case
 - maybe use .rst docs also for Python modules
 - maybe export more imported names if there is no __all__ (this affects ssl.SSLError, for example)
   - a quick and dirty heuristic would be to turn this on if a module has something like
     'from x import y as _y'
 - we don't seem to always detect properties ('closed' in 'io', for example)
"""

import glob
import os
import os.path
import sys
import traceback
import argparse
from collections import defaultdict

from typing import (
    Any, List, Dict, Tuple, Iterable, Mapping, Optional, Set, cast
)

import mypy.build
import mypy.parse
import mypy.errors
import mypy.traverser
import mypy.util
from mypy import defaults
from mypy.modulefinder import FindModuleCache, SearchPaths, BuildSource, default_lib_path
from mypy.nodes import (
    Expression, IntExpr, UnaryExpr, StrExpr, BytesExpr, NameExpr, FloatExpr, MemberExpr,
    TupleExpr, ListExpr, ComparisonExpr, CallExpr, IndexExpr, EllipsisExpr,
    ClassDef, MypyFile, Decorator, AssignmentStmt, TypeInfo,
    IfStmt, ReturnStmt, ImportAll, ImportFrom, Import, FuncDef, FuncBase, TempNode,
    ARG_POS, ARG_STAR, ARG_STAR2, ARG_NAMED, ARG_NAMED_OPT
)
from mypy.stubgenc import generate_stub_for_c_module
from mypy.stubutil import (
    write_header, default_py2_interpreter, CantImport, generate_guarded,
    walk_packages, find_module_path_and_all_py2, find_module_path_and_all_py3,
    report_missing, fail_missing
)
from mypy.stubdoc import parse_all_signatures, find_unique_signatures, Sig
from mypy.options import Options as MypyOptions
from mypy.types import (
    Type, TypeStrVisitor, CallableType,
    UnboundType, NoneTyp, TupleType, TypeList,
)
from mypy.visitor import NodeVisitor
from mypy.find_sources import create_source_list, InvalidSourceList
from mypy.build import build
from mypy.errors import CompileError

MYPY = False
if MYPY:
    from typing_extensions import Final


class Options:
    """Represents stubgen options.

    This class is mutable to simplify testing.
    """
    def __init__(self, pyversion: Tuple[int, int], no_import: bool, doc_dir: str,
                 search_path: List[str], interpreter: str, parse_only: bool, ignore_errors: bool,
                 include_private: bool, output_dir: str, modules: List[str], packages: List[str],
                 files: List[str]) -> None:
        # See parse_options for descriptions of the flags.
        self.pyversion = pyversion
        self.no_import = no_import
        self.doc_dir = doc_dir
        self.search_path = search_path
        self.interpreter = interpreter
        self.decointerpreter = interpreter
        self.parse_only = parse_only
        self.ignore_errors = ignore_errors
        self.include_private = include_private
        self.output_dir = output_dir
        self.modules = modules
        self.packages = packages
        self.files = files


class StubSource(BuildSource):
    """A single source for stub: can be a Python or C module.

    A simple extension of BuildSource that also carries the AST and
    the value of __all__ detected at runtime.
    """
    def __init__(self, module: str, path: Optional[str] = None,
                 runtime_all: Optional[List[str]] = None) -> None:
        super().__init__(path, module, None)
        self.runtime_all = runtime_all
        self.ast = None  # type: Optional[MypyFile]


# What was generated previously in the stub file. We keep track of these to generate
# nicely formatted output (add empty line between non-empty classes, for example).
EMPTY = 'EMPTY'  # type: Final
FUNC = 'FUNC'  # type: Final
CLASS = 'CLASS'  # type: Final
EMPTY_CLASS = 'EMPTY_CLASS'  # type: Final
VAR = 'VAR'  # type: Final
NOT_IN_ALL = 'NOT_IN_ALL'  # type: Final

# Indicates that we failed to generate a reasonable output
# for a given node. These should be manually replaced by a user.

ERROR_MARKER = '<ERROR>'  # type: Final


class AnnotationPrinter(TypeStrVisitor):
    """Visitor used to print existing annotations in a file.

    The main difference from TypeStrVisitor is a better treatment of
    unbound types.

    Notes:
    * This visitor doesn't add imports necessary for annotations, this is done separately
      by ImportTracker.
    * It can print all kinds of types, but the generated strings may not be valid (notably
      callable types) since it prints the same string that reveal_type() does.
    * For Instance types it prints the fully qualified names.
    """
    # TODO: Generate valid string representation for callable types.
    # TODO: Use short names for Instances.
    def __init__(self, stubgen: 'StubGenerator') -> None:
        super().__init__()
        self.stubgen = stubgen

    def visit_unbound_type(self, t: UnboundType) -> str:
        s = t.name
        self.stubgen.import_tracker.require_name(s)
        if t.args:
            s += '[{}]'.format(self.list_str(t.args))
        return s

    def visit_none_type(self, t: NoneTyp) -> str:
        return "None"

    def visit_type_list(self, t: TypeList) -> str:
        return '[{}]'.format(self.list_str(t.items))


class AliasPrinter(NodeVisitor[str]):
    """Visitor used to collect type aliases _and_ type variable definitions.

    Visit r.h.s of the definition to get the string representation of type alias.
    """
    def __init__(self, stubgen: 'StubGenerator') -> None:
        self.stubgen = stubgen
        super().__init__()

    def visit_call_expr(self, node: CallExpr) -> str:
        # Call expressions are not usually types, but we also treat `X = TypeVar(...)` as a
        # type alias that has to be preserved (even if TypeVar is not the same as an alias)
        callee = node.callee.accept(self)
        args = []
        for name, arg, kind in zip(node.arg_names, node.args, node.arg_kinds):
            if kind == ARG_POS:
                args.append(arg.accept(self))
            elif kind == ARG_STAR:
                args.append('*' + arg.accept(self))
            elif kind == ARG_STAR2:
                args.append('**' + arg.accept(self))
            elif kind == ARG_NAMED:
                args.append('{}={}'.format(name, arg.accept(self)))
            else:
                raise ValueError("Unknown argument kind %d in call" % kind)
        return "{}({})".format(callee, ", ".join(args))

    def visit_name_expr(self, node: NameExpr) -> str:
        self.stubgen.import_tracker.require_name(node.name)
        return node.name

    def visit_member_expr(self, o: MemberExpr) -> str:
        node = o  # type: Expression
        trailer = ''
        while isinstance(node, MemberExpr):
            trailer = '.' + node.name + trailer
            node = node.expr
        if not isinstance(node, NameExpr):
            return ERROR_MARKER
        self.stubgen.import_tracker.require_name(node.name)
        return node.name + trailer

    def visit_str_expr(self, node: StrExpr) -> str:
        return repr(node.value)

    def visit_index_expr(self, node: IndexExpr) -> str:
        base = node.base.accept(self)
        index = node.index.accept(self)
        return "{}[{}]".format(base, index)

    def visit_tuple_expr(self, node: TupleExpr) -> str:
        return ", ".join(n.accept(self) for n in node.items)

    def visit_list_expr(self, node: ListExpr) -> str:
        return "[{}]".format(", ".join(n.accept(self) for n in node.items))

    def visit_ellipsis(self, node: EllipsisExpr) -> str:
        return "..."


class ImportTracker:
    """Record necessary imports during stub generation."""

    def __init__(self) -> None:
        # module_for['foo'] has the module name where 'foo' was imported from, or None if
        # 'foo' is a module imported directly; examples
        #     'from pkg.m import f as foo' ==> module_for['foo'] == 'pkg.m'
        #     'from m import f' ==> module_for['f'] == 'm'
        #     'import m' ==> module_for['m'] == None
        self.module_for = {}  # type: Dict[str, Optional[str]]

        # direct_imports['foo'] is the module path used when the name 'foo' was added to the
        # namespace.
        #   import foo.bar.baz  ==> direct_imports['foo'] == 'foo.bar.baz'
        self.direct_imports = {}  # type: Dict[str, str]

        # reverse_alias['foo'] is the name that 'foo' had originally when imported with an
        # alias; examples
        #     'import numpy as np' ==> reverse_alias['np'] == 'numpy'
        #     'from decimal import Decimal as D' ==> reverse_alias['D'] == 'Decimal'
        self.reverse_alias = {}  # type: Dict[str, str]

        # required_names is the set of names that are actually used in a type annotation
        self.required_names = set()  # type: Set[str]

        # Names that should be reexported if they come from another module
        self.reexports = set()  # type: Set[str]

    def add_import_from(self, module: str, names: List[Tuple[str, Optional[str]]]) -> None:
        for name, alias in names:
            self.module_for[alias or name] = module
            if alias:
                self.reverse_alias[alias] = name

    def add_import(self, module: str, alias: Optional[str] = None) -> None:
        name = module.split('.')[0]
        self.module_for[alias or name] = None
        self.direct_imports[name] = module
        if alias:
            self.reverse_alias[alias] = name

    def require_name(self, name: str) -> None:
        self.required_names.add(name.split('.')[0])

    def reexport(self, name: str) -> None:
        """Mark a given non qualified name as needed in __all__.

        This means that in case it comes from a module, it should be
        imported with an alias even is the alias is the same as the name.
        """
        self.require_name(name)
        self.reexports.add(name)

    def import_lines(self) -> List[str]:
        """The list of required import lines (as strings with python code)."""
        result = []

        # To summarize multiple names imported from a same module, we collect those
        # in the `module_map` dictionary, mapping a module path to the list of names that should
        # be imported from it. the names can also be alias in the form 'original as alias'
        module_map = defaultdict(list)  # type: Mapping[str, List[str]]

        for name in sorted(self.required_names):
            # If we haven't seen this name in an import statement, ignore it
            if name not in self.module_for:
                continue

            m = self.module_for[name]
            if m is not None:
                # This name was found in a from ... import ...
                # Collect the name in the module_map
                if name in self.reverse_alias:
                    name = '{} as {}'.format(self.reverse_alias[name], name)
                elif name in self.reexports:
                    name = '{} as {}'.format(name, name)
                module_map[m].append(name)
            else:
                # This name was found in an import ...
                # We can already generate the import line
                if name in self.reverse_alias:
                    name, alias = self.reverse_alias[name], name
                    result.append("import {} as {}\n".format(self.direct_imports[name], alias))
                elif name in self.reexports:
                    assert '.' not in name  # Because reexports only has nonqualified names
                    result.append("import {} as {}\n".format(name, name))
                else:
                    result.append("import {}\n".format(self.direct_imports[name]))

        # Now generate all the from ... import ... lines collected in module_map
        for module, names in sorted(module_map.items()):
            result.append("from {} import {}\n".format(module, ', '.join(sorted(names))))
        return result


class StubGenerator(mypy.traverser.TraverserVisitor):
    def __init__(self, _all_: Optional[List[str]], pyversion: Tuple[int, int],
                 include_private: bool = False, analyzed: bool = False) -> None:
        # Best known value of __all__.
        self._all_ = _all_
        self._output = []  # type: List[str]
        self._import_lines = []  # type: List[str]
        # Current indent level (indent is hardcoded to 4 spaces).
        self._indent = ''
        # Stack of defined variables (per scope).
        self._vars = [[]]  # type: List[List[str]]
        # What was generated previously in the stub file.
        self._state = EMPTY
        self._toplevel_names = []  # type: List[str]
        self._pyversion = pyversion
        self._include_private = include_private
        self.import_tracker = ImportTracker()
        # Was the tree semantically analysed before?
        self.analyzed = analyzed
        # Add imports that could be implicitly generated
        self.import_tracker.add_import_from("collections", [("namedtuple", None)])
        typing_imports = "Any Optional TypeVar".split()
        self.import_tracker.add_import_from("typing", [(t, None) for t in typing_imports])
        # Names in __all__ are required
        for name in _all_ or ():
            self.import_tracker.reexport(name)

    def visit_mypy_file(self, o: MypyFile) -> None:
        super().visit_mypy_file(o)
        undefined_names = [name for name in self._all_ or []
                           if name not in self._toplevel_names]
        if undefined_names:
            if self._state != EMPTY:
                self.add('\n')
            self.add('# Names in __all__ with no definition:\n')
            for name in sorted(undefined_names):
                self.add('#   %s\n' % name)

    def visit_func_def(self, o: FuncDef, is_abstract: bool = False) -> None:
        if self.is_private_name(o.name()):
            return
        if self.is_not_in_all(o.name()):
            return
        if self.is_recorded_name(o.name()):
            return
        if not self._indent and self._state not in (EMPTY, FUNC) and not o.is_awaitable_coroutine:
            self.add('\n')
        if not self.is_top_level():
            self_inits = find_self_initializers(o)
            for init, value in self_inits:
                init_code = self.get_init(init, value)
                if init_code:
                    self.add(init_code)
        self.add("%s%sdef %s(" % (self._indent, 'async ' if o.is_coroutine else '', o.name()))
        self.record_name(o.name())
        args = []  # type: List[str]
        for i, arg_ in enumerate(o.arguments):
            var = arg_.variable
            kind = arg_.kind
            name = var.name()
            annotated_type = (o.unanalyzed_type.arg_types[i]
                              if isinstance(o.unanalyzed_type, CallableType) else None)
            is_self_arg = i == 0 and name == 'self'
            is_cls_arg = i == 0 and name == 'cls'
            if (annotated_type is None
                    and not arg_.initializer
                    and not is_self_arg
                    and not is_cls_arg):
                self.add_typing_import("Any")
                annotation = ": Any"
            elif annotated_type and not is_self_arg:
                annotation = ": {}".format(self.print_annotation(annotated_type))
            else:
                annotation = ""
            if arg_.initializer:
                initializer = '...'
                if kind in (ARG_NAMED, ARG_NAMED_OPT) and not any(arg.startswith('*')
                                                                  for arg in args):
                    args.append('*')
                if not annotation:
                    typename = self.get_str_type_of_node(arg_.initializer, True)
                    annotation = ': {} = ...'.format(typename)
                else:
                    annotation += '={}'.format(initializer)
                arg = name + annotation
            elif kind == ARG_STAR:
                arg = '*%s%s' % (name, annotation)
            elif kind == ARG_STAR2:
                arg = '**%s%s' % (name, annotation)
            else:
                arg = name + annotation
            args.append(arg)
        retname = None
        if isinstance(o.unanalyzed_type, CallableType):
            retname = self.print_annotation(o.unanalyzed_type.ret_type)
        elif isinstance(o, FuncDef) and o.is_abstract:
            # Always assume abstract methods return Any unless explicitly annotated.
            retname = 'Any'
            self.add_typing_import("Any")
        elif o.name() == '__init__' or not has_return_statement(o) and not is_abstract:
            retname = 'None'
        retfield = ''
        if retname is not None:
            retfield = ' -> ' + retname

        self.add(', '.join(args))
        self.add("){}: ...\n".format(retfield))
        self._state = FUNC

    def visit_decorator(self, o: Decorator) -> None:
        if self.is_private_name(o.func.name()):
            return
        is_abstract = False
        for decorator in o.original_decorators:
            if isinstance(decorator, NameExpr):
                if decorator.name in ('property',
                                      'staticmethod',
                                      'classmethod'):
                    self.add('%s@%s\n' % (self._indent, decorator.name))
                elif self.import_tracker.module_for.get(decorator.name) in ('asyncio',
                                                                            'asyncio.coroutines',
                                                                            'types'):
                    self.add_coroutine_decorator(o.func, decorator.name, decorator.name)
                elif (self.import_tracker.module_for.get(decorator.name) == 'abc' and
                      (decorator.name == 'abstractmethod' or
                       self.import_tracker.reverse_alias.get(decorator.name) == 'abstractmethod')):
                    self.add('%s@%s\n' % (self._indent, decorator.name))
                    self.import_tracker.require_name(decorator.name)
                    is_abstract = True
            elif isinstance(decorator, MemberExpr):
                if decorator.name == 'setter' and isinstance(decorator.expr, NameExpr):
                    self.add('%s@%s.setter\n' % (self._indent, decorator.expr.name))
                elif (isinstance(decorator.expr, NameExpr) and
                      (decorator.expr.name == 'abc' or
                       self.import_tracker.reverse_alias.get('abc')) and
                      decorator.name == 'abstractmethod'):
                    self.import_tracker.require_name(decorator.expr.name)
                    self.add('%s@%s.%s\n' % (self._indent, decorator.expr.name, decorator.name))
                    is_abstract = True
                elif decorator.name == 'coroutine':
                    if (isinstance(decorator.expr, MemberExpr) and
                        decorator.expr.name == 'coroutines' and
                        isinstance(decorator.expr.expr, NameExpr) and
                            (decorator.expr.expr.name == 'asyncio' or
                             self.import_tracker.reverse_alias.get(decorator.expr.expr.name) ==
                                'asyncio')):
                        self.add_coroutine_decorator(o.func,
                                                     '%s.coroutines.coroutine' %
                                                     (decorator.expr.expr.name,),
                                                     decorator.expr.expr.name)
                    elif (isinstance(decorator.expr, NameExpr) and
                          (decorator.expr.name in ('asyncio', 'types') or
                           self.import_tracker.reverse_alias.get(decorator.expr.name) in
                            ('asyncio', 'asyncio.coroutines', 'types'))):
                        self.add_coroutine_decorator(o.func,
                                                     decorator.expr.name + '.coroutine',
                                                     decorator.expr.name)
        self.visit_func_def(o.func, is_abstract=is_abstract)

    def visit_class_def(self, o: ClassDef) -> None:
        sep = None  # type: Optional[int]
        if not self._indent and self._state != EMPTY:
            sep = len(self._output)
            self.add('\n')
        self.add('%sclass %s' % (self._indent, o.name))
        self.record_name(o.name)
        base_types = self.get_base_types(o)
        if base_types:
            for base in base_types:
                self.import_tracker.require_name(base)
        if isinstance(o.metaclass, (NameExpr, MemberExpr)):
            meta = o.metaclass.accept(AliasPrinter(self))
            base_types.append('metaclass=' + meta)
        elif self.analyzed and o.info.is_abstract:
            base_types.append('metaclass=abc.ABCMeta')
            self.import_tracker.add_import('abc')
            self.import_tracker.require_name('abc')
        if base_types:
            self.add('(%s)' % ', '.join(base_types))
        self.add(':\n')
        n = len(self._output)
        self._indent += '    '
        self._vars.append([])
        super().visit_class_def(o)
        self._indent = self._indent[:-4]
        self._vars.pop()
        self._vars[-1].append(o.name)
        if len(self._output) == n:
            if self._state == EMPTY_CLASS and sep is not None:
                self._output[sep] = ''
            self._output[-1] = self._output[-1][:-1] + ' ...\n'
            self._state = EMPTY_CLASS
        else:
            self._state = CLASS

    def get_base_types(self, cdef: ClassDef) -> List[str]:
        """Get list of base classes for a class."""
        base_types = []  # type: List[str]
        for base in cdef.base_type_exprs:
            if isinstance(base, NameExpr):
                if base.name != 'object':
                    base_types.append(base.name)
            elif isinstance(base, MemberExpr):
                modname = get_qualified_name(base.expr)
                base_types.append('%s.%s' % (modname, base.name))
            elif isinstance(base, IndexExpr):
                p = AliasPrinter(self)
                base_types.append(base.accept(p))
        return base_types

    def visit_assignment_stmt(self, o: AssignmentStmt) -> None:
        foundl = []

        for lvalue in o.lvalues:
            if isinstance(lvalue, NameExpr) and self.is_namedtuple(o.rvalue):
                assert isinstance(o.rvalue, CallExpr)
                self.process_namedtuple(lvalue, o.rvalue)
                continue
            if (self.is_top_level() and
                    isinstance(lvalue, NameExpr) and not self.is_private_name(lvalue.name) and
                    # it is never an alias with explicit annotation
                    not o.unanalyzed_type and self.is_alias_expression(o.rvalue)):
                self.process_typealias(lvalue, o.rvalue)
                continue
            if isinstance(lvalue, TupleExpr) or isinstance(lvalue, ListExpr):
                items = lvalue.items
                if isinstance(o.unanalyzed_type, TupleType):
                    annotations = o.unanalyzed_type.items  # type: Iterable[Optional[Type]]
                else:
                    annotations = [None] * len(items)
            else:
                items = [lvalue]
                annotations = [o.unanalyzed_type]
            sep = False
            found = False
            for item, annotation in zip(items, annotations):
                if isinstance(item, NameExpr):
                    init = self.get_init(item.name, o.rvalue, annotation)
                    if init:
                        found = True
                        if not sep and not self._indent and \
                                self._state not in (EMPTY, VAR):
                            init = '\n' + init
                            sep = True
                        self.add(init)
                        self.record_name(item.name)
            foundl.append(found)

        if all(foundl):
            self._state = VAR

    def is_namedtuple(self, expr: Expression) -> bool:
        if not isinstance(expr, CallExpr):
            return False
        callee = expr.callee
        return ((isinstance(callee, NameExpr) and callee.name.endswith('namedtuple')) or
                (isinstance(callee, MemberExpr) and callee.name == 'namedtuple'))

    def process_namedtuple(self, lvalue: NameExpr, rvalue: CallExpr) -> None:
        self.import_tracker.require_name('namedtuple')
        if self._state != EMPTY:
            self.add('\n')
        name = repr(getattr(rvalue.args[0], 'value', ERROR_MARKER))
        if isinstance(rvalue.args[1], StrExpr):
            items = repr(rvalue.args[1].value)
        elif isinstance(rvalue.args[1], (ListExpr, TupleExpr)):
            list_items = cast(List[StrExpr], rvalue.args[1].items)
            items = '[%s]' % ', '.join(repr(item.value) for item in list_items)
        else:
            items = ERROR_MARKER
        self.add('%s = namedtuple(%s, %s)\n' % (lvalue.name, name, items))
        self._state = CLASS

    def is_alias_expression(self, expr: Expression, top_level: bool = True) -> bool:
        """Return True for things that look like target for an alias.

        Used to know if assignments look like type aliases, function alias,
        or module alias.
        """
        # Assignment of TypeVar(...) are passed through
        if (isinstance(expr, CallExpr) and
                isinstance(expr.callee, NameExpr) and
                expr.callee.name == 'TypeVar'):
            return True
        elif isinstance(expr, EllipsisExpr):
            return not top_level
        elif isinstance(expr, NameExpr):
            if expr.name in ('True', 'False'):
                return False
            elif expr.name == 'None':
                return not top_level
            else:
                return not self.is_private_name(expr.name)
        elif isinstance(expr, MemberExpr) and self.analyzed:
            # Also add function and module aliases.
            return ((top_level and isinstance(expr.node, (FuncDef, Decorator, MypyFile))
                     or isinstance(expr.node, TypeInfo)) and
                    not self.is_private_member(expr.node.fullname()))
        elif (isinstance(expr, IndexExpr) and isinstance(expr.base, NameExpr) and
              not self.is_private_name(expr.base.name)):
            if isinstance(expr.index, TupleExpr):
                indices = expr.index.items
            else:
                indices = [expr.index]
            if expr.base.name == 'Callable' and len(indices) == 2:
                args, ret = indices
                if isinstance(args, EllipsisExpr):
                    indices = [ret]
                elif isinstance(args, ListExpr):
                    indices = args.items + [ret]
                else:
                    return False
            return all(self.is_alias_expression(i, top_level=False) for i in indices)
        else:
            return False

    def process_typealias(self, lvalue: NameExpr, rvalue: Expression) -> None:
        p = AliasPrinter(self)
        self.add("{} = {}\n".format(lvalue.name, rvalue.accept(p)))
        self.record_name(lvalue.name)
        self._vars[-1].append(lvalue.name)

    def visit_if_stmt(self, o: IfStmt) -> None:
        # Ignore if __name__ == '__main__'.
        expr = o.expr[0]
        if (isinstance(expr, ComparisonExpr) and
                isinstance(expr.operands[0], NameExpr) and
                isinstance(expr.operands[1], StrExpr) and
                expr.operands[0].name == '__name__' and
                '__main__' in expr.operands[1].value):
            return
        super().visit_if_stmt(o)

    def visit_import_all(self, o: ImportAll) -> None:
        self.add_import_line('from %s%s import *\n' % ('.' * o.relative, o.id))

    def visit_import_from(self, o: ImportFrom) -> None:
        exported_names = set()  # type: Set[str]
        self.import_tracker.add_import_from('.' * o.relative + o.id, o.names)
        self._vars[-1].extend(alias or name for name, alias in o.names)
        for name, alias in o.names:
            self.record_name(alias or name)

        if self._all_:
            # Include import froms that import names defined in __all__.
            names = [name for name, alias in o.names
                     if name in self._all_ and alias is None]
            exported_names.update(names)
        else:
            # Include import from targets that import from a submodule of a package.
            if o.relative:
                sub_names = [name for name, alias in o.names
                             if alias is None]
                exported_names.update(sub_names)
                if o.id:
                    for name in sub_names:
                        self.import_tracker.require_name(name)

    def visit_import(self, o: Import) -> None:
        for id, as_id in o.ids:
            self.import_tracker.add_import(id, as_id)
            if as_id is None:
                target_name = id.split('.')[0]
            else:
                target_name = as_id
            self._vars[-1].append(target_name)
            self.record_name(target_name)

    def get_init(self, lvalue: str, rvalue: Expression,
                 annotation: Optional[Type] = None) -> Optional[str]:
        """Return initializer for a variable.

        Return None if we've generated one already or if the variable is internal.
        """
        if lvalue in self._vars[-1]:
            # We've generated an initializer already for this variable.
            return None
        # TODO: Only do this at module top level.
        if self.is_private_name(lvalue) or self.is_not_in_all(lvalue):
            return None
        self._vars[-1].append(lvalue)
        if annotation is not None:
            typename = self.print_annotation(annotation)
            if (isinstance(annotation, UnboundType) and not annotation.args and
                    annotation.name == 'Final' and
                    self.import_tracker.module_for.get('Final') in ('typing, typing_extensions')):
                # Final without type argument is invalid in stubs.
                final_arg = self.get_str_type_of_node(rvalue)
                typename += '[{}]'.format(final_arg)
        else:
            typename = self.get_str_type_of_node(rvalue)
        has_rhs = not (isinstance(rvalue, TempNode) and rvalue.no_rhs)
        initializer = " = ..." if has_rhs and not self.is_top_level() else ""
        return '%s%s: %s%s\n' % (self._indent, lvalue, typename, initializer)

    def add(self, string: str) -> None:
        """Add text to generated stub."""
        self._output.append(string)

    def add_typing_import(self, name: str) -> None:
        """Add a name to be imported from typing, unless it's imported already.

        The import will be internal to the stub.
        """
        self.import_tracker.require_name(name)

    def add_import_line(self, line: str) -> None:
        """Add a line of text to the import section, unless it's already there."""
        if line not in self._import_lines:
            self._import_lines.append(line)

    def add_coroutine_decorator(self, func: FuncDef, name: str, require_name: str) -> None:
        func.is_awaitable_coroutine = True
        if not self._indent and self._state not in (EMPTY, FUNC):
            self.add('\n')
        self.add('%s@%s\n' % (self._indent, name))
        self.import_tracker.require_name(require_name)

    def output(self) -> str:
        """Return the text for the stub."""
        imports = ''
        if self._import_lines:
            imports += ''.join(self._import_lines)
        imports += ''.join(self.import_tracker.import_lines())
        if imports and self._output:
            imports += '\n'
        return imports + ''.join(self._output)

    def is_not_in_all(self, name: str) -> bool:
        if self.is_private_name(name):
            return False
        if self._all_:
            return self.is_top_level() and name not in self._all_
        return False

    def is_private_name(self, name: str) -> bool:
        if self._include_private:
            return False
        return name.startswith('_') and (not name.endswith('__')
                                         or name in ('__all__',
                                                     '__author__',
                                                     '__version__',
                                                     '__str__',
                                                     '__repr__',
                                                     '__getstate__',
                                                     '__setstate__',
                                                     '__slots__'))

    def is_private_member(self, fullname: str) -> bool:
        parts = fullname.split('.')
        for part in parts:
            if self.is_private_name(part):
                return True
        return False

    def get_str_type_of_node(self, rvalue: Expression,
                             can_infer_optional: bool = False) -> str:
        if isinstance(rvalue, IntExpr):
            return 'int'
        if isinstance(rvalue, StrExpr):
            return 'str'
        if isinstance(rvalue, BytesExpr):
            return 'bytes'
        if isinstance(rvalue, FloatExpr):
            return 'float'
        if isinstance(rvalue, UnaryExpr) and isinstance(rvalue.expr, IntExpr):
            return 'int'
        if isinstance(rvalue, NameExpr) and rvalue.name in ('True', 'False'):
            return 'bool'
        if can_infer_optional and \
                isinstance(rvalue, NameExpr) and rvalue.name == 'None':
            self.add_typing_import('Optional')
            self.add_typing_import('Any')
            return 'Optional[Any]'
        self.add_typing_import('Any')
        return 'Any'

    def print_annotation(self, t: Type) -> str:
        printer = AnnotationPrinter(self)
        return t.accept(printer)

    def is_top_level(self) -> bool:
        """Are we processing the top level of a file?"""
        return self._indent == ''

    def record_name(self, name: str) -> None:
        """Mark a name as defined.

        This only does anything if at the top level of a module.
        """
        if self.is_top_level():
            self._toplevel_names.append(name)

    def is_recorded_name(self, name: str) -> bool:
        """Has this name been recorded previously?"""
        return self.is_top_level() and name in self._toplevel_names


class SelfTraverser(mypy.traverser.TraverserVisitor):
    def __init__(self) -> None:
        self.results = []  # type: List[Tuple[str, Expression]]

    def visit_assignment_stmt(self, o: AssignmentStmt) -> None:
        lvalue = o.lvalues[0]
        if (isinstance(lvalue, MemberExpr) and
                isinstance(lvalue.expr, NameExpr) and
                lvalue.expr.name == 'self'):
            self.results.append((lvalue.name, o.rvalue))


def find_self_initializers(fdef: FuncBase) -> List[Tuple[str, Expression]]:
    """Find attribute initializers in a method.

    Return a list of pairs (attribute name, r.h.s. expression).
    """
    traverser = SelfTraverser()
    fdef.accept(traverser)
    return traverser.results


class ReturnSeeker(mypy.traverser.TraverserVisitor):
    def __init__(self) -> None:
        self.found = False

    def visit_return_stmt(self, o: ReturnStmt) -> None:
        if o.expr is None or isinstance(o.expr, NameExpr) and o.expr.name == 'None':
            return
        self.found = True


def has_return_statement(fdef: FuncBase) -> bool:
    """Find if a function has a non-trivial return statement.

    Plain 'return' and 'return None' don't count.
    """
    seeker = ReturnSeeker()
    fdef.accept(seeker)
    return seeker.found


def get_qualified_name(o: Expression) -> str:
    if isinstance(o, NameExpr):
        return o.name
    elif isinstance(o, MemberExpr):
        return '%s.%s' % (get_qualified_name(o.expr), o.name)
    else:
        return ERROR_MARKER


def collect_build_targets(options: Options, mypy_opts: MypyOptions) -> Tuple[List[StubSource],
                                                                             List[StubSource]]:
    """Collect files for which we need to generate stubs.

    Return list of Python modules and C modules.
    """
    if options.packages or options.modules:
        if options.no_import:
            py_modules = find_module_paths_using_search(options.modules,
                                                        options.packages,
                                                        options.search_path,
                                                        options.pyversion)
            c_modules = []  # type: List[StubSource]
        else:
            # Using imports is the default, since we can also find C modules.
            py_modules, c_modules = find_module_paths_using_imports(options.modules,
                                                                    options.packages,
                                                                    options.interpreter,
                                                                    options.pyversion)
    else:
        # Use mypy native source collection for files and directories.
        try:
            source_list = create_source_list(options.files, mypy_opts)
        except InvalidSourceList as e:
            raise SystemExit(str(e))
        py_modules = [StubSource(m.module, m.path) for m in source_list]
        c_modules = []

    return py_modules, c_modules


def find_module_paths_using_imports(modules: List[str], packages: List[str],
                                    interpreter: str,
                                    pyversion: Tuple[int, int],
                                    quiet: bool = True) -> Tuple[List[StubSource],
                                                                 List[StubSource]]:
    """Find path and runtime value of __all__ (if possible) for modules and packages.

    This function uses runtime Python imports to get the information.
    """
    py_modules = []  # type: List[StubSource]
    c_modules = []  # type: List[StubSource]
    modules = modules + list(walk_packages(packages))
    for mod in modules:
        try:
            if pyversion[0] == 2:
                result = find_module_path_and_all_py2(mod, interpreter)
            else:
                result = find_module_path_and_all_py3(mod)
        except CantImport:
            if not quiet:
                traceback.print_exc()
            report_missing(mod)
            continue
        if not result:
            c_modules.append(StubSource(mod))
        else:
            path, runtime_all = result
            py_modules.append(StubSource(mod, path, runtime_all))
    return py_modules, c_modules


def find_module_paths_using_search(modules: List[str], packages: List[str],
                                   search_path: List[str],
                                   pyversion: Tuple[int, int]) -> List[StubSource]:
    """Find sources for modules and packages requested.

    This function just looks for source files at the file system level.
    This is used if user passes --no-import, and will not find C modules.
    Exit if some of the modules or packages can't be found.
    """
    result = []  # type: List[StubSource]
    typeshed_path = default_lib_path(mypy.build.default_data_dir(), pyversion, None)
    search_paths = SearchPaths(('.',) + tuple(search_path), (), (), tuple(typeshed_path))
    cache = FindModuleCache(search_paths)
    for module in modules:
        module_path = cache.find_module(module)
        if not module_path:
            fail_missing(module)
        result.append(StubSource(module, module_path))
    for package in packages:
        p_result = cache.find_modules_recursive(package)
        if not p_result:
            fail_missing(package)
        sources = [StubSource(m.module, m.path) for m in p_result]
        result.extend(sources)
    return result


def mypy_options(stubgen_options: Options) -> MypyOptions:
    """Generate mypy options using the flag passed by user."""
    options = MypyOptions()
    options.follow_imports = 'skip'
    options.incremental = False
    options.ignore_errors = True
    options.semantic_analysis_only = True
    options.python_version = stubgen_options.pyversion
    return options


def parse_source_file(mod: StubSource, mypy_options: MypyOptions) -> None:
    """Parse a source file.

    On success, store AST in the corresponding attribute of the stub source.
    If there are syntax errors, print them and exit.
    """
    assert mod.path is not None, "Not found module was not skipped"
    with open(mod.path, 'rb') as f:
        data = f.read()
    source = mypy.util.decode_python_encoding(data, mypy_options.python_version)
    try:
        mod.ast = mypy.parse.parse(source, fnam=mod.path, module=mod.module,
                                   errors=None, options=mypy_options)
    except mypy.errors.CompileError as e:
        # Syntax error!
        for m in e.messages:
            sys.stderr.write('%s\n' % m)
        sys.exit(1)


def generate_asts_for_modules(py_modules: List[StubSource],
                              parse_only: bool, mypy_options: MypyOptions) -> None:
    """Use mypy to parse (and optionally analyze) source files."""
    if parse_only:
        for mod in py_modules:
            parse_source_file(mod, mypy_options)
        return
    # Perform full semantic analysis of the source set.
    try:
        res = build(list(py_modules), mypy_options)
    except CompileError as e:
        raise SystemExit("Critical error during semantic analysis: {}".format(e))

    for mod in py_modules:
        mod.ast = res.graph[mod.module].tree
        # Use statically inferred __all__ if there is no runtime one.
        if mod.runtime_all is None:
            mod.runtime_all = res.manager.semantic_analyzer.export_map[mod.module]


def generate_stub_from_ast(mod: StubSource,
                           target: str,
                           parse_only: bool = False,
                           pyversion: Tuple[int, int] = defaults.PYTHON3_VERSION,
                           include_private: bool = False,
                           add_header: bool = True) -> None:
    """Use analysed (or just parsed) AST to generate type stub for single file.

    If directory for target doesn't exist it will created. Existing stub
    will be overwritten.
    """
    gen = StubGenerator(mod.runtime_all,
                        pyversion=pyversion,
                        include_private=include_private,
                        analyzed=not parse_only)
    assert mod.ast is not None, "This function must be used only with analyzed modules"
    mod.ast.accept(gen)

    # Write output to file.
    subdir = os.path.dirname(target)
    if subdir and not os.path.isdir(subdir):
        os.makedirs(subdir)
    with open(target, 'w') as file:
        if add_header:
            write_header(file, mod.module, pyversion=pyversion)
        file.write(''.join(gen.output()))


def collect_docs_signatures(doc_dir: str) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Gather all function and class signatures in the docs.

    Return a tuple (function signatures, class signatures).
    Currently only used for C modules.
    """
    all_sigs = []  # type: List[Sig]
    all_class_sigs = []  # type: List[Sig]
    for path in glob.glob('%s/*.rst' % doc_dir):
        with open(path) as f:
            loc_sigs, loc_class_sigs = parse_all_signatures(f.readlines())
        all_sigs += loc_sigs
        all_class_sigs += loc_class_sigs
    sigs = dict(find_unique_signatures(all_sigs))
    class_sigs = dict(find_unique_signatures(all_class_sigs))
    return sigs, class_sigs


def generate_stubs(options: Options,
                   # additional args for testing
                   quiet: bool = False, add_header: bool = True) -> None:
    """Main entry point for the program."""
    mypy_opts = mypy_options(options)
    py_modules, c_modules = collect_build_targets(options, mypy_opts)

    # Collect info from docs (if given):
    sigs = class_sigs = None  # type: Optional[Dict[str, str]]
    if options.doc_dir:
        sigs, class_sigs = collect_docs_signatures(options.doc_dir)

    # Use parsed sources to generate stubs for Python modules.
    generate_asts_for_modules(py_modules, options.parse_only, mypy_opts)
    for mod in py_modules:
        assert mod.path is not None, "Not found module was not skipped"
        target = mod.module.replace('.', '/')
        if os.path.basename(mod.path) == '__init__.py':
            target += '/__init__.pyi'
        else:
            target += '.pyi'
        target = os.path.join(options.output_dir, target)
        with generate_guarded(mod.module, target, options.ignore_errors, quiet):
            generate_stub_from_ast(mod, target,
                                   options.parse_only, options.pyversion,
                                   options.include_private, add_header)

    # Separately analyse C modules using different logic.
    for mod in c_modules:
        target = mod.module.replace('.', '/') + '.pyi'
        target = os.path.join(options.output_dir, target)
        with generate_guarded(mod.module, target, options.ignore_errors, quiet):
            generate_stub_for_c_module(mod.module, target, sigs=sigs, class_sigs=class_sigs,
                                       add_header=add_header)


HEADER = """%(prog)s [-h] [--py2] [more options, see -h]
                     [-m MODULE] [-p PACKAGE] [files ...]"""

DESCRIPTION = """
Generate draft stubs for modules.

Stubs are generated in directory ./out, to avoid overriding files with
manual changes.  This directory is assumed to exist.
"""


def parse_options(args: List[str]) -> Options:
    parser = argparse.ArgumentParser(prog='stubgen',
                                     usage=HEADER,
                                     description=DESCRIPTION)

    parser.add_argument('--py2', action='store_true',
                        help="run in Python 2 mode (default: Python 3 mode)")
    parser.add_argument('--ignore-errors', action='store_true',
                        help="ignore errors when trying to generate stubs for modules")
    parser.add_argument('--no-import', action='store_true',
                        help="don't import the modules, just parse and analyze them "
                             "(doesn't work with C extension modules and might not "
                             "respect __all__)")
    parser.add_argument('--parse-only', action='store_true',
                        help="don't perform semantic analysis of sources, just parse them "
                             "(only applies to Python modules, might affect quality of stubs)")
    parser.add_argument('--include-private', action='store_true',
                        help="generate stubs for objects and members considered private "
                             "(single leading underscore and no trailing underscores)")
    parser.add_argument('--doc-dir', metavar='PATH', default='',
                        help="use .rst documentation in PATH (this may result in "
                             "better stubs in some cases; consider setting this to "
                             "DIR/Python-X.Y.Z/Doc/library)")
    parser.add_argument('--search-path', metavar='PATH', default='',
                        help="specify module search directories, separated by ':' "
                             "(currently only used if --no-import is given)")
    parser.add_argument('--python-executable', metavar='PATH', dest='interpreter', default='',
                        help="use Python interpreter at PATH (only works for "
                             "Python 2 right now)")
    parser.add_argument('-o', '--output', metavar='PATH', dest='output_dir', default='out',
                        help="change the output directory [default: %(default)s]")
    parser.add_argument('-m', '--module', action='append', metavar='MODULE',
                        dest='modules', default=[],
                        help="generate stub for module; can repeat for more modules")
    parser.add_argument('-p', '--package', action='append', metavar='PACKAGE',
                        dest='packages', default=[],
                        help="generate stubs for package recursively; can be repeated")
    parser.add_argument(metavar='files', nargs='*', dest='files',
                        help="generate stubs for given files or directories")

    ns = parser.parse_args(args)

    pyversion = defaults.PYTHON2_VERSION if ns.py2 else defaults.PYTHON3_VERSION
    if not ns.interpreter:
        ns.interpreter = sys.executable if pyversion[0] == 3 else default_py2_interpreter()
    if ns.modules + ns.packages and ns.files:
        parser.error("May only specify one of: modules/packages or files.")

    # Create the output folder if it doesn't already exist.
    if not os.path.exists(ns.output_dir):
        os.makedirs(ns.output_dir)

    return Options(pyversion=pyversion,
                   no_import=ns.no_import,
                   doc_dir=ns.doc_dir,
                   search_path=ns.search_path.split(':'),
                   interpreter=ns.interpreter,
                   ignore_errors=ns.ignore_errors,
                   parse_only=ns.parse_only,
                   include_private=ns.include_private,
                   output_dir=ns.output_dir,
                   modules=ns.modules,
                   packages=ns.packages,
                   files=ns.files)


def main() -> None:
    mypy.util.check_python_version('stubgen')
    # Make sure that the current directory is in sys.path so that
    # stubgen can be run on packages in the current directory.
    if not ('' in sys.path or '.' in sys.path):
        sys.path.insert(0, '')

    options = parse_options(sys.argv[1:])
    generate_stubs(options)


if __name__ == '__main__':
    main()
