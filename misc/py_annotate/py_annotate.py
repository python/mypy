"""Fixer that inserts mypy annotations into methods.

Annotations are inserted either as comments or using the PEP484 syntax (requires
python3.5).

For example, this transforms

  def foo(self, bar, baz=12):
      return bar + baz

into (comment annotation)

  def foo(self, bar, baz=12):
      # type: (Any, int) -> Any
      return bar + baz

or (PEP484 annotation)

  def foo(self, bar: Any, baz: int=12) -> Any:
      return bar + baz

It obtains type information either from a .pyi stub file (described in PEP484),
or by examining basic default argument values such as numbers and strings and
assuming their type implies the argument type.

It also uses some basic heuristics to decide whether to ignore the first
argument:

  - always if it's named 'self'
  - if there's a @classmethod decorator

Finally, it knows that __init__() is supposed to return None.
"""

from __future__ import print_function

__all__ = ['KnownError',
           'FixAnnotate',
           'annotate_string',
           'main']

from collections import namedtuple
import itertools
import logging
import os
import re

from lib2to3 import pygram, pytree, refactor
from lib2to3.fixer_base import BaseFix
from lib2to3.fixer_util import (token, syms, touch_import, find_indentation, find_root,
                                does_tree_import, FromImport, Newline)
from lib2to3.patcomp import compile_pattern
from lib2to3.pgen2 import driver
from lib2to3.pytree import Leaf, Node


class KnownError(Exception):
    """Exceptions we already know about"""
    pass


class Util(object):

    return_expr = compile_pattern("""return_stmt< 'return' any >""")

    @classmethod
    def has_return_exprs(cls, node):
        """Traverse the tree below node looking for 'return expr'.

        Return True if at least 'return expr' is found, False if not.
        (If both 'return' and 'return expr' are found, return True.)
        """
        results = {}
        if cls.return_expr.match(node, results):
            return True
        for child in node.children:
            if child.type not in (syms.funcdef, syms.classdef):
                if cls.has_return_exprs(child):
                    return True
        return False

    driver = driver.Driver(pygram.python_grammar,
                           convert=pytree.convert)

    @classmethod
    def parse_string(cls, text):
        """Use lib2to3 to parse text into a Node."""

        text = text.strip()
        if not text:
            # self.driver.parse_string just returns the ENDMARKER Leaf, wrap in a Node
            # for consistency
            return Node(syms.file_input, [Leaf(token.ENDMARKER, '')])

        # workaround: parsing text without trailing '\n' throws exception
        text += '\n'
        return cls.driver.parse_string(text)


class ArgSignature(object):
    """Partially parsed representation of a function argument"""

    def __init__(self, arg_nodes):
        sig = ArgSignature._split_arg(arg_nodes)
        self._is_tuple, self._stars, self._arg_type, self._name_nodes, self._default = sig
        self._wasModified = False

    @property
    def is_tuple(self):
        """Do we use the unusual packed-tuple syntax (see PEP 3113)"""
        return self._is_tuple

    @property
    def stars(self):
        """String: (''|'*'|'**')"""
        return self._stars

    @property
    def arg_type(self):
        """Existing annotation: (Node|Leaf|None)"""
        return self._arg_type

    @property
    def default(self):
        """Node holding default value or None"""
        return self._default

    @property
    def name(self):
        """Our name as a string. Throws if is_tuple (no reasonable name)."""

        assert not self.is_tuple
        n = self._name_nodes[-1]

        assert n.type == token.NAME, repr(n)
        return n.value

    @staticmethod
    def _split_arg(arg):
        """Takes list of nodes corresponding to a function argument, returns
        a tuple holding its constituent pieces:

        is_tuple: bool, are we a packed-tuple arg
        stars: (''|'*'|'**')
        arg_type: (Node|Leaf|None) -- existing annotation
        name_nodes: NonEmptyList(Node|Leaf) -- argument name
        default: (Node|Leaf) -- default value
        """
        # in cpython, see ast_for_arguments in ast.c

        assert arg, "Need non-empty list"
        arg = list(arg)

        is_tuple, stars, arg_type, default = False, '', None, None

        def is_leaf(n): return isinstance(n, Leaf)

        def get_unique_idx(nodes, test_set):
            """If it exists, get index of unique Leaf node n where n.value in
            test_set. Return None if no such element"""
            matches = [i for i, n in enumerate(nodes)
                       if is_leaf(n) and n.value in test_set]
            assert len(matches) in (0, 1)
            return matches[0] if matches else None

        # [('*'|'**')] (NAME | packed_tuple) [':' test] ['=' test]

        # Strip stars
        idx = get_unique_idx(arg, ['*', '**'])
        if idx is not None:
            assert idx == 0
            stars = arg.pop(idx).value

        # Strip default
        idx = get_unique_idx(arg, '=')
        if idx is not None:
            assert idx == (len(arg) - 2)
            arg, default = arg[:idx], arg[idx+1]

        def split_colon(nodes):
            idx = get_unique_idx(nodes, ':')
            if idx is None:
                return nodes, None
            assert idx == (len(nodes) - 2)
            return nodes[:idx], nodes[idx + 1]

        # Strip one flavor of arg_type (the other flavor, where we have a tname
        # Node, is handled below)
        arg, arg_type = split_colon(arg)

        if 3 == len(arg):
            assert arg[0].type == token.LPAR
            assert arg[2].type == token.RPAR
            assert arg[1].type in (syms.tfpdef, syms.tfplist)

            is_tuple = True

            assert stars == ''
            assert arg_type is None  # type declaration goes inside tuple

            return is_tuple, stars, arg_type, arg, default

        if 1 != len(arg):
            raise KnownError()  # expected/parse_error.py

        node = arg[0]
        if is_leaf(node):
            return is_tuple, stars, arg_type, arg, default

        assert node.type in (syms.tname, syms.tfpdef)

        is_tuple = (node.type == syms.tfpdef)

        if node.type == syms.tname:
            arg, inner_arg_type = split_colon(node.children)
            if inner_arg_type is not None:
                assert arg_type is None
                arg_type = inner_arg_type

        return is_tuple, stars, arg_type, arg, default

    def insert_annotation(self, arg_type):
        """Modifies tree to set string arg_type as our type annotation"""
        # maybe the right way to do this is to insert as next child
        # in our parent instead? Or could replace self._arg[-1]
        # with modified version of itself
        assert self.arg_type is None, 'already annotated'
        assert not self._wasModified, 'can only set annotation once'
        self._wasModified = True

        name = self._name_nodes[-1]
        assert name.type == token.NAME

        typed_name = Node(syms.tname,
                          [Leaf(token.NAME, self.name),
                           Leaf(token.COLON, ':'),
                           clean_clone(arg_type, False)])

        typed_name.prefix = name.prefix

        name.replace(typed_name)


class FuncSignature(object):
    """A function or method"""

    # The pattern to match.
    PATTERN = """
              funcdef<
                'def' name=NAME
                parameters< '(' [args=any+] ')' >
                ['->' ret_annotation=any]
                colon=':' suite=any+ >
              """

    def __init__(self, node, match_results):
        """node must match PATTERN, return FuncSignature, else return None."""

        name = match_results.get('name')
        assert isinstance(name, Leaf), repr(name)
        assert name.type == token.NAME, repr(name)

        self._ret_type = match_results.get('ret_annotation')
        self._full_name = self._make_function_key(name)

        args = self._split_args(match_results.get('args'))
        self._arg_sigs = tuple(map(ArgSignature, args))

        self._node = node
        self._match_results = match_results
        self._inserted_ret_annotation = False

    def __str__(self):
        return self.full_name

    @property
    def full_name(self):
        """Fully-qualified name. string"""
        return self._full_name

    @property
    def short_name(self):
        return self._match_results.get('name').value

    @property
    def ret_type(self):
        """Return type, Node? or None"""
        return self._ret_type

    @property
    def arg_sigs(self):
        """List[ArgSignature]"""
        return self._arg_sigs

    # The parse tree has a different shape when there is a single
    # decorator vs. when there are multiple decorators.
    decorated_pattern = compile_pattern("""
    decorated< (d=decorator | decorators< dd=decorator+ >) funcdef >
    """)

    @property
    def decorators(self):
        """A list of our decorators.

        This is a list of strings; only simple decorators
        (e.g. @staticmethod) are returned.

        If the function is undecorated or only non-simple decorators
        are found, return [].
        """
        # TODO: memoize
        node = self._node
        if node.parent is None:
            return []
        results = {}
        if not self.decorated_pattern.match(node.parent, results):
            return []
        decorators = results.get('dd') or [results['d']]
        decs = []
        for d in decorators:
            for child in d.children:
                if child.type == token.NAME:
                    decs.append(child.value)
        return decs

    @property
    def is_method(self):
        """Whether we are (directly) inside a class."""
        # TODO: memoize
        node = self._node.parent
        while node is not None:
            if node.type == syms.classdef:
                return True
            if node.type == syms.funcdef:
                return False
            node = node.parent
        return False

    @property
    def has_return_exprs(self):
        """True if function has "return expr" anywhere"""
        return Util.has_return_exprs(self._node)

    @property
    def has_pep484_annotations(self):
        """Do we have any pep484 annotations"""
        return self.ret_type or any(arg.arg_type for arg in self.arg_sigs)

    @property
    def has_comment_annotations(self):
        """Do we have any comment annotations"""
        children = self._match_results['suite'][0].children
        for ch in children:
            if ch.prefix.lstrip().startswith('# type:'):
                return True

        return False

    def insert_ret_annotation(self, ret_type):
        """In-place annotation. Can only call once"""
        assert not self._inserted_ret_annotation
        self._inserted_ret_annotation = True

        colon = self._match_results.get('colon')
        # TODO: insert as a Node, not as a prefix
        colon.prefix = ' -> ' + str(ret_type).strip() + colon.prefix

    def try_insert_comment_annotation(self, annotation):
        """Try to insert '# type: {annotation}' comment. """
        # For reference, see lib2to3/fixes/fix_tuple_params.py in stdlib.
        # "Compact" functions (e.g. 'def foo(x, y): return max(x, y)')
        # are not annotated.

        children = self._match_results['suite'][0].children
        if not (len(children) >= 2 and children[1].type == token.INDENT):
            return False  # can't annotate

        node = children[1]
        node.prefix = '%s# type: %s\n%s' % (node.value, annotation, node.prefix)
        node.changed()
        return True

    scope_pattern = compile_pattern("""(
    funcdef < 'def'   name=TOKEN any*> |
    classdef< 'class' name=TOKEN any*>
    )""")

    @classmethod
    def _make_function_key(cls, node):
        """Return fully-qualified name of function that node is under.

        If source is

        class C(object):
          def foo(self):
            x = 1

        We'll return 'C.foo' for any nodes related to 'x', '1', 'foo', 'self',
        and either 'C' or '' otherwise."""

        result = []
        while node is not None:
            match_result = {}
            if cls.scope_pattern.match(node, match_result):
                result.append(match_result.get('name').value)

            node = node.parent

        return '.'.join(reversed(result))

    @staticmethod
    def _split_args(args):
        """Takes match of PATTERN.args, returns list of non-empty lists of nodes, where each list
        corresponds to a function argument."""
        if args is None:
            return []

        assert isinstance(args, list) and 1 == len(args), repr(args)

        args = args[0]
        if isinstance(args, Leaf) or args.type == syms.tname:
            args = [args]
        else:
            args = args.children

        return split_comma(args)


class FixAnnotate(BaseFix):

    # This fixer is compatible with the bottom matcher.
    BM_compatible = True

    # This fixer shouldn't run by default.
    explicit = True

    PATTERN = FuncSignature.PATTERN

    counter = None if not os.getenv('MAXFIXES') else int(os.getenv('MAXFIXES'))

    def __init__(self, options, log):
        super(FixAnnotate, self).__init__(options, log)

        # ParsedPyi obtained from .pyi file, if it exists and use_pyi is True
        self.parsed_pyi = None

        # Did we add globals required by pyi to the top of the py file
        self.added_pyi_globals = False

        self.logger = logging.getLogger('FixAnnotate')

        # Options below

        # List of things to import from "__future__"
        self.future_imports = tuple()

        # insert type annotations in PEP484 style. Otherwise insert as comments
        self._annotate_pep484 = False

        # Strip comments and, formatting from type annotations (False breaks comment output mode)
        self._strip_pyi_formatting = not self.annotate_pep484

    @property
    def annotate_pep484(self):
        return self._annotate_pep484

    @annotate_pep484.setter
    def annotate_pep484(self, value):
        self._annotate_pep484 = bool(value)
        self._strip_pyi_formatting = not self.annotate_pep484

    def transform(self, node, results):
        if FixAnnotate.counter is not None:
            if FixAnnotate.counter <= 0:
                return

        cur_sig = FuncSignature(node, results)
        if not self.can_annotate(cur_sig):
            return

        if FixAnnotate.counter is not None:
            FixAnnotate.counter -= 1

        # Compute the annotation, or directly insert if not self.emit_as_comment
        annot = self.get_or_insert_annotation(cur_sig)

        if not self.annotate_pep484 and annot:
            if cur_sig.try_insert_comment_annotation(annot) and 'Any' in annot:
                touch_import('typing', 'Any', node)

        self.add_globals(node)

    def get_or_insert_annotation(self, cur_sig):
        arg_types = []
        for i, arg_sig in enumerate(cur_sig.arg_sigs):
            is_first = (i == 0)

            if self.parsed_pyi:
                pyi_sig = self.parsed_pyi.funcs[cur_sig.full_name]
                new_type = pyi_sig.arg_sigs[i].arg_type
                new_type = clean_clone(new_type, self._strip_pyi_formatting)
            else:
                new_type = self.infer_arg_from_default(arg_sig.default)
                if new_type and not self.infer_should_annotate(cur_sig, arg_sig, is_first):
                    self.logger.error(('Heuristics failed: default value on self? '
                                       'discarding type from heuristics'))
                    new_type = None

            if self.annotate_pep484:
                if new_type:
                    arg_sig.insert_annotation(new_type)
            else:
                if new_type:
                    arg_types.append(arg_sig.stars + str(new_type).strip())
                elif self.infer_should_annotate(cur_sig, arg_sig, is_first):
                    arg_types.append(arg_sig.stars + 'Any')

        if self.parsed_pyi:
            pyi_sig = self.parsed_pyi.funcs[cur_sig.full_name]
            ret_type = pyi_sig.ret_type
        else:
            ret_type = self.infer_ret_type(cur_sig)

        if self.annotate_pep484:
            if ret_type:
                cur_sig.insert_ret_annotation(ret_type)

        else:
            if self.parsed_pyi and not ret_type:
                ret_type = self.infer_ret_type(cur_sig)

            return '(' + ', '.join(arg_types) + ') -> ' + str(ret_type).strip()

    def can_annotate(self, cur_sig):
        if cur_sig.has_pep484_annotations or cur_sig.has_comment_annotations:
            self.logger.warning('already annotated, skipping %s', cur_sig)
            return False

        if not self.parsed_pyi:
            return True

        if cur_sig.full_name not in self.parsed_pyi.funcs:
            self.logger.warning('no signature for %s, skipping', cur_sig)
            return False

        pyi_sig = self.parsed_pyi.funcs[cur_sig.full_name]

        if not pyi_sig.has_pep484_annotations:
            self.logger.warning('ignoring pyi definition with no annotations: %s', pyi_sig)
            return False

        if not self.func_sig_compatible(cur_sig, pyi_sig):
            self.logger.warning('incompatible annotation, skipping %s', cur_sig)
            return False

        return True

    def add_globals(self, node):
        """Add required globals to the root of node. Idempotent."""
        if self.added_pyi_globals:
            return
        # TODO: get rid of this -- added to prevent adding .parsed_pyi.top_lines every time
        # we annotate a different function in the same file, but can break when we run the tool
        # twice on the same file. Have to do something like what touch_import does.
        self.added_pyi_globals = True

        imports, top_lines = ((self.parsed_pyi.imports, self.parsed_pyi.top_lines) if
                              self.parsed_pyi else ([], []))

        # Copy imports if not already present
        for pkg, names in imports:
            if names is None:
                touch_import(None, pkg, node)  # == 'import pkg'
            else:
                for name in names:
                    touch_import(pkg, name, node)

        root = find_root(node)

        import_idx = [idx for idx, node in enumerate(root.children)
                      if self.import_pattern.match(node)]
        if import_idx:
            future_insert_pos = import_idx[0]
            top_insert_pos = import_idx[-1] + 1
        else:
            future_insert_pos = top_insert_pos = 0

            # first string (normally docstring)
            for idx, node in enumerate(root.children):
                if (node.type == syms.simple_stmt and node.children and
                        node.children[0].type == token.STRING):
                    future_insert_pos = top_insert_pos = idx + 1
                    break

        top_lines = '\n'.join(top_lines)
        top_lines = Util.parse_string(top_lines)  # strips some newlines
        for offset, node in enumerate(top_lines.children[:-1]):
            root.insert_child(top_insert_pos + offset, node)

        # touch_import doesn't do proper order for __future__
        pkg = '__future__'
        future_imports = [n for n in self.future_imports if not does_tree_import(pkg, n, root)]
        for offset, name in enumerate(future_imports):
            node = FromImport(pkg, [Leaf(token.NAME, name, prefix=" ")])
            node = Node(syms.simple_stmt, [node, Newline()])
            root.insert_child(future_insert_pos + offset, node)

    @staticmethod
    def func_sig_compatible(cur_sig, pyi_sig):
        """Can cur_sig be annotated with the info in pyi_sig: number of arguments must match,
        they must have the same star signature and they can't be tuple arguments.
        """

        if len(pyi_sig.arg_sigs) != len(cur_sig.arg_sigs):
            return False

        for pyi, cur in zip(pyi_sig.arg_sigs, cur_sig.arg_sigs):
            # Entirely skip functions that use tuple args
            if cur.is_tuple or pyi.is_tuple:
                return False

            # Stars are expected to match
            if cur.stars != pyi.stars:
                return False

        return True

    @staticmethod
    def infer_ret_type(cur_sig):
        """Heuristic for return value of a function."""
        if cur_sig.short_name == '__init__' or not cur_sig.has_return_exprs:
            return 'None'
        return 'Any'

    @staticmethod
    def infer_should_annotate(func, arg, at_start):
        """Heuristic for whether arg (in func) should be annotated."""

        if func.is_method and at_start and 'staticmethod' not in func.decorators:
            # Don't annotate the first argument if it's named 'self'.
            # Don't annotate the first argument of a class method.
            if 'self' == arg.name or 'classmethod' in func.decorators:
                return False

        return True

    @staticmethod
    def infer_arg_from_default(node):
        """Heuristic to get an argument's type from its default value"""
        if node is None:
            return None

        if node.type == token.NUMBER:
            if re.match(r'\d+[lL]?$', node.value):
                return 'int'
            else:
                return 'float'  # TODO: complex?
        elif node.type == token.STRING:
            if node.value.startswith(('u', 'U')):
                return 'unicode'
            else:
                return 'str'
        elif node.type == token.NAME and node.value in ('True', 'False'):
            return 'bool'

        return None

    def set_pyi_string(self, pyi_string):
        """Set the annotations the fixer will use"""
        self.parsed_pyi = self.parse_pyi_string(pyi_string)
        self.added_pyi_globals = False

    def parse_pyi_string(self, text):
        """Parse .pyi string, return as ParsedPyi"""
        tree = Util.parse_string(text)

        funcs = {}
        for node, match_results in generate_matches(tree, self.pattern):
            sig = FuncSignature(node, match_results)

            if sig.full_name in funcs:
                self.logger.warning('Ignoring redefinition: %s', sig)
            else:
                funcs[sig.full_name] = sig

        imports = []
        for node, match_results in generate_top_matches(tree, self.import_pattern):
            imp = self.parse_top_import(node, match_results)
            if imp:
                imports.append(imp)

        top_lines = []
        for node, match_results in generate_top_matches(tree, self.assign_pattern):
            text = str(node).strip()

            # hack to avoid shadowing real variables -- proper solution is more complicated,
            # use util.find_binding
            if 'TypeVar' in text or (text and '_' == text[0]):
                top_lines.append(text)
            else:
                self.logger.warning("ignoring %s", repr(text))

        return ParsedPyi(tuple(imports), top_lines, funcs)

    assign_pattern = compile_pattern("""
    simple_stmt< expr_stmt<any+> any* >
    """)

    import_pattern = compile_pattern("""
    simple_stmt<
        ( import_from< 'from' pkg=any+ 'import' ['('] names=any [')'] > |
          import_name< 'import' pkg=any+ > )
        any*
    >
    """)
    import_as_pattern = compile_pattern("""import_as_name<NAME 'as' NAME>""")

    def parse_top_import(self, node, results):
        """Takes result of import_pattern, returns component strings:

        Examples:

        'from pkg import a,b,c' gives
        ('pkg', ('a', 'b', 'c'))

        'import pkg' gives
        ('pkg', None)

        'from pkg import a as b' or 'import pkg as pkg2' are not supported.
        """

        # TODO: this might have to be generalized to "get top-level statements that aren't
        # class or function definitions":
        # _T = typing.TypeVar('_T') is used in pyis.
        # Still not clear what is and isn't valid in a pyi... Could we have a loop?

        pkg, names = results['pkg'], results.get('names', None)
        pkg = ''.join(map(str, pkg)).strip()

        if names:
            is_import_as = any(True for _ in generate_matches(names, self.import_as_pattern))

            if is_import_as:
                # fixer_util.touch_import doesn't handle this
                # If necessary, will have to stick import at top of .py file
                self.logger.warning('Ignoring unhandled import-as: %s', repr(str(node).strip()))
                return None

            names = split_comma(names.leaves())
            for name in names:
                assert 1 == len(name)
                assert name[0].type in (token.NAME, token.STAR)
            names = [name[0].value for name in names]

        return pkg, names


class StandaloneRefactoringTool(refactor.RefactoringTool):
    """Slightly modified RefactoringTool that makes the fixer accessible, for running outside of
    the standard 2to3 installation."""

    def __init__(self, options):
        self._fixer = None
        super(StandaloneRefactoringTool, self).__init__([], options=options)

    def get_fixers(self):
        if self.fixer.order == 'pre':
            return [self.fixer], []
        else:
            return [], [self.fixer]

    @property
    def fixer(self):
        if not self._fixer:
            self._fixer = FixAnnotate(self.options, self.fixer_log)
        return self._fixer

ParsedPyi = namedtuple('ParsedPyi', 'imports top_lines funcs')


def is_top_level(node):
    """Is node at top indentation level (module globals)"""
    return 0 == len(find_indentation(node))


def generate_matches(tree, pattern):
    """Generator yielding nodes in tree that match pattern."""
    for node in tree.pre_order():
        results = {}
        if pattern.match(node, results):
            yield node, results


def generate_top_matches(node, pattern):
    """Generator yielding direct children of node that match pattern."""
    for node in node.children:
        results = {}
        if pattern.match(node, results):
            yield node, results


def clean_clone(node, strip_formatting):
    """Clone node so it can be inserted in a tree. Optionally strip formatting."""
    if not node:
        return None

    if strip_formatting:
        # strip formatting and comments, represent as prettyfied string
        # For comment-style annotations, important to have a single line
        # TODO: this seems to work if node is a type annotation but will break for a general node
        # (example: 'import foo' -> 'importfoo'
        s = ''.join(', ' if token.COMMA == n.type else n.value for n in node.leaves())
        assert s

        # parse back into a Node
        node = Util.parse_string(s)
        assert 2 == len(node.children)
        node = node.children[0]
    else:
        node = node.clone()

    node.parent = None

    # TODO: strip line numbers? Not clear if they matter
    return node


def split_comma(nodes):
    """Take iterable of nodes, return list of lists of nodes"""
    def is_comma(n): return token.COMMA == n.type

    groups = itertools.groupby(nodes, is_comma)
    return [list(group) for comma, group in groups if not comma]


def annotate_string(args, py_src, pyi_src=None):
    tool = StandaloneRefactoringTool(options={})
    fixer = tool.fixer

    fixer.future_imports = tuple(args.futures)
    fixer.annotate_pep484 = args.pep484

    if pyi_src is not None:
        fixer.set_pyi_string(pyi_src)

    tree = tool.refactor_string(py_src + '\n', None)

    # tool.refactor_file knows how to handle encodings, use that

    annotated_src = str(tree)[:-1]

    return annotated_src


def get_diff(a, b):
    import difflib
    a, b = a.split('\n'), b.split('\n')

    diff = difflib.Differ().compare(a, b)
    return '\n'.join(diff)


def parse_args(argv):
    import argparse

    parser = argparse.ArgumentParser(prog=argv[0],
                                     description='Add type annotations to python code.',
                                     epilog=('If foo.pyi is not provided, types '
                                             'are derived from default values.'))

    group = parser.add_mutually_exclusive_group()

    group.add_argument('-w', action='store_true',
                       help='overwrite foo.py')

    parser.add_argument('--pep484', action='store_true',
                        help='insert type annotations in PEP-484 style')

    group.add_argument('--diff', action='store_true',
                       help='print out a diff')

    parser.add_argument('--future-import', type=str, action='append', dest='futures',
                        metavar='foo', default=[],
                        help='inserts \'from __future__ import foo\'')

    parser.add_argument('py', type=argparse.FileType('r'), metavar='foo.py',
                        help='python file to annotate')

    parser.add_argument('pyi', type=argparse.FileType('r'), nargs='?', metavar='foo.pyi',
                        help='PEP484 stub file with annotations for foo.py')

    return parser.parse_args(argv[1:])


def main(argv=None):
    """Apply the fixer without using the 2to3 main program.

    Needed so we can have our own options.
    """
    import logging
    import sys

    logging.basicConfig(level=logging.DEBUG)

    if argv is None:
        argv = sys.argv
    args = parse_args(argv)

    py_src = args.py.read()
    pyi_src = args.pyi.read() if args.pyi else None

    annotated_src = annotate_string(args, py_src, pyi_src)
    src_changed = annotated_src != py_src

    if args.diff:
        if src_changed:
            diff = get_diff(py_src, annotated_src)
            print(diff)
    elif args.w:
        if src_changed:
            with open(args.py.name, 'w') as f:
                f.write(annotated_src)
    else:
        sys.stdout.write(annotated_src)

if __name__ == '__main__':
    main()
