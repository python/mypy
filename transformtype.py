from nodes import (
    TypeDef, Node, FuncDef, VarDef, Block, Var, Annotation, ExpressionStmt,
    TypeInfo, SuperExpr, NameExpr, CallExpr, MDEF, MemberExpr, ReturnStmt,
    AssignmentStmt, TypeExpr
)
import nodes
from semanal import self_type
from mtypes import (
    Callable, Instance, Typ, Any, BOUND_VAR, Void, RuntimeTypeVar
)
from checkmember import analyse_member_access
from subtypes import map_instance_to_supertype
import transform
from transformfunc import FuncTransformer
from transutil import self_expr, tvar_slot_name, tvar_arg_name
from rttypevars import translate_runtime_type_vars_locally
from compileslotmap import find_slot_origin
from subtypes import map_instance_to_supertype
from coerce import coerce
from maptypevar2 import num_slots, get_tvar_access_path


class TypeTransformer:
    """Class for transforming type definitions for runtime type checking.

    Transform a type definition by modifying it in-place.
    
    This is used by DyncheckTransformVisitor and is logically aggregated within
    that class.
    """
    # Used for common transformation operations.
    transform.DyncheckTransformVisitor tf
    # Used for transforming methods.
    FuncTransformer func_tf
    
    void __init__(self, transform.DyncheckTransformVisitor tf):
        self.tf = tf
        self.func_tf = FuncTransformer(tf)
    
    TypeDef[] transform_type_def(self, TypeDef tdef):
        """Transform a type definition.

        The result may be one or two definitions.  The first is the
        transformation of the original TypeDef. The second is a
        wrapper type, which is generated for generic types only.
        """
        Node[] defs = []
        
        if tdef.info.type_vars != []:
            # This is a generic type. Insert type variable slots in
            # the class definition for new type variables, i.e. type
            # variables not mapped to superclass type variables.
            defs.extend(self.make_tvar_representation(tdef.info))
        
        # Iterate over definitions and transform each of them.
        for d in tdef.defs.body:
            if isinstance(d, FuncDef):
                # Implicit cast from Array<FuncDef> to Array<Node> is
                # safe below.
                defs.extend((any)self.func_tf.transform_method((FuncDef)d))
            elif isinstance(d, VarDef):
                defs.extend(self.transform_var_def((VarDef)d))
            else:
                defs.append(d)
        
        # For generic classes, add an implicit create wrapper.
        defs.extend(self.make_create_wrapper(tdef))
        
        if tdef.is_generic or tdef.info.base.is_generic:
            self.make_instance_tvar_initializer(
                (FuncDef)tdef.info.methods['__init__'])
        
        TypeDef[] res
        if not tdef.is_generic:
            res = [tdef]
        else:
            res = [tdef, self.generic_class_wrapper(tdef)]
        tdef.defs = Block(defs)
        
        return res
    
    Node[] make_create_wrapper(self, TypeDef tdef):
        """Make and return an implicit create if class needs it;
        otherwise, return an empty array. We include an implicit
        create if the class is generic or if it extends a generic
        class and if it does not define create.
        
        The create of a generic class requires one or more extra type variable
        arguments. The inherited create may not accept these.
        
        For example, assume these definitions:
          class A<T>; end
          class B is A<Int>; end
        
        The constructor for B will be (equivalent to)
        
          def create()
            self.__tv = <std::Int>
            super.create(<std::Int>)
          end
        """
        # FIX intersection types / overloading
        # FIX default args / varargs
        
        info = tdef.info
        
        if '__init__' not in info.methods and (tdef.is_generic or
                                               info.base.is_generic):
            # Generic class with no explicit create method
            # (i.e. create inherited from superclass). Generate a
            # wrapper that initializes type variable slots and calls
            # the superclass create method.
            
            self_type = self_type(info)    
            callee_type = (Callable)analyse_member_access(
                '__init__', self_type, None, False, True, None, None,
                info.base)
            
            # Now the callee type may contain the type variables of a
            # grandparent as bound type variables, but we want the
            # type variables of the parent class. Explicitly set the
            # bound type variables.
            callee_type = self.fix_bound_create_tvars(callee_type,
                map_instance_to_supertype(self_type, info.base))
            
            super_create = (FuncDef)info.base.get_method('__init__')
            
            # Build argument list.
            Var[] args = []
            for i in range(len(super_create.args)):
                args.append(Var(super_create.args[i].name()))
                args[-1].typ = Annotation(callee_type.arg_types[i])
            
            creat = FuncDef('__init__', args,
                            <Node> [None] * len(args), None, None, len(args),
                            Block([]))
            creat.info = tdef.info
            creat.typ = Annotation(callee_type, -1)
            creat.is_implicit = False
            tdef.info.methods['__init__'] = creat
            
            # Insert a call to superclass constructor. If the
            # superclass is object, the constructor does nothing =>
            # omit the call.
            if tdef.info.base.full_name() != 'builtins.object':
                creat.body.body.append(
                    self.make_superclass_constructor_call(tdef.info,
                                                          callee_type))
            
            # Implicit cast from Array<FuncDef> to Array<Node> is safe below.
            return (any)self.func_tf.transform_method(creat)
        else:
            return []
    
    Callable fix_bound_create_tvars(self, Callable callable, Instance typ):
        """Replace the bound type variables of callable with the type arguments
        of the instance type.
        """
        list<tuple<int, Typ>> a = []
        for i in range(len(typ.args)):
            a.append((i + 1, typ.args[i]))
        return Callable(callable.arg_types, callable.arg_kinds,
                        callable.arg_names, callable.ret_type,
                        callable.is_type_obj(), callable.name,
                        callable.variables, a)
    
    ExpressionStmt make_superclass_constructor_call(self, TypeInfo info,
                                                    Callable callee_type):
        """Construct a statement that calls the superclass constructor."""
        callee = SuperExpr('__init__')
        callee.info = info
        
        # We do not handle generic constructors. Either pass runtime
        # type variables from the current scope or perhaps require
        # explicit constructor in this case.
        
        self_type = self_type(info)    
        
        # FIX intersection types / overloading
        # FIX default args / varargs
        
        # Map self type to the superclass context.
        self_type = map_instance_to_supertype(self_type, info.base)
        
        super_create = (FuncDef)info.base.get_method('__init__')
        
        # Add constructor arguments.
        Node[] args = []
        for n in range(callee_type.min_args):
            args.append(NameExpr(super_create.args[n].name()))
            self.tf.set_type(args[-1], callee_type.arg_types[n])
        
        self.tf.set_type(callee, callee_type)
        
        call = CallExpr(callee, args)
        return ExpressionStmt(call)
    
    Node[] transform_var_def(self, VarDef o):
        """Transform a member variable definition.

        The result may be one or more definitions.
        """
        Node[] res = [o]
        
        self.tf.visit_var_def(o)
        
        # Add x* accessor wrappers for member variables that are used to access
        # them via dynamically-typed references (but only for public member
        # variables).
        if o.kind == MDEF:
            for n, vt in o.items:
                Typ t
                if n.typ is not None:
                    t = n.typ.typ
                else:
                    t = Any()
                res.append(self.make_getter_wrapper(n.name(), t))
                res.append(self.make_setter_wrapper(n.name(), t))
        
        return res
    
    FuncDef make_getter_wrapper(self, str name, Typ typ):
        """Create a dynamically-typed getter wrapper for a member.

        The getter will be like this:
        
          def name* as dynamic
            return {dyn <= type | self.name}
          end
        """
        Node member_expr = MemberExpr(self_expr(), name)
        member_expr = coerce(member_expr, Any(), typ, self.tf.type_context())
        ret = ReturnStmt(member_expr)
        
        return FuncDef(name + self.tf.dynamic_suffix(), [], [], None, None, 0,
                       Block([ret]), Annotation(Any()))
    
    FuncDef make_setter_wrapper(self, str name, Typ typ):
        """Create a dynamically-typed setter wrapper for a member.

        The setter will be like this:
        
          def name* = __x as dynamic
            self.name = {type <= dyn | __x}
          end
        """
        Node lvalue = MemberExpr(self_expr(), name)
        rvalue = coerce(NameExpr('__x'), typ, Any(), self.tf.type_context())
        ret = AssignmentStmt([lvalue], rvalue)
        
        return FuncDef(name + self.tf.dynamic_suffix(), [Var('__x')], [None],
                       None, None, 1, Block([ret]), Annotation(Any()))
    
    TypeDef generic_class_wrapper(self, TypeDef tdef):
        """Construct a wrapper class for a generic type."""
        # FIX semanal meta-info for nodes + TypeInfo
        
        Node[] defs = []
        
        # Does the type have a superclass, other than builtins.object?
        has_proper_superclass = tdef.info.base.full_name() != 'builtins.object'
        
        if not has_proper_superclass or self.tf.is_java:
            # Generate member variables for wrapper object.
            defs.extend(self.make_generic_wrapper_member_vars(tdef))
        
        for alt in [False, BOUND_VAR]:
            defs.extend(self.make_tvar_representation(tdef.info, alt))
        
        # Generate constructor.
        defs.append(self.make_generic_wrapper_create(tdef.info))
        
        # Generate method wrappers.
        for d in tdef.defs.body:
            # The dynamic cast below is safe since a class only contains
            # definitions that provide isPrivate.
            if not ((any)d).isPrivate:
                if isinstance(d, FuncDef):
                    if not ((FuncDef)d).is_constructor():
                        # The dynamic cast from Array<FuncDef> to Array<Node> below is
                        # safe since the result is passed to extend.
                        defs.extend((any)self.func_tf.generic_method_wrappers((FuncDef)d))
                else:
                    raise RuntimeError('Definition {} at line {} not supported'.format(type(d), d.line))
        
        Typ base_type = None
        # Inherit superclass wrapper if there is one. A superclass always exists
        # when inheriting a class other Object, since generic classes cannot
        # inherit non-generic ones.
        if has_proper_superclass:
            base = self.find_generic_base_class(tdef.info)
            if base is not None:
                base_type = None # TODO base.defn.name + tf.dynamicSuffix())
        
        # Build the type definition.
        wrapper = TypeDef(tdef.name + self.tf.dynamic_suffix(), Block(defs), None, [base_type], False)          # Interface?
        # FIX fullname
        
        self.tf.add_line_mapping(tdef, wrapper)
        
        return wrapper
    
    TypeInfo find_generic_base_class(self, TypeInfo info):
        base = info.base
        while base is not None:
            if base.type_vars != []:
                return base
            base = base.base
    
    Node[] make_generic_wrapper_member_vars(self, TypeDef tdef):
        """Generate the member variable definition for the wrapped object (__o) for
        a generic wrapper class.
        """
        Node[] defs = [VarDef([(Var(self.object_member_name(tdef.info)), Any())], False, None)]
        
        return defs
    
    str object_member_name(self, TypeInfo info):
        if self.tf.is_java:
            return '__o_{}'.format(info.name)
        else:
            return '__o'
    
    FuncDef make_generic_wrapper_create(self, TypeInfo info):
        """Build constructor of a generic wrapper class."""
        nslots = num_slots(info)
        
        Node[] cdefs = []
        
        # Build superclass constructor call.
        if info.base.full_name() != 'builtins.object' and self.tf.is_java:
            s = SuperExpr('__init__')
            Node[] args = [NameExpr('__o')]
            for n in range(num_slots(info.base)):
                args.append(NameExpr(tvar_arg_name(n + 1)))
            for n in range(num_slots(info.base)):
                args.append(NameExpr(tvar_arg_name(n + 1, BOUND_VAR)))
            c = CallExpr(s, args)
            cdefs.append(ExpressionStmt(c))
        
        # Create initialization of the wrapped object.
        cdefs.append(AssignmentStmt([MemberExpr(self_expr(), self.object_member_name(info))], NameExpr('__o')))
        
        # Build constructor arguments.
        args = [Var('__o')]
        Node[] init = [None]
        
        for alt in [False, BOUND_VAR]:
            for n in range(nslots):
                args.append(Var(tvar_arg_name(n + 1, alt)))
                init.append(None)

        nargs = nslots * 2 + 1
        fdef = FuncDef('__init__',
                       args,
                       init,
                       None,
                       None,
                       len(args),
                       Block(cdefs),
                       Annotation(Callable(<Typ> [Any()] * nargs,
                                  [nodes.ARG_POS] * nargs,
                                  <str> [None] * nargs,
                                  Void(),
                                  is_type_obj=False)))
        fdef.info = info
        
        self.make_wrapper_slot_initializer(fdef)
        
        return fdef
    
    Node[] make_tvar_representation(self, TypeInfo info, any is_alt=False):
        """Return type variable slot member definitions (of form
        "var __tv* as dynamic"). Only include new slots defined in the type.
        """
        Node[] defs = []
        base_slots = num_slots(info.base)
        for n in range(len(info.type_vars)):
            # Only include a type variable if it introduces a new slot.
            slot = get_tvar_access_path(info, n + 1)[0] - 1
            if slot >= base_slots:
                defs.append(VarDef([(Var(tvar_slot_name(slot, is_alt)), Any())], False, None))
        return defs
    
    void make_instance_tvar_initializer(self, FuncDef creat):
        """Add type variable member initialization code to the constructor of a
        class. Modify the constructor body directly.
        """
        for n in range(num_slots(creat.info)):
            rvalue = self.make_tvar_init_expression(creat.info, n)
            init = AssignmentStmt([MemberExpr(self_expr(), tvar_slot_name(n))], rvalue)
            self.tf.set_type(init.lvalues[0], Any())
            self.tf.set_type(init.rvalue, Any())
            creat.body.body.insert(n, init)
    
    void make_wrapper_slot_initializer(self, FuncDef creat):
        """Add type variable member initialization code to the constructor of a
        generic wrapper class. Modify the constructor body directly.
        """
        for alt in [BOUND_VAR, False]:
            for n in range(num_slots(creat.info)):
                rvalue = TypeExpr(RuntimeTypeVar(NameExpr(tvar_slot_name(n, alt))))
                init = AssignmentStmt([MemberExpr(self_expr(), tvar_slot_name(n, alt))], rvalue)
                self.tf.set_type(init.lvalues[0], Any())
                self.tf.set_type(init.rvalue, Any())
                creat.body.body.insert(n, init)
    
    TypeExpr make_tvar_init_expression(self, TypeInfo info, int slot):
        """Return the initializer for the given slot in the given type, i.e. the
        type expression that initializes the given slot using the type arguments
        given to the constructor.
        
        Examples:
          - In "class C<T> ...", the initializer for the slot 0 is
            TypeExpr(RuntimeTypeVar(NameExpr('__tv'))).
          - In "class D is C<Int> ...", the initializer for the slot 0 is
            TypeExpr(<std::Int instance>).
            """
        # Figure out the superclass which defines the slot; also figure out
        # the tvar index that maps to the slot.
        origin, tv = find_slot_origin(info, slot)
        
        # Map self type to the superclass -> extract tvar with target index
        # (only contains subclass tvars?? PROBABLY NOT).
        self_type = self_type(info)
        self_type = map_instance_to_supertype(self_type, origin)
        tvar = self_type.args[tv - 1]
        
        # Map tvar to an expression; refer to local vars instead of member
        # vars always.
        tvar = translate_runtime_type_vars_locally(tvar)
        
        # Build the rvalue (initializer) expression
        return TypeExpr(tvar)
