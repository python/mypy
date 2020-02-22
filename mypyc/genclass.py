from typing import List, Optional, Union
from typing_extensions import overload

from mypy.nodes import (
    ClassDef, FuncDef, OverloadedFuncDef, PassStmt, AssignmentStmt, NameExpr, StrExpr,
    ExpressionStmt, TempNode, Decorator, Statement, Expression, Lvalue, RefExpr, Var,
    is_class_var
)
from mypyc.ops import (
    Op, Value, OpDescription, NonExtClassInfo, Call, FuncDecl, LoadErrorValue, LoadStatic,
    InitStatic, FuncSignature, TupleSet, SetAttr, Return, FuncIR, ClassIR, RInstance,
    BasicBlock, Branch, MethodCall, RuntimeArg,
    NAMESPACE_TYPE,
    object_rprimitive, bool_rprimitive, dict_rprimitive, is_optional_type, is_object_rprimitive,
    is_none_rprimitive,
)
from mypyc.ops_misc import (
    dataclass_sleight_of_hand, py_setattr_op, pytype_from_template_op, py_calc_meta_op,
    type_object_op, py_hasattr_op, not_implemented_op, true_op
)
from mypyc.ops_dict import dict_set_item_op, new_dict_op
from mypyc.ops_tuple import new_tuple_op
from mypyc.genopsutil import (
    is_dataclass_decorator, get_func_def, is_dataclass, is_constant, add_self_to_env
)
from mypyc.genfunc import BuildFuncIR
from mypyc.common import SELF_NAME
from mypyc.genops import IRBuilder


class BuildClassIR:
    def __init__(self, builder: IRBuilder) -> None:
        self.builder = builder
        self.mapper = builder.mapper
        self.module_name = builder.module_name

    def visit_class_def(self, cdef: ClassDef) -> None:
        ir = self.mapper.type_to_ir[cdef.info]

        # We do this check here because the base field of parent
        # classes aren't necessarily populated yet at
        # prepare_class_def time.
        if any(ir.base_mro[i].base != ir. base_mro[i + 1] for i in range(len(ir.base_mro) - 1)):
            self.error("Non-trait MRO must be linear", cdef.line)

        if ir.allow_interpreted_subclasses:
            for parent in ir.mro:
                if not parent.allow_interpreted_subclasses:
                    self.error(
                        'Base class "{}" does not allow interpreted subclasses'.format(
                            parent.fullname), cdef.line)

        # Currently, we only create non-extension classes for classes that are
        # decorated or inherit from Enum. Classes decorated with @trait do not
        # apply here, and are handled in a different way.
        if ir.is_ext_class:
            # If the class is not decorated, generate an extension class for it.
            type_obj = self.allocate_class(cdef)  # type: Optional[Value]
            non_ext = None  # type: Optional[NonExtClassInfo]
            dataclass_non_ext = self.dataclass_non_ext_info(cdef)
        else:
            non_ext_bases = self.populate_non_ext_bases(cdef)
            non_ext_metaclass = self.find_non_ext_metaclass(cdef, non_ext_bases)
            non_ext_dict = self.setup_non_ext_dict(cdef, non_ext_metaclass, non_ext_bases)
            # We populate __annotations__ for non-extension classes
            # because dataclasses uses it to determine which attributes to compute on.
            # TODO: Maybe generate more precise types for annotations
            non_ext_anns = self.primitive_op(new_dict_op, [], cdef.line)
            non_ext = NonExtClassInfo(non_ext_dict, non_ext_bases, non_ext_anns, non_ext_metaclass)
            dataclass_non_ext = None
            type_obj = None

        attrs_to_cache = []  # type: List[Lvalue]

        for stmt in cdef.defs.body:
            if isinstance(stmt, OverloadedFuncDef) and stmt.is_property:
                if not ir.is_ext_class:
                    # properties with both getters and setters in non_extension
                    # classes not supported
                    self.error("Property setters not supported in non-extension classes",
                               stmt.line)
                for item in stmt.items:
                    with self.builder.catch_errors(stmt.line):
                        BuildFuncIR(self.builder).visit_method(cdef, non_ext, get_func_def(item))
            elif isinstance(stmt, (FuncDef, Decorator, OverloadedFuncDef)):
                # Ignore plugin generated methods (since they have no
                # bodies to compile and will need to have the bodies
                # provided by some other mechanism.)
                if cdef.info.names[stmt.name].plugin_generated:
                    continue
                with self.builder.catch_errors(stmt.line):
                    BuildFuncIR(self.builder).visit_method(cdef, non_ext, get_func_def(stmt))
            elif isinstance(stmt, PassStmt):
                continue
            elif isinstance(stmt, AssignmentStmt):
                if len(stmt.lvalues) != 1:
                    self.error("Multiple assignment in class bodies not supported", stmt.line)
                    continue
                lvalue = stmt.lvalues[0]
                if not isinstance(lvalue, NameExpr):
                    self.error("Only assignment to variables is supported in class bodies",
                               stmt.line)
                    continue
                # We want to collect class variables in a dictionary for both real
                # non-extension classes and fake dataclass ones.
                var_non_ext = non_ext or dataclass_non_ext
                if var_non_ext:
                    self.add_non_ext_class_attr(var_non_ext, lvalue, stmt, cdef, attrs_to_cache)
                    if non_ext:
                        continue
                # Variable declaration with no body
                if isinstance(stmt.rvalue, TempNode):
                    continue
                # Only treat marked class variables as class variables.
                if not (is_class_var(lvalue) or stmt.is_final_def):
                    continue
                typ = self.builder.load_native_type_object(cdef.fullname)
                value = self.accept(stmt.rvalue)
                self.primitive_op(
                    py_setattr_op, [typ, self.load_static_unicode(lvalue.name), value], stmt.line)
                if self.builder.non_function_scope() and stmt.is_final_def:
                    self.builder.init_final_static(lvalue, value, cdef.name)
            elif isinstance(stmt, ExpressionStmt) and isinstance(stmt.expr, StrExpr):
                # Docstring. Ignore
                pass
            else:
                self.error("Unsupported statement in class body", stmt.line)

        if not non_ext:  # That is, an extension class
            self.generate_attr_defaults(cdef)
            self.create_ne_from_eq(cdef)
            if dataclass_non_ext:
                assert type_obj
                self.dataclass_finalize(cdef, dataclass_non_ext, type_obj)
        else:
            # Dynamically create the class via the type constructor
            non_ext_class = self.load_non_ext_class(ir, non_ext, cdef.line)
            non_ext_class = self.load_decorated_class(cdef, non_ext_class)

            # Save the decorated class
            self.add(InitStatic(non_ext_class, cdef.name, self.module_name, NAMESPACE_TYPE))

            # Add the non-extension class to the dict
            self.primitive_op(dict_set_item_op,
                              [
                                  self.builder.load_globals_dict(),
                                  self.load_static_unicode(cdef.name),
                                  non_ext_class
                              ], cdef.line)

            # Cache any cachable class attributes
            self.cache_class_attrs(attrs_to_cache, cdef)

            # Set this attribute back to None until the next non-extension class is visited.
            self.non_ext_info = None

    def allocate_class(self, cdef: ClassDef) -> Value:
        # OK AND NOW THE FUN PART
        base_exprs = cdef.base_type_exprs + cdef.removed_base_type_exprs
        if base_exprs:
            bases = [self.accept(x) for x in base_exprs]
            tp_bases = self.primitive_op(new_tuple_op, bases, cdef.line)
        else:
            tp_bases = self.add(LoadErrorValue(object_rprimitive, is_borrowed=True))
        modname = self.load_static_unicode(self.module_name)
        template = self.add(LoadStatic(object_rprimitive, cdef.name + "_template",
                                       self.module_name, NAMESPACE_TYPE))
        # Create the class
        tp = self.primitive_op(pytype_from_template_op,
                               [template, tp_bases, modname], cdef.line)
        # Immediately fix up the trait vtables, before doing anything with the class.
        ir = self.mapper.type_to_ir[cdef.info]
        if not ir.is_trait and not ir.builtin_base:
            self.add(Call(
                FuncDecl(cdef.name + '_trait_vtable_setup',
                         None, self.module_name,
                         FuncSignature([], bool_rprimitive)), [], -1))
        # Populate a '__mypyc_attrs__' field containing the list of attrs
        self.primitive_op(py_setattr_op, [
            tp, self.load_static_unicode('__mypyc_attrs__'),
            self.create_mypyc_attrs_tuple(self.mapper.type_to_ir[cdef.info], cdef.line)],
            cdef.line)

        # Save the class
        self.add(InitStatic(tp, cdef.name, self.module_name, NAMESPACE_TYPE))

        # Add it to the dict
        self.primitive_op(dict_set_item_op,
                          [
                              self.builder.load_globals_dict(),
                              self.load_static_unicode(cdef.name),
                              tp,
                          ], cdef.line)

        return tp

    def populate_non_ext_bases(self, cdef: ClassDef) -> Value:
        """
        Populate the base-class tuple passed to the metaclass constructor
        for non-extension classes.
        """
        ir = self.mapper.type_to_ir[cdef.info]
        bases = []
        for cls in cdef.info.mro[1:]:
            if cls.fullname == 'builtins.object':
                continue
            # Add the current class to the base classes list of concrete subclasses
            if cls in self.mapper.type_to_ir:
                base_ir = self.mapper.type_to_ir[cls]
                if base_ir.children is not None:
                    base_ir.children.append(ir)

            base = self.builder.load_global_str(cls.name, cdef.line)
            bases.append(base)
        return self.primitive_op(new_tuple_op, bases, cdef.line)

    def find_non_ext_metaclass(self, cdef: ClassDef, bases: Value) -> Value:
        """Find the metaclass of a class from its defs and bases. """
        if cdef.metaclass:
            declared_metaclass = self.accept(cdef.metaclass)
        else:
            declared_metaclass = self.primitive_op(type_object_op, [], cdef.line)

        return self.primitive_op(py_calc_meta_op, [declared_metaclass, bases], cdef.line)

    def setup_non_ext_dict(self, cdef: ClassDef, metaclass: Value, bases: Value) -> Value:
        """
        Initialize the class dictionary for a non-extension class. This class dictionary
        is passed to the metaclass constructor.
        """

        # Check if the metaclass defines a __prepare__ method, and if so, call it.
        has_prepare = self.primitive_op(py_hasattr_op,
                                        [metaclass,
                                        self.load_static_unicode('__prepare__')], cdef.line)

        non_ext_dict = self.builder.alloc_temp(dict_rprimitive)

        true_block, false_block, exit_block, = BasicBlock(), BasicBlock(), BasicBlock()
        self.builder.add_bool_branch(has_prepare, true_block, false_block)

        self.builder.activate_block(true_block)
        cls_name = self.load_static_unicode(cdef.name)
        prepare_meth = self.builder.py_get_attr(metaclass, '__prepare__', cdef.line)
        prepare_dict = self.builder.py_call(prepare_meth, [cls_name, bases], cdef.line)
        self.builder.assign(non_ext_dict, prepare_dict, cdef.line)
        self.builder.goto(exit_block)

        self.builder.activate_block(false_block)
        self.builder.assign(non_ext_dict, self.primitive_op(new_dict_op, [], cdef.line), cdef.line)
        self.builder.goto(exit_block)
        self.builder.activate_block(exit_block)

        return non_ext_dict

    def add_non_ext_class_attr(self, non_ext: NonExtClassInfo, lvalue: NameExpr,
                               stmt: AssignmentStmt, cdef: ClassDef,
                               attr_to_cache: List[Lvalue]) -> None:
        """
        Add a class attribute to __annotations__ of a non-extension class. If the
        attribute is assigned to a value, it is also added to __dict__.
        """

        # We populate __annotations__ because dataclasses uses it to determine
        # which attributes to compute on.
        # TODO: Maybe generate more precise types for annotations
        key = self.load_static_unicode(lvalue.name)
        typ = self.primitive_op(type_object_op, [], stmt.line)
        self.primitive_op(dict_set_item_op, [non_ext.anns, key, typ], stmt.line)

        # Only add the attribute to the __dict__ if the assignment is of the form:
        # x: type = value (don't add attributes of the form 'x: type' to the __dict__).
        if not isinstance(stmt.rvalue, TempNode):
            rvalue = self.accept(stmt.rvalue)
            self.builder.add_to_non_ext_dict(non_ext, lvalue.name, rvalue, stmt.line)
            # We cache enum attributes to speed up enum attribute lookup since they
            # are final.
            if (
                cdef.info.bases
                and cdef.info.bases[0].type.fullname == 'enum.Enum'
                # Skip "_order_" and "__order__", since Enum will remove it
                and lvalue.name not in ('_order_', '__order__')
            ):
                attr_to_cache.append(lvalue)

    def generate_attr_defaults(self, cdef: ClassDef) -> None:
        """Generate an initialization method for default attr values (from class vars)"""
        cls = self.mapper.type_to_ir[cdef.info]
        if cls.builtin_base:
            return

        # Pull out all assignments in classes in the mro so we can initialize them
        # TODO: Support nested statements
        default_assignments = []
        for info in reversed(cdef.info.mro):
            if info not in self.mapper.type_to_ir:
                continue
            for stmt in info.defn.defs.body:
                if (isinstance(stmt, AssignmentStmt)
                        and isinstance(stmt.lvalues[0], NameExpr)
                        and not is_class_var(stmt.lvalues[0])
                        and not isinstance(stmt.rvalue, TempNode)):
                    if stmt.lvalues[0].name == '__slots__':
                        continue

                    # Skip type annotated assignments in dataclasses
                    if is_dataclass(cdef) and stmt.type:
                        continue

                    default_assignments.append(stmt)

        if not default_assignments:
            return

        self.builder.enter()
        self.builder.ret_types[-1] = bool_rprimitive

        rt_args = (RuntimeArg(SELF_NAME, RInstance(cls)),)
        self_var = self.builder.read(add_self_to_env(self.builder.environment, cls), -1)

        for stmt in default_assignments:
            lvalue = stmt.lvalues[0]
            assert isinstance(lvalue, NameExpr)
            if not stmt.is_final_def and not is_constant(stmt.rvalue):
                self.builder.warning('Unsupported default attribute value', stmt.rvalue.line)

            # If the attribute is initialized to None and type isn't optional,
            # don't initialize it to anything.
            attr_type = cls.attr_type(lvalue.name)
            if isinstance(stmt.rvalue, RefExpr) and stmt.rvalue.fullname == 'builtins.None':
                if (not is_optional_type(attr_type) and not is_object_rprimitive(attr_type)
                        and not is_none_rprimitive(attr_type)):
                    continue
            val = self.builder.coerce(self.accept(stmt.rvalue), attr_type, stmt.line)
            self.add(SetAttr(self_var, lvalue.name, val, -1))

        self.add(Return(self.primitive_op(true_op, [], -1)))

        blocks, env, ret_type, _ = self.builder.leave()
        ir = FuncIR(
            FuncDecl('__mypyc_defaults_setup',
                     cls.name, self.module_name,
                     FuncSignature(rt_args, ret_type)),
            blocks, env)
        self.builder.functions.append(ir)
        cls.methods[ir.name] = ir

    def create_ne_from_eq(self, cdef: ClassDef) -> None:
        cls = self.mapper.type_to_ir[cdef.info]
        if cls.has_method('__eq__') and not cls.has_method('__ne__'):
            f = self.gen_glue_ne_method(cls, cdef.line)
            cls.method_decls['__ne__'] = f.decl
            cls.methods['__ne__'] = f
            self.builder.functions.append(f)

    def gen_glue_ne_method(self, cls: ClassIR, line: int) -> FuncIR:
        """Generate a __ne__ method from a __eq__ method. """
        self.builder.enter()

        rt_args = (RuntimeArg("self", RInstance(cls)), RuntimeArg("rhs", object_rprimitive))

        # The environment operates on Vars, so we make some up
        fake_vars = [(Var(arg.name), arg.type) for arg in rt_args]
        args = [
            self.builder.read(
                self.builder.environment.add_local_reg(
                    var, type, is_arg=True
                ),
                line
            )
            for var, type in fake_vars
        ]  # type: List[Value]
        self.builder.ret_types[-1] = object_rprimitive

        # If __eq__ returns NotImplemented, then __ne__ should also
        not_implemented_block, regular_block = BasicBlock(), BasicBlock()
        eqval = self.add(MethodCall(args[0], '__eq__', [args[1]], line))
        not_implemented = self.primitive_op(not_implemented_op, [], line)
        self.add(Branch(
            self.builder.binary_op(eqval, not_implemented, 'is', line),
            not_implemented_block,
            regular_block,
            Branch.BOOL_EXPR))

        self.builder.activate_block(regular_block)
        retval = self.builder.coerce(
            self.builder.unary_op(eqval, 'not', line), object_rprimitive, line
        )
        self.add(Return(retval))

        self.builder.activate_block(not_implemented_block)
        self.add(Return(not_implemented))

        blocks, env, ret_type, _ = self.builder.leave()
        return FuncIR(
            FuncDecl('__ne__', cls.name, self.module_name,
                     FuncSignature(rt_args, ret_type)),
            blocks, env)

    def load_non_ext_class(self, ir: ClassIR, non_ext: NonExtClassInfo, line: int) -> Value:
        cls_name = self.load_static_unicode(ir.name)

        self.finish_non_ext_dict(non_ext, line)

        class_type_obj = self.builder.py_call(non_ext.metaclass,
                                              [cls_name, non_ext.bases, non_ext.dict],
                                              line)
        return class_type_obj

    def load_decorated_class(self, cdef: ClassDef, type_obj: Value) -> Value:
        """
        Given a decorated ClassDef and a register containing a non-extension representation of the
        ClassDef created via the type constructor, applies the corresponding decorator functions
        on that decorated ClassDef and returns a register containing the decorated ClassDef.
        """
        decorators = cdef.decorators
        dec_class = type_obj
        for d in reversed(decorators):
            decorator = d.accept(self.builder.visitor)
            assert isinstance(decorator, Value)
            dec_class = self.builder.py_call(decorator, [dec_class], dec_class.line)
        return dec_class

    def cache_class_attrs(self, attrs_to_cache: List[Lvalue], cdef: ClassDef) -> None:
        """Add class attributes to be cached to the global cache"""
        typ = self.builder.load_native_type_object(cdef.fullname)
        for lval in attrs_to_cache:
            assert isinstance(lval, NameExpr)
            rval = self.builder.py_get_attr(typ, lval.name, cdef.line)
            self.builder.init_final_static(lval, rval, cdef.name)

    def create_mypyc_attrs_tuple(self, ir: ClassIR, line: int) -> Value:
        attrs = [name for ancestor in ir.mro for name in ancestor.attributes]
        if ir.inherits_python:
            attrs.append('__dict__')
        return self.primitive_op(new_tuple_op,
                                 [self.load_static_unicode(attr) for attr in attrs],
                                 line)

    def finish_non_ext_dict(self, non_ext: NonExtClassInfo, line: int) -> None:
        # Add __annotations__ to the class dict.
        self.primitive_op(dict_set_item_op,
                          [non_ext.dict, self.load_static_unicode('__annotations__'),
                           non_ext.anns], -1)

        # We add a __doc__ attribute so if the non-extension class is decorated with the
        # dataclass decorator, dataclass will not try to look for __text_signature__.
        # https://github.com/python/cpython/blob/3.7/Lib/dataclasses.py#L957
        filler_doc_str = 'mypyc filler docstring'
        self.builder.add_to_non_ext_dict(
            non_ext, '__doc__', self.load_static_unicode(filler_doc_str), line)
        self.builder.add_to_non_ext_dict(
            non_ext, '__module__', self.load_static_unicode(self.module_name), line)

    def dataclass_finalize(
            self, cdef: ClassDef, non_ext: NonExtClassInfo, type_obj: Value) -> None:
        """Generate code to finish instantiating a dataclass.

        This works by replacing all of the attributes on the class
        (which will be descriptors) with whatever they would be in a
        non-extension class, calling dataclass, then switching them back.

        The resulting class is an extension class and instances of it do not
        have a __dict__ (unless something else requires it).
        All methods written explicitly in the source are compiled and
        may be called through the vtable while the methods generated
        by dataclasses are interpreted and may not be.

        (If we just called dataclass without doing this, it would think that all
        of the descriptors for our attributes are default values and generate an
        incorrect constructor. We need to do the switch so that dataclass gets the
        appropriate defaults.)
        """
        self.finish_non_ext_dict(non_ext, cdef.line)
        dec = self.accept(next(d for d in cdef.decorators if is_dataclass_decorator(d)))
        self.primitive_op(
            dataclass_sleight_of_hand, [dec, type_obj, non_ext.dict, non_ext.anns], cdef.line)

    def dataclass_non_ext_info(self, cdef: ClassDef) -> Optional[NonExtClassInfo]:
        """Set up a NonExtClassInfo to track dataclass attributes.

        In addition to setting up a normal extension class for dataclasses,
        we also collect its class attributes like a non-extension class so
        that we can hand them to the dataclass decorator.
        """
        if is_dataclass(cdef):
            return NonExtClassInfo(
                self.primitive_op(new_dict_op, [], cdef.line),
                self.add(TupleSet([], cdef.line)),
                self.primitive_op(new_dict_op, [], cdef.line),
                self.primitive_op(type_object_op, [], cdef.line),
            )
        else:
            return None

    # Helpers

    def primitive_op(self, desc: OpDescription, args: List[Value], line: int) -> Value:
        return self.builder.primitive_op(desc, args, line)

    @overload
    def accept(self, node: Expression) -> Value: ...

    @overload
    def accept(self, node: Statement) -> None: ...

    def accept(self, node: Union[Statement, Expression]) -> Optional[Value]:
        return self.builder.accept(node)

    def error(self, msg: str, line: int) -> None:
        self.builder.error(msg, line)

    def add(self, op: Op) -> Value:
        return self.builder.add(op)

    def load_static_unicode(self, value: str) -> Value:
        return self.builder.load_static_unicode(value)
