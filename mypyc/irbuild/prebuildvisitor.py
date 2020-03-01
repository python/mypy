from typing import Dict, List, Set

from mypy.nodes import (
    Decorator, Expression, FuncDef, FuncItem, LambdaExpr, NameExpr, SymbolNode, Var, MemberExpr
)
from mypy.traverser import TraverserVisitor


class PreBuildVisitor(TraverserVisitor):
    """
    Class used to visit a mypy file before building the IR for that program. This is done as a
    first pass so that nested functions, encapsulating functions, lambda functions, decorated
    functions, and free variables can be determined before instantiating the IRBuilder.
    """
    def __init__(self) -> None:
        super().__init__()
        # Mapping from FuncItem instances to sets of variables. The FuncItem instances are where
        # these variables were first declared, and these variables are free in any functions that
        # are nested within the FuncItem from which they are mapped.
        self.free_variables = {}  # type: Dict[FuncItem, Set[SymbolNode]]
        # Intermediate data structure used to map SymbolNode instances to the FuncDef in which they
        # were first visited.
        self.symbols_to_funcs = {}  # type: Dict[SymbolNode, FuncItem]
        # Stack representing the function call stack.
        self.funcs = []  # type: List[FuncItem]
        # The set of property setters
        self.prop_setters = set()  # type: Set[FuncDef]
        # A map from any function that contains nested functions to
        # a set of all the functions that are nested within it.
        self.encapsulating_funcs = {}  # type: Dict[FuncItem, List[FuncItem]]
        # A map from a nested func to it's parent/encapsulating func.
        self.nested_funcs = {}  # type: Dict[FuncItem, FuncItem]
        self.funcs_to_decorators = {}  # type: Dict[FuncDef, List[Expression]]

    def add_free_variable(self, symbol: SymbolNode) -> None:
        # Get the FuncItem instance where the free symbol was first declared, and map that FuncItem
        # to the SymbolNode representing the free symbol.
        func = self.symbols_to_funcs[symbol]
        self.free_variables.setdefault(func, set()).add(symbol)

    def visit_decorator(self, dec: Decorator) -> None:
        if dec.decorators:
            # Only add the function being decorated if there exist decorators in the decorator
            # list. Note that meaningful decorators (@property, @abstractmethod) are removed from
            # this list by mypy, but functions decorated by those decorators (in addition to
            # property setters) do not need to be added to the set of decorated functions for
            # the IRBuilder, because they are handled in a special way.
            if isinstance(dec.decorators[0], MemberExpr) and dec.decorators[0].name == 'setter':
                self.prop_setters.add(dec.func)
            else:
                self.funcs_to_decorators[dec.func] = dec.decorators
        super().visit_decorator(dec)

    def visit_func(self, func: FuncItem) -> None:
        # If there were already functions or lambda expressions defined in the function stack, then
        # note the previous FuncItem as containing a nested function and the current FuncItem as
        # being a nested function.
        if self.funcs:
            # Add the new func to the set of nested funcs within the func at top of the func stack.
            self.encapsulating_funcs.setdefault(self.funcs[-1], []).append(func)
            # Add the func at top of the func stack as the parent of new func.
            self.nested_funcs[func] = self.funcs[-1]

        self.funcs.append(func)
        super().visit_func(func)
        self.funcs.pop()

    def visit_func_def(self, fdef: FuncItem) -> None:
        self.visit_func(fdef)

    def visit_lambda_expr(self, expr: LambdaExpr) -> None:
        self.visit_func(expr)

    def visit_name_expr(self, expr: NameExpr) -> None:
        if isinstance(expr.node, (Var, FuncDef)):
            self.visit_symbol_node(expr.node)

    # Check if child is contained within fdef (possibly indirectly within
    # multiple nested functions).
    def is_parent(self, fitem: FuncItem, child: FuncItem) -> bool:
        if child in self.nested_funcs:
            parent = self.nested_funcs[child]
            if parent == fitem:
                return True
            return self.is_parent(fitem, parent)
        return False

    def visit_symbol_node(self, symbol: SymbolNode) -> None:
        if not self.funcs:
            # If the list of FuncDefs is empty, then we are not inside of a function and hence do
            # not need to do anything regarding free variables.
            return

        if symbol in self.symbols_to_funcs:
            orig_func = self.symbols_to_funcs[symbol]
            if self.is_parent(self.funcs[-1], orig_func):
                # If the function in which the symbol was originally seen is nested
                # within the function currently being visited, fix the free_variable
                # and symbol_to_funcs dictionaries.
                self.symbols_to_funcs[symbol] = self.funcs[-1]
                self.free_variables.setdefault(self.funcs[-1], set()).add(symbol)

            elif self.is_parent(orig_func, self.funcs[-1]):
                # If the SymbolNode instance has already been visited before,
                # and it was declared in a FuncDef not nested within the current
                # FuncDef being visited, then it is a free symbol because it is
                # being visited again.
                self.add_free_variable(symbol)

        else:
            # Otherwise, this is the first time the SymbolNode is being visited. We map the
            # SymbolNode to the current FuncDef being visited to note where it was first visited.
            self.symbols_to_funcs[symbol] = self.funcs[-1]

    def visit_var(self, var: Var) -> None:
        self.visit_symbol_node(var)
