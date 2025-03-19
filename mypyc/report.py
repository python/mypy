from mypy.build import BuildResult
from mypyc.ir.module_ir import ModuleIR


def generate_report(result: BuildResult, modules: dict[str, ModuleIR]) -> None:
    for mod, mod_ir in modules.items():
        print(">>", mod, result.graph[mod].path)
