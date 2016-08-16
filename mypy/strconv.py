"""Conversion of parse tree nodes to strings."""

import re
import os

from typing import Any, List

from mypy.util import dump_tagged, short_type
import mypy.nodes
from mypy.visitor import NodeVisitor


class StrConv(NodeVisitor[str]):
    """Visitor for converting a Node to a human-readable string.

    For example, an MypyFile node from program '1' is converted into
    something like this:

      MypyFile:1(
        fnam
        ExpressionStmt:1(
          IntExpr(1)))
    """
    def dump(self, nodes: List[Any], obj: 'mypy.nodes.Node') -> str:
        """Convert a list of items to a multiline pretty-printed string.

        The tag is produced from the type name of obj and its line
        number. See mypy.util.dump_tagged for a description of the nodes
        argument.
        """
        return dump_tagged(nodes, short_type(obj) + ':' + str(obj.line))

    def func_helper(self, o: 'mypy.nodes.FuncItem') -> List[Any]:
        """Return a list in a format suitable for dump() that represents the
        arguments and the body of a function. The caller can then decorate the
        array with information specific to methods, global functions or
        anonymous functions.
        """
        args = []
        init = []
        extra = []
        for i, arg in enumerate(o.arguments):
            kind = arg.kind
            if kind == mypy.nodes.ARG_POS:
                args.append(o.arguments[i].variable)
            elif kind in (mypy.nodes.ARG_OPT, mypy.nodes.ARG_NAMED):
                args.append(o.arguments[i].variable)
                init.append(o.arguments[i].initialization_statement)
            elif kind == mypy.nodes.ARG_STAR:
                extra.append(('VarArg', [o.arguments[i].variable]))
            elif kind == mypy.nodes.ARG_STAR2:
                extra.append(('DictVarArg', [o.arguments[i].variable]))
        a = []  # type: List[Any]
        if args:
            a.append(('Args', args))
        if o.type:
            a.append(o.type)
        if init:
            a.append(('Init', init))
        if o.is_generator:
            a.append('Generator')
        a.extend(extra)
        a.append(o.body)
        return a

    # Top-level structures

    def visit_mypy_file(self, o: 'mypy.nodes.MypyFile') -> str:
        # Skip implicit definitions.
        a = [o.defs]  # type: List[Any]
        if o.is_bom:
            a.insert(0, 'BOM')
        # Omit path to special file with name "main". This is used to simplify
        # test case descriptions; the file "main" is used by default in many
        # test cases.
        if o.path is not None and o.path != 'main':
            # Insert path. Normalize directory separators to / to unify test
            # case# output in all platforms.
            a.insert(0, o.path.replace(os.sep, '/'))
        if o.ignored_lines:
            a.append('IgnoredLines(%s)' % ', '.join(str(line)
                                                    for line in sorted(o.ignored_lines)))
        return self.dump(a, o)

    def visit_import(self, o: 'mypy.nodes.Import') -> str:
        a = []
        for id, as_id in o.ids:
            if as_id is not None:
                a.append('{} : {}'.format(id, as_id))
            else:
                a.append(id)
        return 'Import:{}({})'.format(o.line, ', '.join(a))

    def visit_import_from(self, o):
        a = []
        for name, as_name in o.names:
            if as_name is not None:
                a.append('{} : {}'.format(name, as_name))
            else:
                a.append(name)
        return 'ImportFrom:{}({}, [{}])'.format(o.line, "." * o.relative + o.id, ', '.join(a))

    def visit_import_all(self, o):
        return 'ImportAll:{}({})'.format(o.line, "." * o.relative + o.id)

    # Definitions

    def visit_func_def(self, o):
        a = self.func_helper(o)
        a.insert(0, o.name())
        if mypy.nodes.ARG_NAMED in [arg.kind for arg in o.arguments]:
            a.insert(1, 'MaxPos({})'.format(o.max_pos))
        if o.is_abstract:
            a.insert(-1, 'Abstract')
        if o.is_static:
            a.insert(-1, 'Static')
        if o.is_class:
            a.insert(-1, 'Class')
        if o.is_property:
            a.insert(-1, 'Property')
        return self.dump(a, o)

    def visit_overloaded_func_def(self, o):
        a = o.items[:]
        if o.type:
            a.insert(0, o.type)
        return self.dump(a, o)

    def visit_class_def(self, o):
        a = [o.name, o.defs.body]
        # Display base types unless they are implicitly just builtins.object
        # (in this case base_type_exprs is empty).
        if o.base_type_exprs:
            if o.info and o.info.bases:
                a.insert(1, ('BaseType', o.info.bases))
            else:
                a.insert(1, ('BaseTypeExpr', o.base_type_exprs))
        if o.type_vars:
            a.insert(1, ('TypeVars', o.type_vars))
        if o.metaclass:
            a.insert(1, 'Metaclass({})'.format(o.metaclass))
        if o.decorators:
            a.insert(1, ('Decorators', o.decorators))
        if o.is_builtinclass:
            a.insert(1, 'Builtinclass')
        if o.info and o.info._promote:
            a.insert(1, 'Promote({})'.format(o.info._promote))
        if o.info and o.info.tuple_type:
            a.insert(1, ('TupleType', [o.info.tuple_type]))
        if o.info and o.info.fallback_to_any:
            a.insert(1, 'FallbackToAny')
        return self.dump(a, o)

    def visit_var(self, o):
        l = ''
        # Add :nil line number tag if no line number is specified to remain
        # compatible with old test case descriptions that assume this.
        if o.line < 0:
            l = ':nil'
        return 'Var' + l + '(' + o.name() + ')'

    def visit_global_decl(self, o):
        return self.dump([o.names], o)

    def visit_nonlocal_decl(self, o):
        return self.dump([o.names], o)

    def visit_decorator(self, o):
        return self.dump([o.var, o.decorators, o.func], o)

    def visit_annotation(self, o):
        return 'Type:{}({})'.format(o.line, o.type)

    # Statements

    def visit_block(self, o):
        return self.dump(o.body, o)

    def visit_expression_stmt(self, o):
        return self.dump([o.expr], o)

    def visit_assignment_stmt(self, o):
        if len(o.lvalues) > 1:
            a = [('Lvalues', o.lvalues)]
        else:
            a = [o.lvalues[0]]
        a.append(o.rvalue)
        if o.type:
            a.append(o.type)
        return self.dump(a, o)

    def visit_operator_assignment_stmt(self, o):
        return self.dump([o.op, o.lvalue, o.rvalue], o)

    def visit_while_stmt(self, o):
        a = [o.expr, o.body]
        if o.else_body:
            a.append(('Else', o.else_body.body))
        return self.dump(a, o)

    def visit_for_stmt(self, o):
        a = []
        if o.is_async:
            a.append(('Async', ''))
        a.extend([o.index, o.expr, o.body])
        if o.else_body:
            a.append(('Else', o.else_body.body))
        return self.dump(a, o)

    def visit_return_stmt(self, o):
        return self.dump([o.expr], o)

    def visit_if_stmt(self, o):
        a = []
        for i in range(len(o.expr)):
            a.append(('If', [o.expr[i]]))
            a.append(('Then', o.body[i].body))

        if not o.else_body:
            return self.dump(a, o)
        else:
            return self.dump([a, ('Else', o.else_body.body)], o)

    def visit_break_stmt(self, o):
        return self.dump([], o)

    def visit_continue_stmt(self, o):
        return self.dump([], o)

    def visit_pass_stmt(self, o):
        return self.dump([], o)

    def visit_raise_stmt(self, o):
        return self.dump([o.expr, o.from_expr], o)

    def visit_assert_stmt(self, o):
        return self.dump([o.expr], o)

    def visit_yield_stmt(self, o):
        return self.dump([o.expr], o)

    def visit_yield_from_stmt(self, o):
        return self.dump([o.expr], o)

    def visit_yield_expr(self, o):
        return self.dump([o.expr], o)

    def visit_await_expr(self, o):
        return self.dump([o.expr], o)

    def visit_del_stmt(self, o):
        return self.dump([o.expr], o)

    def visit_try_stmt(self, o):
        a = [o.body]

        for i in range(len(o.vars)):
            a.append(o.types[i])
            if o.vars[i]:
                a.append(o.vars[i])
            a.append(o.handlers[i])

        if o.else_body:
            a.append(('Else', o.else_body.body))
        if o.finally_body:
            a.append(('Finally', o.finally_body.body))

        return self.dump(a, o)

    def visit_with_stmt(self, o):
        a = []
        if o.is_async:
            a.append(('Async', ''))
        for i in range(len(o.expr)):
            a.append(('Expr', [o.expr[i]]))
            if o.target[i]:
                a.append(('Target', [o.target[i]]))
        return self.dump(a + [o.body], o)

    def visit_print_stmt(self, o):
        a = o.args[:]
        if o.target:
            a.append(('Target', [o.target]))
        if o.newline:
            a.append('Newline')
        return self.dump(a, o)

    def visit_exec_stmt(self, o):
        return self.dump([o.expr, o.variables1, o.variables2], o)

    # Expressions

    # Simple expressions

    def visit_int_expr(self, o):
        return 'IntExpr({})'.format(o.value)

    def visit_str_expr(self, o):
        return 'StrExpr({})'.format(self.str_repr(o.value))

    def visit_bytes_expr(self, o):
        return 'BytesExpr({})'.format(self.str_repr(o.value))

    def visit_unicode_expr(self, o):
        return 'UnicodeExpr({})'.format(self.str_repr(o.value))

    def str_repr(self, s):
        s = re.sub(r'\\u[0-9a-fA-F]{4}', lambda m: '\\' + m.group(0), s)
        return re.sub('[^\\x20-\\x7e]',
                      lambda m: r'\u%.4x' % ord(m.group(0)), s)

    def visit_float_expr(self, o):
        return 'FloatExpr({})'.format(o.value)

    def visit_complex_expr(self, o):
        return 'ComplexExpr({})'.format(o.value)

    def visit_ellipsis(self, o):
        return 'Ellipsis'

    def visit_star_expr(self, o):
        return self.dump([o.expr], o)

    def visit_name_expr(self, o):
        return (short_type(o) + '(' + self.pretty_name(o.name, o.kind,
                                                       o.fullname, o.is_def)
                + ')')

    def pretty_name(self, name, kind, fullname, is_def):
        n = name
        if is_def:
            n += '*'
        if kind == mypy.nodes.GDEF or (fullname != name and
                                       fullname is not None):
            # Append fully qualified name for global references.
            n += ' [{}]'.format(fullname)
        elif kind == mypy.nodes.LDEF:
            # Add tag to signify a local reference.
            n += ' [l]'
        elif kind == mypy.nodes.MDEF:
            # Add tag to signify a member reference.
            n += ' [m]'
        return n

    def visit_member_expr(self, o):
        return self.dump([o.expr, self.pretty_name(o.name, o.kind, o.fullname,
                                                   o.is_def)], o)

    def visit_yield_from_expr(self, o):
        if o.expr:
            return self.dump([o.expr.accept(self)], o)
        else:
            return self.dump([], o)

    def visit_call_expr(self, o):
        if o.analyzed:
            return o.analyzed.accept(self)
        args = []
        extra = []
        for i, kind in enumerate(o.arg_kinds):
            if kind in [mypy.nodes.ARG_POS, mypy.nodes.ARG_STAR]:
                args.append(o.args[i])
                if kind == mypy.nodes.ARG_STAR:
                    extra.append('VarArg')
            elif kind == mypy.nodes.ARG_NAMED:
                extra.append(('KwArgs', [o.arg_names[i], o.args[i]]))
            elif kind == mypy.nodes.ARG_STAR2:
                extra.append(('DictVarArg', [o.args[i]]))
            else:
                raise RuntimeError('unknown kind %d' % kind)

        return self.dump([o.callee, ('Args', args)] + extra, o)

    def visit_op_expr(self, o):
        return self.dump([o.op, o.left, o.right], o)

    def visit_comparison_expr(self, o):
        return self.dump([o.operators, o.operands], o)

    def visit_cast_expr(self, o):
        return self.dump([o.expr, o.type], o)

    def visit_reveal_type_expr(self, o):
        return self.dump([o.expr], o)

    def visit_unary_expr(self, o):
        return self.dump([o.op, o.expr], o)

    def visit_list_expr(self, o):
        return self.dump(o.items, o)

    def visit_dict_expr(self, o):
        return self.dump([[k, v] for k, v in o.items], o)

    def visit_set_expr(self, o):
        return self.dump(o.items, o)

    def visit_tuple_expr(self, o):
        return self.dump(o.items, o)

    def visit_index_expr(self, o):
        if o.analyzed:
            return o.analyzed.accept(self)
        return self.dump([o.base, o.index], o)

    def visit_super_expr(self, o):
        return self.dump([o.name], o)

    def visit_type_application(self, o):
        return self.dump([o.expr, ('Types', o.types)], o)

    def visit_type_var_expr(self, o):
        import mypy.types
        a = []
        if o.variance == mypy.nodes.COVARIANT:
            a += ['Variance(COVARIANT)']
        if o.variance == mypy.nodes.CONTRAVARIANT:
            a += ['Variance(CONTRAVARIANT)']
        if o.values:
            a += [('Values', o.values)]
        if not mypy.types.is_named_instance(o.upper_bound, 'builtins.object'):
            a += ['UpperBound({})'.format(o.upper_bound)]
        return self.dump(a, o)

    def visit_type_alias_expr(self, o):
        return 'TypeAliasExpr({})'.format(o.type)

    def visit_namedtuple_expr(self, o):
        return 'NamedTupleExpr:{}({}, {})'.format(o.line,
                                                  o.info.name(),
                                                  o.info.tuple_type)

    def visit__promote_expr(self, o):
        return 'PromoteExpr:{}({})'.format(o.line, o.type)

    def visit_newtype_expr(self, o):
        return 'NewTypeExpr:{}({}, {})'.format(o.line, o.fullname(), self.dump([o.value], o))

    def visit_func_expr(self, o):
        a = self.func_helper(o)
        return self.dump(a, o)

    def visit_generator_expr(self, o):
        condlists = o.condlists if any(o.condlists) else None
        return self.dump([o.left_expr, o.indices, o.sequences, condlists], o)

    def visit_list_comprehension(self, o):
        return self.dump([o.generator], o)

    def visit_set_comprehension(self, o):
        return self.dump([o.generator], o)

    def visit_dictionary_comprehension(self, o):
        condlists = o.condlists if any(o.condlists) else None
        return self.dump([o.key, o.value, o.indices, o.sequences, condlists], o)

    def visit_conditional_expr(self, o):
        return self.dump([('Condition', [o.cond]), o.if_expr, o.else_expr], o)

    def visit_slice_expr(self, o):
        a = [o.begin_index, o.end_index, o.stride]
        if not a[0]:
            a[0] = '<empty>'
        if not a[1]:
            a[1] = '<empty>'
        return self.dump(a, o)

    def visit_backquote_expr(self, o):
        return self.dump([o.expr], o)
