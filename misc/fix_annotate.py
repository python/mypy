"""Fixer for lib2to3 that inserts mypy annotations into all methods.

The simplest way to run this is to copy it into lib2to3's "fixes"
subdirectory and then run "2to3 -f annotate" over your files.

The fixer transforms e.g.

  def foo(self, bar, baz=12):
      return bar + baz

into

  def foo(self, bar, baz=12):
      # type: (Any, int) -> Any
      return bar + baz

It does not do type inference but it recognizes some basic default
argument values such as numbers and strings (and assumes their type
implies the argument type).

It also uses some basic heuristics to decide whether to ignore the
first argument:

  - always if it's named 'self'
  - if there's a @classmethod decorator

Finally, it knows that __init__() is supposed to return None.
"""

from __future__ import print_function

import os
import re

from lib2to3.fixer_base import BaseFix
from lib2to3.patcomp import compile_pattern
from lib2to3.pytree import Leaf, Node
from lib2to3.fixer_util import token, syms, touch_import


class FixAnnotate(BaseFix):

    # This fixer is compatible with the bottom matcher.
    BM_compatible = True

    # This fixer shouldn't run by default.
    explicit = True

    # The pattern to match.
    PATTERN = """
              funcdef< 'def' name=any parameters< '(' [args=any] ')' > ':' suite=any+ >
              """

    counter = None if not os.getenv('MAXFIXES') else int(os.getenv('MAXFIXES'))

    def transform(self, node, results):
        if FixAnnotate.counter is not None:
            if FixAnnotate.counter <= 0:
                return
        suite = results['suite']
        children = suite[0].children

        # NOTE: I've reverse-engineered the structure of the parse tree.
        # It's always a list of nodes, the first of which contains the
        # entire suite.  Its children seem to be:
        #
        #   [0] NEWLINE
        #   [1] INDENT
        #   [2...n-2] statements (the first may be a docstring)
        #   [n-1] DEDENT
        #
        # Comments before the suite are part of the INDENT's prefix.
        #
        # "Compact" functions (e.g. "def foo(x, y): return max(x, y)")
        # have a different structure that isn't matched by PATTERN.

        ## print('-'*60)
        ## print(node)
        ## for i, ch in enumerate(children):
        ##     print(i, repr(ch.prefix), repr(ch))

        # Check if there's already an annotation.
        for ch in children:
            if ch.prefix.lstrip().startswith('# type:'):
                return  # There's already a # type: comment here; don't change anything.

        # Compute the annotation
        annot = self.make_annotation(node, results)

        # Insert '# type: {annot}' comment.
        # For reference, see lib2to3/fixes/fix_tuple_params.py in stdlib.
        if len(children) >= 2 and children[1].type == token.INDENT:
            children[1].prefix = '%s# type: %s\n%s' % (children[1].value, annot, children[1].prefix)
            children[1].changed()
            if FixAnnotate.counter is not None:
                FixAnnotate.counter -= 1

        # Also add 'from typing import Any' at the top.
        if 'Any' in annot:
            touch_import('typing', 'Any', node)

    def make_annotation(self, node, results):
        name = results['name']
        assert isinstance(name, Leaf), repr(name)
        assert name.type == token.NAME, repr(name)
        decorators = self.get_decorators(node)
        is_method = self.is_method(node)
        if name.value == '__init__' or not self.has_return_exprs(node):
            restype = 'None'
        else:
            restype = 'Any'
        args = results.get('args')
        argtypes = []
        if isinstance(args, Node):
            children = args.children
        elif isinstance(args, Leaf):
            children = [args]
        else:
            children = []
        # Interpret children according to the following grammar:
        # (('*'|'**')? NAME ['=' expr] ','?)*
        stars = inferred_type = ''
        in_default = False
        at_start = True
        for child in children:
            if isinstance(child, Leaf):
                if child.value in ('*', '**'):
                    stars += child.value
                elif child.type == token.NAME and not in_default:
                    if not is_method or not at_start or 'staticmethod' in decorators:
                        inferred_type = 'Any'
                    else:
                        # Always skip the first argument if it's named 'self'.
                        # Always skip the first argument of a class method.
                        if  child.value == 'self' or 'classmethod' in decorators:
                            pass
                        else:
                            inferred_type = 'Any'
                elif child.value == '=':
                    in_default = True
                elif in_default and child.value != ',':
                    if child.type == token.NUMBER:
                        if re.match(r'\d+[lL]?$', child.value):
                            inferred_type = 'int'
                        else:
                            inferred_type = 'float'  # TODO: complex?
                    elif child.type == token.STRING:
                        if child.value.startswith(('u', 'U')):
                            inferred_type = 'unicode'
                        else:
                            inferred_type = 'str'
                    elif child.type == token.NAME and child.value in ('True', 'False'):
                        inferred_type = 'bool'
                elif child.value == ',':
                    if inferred_type:
                        argtypes.append(stars + inferred_type)
                    # Reset
                    stars = inferred_type = ''
                    in_default = False
                    at_start = False
        if inferred_type:
            argtypes.append(stars + inferred_type)
        return '(' + ', '.join(argtypes) + ') -> ' + restype

    # The parse tree has a different shape when there is a single
    # decorator vs. when there are multiple decorators.
    DECORATED = "decorated< (d=decorator | decorators< dd=decorator+ >) funcdef >"
    decorated = compile_pattern(DECORATED)

    def get_decorators(self, node):
        """Return a list of decorators found on a function definition.

        This is a list of strings; only simple decorators
        (e.g. @staticmethod) are returned.

        If the function is undecorated or only non-simple decorators
        are found, return [].
        """
        if node.parent is None:
            return []
        results = {}
        if not self.decorated.match(node.parent, results):
            return []
        decorators = results.get('dd') or [results['d']]
        decs = []
        for d in decorators:
            for child in d.children:
                if isinstance(child, Leaf) and child.type == token.NAME:
                    decs.append(child.value)
        return decs

    def is_method(self, node):
        """Return whether the node occurs (directly) inside a class."""
        node = node.parent
        while node is not None:
            if node.type == syms.classdef:
                return True
            if node.type == syms.funcdef:
                return False
            node = node.parent
        return False

    RETURN_EXPR = "return_stmt< 'return' any >"
    return_expr = compile_pattern(RETURN_EXPR)

    def has_return_exprs(self, node):
        """Traverse the tree below node looking for 'return expr'.

        Return True if at least 'return expr' is found, False if not.
        (If both 'return' and 'return expr' are found, return True.)
        """
        results = {}
        if self.return_expr.match(node, results):
            return True
        for child in node.children:
            if child.type not in (syms.funcdef, syms.classdef):
                if self.has_return_exprs(child):
                    return True
        return False
