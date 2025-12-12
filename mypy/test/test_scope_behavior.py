from mypy.nodes import FuncDef, SymbolTable, TypeInfo
from mypy.scope import Scope


def test_scope_module_and_function_behavior() -> None:
    scope = Scope()
    with scope.module_scope("mod1"):
        assert scope.current_module_id() == "mod1"
        # simulate function
        fake_func = FuncDef("f", None, None, None, None)
        with scope.function_scope(fake_func):
            assert "f" in scope.current_full_target()
            # simulate class inside function
            fake_class = TypeInfo(SymbolTable(), "C", None)
            with scope.class_scope(fake_class):
                assert "C" in scope.current_full_target()
        # leaving function restores module
        assert scope.current_full_target() == "mod1"
