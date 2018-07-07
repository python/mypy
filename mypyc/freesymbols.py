from typing import Dict, List, Set

from mypy.nodes import FuncDef, NameExpr, SymbolNode, Var
from mypy.traverser import TraverserVisitor


class FreeVariablesVisitor(TraverserVisitor):
    """Class used to visit nested functions and determine free symbols."""
    def __init__(self) -> None:
        super().__init__()
        # Mapping from FuncDef instances to sets of variables. The FuncDef instances are where
        # these variables were first declared, and these variables are free in any functions that
        # are nested within the FuncDef from which they are mapped.
        self.free_variables = {}  # type: Dict[FuncDef, Set[SymbolNode]]
        # Intermediate data structure used to map SymbolNode instances to the FuncDef in which they
        # were first visited.
        self.symbols_to_fdefs = {}  # type: Dict[SymbolNode, FuncDef]
        # Stack representing the function call stack.
        self.fdefs = []  # type: List[FuncDef]

    def visit_func_def(self, fdef: FuncDef) -> None:
        self.fdefs.append(fdef)
        self.visit_func(fdef)
        self.fdefs.pop()

    def visit_var(self, var: Var) -> None:
        self.visit_symbol_node(var)

    def visit_symbol_node(self, symbol: SymbolNode) -> None:
        if not self.fdefs:
            # If the list of FuncDefs is empty, then we are not inside of a function and hence do
            # not need to do anything regarding free variables.
            return

        if symbol in self.symbols_to_fdefs and self.symbols_to_fdefs[symbol] != self.fdefs[-1]:
            # If the SymbolNode instance has already been visited before, and it was declared in a
            # FuncDef outside of the current FuncDef that is being visted, then it is a free symbol
            # because it is being visited again.
            self.add_free_variable(symbol)
        else:
            # Otherwise, this is the first time the SymbolNode is being visited. We map the
            # SymbolNode to the current FuncDef being visited to note where it was first visited.
            self.symbols_to_fdefs[symbol] = self.fdefs[-1]

    def visit_name_expr(self, expr: NameExpr) -> None:
        if isinstance(expr.node, (Var, FuncDef)):
            self.visit_symbol_node(expr.node)

    def add_free_variable(self, symbol: SymbolNode) -> None:
        # Get the FuncDef instance where the free symbol was first declared, and map that FuncDef
        # to the SymbolNode representing the free symbol.
        fdef = self.symbols_to_fdefs[symbol]
        self.free_variables.setdefault(fdef, set()).add(symbol)
