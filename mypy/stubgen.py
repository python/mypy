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
import imp
import importlib
import json
import os.path
import subprocess
import sys
import textwrap

from typing import Any, List, Dict, Tuple, Iterable, Optional, NamedTuple, Set

import mypy.build
import mypy.parse
import mypy.errors
import mypy.traverser
from mypy import defaults
from mypy.nodes import (
    Node, IntExpr, UnaryExpr, StrExpr, BytesExpr, NameExpr, FloatExpr, MemberExpr, TupleExpr,
    ListExpr, ComparisonExpr, CallExpr, ClassDef, MypyFile, Decorator, AssignmentStmt,
    IfStmt, ImportAll, ImportFrom, Import, FuncDef, FuncBase, ARG_STAR, ARG_STAR2, ARG_NAMED
)
from mypy.stubgenc import parse_all_signatures, find_unique_signatures, generate_stub_for_c_module
from mypy.stubutil import is_c_module, write_header
from mypy.options import Options as MypyOptions


Options = NamedTuple('Options', [('pyversion', Tuple[int, int]),
                                 ('no_import', bool),
                                 ('doc_dir', str),
                                 ('search_path', List[str]),
                                 ('interpreter', str),
                                 ('modules', List[str])])


def generate_stub_for_module(module: str, output_dir: str, quiet: bool = False,
                             add_header: bool = False, sigs: Dict[str, str] = {},
                             class_sigs: Dict[str, str] = {},
                             pyversion: Tuple[int, int] = defaults.PYTHON3_VERSION,
                             no_import: bool = False,
                             search_path: List[str] = [],
                             interpreter: str = sys.executable) -> None:
    target = module.replace('.', '/')
    result = find_module_path_and_all(module=module,
                                      pyversion=pyversion,
                                      no_import=no_import,
                                      search_path=search_path,
                                      interpreter=interpreter)
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
                      target=target, add_header=add_header, module=module, pyversion=pyversion)
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
    if not no_import:
        if pyversion[0] == 2:
            module_path, module_all = load_python_module_info(module, interpreter)
        else:
            # TODO: Support custom interpreters.
            mod = importlib.import_module(module)
            imp.reload(mod)
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


def generate_stub(path: str, output_dir: str, _all_: Optional[List[str]] = None,
                  target: str = None, add_header: bool = False, module: str = None,
                  pyversion: Tuple[int, int] = defaults.PYTHON3_VERSION) -> None:
    source = open(path, 'rb').read()
    options = MypyOptions()
    options.python_version = pyversion
    try:
        ast = mypy.parse.parse(source, fnam=path, errors=None, options=options)
    except mypy.errors.CompileError as e:
        # Syntax error!
        for m in e.messages:
            sys.stderr.write('%s\n' % m)
        sys.exit(1)

    gen = StubGenerator(_all_, pyversion=pyversion)
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


class StubGenerator(mypy.traverser.TraverserVisitor):
    def __init__(self, _all_: Optional[List[str]], pyversion: Tuple[int, int]) -> None:
        self._all_ = _all_
        self._output = []  # type: List[str]
        self._import_lines = []  # type: List[str]
        self._imports = []  # type: List[str]
        self._indent = ''
        self._vars = [[]]  # type: List[List[str]]
        self._state = EMPTY
        self._toplevel_names = []  # type: List[str]
        self._classes = set()  # type: Set[str]
        self._base_classes = []  # type: List[str]
        self._pyversion = pyversion

    def visit_mypy_file(self, o: MypyFile) -> None:
        self._classes = find_classes(o)
        for node in o.defs:
            if isinstance(node, ClassDef):
                self._base_classes.extend(self.get_base_types(node))
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
            init_stmt = arg_.initialization_statement
            if init_stmt:
                if kind == ARG_NAMED and '*' not in args:
                    args.append('*')
                typename = self.get_str_type_of_node(init_stmt.rvalue, True)
                arg = '{}: {} = ...'.format(name, typename)
            elif kind == ARG_STAR:
                arg = '*%s' % name
            elif kind == ARG_STAR2:
                arg = '**%s' % name
            else:
                arg = name
            args.append(arg)
        retname = None
        if o.name() == '__init__':
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
        if not self._indent and self._state != EMPTY:
            sep = len(self._output)
            self.add('\n')
        else:
            sep = None
        self.add('%sclass %s' % (self._indent, o.name))
        self.record_name(o.name)
        base_types = self.get_base_types(o)
        if base_types:
            self.add('(%s)' % ', '.join(base_types))
        self.add(':\n')
        n = len(self._output)
        self._indent += '    '
        self._vars.append([])
        super().visit_class_def(o)
        self._indent = self._indent[:-4]
        self._vars.pop()
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
                self.add_import_line('import %s\n' % modname)
        return base_types

    def visit_assignment_stmt(self, o: AssignmentStmt) -> None:
        foundl = []

        for lvalue in o.lvalues:
            if isinstance(lvalue, NameExpr) and self.is_namedtuple(o.rvalue):
                self.process_namedtuple(lvalue, o.rvalue)
                continue
            if isinstance(lvalue, TupleExpr):
                items = lvalue.items
            elif isinstance(lvalue, ListExpr):
                items = lvalue.items
            else:
                items = [lvalue]
            sep = False
            found = False
            for item in items:
                if isinstance(item, NameExpr):
                    init = self.get_init(item.name, o.rvalue)
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

    def is_namedtuple(self, expr: Node) -> bool:
        if not isinstance(expr, CallExpr):
            return False
        callee = expr.callee
        return ((isinstance(callee, NameExpr) and callee.name.endswith('namedtuple')) or
                (isinstance(callee, MemberExpr) and callee.name == 'namedtuple'))

    def process_namedtuple(self, lvalue, rvalue):
        self.add_import_line('from collections import namedtuple\n')
        if self._state != EMPTY:
            self.add('\n')
        name = repr(getattr(rvalue.args[0], 'value', '<ERROR>'))
        if isinstance(rvalue.args[1], StrExpr):
            items = repr(rvalue.args[1].value)
        elif isinstance(rvalue.args[1], ListExpr):
            list_items = rvalue.args[1].items
            items = '[%s]' % ', '.join(repr(item.value) for item in list_items)
        else:
            items = '<ERROR>'
        self.add('%s = namedtuple(%s, %s)\n' % (lvalue.name, name, items))
        self._classes.add(lvalue.name)
        self._state = CLASS

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
        if self._all_:
            # Include import froms that import names defined in __all__.
            names = [name for name, alias in o.names
                     if name in self._all_ and alias is None]
            exported_names.update(names)
            self.import_and_export_names(o.id, o.relative, names)
        else:
            # Include import from targets that import from a submodule of a package.
            if o.relative:
                sub_names = [name for name, alias in o.names
                             if alias is None]
                exported_names.update(sub_names)
                self.import_and_export_names(o.id, o.relative, sub_names)
        # Import names used as base classes.
        base_names = [(name, alias) for name, alias in o.names
                      if alias or name in self._base_classes and name not in exported_names]
        if base_names:
            imp_names = []  # type: List[str]
            for name, alias in base_names:
                if alias is not None and alias != name:
                    imp_names.append('%s as %s' % (name, alias))
                else:
                    imp_names.append(name)
            self.add_import_line('from %s%s import %s\n' % (
                '.' * o.relative, o.id, ', '.join(imp_names)))

    def import_and_export_names(self, module_id: str, relative: int, names: Iterable[str]) -> None:
        """Import names from a module and export them (via from ... import x as x)."""
        if names and module_id:
            full_module_name = '%s%s' % ('.' * relative, module_id)
            imported_names = ', '.join(['%s as %s' % (name, name) for name in names])
            self.add_import_line('from %s import %s\n' % (full_module_name, imported_names))
            for name in names:
                self.record_name(name)

    def visit_import(self, o: Import) -> None:
        for id, as_id in o.ids:
            if as_id is None:
                target_name = id.split('.')[0]
            else:
                target_name = as_id
            if self._all_ and target_name in self._all_ and (as_id is not None or
                                                             '.' not in id):
                self.add_import_line('import %s as %s\n' % (id, target_name))
                self.record_name(target_name)

    def get_init(self, lvalue: str, rvalue: Node) -> str:
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
        typename = self.get_str_type_of_node(rvalue)
        return '%s%s = ...  # type: %s\n' % (self._indent, lvalue, typename)

    def add(self, string: str) -> None:
        """Add text to generated stub."""
        self._output.append(string)

    def add_typing_import(self, name: str) -> None:
        """Add a name to be imported from typing, unless it's imported already.

        The import will be internal to the stub.
        """
        if name not in self._imports:
            self._imports.append(name)

    def add_import_line(self, line: str) -> None:
        """Add a line of text to the import section, unless it's already there."""
        if line not in self._import_lines:
            self._import_lines.append(line)

    def output(self) -> str:
        """Return the text for the stub."""
        imports = ''
        if self._imports:
            imports += 'from typing import %s\n' % ", ".join(sorted(self._imports))
        if self._import_lines:
            imports += ''.join(self._import_lines)
        if imports and self._output:
            imports += '\n'
        return imports + ''.join(self._output)

    def is_not_in_all(self, name: str) -> bool:
        if self.is_private_name(name):
            return False
        return self.is_top_level() and bool(self._all_) and name not in self._all_

    def is_private_name(self, name: str) -> bool:
        return name.startswith('_') and (not name.endswith('__')
                                         or name in ('__all__',
                                                     '__author__',
                                                     '__version__',
                                                     '__str__',
                                                     '__repr__',
                                                     '__getstate__',
                                                     '__setstate__',
                                                     '__slots__'))

    def get_str_type_of_node(self, rvalue: Node,
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


def find_self_initializers(fdef: FuncBase) -> List[Tuple[str, Node]]:
    results = []  # type: List[Tuple[str, Node]]

    class SelfTraverser(mypy.traverser.TraverserVisitor):
        def visit_assignment_stmt(self, o: AssignmentStmt) -> None:
            lvalue = o.lvalues[0]
            if (isinstance(lvalue, MemberExpr) and
                    isinstance(lvalue.expr, NameExpr) and
                    lvalue.expr.name == 'self'):
                results.append((lvalue.name, o.rvalue))

    fdef.accept(SelfTraverser())
    return results


def find_classes(node: Node) -> Set[str]:
    results = set()  # type: Set[str]

    class ClassTraverser(mypy.traverser.TraverserVisitor):
        def visit_class_def(self, o: ClassDef) -> None:
            results.add(o.name)

    node.accept(ClassTraverser())
    return results


def get_qualified_name(o: Node) -> str:
    if isinstance(o, NameExpr):
        return o.name
    elif isinstance(o, MemberExpr):
        return '%s.%s' % (get_qualified_name(o.expr), o.name)
    else:
        return '<ERROR>'


def main() -> None:
    options = parse_options()
    if not os.path.isdir('out'):
        raise SystemExit('Directory "out" does not exist')
    sigs = {}  # type: Any
    class_sigs = {}  # type: Any
    if options.doc_dir:
        all_sigs = []  # type: Any
        all_class_sigs = []  # type: Any
        for path in glob.glob('%s/*.rst' % options.doc_dir):
            func_sigs, class_sigs = parse_all_signatures(open(path).readlines())
            all_sigs += func_sigs
            all_class_sigs += class_sigs
        sigs = dict(find_unique_signatures(all_sigs))
        class_sigs = dict(find_unique_signatures(all_class_sigs))
    for module in options.modules:
        generate_stub_for_module(module, 'out',
                                 add_header=True,
                                 sigs=sigs,
                                 class_sigs=class_sigs,
                                 pyversion=options.pyversion,
                                 no_import=options.no_import,
                                 search_path=options.search_path,
                                 interpreter=options.interpreter)


def parse_options() -> Options:
    args = sys.argv[1:]
    pyversion = defaults.PYTHON3_VERSION
    no_import = False
    doc_dir = ''
    search_path = []  # type: List[str]
    interpreter = ''
    while args and args[0].startswith('-'):
        if args[0] == '--doc-dir':
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
        elif args[0] == '--py2':
            pyversion = defaults.PYTHON2_VERSION
        elif args[0] == '--no-import':
            no_import = True
        elif args[0] in ('-h', '--help'):
            usage()
        else:
            raise SystemExit('Unrecognized option %s' % args[0])
        args = args[1:]
    if not args:
        usage()
    if not interpreter:
        interpreter = sys.executable if pyversion[0] == 3 else default_python2_interpreter()
    return Options(pyversion=pyversion,
                   no_import=no_import,
                   doc_dir=doc_dir,
                   search_path=search_path,
                   interpreter=interpreter,
                   modules=args)


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
                       [--search-path PATH] [-p PATH] MODULE ...

        Generate draft stubs for modules.

        Stubs are generated in directory ./out, to avoid overriding files with
        manual changes.  This directory is assumed to exist.

        Options:
          --py2           run in Python 2 mode (default: Python 3 mode)
          --no-import     don't import the modules, just parse and analyze them
                          (doesn't work with C extension modules and doesn't
                          respect __all__)
          --doc-dir PATH  use .rst documentation in PATH (this may result in
                          better stubs in some cases; consider setting this to
                          DIR/Python-X.Y.Z/Doc/library)
          --search-path PATH
                          specify module search directories, separated by ':'
                          (currently only used if --no-import is given)
          -p PATH         use Python interpreter at PATH (only works for
                          Python 2 right now)
          -h, --help      print this help message and exit
    """.rstrip())

    raise SystemExit(usage)


if __name__ == '__main__':
    main()
