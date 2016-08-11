"""Code to extract the public interface of a given module on a best-effort basis.

The public interface of a module consists of anything that somebody importing
a module could conceivably access. The public interface consists of:

- Top-level imports
- Top-level constants
- Top-level classes, their attributes, internal class definitions, and methods
- Top-level functions

Things which are currently not handled very well or are not verified to work
correctly in all cases:

- Respecting the '__all__' variable
- More accurate import handling/nested imports
- Decorators
- Complex assignment statements
- Constant-level expressions
- Repeated functions/redefining thing in tricky ways
- Python version checks
"""

from typing import Dict, List, Optional, Union
from abc import ABCMeta, abstractmethod
import base64
from contextlib import contextmanager
import hashlib

from mypy.visitor import NodeVisitor
from mypy.nodes import (MypyFile, Node, Import, ImportFrom, ImportAll, ImportBase,
                        FuncDef, OverloadedFuncDef, Decorator, ClassDef, Block,
                        AssignmentStmt, WhileStmt, ForStmt, IfStmt, TryStmt, WithStmt,
                        Expression, NameExpr, ListExpr, TupleExpr, StarExpr,
                        )
from mypy.types import Type


class SymbolSignature:
    """Represents the "signature" of any kind of publicly accessible symbol.

    Any change to a signature means that the the types for that symbol
    have changed in some way."""

    def __init__(self, fullname: str) -> None:
        self._fullname = fullname

    def fullname(self) -> str:
        """The fully qualified name of this symbol."""
        return self._fullname

    @abstractmethod
    def signature(self) -> str:
        """The 'signature' of this symbol.

        The signature should ideally correspond to the type signature of this symbol,
        but any distinctly unique string will work. For example, if it's not possible
        to compute the type of a certain expression, you could set the signature to the
        serialized form the the expression itself, if necessary."""
        raise NotImplementedError()

    def kind(self) -> str:
        """Represents whether this symbol is a constant, function, class, etc."""
        return self.__class__.__name__.replace('Signature', '')

    def __str__(self) -> str:
        return '{} ({}): {}'.format(self.fullname(), self.kind(), self.signature())


class FunctionSignature(SymbolSignature):
    def __init__(self, fullname: str, type: Type) -> None:
        super().__init__(fullname)
        self.type = type
        self._signature = str(self.type)

    def signature(self) -> str:
        return self._signature


class OverloadedFunctionSignature(SymbolSignature):
    def __init__(self, fullname: str, types: List[Type]) -> None:
        super().__init__(fullname)
        self.types = types
        self._signature = '; '.join(map(str, self.types))

    def signature(self) -> str:
        return self._signature


class ClassSignature(SymbolSignature):
    def __init__(self, fullname: str, classname: str, base_classes: List[str]) -> None:
        super().__init__(fullname)
        self.classname = classname
        self.base_classes = base_classes
        if len(base_classes) == 0:
            self._signature = classname
        else:
            self._signature = '{} (extends {})'.format(classname, ', '.join(base_classes))

    def signature(self) -> str:
        return self._signature


class ExpressionSignature(SymbolSignature):
    def __init__(self, fullname: str, signature: Union[Type, str]) -> None:
        super().__init__(fullname)
        self.type = None  # type: Optional[Type]

        if isinstance(signature, Type):
            self.type = signature
            self._signature = str(signature)
        elif isinstance(signature, str):
            self._signature = signature
        else:
            raise AssertionError("Encountered unknown signature type: {}".format(type(signature)))

    def signature(self) -> str:
        return self._signature


class ModuleInterface:
    """Represents the public 'interface' of a given module."""
    def __init__(self) -> None:
        # TODO: Represent the imports in a cleaner way.
        self.fullname = ''
        self.imports = []  # type: List[ImportBase]
        self.symbols = {}  # type: Dict[str, SymbolSignature]

    def add_symbol(self, symbol: SymbolSignature) -> None:
        self.symbols[symbol.fullname()] = symbol

    def __str__(self) -> str:
        output = ['Interface for ' + self.fullname + ':']
        output.extend('    ' + str(imp) for imp in self.imports)
        output.extend('    {} ({})\n        {}'.format(
            sym.fullname(), sym.kind(), sym.signature()) for sym in self.symbols.values())
        return '\n'.join(output)

    def compute_hash(self) -> str:
        """Computes the hash of all stored imports and symbols.

        The order in which the imports are added is significant;
        the order in which symbols are added is ignored."""
        hash_obj = hashlib.md5(self.fullname.encode('utf-8'))
        for imp in self.imports:
            hash_obj.update(str(imp).encode('utf-8'))
        for key in sorted(self.symbols.keys()):
            hash_obj.update(str(self.symbols[key]).encode('utf-8'))
        return base64.b64encode(hash_obj.digest()).decode('utf-8')


def extract_interface(module: MypyFile) -> ModuleInterface:
    """Returns a best-effort approximation of the public interface of the given MypyFile."""
    interface = ModuleInterface()
    extractor = InterfaceExtractor(interface)
    extractor.visit_mypy_file(module)
    return interface


class InterfaceExtractor(NodeVisitor[None]):
    def __init__(self, interface: ModuleInterface) -> None:
        self.interface = interface
        self._scope_stack = []  # type: List[str]
        self._qualname = ''

    # Helpers

    def _visit(self, *nodes: Node, scope: Optional[str] = None) -> None:
        """Visits the given node(s).

        If `scope` is a string, assumes all visited nodes live within that
        particular scope."""
        if scope is not None:
            self._scope_stack.append(scope)
            self._qualname = '.'.join(self._scope_stack) + '.'

        for node in nodes:
            if node is not None:
                node.accept(self)

        if scope is not None:
            self._scope_stack.pop()
            self._qualname = '.'.join(self._scope_stack) + '.'

    def _qualified_name(self, name: str) -> str:
        """Returns the fully qualified name of the given symbol based on the current sccope."""
        assert name is not None
        return self._qualname + name

    def _flatten_node(self, node: Node) -> str:
        """Returns the string representation of a node as a one-line string."""
        return ' '.join(line.strip() for line in str(node).split('\n'))

    # Module structure

    def visit_mypy_file(self, module: MypyFile) -> None:
        self.interface.fullname = module.fullname()
        self._visit(*module.defs, scope=module.fullname())

    # TODO: Store these imports in a more useful way.

    def visit_import(self, imp: Import) -> None:
        self.interface.imports.append(imp)

    def visit_import_from(self, imp: ImportFrom) -> None:
        self.interface.imports.append(imp)

    def visit_import_all(self, imp: ImportAll) -> None:
        self.interface.imports.append(imp)

    # Definitions

    def visit_func_def(self, func: FuncDef) -> None:
        if func.fullname() is not None:
            name = func.fullname()
        else:
            name = self._qualified_name(func.name())

        self.interface.add_symbol(FunctionSignature(name, func.type))

    def visit_overloaded_func_def(self,
                                  func: OverloadedFuncDef) -> None:
        if func.fullname() is not None:
            name = func.fullname()
        else:
            name = self._qualified_name(func.name())

        types = [defn.func.type for defn in func.items]
        self.interface.add_symbol(OverloadedFunctionSignature(name, types))

    def visit_class_def(self, cls: ClassDef) -> None:
        info = cls.info
        bases = []
        for base in cls.base_type_exprs:
            if isinstance(base, NameExpr):
                bases.append(base.name)
            else:
                bases.append(self._flatten_node(base))
        self.interface.add_symbol(ClassSignature(info.fullname(), info.name(), bases))
        self._visit(cls.defs, scope=info.name())

    def visit_decorator(self, decorator: Decorator) -> None:
        # TODO: Do I need decorator.var and decorator.is_overload?
        self._visit(decorator.func)

    # Statements

    def visit_block(self, block: Block) -> None:
        if not block.is_unreachable:
            self._visit(*block.body)

    def _handle_seq_assignment(self, lvalue: Expression, signature: Union[Type, str]) -> None:
        if isinstance(lvalue, NameExpr):
            name = self._qualified_name(lvalue.name)
            self.interface.add_symbol(ExpressionSignature(name, signature))
        elif isinstance(lvalue, (ListExpr, TupleExpr)):
            # TODO: This is a cop-out. Rather then trying to extract the type
            # signatures of each individual item in the tuple or list, I'm just
            # going to give them all the same signature as the overall expression.
            # After all, the goal of this visitor is to obtain relatively unique
            # signatures, not to obtain accurate type information.
            for item in lvalue.items:
                self._handle_seq_assignment(item, signature)
        elif isinstance(lvalue, StarExpr):
            self._handle_seq_assignment(lvalue.expr, signature)
        else:
            # Assume all other kinds of expressions are either valid things like
            # MemberExpr or IndexExpr, or invalid things that'll be caught later
            # by the syntax checker.
            pass

    def visit_assignment_stmt(self, stmt: AssignmentStmt) -> None:
        # If we cannot deduce the type signature of this variable, resort
        # to using the serialized form of the entire expression.
        signature = None  # type: Union[Type, str]
        if stmt.type is not None:
            signature = stmt.type
        else:
            signature = self._flatten_node(stmt.rvalue)

        for lvalue in stmt.lvalues:
            self._handle_seq_assignment(lvalue, signature)

    def visit_while_stmt(self, stmt: WhileStmt) -> None:
        # Hopefully nobody will try defining something within a top-level or
        # class-level while statement, but I suppose it could happen.
        self._visit(stmt.body)
        self._visit(stmt.else_body)

    def visit_for_stmt(self, stmt: ForStmt) -> None:
        # Similar thing here.
        self._visit(stmt.body)
        self._visit(stmt.else_body)

    def visit_if_stmt(self, stmt: IfStmt) -> None:
        # TODO: Make sure we respect Python version checks
        self._visit(*stmt.body)
        self._visit(stmt.else_body)

    def visit_try_stmt(self, stmt: TryStmt) -> None:
        self._visit(stmt.body)
        self._visit(*stmt.handlers)  # "except" clauses
        self._visit(stmt.else_body)
        self._visit(stmt.finally_body)

    def visit_with_stmt(self, stmt: WithStmt) -> None:
        self._visit(stmt.body)
