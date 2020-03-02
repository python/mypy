"""Transform a mypy AST to the IR form (Intermediate Representation).

For example, consider a function like this:

   def f(x: int) -> int:
       return x * 2 + 1

It would be translated to something that conceptually looks like this:

   r0 = 2
   r1 = 1
   r2 = x * r0 :: int
   r3 = r2 + r1 :: int
   return r3

The IR is implemented in mypyc.ops.

For the core of the implementation, look at build_ir() below,
mypyc.irbuild.builder, and mypyc.irbuild.visitor.
"""

from collections import OrderedDict
from typing import List, Dict, Callable, Any, TypeVar, cast

from mypy.nodes import MypyFile, Expression
from mypy.types import Type
from mypy.state import strict_optional_set
from mypy.build import Graph

from mypyc.errors import Errors
from mypyc.options import CompilerOptions
from mypyc.ir.module_ir import ModuleIR, ModuleIRs
from mypyc.irbuild.prebuildvisitor import PreBuildVisitor
from mypyc.irbuild.vtable import compute_vtable
from mypyc.irbuild.prepare import build_type_map
from mypyc.irbuild.builder import IRBuilder
from mypyc.irbuild.visitor import IRBuilderVisitor
from mypyc.irbuild.mapper import Mapper


# The stubs for callable contextmanagers are busted so cast it to the
# right type...
F = TypeVar('F', bound=Callable[..., Any])
strict_optional_dec = cast(Callable[[F], F], strict_optional_set(True))


@strict_optional_dec  # Turn on strict optional for any type manipulations we do
def build_ir(modules: List[MypyFile],
             graph: Graph,
             types: Dict[Expression, Type],
             mapper: 'Mapper',
             options: CompilerOptions,
             errors: Errors) -> ModuleIRs:

    build_type_map(mapper, modules, graph, types, options, errors)

    result = OrderedDict()  # type: ModuleIRs

    # Generate IR for all modules.
    class_irs = []

    for module in modules:
        # First pass to determine free symbols.
        pbv = PreBuildVisitor()
        module.accept(pbv)

        # Construct and configure builder objects (cyclic runtime dependency).
        visitor = IRBuilderVisitor()
        builder = IRBuilder(
            module.fullname, types, graph, errors, mapper, pbv, visitor, options
        )
        visitor.builder = builder

        # Second pass does the bulk of the work.
        builder.visit_mypy_file(module)
        module_ir = ModuleIR(
            module.fullname,
            list(builder.imports),
            builder.functions,
            builder.classes,
            builder.final_names
        )
        result[module.fullname] = module_ir
        class_irs.extend(builder.classes)

    # Compute vtables.
    for cir in class_irs:
        if cir.is_ext_class:
            compute_vtable(cir)

    return result
