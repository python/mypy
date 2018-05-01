"""Abstract syntax tree node classes (i.e. parse tree)."""

import os
from abc import abstractmethod
from collections import OrderedDict, defaultdict
from typing import (
    Any, TypeVar, List, Tuple, cast, Set, Dict, Union, Optional, Callable, Sequence
)

MYPY = False
if MYPY:
    from typing import DefaultDict

import mypy.strconv
from mypy.util import short_type
from mypy.visitor import NodeVisitor, StatementVisitor, ExpressionVisitor


class Context:
    """Base type for objects that are valid as error message locations."""
    __slots__ = ('line', 'column')

    def __init__(self, line: int = -1, column: int = -1) -> None:
        self.line = line
        self.column = column

    def set_line(self, target: Union['Context', int], column: Optional[int] = None) -> None:
        """If target is a node, pull line (and column) information
        into this node. If column is specified, this will override any column
        information coming from a node.
        """
        if isinstance(target, int):
            self.line = target
        else:
            self.line = target.line
            self.column = target.column

        if column is not None:
            self.column = column

    def get_line(self) -> int:
        """Don't use. Use x.line."""
        return self.line

    def get_column(self) -> int:
        """Don't use. Use x.column."""
        return self.column


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
# Type variable declared using TypeVar(...) has kind TVAR. It's not
# valid as a type unless bound in a TypeVarScope.  That happens within:
# (1) a generic class that uses the type variable as a type argument or
# (2) a generic function that refers to the type variable in its signature.
TVAR = 4  # type: int

TYPE_ALIAS = 6  # type: int
# Placeholder for a name imported via 'from ... import'. Second phase of
# semantic will replace this the actual imported reference. This is
# needed so that we can detect whether a name has been imported during
# XXX what?
UNBOUND_IMPORTED = 7  # type: int


LITERAL_YES = 2
LITERAL_TYPE = 1
LITERAL_NO = 0

node_kinds = {
    LDEF: 'Ldef',
    GDEF: 'Gdef',
    MDEF: 'Mdef',
    MODULE_REF: 'ModuleRef',
    TVAR: 'Tvar',
    TYPE_ALIAS: 'TypeAlias',
    UNBOUND_IMPORTED: 'UnboundImported',
}
inverse_node_kinds = {_kind: _name for _name, _kind in node_kinds.items()}


implicit_module_attrs = {'__name__': '__builtins__.str',
                         '__doc__': None,  # depends on Python version, see semanal.py
                         '__file__': '__builtins__.str',
                         '__package__': '__builtins__.str'}


type_aliases = {
    'typing.List': '__builtins__.list',
    'typing.Dict': '__builtins__.dict',
    'typing.Set': '__builtins__.set',
    'typing.FrozenSet': '__builtins__.frozenset',
}

reverse_type_aliases = dict((name.replace('__builtins__', 'builtins'), alias)
                            for alias, name in type_aliases.items())  # type: Dict[str, str]

collections_type_aliases = {
    'typing.ChainMap': '__mypy_collections__.ChainMap',
    'typing.Counter': '__mypy_collections__.Counter',
    'typing.DefaultDict': '__mypy_collections__.defaultdict',
    'typing.Deque': '__mypy_collections__.deque',
}

reverse_collection_aliases = dict((name.replace('__mypy_collections__', 'collections'), alias)
                                  for alias, name in
                                  collections_type_aliases.items())  # type: Dict[str, str]

nongen_builtins = {'builtins.tuple': 'typing.Tuple',
                   'builtins.enumerate': ''}
nongen_builtins.update(reverse_type_aliases)
nongen_builtins.update(reverse_collection_aliases)


class Node(Context):
    """Common base class for all non-type parse tree nodes."""

    __slots__ = ()

    def __str__(self) -> str:
        ans = self.accept(mypy.strconv.StrConv())
        if ans is None:
            return repr(self)
        return ans

    def accept(self, visitor: NodeVisitor[T]) -> T:
        raise RuntimeError('Not implemented')


class Statement(Node):
    """A statement node."""

    __slots__ = ()

    def accept(self, visitor: StatementVisitor[T]) -> T:
        raise RuntimeError('Not implemented')


class Expression(Node):
    """An expression node."""

    __slots__ = ()

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        raise RuntimeError('Not implemented')


# TODO:
# Lvalue = Union['NameExpr', 'MemberExpr', 'IndexExpr', 'SuperExpr', 'StarExpr'
#                'TupleExpr']; see #1783.
Lvalue = Expression


class SymbolNode(Node):
    """Nodes that can be stored in a symbol table."""

    __slots__ = ()

    # TODO do not use methods for these

    @abstractmethod
    def name(self) -> str: pass

    @abstractmethod
    def fullname(self) -> str: pass

    @abstractmethod
    def serialize(self) -> JsonDict: pass

    @classmethod
    def deserialize(cls, data: JsonDict) -> 'SymbolNode':
        classname = data['.class']
        method = deserialize_map.get(classname)
        if method is not None:
            return method(data)
        raise NotImplementedError('unexpected .class {}'.format(classname))


class MypyFile(SymbolNode):
    """The abstract syntax tree of a single source file."""

    # Module name ('__main__' for initial file)
    _name = None      # type: str
    # Fully qualified module name
    _fullname = None  # type: str
    # Path to the file (None if not known)
    path = ''
    # Top-level definitions and statements
    defs = None  # type: List[Statement]
    # Type alias dependencies as mapping from target to set of alias full names
    alias_deps = None  # type: DefaultDict[str, Set[str]]
    # Is there a UTF-8 BOM at the start?
    is_bom = False
    names = None  # type: SymbolTable
    # All import nodes within the file (also ones within functions etc.)
    imports = None  # type: List[ImportBase]
    # Lines to ignore when checking
    ignored_lines = None  # type: Set[int]
    # Is this file represented by a stub file (.pyi)?
    is_stub = False
    # Is this loaded from the cache and thus missing the actual body of the file?
    is_cache_skeleton = False

    def __init__(self,
                 defs: List[Statement],
                 imports: List['ImportBase'],
                 is_bom: bool = False,
                 ignored_lines: Optional[Set[int]] = None) -> None:
        super().__init__()
        self.defs = defs
        self.line = 1  # Dummy line number
        self.imports = imports
        self.is_bom = is_bom
        self.alias_deps = defaultdict(set)
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
        tree.is_cache_skeleton = True
        return tree


class ImportBase(Statement):
    """Base class for all import statements."""

    is_unreachable = False  # Set by semanal.SemanticAnalyzerPass1 if inside `if False` etc.
    is_top_level = False  # Ditto if outside any class or def
    is_mypy_only = False  # Ditto if inside `if TYPE_CHECKING` or `if MYPY`

    # If an import replaces existing definitions, we construct dummy assignment
    # statements that assign the imported names to the names in the current scope,
    # for type checking purposes. Example:
    #
    #     x = 1
    #     from m import x   <-- add assignment representing "x = m.x"
    assignments = None  # type: List[AssignmentStmt]

    def __init__(self) -> None:
        super().__init__()
        self.assignments = []


class Import(ImportBase):
    """import m [as n]"""

    ids = None  # type: List[Tuple[str, Optional[str]]]     # (module id, as id)

    def __init__(self, ids: List[Tuple[str, Optional[str]]]) -> None:
        super().__init__()
        self.ids = ids

    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_import(self)


class ImportFrom(ImportBase):
    """from m import x [as y], ..."""

    id = None  # type: str
    relative = None  # type: int
    names = None  # type: List[Tuple[str, Optional[str]]]  # Tuples (name, as name)

    def __init__(self, id: str, relative: int, names: List[Tuple[str, Optional[str]]]) -> None:
        super().__init__()
        self.id = id
        self.names = names
        self.relative = relative

    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_import_from(self)


class ImportAll(ImportBase):
    """from m import *"""
    id = None  # type: str
    relative = None  # type: int
    imported_names = None  # type: List[str]

    def __init__(self, id: str, relative: int) -> None:
        super().__init__()
        self.id = id
        self.relative = relative
        self.imported_names = []

    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_import_all(self)


class ImportedName(SymbolNode):
    """Indirect reference to a fullname stored in symbol table.

    This node is not present in the original program as such. This is
    just a temporary artifact in binding imported names. After semantic
    analysis pass 2, these references should be replaced with direct
    reference to a real AST node.

    Note that this is neither a Statement nor an Expression so this
    can't be visited.
    """

    def __init__(self, target_fullname: str) -> None:
        super().__init__()
        self.target_fullname = target_fullname

    def name(self) -> str:
        return self.target_fullname.split('.')[-1]

    def fullname(self) -> str:
        return self.target_fullname

    def serialize(self) -> JsonDict:
        assert False, "ImportedName leaked from semantic analysis"

    @classmethod
    def deserialize(cls, data: JsonDict) -> 'ImportedName':
        assert False, "ImportedName should never be serialized"

    def __str__(self) -> str:
        return 'ImportedName(%s)' % self.target_fullname


class FuncBase(Node):
    """Abstract base class for function-like nodes"""

    __slots__ = ('type',
                 'unanalyzed_type',
                 'info',
                 'is_property',
                 '_fullname',
                 )

    def __init__(self) -> None:
        super().__init__()
        # Type signature. This is usually CallableType or Overloaded, but it can be
        # something else for decorated functions.
        self.type = None  # type: Optional[mypy.types.Type]
        # Original, not semantically analyzed type (used for reprocessing)
        self.unanalyzed_type = None  # type: Optional[mypy.types.Type]
        # If method, reference to TypeInfo
        # TODO: Type should be Optional[TypeInfo]
        self.info = cast(TypeInfo, None)
        self.is_property = False
        # Name with module prefix
        # TODO: Type should be Optional[str]
        self._fullname = cast(str, None)

    @abstractmethod
    def name(self) -> str: pass

    def fullname(self) -> str:
        return self._fullname


OverloadPart = Union['FuncDef', 'Decorator']


class OverloadedFuncDef(FuncBase, SymbolNode, Statement):
    """A logical node representing all the variants of a multi-declaration function.

    A multi-declaration function is often an @overload, but can also be a
    @property with a setter and a/or a deleter.

    This node has no explicit representation in the source program.
    Overloaded variants must be consecutive in the source file.
    """

    items = None  # type: List[OverloadPart]
    impl = None  # type: Optional[OverloadPart]

    def __init__(self, items: List['OverloadPart']) -> None:
        super().__init__()
        assert len(items) > 0
        self.items = items
        self.impl = None
        self.set_line(items[0].line)

    def name(self) -> str:
        return self.items[0].name()

    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_overloaded_func_def(self)

    def serialize(self) -> JsonDict:
        return {'.class': 'OverloadedFuncDef',
                'items': [i.serialize() for i in self.items],
                'type': None if self.type is None else self.type.serialize(),
                'fullname': self._fullname,
                'is_property': self.is_property,
                'impl': None if self.impl is None else self.impl.serialize()
                }

    @classmethod
    def deserialize(cls, data: JsonDict) -> 'OverloadedFuncDef':
        assert data['.class'] == 'OverloadedFuncDef'
        res = OverloadedFuncDef([
            cast(OverloadPart, SymbolNode.deserialize(d))
            for d in data['items']])
        if data.get('impl') is not None:
            res.impl = cast(OverloadPart, SymbolNode.deserialize(data['impl']))
        if data.get('type') is not None:
            res.type = mypy.types.deserialize_type(data['type'])
        res._fullname = data['fullname']
        res.is_property = data['is_property']
        # NOTE: res.info will be set in the fixup phase.
        return res


class Argument(Node):
    """A single argument in a FuncItem."""

    __slots__ = ('variable', 'type_annotation', 'initializer', 'kind')

    def __init__(self,
                 variable: 'Var',
                 type_annotation: 'Optional[mypy.types.Type]',
                 initializer: Optional[Expression],
                 kind: int) -> None:
        super().__init__()
        self.variable = variable
        self.type_annotation = type_annotation
        self.initializer = initializer
        self.kind = kind  # must be an ARG_* constant

    def set_line(self, target: Union[Context, int], column: Optional[int] = None) -> None:
        super().set_line(target, column)

        if self.initializer:
            self.initializer.set_line(self.line, self.column)

        self.variable.set_line(self.line, self.column)


FUNCITEM_FLAGS = [
    'is_overload', 'is_generator', 'is_coroutine', 'is_async_generator',
    'is_awaitable_coroutine', 'is_static', 'is_class',
]


class FuncItem(FuncBase):
    """Base class for nodes usable as overloaded function items."""

    __slots__ = ('arguments',  # Note that can be None if deserialized (type is a lie!)
                 'arg_names',  # Names of arguments
                 'arg_kinds',  # Kinds of arguments
                 'min_args',  # Minimum number of arguments
                 'max_pos',  # Maximum number of positional arguments, -1 if no explicit
                             # limit (*args not included)
                 'body',  # Body of the function
                 'is_overload',  # Is this an overload variant of function with more than
                                 # one overload variant?
                 'is_generator',  # Contains a yield statement?
                 'is_coroutine',  # Defined using 'async def' syntax?
                 'is_async_generator',  # Is an async def generator?
                 'is_awaitable_coroutine',  # Decorated with '@{typing,asyncio}.coroutine'?
                 'is_static',  # Uses @staticmethod?
                 'is_class',  # Uses @classmethod?
                 'expanded',  # Variants of function with type variables with values expanded
                 )

    def __init__(self,
                 arguments: List[Argument],
                 body: 'Block',
                 typ: 'Optional[mypy.types.FunctionLike]' = None) -> None:
        super().__init__()
        self.arguments = arguments
        self.arg_names = [arg.variable.name() for arg in self.arguments]
        self.arg_kinds = [arg.kind for arg in self.arguments]  # type: List[int]
        self.max_pos = self.arg_kinds.count(ARG_POS) + self.arg_kinds.count(ARG_OPT)
        self.body = body
        self.type = typ
        self.unanalyzed_type = typ
        self.is_overload = False
        self.is_generator = False
        self.is_coroutine = False
        self.is_async_generator = False
        self.is_awaitable_coroutine = False
        self.is_static = False
        self.is_class = False
        self.expanded = []  # type: List[FuncItem]

        self.min_args = 0
        for i in range(len(self.arguments)):
            if self.arguments[i] is None and i < self.max_fixed_argc():
                self.min_args = i + 1

    def max_fixed_argc(self) -> int:
        return self.max_pos

    def set_line(self, target: Union[Context, int], column: Optional[int] = None) -> None:
        super().set_line(target, column)
        for arg in self.arguments:
            arg.set_line(self.line, self.column)

    def is_dynamic(self) -> bool:
        return self.type is None


FUNCDEF_FLAGS = FUNCITEM_FLAGS + [
    'is_decorated', 'is_conditional', 'is_abstract', 'is_property',
]


class FuncDef(FuncItem, SymbolNode, Statement):
    """Function definition.

    This is a non-lambda function defined using 'def'.
    """

    __slots__ = ('_name',
                 'is_decorated',
                 'is_conditional',
                 'is_abstract',
                 'is_property',
                 'original_def',
                 )

    def __init__(self,
                 name: str,              # Function name
                 arguments: List[Argument],
                 body: 'Block',
                 typ: 'Optional[mypy.types.FunctionLike]' = None) -> None:
        super().__init__(arguments, body, typ)
        self._name = name
        self.is_decorated = False
        self.is_conditional = False  # Defined conditionally (within block)?
        self.is_abstract = False
        self.is_property = False
        # Original conditional definition
        self.original_def = None  # type: Union[None, FuncDef, Var, Decorator]

    def name(self) -> str:
        return self._name

    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_func_def(self)

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
                'flags': get_flags(self, FUNCDEF_FLAGS),
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
                       else cast(mypy.types.FunctionLike,
                                 mypy.types.deserialize_type(data['type']))))
        ret._fullname = data['fullname']
        set_flags(ret, data['flags'])
        # NOTE: ret.info is set in the fixup phase.
        ret.arg_names = data['arg_names']
        ret.arg_kinds = data['arg_kinds']
        # Mark these as 'None' so that future uses will trigger an error
        _dummy = None  # type: Any
        ret.arguments = _dummy
        ret.max_pos = _dummy
        ret.min_args = _dummy
        return ret


class Decorator(SymbolNode, Statement):
    """A decorated function.

    A single Decorator object can include any number of function decorators.
    """

    func = None  # type: FuncDef                # Decorated function
    decorators = None  # type: List[Expression] # Decorators (may be empty)
    # TODO: This is mostly used for the type; consider replacing with a 'type' attribute
    var = None  # type: Var                     # Represents the decorated function obj
    is_overload = False

    def __init__(self, func: FuncDef, decorators: List[Expression],
                 var: 'Var') -> None:
        super().__init__()
        self.func = func
        self.decorators = decorators
        self.var = var
        self.is_overload = False

    def name(self) -> str:
        return self.func.name()

    def fullname(self) -> str:
        return self.func.fullname()

    @property
    def info(self) -> 'TypeInfo':
        return self.func.info

    @property
    def type(self) -> 'Optional[mypy.types.Type]':
        return self.var.type

    def accept(self, visitor: StatementVisitor[T]) -> T:
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


VAR_FLAGS = [
    'is_self', 'is_initialized_in_class', 'is_staticmethod',
    'is_classmethod', 'is_property', 'is_settable_property', 'is_suppressed_import',
    'is_classvar', 'is_abstract_var'
]


class Var(SymbolNode):
    """A variable.

    It can refer to global/local variable or a data attribute.
    """

    __slots__ = ('_name',
                 '_fullname',
                 'info',
                 'type',
                 'is_self',
                 'is_ready',
                 'is_inferred',
                 'is_initialized_in_class',
                 'is_staticmethod',
                 'is_classmethod',
                 'is_property',
                 'is_settable_property',
                 'is_classvar',
                 'is_abstract_var',
                 'is_suppressed_import',
                 )

    def __init__(self, name: str, type: 'Optional[mypy.types.Type]' = None) -> None:
        super().__init__()
        self._name = name   # Name without module prefix
        # TODO: Should be Optional[str]
        self._fullname = cast(str, None)  # Name with module prefix
        # TODO: Should be Optional[TypeInfo]
        self.info = cast(TypeInfo, None)  # Defining class (for member variables)
        self.type = type  # type: Optional[mypy.types.Type] # Declared or inferred type, or None
        # Is this the first argument to an ordinary method (usually "self")?
        self.is_self = False
        self.is_ready = True  # If inferred, is the inferred type available?
        self.is_inferred = (self.type is None)
        # Is this initialized explicitly to a non-None value in class body?
        self.is_initialized_in_class = False
        self.is_staticmethod = False
        self.is_classmethod = False
        self.is_property = False
        self.is_settable_property = False
        self.is_classvar = False
        self.is_abstract_var = False
        # Set to true when this variable refers to a module we were unable to
        # parse for some reason (eg a silenced module)
        self.is_suppressed_import = False

    def name(self) -> str:
        return self._name

    def fullname(self) -> str:
        return self._fullname

    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_var(self)

    def serialize(self) -> JsonDict:
        # TODO: Leave default values out?
        # NOTE: Sometimes self.is_ready is False here, but we don't care.
        data = {'.class': 'Var',
                'name': self._name,
                'fullname': self._fullname,
                'type': None if self.type is None else self.type.serialize(),
                'flags': get_flags(self, VAR_FLAGS),
                }  # type: JsonDict
        return data

    @classmethod
    def deserialize(cls, data: JsonDict) -> 'Var':
        assert data['.class'] == 'Var'
        name = data['name']
        type = None if data['type'] is None else mypy.types.deserialize_type(data['type'])
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
    # Special base classes like Generic[...] get moved here during semantic analysis
    removed_base_type_exprs = None  # type: List[Expression]
    info = None  # type: TypeInfo  # Related TypeInfo
    metaclass = None  # type: Optional[Expression]
    decorators = None  # type: List[Expression]
    keywords = None  # type: OrderedDict[str, Expression]
    analyzed = None  # type: Optional[Expression]
    has_incompatible_baseclass = False

    def __init__(self,
                 name: str,
                 defs: 'Block',
                 type_vars: Optional[List['mypy.types.TypeVarDef']] = None,
                 base_type_exprs: Optional[List[Expression]] = None,
                 metaclass: Optional[Expression] = None,
                 keywords: Optional[List[Tuple[str, Expression]]] = None) -> None:
        super().__init__()
        self.name = name
        self.defs = defs
        self.type_vars = type_vars or []
        self.base_type_exprs = base_type_exprs or []
        self.removed_base_type_exprs = []
        self.metaclass = metaclass
        self.decorators = []
        self.keywords = OrderedDict(keywords or [])

    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_class_def(self)

    def is_generic(self) -> bool:
        return self.info.is_generic()

    def serialize(self) -> JsonDict:
        # Not serialized: defs, base_type_exprs, metaclass, decorators,
        # analyzed (for named tuples etc.)
        return {'.class': 'ClassDef',
                'name': self.name,
                'fullname': self.fullname,
                'type_vars': [v.serialize() for v in self.type_vars],
                }

    @classmethod
    def deserialize(self, data: JsonDict) -> 'ClassDef':
        assert data['.class'] == 'ClassDef'
        res = ClassDef(data['name'],
                       Block([]),
                       [mypy.types.TypeVarDef.deserialize(v) for v in data['type_vars']],
                       )
        res.fullname = data['fullname']
        return res


class GlobalDecl(Statement):
    """Declaration global x, y, ..."""

    names = None  # type: List[str]

    def __init__(self, names: List[str]) -> None:
        super().__init__()
        self.names = names

    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_global_decl(self)


class NonlocalDecl(Statement):
    """Declaration nonlocal x, y, ..."""

    names = None  # type: List[str]

    def __init__(self, names: List[str]) -> None:
        super().__init__()
        self.names = names

    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_nonlocal_decl(self)


class Block(Statement):
    __slots__ = ('body', 'is_unreachable')

    def __init__(self, body: List[Statement]) -> None:
        super().__init__()
        self.body = body
        # True if we can determine that this block is not executed during semantic
        # analysis. For example, this applies to blocks that are protected by
        # something like "if PY3:" when using Python 2. However, some code is
        # only considered unreachable during type checking and this is not true
        # in those cases.
        self.is_unreachable = False

    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_block(self)


# Statements


class ExpressionStmt(Statement):
    """An expression as a statement, such as print(s)."""
    expr = None  # type: Expression

    def __init__(self, expr: Expression) -> None:
        super().__init__()
        self.expr = expr

    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_expression_stmt(self)


class AssignmentStmt(Statement):
    """Assignment statement
    The same node class is used for single assignment, multiple assignment
    (e.g. x, y = z) and chained assignment (e.g. x = y = z), assignments
    that define new names, and assignments with explicit types (# type).

    An lvalue can be NameExpr, TupleExpr, ListExpr, MemberExpr, IndexExpr.
    """

    lvalues = None  # type: List[Lvalue]
    rvalue = None  # type: Expression
    # Declared type in a comment, may be None.
    type = None  # type: Optional[mypy.types.Type]
    # Original, not semantically analyzed type in annotation (used for reprocessing)
    unanalyzed_type = None  # type: Optional[mypy.types.Type]
    # This indicates usage of PEP 526 type annotation syntax in assignment.
    new_syntax = False  # type: bool
    # Does this assignment define a type alias?
    is_alias_def = False

    def __init__(self, lvalues: List[Lvalue], rvalue: Expression,
                 type: 'Optional[mypy.types.Type]' = None, new_syntax: bool = False) -> None:
        super().__init__()
        self.lvalues = lvalues
        self.rvalue = rvalue
        self.type = type
        self.unanalyzed_type = type
        self.new_syntax = new_syntax

    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_assignment_stmt(self)


class OperatorAssignmentStmt(Statement):
    """Operator assignment statement such as x += 1"""

    op = ''
    lvalue = None  # type: Lvalue
    rvalue = None  # type: Expression

    def __init__(self, op: str, lvalue: Lvalue, rvalue: Expression) -> None:
        super().__init__()
        self.op = op
        self.lvalue = lvalue
        self.rvalue = rvalue

    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_operator_assignment_stmt(self)


class WhileStmt(Statement):
    expr = None  # type: Expression
    body = None  # type: Block
    else_body = None  # type: Optional[Block]

    def __init__(self, expr: Expression, body: Block, else_body: Optional[Block]) -> None:
        super().__init__()
        self.expr = expr
        self.body = body
        self.else_body = else_body

    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_while_stmt(self)


class ForStmt(Statement):
    # Index variables
    index = None  # type: Lvalue
    # Type given by type comments for index, can be None
    index_type = None  # type: Optional[mypy.types.Type]
    # Inferred iterable item type
    inferred_item_type = None  # type: Optional[mypy.types.Type]
    # Inferred iterator type
    inferred_iterator_type = None  # type: Optional[mypy.types.Type]
    # Expression to iterate
    expr = None  # type: Expression
    body = None  # type: Block
    else_body = None  # type: Optional[Block]
    is_async = False  # True if `async for ...` (PEP 492, Python 3.5)

    def __init__(self,
                 index: Lvalue,
                 expr: Expression,
                 body: Block,
                 else_body: Optional[Block],
                 index_type: 'Optional[mypy.types.Type]' = None) -> None:
        super().__init__()
        self.index = index
        self.index_type = index_type
        self.expr = expr
        self.body = body
        self.else_body = else_body

    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_for_stmt(self)


class ReturnStmt(Statement):
    expr = None  # type: Optional[Expression]

    def __init__(self, expr: Optional[Expression]) -> None:
        super().__init__()
        self.expr = expr

    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_return_stmt(self)


class AssertStmt(Statement):
    expr = None  # type: Expression
    msg = None  # type: Optional[Expression]

    def __init__(self, expr: Expression, msg: Optional[Expression] = None) -> None:
        super().__init__()
        self.expr = expr
        self.msg = msg

    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_assert_stmt(self)


class DelStmt(Statement):
    expr = None  # type: Lvalue

    def __init__(self, expr: Lvalue) -> None:
        super().__init__()
        self.expr = expr

    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_del_stmt(self)


class BreakStmt(Statement):
    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_break_stmt(self)


class ContinueStmt(Statement):
    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_continue_stmt(self)


class PassStmt(Statement):
    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_pass_stmt(self)


class IfStmt(Statement):
    expr = None  # type: List[Expression]
    body = None  # type: List[Block]
    else_body = None  # type: Optional[Block]

    def __init__(self, expr: List[Expression], body: List[Block],
                 else_body: Optional[Block]) -> None:
        super().__init__()
        self.expr = expr
        self.body = body
        self.else_body = else_body

    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_if_stmt(self)


class RaiseStmt(Statement):
    # Plain 'raise' is a valid statement.
    expr = None  # type: Optional[Expression]
    from_expr = None  # type: Optional[Expression]

    def __init__(self, expr: Optional[Expression], from_expr: Optional[Expression]) -> None:
        super().__init__()
        self.expr = expr
        self.from_expr = from_expr

    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_raise_stmt(self)


class TryStmt(Statement):
    body = None  # type: Block                # Try body
    # Plain 'except:' also possible
    types = None  # type: List[Optional[Expression]]    # Except type expressions
    vars = None  # type: List[Optional[NameExpr]]     # Except variable names
    handlers = None  # type: List[Block]      # Except bodies
    else_body = None  # type: Optional[Block]
    finally_body = None  # type: Optional[Block]

    def __init__(self, body: Block, vars: List['Optional[NameExpr]'],
                 types: List[Optional[Expression]],
                 handlers: List[Block], else_body: Optional[Block],
                 finally_body: Optional[Block]) -> None:
        super().__init__()
        self.body = body
        self.vars = vars
        self.types = types
        self.handlers = handlers
        self.else_body = else_body
        self.finally_body = finally_body

    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_try_stmt(self)


class WithStmt(Statement):
    expr = None  # type: List[Expression]
    target = None  # type: List[Optional[Lvalue]]
    # Type given by type comments for target, can be None
    target_type = None  # type: Optional[mypy.types.Type]
    body = None  # type: Block
    is_async = False  # True if `async with ...` (PEP 492, Python 3.5)

    def __init__(self, expr: List[Expression], target: List[Optional[Lvalue]],
                 body: Block, target_type: 'Optional[mypy.types.Type]' = None) -> None:
        super().__init__()
        self.expr = expr
        self.target = target
        self.target_type = target_type
        self.body = body

    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_with_stmt(self)


class PrintStmt(Statement):
    """Python 2 print statement"""

    args = None  # type: List[Expression]
    newline = False
    # The file-like target object (given using >>).
    target = None  # type: Optional[Expression]

    def __init__(self,
                 args: List[Expression],
                 newline: bool,
                 target: Optional[Expression] = None) -> None:
        super().__init__()
        self.args = args
        self.newline = newline
        self.target = target

    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_print_stmt(self)


class ExecStmt(Statement):
    """Python 2 exec statement"""

    expr = None  # type: Expression
    globals = None  # type: Optional[Expression]
    locals = None  # type: Optional[Expression]

    def __init__(self, expr: Expression,
                 globals: Optional[Expression],
                 locals: Optional[Expression]) -> None:
        super().__init__()
        self.expr = expr
        self.globals = globals
        self.locals = locals

    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_exec_stmt(self)


# Expressions


class IntExpr(Expression):
    """Integer literal"""

    value = 0

    def __init__(self, value: int) -> None:
        super().__init__()
        self.value = value

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
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

    def __init__(self, value: str) -> None:
        super().__init__()
        self.value = value

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_str_expr(self)


class BytesExpr(Expression):
    """Bytes literal"""

    value = ''  # TODO use bytes

    def __init__(self, value: str) -> None:
        super().__init__()
        self.value = value

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_bytes_expr(self)


class UnicodeExpr(Expression):
    """Unicode literal (Python 2.x)"""

    value = ''  # TODO use bytes

    def __init__(self, value: str) -> None:
        super().__init__()
        self.value = value

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_unicode_expr(self)


class FloatExpr(Expression):
    """Float literal"""

    value = 0.0

    def __init__(self, value: float) -> None:
        super().__init__()
        self.value = value

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_float_expr(self)


class ComplexExpr(Expression):
    """Complex literal"""

    value = 0.0j

    def __init__(self, value: complex) -> None:
        super().__init__()
        self.value = value

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_complex_expr(self)


class EllipsisExpr(Expression):
    """Ellipsis (...)"""

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_ellipsis(self)


class StarExpr(Expression):
    """Star expression"""

    expr = None  # type: Expression

    def __init__(self, expr: Expression) -> None:
        super().__init__()
        self.expr = expr

        # Whether this starred expression is used in a tuple/list and as lvalue
        self.valid = False

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_star_expr(self)


class RefExpr(Expression):
    """Abstract base class for name-like constructs"""

    __slots__ = ('kind', 'node', 'fullname', 'is_new_def', 'is_inferred_def')

    def __init__(self) -> None:
        super().__init__()
        # LDEF/GDEF/MDEF/... (None if not available)
        self.kind = None  # type: Optional[int]
        # Var, FuncDef or TypeInfo that describes this
        self.node = None  # type: Optional[SymbolNode]
        # Fully qualified name (or name if not global)
        self.fullname = None  # type: Optional[str]
        # Does this define a new name?
        self.is_new_def = False
        # Does this define a new name with inferred type?
        #
        # For members, after semantic analysis, this does not take base
        # classes into consideration at all; the type checker deals with these.
        self.is_inferred_def = False


class NameExpr(RefExpr):
    """Name expression

    This refers to a local name, global name or a module.
    """

    __slots__ = ('name',)

    def __init__(self, name: str) -> None:
        super().__init__()
        self.name = name  # Name referred to (may be qualified)

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_name_expr(self)

    def serialize(self) -> JsonDict:
        # TODO: Find out where and why NameExpr is being serialized (if at all).
        assert False, "Serializing NameExpr: %s" % (self,)
        return {'.class': 'NameExpr',
                'kind': self.kind,
                'node': None if self.node is None else self.node.serialize(),
                'fullname': self.fullname,
                'is_new_def': self.is_new_def,
                'is_inferred_def': self.is_inferred_def,
                'name': self.name,
                }

    @classmethod
    def deserialize(cls, data: JsonDict) -> 'NameExpr':
        assert data['.class'] == 'NameExpr'
        ret = NameExpr(data['name'])
        ret.kind = data['kind']
        ret.node = None if data['node'] is None else SymbolNode.deserialize(data['node'])
        ret.fullname = data['fullname']
        ret.is_new_def = data['is_new_def']
        ret.is_inferred_def = data['is_inferred_def']
        return ret


class MemberExpr(RefExpr):
    """Member access expression x.y"""

    __slots__ = ('expr', 'name', 'def_var')

    def __init__(self, expr: Expression, name: str) -> None:
        super().__init__()
        self.expr = expr
        self.name = name
        # The variable node related to a definition through 'self.x = <initializer>'.
        # The nodes of other kinds of member expressions are resolved during type checking.
        self.def_var = None  # type: Optional[Var]

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
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
# In an argument list, keyword-only and also optional
ARG_NAMED_OPT = 5


class CallExpr(Expression):
    """Call expression.

    This can also represent several special forms that are syntactically calls
    such as cast(...) and None  # type: ....
    """

    __slots__ = ('callee', 'args', 'arg_kinds', 'arg_names', 'analyzed')

    def __init__(self,
                 callee: Expression,
                 args: List[Expression],
                 arg_kinds: List[int],
                 arg_names: List[Optional[str]],
                 analyzed: Optional[Expression] = None) -> None:
        super().__init__()
        if not arg_names:
            arg_names = [None] * len(args)

        self.callee = callee
        self.args = args
        self.arg_kinds = arg_kinds  # ARG_ constants
        # Each name can be None if not a keyword argument.
        self.arg_names = arg_names  # type: List[Optional[str]]
        # If not None, the node that represents the meaning of the CallExpr. For
        # cast(...) this is a CastExpr.
        self.analyzed = analyzed

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_call_expr(self)


class YieldFromExpr(Expression):
    expr = None  # type: Expression

    def __init__(self, expr: Expression) -> None:
        super().__init__()
        self.expr = expr

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_yield_from_expr(self)


class YieldExpr(Expression):
    expr = None  # type: Optional[Expression]

    def __init__(self, expr: Optional[Expression]) -> None:
        super().__init__()
        self.expr = expr

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
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
    analyzed = None  # type: Union[TypeApplication, TypeAliasExpr, None]

    def __init__(self, base: Expression, index: Expression) -> None:
        super().__init__()
        self.base = base
        self.index = index
        self.analyzed = None

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_index_expr(self)


class UnaryExpr(Expression):
    """Unary operation"""

    op = ''
    expr = None  # type: Expression
    # Inferred operator method type
    method_type = None  # type: Optional[mypy.types.Type]

    def __init__(self, op: str, expr: Expression) -> None:
        super().__init__()
        self.op = op
        self.expr = expr

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_unary_expr(self)


# Map from binary operator id to related method name (in Python 3).
op_methods = {
    '+': '__add__',
    '-': '__sub__',
    '*': '__mul__',
    '/': '__truediv__',
    '%': '__mod__',
    'divmod': '__divmod__',
    '//': '__floordiv__',
    '**': '__pow__',
    '@': '__matmul__',
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
    '+', '-', '*', '/', '%', '//', '**', '@', '&', '|', '^', '<<', '>>'}

inplace_operator_methods = set(
    '__i' + op_methods[op][2:] for op in ops_with_inplace_method)

reverse_op_methods = {
    '__add__': '__radd__',
    '__sub__': '__rsub__',
    '__mul__': '__rmul__',
    '__truediv__': '__rtruediv__',
    '__mod__': '__rmod__',
    '__divmod__': '__rdivmod__',
    '__floordiv__': '__rfloordiv__',
    '__pow__': '__rpow__',
    '__matmul__': '__rmatmul__',
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

unary_op_methods = {
    '-': '__neg__',
    '+': '__pos__',
    '~': '__invert__',
}


class OpExpr(Expression):
    """Binary operation (other than . or [] or comparison operators,
    which have specific nodes)."""

    op = ''
    left = None  # type: Expression
    right = None  # type: Expression
    # Inferred type for the operator method type (when relevant).
    method_type = None  # type: Optional[mypy.types.Type]
    # Is the right side going to be evaluated every time?
    right_always = False
    # Is the right side unreachable?
    right_unreachable = False

    def __init__(self, op: str, left: Expression, right: Expression) -> None:
        super().__init__()
        self.op = op
        self.left = left
        self.right = right

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_op_expr(self)


class ComparisonExpr(Expression):
    """Comparison expression (e.g. a < b > c < d)."""

    operators = None  # type: List[str]
    operands = None  # type: List[Expression]
    # Inferred type for the operator methods (when relevant; None for 'is').
    method_types = None  # type: List[Optional[mypy.types.Type]]

    def __init__(self, operators: List[str], operands: List[Expression]) -> None:
        super().__init__()
        self.operators = operators
        self.operands = operands
        self.method_types = []

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
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
        super().__init__()
        self.begin_index = begin_index
        self.end_index = end_index
        self.stride = stride

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_slice_expr(self)


class CastExpr(Expression):
    """Cast expression cast(type, expr)."""

    expr = None  # type: Expression
    type = None  # type: mypy.types.Type

    def __init__(self, expr: Expression, typ: 'mypy.types.Type') -> None:
        super().__init__()
        self.expr = expr
        self.type = typ

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_cast_expr(self)


class RevealTypeExpr(Expression):
    """Reveal type expression reveal_type(expr)."""

    expr = None  # type: Expression

    def __init__(self, expr: Expression) -> None:
        super().__init__()
        self.expr = expr

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_reveal_type_expr(self)


class SuperExpr(Expression):
    """Expression super().name"""

    name = ''
    info = None  # type: Optional[TypeInfo]  # Type that contains this super expression
    call = None  # type: CallExpr  # The expression super(...)

    def __init__(self, name: str, call: CallExpr) -> None:
        super().__init__()
        self.name = name
        self.call = call

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_super_expr(self)


class LambdaExpr(FuncItem, Expression):
    """Lambda expression"""

    def name(self) -> str:
        return '<lambda>'

    def expr(self) -> Expression:
        """Return the expression (the body) of the lambda."""
        ret = cast(ReturnStmt, self.body.body[-1])
        expr = ret.expr
        assert expr is not None  # lambda can't have empty body
        return expr

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_lambda_expr(self)

    def is_dynamic(self) -> bool:
        return False


class ListExpr(Expression):
    """List literal expression [...]."""

    items = None  # type: List[Expression]

    def __init__(self, items: List[Expression]) -> None:
        super().__init__()
        self.items = items

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_list_expr(self)


class DictExpr(Expression):
    """Dictionary literal expression {key: value, ...}."""

    items = None  # type: List[Tuple[Expression, Expression]]

    def __init__(self, items: List[Tuple[Expression, Expression]]) -> None:
        super().__init__()
        self.items = items

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_dict_expr(self)


class TupleExpr(Expression):
    """Tuple literal expression (..., ...)

    Also lvalue sequences (..., ...) and [..., ...]"""

    items = None  # type: List[Expression]

    def __init__(self, items: List[Expression]) -> None:
        super().__init__()
        self.items = items

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_tuple_expr(self)


class SetExpr(Expression):
    """Set literal expression {value, ...}."""

    items = None  # type: List[Expression]

    def __init__(self, items: List[Expression]) -> None:
        super().__init__()
        self.items = items

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_set_expr(self)


class GeneratorExpr(Expression):
    """Generator expression ... for ... in ... [ for ...  in ... ] [ if ... ]."""

    left_expr = None  # type: Expression
    sequences = None  # type: List[Expression]
    condlists = None  # type: List[List[Expression]]
    is_async = None  # type: List[bool]
    indices = None  # type: List[Lvalue]

    def __init__(self, left_expr: Expression, indices: List[Lvalue],
                 sequences: List[Expression], condlists: List[List[Expression]],
                 is_async: List[bool]) -> None:
        super().__init__()
        self.left_expr = left_expr
        self.sequences = sequences
        self.condlists = condlists
        self.indices = indices
        self.is_async = is_async

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_generator_expr(self)


class ListComprehension(Expression):
    """List comprehension (e.g. [x + 1 for x in a])"""

    generator = None  # type: GeneratorExpr

    def __init__(self, generator: GeneratorExpr) -> None:
        super().__init__()
        self.generator = generator

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_list_comprehension(self)


class SetComprehension(Expression):
    """Set comprehension (e.g. {x + 1 for x in a})"""

    generator = None  # type: GeneratorExpr

    def __init__(self, generator: GeneratorExpr) -> None:
        super().__init__()
        self.generator = generator

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_set_comprehension(self)


class DictionaryComprehension(Expression):
    """Dictionary comprehension (e.g. {k: v for k, v in a}"""

    key = None  # type: Expression
    value = None  # type: Expression
    sequences = None  # type: List[Expression]
    condlists = None  # type: List[List[Expression]]
    is_async = None  # type: List[bool]
    indices = None  # type: List[Lvalue]

    def __init__(self, key: Expression, value: Expression, indices: List[Lvalue],
                 sequences: List[Expression], condlists: List[List[Expression]],
                 is_async: List[bool]) -> None:
        super().__init__()
        self.key = key
        self.value = value
        self.sequences = sequences
        self.condlists = condlists
        self.indices = indices
        self.is_async = is_async

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_dictionary_comprehension(self)


class ConditionalExpr(Expression):
    """Conditional expression (e.g. x if y else z)"""

    cond = None  # type: Expression
    if_expr = None  # type: Expression
    else_expr = None  # type: Expression

    def __init__(self, cond: Expression, if_expr: Expression, else_expr: Expression) -> None:
        super().__init__()
        self.cond = cond
        self.if_expr = if_expr
        self.else_expr = else_expr

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_conditional_expr(self)


class BackquoteExpr(Expression):
    """Python 2 expression `...`."""

    expr = None  # type: Expression

    def __init__(self, expr: Expression) -> None:
        super().__init__()
        self.expr = expr

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_backquote_expr(self)


class TypeApplication(Expression):
    """Type application expr[type, ...]"""

    expr = None  # type: Expression
    types = None  # type: List[mypy.types.Type]

    def __init__(self, expr: Expression, types: List['mypy.types.Type']) -> None:
        super().__init__()
        self.expr = expr
        self.types = types

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
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
        super().__init__()
        self._name = name
        self._fullname = fullname
        self.values = values
        self.upper_bound = upper_bound
        self.variance = variance

    def name(self) -> str:
        return self._name

    def fullname(self) -> str:
        return self._fullname

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
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
                           [mypy.types.deserialize_type(v) for v in data['values']],
                           mypy.types.deserialize_type(data['upper_bound']),
                           data['variance'])


class TypeAliasExpr(Expression):
    """Type alias expression (rvalue)."""

    type = None  # type: mypy.types.Type
    # Simple fallback type for aliases that are invalid in runtime expressions
    # (for example Union, Tuple, Callable).
    fallback = None  # type: mypy.types.Type
    # This type alias is subscripted in a runtime expression like Alias[int](42)
    # (not in a type context like type annotation or base class).
    in_runtime = False  # type: bool

    def __init__(self, type: 'mypy.types.Type', tvars: List[str],
                 fallback: 'mypy.types.Type', in_runtime: bool = False) -> None:
        super().__init__()
        self.type = type
        self.fallback = fallback
        self.in_runtime = in_runtime
        self.tvars = tvars

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_type_alias_expr(self)


class NamedTupleExpr(Expression):
    """Named tuple expression namedtuple(...) or NamedTuple(...)."""

    # The class representation of this named tuple (its tuple_type attribute contains
    # the tuple item types)
    info = None  # type: TypeInfo

    def __init__(self, info: 'TypeInfo') -> None:
        super().__init__()
        self.info = info

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_namedtuple_expr(self)


class TypedDictExpr(Expression):
    """Typed dict expression TypedDict(...)."""

    # The class representation of this typed dict
    info = None  # type: TypeInfo

    def __init__(self, info: 'TypeInfo') -> None:
        super().__init__()
        self.info = info

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_typeddict_expr(self)


class EnumCallExpr(Expression):
    """Named tuple expression Enum('name', 'val1 val2 ...')."""

    # The class representation of this enumerated type
    info = None  # type: TypeInfo
    # The item names (for debugging)
    items = None  # type: List[str]
    values = None  # type: List[Optional[Expression]]

    def __init__(self, info: 'TypeInfo', items: List[str],
                 values: List[Optional[Expression]]) -> None:
        super().__init__()
        self.info = info
        self.items = items
        self.values = values

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_enum_call_expr(self)


class PromoteExpr(Expression):
    """Ducktype class decorator expression _promote(...)."""

    type = None  # type: mypy.types.Type

    def __init__(self, type: 'mypy.types.Type') -> None:
        super().__init__()
        self.type = type

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit__promote_expr(self)


class NewTypeExpr(Expression):
    """NewType expression NewType(...)."""
    name = None  # type: str
    # The base type (the second argument to NewType)
    old_type = None  # type: Optional[mypy.types.Type]
    # The synthesized class representing the new type (inherits old_type)
    info = None  # type: Optional[TypeInfo]

    def __init__(self, name: str, old_type: 'Optional[mypy.types.Type]', line: int) -> None:
        super().__init__()
        self.name = name
        self.old_type = old_type
        self.line = line

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_newtype_expr(self)


class AwaitExpr(Expression):
    """Await expression (await ...)."""

    expr = None  # type: Expression

    def __init__(self, expr: Expression) -> None:
        super().__init__()
        self.expr = expr

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_await_expr(self)


# Constants


class TempNode(Expression):
    """Temporary dummy node used during type checking.

    This node is not present in the original program; it is just an artifact
    of the type checker implementation. It only represents an opaque node with
    some fixed type.
    """

    type = None  # type: mypy.types.Type
    # Is this TempNode used to indicate absence of a right hand side in an annotated assignment?
    # (e.g. for 'x: int' the rvalue is TempNode(AnyType(TypeOfAny.special_form), no_rhs=True))
    no_rhs = False  # type: bool

    def __init__(self, typ: 'mypy.types.Type', no_rhs: bool = False) -> None:
        super().__init__()
        self.type = typ
        self.no_rhs = no_rhs

    def __repr__(self) -> str:
        return 'TempNode(%s)' % str(self.type)

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
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
    # Used to stash the names of the mro classes temporarily between
    # deserialization and fixup. See deserialize() for why.
    _mro_refs = None  # type: Optional[List[str]]

    declared_metaclass = None  # type: Optional[mypy.types.Instance]
    metaclass_type = None  # type: Optional[mypy.types.Instance]

    names = None  # type: SymbolTable      # Names defined directly in this type
    is_abstract = False                    # Does the class have any abstract attributes?
    is_protocol = False                    # Is this a protocol class?
    runtime_protocol = False               # Does this protocol support isinstance checks?
    abstract_attributes = None  # type: List[str]

    # The attributes 'assuming' and 'assuming_proper' represent structural subtype matrices.
    #
    # In languages with structural subtyping, one can keep a global subtype matrix like this:
    #   . A B C .
    #   A 1 0 0
    #   B 1 1 1
    #   C 1 0 1
    #   .
    # where 1 indicates that the type in corresponding row is a subtype of the type
    # in corresponding column. This matrix typically starts filled with all 1's and
    # a typechecker tries to "disprove" every subtyping relation using atomic (or nominal) types.
    # However, we don't want to keep this huge global state. Instead, we keep the subtype
    # information in the form of list of pairs (subtype, supertype) shared by all 'Instance's
    # with given supertype's TypeInfo. When we enter a subtype check we push a pair in this list
    # thus assuming that we started with 1 in corresponding matrix element. Such algorithm allows
    # to treat recursive and mutually recursive protocols and other kinds of complex situations.
    #
    # If concurrent/parallel type checking will be added in future,
    # then there should be one matrix per thread/process to avoid false negatives
    # during the type checking phase.
    assuming = None  # type: List[Tuple[mypy.types.Instance, mypy.types.Instance]]
    assuming_proper = None  # type: List[Tuple[mypy.types.Instance, mypy.types.Instance]]
    # Ditto for temporary 'inferring' stack of recursive constraint inference.
    # It contains Instance's of protocol types that appeared as an argument to
    # constraints.infer_constraints(). We need 'inferring' to avoid infinite recursion for
    # recursive and mutually recursive protocols.
    #
    # We make 'assuming' and 'inferring' attributes here instead of passing they as kwargs,
    # since this would require to pass them in many dozens of calls. In particular,
    # there is a dependency infer_constraint -> is_subtype -> is_callable_subtype ->
    # -> infer_constraints.
    inferring = None  # type: List[mypy.types.Instance]
    # 'inferring' and 'assuming' can't be made sets, since we need to use
    # is_same_type to correctly treat unions.

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

    # Generic type variable names (full names)
    type_vars = None  # type: List[str]

    # Direct base classes.
    bases = None  # type: List[mypy.types.Instance]

    # Another type which this type will be treated as a subtype of,
    # even though it's not a subclass in Python.  The non-standard
    # `@_promote` decorator introduces this, and there are also
    # several builtin examples, in particular `int` -> `float`.
    _promote = None  # type: Optional[mypy.types.Type]

    # Representation of a Tuple[...] base class, if the class has any
    # (e.g., for named tuples). If this is not None, the actual Type
    # object used for this class is not an Instance but a TupleType;
    # the corresponding Instance is set as the fallback type of the
    # tuple type.
    tuple_type = None  # type: Optional[mypy.types.TupleType]

    # Is this a named tuple type?
    is_named_tuple = False

    # If this class is defined by the TypedDict type constructor,
    # then this is not None.
    typeddict_type = None  # type: Optional[mypy.types.TypedDictType]

    # Is this a newtype type?
    is_newtype = False

    # If during analysis of ClassDef associated with this TypeInfo a syntethic
    # type (NamedTuple or TypedDict) was generated, store the corresponding
    # TypeInfo here. (This attribute does not need to be serialized, it is only
    # needed during the semantic passes.)
    replaced = None  # type: TypeInfo

    # This is a dictionary that will be serialized and un-serialized as is.
    # It is useful for plugins to add their data to save in the cache.
    metadata = None  # type: Dict[str, JsonDict]

    FLAGS = [
        'is_abstract', 'is_enum', 'fallback_to_any', 'is_named_tuple',
        'is_newtype', 'is_protocol', 'runtime_protocol'
    ]

    def __init__(self, names: 'SymbolTable', defn: ClassDef, module_name: str) -> None:
        """Initialize a TypeInfo."""
        super().__init__()
        self.names = names
        self.defn = defn
        self.module_name = module_name
        self.type_vars = []
        self.bases = []
        # Leave self.mro uninitialized until we compute it for real,
        # so we don't accidentally try to use it prematurely.
        self._fullname = defn.fullname
        self.is_abstract = False
        self.abstract_attributes = []
        self.assuming = []
        self.assuming_proper = []
        self.inferring = []
        self.add_type_vars()
        self.metadata = {}

    def add_type_vars(self) -> None:
        if self.defn.type_vars:
            for vd in self.defn.type_vars:
                self.type_vars.append(vd.fullname)

    def name(self) -> str:
        """Short name."""
        return self.defn.name

    def fullname(self) -> str:
        return self._fullname

    def is_generic(self) -> bool:
        """Is the type generic (i.e. does it have type variables)?"""
        return len(self.type_vars) > 0

    def get(self, name: str) -> 'Optional[SymbolTableNode]':
        if self.mro is None:  # Might be because of a previous error.
            return None

        for cls in self.mro:
            n = cls.names.get(name)
            if n:
                return n
        return None

    def get_containing_type_info(self, name: str) -> 'Optional[TypeInfo]':
        for cls in self.mro:
            if name in cls.names:
                return cls
        return None

    @property
    def protocol_members(self) -> List[str]:
        # Protocol members are names of all attributes/methods defined in a protocol
        # and in all its supertypes (except for 'object').
        members = set()  # type: Set[str]
        assert self.mro, "This property can be only acessed after MRO is (re-)calculated"
        for base in self.mro[:-1]:  # we skip "object" since everyone implements it
            if base.is_protocol:
                for name in base.names:
                    members.add(name)
        return sorted(list(members))

    def __getitem__(self, name: str) -> 'SymbolTableNode':
        n = self.get(name)
        if n:
            return n
        else:
            raise KeyError(name)

    def __repr__(self) -> str:
        return '<TypeInfo %s>' % self.fullname()

    def has_readable_member(self, name: str) -> bool:
        return self.get(name) is not None

    def get_method(self, name: str) -> Optional[FuncBase]:
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

    def calculate_metaclass_type(self) -> 'Optional[mypy.types.Instance]':
        declared = self.declared_metaclass
        if declared is not None and not declared.type.has_base('builtins.type'):
            return declared
        if self._fullname == 'builtins.type':
            return mypy.types.Instance(self, [])
        candidates = [s.declared_metaclass
                      for s in self.mro
                      if s.declared_metaclass is not None
                      and s.declared_metaclass.type is not None]
        for c in candidates:
            if c.type.mro is None:
                continue
            if all(other.type in c.type.mro for other in candidates):
                return c
        return None

    def is_metaclass(self) -> bool:
        return (self.has_base('builtins.type') or self.fullname() == 'abc.ABCMeta' or
                self.fallback_to_any)

    def has_base(self, fullname: str) -> bool:
        """Return True if type has a base type with the specified name.

        This can be either via extension or via implementation.
        """
        if self.mro:
            for cls in self.mro:
                if cls.fullname() == fullname:
                    return True
        return False

    def direct_base_classes(self) -> 'List[TypeInfo]':
        """Return a direct base classes.

        Omit base classes of other base classes.
        """
        return [base.type for base in self.bases]

    def __str__(self) -> str:
        """Return a string representation of the type.

        This includes the most important information about the type.
        """
        return self.dump()

    def dump(self,
             str_conv: 'Optional[mypy.strconv.StrConv]' = None,
             type_str_conv: 'Optional[mypy.types.TypeStrVisitor]' = None) -> str:
        """Return a string dump of the contents of the TypeInfo."""
        if not str_conv:
            str_conv = mypy.strconv.StrConv()
        base = ''  # type: str

        def type_str(typ: 'mypy.types.Type') -> str:
            if type_str_conv:
                return typ.accept(type_str_conv)
            return str(typ)

        head = 'TypeInfo' + str_conv.format_id(self)
        if self.bases:
            base = 'Bases({})'.format(', '.join(type_str(base)
                                                for base in self.bases))
        mro = 'Mro({})'.format(', '.join(item.fullname() + str_conv.format_id(item)
                                         for item in self.mro))
        names = []
        for name in sorted(self.names):
            description = name + str_conv.format_id(self.names[name].node)
            node = self.names[name].node
            if isinstance(node, Var) and node.type:
                description += ' ({})'.format(type_str(node.type))
            names.append(description)
        items = [
            'Name({})'.format(self.fullname()),
            base,
            mro,
            ('Names', names),
        ]
        if self.declared_metaclass:
            items.append('DeclaredMetaclass({})'.format(type_str(self.declared_metaclass)))
        if self.metaclass_type:
            items.append('MetaclassType({})'.format(type_str(self.metaclass_type)))
        return mypy.strconv.dump_tagged(
            items,
            head,
            str_conv=str_conv)

    def serialize(self) -> JsonDict:
        # NOTE: This is where all ClassDefs originate, so there shouldn't be duplicates.
        data = {'.class': 'TypeInfo',
                'module_name': self.module_name,
                'fullname': self.fullname(),
                'names': self.names.serialize(self.fullname()),
                'defn': self.defn.serialize(),
                'abstract_attributes': self.abstract_attributes,
                'type_vars': self.type_vars,
                'bases': [b.serialize() for b in self.bases],
                'mro': [c.fullname() for c in self.mro],
                '_promote': None if self._promote is None else self._promote.serialize(),
                'declared_metaclass': (None if self.declared_metaclass is None
                                       else self.declared_metaclass.serialize()),
                'metaclass_type':
                    None if self.metaclass_type is None else self.metaclass_type.serialize(),
                'tuple_type': None if self.tuple_type is None else self.tuple_type.serialize(),
                'typeddict_type':
                    None if self.typeddict_type is None else self.typeddict_type.serialize(),
                'flags': get_flags(self, TypeInfo.FLAGS),
                'metadata': self.metadata,
                }
        return data

    @classmethod
    def deserialize(cls, data: JsonDict) -> 'TypeInfo':
        names = SymbolTable.deserialize(data['names'])
        defn = ClassDef.deserialize(data['defn'])
        module_name = data['module_name']
        ti = TypeInfo(names, defn, module_name)
        ti._fullname = data['fullname']
        # TODO: Is there a reason to reconstruct ti.subtypes?
        ti.abstract_attributes = data['abstract_attributes']
        ti.type_vars = data['type_vars']
        ti.bases = [mypy.types.Instance.deserialize(b) for b in data['bases']]
        ti._promote = (None if data['_promote'] is None
                       else mypy.types.deserialize_type(data['_promote']))
        ti.declared_metaclass = (None if data['declared_metaclass'] is None
                                 else mypy.types.Instance.deserialize(data['declared_metaclass']))
        ti.metaclass_type = (None if data['metaclass_type'] is None
                             else mypy.types.Instance.deserialize(data['metaclass_type']))
        # NOTE: ti.mro will be set in the fixup phase based on these
        # names.  The reason we need to store the mro instead of just
        # recomputing it from base classes has to do with a subtle
        # point about fine-grained incremental: the cache files might
        # not be loaded until after a class in the mro has changed its
        # bases, which causes the mro to change. If we recomputed our
        # mro, we would compute the *new* mro, which leaves us with no
        # way to detact that the mro has changed! Thus we need to make
        # sure to load the original mro so that once the class is
        # rechecked, it can tell that the mro has changed.
        ti._mro_refs = data['mro']
        ti.tuple_type = (None if data['tuple_type'] is None
                         else mypy.types.TupleType.deserialize(data['tuple_type']))
        ti.typeddict_type = (None if data['typeddict_type'] is None
                            else mypy.types.TypedDictType.deserialize(data['typeddict_type']))
        ti.metadata = data['metadata']
        set_flags(ti, data['flags'])
        return ti


class FakeInfo(TypeInfo):
    # types.py defines a single instance of this class, called types.NOT_READY.
    # This instance is used as a temporary placeholder in the process of de-serialization
    # of 'Instance' types. The de-serialization happens in two steps: In the first step,
    # Instance.type is set to NOT_READY. In the second step (in fixup.py) it is replaced by
    # an actual TypeInfo. If you see the assertion error below, then most probably something
    # went wrong during the second step and an 'Instance' that raised this error was not fixed.
    # Note:
    # 'None' is not used as a dummy value for two reasons:
    # 1. This will require around 80-100 asserts to make 'mypy --strict-optional mypy'
    #    pass cleanly.
    # 2. If NOT_READY value is accidentally used somewhere, it will be obvious where the value
    #    is from, whereas a 'None' value could come from anywhere.
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def __getattribute__(self, attr: str) -> None:
        raise AssertionError('De-serialization failure: TypeInfo not fixed')


class SymbolTableNode:
    """Description of a name binding in a symbol table.

    These are only used as values in module (global), function (local)
    and class symbol tables (see SymbolTable). The name that is bound is
    the key in SymbolTable.

    Symbol tables don't contain direct references to AST nodes primarily
    because there can be multiple symbol table references to a single
    AST node (due to imports and aliases), and different references can
    behave differently. This class describes the unique properties of
    each reference.

    The most fundamental attributes are 'kind' and 'node'.  The 'node'
    attribute defines the AST node that the name refers to.

    For many bindings, including those targeting variables, functions
    and classes, the kind is one of LDEF, GDEF or MDEF, depending on the
    scope of the definition. These three kinds can usually be used
    interchangeably and the difference between local, global and class
    scopes is mostly descriptive, with no semantic significance.
    However, some tools that consume mypy ASTs may care about these so
    they should be correct.

    A few definitions get special kinds, including type variables (TVAR),
    imported modules and module aliases (MODULE_REF), and type aliases
    (TYPE_ALIAS).

    Type aliases are very special and have additional attributes that
    are only used for them ('type_override', 'alias_tvars' at least).

    Attributes:
        kind: Kind of node. Possible values:
               - LDEF: local definition
               - GDEF: global (module-level) definition
               - MDEF: class member definition
               - TVAR: TypeVar(...) definition in any scope
               - MODULE_REF: reference to a module
               - TYPE_ALIAS: type alias
               - UNBOUND_IMPORTED: temporary kind for imported names (we
                 don't know the final kind yet)
        node: AST node of definition (among others, this can be
            FuncDef/Var/TypeInfo/TypeVarExpr/MypyFile, or None for a bound
            type variable or a cross_ref that hasn't been fixed up yet).
        type_override: If this not None, override the type of the 'node'
            attribute. This is only used for type aliases.
        alias_tvars: For generic aliases this stores the (qualified) names
            of type variables. (For example see
            testGenericAliasWithTypeVarsFromDifferentModules.)
        module_public: If False, this name won't be imported via
            'from <module> import *'. This has no effect on names within
            classes.
        module_hidden: If True, the name will be never exported (needed for
            stub files)
        cross_ref: For deserialized MODULE_REF nodes, the referenced module
            name; for other nodes, optionally the name of the referenced object.
        normalized: Used to distinguish between 'typing.List' and
            'builtins.list'.  This is True when the former has been normalized
            to the latter, and it allow us to reject 'list[str]' and similar.
        implicit: Was this defined by assignment to self attribute?
        is_aliasing: Is this node refers to other node via node aliasing?
            (This is currently used for simple aliases like `A = int` instead
            of .type_override)
        alias_name: TODO
    """

    __slots__ = ('kind',
                 'node',
                 'type_override',
                 'alias_tvars',
                 'module_public',
                 'module_hidden',
                 'cross_ref',
                 'normalized',
                 'implicit',
                 'is_aliasing',
                 'alias_name',
                 )

    # TODO: This is a mess. Refactor!
    # TODO: Better describe how type aliases work.

    def __init__(self,
                 kind: int,
                 node: Optional[SymbolNode],
                 typ: 'Optional[mypy.types.Type]' = None,
                 module_public: bool = True,
                 normalized: bool = False,
                 alias_tvars: Optional[List[str]] = None,
                 implicit: bool = False,
                 module_hidden: bool = False) -> None:
        self.kind = kind
        self.node = node
        self.type_override = typ
        self.module_public = module_public
        self.normalized = normalized
        self.alias_tvars = alias_tvars
        self.implicit = implicit
        self.module_hidden = module_hidden
        self.cross_ref = None  # type: Optional[str]
        self.is_aliasing = False
        self.alias_name = None  # type: Optional[str]

    @property
    def fullname(self) -> Optional[str]:
        if self.node is not None:
            return self.node.fullname()
        else:
            return None

    @property
    def type(self) -> 'Optional[mypy.types.Type]':
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

    def copy(self) -> 'SymbolTableNode':
        new = SymbolTableNode(self.kind,
                              self.node,
                              self.type_override,
                              self.module_public,
                              self.normalized,
                              self.alias_tvars,
                              self.implicit,
                              self.module_hidden)
        new.cross_ref = self.cross_ref
        return new

    def __str__(self) -> str:
        s = '{}/{}'.format(node_kinds[self.kind], short_type(self.node))
        if isinstance(self.node, SymbolNode):
            s += ' ({})'.format(self.node.fullname())
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
        if self.module_hidden:
            data['module_hidden'] = True
        if not self.module_public:
            data['module_public'] = False
        if self.normalized:
            data['normalized'] = True
        if self.implicit:
            data['implicit'] = True
        if self.kind == MODULE_REF:
            assert self.node is not None, "Missing module cross ref in %s for %s" % (prefix, name)
            data['cross_ref'] = self.node.fullname()
        else:
            if self.node is not None:
                if prefix is not None:
                    fullname = self.node.fullname()
                    if (fullname is not None and '.' in fullname and
                            fullname != prefix + '.' + name):
                        data['cross_ref'] = fullname
                        return data
                data['node'] = self.node.serialize()
            if self.type_override is not None:
                data['type_override'] = self.type_override.serialize()
                data['alias_tvars'] = self.alias_tvars
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
                typ = mypy.types.deserialize_type(data['type_override'])
            stnode = SymbolTableNode(kind, node, typ=typ)
            if 'alias_tvars' in data:
                stnode.alias_tvars = data['alias_tvars']
        if 'module_hidden' in data:
            stnode.module_hidden = data['module_hidden']
        if 'module_public' in data:
            stnode.module_public = data['module_public']
        if 'normalized' in data:
            stnode.normalized = data['normalized']
        if 'implicit' in data:
            stnode.implicit = data['implicit']
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

    def copy(self) -> 'SymbolTable':
        return SymbolTable((key, node.copy())
                           for key, node in self.items())

    def serialize(self, fullname: str) -> JsonDict:
        data = {'.class': 'SymbolTable'}  # type: JsonDict
        for key, value in self.items():
            # Skip __builtins__: it's a reference to the builtins
            # module that gets added to every module by
            # SemanticAnalyzerPass2.visit_file(), but it shouldn't be
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


def get_flags(node: Node, names: List[str]) -> List[str]:
    return [name for name in names if getattr(node, name)]


def set_flags(node: Node, flags: List[str]) -> None:
    for name in flags:
        setattr(node, name, True)


def get_member_expr_fullname(expr: MemberExpr) -> Optional[str]:
    """Return the qualified name representation of a member expression.

    Return a string of form foo.bar, foo.bar.baz, or similar, or None if the
    argument cannot be represented in this form.
    """
    initial = None  # type: Optional[str]
    if isinstance(expr.expr, NameExpr):
        initial = expr.expr.name
    elif isinstance(expr.expr, MemberExpr):
        initial = get_member_expr_fullname(expr.expr)
    else:
        return None
    return '{}.{}'.format(initial, expr.name)


deserialize_map = {
    key: obj.deserialize  # type: ignore
    for key, obj in globals().items()
    if isinstance(obj, type) and issubclass(obj, SymbolNode) and obj is not SymbolNode
}


def check_arg_kinds(arg_kinds: List[int], nodes: List[T], fail: Callable[[str, T], None]) -> None:
    is_var_arg = False
    is_kw_arg = False
    seen_named = False
    seen_opt = False
    for kind, node in zip(arg_kinds, nodes):
        if kind == ARG_POS:
            if is_var_arg or is_kw_arg or seen_named or seen_opt:
                fail("Required positional args may not appear "
                     "after default, named or var args",
                     node)
                break
        elif kind == ARG_OPT:
            if is_var_arg or is_kw_arg or seen_named:
                fail("Positional default args may not appear after named or var args", node)
                break
            seen_opt = True
        elif kind == ARG_STAR:
            if is_var_arg or is_kw_arg or seen_named:
                fail("Var args may not appear after named or var args", node)
                break
            is_var_arg = True
        elif kind == ARG_NAMED or kind == ARG_NAMED_OPT:
            seen_named = True
            if is_kw_arg:
                fail("A **kwargs argument must be the last argument", node)
                break
        elif kind == ARG_STAR2:
            if is_kw_arg:
                fail("You may only have one **kwargs argument", node)
                break
            is_kw_arg = True


def check_arg_names(names: Sequence[Optional[str]], nodes: List[T], fail: Callable[[str, T], None],
                    description: str = 'function definition') -> None:
    seen_names = set()  # type: Set[Optional[str]]
    for name, node in zip(names, nodes):
        if name is not None and name in seen_names:
            fail("Duplicate argument '{}' in {}".format(name, description), node)
            break
        seen_names.add(name)


def is_class_var(expr: NameExpr) -> bool:
    """Return whether the expression is ClassVar[...]"""
    if isinstance(expr.node, Var):
        return expr.node.is_classvar
    return False
