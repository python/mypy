from typing import List, cast

from mypy.output import TypeOutputVisitor
from mypy.nodes import (
    Node, VarDef, ClassDef, FuncDef, MypyFile, CoerceExpr, TypeExpr, CallExpr,
    TypeVarExpr
)
from mypy.visitor import NodeVisitor
from mypy.types import Void, TypeVisitor, Callable, Instance, Type, UnboundType
from mypy.maptypevar import num_slots
from mypy.transutil import tvar_arg_name
from mypy import coerce
from mypy import nodes


class PrettyPrintVisitor(NodeVisitor):
    """Convert transformed parse trees into formatted source code.

    Use automatic formatting (i.e. omit original formatting).
    """

    def __init__(self) -> None:
        super().__init__()
        self.result = [] # type: List[str]
        self.indent = 0

    def output(self) -> str:
        return ''.join(self.result)

    #
    # Definitions
    #

    def visit_mypy_file(self, file: MypyFile) -> None:
        for d in file.defs:
            d.accept(self)

    def visit_class_def(self, tdef: ClassDef) -> None:
        self.string('class ')
        self.string(tdef.name)
        if tdef.base_types:
            b = [] # type: List[str]
            for bt in tdef.base_types:
                if not bt:
                    continue
                elif isinstance(bt, UnboundType):
                    b.append(bt.name)
                elif (cast(Instance, bt)).type.fullname() != 'builtins.object':
                    typestr = bt.accept(TypeErasedPrettyPrintVisitor())
                    b.append(typestr)
            if b:
                self.string('({})'.format(', '.join(b)))
        self.string(':\n')
        for d in tdef.defs.body:
            d.accept(self)
        self.dedent()

    def visit_func_def(self, fdef: FuncDef) -> None:
        # FIX varargs, default args, keyword args etc.
        ftyp = cast(Callable, fdef.type)
        self.string('def ')
        self.string(fdef.name())
        self.string('(')
        for i in range(len(fdef.args)):
            a = fdef.args[i]
            self.string(a.name())
            if i < len(ftyp.arg_types):
                self.string(': ')
                self.type(ftyp.arg_types[i])
            else:
                self.string('xxx ')
            if i < len(fdef.args) - 1:
                self.string(', ')
        self.string(') -> ')
        self.type(ftyp.ret_type)
        fdef.body.accept(self)

    def visit_var_def(self, vdef: VarDef) -> None:
        if vdef.items[0].name() not in nodes.implicit_module_attrs:
            self.string(vdef.items[0].name())
            self.string(': ')
            self.type(vdef.items[0].type)
            if vdef.init:
                self.string(' = ')
                self.node(vdef.init)
            self.string('\n')

    #
    # Statements
    #

    def visit_block(self, b):
        self.string(':\n')
        for s in b.body:
            s.accept(self)
        self.dedent()

    def visit_pass_stmt(self, o):
        self.string('pass\n')

    def visit_return_stmt(self, o):
        self.string('return ')
        if o.expr:
            self.node(o.expr)
        self.string('\n')

    def visit_expression_stmt(self, o):
        self.node(o.expr)
        self.string('\n')

    def visit_assignment_stmt(self, o):
        if isinstance(o.rvalue, CallExpr) and isinstance(o.rvalue.analyzed,
                                                         TypeVarExpr):
            # Skip type variable definition 'x = typevar(...)'.
            return
        self.node(o.lvalues[0]) # FIX multiple lvalues
        if o.type:
            self.string(': ')
            self.type(o.type)
        self.string(' = ')
        self.node(o.rvalue)
        self.string('\n')

    def visit_if_stmt(self, o):
        self.string('if ')
        self.node(o.expr[0])
        self.node(o.body[0])
        for e, b in zip(o.expr[1:], o.body[1:]):
            self.string('elif ')
            self.node(e)
            self.node(b)
        if o.else_body:
            self.string('else')
            self.node(o.else_body)

    def visit_while_stmt(self, o):
        self.string('while ')
        self.node(o.expr)
        self.node(o.body)
        if o.else_body:
            self.string('else')
            self.node(o.else_body)

    #
    # Expressions
    #

    def visit_call_expr(self, o):
        if o.analyzed:
            o.analyzed.accept(self)
            return
        self.node(o.callee)
        self.string('(')
        self.omit_next_space = True
        for i in range(len(o.args)):
            self.node(o.args[i])
            if i < len(o.args) - 1:
                self.string(', ')
        self.string(')')

    def visit_yield_from_expr(self, o):
        self.visit_call_expr(o.callee)

    def visit_member_expr(self, o):
        self.node(o.expr)
        self.string('.' + o.name)
        if o.direct:
            self.string('!')

    def visit_name_expr(self, o):
        self.string(o.name)

    def visit_coerce_expr(self, o: CoerceExpr) -> None:
        self.string('{')
        self.full_type(o.target_type)
        if coerce.is_special_primitive(o.source_type):
            self.string(' <= ')
            self.type(o.source_type)
        self.string(' ')
        self.node(o.expr)
        self.string('}')

    def visit_type_expr(self, o: TypeExpr) -> None:
        # Type expressions are only generated during transformation, so we must
        # use automatic formatting.
        self.string('<')
        self.full_type(o.type)
        self.string('>')

    def visit_index_expr(self, o):
        if o.analyzed:
            o.analyzed.accept(self)
            return
        self.node(o.base)
        self.string('[')
        self.node(o.index)
        self.string(']')

    def visit_int_expr(self, o):
        self.string(str(o.value))

    def visit_str_expr(self, o):
        self.string(repr(o.value))

    def visit_op_expr(self, o):
        self.node(o.left)
        self.string(' %s ' % o.op)
        self.node(o.right)

    def visit_unary_expr(self, o):
        self.string(o.op)
        if o.op == 'not':
            self.string(' ')
        self.node(o.expr)

    def visit_paren_expr(self, o):
        self.string('(')
        self.node(o.expr)
        self.string(')')

    def visit_super_expr(self, o):
        self.string('super().')
        self.string(o.name)

    def visit_cast_expr(self, o):
        self.string('cast(')
        self.type(o.type)
        self.string(', ')
        self.node(o.expr)
        self.string(')')

    def visit_type_application(self, o):
        # Type arguments are erased in transformation.
        self.node(o.expr)

    def visit_undefined_expr(self, o):
        # Omit declared type as redundant.
        self.string('Undefined')

    #
    # Helpers
    #

    def string(self, s: str) -> None:
        if not s:
            return
        if self.last_output_char() == '\n':
            self.result.append(' ' * self.indent)
        self.result.append(s)
        if s.endswith(':\n'):
            self.indent += 4

    def dedent(self) -> None:
        self.indent -= 4

    def node(self, n: Node) -> None:
        n.accept(self)

    def last_output_char(self) -> str:
        if self.result:
            return self.result[-1][-1]
        return ''

    def type(self, t):
        """Pretty-print a type with erased type arguments."""
        if t:
            v = TypeErasedPrettyPrintVisitor()
            self.string(t.accept(v))

    def full_type(self, t):
        """Pretty-print a type, includingn type arguments."""
        if t:
            v = TypePrettyPrintVisitor()
            self.string(t.accept(v))


class TypeErasedPrettyPrintVisitor(TypeVisitor[str]):
    """Pretty-print types.

    Omit type variables (e.g. C instead of C[int]).

    Note that the translation does not preserve all information about the
    types, but this is fine since this is only used in test case output.
    """

    def visit_any(self, t):
        return 'Any'

    def visit_void(self, t):
        return 'None'

    def visit_instance(self, t):
        return t.type.name()

    def visit_type_var(self, t):
        return 'Any*'

    def visit_runtime_type_var(self, t):
        v = PrettyPrintVisitor()
        t.node.accept(v)
        return v.output()


class TypePrettyPrintVisitor(TypeVisitor[str]):
    """Pretty-print types.

    Include type variables.

    Note that the translation does not preserve all information about the
    types, but this is fine since this is only used in test case output.
    """

    def visit_any(self, t):
        return 'Any'

    def visit_void(self, t):
        return 'None'

    def visit_instance(self, t):
        s = t.type.name()
        if t.args:
            argstr = ', '.join([a.accept(self) for a in t.args])
            s += '[%s]' % argstr
        return s

    def visit_type_var(self, t):
        return 'Any*'

    def visit_runtime_type_var(self, t):
        v = PrettyPrintVisitor()
        t.node.accept(v)
        return v.output()
