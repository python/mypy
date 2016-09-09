"""Abstract syntax tree node classes (i.e. parse tree)."""

import os
import re
from abc import abstractmethod, ABCMeta

from typing import (
    Any, TypeVar, List, Tuple, cast, Set, Dict, Union, Optional
)

from mypy.lex import Token
import mypy.strconv
from mypy.visitor import NodeVisitor
from mypy.util import dump_tagged, short_type


class Context:
    """Base type for objects that are valid as error message locations."""
    @abstractmethod
    def get_line(self) -> int: pass


if False:
    # break import cycle only needed for mypy
    import mypy.types


T = TypeVar('T')

JsonDict = Dict[str, Any]


# Symbol table node kinds
#
# TODO rename to use more descriptive names

LDEF = 0  # type: int
GDEF = 1  # type: int
MDEF = 2  # type: int
MODULE_REF = 3  # type: int
# Type variable declared using TypeVar(...) has kind UNBOUND_TVAR. It's not
# valid as a type. A type variable is valid as a type (kind BOUND_TVAR) within
# (1) a generic class that uses the type variable as a type argument or
# (2) a generic function that refers to the type variable in its signature.
UNBOUND_TVAR = 4  # type: int
BOUND_TVAR = 5  # type: int
TYPE_ALIAS = 6  # type: int
# Placeholder for a name imported via 'from ... import'. Second phase of
# semantic will replace this the actual imported reference. This is
# needed so that we can detect whether a name has been imported during
# XXX what?
UNBOUND_IMPORTED = 7  # type: int


LITERAL_YES = 2
LITERAL_TYPE = 1
LITERAL_NO = 0

# Hard coded name of Enum baseclass.
ENUM_BASECLASS = "enum.Enum"

node_kinds = {
    LDEF: 'Ldef',
    GDEF: 'Gdef',
    MDEF: 'Mdef',
    MODULE_REF: 'ModuleRef',
    UNBOUND_TVAR: 'UnboundTvar',
    BOUND_TVAR: 'Tvar',
    TYPE_ALIAS: 'TypeAlias',
    UNBOUND_IMPORTED: 'UnboundImported',
}
inverse_node_kinds = {_kind: _name for _name, _kind in node_kinds.items()}


implicit_module_attrs = {'__name__': '__builtins__.str',
                         '__doc__': '__builtins__.str',
                         '__file__': '__builtins__.str',
                         '__package__': '__builtins__.str'}


type_aliases = {
    'typing.List': '__builtins__.list',
    'typing.Dict': '__builtins__.dict',
    'typing.Set': '__builtins__.set',
}

reverse_type_aliases = dict((name.replace('__builtins__', 'builtins'), alias)
                            for alias, name in type_aliases.items())  # type: Dict[str, str]


class Node(Context):
    """Common base class for all non-type parse tree nodes."""

    line = -1

    literal = LITERAL_NO
    literal_hash = None  # type: Any

    def __str__(self) -> str:
        ans = self.accept(mypy.strconv.StrConv())
        if ans is None:
            return repr(self)
        return ans

    def set_line(self, target: Union[Token, 'Node', int]) -> 'Node':
        if isinstance(target, int):
            self.line = target
        else:
            self.line = target.line
        return self

    def get_line(self) -> int:
        # TODO this should be just 'line'
        return self.line

    def accept(self, visitor: NodeVisitor[T]) -> T:
        raise RuntimeError('Not implemented')


# These are placeholders for a future refactoring; see #1783.
# For now they serve as (unchecked) documentation of what various
# fields of Node subtypes are expected to contain.
Statement = Node
Expression = Node


class SymbolNode(Node):
    # Nodes that can be stored in a symbol table.

    # TODO do not use methods for these

    @abstractmethod
    def name(self) -> str: pass

    @abstractmethod
    def fullname(self) -> str: pass

    # NOTE: Can't use @abstractmethod, since many subclasses of Node
    # don't implement serialize().
    def serialize(self) -> Any:
        raise NotImplementedError('Cannot serialize {} instance'.format(self.__class__.__name__))

    @classmethod
    def deserialize(cls, data: JsonDict) -> 'SymbolNode':
        classname = data['.class']
        glo = globals()
        if classname in glo:
            cl = glo[classname]
            if issubclass(cl, cls) and 'deserialize' in cl.__dict__:
                return cl.deserialize(data)
        raise NotImplementedError('unexpected .class {}'.format(classname))


class MypyFile(SymbolNode, Statement):
    """The abstract syntax tree of a single source file."""

    # Module name ('__main__' for initial file)
    _name = None      # type: str
    # Fully qualified module name
    _fullname = None  # type: str
    # Path to the file (None if not known)
    path = ''
    # Top-level definitions and statements
    defs = None  # type: List[Statement]
    # Is there a UTF-8 BOM at the start?
    is_bom = False
    names = None  # type: SymbolTable
    # All import nodes within the file (also ones within functions etc.)
    imports = None  # type: List[ImportBase]
    # Lines to ignore when checking
    ignored_lines = None  # type: Set[int]
    # Is this file represented by a stub file (.pyi)?
    is_stub = False
    # Do weak typing globally in the file?
    weak_opts = None  # type: Set[str]

    def __init__(self,
                 defs: List[Statement],
                 imports: List['ImportBase'],
                 is_bom: bool = False,
                 ignored_lines: Set[int] = None,
                 weak_opts: Set[str] = None) -> None:
        self.defs = defs
        self.line = 1  # Dummy line number
        self.imports = imports
        self.is_bom = is_bom
        self.weak_opts = weak_opts
        if ignored_lines:
            self.ignored_lines = ignored_lines
        else:
            self.ignored_lines = set()

    def name(self) -> str:
        return self._name

    def fullname(self) -> str:
        return self._fullname

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_mypy_file(self)

    def is_package_init_file(self) -> bool:
        return not (self.path is None) and len(self.path) != 0 \
            and os.path.basename(self.path).startswith('__init__.')

    def serialize(self) -> JsonDict:
        return {'.class': 'MypyFile',
                '_name': self._name,
                '_fullname': self._fullname,
                'names': self.names.serialize(self._fullname),
                'is_stub': self.is_stub,
                'path': self.path,
                }

    @classmethod
    def deserialize(cls, data: JsonDict) -> 'MypyFile':
        assert data['.class'] == 'MypyFile', data
        tree = MypyFile([], [])
        tree._name = data['_name']
        tree._fullname = data['_fullname']
        tree.names = SymbolTable.deserialize(data['names'])
        tree.is_stub = data['is_stub']
        tree.path = data['path']
        return tree


class ImportBase(Statement):
    """Base class for all import statements."""
    is_unreachable = False
    is_top_level = False  # Set by semanal.FirstPass
    # If an import replaces existing definitions, we construct dummy assignment
    # statements that assign the imported names to the names in the current scope,
    # for type checking purposes. Example:
    #
    #     x = 1
    #     from m import x   <-- add assignment representing "x = m.x"
    assignments = None  # type: List[AssignmentStmt]

    def __init__(self) -> None:
        self.assignments = []


class Import(ImportBase):
    """import m [as n]"""

    ids = None  # type: List[Tuple[str, Optional[str]]]     # (module id, as id)

    def __init__(self, ids: List[Tuple[str, Optional[str]]]) -> None:
        super().__init__()
        self.ids = ids

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_import(self)


class ImportFrom(ImportBase):
    """from m import x [as y], ..."""

    names = None  # type: List[Tuple[str, Optional[str]]]  # Tuples (name, as name)

    def __init__(self, id: str, relative: int, names: List[Tuple[str, Optional[str]]]) -> None:
        super().__init__()
        self.id = id
        self.names = names
        self.relative = relative

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_import_from(self)


class ImportAll(ImportBase):
    """from m import *"""

    def __init__(self, id: str, relative: int) -> None:
        super().__init__()
        self.id = id
        self.relative = relative

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_import_all(self)


class FuncBase(SymbolNode):
    """Abstract base class for function-like nodes"""

    # Type signature. This is usually CallableType or Overloaded, but it can be something else for
    # decorated functions/
    type = None  # type: mypy.types.Type
    # If method, reference to TypeInfo
    info = None  # type: TypeInfo
    is_property = False
    _fullname = None  # type: str       # Name with module prefix

    @abstractmethod
    def name(self) -> str: pass

    def fullname(self) -> str:
        return self._fullname

    def is_method(self) -> bool:
        return bool(self.info)


class OverloadedFuncDef(FuncBase, Statement):
    """A logical node representing all the variants of an overloaded function.

    This node has no explicit representation in the source program.
    Overloaded variants must be consecutive in the source file.
    """

    items = None  # type: List[Decorator]

    def __init__(self, items: List['Decorator']) -> None:
        self.items = items
        self.set_line(items[0].line)

    def name(self) -> str:
        return self.items[0].func.name()

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_overloaded_func_def(self)

    def serialize(self) -> JsonDict:
        return {'.class': 'OverloadedFuncDef',
                'items': [i.serialize() for i in self.items],
                'type': None if self.type is None else self.type.serialize(),
                'fullname': self._fullname,
                'is_property': self.is_property,
                }

    @classmethod
    def deserialize(cls, data: JsonDict) -> 'OverloadedFuncDef':
        assert data['.class'] == 'OverloadedFuncDef'
        res = OverloadedFuncDef([Decorator.deserialize(d) for d in data['items']])
        if data.get('type') is not None:
            res.type = mypy.types.Type.deserialize(data['type'])
        res._fullname = data['fullname']
        res.is_property = data['is_property']
        # NOTE: res.info will be set in the fixup phase.
        return res


class Argument(Node):
    """A single argument in a FuncItem."""

    variable = None  # type: Var
    type_annotation = None  # type: Optional[mypy.types.Type]
    initializater = None  # type: Optional[Expression]
    kind = None  # type: int
    initialization_statement = None  # type: Optional[AssignmentStmt]

    def __init__(self, variable: 'Var', type_annotation: 'Optional[mypy.types.Type]',
            initializer: Optional[Expression], kind: int,
            initialization_statement: Optional['AssignmentStmt'] = None) -> None:
        self.variable = variable

        self.type_annotation = type_annotation
        self.initializer = initializer

        self.initialization_statement = initialization_statement
        if not self.initialization_statement:
            self.initialization_statement = self._initialization_statement()

        self.kind = kind

    def _initialization_statement(self) -> Optional['AssignmentStmt']:
        """Convert the initializer into an assignment statement.
        """
        if not self.initializer:
            return None

        rvalue = self.initializer
        lvalue = NameExpr(self.variable.name())
        assign = AssignmentStmt([lvalue], rvalue)
        return assign

    def set_line(self, target: Union[Token, Node, int]) -> Node:
        super().set_line(target)

        if self.initializer:
            self.initializer.set_line(self.line)

        self.variable.set_line(self.line)

        if self.initialization_statement:
            self.initialization_statement.set_line(self.line)
            self.initialization_statement.lvalues[0].set_line(self.line)

    def serialize(self) -> JsonDict:
        # Note: we are deliberately not saving the type annotation since
        # it is not used by later stages of mypy.
        data = {'.class': 'Argument',
                'kind': self.kind,
                'variable': self.variable.serialize(),
                }  # type: JsonDict
        # TODO: initializer?
        return data

    @classmethod
    def deserialize(cls, data: JsonDict) -> 'Argument':
        assert data['.class'] == 'Argument'
        return Argument(Var.deserialize(data['variable']),
                        None,
                        None,  # TODO: initializer?
                        kind=data['kind'])


class FuncItem(FuncBase):
    arguments = []  # type: List[Argument]
    arg_names = []  # type: List[str]
    arg_kinds = []  # type: List[int]
    # Minimum number of arguments
    min_args = 0
    # Maximum number of positional arguments, -1 if no explicit limit (*args not included)
    max_pos = 0
    body = None  # type: Block
    # Is this an overload variant of function with more than one overload variant?
    is_overload = False
    is_generator = False   # Contains a yield statement?
    is_coroutine = False   # Defined using 'async def' syntax?
    is_awaitable_coroutine = False  # Decorated with '@{typing,asyncio}.coroutine'?
    is_static = False      # Uses @staticmethod?
    is_class = False       # Uses @classmethod?
    # Variants of function with type variables with values expanded
    expanded = None  # type: List[FuncItem]

    FLAGS = [
        'is_overload', 'is_generator', 'is_coroutine', 'is_awaitable_coroutine',
        'is_static', 'is_class',
    ]

    def __init__(self, arguments: List[Argument], body: 'Block',
                 typ: 'mypy.types.FunctionLike' = None) -> None:
        self.arguments = arguments
        self.arg_names = [arg.variable.name() for arg in self.arguments]
        self.arg_kinds = [arg.kind for arg in self.arguments]
        self.max_pos = self.arg_kinds.count(ARG_POS) + self.arg_kinds.count(ARG_OPT)
        self.body = body
        self.type = typ
        self.expanded = []

        self.min_args = 0
        for i in range(len(self.arguments)):
            if self.arguments[i] is None and i < self.max_fixed_argc():
                self.min_args = i + 1

    def max_fixed_argc(self) -> int:
        return self.max_pos

    def set_line(self, target: Union[Token, Node, int]) -> Node:
        super().set_line(target)
        for arg in self.arguments:
            arg.set_line(self.line)
        return self

    def is_dynamic(self) -> bool:
        return self.type is None


class FuncDef(FuncItem, Statement):
    """Function definition.

    This is a non-lambda function defined using 'def'.
    """

    is_decorated = False
    is_conditional = False             # Defined conditionally (within block)?
    is_abstract = False
    is_property = False
    original_def = None  # type: Union[None, FuncDef, Var]  # Original conditional definition

    FLAGS = FuncItem.FLAGS + [
        'is_decorated', 'is_conditional', 'is_abstract', 'is_property'
    ]

    def __init__(self,
                 name: str,              # Function name
                 arguments: List[Argument],
                 body: 'Block',
                 typ: 'mypy.types.FunctionLike' = None) -> None:
        super().__init__(arguments, body, typ)
        self._name = name

    def name(self) -> str:
        return self._name

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_func_def(self)

    def is_constructor(self) -> bool:
        return self.info is not None and self._name == '__init__'

    def serialize(self) -> JsonDict:
        # We're deliberating omitting arguments and storing only arg_names and
        # arg_kinds for space-saving reasons (arguments is not used in later
        # stages of mypy).
        # TODO: After a FuncDef is deserialized, the only time we use `arg_names`
        # and `arg_kinds` is when `type` is None and we need to infer a type. Can
        # we store the inferred type ahead of time?
        return {'.class': 'FuncDef',
                'name': self._name,
                'fullname': self._fullname,
                'arg_names': self.arg_names,
                'arg_kinds': self.arg_kinds,
                'type': None if self.type is None else self.type.serialize(),
                'flags': get_flags(self, FuncDef.FLAGS),
                # TODO: Do we need expanded, original_def?
                }

    @classmethod
    def deserialize(cls, data: JsonDict) -> 'FuncDef':
        assert data['.class'] == 'FuncDef'
        body = Block([])
        ret = FuncDef(data['name'],
                      [],
                      body,
                      (None if data['type'] is None
                       else mypy.types.FunctionLike.deserialize(data['type'])))
        ret._fullname = data['fullname']
        set_flags(ret, data['flags'])
        # NOTE: ret.info is set in the fixup phase.
        ret.arg_names = data['arg_names']
        ret.arg_kinds = data['arg_kinds']
        # Mark these as 'None' so that future uses will trigger an error
        ret.arguments = None
        ret.max_pos = None
        ret.min_args = None
        return ret


class Decorator(SymbolNode, Statement):
    """A decorated function.

    A single Decorator object can include any number of function decorators.
    """

    func = None  # type: FuncDef                # Decorated function
    decorators = None  # type: List[Expression] # Decorators, at least one  # XXX Not true
    var = None  # type: Var                     # Represents the decorated function obj
    is_overload = False

    def __init__(self, func: FuncDef, decorators: List[Expression],
                 var: 'Var') -> None:
        self.func = func
        self.decorators = decorators
        self.var = var
        self.is_overload = False

    def name(self) -> str:
        return self.func.name()

    def fullname(self) -> str:
        return self.func.fullname()

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_decorator(self)

    def serialize(self) -> JsonDict:
        return {'.class': 'Decorator',
                'func': self.func.serialize(),
                'var': self.var.serialize(),
                'is_overload': self.is_overload,
                }

    @classmethod
    def deserialize(cls, data: JsonDict) -> 'Decorator':
        assert data['.class'] == 'Decorator'
        dec = Decorator(FuncDef.deserialize(data['func']),
                        [],
                        Var.deserialize(data['var']))
        dec.is_overload = data['is_overload']
        return dec


class Var(SymbolNode, Statement):
    """A variable.

    It can refer to global/local variable or a data attribute.
    """

    _name = None      # type: str   # Name without module prefix
    _fullname = None  # type: str   # Name with module prefix
    info = None  # type: TypeInfo   # Defining class (for member variables)
    type = None  # type: mypy.types.Type # Declared or inferred type, or None
    # Is this the first argument to an ordinary method (usually "self")?
    is_self = False
    is_ready = False  # If inferred, is the inferred type available?
    # Is this initialized explicitly to a non-None value in class body?
    is_initialized_in_class = False
    is_staticmethod = False
    is_classmethod = False
    is_property = False
    is_settable_property = False
    # Set to true when this variable refers to a module we were unable to
    # parse for some reason (eg a silenced module)
    is_suppressed_import = False

    FLAGS = [
        'is_self', 'is_ready', 'is_initialized_in_class', 'is_staticmethod',
        'is_classmethod', 'is_property', 'is_settable_property', 'is_suppressed_import'
    ]

    def __init__(self, name: str, type: 'mypy.types.Type' = None) -> None:
        self._name = name
        self.type = type
        self.is_self = False
        self.is_ready = True
        self.is_initialized_in_class = False

    def name(self) -> str:
        return self._name

    def fullname(self) -> str:
        return self._fullname

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_var(self)

    def serialize(self) -> JsonDict:
        # TODO: Leave default values out?
        # NOTE: Sometimes self.is_ready is False here, but we don't care.
        data = {'.class': 'Var',
                'name': self._name,
                'fullname': self._fullname,
                'type': None if self.type is None else self.type.serialize(),
                'flags': get_flags(self, Var.FLAGS),
                }  # type: JsonDict
        return data

    @classmethod
    def deserialize(cls, data: JsonDict) -> 'Var':
        assert data['.class'] == 'Var'
        name = data['name']
        type = None if data['type'] is None else mypy.types.Type.deserialize(data['type'])
        v = Var(name, type)
        v._fullname = data['fullname']
        set_flags(v, data['flags'])
        return v


class ClassDef(Statement):
    """Class definition"""

    name = None  # type: str       # Name of the class without module prefix
    fullname = None  # type: str   # Fully qualified name of the class
    defs = None  # type: Block
    type_vars = None  # type: List[mypy.types.TypeVarDef]
    # Base class expressions (not semantically analyzed -- can be arbitrary expressions)
    base_type_exprs = None  # type: List[Expression]
    info = None  # type: TypeInfo  # Related TypeInfo
    metaclass = ''
    decorators = None  # type: List[Expression]
    # Built-in/extension class? (single implementation inheritance only)
    is_builtinclass = False
    has_incompatible_baseclass = False

    def __init__(self,
                 name: str,
                 defs: 'Block',
                 type_vars: List['mypy.types.TypeVarDef'] = None,
                 base_type_exprs: List[Expression] = None,
                 metaclass: str = None) -> None:
        self.name = name
        self.defs = defs
        self.type_vars = type_vars or []
        self.base_type_exprs = base_type_exprs or []
        self.metaclass = metaclass
        self.decorators = []

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_class_def(self)

    def is_generic(self) -> bool:
        return self.info.is_generic()

    def serialize(self) -> JsonDict:
        # Not serialized: defs, base_type_exprs, decorators
        return {'.class': 'ClassDef',
                'name': self.name,
                'fullname': self.fullname,
                'type_vars': [v.serialize() for v in self.type_vars],
                'metaclass': self.metaclass,
                'is_builtinclass': self.is_builtinclass,
                }

    @classmethod
    def deserialize(self, data: JsonDict) -> 'ClassDef':
        assert data['.class'] == 'ClassDef'
        res = ClassDef(data['name'],
                       Block([]),
                       [mypy.types.TypeVarDef.deserialize(v) for v in data['type_vars']],
                       metaclass=data['metaclass'],
                       )
        res.fullname = data['fullname']
        res.is_builtinclass = data['is_builtinclass']
        return res


class GlobalDecl(Statement):
    """Declaration global x, y, ..."""

    names = None  # type: List[str]

    def __init__(self, names: List[str]) -> None:
        self.names = names

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_global_decl(self)


class NonlocalDecl(Statement):
    """Declaration nonlocal x, y, ..."""

    names = None  # type: List[str]

    def __init__(self, names: List[str]) -> None:
        self.names = names

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_nonlocal_decl(self)


class Block(Statement):
    body = None  # type: List[Statement]
    # True if we can determine that this block is not executed. For example,
    # this applies to blocks that are protected by something like "if PY3:"
    # when using Python 2.
    is_unreachable = False

    def __init__(self, body: List[Statement]) -> None:
        self.body = body

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_block(self)


# Statements


class ExpressionStmt(Statement):
    """An expression as a statement, such as print(s)."""
    expr = None  # type: Expression

    def __init__(self, expr: Expression) -> None:
        self.expr = expr

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_expression_stmt(self)


class AssignmentStmt(Statement):
    """Assignment statement
    The same node class is used for single assignment, multiple assignment
    (e.g. x, y = z) and chained assignment (e.g. x = y = z), assignments
    that define new names, and assignments with explicit types (# type).

    An lvalue can be NameExpr, TupleExpr, ListExpr, MemberExpr, IndexExpr.
    """

    lvalues = None  # type: List[Expression]
    rvalue = None  # type: Expression
    # Declared type in a comment, may be None.
    type = None  # type: mypy.types.Type

    def __init__(self, lvalues: List[Expression], rvalue: Expression,
                 type: 'mypy.types.Type' = None) -> None:
        self.lvalues = lvalues
        self.rvalue = rvalue
        self.type = type

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_assignment_stmt(self)


class OperatorAssignmentStmt(Statement):
    """Operator assignment statement such as x += 1"""

    op = ''
    lvalue = None  # type: Expression
    rvalue = None  # type: Expression

    def __init__(self, op: str, lvalue: Expression, rvalue: Expression) -> None:
        self.op = op
        self.lvalue = lvalue
        self.rvalue = rvalue

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_operator_assignment_stmt(self)


class WhileStmt(Statement):
    expr = None  # type: Expression
    body = None  # type: Block
    else_body = None  # type: Block

    def __init__(self, expr: Expression, body: Block, else_body: Block) -> None:
        self.expr = expr
        self.body = body
        self.else_body = else_body

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_while_stmt(self)


class ForStmt(Statement):
    # Index variables
    index = None  # type: Expression
    # Expression to iterate
    expr = None  # type: Expression
    body = None  # type: Block
    else_body = None  # type: Block
    is_async = False  # True if `async for ...` (PEP 492, Python 3.5)

    def __init__(self, index: Expression, expr: Expression, body: Block,
                 else_body: Block) -> None:
        self.index = index
        self.expr = expr
        self.body = body
        self.else_body = else_body

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_for_stmt(self)


class ReturnStmt(Statement):
    expr = None  # type: Optional[Expression]

    def __init__(self, expr: Optional[Expression]) -> None:
        self.expr = expr

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_return_stmt(self)


class AssertStmt(Statement):
    expr = None  # type: Expression

    def __init__(self, expr: Expression) -> None:
        self.expr = expr

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_assert_stmt(self)


class DelStmt(Statement):
    expr = None  # type: Expression

    def __init__(self, expr: Expression) -> None:
        self.expr = expr

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_del_stmt(self)


class BreakStmt(Statement):
    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_break_stmt(self)


class ContinueStmt(Statement):
    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_continue_stmt(self)


class PassStmt(Statement):
    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_pass_stmt(self)


class IfStmt(Statement):
    expr = None  # type: List[Expression]
    body = None  # type: List[Block]
    else_body = None  # type: Block

    def __init__(self, expr: List[Expression], body: List[Block],
                 else_body: Block) -> None:
        self.expr = expr
        self.body = body
        self.else_body = else_body

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_if_stmt(self)


class RaiseStmt(Statement):
    expr = None  # type: Expression
    from_expr = None  # type: Expression

    def __init__(self, expr: Expression, from_expr: Expression = None) -> None:
        self.expr = expr
        self.from_expr = from_expr

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_raise_stmt(self)


class TryStmt(Statement):
    body = None  # type: Block                # Try body
    types = None  # type: List[Expression]    # Except type expressions
    vars = None  # type: List[NameExpr]     # Except variable names
    handlers = None  # type: List[Block]      # Except bodies
    else_body = None  # type: Block
    finally_body = None  # type: Block

    def __init__(self, body: Block, vars: List['NameExpr'], types: List[Expression],
                 handlers: List[Block], else_body: Block,
                 finally_body: Block) -> None:
        self.body = body
        self.vars = vars
        self.types = types
        self.handlers = handlers
        self.else_body = else_body
        self.finally_body = finally_body

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_try_stmt(self)


class WithStmt(Statement):
    expr = None  # type: List[Expression]
    target = None  # type: List[Expression]
    body = None  # type: Block
    is_async = False  # True if `async with ...` (PEP 492, Python 3.5)

    def __init__(self, expr: List[Expression], target: List[Expression],
                 body: Block) -> None:
        self.expr = expr
        self.target = target
        self.body = body

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_with_stmt(self)


class PrintStmt(Statement):
    """Python 2 print statement"""

    args = None  # type: List[Expression]
    newline = False
    # The file-like target object (given using >>).
    target = None  # type: Optional[Expression]

    def __init__(self, args: List[Expression], newline: bool, target: Expression = None) -> None:
        self.args = args
        self.newline = newline
        self.target = target

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_print_stmt(self)


class ExecStmt(Statement):
    """Python 2 exec statement"""

    expr = None  # type: Expression
    variables1 = None  # type: Optional[Expression]
    variables2 = None  # type: Optional[Expression]

    def __init__(self, expr: Expression,
                 variables1: Optional[Expression],
                 variables2: Optional[Expression]) -> None:
        self.expr = expr
        self.variables1 = variables1
        self.variables2 = variables2

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_exec_stmt(self)


# Expressions


class IntExpr(Expression):
    """Integer literal"""

    value = 0
    literal = LITERAL_YES

    def __init__(self, value: int) -> None:
        self.value = value
        self.literal_hash = value

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_int_expr(self)


# How mypy uses StrExpr, BytesExpr, and UnicodeExpr:
# In Python 2 mode:
# b'x', 'x' -> StrExpr
# u'x' -> UnicodeExpr
# BytesExpr is unused
#
# In Python 3 mode:
# b'x' -> BytesExpr
# 'x', u'x' -> StrExpr
# UnicodeExpr is unused

class StrExpr(Expression):
    """String literal"""

    value = ''
    literal = LITERAL_YES

    def __init__(self, value: str) -> None:
        self.value = value
        self.literal_hash = value

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_str_expr(self)


class BytesExpr(Expression):
    """Bytes literal"""

    value = ''  # TODO use bytes
    literal = LITERAL_YES

    def __init__(self, value: str) -> None:
        self.value = value
        self.literal_hash = value

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_bytes_expr(self)


class UnicodeExpr(Expression):
    """Unicode literal (Python 2.x)"""

    value = ''  # TODO use bytes
    literal = LITERAL_YES

    def __init__(self, value: str) -> None:
        self.value = value
        self.literal_hash = value

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_unicode_expr(self)


class FloatExpr(Expression):
    """Float literal"""

    value = 0.0
    literal = LITERAL_YES

    def __init__(self, value: float) -> None:
        self.value = value
        self.literal_hash = value

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_float_expr(self)


class ComplexExpr(Expression):
    """Complex literal"""

    value = 0.0j
    literal = LITERAL_YES

    def __init__(self, value: complex) -> None:
        self.value = value
        self.literal_hash = value

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_complex_expr(self)


class EllipsisExpr(Expression):
    """Ellipsis (...)"""

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_ellipsis(self)


class StarExpr(Expression):
    """Star expression"""

    expr = None  # type: Expression

    def __init__(self, expr: Expression) -> None:
        self.expr = expr
        self.literal = self.expr.literal
        self.literal_hash = ('Star', expr.literal_hash,)

        # Whether this starred expression is used in a tuple/list and as lvalue
        self.valid = False

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_star_expr(self)


class RefExpr(Expression):
    """Abstract base class for name-like constructs"""

    kind = None  # type: int      # LDEF/GDEF/MDEF/... (None if not available)
    node = None  # type: SymbolNode  # Var, FuncDef or TypeInfo that describes this
    fullname = None  # type: str  # Fully qualified name (or name if not global)

    # Does this define a new name with inferred type?
    #
    # For members, after semantic analysis, this does not take base
    # classes into consideration at all; the type checker deals with these.
    is_def = False


class NameExpr(RefExpr):
    """Name expression

    This refers to a local name, global name or a module.
    """

    name = None  # type: str      # Name referred to (may be qualified)

    literal = LITERAL_TYPE

    def __init__(self, name: str) -> None:
        self.name = name
        self.literal_hash = ('Var', name,)

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_name_expr(self)

    def serialize(self) -> JsonDict:
        # TODO: Find out where and why NameExpr is being serialized (if at all).
        assert False, "Serializing NameExpr: %s" % (self,)
        return {'.class': 'NameExpr',
                'kind': self.kind,
                'node': None if self.node is None else self.node.serialize(),
                'fullname': self.fullname,
                'is_def': self.is_def,
                'name': self.name,
                'literal': self.literal,
                }

    @classmethod
    def deserialize(cls, data: JsonDict) -> 'NameExpr':
        assert data['.class'] == 'NameExpr'
        ret = NameExpr(data['name'])
        ret.kind = data['kind']
        ret.node = None if data['node'] is None else SymbolNode.deserialize(data['node'])
        ret.fullname = data['fullname']
        ret.is_def = data['is_def']
        ret.literal = data['literal']
        return ret


class MemberExpr(RefExpr):
    """Member access expression x.y"""

    expr = None  # type: Expression
    name = None  # type: str
    # The variable node related to a definition.
    def_var = None  # type: Var

    def __init__(self, expr: Expression, name: str) -> None:
        self.expr = expr
        self.name = name
        self.literal = self.expr.literal
        self.literal_hash = ('Member', expr.literal_hash, name)

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_member_expr(self)


# Kinds of arguments

# Positional argument
ARG_POS = 0  # type: int
# Positional, optional argument (functions only, not calls)
ARG_OPT = 1  # type: int
# *arg argument
ARG_STAR = 2  # type: int
# Keyword argument x=y in call, or keyword-only function arg
ARG_NAMED = 3  # type: int
# **arg argument
ARG_STAR2 = 4  # type: int


class CallExpr(Expression):
    """Call expression.

    This can also represent several special forms that are syntactically calls
    such as cast(...) and None  # type: ....
    """

    callee = None  # type: Expression
    args = None  # type: List[Expression]
    arg_kinds = None  # type: List[int]  # ARG_ constants
    # Each name can be None if not a keyword argument.
    arg_names = None  # type: List[str]
    # If not None, the node that represents the meaning of the CallExpr. For
    # cast(...) this is a CastExpr.
    analyzed = None  # type: Optional[Expression]

    def __init__(self, callee: Expression, args: List[Expression], arg_kinds: List[int],
                 arg_names: List[str] = None, analyzed: Expression = None) -> None:
        if not arg_names:
            arg_names = [None] * len(args)

        self.callee = callee
        self.args = args
        self.arg_kinds = arg_kinds
        self.arg_names = arg_names
        self.analyzed = analyzed

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_call_expr(self)


class YieldFromExpr(Expression):
    expr = None  # type: Expression

    def __init__(self, expr: Expression) -> None:
        self.expr = expr

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_yield_from_expr(self)


class YieldExpr(Expression):
    expr = None  # type: Optional[Expression]

    def __init__(self, expr: Optional[Expression]) -> None:
        self.expr = expr

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_yield_expr(self)


class IndexExpr(Expression):
    """Index expression x[y].

    Also wraps type application such as List[int] as a special form.
    """

    base = None  # type: Expression
    index = None  # type: Expression
    # Inferred __getitem__ method type
    method_type = None  # type: mypy.types.Type
    # If not None, this is actually semantically a type application
    # Class[type, ...] or a type alias initializer.
    analyzed = None  # type: Union[TypeApplication, TypeAliasExpr]

    def __init__(self, base: Expression, index: Expression) -> None:
        self.base = base
        self.index = index
        self.analyzed = None
        if self.index.literal == LITERAL_YES:
            self.literal = self.base.literal
            self.literal_hash = ('Member', base.literal_hash,
                                 index.literal_hash)

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_index_expr(self)


class UnaryExpr(Expression):
    """Unary operation"""

    op = ''
    expr = None  # type: Expression
    # Inferred operator method type
    method_type = None  # type: mypy.types.Type

    def __init__(self, op: str, expr: Expression) -> None:
        self.op = op
        self.expr = expr
        self.literal = self.expr.literal
        self.literal_hash = ('Unary', op, expr.literal_hash)

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_unary_expr(self)


# Map from binary operator id to related method name (in Python 3).
op_methods = {
    '+': '__add__',
    '-': '__sub__',
    '*': '__mul__',
    '/': '__truediv__',
    '%': '__mod__',
    '//': '__floordiv__',
    '**': '__pow__',
    '&': '__and__',
    '|': '__or__',
    '^': '__xor__',
    '<<': '__lshift__',
    '>>': '__rshift__',
    '==': '__eq__',
    '!=': '__ne__',
    '<': '__lt__',
    '>=': '__ge__',
    '>': '__gt__',
    '<=': '__le__',
    'in': '__contains__',
}  # type: Dict[str, str]

comparison_fallback_method = '__cmp__'
ops_falling_back_to_cmp = {'__ne__', '__eq__',
                           '__lt__', '__le__',
                           '__gt__', '__ge__'}


ops_with_inplace_method = {
    '+', '-', '*', '/', '%', '//', '**', '&', '|', '^', '<<', '>>'}

inplace_operator_methods = set(
    '__i' + op_methods[op][2:] for op in ops_with_inplace_method)

reverse_op_methods = {
    '__add__': '__radd__',
    '__sub__': '__rsub__',
    '__mul__': '__rmul__',
    '__truediv__': '__rtruediv__',
    '__mod__': '__rmod__',
    '__floordiv__': '__rfloordiv__',
    '__pow__': '__rpow__',
    '__and__': '__rand__',
    '__or__': '__ror__',
    '__xor__': '__rxor__',
    '__lshift__': '__rlshift__',
    '__rshift__': '__rrshift__',
    '__eq__': '__eq__',
    '__ne__': '__ne__',
    '__lt__': '__gt__',
    '__ge__': '__le__',
    '__gt__': '__lt__',
    '__le__': '__ge__',
}

normal_from_reverse_op = dict((m, n) for n, m in reverse_op_methods.items())
reverse_op_method_set = set(reverse_op_methods.values())


class OpExpr(Expression):
    """Binary operation (other than . or [] or comparison operators,
    which have specific nodes)."""

    op = ''
    left = None  # type: Expression
    right = None  # type: Expression
    # Inferred type for the operator method type (when relevant).
    method_type = None  # type: mypy.types.Type

    def __init__(self, op: str, left: Expression, right: Expression) -> None:
        self.op = op
        self.left = left
        self.right = right
        self.literal = min(self.left.literal, self.right.literal)
        self.literal_hash = ('Binary', op, left.literal_hash, right.literal_hash)

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_op_expr(self)


class ComparisonExpr(Expression):
    """Comparison expression (e.g. a < b > c < d)."""

    operators = None  # type: List[str]
    operands = None  # type: List[Expression]
    # Inferred type for the operator methods (when relevant; None for 'is').
    method_types = None  # type: List[mypy.types.Type]

    def __init__(self, operators: List[str], operands: List[Expression]) -> None:
        self.operators = operators
        self.operands = operands
        self.method_types = []
        self.literal = min(o.literal for o in self.operands)
        self.literal_hash = (('Comparison',) + tuple(operators) +
                             tuple(o.literal_hash for o in operands))

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_comparison_expr(self)


class SliceExpr(Expression):
    """Slice expression (e.g. 'x:y', 'x:', '::2' or ':').

    This is only valid as index in index expressions.
    """

    begin_index = None  # type: Optional[Expression]
    end_index = None  # type: Optional[Expression]
    stride = None  # type: Optional[Expression]

    def __init__(self, begin_index: Optional[Expression],
                 end_index: Optional[Expression],
                 stride: Optional[Expression]) -> None:
        self.begin_index = begin_index
        self.end_index = end_index
        self.stride = stride

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_slice_expr(self)


class CastExpr(Expression):
    """Cast expression cast(type, expr)."""

    expr = None  # type: Expression
    type = None  # type: mypy.types.Type

    def __init__(self, expr: Expression, typ: 'mypy.types.Type') -> None:
        self.expr = expr
        self.type = typ

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_cast_expr(self)


class RevealTypeExpr(Expression):
    """Reveal type expression reveal_type(expr)."""

    expr = None  # type: Expression

    def __init__(self, expr: Expression) -> None:
        self.expr = expr

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_reveal_type_expr(self)


class SuperExpr(Expression):
    """Expression super().name"""

    name = ''
    info = None  # type: TypeInfo  # Type that contains this super expression

    def __init__(self, name: str) -> None:
        self.name = name

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_super_expr(self)


class FuncExpr(FuncItem, Expression):
    """Lambda expression"""

    def name(self) -> str:
        return '<lambda>'

    def expr(self) -> Expression:
        """Return the expression (the body) of the lambda."""
        ret = cast(ReturnStmt, self.body.body[-1])
        return ret.expr

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_func_expr(self)


class ListExpr(Expression):
    """List literal expression [...]."""

    items = None  # type: List[Expression]

    def __init__(self, items: List[Expression]) -> None:
        self.items = items
        if all(x.literal == LITERAL_YES for x in items):
            self.literal = LITERAL_YES
            self.literal_hash = ('List',) + tuple(x.literal_hash for x in items)

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_list_expr(self)


class DictExpr(Expression):
    """Dictionary literal expression {key: value, ...}."""

    items = None  # type: List[Tuple[Expression, Expression]]

    def __init__(self, items: List[Tuple[Expression, Expression]]) -> None:
        self.items = items
        # key is None for **item, e.g. {'a': 1, **x} has
        # keys ['a', None] and values [1, x].
        if all(x[0] and x[0].literal == LITERAL_YES and x[1].literal == LITERAL_YES
               for x in items):
            self.literal = LITERAL_YES
            self.literal_hash = ('Dict',) + tuple(
                (x[0].literal_hash, x[1].literal_hash) for x in items)  # type: ignore

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_dict_expr(self)


class TupleExpr(Expression):
    """Tuple literal expression (..., ...)"""

    items = None  # type: List[Expression]

    def __init__(self, items: List[Expression]) -> None:
        self.items = items
        if all(x.literal == LITERAL_YES for x in items):
            self.literal = LITERAL_YES
            self.literal_hash = ('Tuple',) + tuple(x.literal_hash for x in items)

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_tuple_expr(self)


class SetExpr(Expression):
    """Set literal expression {value, ...}."""

    items = None  # type: List[Expression]

    def __init__(self, items: List[Expression]) -> None:
        self.items = items
        if all(x.literal == LITERAL_YES for x in items):
            self.literal = LITERAL_YES
            self.literal_hash = ('Set',) + tuple(x.literal_hash for x in items)

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_set_expr(self)


class GeneratorExpr(Expression):
    """Generator expression ... for ... in ... [ for ...  in ... ] [ if ... ]."""

    left_expr = None  # type: Expression
    sequences = None  # type: List[Expression]
    condlists = None  # type: List[List[Expression]]
    indices = None  # type: List[Expression]

    def __init__(self, left_expr: Expression, indices: List[Expression],
                 sequences: List[Expression], condlists: List[List[Expression]]) -> None:
        self.left_expr = left_expr
        self.sequences = sequences
        self.condlists = condlists
        self.indices = indices

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_generator_expr(self)


class ListComprehension(Expression):
    """List comprehension (e.g. [x + 1 for x in a])"""

    generator = None  # type: GeneratorExpr

    def __init__(self, generator: GeneratorExpr) -> None:
        self.generator = generator

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_list_comprehension(self)


class SetComprehension(Expression):
    """Set comprehension (e.g. {x + 1 for x in a})"""

    generator = None  # type: GeneratorExpr

    def __init__(self, generator: GeneratorExpr) -> None:
        self.generator = generator

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_set_comprehension(self)


class DictionaryComprehension(Expression):
    """Dictionary comprehension (e.g. {k: v for k, v in a}"""

    key = None  # type: Expression
    value = None  # type: Expression
    sequences = None  # type: List[Expression]
    condlists = None  # type: List[List[Expression]]
    indices = None  # type: List[Expression]

    def __init__(self, key: Expression, value: Expression, indices: List[Expression],
                 sequences: List[Expression], condlists: List[List[Expression]]) -> None:
        self.key = key
        self.value = value
        self.sequences = sequences
        self.condlists = condlists
        self.indices = indices

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_dictionary_comprehension(self)


class ConditionalExpr(Expression):
    """Conditional expression (e.g. x if y else z)"""

    cond = None  # type: Expression
    if_expr = None  # type: Expression
    else_expr = None  # type: Expression

    def __init__(self, cond: Expression, if_expr: Expression, else_expr: Expression) -> None:
        self.cond = cond
        self.if_expr = if_expr
        self.else_expr = else_expr

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_conditional_expr(self)


class BackquoteExpr(Expression):
    """Python 2 expression `...`."""

    expr = None  # type: Expression

    def __init__(self, expr: Expression) -> None:
        self.expr = expr

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_backquote_expr(self)


class TypeApplication(Expression):
    """Type application expr[type, ...]"""

    expr = None  # type: Expression
    types = None  # type: List[mypy.types.Type]

    def __init__(self, expr: Expression, types: List['mypy.types.Type']) -> None:
        self.expr = expr
        self.types = types

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_type_application(self)


# Variance of a type variable. For example, T in the definition of
# List[T] is invariant, so List[int] is not a subtype of List[object],
# and also List[object] is not a subtype of List[int].
#
# The T in Iterable[T] is covariant, so Iterable[int] is a subtype of
# Iterable[object], but not vice versa.
#
# If T is contravariant in Foo[T], Foo[object] is a subtype of
# Foo[int], but not vice versa.
INVARIANT = 0  # type: int
COVARIANT = 1  # type: int
CONTRAVARIANT = 2  # type: int


class TypeVarExpr(SymbolNode, Expression):
    """Type variable expression TypeVar(...)."""

    _name = ''
    _fullname = ''
    # Value restriction: only types in the list are valid as values. If the
    # list is empty, there is no restriction.
    values = None  # type: List[mypy.types.Type]
    # Upper bound: only subtypes of upper_bound are valid as values. By default
    # this is 'object', meaning no restriction.
    upper_bound = None  # type: mypy.types.Type
    # Variance of the type variable. Invariant is the default.
    # TypeVar(..., covariant=True) defines a covariant type variable.
    # TypeVar(..., contravariant=True) defines a contravariant type
    # variable.
    variance = INVARIANT

    def __init__(self, name: str, fullname: str,
                 values: List['mypy.types.Type'],
                 upper_bound: 'mypy.types.Type',
                 variance: int=INVARIANT) -> None:
        self._name = name
        self._fullname = fullname
        self.values = values
        self.upper_bound = upper_bound
        self.variance = variance

    def name(self) -> str:
        return self._name

    def fullname(self) -> str:
        return self._fullname

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_type_var_expr(self)

    def serialize(self) -> JsonDict:
        return {'.class': 'TypeVarExpr',
                'name': self._name,
                'fullname': self._fullname,
                'values': [t.serialize() for t in self.values],
                'upper_bound': self.upper_bound.serialize(),
                'variance': self.variance,
                }

    @classmethod
    def deserialize(cls, data: JsonDict) -> 'TypeVarExpr':
        assert data['.class'] == 'TypeVarExpr'
        return TypeVarExpr(data['name'],
                           data['fullname'],
                           [mypy.types.Type.deserialize(v) for v in data['values']],
                           mypy.types.Type.deserialize(data['upper_bound']),
                           data['variance'])


class TypeAliasExpr(Expression):
    """Type alias expression (rvalue)."""

    type = None  # type: mypy.types.Type

    def __init__(self, type: 'mypy.types.Type') -> None:
        self.type = type

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_type_alias_expr(self)


class NamedTupleExpr(Expression):
    """Named tuple expression namedtuple(...)."""

    # The class representation of this named tuple (its tuple_type attribute contains
    # the tuple item types)
    info = None  # type: TypeInfo

    def __init__(self, info: 'TypeInfo') -> None:
        self.info = info

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_namedtuple_expr(self)


class PromoteExpr(Expression):
    """Ducktype class decorator expression _promote(...)."""

    type = None  # type: mypy.types.Type

    def __init__(self, type: 'mypy.types.Type') -> None:
        self.type = type

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit__promote_expr(self)


class NewTypeExpr(Expression):
    """NewType expression NewType(...)."""

    info = None  # type: Optional[TypeInfo]

    def __init__(self, info: Optional['TypeInfo']) -> None:
        self.info = info

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_newtype_expr(self)


class AwaitExpr(Node):
    """Await expression (await ...)."""

    expr = None  # type: Node

    def __init__(self, expr: Node) -> None:
        self.expr = expr

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_await_expr(self)


# Constants


class TempNode(Expression):
    """Temporary dummy node used during type checking.

    This node is not present in the original program; it is just an artifact
    of the type checker implementation. It only represents an opaque node with
    some fixed type.
    """

    type = None  # type: mypy.types.Type

    def __init__(self, typ: 'mypy.types.Type') -> None:
        self.type = typ

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_temp_node(self)


class TypeInfo(SymbolNode):
    """The type structure of a single class.

    Each TypeInfo corresponds one-to-one to a ClassDef, which
    represents the AST of the class.

    In type-theory terms, this is a "type constructor", and if the
    class is generic then it will be a type constructor of higher kind.
    Where the class is used in an actual type, it's in the form of an
    Instance, which amounts to a type application of the tycon to
    the appropriate number of arguments.
    """

    _fullname = None  # type: str          # Fully qualified name
    # Fully qualified name for the module this type was defined in. This
    # information is also in the fullname, but is harder to extract in the
    # case of nested class definitions.
    module_name = None  # type: str
    defn = None  # type: ClassDef          # Corresponding ClassDef
    # Method Resolution Order: the order of looking up attributes. The first
    # value always to refers to this class.
    mro = None  # type: List[TypeInfo]
    subtypes = None  # type: Set[TypeInfo] # Direct subclasses encountered so far
    names = None  # type: SymbolTable      # Names defined directly in this type
    is_abstract = False                    # Does the class have any abstract attributes?
    abstract_attributes = None  # type: List[str]
    # Classes inheriting from Enum shadow their true members with a __getattr__, so we
    # have to treat them as a special case.
    is_enum = False
    # If true, any unknown attributes should have type 'Any' instead
    # of generating a type error.  This would be true if there is a
    # base class with type 'Any', but other use cases may be
    # possible. This is similar to having __getattr__ that returns Any
    # (and __setattr__), but without the __getattr__ method.
    fallback_to_any = False

    # Information related to type annotations.

    # Generic type variable names
    type_vars = None  # type: List[str]

    # Direct base classes.
    bases = None  # type: List[mypy.types.Instance]

    # Another type which this type will be treated as a subtype of,
    # even though it's not a subclass in Python.  The non-standard
    # `@_promote` decorator introduces this, and there are also
    # several builtin examples, in particular `int` -> `float`.
    _promote = None  # type: mypy.types.Type

    # Representation of a Tuple[...] base class, if the class has any
    # (e.g., for named tuples). If this is not None, the actual Type
    # object used for this class is not an Instance but a TupleType;
    # the corresponding Instance is set as the fallback type of the
    # tuple type.
    tuple_type = None  # type: mypy.types.TupleType

    # Is this a named tuple type?
    is_named_tuple = False

    # Is this a newtype type?
    is_newtype = False

    # Is this a dummy from deserialization?
    is_dummy = False

    # Alternative to fullname() for 'anonymous' classes.
    alt_fullname = None  # type: Optional[str]

    FLAGS = [
        'is_abstract', 'is_enum', 'fallback_to_any', 'is_named_tuple',
        'is_newtype', 'is_dummy'
    ]

    def __init__(self, names: 'SymbolTable', defn: ClassDef, module_name: str) -> None:
        """Initialize a TypeInfo."""
        self.names = names
        self.defn = defn
        self.module_name = module_name
        self.subtypes = set()
        self.type_vars = []
        self.bases = []
        # Leave self.mro uninitialized until we compute it for real,
        # so we don't accidentally try to use it prematurely.
        self._fullname = defn.fullname
        self.is_abstract = False
        self.abstract_attributes = []
        if defn.type_vars:
            for vd in defn.type_vars:
                self.type_vars.append(vd.name)

    def name(self) -> str:
        """Short name."""
        return self.defn.name

    def fullname(self) -> str:
        return self._fullname

    def is_generic(self) -> bool:
        """Is the type generic (i.e. does it have type variables)?"""
        return len(self.type_vars) > 0

    def get(self, name: str) -> 'SymbolTableNode':
        for cls in self.mro:
            n = cls.names.get(name)
            if n:
                return n
        return None

    def __getitem__(self, name: str) -> 'SymbolTableNode':
        n = self.get(name)
        if n:
            return n
        else:
            raise KeyError(name)

    def __repr__(self) -> str:
        return '<TypeInfo %s>' % self.fullname()

    # IDEA: Refactor the has* methods to be more consistent and document
    #       them.

    def has_readable_member(self, name: str) -> bool:
        return self.get(name) is not None

    def has_writable_member(self, name: str) -> bool:
        return self.has_var(name)

    def has_var(self, name: str) -> bool:
        return self.get_var(name) is not None

    def has_method(self, name: str) -> bool:
        return self.get_method(name) is not None

    def get_var(self, name: str) -> Var:
        for cls in self.mro:
            if name in cls.names:
                node = cls.names[name].node
                if isinstance(node, Var):
                    return node
                else:
                    return None
        return None

    def get_var_or_getter(self, name: str) -> SymbolNode:
        # TODO getter
        return self.get_var(name)

    def get_var_or_setter(self, name: str) -> SymbolNode:
        # TODO setter
        return self.get_var(name)

    def get_method(self, name: str) -> FuncBase:
        if self.mro is None:  # Might be because of a previous error.
            return None
        for cls in self.mro:
            if name in cls.names:
                node = cls.names[name].node
                if isinstance(node, FuncBase):
                    return node
                else:
                    return None
        return None

    def calculate_mro(self) -> None:
        """Calculate and set mro (method resolution order).

        Raise MroError if cannot determine mro.
        """
        mro = linearize_hierarchy(self)
        assert mro, "Could not produce a MRO at all for %s" % (self,)
        self.mro = mro
        self.is_enum = self._calculate_is_enum()

    def _calculate_is_enum(self) -> bool:
        """
        If this is "enum.Enum" itself, then yes, it's an enum.
        If the flag .is_enum has been set on anything in the MRO, it's an enum.
        """
        if self.fullname() == ENUM_BASECLASS:
            return True
        if self.mro:
            return any(type_info.is_enum for type_info in self.mro)
        return False

    def has_base(self, fullname: str) -> bool:
        """Return True if type has a base type with the specified name.

        This can be either via extension or via implementation.
        """
        if self.mro:
            for cls in self.mro:
                if cls.fullname() == fullname:
                    return True
        return False

    def all_subtypes(self) -> 'Set[TypeInfo]':
        """Return TypeInfos of all subtypes, including this type, as a set."""
        subtypes = set([self])
        for subt in self.subtypes:
            for t in subt.all_subtypes():
                subtypes.add(t)
        return subtypes

    def all_base_classes(self) -> 'List[TypeInfo]':
        """Return a list of base classes, including indirect bases."""
        assert False

    def direct_base_classes(self) -> 'List[TypeInfo]':
        """Return a direct base classes.

        Omit base classes of other base classes.
        """
        return [base.type for base in self.bases]

    def __str__(self) -> str:
        """Return a string representation of the type.

        This includes the most important information about the type.
        """
        base = None  # type: str
        if self.bases:
            base = 'Bases({})'.format(', '.join(str(base)
                                                for base in self.bases))
        return dump_tagged(['Name({})'.format(self.fullname()),
                            base,
                            ('Names', sorted(self.names.keys()))],
                           'TypeInfo')

    def serialize(self) -> Union[str, JsonDict]:
        # NOTE: This is where all ClassDefs originate, so there shouldn't be duplicates.
        data = {'.class': 'TypeInfo',
                'module_name': self.module_name,
                'fullname': self.fullname(),
                'alt_fullname': self.alt_fullname,
                'names': self.names.serialize(self.alt_fullname or self.fullname()),
                'defn': self.defn.serialize(),
                'abstract_attributes': self.abstract_attributes,
                'type_vars': self.type_vars,
                'bases': [b.serialize() for b in self.bases],
                '_promote': None if self._promote is None else self._promote.serialize(),
                'tuple_type': None if self.tuple_type is None else self.tuple_type.serialize(),
                'flags': get_flags(self, TypeInfo.FLAGS),
                }
        return data

    @classmethod
    def deserialize(cls, data: JsonDict) -> 'TypeInfo':
        names = SymbolTable.deserialize(data['names'])
        defn = ClassDef.deserialize(data['defn'])
        module_name = data['module_name']
        ti = TypeInfo(names, defn, module_name)
        ti._fullname = data['fullname']
        ti.alt_fullname = data['alt_fullname']
        # TODO: Is there a reason to reconstruct ti.subtypes?
        ti.abstract_attributes = data['abstract_attributes']
        ti.type_vars = data['type_vars']
        ti.bases = [mypy.types.Instance.deserialize(b) for b in data['bases']]
        ti._promote = (None if data['_promote'] is None
                       else mypy.types.Type.deserialize(data['_promote']))
        ti.tuple_type = (None if data['tuple_type'] is None
                         else mypy.types.TupleType.deserialize(data['tuple_type']))
        set_flags(ti, data['flags'])
        return ti


class SymbolTableNode:
    # Kind of node. Possible values:
    #  - LDEF: local definition (of any kind)
    #  - GDEF: global (module-level) definition
    #  - MDEF: class member definition
    #  - UNBOUND_TVAR: TypeVar(...) definition, not bound
    #  - TVAR: type variable in a bound scope (generic function / generic clas)
    #  - MODULE_REF: reference to a module
    #  - TYPE_ALIAS: type alias
    #  - UNBOUND_IMPORTED: temporary kind for imported names
    kind = None  # type: int
    # AST node of definition (FuncDef/Var/TypeInfo/Decorator/TypeVarExpr,
    # or None for a bound type variable).
    node = None  # type: Optional[SymbolNode]
    # Type variable definition (for bound type variables only)
    tvar_def = None  # type: Optional[mypy.types.TypeVarDef]
    # Module id (e.g. "foo.bar") or None
    mod_id = ''
    # If this not None, override the type of the 'node' attribute.
    type_override = None  # type: Optional[mypy.types.Type]
    # If False, this name won't be imported via 'from <module> import *'.
    # This has no effect on names within classes.
    module_public = True
    # For deserialized MODULE_REF nodes, the referenced module name;
    # for other nodes, optionally the name of the referenced object.
    cross_ref = None  # type: Optional[str]

    def __init__(self, kind: int, node: Optional[SymbolNode], mod_id: str = None,
                 typ: 'mypy.types.Type' = None,
                 tvar_def: 'mypy.types.TypeVarDef' = None,
                 module_public: bool = True) -> None:
        self.kind = kind
        self.node = node
        self.type_override = typ
        self.mod_id = mod_id
        self.tvar_def = tvar_def
        self.module_public = module_public

    @property
    def fullname(self) -> str:
        if self.node is not None:
            return self.node.fullname()
        else:
            return None

    @property
    def type(self) -> 'mypy.types.Type':
        # IDEA: Get rid of the Any type.
        node = self.node  # type: Any
        if self.type_override is not None:
            return self.type_override
        elif ((isinstance(node, Var) or isinstance(node, FuncDef))
              and node.type is not None):
            return node.type
        elif isinstance(node, Decorator):
            return node.var.type
        else:
            return None

    def __str__(self) -> str:
        s = '{}/{}'.format(node_kinds[self.kind], short_type(self.node))
        if self.mod_id is not None:
            s += ' ({})'.format(self.mod_id)
        # Include declared type of variables and functions.
        if self.type is not None:
            s += ' : {}'.format(self.type)
        return s

    def serialize(self, prefix: str, name: str) -> JsonDict:
        """Serialize a SymbolTableNode.

        Args:
          prefix: full name of the containing module or class; or None
          name: name of this object relative to the containing object
        """
        data = {'.class': 'SymbolTableNode',
                'kind': node_kinds[self.kind],
                }  # type: JsonDict
        if self.tvar_def:
            data['tvar_def'] = self.tvar_def.serialize()
        if not self.module_public:
            data['module_public'] = False
        if self.kind == MODULE_REF:
            assert self.node is not None, "Missing module cross ref in %s for %s" % (prefix, name)
            data['cross_ref'] = self.node.fullname()
        else:
            if self.node is not None:
                if prefix is not None:
                    # Check whether this is an alias for another object.
                    # If the object's canonical full name differs from
                    # the full name computed from prefix and name,
                    # it's an alias, and we serialize it as a cross ref.
                    if isinstance(self.node, TypeInfo):
                        fullname = self.node.alt_fullname or self.node.fullname()
                    else:
                        fullname = self.node.fullname()
                    if (fullname is not None and '.' in fullname and
                            fullname != prefix + '.' + name):
                        data['cross_ref'] = fullname
                        return data
                data['node'] = self.node.serialize()
            if self.type_override is not None:
                data['type_override'] = self.type_override.serialize()
        return data

    @classmethod
    def deserialize(cls, data: JsonDict) -> 'SymbolTableNode':
        assert data['.class'] == 'SymbolTableNode'
        kind = inverse_node_kinds[data['kind']]
        if 'cross_ref' in data:
            # This will be fixed up later.
            stnode = SymbolTableNode(kind, None)
            stnode.cross_ref = data['cross_ref']
        else:
            node = None
            if 'node' in data:
                node = SymbolNode.deserialize(data['node'])
            typ = None
            if 'type_override' in data:
                typ = mypy.types.Type.deserialize(data['type_override'])
            stnode = SymbolTableNode(kind, node, typ=typ)
        if 'tvar_def' in data:
            stnode.tvar_def = mypy.types.TypeVarDef.deserialize(data['tvar_def'])
        if 'module_public' in data:
            stnode.module_public = data['module_public']
        return stnode


class SymbolTable(Dict[str, SymbolTableNode]):
    def __str__(self) -> str:
        a = []  # type: List[str]
        for key, value in self.items():
            # Filter out the implicit import of builtins.
            if isinstance(value, SymbolTableNode):
                if (value.fullname != 'builtins' and
                        (value.fullname or '').split('.')[-1] not in
                        implicit_module_attrs):
                    a.append('  ' + str(key) + ' : ' + str(value))
            else:
                a.append('  <invalid item>')
        a = sorted(a)
        a.insert(0, 'SymbolTable(')
        a[-1] += ')'
        return '\n'.join(a)

    def serialize(self, fullname: str) -> JsonDict:
        data = {'.class': 'SymbolTable'}  # type: JsonDict
        for key, value in self.items():
            # Skip __builtins__: it's a reference to the builtins
            # module that gets added to every module by
            # SemanticAnalyzer.visit_file(), but it shouldn't be
            # accessed by users of the module.
            if key == '__builtins__':
                continue
            data[key] = value.serialize(fullname, key)
        return data

    @classmethod
    def deserialize(cls, data: JsonDict) -> 'SymbolTable':
        assert data['.class'] == 'SymbolTable'
        st = SymbolTable()
        for key, value in data.items():
            if key != '.class':
                st[key] = SymbolTableNode.deserialize(value)
        return st


def function_type(func: FuncBase, fallback: 'mypy.types.Instance') -> 'mypy.types.FunctionLike':
    if func.type:
        assert isinstance(func.type, mypy.types.FunctionLike)
        return func.type
    else:
        # Implicit type signature with dynamic types.
        # Overloaded functions always have a signature, so func must be an ordinary function.
        fdef = cast(FuncDef, func)
        name = func.name()
        if name:
            name = '"{}"'.format(name)

        return mypy.types.CallableType(
            [mypy.types.AnyType()] * len(fdef.arg_names),
            fdef.arg_kinds,
            fdef.arg_names,
            mypy.types.AnyType(),
            fallback,
            name,
            implicit=True,
        )


def method_type_with_fallback(func: FuncBase,
                              fallback: 'mypy.types.Instance') -> 'mypy.types.FunctionLike':
    """Return the signature of a method (omit self)."""
    return method_type(function_type(func, fallback))


def method_type(sig: 'mypy.types.FunctionLike') -> 'mypy.types.FunctionLike':
    if isinstance(sig, mypy.types.CallableType):
        return method_callable(sig)
    else:
        sig = cast(mypy.types.Overloaded, sig)
        items = []  # type: List[mypy.types.CallableType]
        for c in sig.items():
            items.append(method_callable(c))
        return mypy.types.Overloaded(items)


def method_callable(c: 'mypy.types.CallableType') -> 'mypy.types.CallableType':
    if c.arg_kinds and c.arg_kinds[0] == ARG_STAR:
        # The signature is of the form 'def foo(*args, ...)'.
        # In this case we shouldn't drop the first arg,
        # since self will be absorbed by the *args.
        return c
    return c.copy_modified(arg_types=c.arg_types[1:],
                           arg_kinds=c.arg_kinds[1:],
                           arg_names=c.arg_names[1:])


class MroError(Exception):
    """Raised if a consistent mro cannot be determined for a class."""


def linearize_hierarchy(info: TypeInfo) -> List[TypeInfo]:
    # TODO describe
    if info.mro:
        return info.mro
    bases = info.direct_base_classes()
    lin_bases = []
    for base in bases:
        assert base is not None, "Cannot linearize bases for %s %s" % (info.fullname(), bases)
        lin_bases.append(linearize_hierarchy(base))
    lin_bases.append(bases)
    return [info] + merge(lin_bases)


def merge(seqs: List[List[TypeInfo]]) -> List[TypeInfo]:
    seqs = [s[:] for s in seqs]
    result = []  # type: List[TypeInfo]
    while True:
        seqs = [s for s in seqs if s]
        if not seqs:
            return result
        for seq in seqs:
            head = seq[0]
            if not [s for s in seqs if head in s[1:]]:
                break
        else:
            raise MroError()
        result.append(head)
        for s in seqs:
            if s[0] is head:
                del s[0]


def get_flags(node: Node, names: List[str]) -> List[str]:
    return [name for name in names if getattr(node, name)]


def set_flags(node: Node, flags: List[str]) -> None:
    for name in flags:
        setattr(node, name, True)
