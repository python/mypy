"""Generator of dynamically typed draft stubs for arbitrary modules.

Basic usage:

  $ mkdir out
  $ stubgen urllib.parse

  => Generate out/urllib/parse.pyi.

For Python 2 mode, use --py2:

  $ stubgen --py2 textwrap

For C modules, you can get more precise function signatures by parsing .rst (Sphinx)
documentation for extra information. For this, use the --docpath option:

  $ scripts/stubgen --docpath <DIR>/Python-3.4.2/Doc/library curses

  => Generate out/curses.py.

Use "stubgen -h" for more help.

Note: You should verify the generated stubs manually.

TODO:

 - support stubs for C modules in Python 2 mode
 - support non-default Python interpreters in Python 3 mode
 - if using --no-import, look for __all__ in the AST
 - infer some return types, such as no return statement with value -> None
 - detect 'if PY2 / is_py2' etc. and either preserve those or only include Python 2 or 3 case
 - maybe export more imported names if there is no __all__ (this affects ssl.SSLError, for example)
   - a quick and dirty heuristic would be to turn this on if a module has something like
     'from x import y as _y'
 - we don't seem to always detect properties ('closed' in 'io', for example)
"""

import glob
import importlib
import json
import os.path
import pkgutil
import subprocess
import sys
import textwrap
import traceback
from collections import defaultdict

from typing import (
    Any, List, Dict, Tuple, Iterable, Iterator, Mapping, Optional, NamedTuple, Set, Union, cast
)

import mypy.build
import mypy.parse
import mypy.errors
import mypy.traverser
from mypy import defaults
from mypy.nodes import (
    Expression, IntExpr, UnaryExpr, StrExpr, BytesExpr, NameExpr, FloatExpr, MemberExpr, TupleExpr,
    ListExpr, ComparisonExpr, CallExpr, IndexExpr, EllipsisExpr,
    ClassDef, MypyFile, Decorator, AssignmentStmt,
    IfStmt, ImportAll, ImportFrom, Import, FuncDef, FuncBase, TempNode,
    ARG_POS, ARG_STAR, ARG_STAR2, ARG_NAMED, ARG_NAMED_OPT,
)
from mypy.stubgenc import parse_all_signatures, find_unique_signatures, generate_stub_for_c_module
from mypy.stubutil import is_c_module, write_header
from mypy.options import Options as MypyOptions
from mypy.types import Type, TypeStrVisitor, AnyType, CallableType, UnboundType, NoneTyp, TupleType
from mypy.visitor import NodeVisitor

Options = NamedTuple('Options', [('pyversion', Tuple[int, int]),
                                 ('no_import', bool),
                                 ('doc_dir', str),
                                 ('search_path', List[str]),
                                 ('interpreter', str),
                                 ('modules', List[str]),
                                 ('ignore_errors', bool),
                                 ('recursive', bool),
                                 ('include_private', bool),
                                 ('output_dir', str),
                                 ])


class CantImport(Exception):
    pass


def generate_stub_for_module(module: str, output_dir: str, quiet: bool = False,
                             add_header: bool = False, sigs: Dict[str, str] = {},
                             class_sigs: Dict[str, str] = {},
                             pyversion: Tuple[int, int] = defaults.PYTHON3_VERSION,
                             no_import: bool = False,
                             search_path: List[str] = [],
                             interpreter: str = sys.executable,
                             include_private: bool = False) -> None:
    target = module.replace('.', '/')
    try:
        result = find_module_path_and_all(module=module,
                                          pyversion=pyversion,
                                          no_import=no_import,
                                          search_path=search_path,
                                          interpreter=interpreter)
    except CantImport:
        if not quiet:
            traceback.print_exc()
        print('Failed to import %s; skipping it' % module)
        return

    if not result:
        # C module
        target = os.path.join(output_dir, target + '.pyi')
        generate_stub_for_c_module(module_name=module,
                                   target=target,
                                   add_header=add_header,
                                   sigs=sigs,
                                   class_sigs=class_sigs)
    else:
        # Python module
        module_path, module_all = result
        if os.path.basename(module_path) == '__init__.py':
            target += '/__init__.pyi'
        else:
            target += '.pyi'
        target = os.path.join(output_dir, target)

        generate_stub(module_path, output_dir, module_all,
                      target=target, add_header=add_header, module=module,
                      pyversion=pyversion, include_private=include_private)
    if not quiet:
        print('Created %s' % target)


def find_module_path_and_all(module: str, pyversion: Tuple[int, int],
                             no_import: bool,
                             search_path: List[str],
                             interpreter: str) -> Optional[Tuple[str,
                                                                 Optional[List[str]]]]:
    """Find module and determine __all__.

    Return None if the module is a C module. Return (module_path, __all__) if
    Python module. Raise an exception or exit if failed.
    """
    module_path = None  # type: Optional[str]
    if not no_import:
        if pyversion[0] == 2:
            module_path, module_all = load_python_module_info(module, interpreter)
        else:
            # TODO: Support custom interpreters.
            try:
                mod = importlib.import_module(module)
            except Exception:
                raise CantImport(module)
            if is_c_module(mod):
                return None
            module_path = mod.__file__
            module_all = getattr(mod, '__all__', None)
    else:
        # Find module by going through search path.
        module_path = mypy.build.find_module(module, ['.'] + search_path)
        if not module_path:
            raise SystemExit(
                "Can't find module '{}' (consider using --search-path)".format(module))
        module_all = None
    return module_path, module_all


def load_python_module_info(module: str, interpreter: str) -> Tuple[str, Optional[List[str]]]:
    """Return tuple (module path, module __all__) for a Python 2 module.

    The path refers to the .py/.py[co] file. The second tuple item is
    None if the module doesn't define __all__.

    Exit if the module can't be imported or if it's a C extension module.
    """
    cmd_template = '{interpreter} -c "%s"'.format(interpreter=interpreter)
    code = ("import importlib, json; mod = importlib.import_module('%s'); "
            "print(mod.__file__); print(json.dumps(getattr(mod, '__all__', None)))") % module
    try:
        output_bytes = subprocess.check_output(cmd_template % code, shell=True)
    except subprocess.CalledProcessError:
        print("Can't import module %s" % module, file=sys.stderr)
        sys.exit(1)
    output = output_bytes.decode('ascii').strip().splitlines()
    module_path = output[0]
    if not module_path.endswith(('.py', '.pyc', '.pyo')):
        raise SystemExit('%s looks like a C module; they are not supported for Python 2' %
                         module)
    if module_path.endswith(('.pyc', '.pyo')):
        module_path = module_path[:-1]
    module_all = json.loads(output[1])
    return module_path, module_all


def generate_stub(path: str,
                  output_dir: str,
                  _all_: Optional[List[str]] = None,
                  target: Optional[str] = None,
                  add_header: bool = False,
                  module: Optional[str] = None,
                  pyversion: Tuple[int, int] = defaults.PYTHON3_VERSION,
                  include_private: bool = False
                  ) -> None:
    with open(path, 'rb') as f:
        source = f.read()
    options = MypyOptions()
    options.python_version = pyversion
    try:
        ast = mypy.parse.parse(source, fnam=path, errors=None, options=options)
    except mypy.errors.CompileError as e:
        # Syntax error!
        for m in e.messages:
            sys.stderr.write('%s\n' % m)
        sys.exit(1)

    gen = StubGenerator(_all_, pyversion=pyversion, include_private=include_private)
    ast.accept(gen)
    if not target:
        target = os.path.join(output_dir, os.path.basename(path))
    subdir = os.path.dirname(target)
    if subdir and not os.path.isdir(subdir):
        os.makedirs(subdir)
    with open(target, 'w') as file:
        if add_header:
            write_header(file, module, pyversion=pyversion)
        file.write(''.join(gen.output()))


# What was generated previously in the stub file. We keep track of these to generate
# nicely formatted output (add empty line between non-empty classes, for example).
EMPTY = 'EMPTY'
FUNC = 'FUNC'
CLASS = 'CLASS'
EMPTY_CLASS = 'EMPTY_CLASS'
VAR = 'VAR'
NOT_IN_ALL = 'NOT_IN_ALL'


class AnnotationPrinter(TypeStrVisitor):

    def __init__(self, stubgen: 'StubGenerator') -> None:
        super().__init__()
        self.stubgen = stubgen

    def visit_unbound_type(self, t: UnboundType)-> str:
        s = t.name
        base = s.split('.')[0]
        self.stubgen.import_tracker.require_name(base)
        if t.args != []:
            s += '[{}]'.format(self.list_str(t.args))
        return s

    def visit_none_type(self, t: NoneTyp) -> str:
        return "None"


class AliasPrinter(NodeVisitor[str]):

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

    def add_import(self, module: str, alias: Optional[str]=None) -> None:
        name = module.split('.')[0]
        self.module_for[alias or name] = None
        self.direct_imports[name] = module
        if alias:
            self.reverse_alias[alias] = name

    def require_name(self, name: str) -> None:
        self.required_names.add(name.split('.')[0])

    def reexport(self, name: str) -> None:
        """
        Mark a given non qualified name as needed in __all__. This means that in case it
        comes from a module, it should be imported with an alias even is the alias is the same
        as the name.

        """
        self.require_name(name)
        self.reexports.add(name)

    def import_lines(self) -> List[str]:
        """
        The list of required import lines (as strings with python code)
        """
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
                 include_private: bool = False) -> None:
        self._all_ = _all_
        self._output = []  # type: List[str]
        self._import_lines = []  # type: List[str]
        self._indent = ''
        self._vars = [[]]  # type: List[List[str]]
        self._state = EMPTY
        self._toplevel_names = []  # type: List[str]
        self._pyversion = pyversion
        self._include_private = include_private
        self.import_tracker = ImportTracker()
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

    def visit_func_def(self, o: FuncDef) -> None:
        if self.is_private_name(o.name()):
            return
        if self.is_not_in_all(o.name()):
            return
        if self.is_recorded_name(o.name()):
            return
        if not self._indent and self._state not in (EMPTY, FUNC):
            self.add('\n')
        if not self.is_top_level():
            self_inits = find_self_initializers(o)
            for init, value in self_inits:
                init_code = self.get_init(init, value)
                if init_code:
                    self.add(init_code)
        self.add("%sdef %s(" % (self._indent, o.name()))
        self.record_name(o.name())
        args = []  # type: List[str]
        for i, arg_ in enumerate(o.arguments):
            var = arg_.variable
            kind = arg_.kind
            name = var.name()
            annotated_type = o.type.arg_types[i] if isinstance(o.type, CallableType) else None
            if annotated_type and not (
                    i == 0 and name == 'self' and isinstance(annotated_type, AnyType)):
                annotation = ": {}".format(self.print_annotation(annotated_type))
            else:
                annotation = ""
            if arg_.initializer:
                initializer = '...'
                if kind in (ARG_NAMED, ARG_NAMED_OPT) and '*' not in args:
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
        if isinstance(o.type, CallableType):
            retname = self.print_annotation(o.type.ret_type)
        elif o.name() == '__init__':
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
        for decorator in o.decorators:
            if isinstance(decorator, NameExpr) and decorator.name in ('property',
                                                                      'staticmethod',
                                                                      'classmethod'):
                self.add('%s@%s\n' % (self._indent, decorator.name))
            elif (isinstance(decorator, MemberExpr) and decorator.name == 'setter' and
                  isinstance(decorator.expr, NameExpr)):
                self.add('%s@%s.setter\n' % (self._indent, decorator.expr.name))
        super().visit_decorator(o)

    def visit_class_def(self, o: ClassDef) -> None:
        sep = None  # type: Optional[int]
        if not self._indent and self._state != EMPTY:
            sep = len(self._output)
            self.add('\n')
        self.add('%sclass %s' % (self._indent, o.name))
        self.record_name(o.name)
        base_types = self.get_base_types(o)
        if base_types:
            self.add('(%s)' % ', '.join(base_types))
            for base in base_types:
                self.import_tracker.require_name(base)
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
                    isinstance(lvalue, NameExpr) and self.is_type_expression(o.rvalue)):
                self.process_typealias(lvalue, o.rvalue)
                continue
            if isinstance(lvalue, TupleExpr) or isinstance(lvalue, ListExpr):
                items = lvalue.items
                if isinstance(o.type, TupleType):
                    annotations = o.type.items  # type: Iterable[Optional[Type]]
                else:
                    annotations = [None] * len(items)
            else:
                items = [lvalue]
                annotations = [o.type]
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
        name = repr(getattr(rvalue.args[0], 'value', '<ERROR>'))
        if isinstance(rvalue.args[1], StrExpr):
            items = repr(rvalue.args[1].value)
        elif isinstance(rvalue.args[1], ListExpr):
            list_items = cast(List[StrExpr], rvalue.args[1].items)
            items = '[%s]' % ', '.join(repr(item.value) for item in list_items)
        else:
            items = '<ERROR>'
        self.add('%s = namedtuple(%s, %s)\n' % (lvalue.name, name, items))
        self._state = CLASS

    def is_type_expression(self, expr: Expression, top_level: bool=True) -> bool:
        """Return True for things that look like type expressions

        Used to know if assignments look like typealiases
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
                return True
        elif isinstance(expr, IndexExpr) and isinstance(expr.base, NameExpr):
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
            return all(self.is_type_expression(i, top_level=False) for i in indices)
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


def find_self_initializers(fdef: FuncBase) -> List[Tuple[str, Expression]]:
    results = []  # type: List[Tuple[str, Expression]]

    class SelfTraverser(mypy.traverser.TraverserVisitor):
        def visit_assignment_stmt(self, o: AssignmentStmt) -> None:
            lvalue = o.lvalues[0]
            if (isinstance(lvalue, MemberExpr) and
                    isinstance(lvalue.expr, NameExpr) and
                    lvalue.expr.name == 'self'):
                results.append((lvalue.name, o.rvalue))

    fdef.accept(SelfTraverser())
    return results


def get_qualified_name(o: Expression) -> str:
    if isinstance(o, NameExpr):
        return o.name
    elif isinstance(o, MemberExpr):
        return '%s.%s' % (get_qualified_name(o.expr), o.name)
    else:
        return '<ERROR>'


def walk_packages(packages: List[str]) -> Iterator[str]:
    for package_name in packages:
        package = __import__(package_name)
        yield package.__name__
        for importer, qualified_name, ispkg in pkgutil.walk_packages(package.__path__,
                                                                     prefix=package.__name__ + ".",
                                                                     onerror=lambda r: None):
            yield qualified_name


def main() -> None:
    options = parse_options(sys.argv[1:])
    if not os.path.isdir(options.output_dir):
        raise SystemExit('Directory "{}" does not exist'.format(options.output_dir))
    if options.recursive and options.no_import:
        raise SystemExit('recursive stub generation without importing is not currently supported')
    sigs = {}  # type: Any
    class_sigs = {}  # type: Any
    if options.doc_dir:
        all_sigs = []  # type: Any
        all_class_sigs = []  # type: Any
        for path in glob.glob('%s/*.rst' % options.doc_dir):
            with open(path) as f:
                func_sigs, class_sigs = parse_all_signatures(f.readlines())
            all_sigs += func_sigs
            all_class_sigs += class_sigs
        sigs = dict(find_unique_signatures(all_sigs))
        class_sigs = dict(find_unique_signatures(all_class_sigs))
    for module in (options.modules if not options.recursive else walk_packages(options.modules)):
        try:
            generate_stub_for_module(module,
                                     output_dir=options.output_dir,
                                     add_header=True,
                                     sigs=sigs,
                                     class_sigs=class_sigs,
                                     pyversion=options.pyversion,
                                     no_import=options.no_import,
                                     search_path=options.search_path,
                                     interpreter=options.interpreter,
                                     include_private=options.include_private)
        except Exception as e:
            if not options.ignore_errors:
                raise e
            else:
                print("Stub generation failed for", module, file=sys.stderr)


def parse_options(args: List[str]) -> Options:
    # TODO: why not use click and reduce the amount of code to maintain
    # within this module.
    pyversion = defaults.PYTHON3_VERSION
    no_import = False
    recursive = False
    ignore_errors = False
    doc_dir = ''
    search_path = []  # type: List[str]
    interpreter = ''
    include_private = False
    output_dir = 'out'
    while args and args[0].startswith('-'):
        if args[0] in '-o':
            output_dir = args[1]
            args = args[1:]
        elif args[0] == '--doc-dir':
            doc_dir = args[1]
            args = args[1:]
        elif args[0] == '--search-path':
            if not args[1]:
                usage()
            search_path = args[1].split(':')
            args = args[1:]
        elif args[0] == '-p':
            interpreter = args[1]
            args = args[1:]
        elif args[0] == '--recursive':
            recursive = True
        elif args[0] == '--ignore-errors':
            ignore_errors = True
        elif args[0] == '--py2':
            pyversion = defaults.PYTHON2_VERSION
        elif args[0] == '--no-import':
            no_import = True
        elif args[0] == '--include-private':
            include_private = True
        elif args[0] in ('-h', '--help'):
            usage()
        else:
            raise SystemExit('Unrecognized option %s' % args[0])
        args = args[1:]
    if not args:
        usage()
    if not interpreter:
        interpreter = sys.executable if pyversion[0] == 3 else default_python2_interpreter()
    # Create the output folder if it doesn't already exist.
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    return Options(pyversion=pyversion,
                   no_import=no_import,
                   doc_dir=doc_dir,
                   search_path=search_path,
                   interpreter=interpreter,
                   modules=args,
                   ignore_errors=ignore_errors,
                   recursive=recursive,
                   include_private=include_private,
                   output_dir=output_dir)


def default_python2_interpreter() -> str:
    # TODO: Make this do something reasonable in Windows.
    for candidate in ('/usr/bin/python2', '/usr/bin/python'):
        if not os.path.exists(candidate):
            continue
        output = subprocess.check_output([candidate, '--version'],
                                         stderr=subprocess.STDOUT).strip()
        if b'Python 2' in output:
            return candidate
    raise SystemExit("Can't find a Python 2 interpreter -- please use the -p option")


def usage() -> None:
    usage = textwrap.dedent("""\
        usage: stubgen [--py2] [--no-import] [--doc-dir PATH]
                       [--search-path PATH] [-p PATH] [-o PATH]
                       MODULE ...

        Generate draft stubs for modules.

        Stubs are generated in directory ./out, to avoid overriding files with
        manual changes.  This directory is assumed to exist.

        Options:
          --py2           run in Python 2 mode (default: Python 3 mode)
          --recursive     traverse listed modules to generate inner package modules as well
          --ignore-errors ignore errors when trying to generate stubs for modules
          --no-import     don't import the modules, just parse and analyze them
                          (doesn't work with C extension modules and doesn't
                          respect __all__)
          --include-private
                          generate stubs for objects and members considered private
                          (single leading undescore and no trailing underscores)
          --doc-dir PATH  use .rst documentation in PATH (this may result in
                          better stubs in some cases; consider setting this to
                          DIR/Python-X.Y.Z/Doc/library)
          --search-path PATH
                          specify module search directories, separated by ':'
                          (currently only used if --no-import is given)
          -p PATH         use Python interpreter at PATH (only works for
                          Python 2 right now)
          -o PATH         Change the output folder [default: out]
          -h, --help      print this help message and exit
    """.rstrip())

    raise SystemExit(usage)


if __name__ == '__main__':
    main()
