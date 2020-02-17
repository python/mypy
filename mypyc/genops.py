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
"""

from typing import (
    TypeVar, Callable, Dict, List, Tuple, Optional, Union, Sequence, Set, Any, cast
)
from typing_extensions import overload, NoReturn
from collections import OrderedDict
import importlib.util

from mypy.build import Graph
from mypy.nodes import (
    MypyFile, SymbolNode, Statement, FuncDef, ReturnStmt, AssignmentStmt, OpExpr,
    IntExpr, NameExpr, LDEF, Var, IfStmt, UnaryExpr, ComparisonExpr, WhileStmt, CallExpr,
    IndexExpr, Block, Expression, ListExpr, ExpressionStmt, MemberExpr, ForStmt, RefExpr, Lvalue,
    BreakStmt, ContinueStmt, ConditionalExpr, OperatorAssignmentStmt, TupleExpr, ClassDef,
    TypeInfo, Import, ImportFrom, ImportAll, DictExpr, StrExpr, CastExpr, TempNode,
    PassStmt, PromoteExpr, AssignmentExpr, AwaitExpr, BackquoteExpr, AssertStmt, BytesExpr,
    ComplexExpr, Decorator, DelStmt, DictionaryComprehension, EllipsisExpr, EnumCallExpr, ExecStmt,
    FloatExpr, GeneratorExpr, GlobalDecl, LambdaExpr, ListComprehension, SetComprehension,
    NamedTupleExpr, NewTypeExpr, NonlocalDecl, OverloadedFuncDef, PrintStmt, RaiseStmt,
    RevealExpr, SetExpr, SliceExpr, StarExpr, SuperExpr, TryStmt, TypeAliasExpr, TypeApplication,
    TypeVarExpr, TypedDictExpr, UnicodeExpr, WithStmt, YieldFromExpr, YieldExpr, GDEF, ARG_POS,
    ARG_NAMED, ARG_STAR, ARG_STAR2, op_methods
)
from mypy.types import (
    Type, Instance, TupleType, AnyType, TypeOfAny, UninhabitedType, get_proper_type
)
from mypy.visitor import ExpressionVisitor, StatementVisitor
from mypy.checkexpr import map_actuals_to_formals
from mypy.state import strict_optional_set
from mypy.util import split_target

from mypyc.common import (
    TEMP_ATTR_NAME, MAX_LITERAL_SHORT_INT, TOP_LEVEL_NAME, FAST_ISINSTANCE_MAX_SUBCLASSES
)
from mypyc.prebuildvisitor import PreBuildVisitor
from mypyc.ops import (
    BasicBlock, AssignmentTarget, AssignmentTargetRegister, AssignmentTargetIndex,
    AssignmentTargetAttr, AssignmentTargetTuple, Environment, Op, LoadInt, RType, Value, Register,
    FuncIR, Assign, Branch, Goto, Call, Box, Unbox, Cast, RTuple, Unreachable,
    TupleGet, TupleSet, ClassIR, NonExtClassInfo, RInstance, ModuleIR, ModuleIRs, GetAttr, SetAttr,
    LoadStatic, InitStatic, MethodCall, INVALID_FUNC_DEF, int_rprimitive, float_rprimitive,
    bool_rprimitive, list_rprimitive, is_list_rprimitive, dict_rprimitive, set_rprimitive,
    str_rprimitive, none_rprimitive, is_none_rprimitive, object_rprimitive,
    exc_rtuple, PrimitiveOp, ControlOp, OpDescription, RegisterOp, is_object_rprimitive,
    FuncSignature, NAMESPACE_TYPE, NAMESPACE_MODULE,
    RaiseStandardError, LoadErrorValue, NO_TRACEBACK_LINE_NO, FuncDecl,
    FUNC_STATICMETHOD, FUNC_CLASSMETHOD, RUnion, optional_value_type,
    all_concrete_classes
)
from mypyc.ops_primitive import binary_ops, unary_ops, func_ops, method_ops, name_ref_ops
from mypyc.ops_list import (
    list_append_op, list_extend_op, list_len_op, new_list_op, to_list, list_pop_last
)
from mypyc.ops_tuple import list_tuple_op, new_tuple_op
from mypyc.ops_dict import (
    new_dict_op, dict_get_item_op, dict_set_item_op, dict_update_in_display_op,
)
from mypyc.ops_set import new_set_op, set_add_op, set_update_op
from mypyc.ops_misc import (
    none_op, none_object_op, true_op, false_op, iter_op, next_op,
    py_getattr_op, py_setattr_op, py_delattr_op,
    py_call_op, py_call_with_kwargs_op, py_method_call_op,
    fast_isinstance_op, bool_op, new_slice_op, type_op, import_op,
    get_module_dict_op, ellipsis_op, type_is_op,
)
from mypyc.ops_exc import (
    raise_exception_op, reraise_exception_op,
    error_catch_op, restore_exc_info_op, exc_matches_op, get_exc_value_op,
    get_exc_info_op, keep_propagating_op
)
from mypyc.genops_for import ForGenerator, ForRange, ForList, ForIterable, ForEnumerate, ForZip
from mypyc.rt_subtype import is_runtime_subtype
from mypyc.subtype import is_subtype
from mypyc.sametype import is_same_type
from mypyc.crash import catch_errors
from mypyc.options import CompilerOptions
from mypyc.errors import Errors
from mypyc.nonlocalcontrol import (
    NonlocalControl, BaseNonlocalControl, LoopNonlocalControl, ExceptNonlocalControl,
    FinallyNonlocalControl, TryFinallyNonlocalControl, GeneratorNonlocalControl
)
from mypyc.genclass import BuildClassIR
from mypyc.genfunc import BuildFuncIR
from mypyc.genopscontext import FuncInfo, ImplicitClass
from mypyc.genopsmapper import Mapper
from mypyc.genopsvtable import compute_vtable
from mypyc.genopsprepare import build_type_map

GenFunc = Callable[[], None]
DictEntry = Tuple[Optional[Value], Value]


class UnsupportedException(Exception):
    pass


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

        # Second pass.
        builder = IRBuilder(
            module.fullname, types, graph, errors, mapper, pbv, options
        )
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


# Infrastructure for special casing calls to builtin functions in a
# programmatic way.  Most special cases should be handled using the
# data driven "primitive ops" system, but certain operations require
# special handling that has access to the AST/IR directly and can make
# decisions/optimizations based on it.
#
# For example, we use specializers to statically emit the length of a
# fixed length tuple and to emit optimized code for any/all calls with
# generator comprehensions as the argument.
#
# Specalizers are attempted before compiling the arguments to the
# function.  Specializers can return None to indicate that they failed
# and the call should be compiled normally. Otherwise they should emit
# code for the call and return a value containing the result.
#
# Specializers take three arguments: the IRBuilder, the CallExpr being
# compiled, and the RefExpr that is the left hand side of the call.
#
# Specializers can operate on methods as well, and are keyed on the
# name and RType in that case.
Specializer = Callable[['IRBuilder', CallExpr, RefExpr], Optional[Value]]

specializers = {}  # type: Dict[Tuple[str, Optional[RType]], Specializer]


def specialize_function(
        name: str, typ: Optional[RType] = None) -> Callable[[Specializer], Specializer]:
    """Decorator to register a function as being a specializer."""
    def wrapper(f: Specializer) -> Specializer:
        specializers[name, typ] = f
        return f
    return wrapper


class IRBuilder(ExpressionVisitor[Value], StatementVisitor[None]):
    def __init__(self,
                 current_module: str,
                 types: Dict[Expression, Type],
                 graph: Graph,
                 errors: Errors,
                 mapper: Mapper,
                 pbv: PreBuildVisitor,
                 options: CompilerOptions) -> None:
        self.current_module = current_module
        self.types = types
        self.graph = graph
        self.environment = Environment()
        self.environments = [self.environment]
        self.ret_types = []  # type: List[RType]
        self.blocks = []  # type: List[List[BasicBlock]]
        self.functions = []  # type: List[FuncIR]
        self.classes = []  # type: List[ClassIR]
        self.final_names = []  # type: List[Tuple[str, RType]]
        self.callable_class_names = set()  # type: Set[str]
        self.options = options

        # These variables keep track of the number of lambdas, implicit indices, and implicit
        # iterators instantiated so we avoid name conflicts. The indices and iterators are
        # instantiated from for-loops.
        self.lambda_counter = 0
        self.temp_counter = 0

        # These variables are populated from the first-pass PreBuildVisitor.
        self.free_variables = pbv.free_variables
        self.prop_setters = pbv.prop_setters
        self.encapsulating_funcs = pbv.encapsulating_funcs
        self.nested_fitems = pbv.nested_funcs.keys()
        self.fdefs_to_decorators = pbv.funcs_to_decorators

        # This list operates similarly to a function call stack for nested functions. Whenever a
        # function definition begins to be generated, a FuncInfo instance is added to the stack,
        # and information about that function (e.g. whether it is nested, its environment class to
        # be generated) is stored in that FuncInfo instance. When the function is done being
        # generated, its corresponding FuncInfo is popped off the stack.
        self.fn_info = FuncInfo(INVALID_FUNC_DEF, '', '')
        self.fn_infos = [self.fn_info]  # type: List[FuncInfo]

        # This list operates as a stack of constructs that modify the
        # behavior of nonlocal control flow constructs.
        self.nonlocal_control = []  # type: List[NonlocalControl]
        # Stack of except handler entry blocks
        self.error_handlers = [None]  # type: List[Optional[BasicBlock]]

        self.errors = errors
        self.mapper = mapper
        # Notionally a list of all of the modules imported by the
        # module being compiled, but stored as an OrderedDict so we
        # can also do quick lookups.
        self.imports = OrderedDict()  # type: OrderedDict[str, None]

    def visit_mypy_file(self, mypyfile: MypyFile) -> None:
        if mypyfile.fullname in ('typing', 'abc'):
            # These module are special; their contents are currently all
            # built-in primitives.
            return

        self.module_path = mypyfile.path
        self.module_name = mypyfile.fullname

        classes = [node for node in mypyfile.defs if isinstance(node, ClassDef)]

        # Collect all classes.
        for cls in classes:
            ir = self.mapper.type_to_ir[cls.info]
            self.classes.append(ir)

        self.enter('<top level>')

        # Make sure we have a builtins import
        self.gen_import('builtins', -1)

        # Generate ops.
        for node in mypyfile.defs:
            self.accept(node)
        self.maybe_add_implicit_return()

        # Generate special function representing module top level.
        blocks, env, ret_type, _ = self.leave()
        sig = FuncSignature([], none_rprimitive)
        func_ir = FuncIR(FuncDecl(TOP_LEVEL_NAME, None, self.module_name, sig), blocks, env,
                         traceback_name="<module>")
        self.functions.append(func_ir)

    def visit_method(
            self, cdef: ClassDef, non_ext: Optional[NonExtClassInfo], fdef: FuncDef) -> None:
        BuildFuncIR(self).visit_method(cdef, non_ext, fdef)

    def visit_class_def(self, cdef: ClassDef) -> None:
        BuildClassIR(self).visit_class_def(cdef)

    def add_to_non_ext_dict(self, non_ext: NonExtClassInfo,
                            key: str, val: Value, line: int) -> None:
        # Add an attribute entry into the class dict of a non-extension class.
        key_unicode = self.load_static_unicode(key)
        self.primitive_op(dict_set_item_op, [non_ext.dict, key_unicode, val], line)

    def gen_import(self, id: str, line: int) -> None:
        self.imports[id] = None

        needs_import, out = BasicBlock(), BasicBlock()
        first_load = self.load_module(id)
        comparison = self.binary_op(first_load, self.none_object(), 'is not', line)
        self.add_bool_branch(comparison, out, needs_import)

        self.activate_block(needs_import)
        value = self.primitive_op(import_op, [self.load_static_unicode(id)], line)
        self.add(InitStatic(value, id, namespace=NAMESPACE_MODULE))
        self.goto_and_activate(out)

    def visit_import(self, node: Import) -> None:
        if node.is_mypy_only:
            return
        globals = self.load_globals_dict()
        for node_id, as_name in node.ids:
            self.gen_import(node_id, node.line)

            # Update the globals dict with the appropriate module:
            # * For 'import foo.bar as baz' we add 'foo.bar' with the name 'baz'
            # * For 'import foo.bar' we add 'foo' with the name 'foo'
            # Typically we then ignore these entries and access things directly
            # via the module static, but we will use the globals version for modules
            # that mypy couldn't find, since it doesn't analyze module references
            # from those properly.

            # Miscompiling imports inside of functions, like below in import from.
            if as_name:
                name = as_name
                base = node_id
            else:
                base = name = node_id.split('.')[0]

            # Python 3.7 has a nice 'PyImport_GetModule' function that we can't use :(
            mod_dict = self.primitive_op(get_module_dict_op, [], node.line)
            obj = self.primitive_op(dict_get_item_op,
                                    [mod_dict, self.load_static_unicode(base)], node.line)
            self.translate_special_method_call(
                globals, '__setitem__', [self.load_static_unicode(name), obj],
                result_type=None, line=node.line)

    def visit_import_from(self, node: ImportFrom) -> None:
        if node.is_mypy_only:
            return

        module_state = self.graph[self.module_name]
        if module_state.ancestors is not None and module_state.ancestors:
            module_package = module_state.ancestors[0]
        else:
            module_package = ''

        id = importlib.util.resolve_name('.' * node.relative + node.id, module_package)

        self.gen_import(id, node.line)
        module = self.load_module(id)

        # Copy everything into our module's dict.
        # Note that we miscompile import from inside of functions here,
        # since that case *shouldn't* load it into the globals dict.
        # This probably doesn't matter much and the code runs basically right.
        globals = self.load_globals_dict()
        for name, maybe_as_name in node.names:
            # If one of the things we are importing is a module,
            # import it as a module also.
            fullname = id + '.' + name
            if fullname in self.graph or fullname in module_state.suppressed:
                self.gen_import(fullname, node.line)

            as_name = maybe_as_name or name
            obj = self.py_get_attr(module, name, node.line)
            self.translate_special_method_call(
                globals, '__setitem__', [self.load_static_unicode(as_name), obj],
                result_type=None, line=node.line)

    def visit_import_all(self, node: ImportAll) -> None:
        if node.is_mypy_only:
            return
        self.gen_import(node.id, node.line)

    def assign_if_null(self, target: AssignmentTargetRegister,
                       get_val: Callable[[], Value], line: int) -> None:
        """Generate blocks for registers that NULL values."""
        error_block, body_block = BasicBlock(), BasicBlock()
        self.add(Branch(target.register, error_block, body_block, Branch.IS_ERROR))
        self.activate_block(error_block)
        self.add(Assign(target.register, self.coerce(get_val(), target.register.type, line)))
        self.goto(body_block)
        self.activate_block(body_block)

    def maybe_add_implicit_return(self) -> None:
        if is_none_rprimitive(self.ret_types[-1]) or is_object_rprimitive(self.ret_types[-1]):
            self.add_implicit_return()
        else:
            self.add_implicit_unreachable()

    def visit_func_def(self, fdef: FuncDef) -> None:
        BuildFuncIR(self).visit_func_def(fdef)

    def visit_overloaded_func_def(self, o: OverloadedFuncDef) -> None:
        BuildFuncIR(self).visit_overloaded_func_def(o)

    def add_implicit_return(self) -> None:
        block = self.blocks[-1][-1]
        if not block.ops or not isinstance(block.ops[-1], ControlOp):
            retval = self.coerce(self.none(), self.ret_types[-1], -1)
            self.nonlocal_control[-1].gen_return(self, retval, self.fn_info.fitem.line)

    def add_implicit_unreachable(self) -> None:
        block = self.blocks[-1][-1]
        if not block.ops or not isinstance(block.ops[-1], ControlOp):
            self.add(Unreachable())

    def visit_block(self, block: Block) -> None:
        if not block.is_unreachable:
            for stmt in block.body:
                self.accept(stmt)
        # Raise a RuntimeError if we hit a non-empty unreachable block.
        # Don't complain about empty unreachable blocks, since mypy inserts
        # those after `if MYPY`.
        elif block.body:
            self.add(RaiseStandardError(RaiseStandardError.RUNTIME_ERROR,
                                        'Reached allegedly unreachable code!',
                                        block.line))
            self.add(Unreachable())

    def visit_expression_stmt(self, stmt: ExpressionStmt) -> None:
        if isinstance(stmt.expr, StrExpr):
            # Docstring. Ignore
            return
        # ExpressionStmts do not need to be coerced like other Expressions.
        stmt.expr.accept(self)

    def visit_return_stmt(self, stmt: ReturnStmt) -> None:
        if stmt.expr:
            retval = self.accept(stmt.expr)
        else:
            retval = self.none()
        retval = self.coerce(retval, self.ret_types[-1], stmt.line)
        self.nonlocal_control[-1].gen_return(self, retval, stmt.line)

    def disallow_class_assignments(self, lvalues: List[Lvalue], line: int) -> None:
        # Some best-effort attempts to disallow assigning to class
        # variables that aren't marked ClassVar, since we blatantly
        # miscompile the interaction between instance and class
        # variables.
        for lvalue in lvalues:
            if (isinstance(lvalue, MemberExpr)
                    and isinstance(lvalue.expr, RefExpr)
                    and isinstance(lvalue.expr.node, TypeInfo)):
                var = lvalue.expr.node[lvalue.name].node
                if isinstance(var, Var) and not var.is_classvar:
                    self.error(
                        "Only class variables defined as ClassVar can be assigned to",
                        line)

    def non_function_scope(self) -> bool:
        # Currently the stack always has at least two items: dummy and top-level.
        return len(self.fn_infos) <= 2

    def init_final_static(self, lvalue: Lvalue, rvalue_reg: Value,
                          class_name: Optional[str] = None) -> None:
        assert isinstance(lvalue, NameExpr)
        assert isinstance(lvalue.node, Var)
        if lvalue.node.final_value is None:
            if class_name is None:
                name = lvalue.name
            else:
                name = '{}.{}'.format(class_name, lvalue.name)
            assert name is not None, "Full name not set for variable"
            self.final_names.append((name, rvalue_reg.type))
            self.add(InitStatic(rvalue_reg, name, self.module_name))

    def load_final_static(self, fullname: str, typ: RType, line: int,
                          error_name: Optional[str] = None) -> Value:
        if error_name is None:
            error_name = fullname
        ok_block, error_block = BasicBlock(), BasicBlock()
        split_name = split_target(self.graph, fullname)
        assert split_name is not None
        value = self.add(LoadStatic(typ, split_name[1], split_name[0], line=line))
        self.add(Branch(value, error_block, ok_block, Branch.IS_ERROR, rare=True))
        self.activate_block(error_block)
        self.add(RaiseStandardError(RaiseStandardError.VALUE_ERROR,
                                    'value for final name "{}" was not set'.format(error_name),
                                    line))
        self.add(Unreachable())
        self.activate_block(ok_block)
        return value

    def load_final_literal_value(self, val: Union[int, str, bytes, float, bool],
                                 line: int) -> Value:
        """Load value of a final name or class-level attribute."""
        if isinstance(val, bool):
            if val:
                return self.primitive_op(true_op, [], line)
            else:
                return self.primitive_op(false_op, [], line)
        elif isinstance(val, int):
            # TODO: take care of negative integer initializers
            # (probably easier to fix this in mypy itself).
            if val > MAX_LITERAL_SHORT_INT:
                return self.load_static_int(val)
            return self.add(LoadInt(val))
        elif isinstance(val, float):
            return self.load_static_float(val)
        elif isinstance(val, str):
            return self.load_static_unicode(val)
        elif isinstance(val, bytes):
            return self.load_static_bytes(val)
        else:
            assert False, "Unsupported final literal value"

    def visit_assignment_stmt(self, stmt: AssignmentStmt) -> None:
        assert len(stmt.lvalues) >= 1
        self.disallow_class_assignments(stmt.lvalues, stmt.line)
        lvalue = stmt.lvalues[0]
        if stmt.type and isinstance(stmt.rvalue, TempNode):
            # This is actually a variable annotation without initializer. Don't generate
            # an assignment but we need to call get_assignment_target since it adds a
            # name binding as a side effect.
            self.get_assignment_target(lvalue, stmt.line)
            return

        line = stmt.rvalue.line
        rvalue_reg = self.accept(stmt.rvalue)
        if self.non_function_scope() and stmt.is_final_def:
            self.init_final_static(lvalue, rvalue_reg)
        for lvalue in stmt.lvalues:
            target = self.get_assignment_target(lvalue)
            self.assign(target, rvalue_reg, line)

    def visit_operator_assignment_stmt(self, stmt: OperatorAssignmentStmt) -> None:
        """Operator assignment statement such as x += 1"""
        self.disallow_class_assignments([stmt.lvalue], stmt.line)
        target = self.get_assignment_target(stmt.lvalue)
        target_value = self.read(target, stmt.line)
        rreg = self.accept(stmt.rvalue)
        # the Python parser strips the '=' from operator assignment statements, so re-add it
        op = stmt.op + '='
        res = self.binary_op(target_value, rreg, op, stmt.line)
        # usually operator assignments are done in-place
        # but when target doesn't support that we need to manually assign
        self.assign(target, res, res.line)

    def get_assignment_target(self, lvalue: Lvalue,
                              line: int = -1) -> AssignmentTarget:
        if isinstance(lvalue, NameExpr):
            # If we are visiting a decorator, then the SymbolNode we really want to be looking at
            # is the function that is decorated, not the entire Decorator node itself.
            symbol = lvalue.node
            if isinstance(symbol, Decorator):
                symbol = symbol.func
            if symbol is None:
                # New semantic analyzer doesn't create ad-hoc Vars for special forms.
                assert lvalue.is_special_form
                symbol = Var(lvalue.name)
            if lvalue.kind == LDEF:
                if symbol not in self.environment.symtable:
                    # If the function is a generator function, then first define a new variable
                    # in the current function's environment class. Next, define a target that
                    # refers to the newly defined variable in that environment class. Add the
                    # target to the table containing class environment variables, as well as the
                    # current environment.
                    if self.fn_info.is_generator:
                        return self.add_var_to_env_class(symbol, self.node_type(lvalue),
                                                         self.fn_info.generator_class,
                                                         reassign=False)

                    # Otherwise define a new local variable.
                    return self.environment.add_local_reg(symbol, self.node_type(lvalue))
                else:
                    # Assign to a previously defined variable.
                    return self.environment.lookup(symbol)
            elif lvalue.kind == GDEF:
                globals_dict = self.load_globals_dict()
                name = self.load_static_unicode(lvalue.name)
                return AssignmentTargetIndex(globals_dict, name)
            else:
                assert False, lvalue.kind
        elif isinstance(lvalue, IndexExpr):
            # Indexed assignment x[y] = e
            base = self.accept(lvalue.base)
            index = self.accept(lvalue.index)
            return AssignmentTargetIndex(base, index)
        elif isinstance(lvalue, MemberExpr):
            # Attribute assignment x.y = e
            obj = self.accept(lvalue.expr)
            return AssignmentTargetAttr(obj, lvalue.name)
        elif isinstance(lvalue, TupleExpr):
            # Multiple assignment a, ..., b = e
            star_idx = None  # type: Optional[int]
            lvalues = []
            for idx, item in enumerate(lvalue.items):
                targ = self.get_assignment_target(item)
                lvalues.append(targ)
                if isinstance(item, StarExpr):
                    if star_idx is not None:
                        self.error("Two starred expressions in assignment", line)
                    star_idx = idx

            return AssignmentTargetTuple(lvalues, star_idx)

        elif isinstance(lvalue, StarExpr):
            return self.get_assignment_target(lvalue.expr)

        assert False, 'Unsupported lvalue: %r' % lvalue

    def read(self, target: Union[Value, AssignmentTarget], line: int = -1) -> Value:
        if isinstance(target, Value):
            return target
        if isinstance(target, AssignmentTargetRegister):
            return target.register
        if isinstance(target, AssignmentTargetIndex):
            reg = self.gen_method_call(
                target.base, '__getitem__', [target.index], target.type, line)
            if reg is not None:
                return reg
            assert False, target.base.type
        if isinstance(target, AssignmentTargetAttr):
            if isinstance(target.obj.type, RInstance) and target.obj.type.class_ir.is_ext_class:
                return self.add(GetAttr(target.obj, target.attr, line))
            else:
                return self.py_get_attr(target.obj, target.attr, line)

        assert False, 'Unsupported lvalue: %r' % target

    def assign(self, target: Union[Register, AssignmentTarget],
               rvalue_reg: Value, line: int) -> None:
        if isinstance(target, Register):
            self.add(Assign(target, rvalue_reg))
        elif isinstance(target, AssignmentTargetRegister):
            rvalue_reg = self.coerce(rvalue_reg, target.type, line)
            self.add(Assign(target.register, rvalue_reg))
        elif isinstance(target, AssignmentTargetAttr):
            if isinstance(target.obj_type, RInstance):
                rvalue_reg = self.coerce(rvalue_reg, target.type, line)
                self.add(SetAttr(target.obj, target.attr, rvalue_reg, line))
            else:
                key = self.load_static_unicode(target.attr)
                boxed_reg = self.box(rvalue_reg)
                self.add(PrimitiveOp([target.obj, key, boxed_reg], py_setattr_op, line))
        elif isinstance(target, AssignmentTargetIndex):
            target_reg2 = self.gen_method_call(
                target.base, '__setitem__', [target.index, rvalue_reg], None, line)
            assert target_reg2 is not None, target.base.type
        elif isinstance(target, AssignmentTargetTuple):
            if isinstance(rvalue_reg.type, RTuple) and target.star_idx is None:
                rtypes = rvalue_reg.type.types
                assert len(rtypes) == len(target.items)
                for i in range(len(rtypes)):
                    item_value = self.add(TupleGet(rvalue_reg, i, line))
                    self.assign(target.items[i], item_value, line)
            else:
                self.process_iterator_tuple_assignment(target, rvalue_reg, line)
        else:
            assert False, 'Unsupported assignment target'

    def process_iterator_tuple_assignment_helper(self,
                                                 litem: AssignmentTarget,
                                                 ritem: Value, line: int) -> None:
        error_block, ok_block = BasicBlock(), BasicBlock()
        self.add(Branch(ritem, error_block, ok_block, Branch.IS_ERROR))

        self.activate_block(error_block)
        self.add(RaiseStandardError(RaiseStandardError.VALUE_ERROR,
                                    'not enough values to unpack', line))
        self.add(Unreachable())

        self.activate_block(ok_block)
        self.assign(litem, ritem, line)

    def process_iterator_tuple_assignment(self,
                                          target: AssignmentTargetTuple,
                                          rvalue_reg: Value,
                                          line: int) -> None:

        iterator = self.primitive_op(iter_op, [rvalue_reg], line)

        # This may be the whole lvalue list if there is no starred value
        split_idx = target.star_idx if target.star_idx is not None else len(target.items)

        # Assign values before the first starred value
        for litem in target.items[:split_idx]:
            ritem = self.primitive_op(next_op, [iterator], line)
            error_block, ok_block = BasicBlock(), BasicBlock()
            self.add(Branch(ritem, error_block, ok_block, Branch.IS_ERROR))

            self.activate_block(error_block)
            self.add(RaiseStandardError(RaiseStandardError.VALUE_ERROR,
                                        'not enough values to unpack', line))
            self.add(Unreachable())

            self.activate_block(ok_block)

            self.assign(litem, ritem, line)

        # Assign the starred value and all values after it
        if target.star_idx is not None:
            post_star_vals = target.items[split_idx + 1:]
            iter_list = self.primitive_op(to_list, [iterator], line)
            iter_list_len = self.primitive_op(list_len_op, [iter_list], line)
            post_star_len = self.add(LoadInt(len(post_star_vals)))
            condition = self.binary_op(post_star_len, iter_list_len, '<=', line)

            error_block, ok_block = BasicBlock(), BasicBlock()
            self.add(Branch(condition, ok_block, error_block, Branch.BOOL_EXPR))

            self.activate_block(error_block)
            self.add(RaiseStandardError(RaiseStandardError.VALUE_ERROR,
                                        'not enough values to unpack', line))
            self.add(Unreachable())

            self.activate_block(ok_block)

            for litem in reversed(post_star_vals):
                ritem = self.primitive_op(list_pop_last, [iter_list], line)
                self.assign(litem, ritem, line)

            # Assign the starred value
            self.assign(target.items[target.star_idx], iter_list, line)

        # There is no starred value, so check if there are extra values in rhs that
        # have not been assigned.
        else:
            extra = self.primitive_op(next_op, [iterator], line)
            error_block, ok_block = BasicBlock(), BasicBlock()
            self.add(Branch(extra, ok_block, error_block, Branch.IS_ERROR))

            self.activate_block(error_block)
            self.add(RaiseStandardError(RaiseStandardError.VALUE_ERROR,
                                        'too many values to unpack', line))
            self.add(Unreachable())

            self.activate_block(ok_block)

    def visit_if_stmt(self, stmt: IfStmt) -> None:
        if_body, next = BasicBlock(), BasicBlock()
        else_body = BasicBlock() if stmt.else_body else next

        # If statements are normalized
        assert len(stmt.expr) == 1

        self.process_conditional(stmt.expr[0], if_body, else_body)
        self.activate_block(if_body)
        self.accept(stmt.body[0])
        self.goto(next)
        if stmt.else_body:
            self.activate_block(else_body)
            self.accept(stmt.else_body)
            self.goto(next)
        self.activate_block(next)

    def push_loop_stack(self, continue_block: BasicBlock, break_block: BasicBlock) -> None:
        self.nonlocal_control.append(
            LoopNonlocalControl(self.nonlocal_control[-1], continue_block, break_block))

    def pop_loop_stack(self) -> None:
        self.nonlocal_control.pop()

    def visit_while_stmt(self, s: WhileStmt) -> None:
        body, next, top, else_block = BasicBlock(), BasicBlock(), BasicBlock(), BasicBlock()
        normal_loop_exit = else_block if s.else_body is not None else next

        self.push_loop_stack(top, next)

        # Split block so that we get a handle to the top of the loop.
        self.goto_and_activate(top)
        self.process_conditional(s.expr, body, normal_loop_exit)

        self.activate_block(body)
        self.accept(s.body)
        # Add branch to the top at the end of the body.
        self.goto(top)

        self.pop_loop_stack()

        if s.else_body is not None:
            self.activate_block(else_block)
            self.accept(s.else_body)
            self.goto(next)

        self.activate_block(next)

    def visit_for_stmt(self, s: ForStmt) -> None:
        def body() -> None:
            self.accept(s.body)

        def else_block() -> None:
            assert s.else_body is not None
            self.accept(s.else_body)

        self.for_loop_helper(s.index, s.expr, body,
                             else_block if s.else_body else None, s.line)

    def spill(self, value: Value) -> AssignmentTarget:
        """Moves a given Value instance into the generator class' environment class."""
        name = '{}{}'.format(TEMP_ATTR_NAME, self.temp_counter)
        self.temp_counter += 1
        target = self.add_var_to_env_class(Var(name), value.type, self.fn_info.generator_class)
        # Shouldn't be able to fail, so -1 for line
        self.assign(target, value, -1)
        return target

    def maybe_spill(self, value: Value) -> Union[Value, AssignmentTarget]:
        """
        Moves a given Value instance into the environment class for generator functions. For
        non-generator functions, leaves the Value instance as it is.

        Returns an AssignmentTarget associated with the Value for generator functions and the
        original Value itself for non-generator functions.
        """
        if self.fn_info.is_generator:
            return self.spill(value)
        return value

    def maybe_spill_assignable(self, value: Value) -> Union[Register, AssignmentTarget]:
        """
        Moves a given Value instance into the environment class for generator functions. For
        non-generator functions, allocate a temporary Register.

        Returns an AssignmentTarget associated with the Value for generator functions and an
        assignable Register for non-generator functions.
        """
        if self.fn_info.is_generator:
            return self.spill(value)

        if isinstance(value, Register):
            return value

        # Allocate a temporary register for the assignable value.
        reg = self.alloc_temp(value.type)
        self.assign(reg, value, -1)
        return reg

    def for_loop_helper(self, index: Lvalue, expr: Expression,
                        body_insts: GenFunc, else_insts: Optional[GenFunc],
                        line: int) -> None:
        """Generate IR for a loop.

        Args:
            index: the loop index Lvalue
            expr: the expression to iterate over
            body_insts: a function that generates the body of the loop
            else_insts: a function that generates the else block instructions
        """
        # Body of the loop
        body_block = BasicBlock()
        # Block that steps to the next item
        step_block = BasicBlock()
        # Block for the else clause, if we need it
        else_block = BasicBlock()
        # Block executed after the loop
        exit_block = BasicBlock()

        # Determine where we want to exit, if our condition check fails.
        normal_loop_exit = else_block if else_insts is not None else exit_block

        for_gen = self.make_for_loop_generator(index, expr, body_block, normal_loop_exit, line)

        self.push_loop_stack(step_block, exit_block)
        condition_block = self.goto_new_block()

        # Add loop condition check.
        for_gen.gen_condition()

        # Generate loop body.
        self.activate_block(body_block)
        for_gen.begin_body()
        body_insts()

        # We generate a separate step block (which might be empty).
        self.goto_and_activate(step_block)
        for_gen.gen_step()
        # Go back to loop condition.
        self.goto(condition_block)

        for_gen.add_cleanup(normal_loop_exit)
        self.pop_loop_stack()

        if else_insts is not None:
            self.activate_block(else_block)
            else_insts()
            self.goto(exit_block)

        self.activate_block(exit_block)

    def extract_int(self, e: Expression) -> Optional[int]:
        if isinstance(e, IntExpr):
            return e.value
        elif isinstance(e, UnaryExpr) and e.op == '-' and isinstance(e.expr, IntExpr):
            return -e.expr.value
        else:
            return None

    def make_for_loop_generator(self,
                                index: Lvalue,
                                expr: Expression,
                                body_block: BasicBlock,
                                loop_exit: BasicBlock,
                                line: int,
                                nested: bool = False) -> ForGenerator:
        """Return helper object for generating a for loop over an iterable.

        If "nested" is True, this is a nested iterator such as "e" in "enumerate(e)".
        """

        if is_list_rprimitive(self.node_type(expr)):
            # Special case "for x in <list>".
            expr_reg = self.accept(expr)
            target_list_type = get_proper_type(self.types[expr])
            assert isinstance(target_list_type, Instance)
            target_type = self.type_to_rtype(target_list_type.args[0])

            for_list = ForList(self, index, body_block, loop_exit, line, nested)
            for_list.init(expr_reg, target_type, reverse=False)
            return for_list

        if (isinstance(expr, CallExpr)
                and isinstance(expr.callee, RefExpr)):
            if (expr.callee.fullname == 'builtins.range'
                    and (len(expr.args) <= 2
                         or (len(expr.args) == 3
                             and self.extract_int(expr.args[2]) is not None))
                    and set(expr.arg_kinds) == {ARG_POS}):
                # Special case "for x in range(...)".
                # We support the 3 arg form but only for int literals, since it doesn't
                # seem worth the hassle of supporting dynamically determining which
                # direction of comparison to do.
                if len(expr.args) == 1:
                    start_reg = self.add(LoadInt(0))
                    end_reg = self.accept(expr.args[0])
                else:
                    start_reg = self.accept(expr.args[0])
                    end_reg = self.accept(expr.args[1])
                if len(expr.args) == 3:
                    step = self.extract_int(expr.args[2])
                    assert step is not None
                    if step == 0:
                        self.error("range() step can't be zero", expr.args[2].line)
                else:
                    step = 1

                for_range = ForRange(self, index, body_block, loop_exit, line, nested)
                for_range.init(start_reg, end_reg, step)
                return for_range

            elif (expr.callee.fullname == 'builtins.enumerate'
                    and len(expr.args) == 1
                    and expr.arg_kinds == [ARG_POS]
                    and isinstance(index, TupleExpr)
                    and len(index.items) == 2):
                # Special case "for i, x in enumerate(y)".
                lvalue1 = index.items[0]
                lvalue2 = index.items[1]
                for_enumerate = ForEnumerate(self, index, body_block, loop_exit, line,
                                             nested)
                for_enumerate.init(lvalue1, lvalue2, expr.args[0])
                return for_enumerate

            elif (expr.callee.fullname == 'builtins.zip'
                    and len(expr.args) >= 2
                    and set(expr.arg_kinds) == {ARG_POS}
                    and isinstance(index, TupleExpr)
                    and len(index.items) == len(expr.args)):
                # Special case "for x, y in zip(a, b)".
                for_zip = ForZip(self, index, body_block, loop_exit, line, nested)
                for_zip.init(index.items, expr.args)
                return for_zip

            if (expr.callee.fullname == 'builtins.reversed'
                    and len(expr.args) == 1
                    and expr.arg_kinds == [ARG_POS]
                    and is_list_rprimitive(self.node_type(expr.args[0]))):
                # Special case "for x in reversed(<list>)".
                expr_reg = self.accept(expr.args[0])
                target_list_type = get_proper_type(self.types[expr.args[0]])
                assert isinstance(target_list_type, Instance)
                target_type = self.type_to_rtype(target_list_type.args[0])

                for_list = ForList(self, index, body_block, loop_exit, line, nested)
                for_list.init(expr_reg, target_type, reverse=True)
                return for_list

        # Default to a generic for loop.
        expr_reg = self.accept(expr)
        for_obj = ForIterable(self, index, body_block, loop_exit, line, nested)
        item_type = self._analyze_iterable_item_type(expr)
        item_rtype = self.type_to_rtype(item_type)
        for_obj.init(expr_reg, item_rtype)
        return for_obj

    def _analyze_iterable_item_type(self, expr: Expression) -> Type:
        """Return the item type given by 'expr' in an iterable context."""
        # This logic is copied from mypy's TypeChecker.analyze_iterable_item_type.
        iterable = get_proper_type(self.types[expr])
        echk = self.graph[self.module_name].type_checker().expr_checker
        iterator = echk.check_method_call_by_name('__iter__', iterable, [], [], expr)[0]

        from mypy.join import join_types
        if isinstance(iterable, TupleType):
            joined = UninhabitedType()  # type: Type
            for item in iterable.items:
                joined = join_types(joined, item)
            return joined
        else:
            # Non-tuple iterable.
            return echk.check_method_call_by_name('__next__', iterator, [], [], expr)[0]

    def visit_break_stmt(self, node: BreakStmt) -> None:
        self.nonlocal_control[-1].gen_break(self, node.line)

    def visit_continue_stmt(self, node: ContinueStmt) -> None:
        self.nonlocal_control[-1].gen_continue(self, node.line)

    def visit_unary_expr(self, expr: UnaryExpr) -> Value:
        return self.unary_op(self.accept(expr.expr), expr.op, expr.line)

    def visit_op_expr(self, expr: OpExpr) -> Value:
        if expr.op in ('and', 'or'):
            return self.shortcircuit_expr(expr)
        return self.binary_op(self.accept(expr.left), self.accept(expr.right), expr.op, expr.line)

    def translate_eq_cmp(self,
                         lreg: Value,
                         rreg: Value,
                         expr_op: str,
                         line: int) -> Optional[Value]:
        ltype = lreg.type
        rtype = rreg.type
        if not (isinstance(ltype, RInstance) and ltype == rtype):
            return None

        class_ir = ltype.class_ir
        # Check whether any subclasses of the operand redefines __eq__
        # or it might be redefined in a Python parent class or by
        # dataclasses
        cmp_varies_at_runtime = (
            not class_ir.is_method_final('__eq__')
            or not class_ir.is_method_final('__ne__')
            or class_ir.inherits_python
            or class_ir.is_augmented
        )

        if cmp_varies_at_runtime:
            # We might need to call left.__eq__(right) or right.__eq__(left)
            # depending on which is the more specific type.
            return None

        if not class_ir.has_method('__eq__'):
            # There's no __eq__ defined, so just use object identity.
            identity_ref_op = 'is' if expr_op == '==' else 'is not'
            return self.binary_op(lreg, rreg, identity_ref_op, line)

        return self.gen_method_call(
            lreg,
            op_methods[expr_op],
            [rreg],
            ltype,
            line
        )

    def matching_primitive_op(self,
                              candidates: List[OpDescription],
                              args: List[Value],
                              line: int,
                              result_type: Optional[RType] = None) -> Optional[Value]:
        # Find the highest-priority primitive op that matches.
        matching = None  # type: Optional[OpDescription]
        for desc in candidates:
            if len(desc.arg_types) != len(args):
                continue
            if all(is_subtype(actual.type, formal)
                   for actual, formal in zip(args, desc.arg_types)):
                if matching:
                    assert matching.priority != desc.priority, 'Ambiguous:\n1) %s\n2) %s' % (
                        matching, desc)
                    if desc.priority > matching.priority:
                        matching = desc
                else:
                    matching = desc
        if matching:
            target = self.primitive_op(matching, args, line)
            if result_type and not is_runtime_subtype(target.type, result_type):
                if is_none_rprimitive(result_type):
                    # Special case None return. The actual result may actually be a bool
                    # and so we can't just coerce it.
                    target = self.none()
                else:
                    target = self.coerce(target, result_type, line)
            return target
        return None

    def binary_op(self,
                  lreg: Value,
                  rreg: Value,
                  expr_op: str,
                  line: int) -> Value:
        # Special case == and != when we can resolve the method call statically.
        value = None
        if expr_op in ('==', '!='):
            value = self.translate_eq_cmp(lreg, rreg, expr_op, line)
        if value is not None:
            return value

        ops = binary_ops.get(expr_op, [])
        target = self.matching_primitive_op(ops, [lreg, rreg], line)
        assert target, 'Unsupported binary operation: %s' % expr_op
        return target

    def unary_op(self,
                 lreg: Value,
                 expr_op: str,
                 line: int) -> Value:
        ops = unary_ops.get(expr_op, [])
        target = self.matching_primitive_op(ops, [lreg], line)
        assert target, 'Unsupported unary operation: %s' % expr_op
        return target

    def visit_index_expr(self, expr: IndexExpr) -> Value:
        base = self.accept(expr.base)

        if isinstance(base.type, RTuple) and isinstance(expr.index, IntExpr):
            return self.add(TupleGet(base, expr.index.value, expr.line))

        index_reg = self.accept(expr.index)
        return self.gen_method_call(
            base, '__getitem__', [index_reg], self.node_type(expr), expr.line)

    def visit_int_expr(self, expr: IntExpr) -> Value:
        if expr.value > MAX_LITERAL_SHORT_INT:
            return self.load_static_int(expr.value)
        return self.add(LoadInt(expr.value))

    def visit_float_expr(self, expr: FloatExpr) -> Value:
        return self.load_static_float(expr.value)

    def visit_complex_expr(self, expr: ComplexExpr) -> Value:
        return self.load_static_complex(expr.value)

    def visit_bytes_expr(self, expr: BytesExpr) -> Value:
        value = bytes(expr.value, 'utf8').decode('unicode-escape').encode('raw-unicode-escape')
        return self.load_static_bytes(value)

    def is_native_module(self, module: str) -> bool:
        """Is the given module one compiled by mypyc?"""
        return module in self.mapper.group_map

    def is_native_ref_expr(self, expr: RefExpr) -> bool:
        if expr.node is None:
            return False
        if '.' in expr.node.fullname:
            return self.is_native_module(expr.node.fullname.rpartition('.')[0])
        return True

    def is_native_module_ref_expr(self, expr: RefExpr) -> bool:
        return self.is_native_ref_expr(expr) and expr.kind == GDEF

    def is_synthetic_type(self, typ: TypeInfo) -> bool:
        """Is a type something other than just a class we've created?"""
        return typ.is_named_tuple or typ.is_newtype or typ.typeddict_type is not None

    def get_final_ref(self, expr: MemberExpr) -> Optional[Tuple[str, Var, bool]]:
        """Check if `expr` is a final attribute.

        This needs to be done differently for class and module attributes to
        correctly determine fully qualified name. Return a tuple that consists of
        the qualified name, the corresponding Var node, and a flag indicating whether
        the final name was defined in a compiled module. Return None if `expr` does not
        refer to a final attribute.
        """
        final_var = None
        if isinstance(expr.expr, RefExpr) and isinstance(expr.expr.node, TypeInfo):
            # a class attribute
            sym = expr.expr.node.get(expr.name)
            if sym and isinstance(sym.node, Var):
                # Enum attribute are treated as final since they are added to the global cache
                expr_fullname = expr.expr.node.bases[0].type.fullname
                is_final = sym.node.is_final or expr_fullname == 'enum.Enum'
                if is_final:
                    final_var = sym.node
                    fullname = '{}.{}'.format(sym.node.info.fullname, final_var.name)
                    native = self.is_native_module(expr.expr.node.module_name)
        elif self.is_module_member_expr(expr):
            # a module attribute
            if isinstance(expr.node, Var) and expr.node.is_final:
                final_var = expr.node
                fullname = expr.node.fullname
                native = self.is_native_ref_expr(expr)
        if final_var is not None:
            return fullname, final_var, native
        return None

    def emit_load_final(self, final_var: Var, fullname: str,
                        name: str, native: bool, typ: Type, line: int) -> Optional[Value]:
        """Emit code for loading value of a final name (if possible).

        Args:
            final_var: Var corresponding to the final name
            fullname: its qualified name
            name: shorter name to show in errors
            native: whether the name was defined in a compiled module
            typ: its type
            line: line number where loading occurs
        """
        if final_var.final_value is not None:  # this is safe even for non-native names
            return self.load_final_literal_value(final_var.final_value, line)
        elif native:
            return self.load_final_static(fullname, self.mapper.type_to_rtype(typ),
                                          line, name)
        else:
            return None

    def visit_name_expr(self, expr: NameExpr) -> Value:
        assert expr.node, "RefExpr not resolved"
        fullname = expr.node.fullname
        if fullname in name_ref_ops:
            # Use special access op for this particular name.
            desc = name_ref_ops[fullname]
            assert desc.result_type is not None
            return self.add(PrimitiveOp([], desc, expr.line))

        if isinstance(expr.node, Var) and expr.node.is_final:
            value = self.emit_load_final(expr.node, fullname, expr.name,
                                         self.is_native_ref_expr(expr), self.types[expr],
                                         expr.line)
            if value is not None:
                return value

        if isinstance(expr.node, MypyFile) and expr.node.fullname in self.imports:
            return self.load_module(expr.node.fullname)

        # If the expression is locally defined, then read the result from the corresponding
        # assignment target and return it. Otherwise if the expression is a global, load it from
        # the globals dictionary.
        # Except for imports, that currently always happens in the global namespace.
        if expr.kind == LDEF and not (isinstance(expr.node, Var)
                                      and expr.node.is_suppressed_import):
            # Try to detect and error when we hit the irritating mypy bug
            # where a local variable is cast to None. (#5423)
            if (isinstance(expr.node, Var) and is_none_rprimitive(self.node_type(expr))
                    and expr.node.is_inferred):
                self.error(
                    "Local variable '{}' has inferred type None; add an annotation".format(
                        expr.node.name),
                    expr.node.line)

            # TODO: Behavior currently only defined for Var and FuncDef node types.
            return self.read(self.get_assignment_target(expr), expr.line)

        return self.load_global(expr)

    def is_module_member_expr(self, expr: MemberExpr) -> bool:
        return isinstance(expr.expr, RefExpr) and isinstance(expr.expr.node, MypyFile)

    def visit_member_expr(self, expr: MemberExpr) -> Value:
        # First check if this is maybe a final attribute.
        final = self.get_final_ref(expr)
        if final is not None:
            fullname, final_var, native = final
            value = self.emit_load_final(final_var, fullname, final_var.name, native,
                                         self.types[expr], expr.line)
            if value is not None:
                return value

        if isinstance(expr.node, MypyFile) and expr.node.fullname in self.imports:
            return self.load_module(expr.node.fullname)

        obj = self.accept(expr.expr)
        return self.get_attr(obj, expr.name, self.node_type(expr), expr.line)

    def get_attr(self, obj: Value, attr: str, result_type: RType, line: int) -> Value:
        if (isinstance(obj.type, RInstance) and obj.type.class_ir.is_ext_class
                and obj.type.class_ir.has_attr(attr)):
            return self.add(GetAttr(obj, attr, line))
        elif isinstance(obj.type, RUnion):
            return self.union_get_attr(obj, obj.type, attr, result_type, line)
        else:
            return self.py_get_attr(obj, attr, line)

    def union_get_attr(self,
                       obj: Value,
                       rtype: RUnion,
                       attr: str,
                       result_type: RType,
                       line: int) -> Value:
        def get_item_attr(value: Value) -> Value:
            return self.get_attr(value, attr, result_type, line)

        return self.decompose_union_helper(obj, rtype, result_type, get_item_attr, line)

    def decompose_union_helper(self,
                               obj: Value,
                               rtype: RUnion,
                               result_type: RType,
                               process_item: Callable[[Value], Value],
                               line: int) -> Value:
        """Generate isinstance() + specialized operations for union items.

        Say, for Union[A, B] generate ops resembling this (pseudocode):

            if isinstance(obj, A):
                result = <result of process_item(cast(A, obj)>
            else:
                result = <result of process_item(cast(B, obj)>

        Args:
            obj: value with a union type
            rtype: the union type
            result_type: result of the operation
            process_item: callback to generate op for a single union item (arg is coerced
                to union item type)
            line: line number
        """
        # TODO: Optimize cases where a single operation can handle multiple union items
        #     (say a method is implemented in a common base class)
        fast_items = []
        rest_items = []
        for item in rtype.items:
            if isinstance(item, RInstance):
                fast_items.append(item)
            else:
                # For everything but RInstance we fall back to C API
                rest_items.append(item)
        exit_block = BasicBlock()
        result = self.alloc_temp(result_type)
        for i, item in enumerate(fast_items):
            more_types = i < len(fast_items) - 1 or rest_items
            if more_types:
                # We are not at the final item so we need one more branch
                op = self.isinstance_native(obj, item.class_ir, line)
                true_block, false_block = BasicBlock(), BasicBlock()
                self.add_bool_branch(op, true_block, false_block)
                self.activate_block(true_block)
            coerced = self.coerce(obj, item, line)
            temp = process_item(coerced)
            temp2 = self.coerce(temp, result_type, line)
            self.add(Assign(result, temp2))
            self.goto(exit_block)
            if more_types:
                self.activate_block(false_block)
        if rest_items:
            # For everything else we use generic operation. Use force=True to drop the
            # union type.
            coerced = self.coerce(obj, object_rprimitive, line, force=True)
            temp = process_item(coerced)
            temp2 = self.coerce(temp, result_type, line)
            self.add(Assign(result, temp2))
            self.goto(exit_block)
        self.activate_block(exit_block)
        return result

    def isinstance_helper(self, obj: Value, class_irs: List[ClassIR], line: int) -> Value:
        """Fast path for isinstance() that checks against a list of native classes."""
        if not class_irs:
            return self.primitive_op(false_op, [], line)
        ret = self.isinstance_native(obj, class_irs[0], line)
        for class_ir in class_irs[1:]:
            def other() -> Value:
                return self.isinstance_native(obj, class_ir, line)
            ret = self.shortcircuit_helper('or', bool_rprimitive, lambda: ret, other, line)
        return ret

    def isinstance_native(self, obj: Value, class_ir: ClassIR, line: int) -> Value:
        """Fast isinstance() check for a native class.

        If there three or less concrete (non-trait) classes among the class and all
        its children, use even faster type comparison checks `type(obj) is typ`.
        """
        concrete = all_concrete_classes(class_ir)
        if concrete is None or len(concrete) > FAST_ISINSTANCE_MAX_SUBCLASSES + 1:
            return self.primitive_op(fast_isinstance_op,
                                     [obj, self.get_native_type(class_ir)],
                                     line)
        if not concrete:
            # There can't be any concrete instance that matches this.
            return self.primitive_op(false_op, [], line)
        type_obj = self.get_native_type(concrete[0])
        ret = self.primitive_op(type_is_op, [obj, type_obj], line)
        for c in concrete[1:]:
            def other() -> Value:
                return self.primitive_op(type_is_op, [obj, self.get_native_type(c)], line)
            ret = self.shortcircuit_helper('or', bool_rprimitive, lambda: ret, other, line)
        return ret

    def get_native_type(self, cls: ClassIR) -> Value:
        fullname = '%s.%s' % (cls.module_name, cls.name)
        return self.load_native_type_object(fullname)

    def py_get_attr(self, obj: Value, attr: str, line: int) -> Value:
        key = self.load_static_unicode(attr)
        return self.add(PrimitiveOp([obj, key], py_getattr_op, line))

    def py_call(self,
                function: Value,
                arg_values: List[Value],
                line: int,
                arg_kinds: Optional[List[int]] = None,
                arg_names: Optional[Sequence[Optional[str]]] = None) -> Value:
        """Use py_call_op or py_call_with_kwargs_op for function call."""
        # If all arguments are positional, we can use py_call_op.
        if (arg_kinds is None) or all(kind == ARG_POS for kind in arg_kinds):
            return self.primitive_op(py_call_op, [function] + arg_values, line)

        # Otherwise fallback to py_call_with_kwargs_op.
        assert arg_names is not None

        pos_arg_values = []
        kw_arg_key_value_pairs = []  # type: List[DictEntry]
        star_arg_values = []
        for value, kind, name in zip(arg_values, arg_kinds, arg_names):
            if kind == ARG_POS:
                pos_arg_values.append(value)
            elif kind == ARG_NAMED:
                assert name is not None
                key = self.load_static_unicode(name)
                kw_arg_key_value_pairs.append((key, value))
            elif kind == ARG_STAR:
                star_arg_values.append(value)
            elif kind == ARG_STAR2:
                # NOTE: mypy currently only supports a single ** arg, but python supports multiple.
                # This code supports multiple primarily to make the logic easier to follow.
                kw_arg_key_value_pairs.append((None, value))
            else:
                assert False, ("Argument kind should not be possible:", kind)

        if len(star_arg_values) == 0:
            # We can directly construct a tuple if there are no star args.
            pos_args_tuple = self.primitive_op(new_tuple_op, pos_arg_values, line)
        else:
            # Otherwise we construct a list and call extend it with the star args, since tuples
            # don't have an extend method.
            pos_args_list = self.primitive_op(new_list_op, pos_arg_values, line)
            for star_arg_value in star_arg_values:
                self.primitive_op(list_extend_op, [pos_args_list, star_arg_value], line)
            pos_args_tuple = self.primitive_op(list_tuple_op, [pos_args_list], line)

        kw_args_dict = self.make_dict(kw_arg_key_value_pairs, line)

        return self.primitive_op(
            py_call_with_kwargs_op, [function, pos_args_tuple, kw_args_dict], line)

    def py_method_call(self,
                       obj: Value,
                       method_name: str,
                       arg_values: List[Value],
                       line: int,
                       arg_kinds: Optional[List[int]],
                       arg_names: Optional[Sequence[Optional[str]]]) -> Value:
        if (arg_kinds is None) or all(kind == ARG_POS for kind in arg_kinds):
            method_name_reg = self.load_static_unicode(method_name)
            return self.primitive_op(py_method_call_op, [obj, method_name_reg] + arg_values, line)
        else:
            method = self.py_get_attr(obj, method_name, line)
            return self.py_call(method, arg_values, line, arg_kinds=arg_kinds, arg_names=arg_names)

    def call(self, decl: FuncDecl, args: Sequence[Value],
             arg_kinds: List[int],
             arg_names: Sequence[Optional[str]],
             line: int) -> Value:
        # Normalize args to positionals.
        args = self.native_args_to_positional(
            args, arg_kinds, arg_names, decl.sig, line)
        return self.add(Call(decl, args, line))

    def visit_call_expr(self, expr: CallExpr) -> Value:
        if isinstance(expr.analyzed, CastExpr):
            return self.translate_cast_expr(expr.analyzed)

        callee = expr.callee
        if isinstance(callee, IndexExpr) and isinstance(callee.analyzed, TypeApplication):
            callee = callee.analyzed.expr  # Unwrap type application

        if isinstance(callee, MemberExpr):
            return self.translate_method_call(expr, callee)
        elif isinstance(callee, SuperExpr):
            return self.translate_super_method_call(expr, callee)
        else:
            return self.translate_call(expr, callee)

    def translate_call(self, expr: CallExpr, callee: Expression) -> Value:
        # The common case of calls is refexprs
        if isinstance(callee, RefExpr):
            return self.translate_refexpr_call(expr, callee)

        function = self.accept(callee)
        args = [self.accept(arg) for arg in expr.args]
        return self.py_call(function, args, expr.line,
                            arg_kinds=expr.arg_kinds, arg_names=expr.arg_names)

    def translate_refexpr_call(self, expr: CallExpr, callee: RefExpr) -> Value:
        """Translate a non-method call."""

        # TODO: Allow special cases to have default args or named args. Currently they don't since
        # they check that everything in arg_kinds is ARG_POS.

        # If there is a specializer for this function, try calling it.
        if callee.fullname and (callee.fullname, None) in specializers:
            val = specializers[callee.fullname, None](self, expr, callee)
            if val is not None:
                return val

        # Gen the argument values
        arg_values = [self.accept(arg) for arg in expr.args]

        return self.call_refexpr_with_args(expr, callee, arg_values)

    def call_refexpr_with_args(
            self, expr: CallExpr, callee: RefExpr, arg_values: List[Value]) -> Value:

        # Handle data-driven special-cased primitive call ops.
        if callee.fullname is not None and expr.arg_kinds == [ARG_POS] * len(arg_values):
            ops = func_ops.get(callee.fullname, [])
            target = self.matching_primitive_op(ops, arg_values, expr.line, self.node_type(expr))
            if target:
                return target

        # Standard native call if signature and fullname are good and all arguments are positional
        # or named.
        callee_node = callee.node
        if isinstance(callee_node, OverloadedFuncDef):
            callee_node = callee_node.impl
        if (callee_node is not None
                and callee.fullname is not None
                and callee_node in self.mapper.func_to_decl
                and all(kind in (ARG_POS, ARG_NAMED) for kind in expr.arg_kinds)):
            decl = self.mapper.func_to_decl[callee_node]
            return self.call(decl, arg_values, expr.arg_kinds, expr.arg_names, expr.line)

        # Fall back to a Python call
        function = self.accept(callee)
        return self.py_call(function, arg_values, expr.line,
                            arg_kinds=expr.arg_kinds, arg_names=expr.arg_names)

    def translate_method_call(self, expr: CallExpr, callee: MemberExpr) -> Value:
        """Generate IR for an arbitrary call of form e.m(...).

        This can also deal with calls to module-level functions.
        """
        if self.is_native_ref_expr(callee):
            # Call to module-level native function or such
            return self.translate_call(expr, callee)
        elif (
            isinstance(callee.expr, RefExpr)
            and isinstance(callee.expr.node, TypeInfo)
            and callee.expr.node in self.mapper.type_to_ir
            and self.mapper.type_to_ir[callee.expr.node].has_method(callee.name)
        ):
            # Call a method via the *class*
            assert isinstance(callee.expr.node, TypeInfo)
            ir = self.mapper.type_to_ir[callee.expr.node]
            decl = ir.method_decl(callee.name)
            args = []
            arg_kinds, arg_names = expr.arg_kinds[:], expr.arg_names[:]
            # Add the class argument for class methods in extension classes
            if decl.kind == FUNC_CLASSMETHOD and ir.is_ext_class:
                args.append(self.load_native_type_object(callee.expr.node.fullname))
                arg_kinds.insert(0, ARG_POS)
                arg_names.insert(0, None)
            args += [self.accept(arg) for arg in expr.args]

            if ir.is_ext_class:
                return self.call(decl, args, arg_kinds, arg_names, expr.line)
            else:
                obj = self.accept(callee.expr)
                return self.gen_method_call(obj,
                                            callee.name,
                                            args,
                                            self.node_type(expr),
                                            expr.line,
                                            expr.arg_kinds,
                                            expr.arg_names)

        elif self.is_module_member_expr(callee):
            # Fall back to a PyCall for non-native module calls
            function = self.accept(callee)
            args = [self.accept(arg) for arg in expr.args]
            return self.py_call(function, args, expr.line,
                                arg_kinds=expr.arg_kinds, arg_names=expr.arg_names)
        else:
            receiver_typ = self.node_type(callee.expr)

            # If there is a specializer for this method name/type, try calling it.
            if (callee.name, receiver_typ) in specializers:
                val = specializers[callee.name, receiver_typ](self, expr, callee)
                if val is not None:
                    return val

            obj = self.accept(callee.expr)
            args = [self.accept(arg) for arg in expr.args]
            return self.gen_method_call(obj,
                                        callee.name,
                                        args,
                                        self.node_type(expr),
                                        expr.line,
                                        expr.arg_kinds,
                                        expr.arg_names)

    def translate_super_method_call(self, expr: CallExpr, callee: SuperExpr) -> Value:
        if callee.info is None or callee.call.args:
            return self.translate_call(expr, callee)
        ir = self.mapper.type_to_ir[callee.info]
        # Search for the method in the mro, skipping ourselves.
        for base in ir.mro[1:]:
            if callee.name in base.method_decls:
                break
        else:
            return self.translate_call(expr, callee)

        decl = base.method_decl(callee.name)
        arg_values = [self.accept(arg) for arg in expr.args]
        arg_kinds, arg_names = expr.arg_kinds[:], expr.arg_names[:]

        if decl.kind != FUNC_STATICMETHOD:
            vself = next(iter(self.environment.indexes))  # grab first argument
            if decl.kind == FUNC_CLASSMETHOD:
                vself = self.primitive_op(type_op, [vself], expr.line)
            elif self.fn_info.is_generator:
                # For generator classes, the self target is the 6th value
                # in the symbol table (which is an ordered dict). This is sort
                # of ugly, but we can't search by name since the 'self' parameter
                # could be named anything, and it doesn't get added to the
                # environment indexes.
                self_targ = list(self.environment.symtable.values())[6]
                vself = self.read(self_targ, self.fn_info.fitem.line)
            arg_values.insert(0, vself)
            arg_kinds.insert(0, ARG_POS)
            arg_names.insert(0, None)

        return self.call(decl, arg_values, arg_kinds, arg_names, expr.line)

    def gen_method_call(self,
                        base: Value,
                        name: str,
                        arg_values: List[Value],
                        return_rtype: Optional[RType],
                        line: int,
                        arg_kinds: Optional[List[int]] = None,
                        arg_names: Optional[List[Optional[str]]] = None) -> Value:
        # If arg_kinds contains values other than arg_pos and arg_named, then fallback to
        # Python method call.
        if (arg_kinds is not None
                and not all(kind in (ARG_POS, ARG_NAMED) for kind in arg_kinds)):
            return self.py_method_call(base, name, arg_values, base.line, arg_kinds, arg_names)

        # If the base type is one of ours, do a MethodCall
        if (isinstance(base.type, RInstance) and base.type.class_ir.is_ext_class
                and not base.type.class_ir.builtin_base):
            if base.type.class_ir.has_method(name):
                decl = base.type.class_ir.method_decl(name)
                if arg_kinds is None:
                    assert arg_names is None, "arg_kinds not present but arg_names is"
                    arg_kinds = [ARG_POS for _ in arg_values]
                    arg_names = [None for _ in arg_values]
                else:
                    assert arg_names is not None, "arg_kinds present but arg_names is not"

                # Normalize args to positionals.
                assert decl.bound_sig
                arg_values = self.native_args_to_positional(
                    arg_values, arg_kinds, arg_names, decl.bound_sig, line)
                return self.add(MethodCall(base, name, arg_values, line))
            elif base.type.class_ir.has_attr(name):
                function = self.add(GetAttr(base, name, line))
                return self.py_call(function, arg_values, line,
                                    arg_kinds=arg_kinds, arg_names=arg_names)

        elif isinstance(base.type, RUnion):
            return self.union_method_call(base, base.type, name, arg_values, return_rtype, line,
                                          arg_kinds, arg_names)

        # Try to do a special-cased method call
        if not arg_kinds or arg_kinds == [ARG_POS] * len(arg_values):
            target = self.translate_special_method_call(base, name, arg_values, return_rtype, line)
            if target:
                return target

        # Fall back to Python method call
        return self.py_method_call(base, name, arg_values, line, arg_kinds, arg_names)

    def union_method_call(self,
                          base: Value,
                          obj_type: RUnion,
                          name: str,
                          arg_values: List[Value],
                          return_rtype: Optional[RType],
                          line: int,
                          arg_kinds: Optional[List[int]],
                          arg_names: Optional[List[Optional[str]]]) -> Value:
        # Union method call needs a return_rtype for the type of the output register.
        # If we don't have one, use object_rprimitive.
        return_rtype = return_rtype or object_rprimitive

        def call_union_item(value: Value) -> Value:
            return self.gen_method_call(value, name, arg_values, return_rtype, line,
                                        arg_kinds, arg_names)

        return self.decompose_union_helper(base, obj_type, return_rtype, call_union_item, line)

    def translate_cast_expr(self, expr: CastExpr) -> Value:
        src = self.accept(expr.expr)
        target_type = self.type_to_rtype(expr.type)
        return self.coerce(src, target_type, expr.line)

    def shortcircuit_helper(self, op: str,
                            expr_type: RType,
                            left: Callable[[], Value],
                            right: Callable[[], Value], line: int) -> Value:
        # Having actual Phi nodes would be really nice here!
        target = self.alloc_temp(expr_type)
        # left_body takes the value of the left side, right_body the right
        left_body, right_body, next = BasicBlock(), BasicBlock(), BasicBlock()
        # true_body is taken if the left is true, false_body if it is false.
        # For 'and' the value is the right side if the left is true, and for 'or'
        # it is the right side if the left is false.
        true_body, false_body = (
            (right_body, left_body) if op == 'and' else (left_body, right_body))

        left_value = left()
        self.add_bool_branch(left_value, true_body, false_body)

        self.activate_block(left_body)
        left_coerced = self.coerce(left_value, expr_type, line)
        self.add(Assign(target, left_coerced))
        self.goto(next)

        self.activate_block(right_body)
        right_value = right()
        right_coerced = self.coerce(right_value, expr_type, line)
        self.add(Assign(target, right_coerced))
        self.goto(next)

        self.activate_block(next)
        return target

    def shortcircuit_expr(self, expr: OpExpr) -> Value:
        return self.shortcircuit_helper(
            expr.op, self.node_type(expr),
            lambda: self.accept(expr.left),
            lambda: self.accept(expr.right),
            expr.line
        )

    def visit_conditional_expr(self, expr: ConditionalExpr) -> Value:
        if_body, else_body, next = BasicBlock(), BasicBlock(), BasicBlock()

        self.process_conditional(expr.cond, if_body, else_body)
        expr_type = self.node_type(expr)
        # Having actual Phi nodes would be really nice here!
        target = self.alloc_temp(expr_type)

        self.activate_block(if_body)
        true_value = self.accept(expr.if_expr)
        true_value = self.coerce(true_value, expr_type, expr.line)
        self.add(Assign(target, true_value))
        self.goto(next)

        self.activate_block(else_body)
        false_value = self.accept(expr.else_expr)
        false_value = self.coerce(false_value, expr_type, expr.line)
        self.add(Assign(target, false_value))
        self.goto(next)

        self.activate_block(next)

        return target

    def translate_special_method_call(self,
                                      base_reg: Value,
                                      name: str,
                                      args: List[Value],
                                      result_type: Optional[RType],
                                      line: int) -> Optional[Value]:
        """Translate a method call which is handled nongenerically.

        These are special in the sense that we have code generated specifically for them.
        They tend to be method calls which have equivalents in C that are more direct
        than calling with the PyObject api.

        Return None if no translation found; otherwise return the target register.
        """
        ops = method_ops.get(name, [])
        return self.matching_primitive_op(ops, [base_reg] + args, line, result_type=result_type)

    def visit_list_expr(self, expr: ListExpr) -> Value:
        return self._visit_list_display(expr.items, expr.line)

    def _visit_list_display(self, items: List[Expression], line: int) -> Value:
        return self._visit_display(
            items,
            new_list_op,
            list_append_op,
            list_extend_op,
            line
        )

    def _visit_display(self,
                       items: List[Expression],
                       constructor_op: OpDescription,
                       append_op: OpDescription,
                       extend_op: OpDescription,
                       line: int
                       ) -> Value:
        accepted_items = []
        for item in items:
            if isinstance(item, StarExpr):
                accepted_items.append((True, self.accept(item.expr)))
            else:
                accepted_items.append((False, self.accept(item)))

        result = None  # type: Union[Value, None]
        initial_items = []
        for starred, value in accepted_items:
            if result is None and not starred and constructor_op.is_var_arg:
                initial_items.append(value)
                continue

            if result is None:
                result = self.primitive_op(constructor_op, initial_items, line)

            self.primitive_op(extend_op if starred else append_op, [result, value], line)

        if result is None:
            result = self.primitive_op(constructor_op, initial_items, line)

        return result

    def visit_tuple_expr(self, expr: TupleExpr) -> Value:
        if any(isinstance(item, StarExpr) for item in expr.items):
            # create a tuple of unknown length
            return self._visit_tuple_display(expr)

        # create a tuple of fixed length (RTuple)
        tuple_type = self.node_type(expr)
        # When handling NamedTuple et. al we might not have proper type info,
        # so make some up if we need it.
        types = (tuple_type.types if isinstance(tuple_type, RTuple)
                 else [object_rprimitive] * len(expr.items))

        items = []
        for item_expr, item_type in zip(expr.items, types):
            reg = self.accept(item_expr)
            items.append(self.coerce(reg, item_type, item_expr.line))
        return self.add(TupleSet(items, expr.line))

    def _visit_tuple_display(self, expr: TupleExpr) -> Value:
        """Create a list, then turn it into a tuple."""
        val_as_list = self._visit_list_display(expr.items, expr.line)
        return self.primitive_op(list_tuple_op, [val_as_list], expr.line)

    def visit_dict_expr(self, expr: DictExpr) -> Value:
        """First accepts all keys and values, then makes a dict out of them."""
        key_value_pairs = []
        for key_expr, value_expr in expr.items:
            key = self.accept(key_expr) if key_expr is not None else None
            value = self.accept(value_expr)
            key_value_pairs.append((key, value))

        return self.make_dict(key_value_pairs, expr.line)

    def visit_set_expr(self, expr: SetExpr) -> Value:
        return self._visit_display(
            expr.items,
            new_set_op,
            set_add_op,
            set_update_op,
            expr.line
        )

    def visit_str_expr(self, expr: StrExpr) -> Value:
        return self.load_static_unicode(expr.value)

    # Conditional expressions

    def process_conditional(self, e: Expression, true: BasicBlock, false: BasicBlock) -> None:
        if isinstance(e, OpExpr) and e.op in ['and', 'or']:
            if e.op == 'and':
                # Short circuit 'and' in a conditional context.
                new = BasicBlock()
                self.process_conditional(e.left, new, false)
                self.activate_block(new)
                self.process_conditional(e.right, true, false)
            else:
                # Short circuit 'or' in a conditional context.
                new = BasicBlock()
                self.process_conditional(e.left, true, new)
                self.activate_block(new)
                self.process_conditional(e.right, true, false)
        elif isinstance(e, UnaryExpr) and e.op == 'not':
            self.process_conditional(e.expr, false, true)
        # Catch-all for arbitrary expressions.
        else:
            reg = self.accept(e)
            self.add_bool_branch(reg, true, false)

    def visit_basic_comparison(self, op: str, left: Value, right: Value, line: int) -> Value:
        negate = False
        if op == 'is not':
            op, negate = 'is', True
        elif op == 'not in':
            op, negate = 'in', True

        target = self.binary_op(left, right, op, line)

        if negate:
            target = self.unary_op(target, 'not', line)
        return target

    def visit_comparison_expr(self, e: ComparisonExpr) -> Value:
        # TODO: Don't produce an expression when used in conditional context

        # All of the trickiness here is due to support for chained conditionals
        # (`e1 < e2 > e3`, etc). `e1 < e2 > e3` is approximately equivalent to
        # `e1 < e2 and e2 > e3` except that `e2` is only evaluated once.
        expr_type = self.node_type(e)

        # go(i, prev) generates code for `ei opi e{i+1} op{i+1} ... en`,
        # assuming that prev contains the value of `ei`.
        def go(i: int, prev: Value) -> Value:
            if i == len(e.operators) - 1:
                return self.visit_basic_comparison(
                    e.operators[i], prev, self.accept(e.operands[i + 1]), e.line)

            next = self.accept(e.operands[i + 1])
            return self.shortcircuit_helper(
                'and', expr_type,
                lambda: self.visit_basic_comparison(
                    e.operators[i], prev, next, e.line),
                lambda: go(i + 1, next),
                e.line)

        return go(0, self.accept(e.operands[0]))

    def add_bool_branch(self, value: Value, true: BasicBlock, false: BasicBlock) -> None:
        if is_runtime_subtype(value.type, int_rprimitive):
            zero = self.add(LoadInt(0))
            value = self.binary_op(value, zero, '!=', value.line)
        elif is_same_type(value.type, list_rprimitive):
            length = self.primitive_op(list_len_op, [value], value.line)
            zero = self.add(LoadInt(0))
            value = self.binary_op(length, zero, '!=', value.line)
        elif (isinstance(value.type, RInstance) and value.type.class_ir.is_ext_class
                and value.type.class_ir.has_method('__bool__')):
            # Directly call the __bool__ method on classes that have it.
            value = self.gen_method_call(value, '__bool__', [], bool_rprimitive, value.line)
        else:
            value_type = optional_value_type(value.type)
            if value_type is not None:
                is_none = self.binary_op(value, self.none_object(), 'is not', value.line)
                branch = Branch(is_none, true, false, Branch.BOOL_EXPR)
                self.add(branch)
                always_truthy = False
                if isinstance(value_type, RInstance):
                    # check whether X.__bool__ is always just the default (object.__bool__)
                    if (not value_type.class_ir.has_method('__bool__')
                            and value_type.class_ir.is_method_final('__bool__')):
                        always_truthy = True

                if not always_truthy:
                    # Optional[X] where X may be falsey and requires a check
                    branch.true = self.new_block()
                    # unbox_or_cast instead of coerce because we want the
                    # type to change even if it is a subtype.
                    remaining = self.unbox_or_cast(value, value_type, value.line)
                    self.add_bool_branch(remaining, true, false)
                return
            elif not is_same_type(value.type, bool_rprimitive):
                value = self.primitive_op(bool_op, [value], value.line)
        self.add(Branch(value, true, false, Branch.BOOL_EXPR))

    def visit_nonlocal_decl(self, o: NonlocalDecl) -> None:
        pass

    def visit_slice_expr(self, expr: SliceExpr) -> Value:
        def get_arg(arg: Optional[Expression]) -> Value:
            if arg is None:
                return self.none_object()
            else:
                return self.accept(arg)

        args = [get_arg(expr.begin_index),
                get_arg(expr.end_index),
                get_arg(expr.stride)]
        return self.primitive_op(new_slice_op, args, expr.line)

    def visit_raise_stmt(self, s: RaiseStmt) -> None:
        if s.expr is None:
            self.primitive_op(reraise_exception_op, [], NO_TRACEBACK_LINE_NO)
            self.add(Unreachable())
            return

        exc = self.accept(s.expr)
        self.primitive_op(raise_exception_op, [exc], s.line)
        self.add(Unreachable())

    def visit_try_except(self,
                         body: GenFunc,
                         handlers: Sequence[
                             Tuple[Optional[Expression], Optional[Expression], GenFunc]],
                         else_body: Optional[GenFunc],
                         line: int) -> None:
        """Generalized try/except/else handling that takes functions to gen the bodies.

        The point of this is to also be able to support with."""
        assert handlers, "try needs except"

        except_entry, exit_block, cleanup_block = BasicBlock(), BasicBlock(), BasicBlock()
        double_except_block = BasicBlock()
        # If there is an else block, jump there after the try, otherwise just leave
        else_block = BasicBlock() if else_body else exit_block

        # Compile the try block with an error handler
        self.error_handlers.append(except_entry)
        self.goto_and_activate(BasicBlock())
        body()
        self.goto(else_block)
        self.error_handlers.pop()

        # The error handler catches the error and then checks it
        # against the except clauses. We compile the error handler
        # itself with an error handler so that it can properly restore
        # the *old* exc_info if an exception occurs.
        # The exception chaining will be done automatically when the
        # exception is raised, based on the exception in exc_info.
        self.error_handlers.append(double_except_block)
        self.activate_block(except_entry)
        old_exc = self.maybe_spill(self.primitive_op(error_catch_op, [], line))
        # Compile the except blocks with the nonlocal control flow overridden to clear exc_info
        self.nonlocal_control.append(
            ExceptNonlocalControl(self.nonlocal_control[-1], old_exc))

        # Process the bodies
        for type, var, handler_body in handlers:
            next_block = None
            if type:
                next_block, body_block = BasicBlock(), BasicBlock()
                matches = self.primitive_op(exc_matches_op, [self.accept(type)], type.line)
                self.add(Branch(matches, body_block, next_block, Branch.BOOL_EXPR))
                self.activate_block(body_block)
            if var:
                target = self.get_assignment_target(var)
                self.assign(target, self.primitive_op(get_exc_value_op, [], var.line), var.line)
            handler_body()
            self.goto(cleanup_block)
            if next_block:
                self.activate_block(next_block)

        # Reraise the exception if needed
        if next_block:
            self.primitive_op(reraise_exception_op, [], NO_TRACEBACK_LINE_NO)
            self.add(Unreachable())

        self.nonlocal_control.pop()
        self.error_handlers.pop()

        # Cleanup for if we leave except through normal control flow:
        # restore the saved exc_info information and continue propagating
        # the exception if it exists.
        self.activate_block(cleanup_block)
        self.primitive_op(restore_exc_info_op, [self.read(old_exc)], line)
        self.goto(exit_block)

        # Cleanup for if we leave except through a raised exception:
        # restore the saved exc_info information and continue propagating
        # the exception.
        self.activate_block(double_except_block)
        self.primitive_op(restore_exc_info_op, [self.read(old_exc)], line)
        self.primitive_op(keep_propagating_op, [], NO_TRACEBACK_LINE_NO)
        self.add(Unreachable())

        # If present, compile the else body in the obvious way
        if else_body:
            self.activate_block(else_block)
            else_body()
            self.goto(exit_block)

        self.activate_block(exit_block)

    def visit_try_except_stmt(self, t: TryStmt) -> None:
        def body() -> None:
            self.accept(t.body)

        # Work around scoping woes
        def make_handler(body: Block) -> GenFunc:
            return lambda: self.accept(body)

        handlers = [(type, var, make_handler(body)) for type, var, body in
                    zip(t.types, t.vars, t.handlers)]
        else_body = (lambda: self.accept(t.else_body)) if t.else_body else None
        self.visit_try_except(body, handlers, else_body, t.line)

    def try_finally_try(self, err_handler: BasicBlock, return_entry: BasicBlock,
                        main_entry: BasicBlock, try_body: GenFunc) -> Optional[Register]:
        # Compile the try block with an error handler
        control = TryFinallyNonlocalControl(return_entry)
        self.error_handlers.append(err_handler)

        self.nonlocal_control.append(control)
        self.goto_and_activate(BasicBlock())
        try_body()
        self.goto(main_entry)
        self.nonlocal_control.pop()
        self.error_handlers.pop()

        return control.ret_reg

    def try_finally_entry_blocks(self,
                                 err_handler: BasicBlock, return_entry: BasicBlock,
                                 main_entry: BasicBlock, finally_block: BasicBlock,
                                 ret_reg: Optional[Register]) -> Value:
        old_exc = self.alloc_temp(exc_rtuple)

        # Entry block for non-exceptional flow
        self.activate_block(main_entry)
        if ret_reg:
            self.add(Assign(ret_reg, self.add(LoadErrorValue(self.ret_types[-1]))))
        self.goto(return_entry)

        self.activate_block(return_entry)
        self.add(Assign(old_exc, self.add(LoadErrorValue(exc_rtuple))))
        self.goto(finally_block)

        # Entry block for errors
        self.activate_block(err_handler)
        if ret_reg:
            self.add(Assign(ret_reg, self.add(LoadErrorValue(self.ret_types[-1]))))
        self.add(Assign(old_exc, self.primitive_op(error_catch_op, [], -1)))
        self.goto(finally_block)

        return old_exc

    def try_finally_body(
            self, finally_block: BasicBlock, finally_body: GenFunc,
            ret_reg: Optional[Value], old_exc: Value) -> Tuple[BasicBlock,
                                                               'FinallyNonlocalControl']:
        cleanup_block = BasicBlock()
        # Compile the finally block with the nonlocal control flow overridden to restore exc_info
        self.error_handlers.append(cleanup_block)
        finally_control = FinallyNonlocalControl(
            self.nonlocal_control[-1], ret_reg, old_exc)
        self.nonlocal_control.append(finally_control)
        self.activate_block(finally_block)
        finally_body()
        self.nonlocal_control.pop()

        return cleanup_block, finally_control

    def try_finally_resolve_control(self, cleanup_block: BasicBlock,
                                    finally_control: FinallyNonlocalControl,
                                    old_exc: Value, ret_reg: Optional[Value]) -> BasicBlock:
        """Resolve the control flow out of a finally block.

        This means returning if there was a return, propagating
        exceptions, break/continue (soon), or just continuing on.
        """
        reraise, rest = BasicBlock(), BasicBlock()
        self.add(Branch(old_exc, rest, reraise, Branch.IS_ERROR))

        # Reraise the exception if there was one
        self.activate_block(reraise)
        self.primitive_op(reraise_exception_op, [], NO_TRACEBACK_LINE_NO)
        self.add(Unreachable())
        self.error_handlers.pop()

        # If there was a return, keep returning
        if ret_reg:
            self.activate_block(rest)
            return_block, rest = BasicBlock(), BasicBlock()
            self.add(Branch(ret_reg, rest, return_block, Branch.IS_ERROR))

            self.activate_block(return_block)
            self.nonlocal_control[-1].gen_return(self, ret_reg, -1)

        # TODO: handle break/continue
        self.activate_block(rest)
        out_block = BasicBlock()
        self.goto(out_block)

        # If there was an exception, restore again
        self.activate_block(cleanup_block)
        finally_control.gen_cleanup(self, -1)
        self.primitive_op(keep_propagating_op, [], NO_TRACEBACK_LINE_NO)
        self.add(Unreachable())

        return out_block

    def visit_try_finally_stmt(self, try_body: GenFunc, finally_body: GenFunc) -> None:
        """Generalized try/finally handling that takes functions to gen the bodies.

        The point of this is to also be able to support with."""
        # Finally is a big pain, because there are so many ways that
        # exits can occur. We emit 10+ basic blocks for every finally!

        err_handler, main_entry, return_entry, finally_block = (
            BasicBlock(), BasicBlock(), BasicBlock(), BasicBlock())

        # Compile the body of the try
        ret_reg = self.try_finally_try(
            err_handler, return_entry, main_entry, try_body)

        # Set up the entry blocks for the finally statement
        old_exc = self.try_finally_entry_blocks(
            err_handler, return_entry, main_entry, finally_block, ret_reg)

        # Compile the body of the finally
        cleanup_block, finally_control = self.try_finally_body(
            finally_block, finally_body, ret_reg, old_exc)

        # Resolve the control flow out of the finally block
        out_block = self.try_finally_resolve_control(
            cleanup_block, finally_control, old_exc, ret_reg)

        self.activate_block(out_block)

    def visit_try_stmt(self, t: TryStmt) -> None:
        # Our compilation strategy for try/except/else/finally is to
        # treat try/except/else and try/finally as separate language
        # constructs that we compile separately. When we have a
        # try/except/else/finally, we treat the try/except/else as the
        # body of a try/finally block.
        if t.finally_body:
            def visit_try_body() -> None:
                if t.handlers:
                    self.visit_try_except_stmt(t)
                else:
                    self.accept(t.body)
            body = t.finally_body

            self.visit_try_finally_stmt(visit_try_body, lambda: self.accept(body))
        else:
            self.visit_try_except_stmt(t)

    def get_sys_exc_info(self) -> List[Value]:
        exc_info = self.primitive_op(get_exc_info_op, [], -1)
        return [self.add(TupleGet(exc_info, i, -1)) for i in range(3)]

    def visit_with(self, expr: Expression, target: Optional[Lvalue],
                   body: GenFunc, line: int) -> None:

        # This is basically a straight transcription of the Python code in PEP 343.
        # I don't actually understand why a bunch of it is the way it is.
        # We could probably optimize the case where the manager is compiled by us,
        # but that is not our common case at all, so.
        mgr_v = self.accept(expr)
        typ = self.primitive_op(type_op, [mgr_v], line)
        exit_ = self.maybe_spill(self.py_get_attr(typ, '__exit__', line))
        value = self.py_call(self.py_get_attr(typ, '__enter__', line), [mgr_v], line)
        mgr = self.maybe_spill(mgr_v)
        exc = self.maybe_spill_assignable(self.primitive_op(true_op, [], -1))

        def try_body() -> None:
            if target:
                self.assign(self.get_assignment_target(target), value, line)
            body()

        def except_body() -> None:
            self.assign(exc, self.primitive_op(false_op, [], -1), line)
            out_block, reraise_block = BasicBlock(), BasicBlock()
            self.add_bool_branch(self.py_call(self.read(exit_),
                                              [self.read(mgr)] + self.get_sys_exc_info(), line),
                                 out_block, reraise_block)
            self.activate_block(reraise_block)
            self.primitive_op(reraise_exception_op, [], NO_TRACEBACK_LINE_NO)
            self.add(Unreachable())
            self.activate_block(out_block)

        def finally_body() -> None:
            out_block, exit_block = BasicBlock(), BasicBlock()
            self.add(Branch(self.read(exc), exit_block, out_block, Branch.BOOL_EXPR))
            self.activate_block(exit_block)
            none = self.none_object()
            self.py_call(self.read(exit_), [self.read(mgr), none, none, none], line)
            self.goto_and_activate(out_block)

        self.visit_try_finally_stmt(
            lambda: self.visit_try_except(try_body, [(None, None, except_body)], None, line),
            finally_body)

    def visit_with_stmt(self, o: WithStmt) -> None:
        # Generate separate logic for each expr in it, left to right
        def generate(i: int) -> None:
            if i >= len(o.expr):
                self.accept(o.body)
            else:
                self.visit_with(o.expr[i], o.target[i], lambda: generate(i + 1), o.line)

        generate(0)

    def visit_lambda_expr(self, expr: LambdaExpr) -> Value:
        return BuildFuncIR(self).visit_lambda_expr(expr)

    def visit_pass_stmt(self, o: PassStmt) -> None:
        pass

    def visit_global_decl(self, o: GlobalDecl) -> None:
        # Pure declaration -- no runtime effect
        pass

    def visit_assert_stmt(self, a: AssertStmt) -> None:
        if self.options.strip_asserts:
            return
        cond = self.accept(a.expr)
        ok_block, error_block = BasicBlock(), BasicBlock()
        self.add_bool_branch(cond, ok_block, error_block)
        self.activate_block(error_block)
        if a.msg is None:
            # Special case (for simpler generated code)
            self.add(RaiseStandardError(RaiseStandardError.ASSERTION_ERROR, None, a.line))
        elif isinstance(a.msg, StrExpr):
            # Another special case
            self.add(RaiseStandardError(RaiseStandardError.ASSERTION_ERROR, a.msg.value,
                                        a.line))
        else:
            # The general case -- explicitly construct an exception instance
            message = self.accept(a.msg)
            exc_type = self.load_module_attr_by_fullname('builtins.AssertionError', a.line)
            exc = self.py_call(exc_type, [message], a.line)
            self.primitive_op(raise_exception_op, [exc], a.line)
        self.add(Unreachable())
        self.activate_block(ok_block)

    def translate_list_comprehension(self, gen: GeneratorExpr) -> Value:
        list_ops = self.primitive_op(new_list_op, [], gen.line)
        loop_params = list(zip(gen.indices, gen.sequences, gen.condlists))

        def gen_inner_stmts() -> None:
            e = self.accept(gen.left_expr)
            self.primitive_op(list_append_op, [list_ops, e], gen.line)

        self.comprehension_helper(loop_params, gen_inner_stmts, gen.line)
        return list_ops

    def visit_list_comprehension(self, o: ListComprehension) -> Value:
        return self.translate_list_comprehension(o.generator)

    def visit_set_comprehension(self, o: SetComprehension) -> Value:
        gen = o.generator
        set_ops = self.primitive_op(new_set_op, [], o.line)
        loop_params = list(zip(gen.indices, gen.sequences, gen.condlists))

        def gen_inner_stmts() -> None:
            e = self.accept(gen.left_expr)
            self.primitive_op(set_add_op, [set_ops, e], o.line)

        self.comprehension_helper(loop_params, gen_inner_stmts, o.line)
        return set_ops

    def visit_dictionary_comprehension(self, o: DictionaryComprehension) -> Value:
        d = self.primitive_op(new_dict_op, [], o.line)
        loop_params = list(zip(o.indices, o.sequences, o.condlists))

        def gen_inner_stmts() -> None:
            k = self.accept(o.key)
            v = self.accept(o.value)
            self.primitive_op(dict_set_item_op, [d, k, v], o.line)

        self.comprehension_helper(loop_params, gen_inner_stmts, o.line)
        return d

    def visit_generator_expr(self, o: GeneratorExpr) -> Value:
        self.warning('Treating generator comprehension as list', o.line)
        return self.primitive_op(iter_op, [self.translate_list_comprehension(o)], o.line)

    def comprehension_helper(self,
                             loop_params: List[Tuple[Lvalue, Expression, List[Expression]]],
                             gen_inner_stmts: Callable[[], None],
                             line: int) -> None:
        """Helper function for list comprehensions.

        "loop_params" is a list of (index, expr, [conditions]) tuples defining nested loops:
            - "index" is the Lvalue indexing that loop;
            - "expr" is the expression for the object to be iterated over;
            - "conditions" is a list of conditions, evaluated in order with short-circuiting,
                that must all be true for the loop body to be executed
        "gen_inner_stmts" is a function to generate the IR for the body of the innermost loop
        """
        def handle_loop(loop_params: List[Tuple[Lvalue, Expression, List[Expression]]]) -> None:
            """Generate IR for a loop.

            Given a list of (index, expression, [conditions]) tuples, generate IR
            for the nested loops the list defines.
            """
            index, expr, conds = loop_params[0]
            self.for_loop_helper(index, expr,
                                 lambda: loop_contents(conds, loop_params[1:]),
                                 None, line)

        def loop_contents(
                conds: List[Expression],
                remaining_loop_params: List[Tuple[Lvalue, Expression, List[Expression]]],
        ) -> None:
            """Generate the body of the loop.

            "conds" is a list of conditions to be evaluated (in order, with short circuiting)
                to gate the body of the loop.
            "remaining_loop_params" is the parameters for any further nested loops; if it's empty
                we'll instead evaluate the "gen_inner_stmts" function.
            """
            # Check conditions, in order, short circuiting them.
            for cond in conds:
                cond_val = self.accept(cond)
                cont_block, rest_block = BasicBlock(), BasicBlock()
                # If the condition is true we'll skip the continue.
                self.add_bool_branch(cond_val, rest_block, cont_block)
                self.activate_block(cont_block)
                self.nonlocal_control[-1].gen_continue(self, cond.line)
                self.goto_and_activate(rest_block)

            if remaining_loop_params:
                # There's another nested level, so the body of this loop is another loop.
                return handle_loop(remaining_loop_params)
            else:
                # We finally reached the actual body of the generator.
                # Generate the IR for the inner loop body.
                gen_inner_stmts()

        handle_loop(loop_params)

    def visit_decorator(self, dec: Decorator) -> None:
        BuildFuncIR(self).visit_decorator(dec)

    def visit_del_stmt(self, o: DelStmt) -> None:
        self.visit_del_item(self.get_assignment_target(o.expr), o.line)

    def visit_del_item(self, target: AssignmentTarget, line: int) -> None:
        if isinstance(target, AssignmentTargetIndex):
            self.translate_special_method_call(
                target.base,
                '__delitem__',
                [target.index],
                result_type=None,
                line=line
            )
        elif isinstance(target, AssignmentTargetAttr):
            key = self.load_static_unicode(target.attr)
            self.add(PrimitiveOp([target.obj, key], py_delattr_op, line))
        elif isinstance(target, AssignmentTargetRegister):
            # Delete a local by assigning an error value to it, which will
            # prompt the insertion of uninit checks.
            self.add(Assign(target.register,
                            self.add(LoadErrorValue(target.type, undefines=True))))
        elif isinstance(target, AssignmentTargetTuple):
            for subtarget in target.items:
                self.visit_del_item(subtarget, line)

    def visit_super_expr(self, o: SuperExpr) -> Value:
        # self.warning('can not optimize super() expression', o.line)
        sup_val = self.load_module_attr_by_fullname('builtins.super', o.line)
        if o.call.args:
            args = [self.accept(arg) for arg in o.call.args]
        else:
            assert o.info is not None
            typ = self.load_native_type_object(o.info.fullname)
            ir = self.mapper.type_to_ir[o.info]
            iter_env = iter(self.environment.indexes)
            vself = next(iter_env)  # grab first argument
            if self.fn_info.is_generator:
                # grab sixth argument (see comment in translate_super_method_call)
                self_targ = list(self.environment.symtable.values())[6]
                vself = self.read(self_targ, self.fn_info.fitem.line)
            elif not ir.is_ext_class:
                vself = next(iter_env)  # second argument is self if non_extension class
            args = [typ, vself]
        res = self.py_call(sup_val, args, o.line)
        return self.py_get_attr(res, o.name, o.line)

    def visit_yield_expr(self, expr: YieldExpr) -> Value:
        return BuildFuncIR(self).visit_yield_expr(expr)

    def visit_yield_from_expr(self, o: YieldFromExpr) -> Value:
        return BuildFuncIR(self).visit_yield_from_expr(o)

    def visit_ellipsis(self, o: EllipsisExpr) -> Value:
        return self.primitive_op(ellipsis_op, [], o.line)

    # Builtin function special cases

    @specialize_function('builtins.globals')
    def translate_globals(self, expr: CallExpr, callee: RefExpr) -> Optional[Value]:
        # Special case builtins.globals
        if len(expr.args) == 0:
            return self.load_globals_dict()
        return None

    @specialize_function('builtins.len')
    def translate_len(
            self, expr: CallExpr, callee: RefExpr) -> Optional[Value]:
        # Special case builtins.len
        if (len(expr.args) == 1
                and expr.arg_kinds == [ARG_POS]):
            expr_rtype = self.node_type(expr.args[0])
            if isinstance(expr_rtype, RTuple):
                # len() of fixed-length tuple can be trivially determined statically,
                # though we still need to evaluate it.
                self.accept(expr.args[0])
                return self.add(LoadInt(len(expr_rtype.types)))
        return None

    # Special cases for things that consume iterators where we know we
    # can safely compile a generator into a list.
    @specialize_function('builtins.tuple')
    @specialize_function('builtins.set')
    @specialize_function('builtins.dict')
    @specialize_function('builtins.sum')
    @specialize_function('builtins.min')
    @specialize_function('builtins.max')
    @specialize_function('builtins.sorted')
    @specialize_function('collections.OrderedDict')
    @specialize_function('join', str_rprimitive)
    @specialize_function('extend', list_rprimitive)
    @specialize_function('update', dict_rprimitive)
    @specialize_function('update', set_rprimitive)
    def translate_safe_generator_call(self, expr: CallExpr, callee: RefExpr) -> Optional[Value]:
        if (len(expr.args) > 0
                and expr.arg_kinds[0] == ARG_POS
                and isinstance(expr.args[0], GeneratorExpr)):
            if isinstance(callee, MemberExpr):
                return self.gen_method_call(
                    self.accept(callee.expr), callee.name,
                    ([self.translate_list_comprehension(expr.args[0])]
                        + [self.accept(arg) for arg in expr.args[1:]]),
                    self.node_type(expr), expr.line, expr.arg_kinds, expr.arg_names)
            else:
                return self.call_refexpr_with_args(
                    expr, callee,
                    ([self.translate_list_comprehension(expr.args[0])]
                        + [self.accept(arg) for arg in expr.args[1:]]))
        return None

    @specialize_function('builtins.any')
    def translate_any_call(self, expr: CallExpr, callee: RefExpr) -> Optional[Value]:
        if (len(expr.args) == 1
                and expr.arg_kinds == [ARG_POS]
                and isinstance(expr.args[0], GeneratorExpr)):
            return self.any_all_helper(expr.args[0], false_op, lambda x: x, true_op)
        return None

    @specialize_function('builtins.all')
    def translate_all_call(self, expr: CallExpr, callee: RefExpr) -> Optional[Value]:
        if (len(expr.args) == 1
                and expr.arg_kinds == [ARG_POS]
                and isinstance(expr.args[0], GeneratorExpr)):
            return self.any_all_helper(expr.args[0],
                                       true_op,
                                       lambda x: self.unary_op(x, 'not', expr.line),
                                       false_op)
        return None

    # Special case for 'dataclasses.field' and 'attr.Factory' function calls
    # because the results of such calls are typechecked by mypy using the types
    # of the arguments to their respective functions, resulting in attempted
    # coercions by mypyc that throw a runtime error.
    @specialize_function('dataclasses.field')
    @specialize_function('attr.Factory')
    def translate_dataclasses_field_call(self, expr: CallExpr, callee: RefExpr) -> Optional[Value]:
        self.types[expr] = AnyType(TypeOfAny.from_error)
        return None

    def any_all_helper(self,
                       gen: GeneratorExpr,
                       initial_value_op: OpDescription,
                       modify: Callable[[Value], Value],
                       new_value_op: OpDescription) -> Value:
        retval = self.alloc_temp(bool_rprimitive)
        self.assign(retval, self.primitive_op(initial_value_op, [], -1), -1)
        loop_params = list(zip(gen.indices, gen.sequences, gen.condlists))
        true_block, false_block, exit_block = BasicBlock(), BasicBlock(), BasicBlock()

        def gen_inner_stmts() -> None:
            comparison = modify(self.accept(gen.left_expr))
            self.add_bool_branch(comparison, true_block, false_block)
            self.activate_block(true_block)
            self.assign(retval, self.primitive_op(new_value_op, [], -1), -1)
            self.goto(exit_block)
            self.activate_block(false_block)

        self.comprehension_helper(loop_params, gen_inner_stmts, gen.line)
        self.goto_and_activate(exit_block)

        return retval

    # Special case for calling next() on a generator expression, an
    # idiom that shows up some in mypy.
    #
    # For example, next(x for x in l if x.id == 12, None) will
    # generate code that searches l for an element where x.id == 12
    # and produce the first such object, or None if no such element
    # exists.
    @specialize_function('builtins.next')
    def translate_next_call(self, expr: CallExpr, callee: RefExpr) -> Optional[Value]:
        if not (expr.arg_kinds in ([ARG_POS], [ARG_POS, ARG_POS])
                and isinstance(expr.args[0], GeneratorExpr)):
            return None

        gen = expr.args[0]

        retval = self.alloc_temp(self.node_type(expr))
        default_val = None
        if len(expr.args) > 1:
            default_val = self.accept(expr.args[1])

        exit_block = BasicBlock()

        def gen_inner_stmts() -> None:
            # next takes the first element of the generator, so if
            # something gets produced, we are done.
            self.assign(retval, self.accept(gen.left_expr), gen.left_expr.line)
            self.goto(exit_block)

        loop_params = list(zip(gen.indices, gen.sequences, gen.condlists))
        self.comprehension_helper(loop_params, gen_inner_stmts, gen.line)

        # Now we need the case for when nothing got hit. If there was
        # a default value, we produce it, and otherwise we raise
        # StopIteration.
        if default_val:
            self.assign(retval, default_val, gen.left_expr.line)
            self.goto(exit_block)
        else:
            self.add(RaiseStandardError(RaiseStandardError.STOP_ITERATION, None, expr.line))
            self.add(Unreachable())

        self.activate_block(exit_block)
        return retval

    @specialize_function('builtins.isinstance')
    def translate_isinstance(self, expr: CallExpr, callee: RefExpr) -> Optional[Value]:
        # Special case builtins.isinstance
        if (len(expr.args) == 2
                and expr.arg_kinds == [ARG_POS, ARG_POS]
                and isinstance(expr.args[1], (RefExpr, TupleExpr))):
            irs = self.flatten_classes(expr.args[1])
            if irs is not None:
                return self.isinstance_helper(self.accept(expr.args[0]), irs, expr.line)
        return None

    def flatten_classes(self, arg: Union[RefExpr, TupleExpr]) -> Optional[List[ClassIR]]:
        """Flatten classes in isinstance(obj, (A, (B, C))).

        If at least one item is not a reference to a native class, return None.
        """
        if isinstance(arg, RefExpr):
            if isinstance(arg.node, TypeInfo) and self.is_native_module_ref_expr(arg):
                ir = self.mapper.type_to_ir.get(arg.node)
                if ir:
                    return [ir]
            return None
        else:
            res = []  # type: List[ClassIR]
            for item in arg.items:
                if isinstance(item, (RefExpr, TupleExpr)):
                    item_part = self.flatten_classes(item)
                    if item_part is None:
                        return None
                    res.extend(item_part)
                else:
                    return None
            return res

    def visit_await_expr(self, o: AwaitExpr) -> Value:
        return BuildFuncIR(self).visit_await_expr(o)

    # Unimplemented constructs
    def visit_assignment_expr(self, o: AssignmentExpr) -> Value:
        self.bail("I Am The Walrus (unimplemented)", o.line)

    # Unimplemented constructs that shouldn't come up because they are py2 only
    def visit_backquote_expr(self, o: BackquoteExpr) -> Value:
        self.bail("Python 2 features are unsupported", o.line)

    def visit_exec_stmt(self, o: ExecStmt) -> None:
        self.bail("Python 2 features are unsupported", o.line)

    def visit_print_stmt(self, o: PrintStmt) -> None:
        self.bail("Python 2 features are unsupported", o.line)

    def visit_unicode_expr(self, o: UnicodeExpr) -> Value:
        self.bail("Python 2 features are unsupported", o.line)

    # Constructs that shouldn't ever show up
    def visit_enum_call_expr(self, o: EnumCallExpr) -> Value:
        assert False, "can't compile analysis-only expressions"

    def visit__promote_expr(self, o: PromoteExpr) -> Value:
        assert False, "can't compile analysis-only expressions"

    def visit_namedtuple_expr(self, o: NamedTupleExpr) -> Value:
        assert False, "can't compile analysis-only expressions"

    def visit_newtype_expr(self, o: NewTypeExpr) -> Value:
        assert False, "can't compile analysis-only expressions"

    def visit_temp_node(self, o: TempNode) -> Value:
        assert False, "can't compile analysis-only expressions"

    def visit_type_alias_expr(self, o: TypeAliasExpr) -> Value:
        assert False, "can't compile analysis-only expressions"

    def visit_type_application(self, o: TypeApplication) -> Value:
        assert False, "can't compile analysis-only expressions"

    def visit_type_var_expr(self, o: TypeVarExpr) -> Value:
        assert False, "can't compile analysis-only expressions"

    def visit_typeddict_expr(self, o: TypedDictExpr) -> Value:
        assert False, "can't compile analysis-only expressions"

    def visit_reveal_expr(self, o: RevealExpr) -> Value:
        assert False, "can't compile analysis-only expressions"

    def visit_var(self, o: Var) -> None:
        assert False, "can't compile Var; should have been handled already?"

    def visit_cast_expr(self, o: CastExpr) -> Value:
        assert False, "CastExpr should have been handled in CallExpr"

    def visit_star_expr(self, o: StarExpr) -> Value:
        assert False, "should have been handled in Tuple/List/Set/DictExpr or CallExpr"

    # Helpers

    def enter(self, fn_info: Union[FuncInfo, str] = '') -> None:
        if isinstance(fn_info, str):
            fn_info = FuncInfo(name=fn_info)
        self.environment = Environment(fn_info.name)
        self.environments.append(self.environment)
        self.fn_info = fn_info
        self.fn_infos.append(self.fn_info)
        self.ret_types.append(none_rprimitive)
        self.error_handlers.append(None)
        if fn_info.is_generator:
            self.nonlocal_control.append(GeneratorNonlocalControl())
        else:
            self.nonlocal_control.append(BaseNonlocalControl())
        self.blocks.append([])
        self.new_block()

    def activate_block(self, block: BasicBlock) -> None:
        if self.blocks[-1]:
            assert isinstance(self.blocks[-1][-1].ops[-1], ControlOp)

        block.error_handler = self.error_handlers[-1]
        self.blocks[-1].append(block)

    def goto_and_activate(self, block: BasicBlock) -> None:
        self.goto(block)
        self.activate_block(block)

    def new_block(self) -> BasicBlock:
        block = BasicBlock()
        self.activate_block(block)
        return block

    def goto_new_block(self) -> BasicBlock:
        block = BasicBlock()
        self.goto_and_activate(block)
        return block

    def leave(self) -> Tuple[List[BasicBlock], Environment, RType, FuncInfo]:
        blocks = self.blocks.pop()
        env = self.environments.pop()
        ret_type = self.ret_types.pop()
        fn_info = self.fn_infos.pop()
        self.error_handlers.pop()
        self.nonlocal_control.pop()
        self.environment = self.environments[-1]
        self.fn_info = self.fn_infos[-1]
        return blocks, env, ret_type, fn_info

    def add(self, op: Op) -> Value:
        if self.blocks[-1][-1].ops:
            assert not isinstance(self.blocks[-1][-1].ops[-1], ControlOp), (
                "Can't add to finished block")

        self.blocks[-1][-1].ops.append(op)
        if isinstance(op, RegisterOp):
            self.environment.add_op(op)
        return op

    def goto(self, target: BasicBlock) -> None:
        if not self.blocks[-1][-1].ops or not isinstance(self.blocks[-1][-1].ops[-1], ControlOp):
            self.add(Goto(target))

    def primitive_op(self, desc: OpDescription, args: List[Value], line: int) -> Value:
        assert desc.result_type is not None
        coerced = []
        for i, arg in enumerate(args):
            formal_type = self.op_arg_type(desc, i)
            arg = self.coerce(arg, formal_type, line)
            coerced.append(arg)
        target = self.add(PrimitiveOp(coerced, desc, line))
        return target

    def op_arg_type(self, desc: OpDescription, n: int) -> RType:
        if n >= len(desc.arg_types):
            assert desc.is_var_arg
            return desc.arg_types[-1]
        return desc.arg_types[n]

    @overload
    def accept(self, node: Expression) -> Value: ...

    @overload
    def accept(self, node: Statement) -> None: ...

    def accept(self, node: Union[Statement, Expression]) -> Optional[Value]:
        with self.catch_errors(node.line):
            if isinstance(node, Expression):
                try:
                    res = node.accept(self)
                    res = self.coerce(res, self.node_type(node), node.line)
                # If we hit an error during compilation, we want to
                # keep trying, so we can produce more error
                # messages. Generate a temp of the right type to keep
                # from causing more downstream trouble.
                except UnsupportedException:
                    res = self.alloc_temp(self.node_type(node))
                return res
            else:
                try:
                    node.accept(self)
                except UnsupportedException:
                    pass
                return None

    def alloc_temp(self, type: RType) -> Register:
        return self.environment.add_temp(type)

    def type_to_rtype(self, typ: Optional[Type]) -> RType:
        return self.mapper.type_to_rtype(typ)

    def node_type(self, node: Expression) -> RType:
        if isinstance(node, IntExpr):
            # TODO: Don't special case IntExpr
            return int_rprimitive
        if node not in self.types:
            return object_rprimitive
        mypy_type = self.types[node]
        return self.type_to_rtype(mypy_type)

    def box(self, src: Value) -> Value:
        if src.type.is_unboxed:
            return self.add(Box(src))
        else:
            return src

    def unbox_or_cast(self, src: Value, target_type: RType, line: int) -> Value:
        if target_type.is_unboxed:
            return self.add(Unbox(src, target_type, line))
        else:
            return self.add(Cast(src, target_type, line))

    def box_expr(self, expr: Expression) -> Value:
        return self.box(self.accept(expr))

    def make_dict(self, key_value_pairs: Sequence[DictEntry], line: int) -> Value:
        result = None  # type: Union[Value, None]
        initial_items = []  # type: List[Value]
        for key, value in key_value_pairs:
            if key is not None:
                # key:value
                if result is None:
                    initial_items.extend((key, value))
                    continue

                self.translate_special_method_call(
                    result,
                    '__setitem__',
                    [key, value],
                    result_type=None,
                    line=line)
            else:
                # **value
                if result is None:
                    result = self.primitive_op(new_dict_op, initial_items, line)

                self.primitive_op(
                    dict_update_in_display_op,
                    [result, value],
                    line=line
                )

        if result is None:
            result = self.primitive_op(new_dict_op, initial_items, line)

        return result

    def none(self) -> Value:
        return self.add(PrimitiveOp([], none_op, line=-1))

    def none_object(self) -> Value:
        return self.add(PrimitiveOp([], none_object_op, line=-1))

    def add_var_to_env_class(self,
                             var: SymbolNode,
                             rtype: RType,
                             base: Union[FuncInfo, ImplicitClass],
                             reassign: bool = False) -> AssignmentTarget:
        # First, define the variable name as an attribute of the environment class, and then
        # construct a target for that attribute.
        self.fn_info.env_class.attributes[var.name] = rtype
        attr_target = AssignmentTargetAttr(base.curr_env_reg, var.name)

        if reassign:
            # Read the local definition of the variable, and set the corresponding attribute of
            # the environment class' variable to be that value.
            reg = self.read(self.environment.lookup(var), self.fn_info.fitem.line)
            self.add(SetAttr(base.curr_env_reg, var.name, reg, self.fn_info.fitem.line))

        # Override the local definition of the variable to instead point at the variable in
        # the environment class.
        return self.environment.add_target(var, attr_target)

    def is_builtin_ref_expr(self, expr: RefExpr) -> bool:
        assert expr.node, "RefExpr not resolved"
        return '.' in expr.node.fullname and expr.node.fullname.split('.')[0] == 'builtins'

    def load_global(self, expr: NameExpr) -> Value:
        """Loads a Python-level global.

        This takes a NameExpr and uses its name as a key to retrieve the corresponding PyObject *
        from the _globals dictionary in the C-generated code.
        """
        # If the global is from 'builtins', turn it into a module attr load instead
        if self.is_builtin_ref_expr(expr):
            assert expr.node, "RefExpr not resolved"
            return self.load_module_attr_by_fullname(expr.node.fullname, expr.line)
        if (self.is_native_module_ref_expr(expr) and isinstance(expr.node, TypeInfo)
                and not self.is_synthetic_type(expr.node)):
            assert expr.fullname is not None
            return self.load_native_type_object(expr.fullname)
        return self.load_global_str(expr.name, expr.line)

    def load_global_str(self, name: str, line: int) -> Value:
        _globals = self.load_globals_dict()
        reg = self.load_static_unicode(name)
        return self.primitive_op(dict_get_item_op, [_globals, reg], line)

    def load_globals_dict(self) -> Value:
        return self.add(LoadStatic(dict_rprimitive, 'globals', self.module_name))

    def literal_static_name(self, value: Union[int, float, complex, str, bytes]) -> str:
        return self.mapper.literal_static_name(self.current_module, value)

    def load_static_int(self, value: int) -> Value:
        """Loads a static integer Python 'int' object into a register."""
        static_symbol = self.literal_static_name(value)
        return self.add(LoadStatic(int_rprimitive, static_symbol, ann=value))

    def load_static_float(self, value: float) -> Value:
        """Loads a static float value into a register."""
        static_symbol = self.literal_static_name(value)
        return self.add(LoadStatic(float_rprimitive, static_symbol, ann=value))

    def load_static_bytes(self, value: bytes) -> Value:
        """Loads a static bytes value into a register."""
        static_symbol = self.literal_static_name(value)
        return self.add(LoadStatic(object_rprimitive, static_symbol, ann=value))

    def load_static_complex(self, value: complex) -> Value:
        """Loads a static complex value into a register."""
        static_symbol = self.literal_static_name(value)
        return self.add(LoadStatic(object_rprimitive, static_symbol, ann=value))

    def load_static_unicode(self, value: str) -> Value:
        """Loads a static unicode value into a register.

        This is useful for more than just unicode literals; for example, method calls
        also require a PyObject * form for the name of the method.
        """
        static_symbol = self.literal_static_name(value)
        return self.add(LoadStatic(str_rprimitive, static_symbol, ann=value))

    def load_module(self, name: str) -> Value:
        return self.add(LoadStatic(object_rprimitive, name, namespace=NAMESPACE_MODULE))

    def load_module_attr_by_fullname(self, fullname: str, line: int) -> Value:
        module, _, name = fullname.rpartition('.')
        left = self.load_module(module)
        return self.py_get_attr(left, name, line)

    def load_native_type_object(self, fullname: str) -> Value:
        module, name = fullname.rsplit('.', 1)
        return self.add(LoadStatic(object_rprimitive, name, module, NAMESPACE_TYPE))

    def coerce(self, src: Value, target_type: RType, line: int, force: bool = False) -> Value:
        """Generate a coercion/cast from one type to other (only if needed).

        For example, int -> object boxes the source int; int -> int emits nothing;
        object -> int unboxes the object. All conversions preserve object value.

        If force is true, always generate an op (even if it is just an assignment) so
        that the result will have exactly target_type as the type.

        Returns the register with the converted value (may be same as src).
        """
        if src.type.is_unboxed and not target_type.is_unboxed:
            return self.box(src)
        if ((src.type.is_unboxed and target_type.is_unboxed)
                and not is_runtime_subtype(src.type, target_type)):
            # To go from one unboxed type to another, we go through a boxed
            # in-between value, for simplicity.
            tmp = self.box(src)
            return self.unbox_or_cast(tmp, target_type, line)
        if ((not src.type.is_unboxed and target_type.is_unboxed)
                or not is_subtype(src.type, target_type)):
            return self.unbox_or_cast(src, target_type, line)
        elif force:
            tmp = self.alloc_temp(target_type)
            self.add(Assign(tmp, src))
            return tmp
        return src

    def native_args_to_positional(self,
                                  args: Sequence[Value],
                                  arg_kinds: List[int],
                                  arg_names: Sequence[Optional[str]],
                                  sig: FuncSignature,
                                  line: int) -> List[Value]:
        """Prepare arguments for a native call.

        Given args/kinds/names and a target signature for a native call, map
        keyword arguments to their appropriate place in the argument list,
        fill in error values for unspecified default arguments,
        package arguments that will go into *args/**kwargs into a tuple/dict,
        and coerce arguments to the appropriate type.
        """

        sig_arg_kinds = [arg.kind for arg in sig.args]
        sig_arg_names = [arg.name for arg in sig.args]
        formal_to_actual = map_actuals_to_formals(arg_kinds,
                                                  arg_names,
                                                  sig_arg_kinds,
                                                  sig_arg_names,
                                                  lambda n: AnyType(TypeOfAny.special_form))

        # Flatten out the arguments, loading error values for default
        # arguments, constructing tuples/dicts for star args, and
        # coercing everything to the expected type.
        output_args = []
        for lst, arg in zip(formal_to_actual, sig.args):
            output_arg = None
            if arg.kind == ARG_STAR:
                output_arg = self.primitive_op(new_tuple_op, [args[i] for i in lst], line)
            elif arg.kind == ARG_STAR2:
                dict_entries = [(self.load_static_unicode(cast(str, arg_names[i])), args[i])
                                for i in lst]
                output_arg = self.make_dict(dict_entries, line)
            elif not lst:
                output_arg = self.add(LoadErrorValue(arg.type, is_borrowed=True))
            else:
                output_arg = args[lst[0]]
            output_args.append(self.coerce(output_arg, arg.type, line))

        return output_args

    # Lacks a good type because there wasn't a reasonable type in 3.5 :(
    def catch_errors(self, line: int) -> Any:
        return catch_errors(self.module_path, line)

    def warning(self, msg: str, line: int) -> None:
        self.errors.warning(msg, self.module_path, line)

    def error(self, msg: str, line: int) -> None:
        self.errors.error(msg, self.module_path, line)

    def bail(self, msg: str, line: int) -> 'NoReturn':
        """Reports an error and aborts compilation up until the last accept() call

        (accept() catches the UnsupportedException and keeps on
        processing. This allows errors to be non-blocking without always
        needing to write handling for them.
        """
        self.error(msg, line)
        raise UnsupportedException()
