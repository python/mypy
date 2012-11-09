from types import Typ, TypeVarDef
from util import dump_tagged
from nodes import Node, Annotation, TypeDef, Var, FuncBase, AccessorNode


# Class representing the type structure of a single class. The corresponding
# TypeDef instance represents the parse tree of the class.
class TypeInfo(Node, AccessorNode):
    str full_name      # Fully qualified name
    bool is_interface  # Is this a interface type?
    TypeDef defn  # Corresponding TypeDef
    TypeInfo base = None # Superclass or nil (not interface)
    set<TypeInfo> subtypes = set() # Direct subclasses
    
    dict<str, Var> vars = {}     # Member variables; also slots
    dict<str, FuncBase> methods = {}
    
    # TypeInfos of base interfaces
    list<TypeInfo> interfaces = []
    
    # Information related to type annotations.
    
    # Generic type variable names
    list<str> type_vars = []
    
    # Type variable bounds (each may be nil)
    # TODO implement these
    list<Typ> bounds = []
    
    # Inherited generic types (Instance or UnboundType or nil). The first base
    # is the superclass, and the rest are interfaces.
    list<Typ> bases = []
    
    
    # Construct a TypeInfo.
    void __init__(self, dict<str, Var> vars, dict<str, FuncBase> methods, TypeDef defn):
        self.full_name = defn.full_name
        self.is_interface = defn.is_interface
        self.vars = vars
        self.methods = methods
        self.defn = defn
        if defn.type_vars is not None:
            for vd in defn.type_vars.items:
                self.type_vars.append(vd.name)
    
    # Short name.
    str name(self):
        return self.defn.name
    
    # Is the type generic (i.e. does it have type variables)?
    bool is_generic(self):
        return self.type_vars is not None and len(self.type_vars) > 0
    
    void set_type_bounds(self, list<TypeVarDef> a):
        for vd in a:
            self.bounds.append(vd.bound)
    
    
    # IDEA: Refactor the has* methods to be more consistent and document
    #       them.
    
    bool has_readable_member(self, str name):
        return self.has_var(name) or self.has_method(name)
    
    bool has_writable_member(self, str name):
        return self.has_var(name) or self.has_setter(name)
    
    bool has_var(self, str name):
        return self.get_var(name) is not None
    
    bool has_method(self, str name):
        return name in self.methods or (self.base is not None and self.base.has_method(name))
    
    def has_setter(self, name):
        # FIX implement
        return False
    
    
    Var get_var(self, str name):
        if name in self.vars:
            return self.vars[name]
        elif self.base is not None:
            return self.base.get_var(name)
        else:
            return None
    
    AccessorNode get_var_or_getter(self, str name):
        # TODO getter
        if name in self.vars:
            return self.vars[name]
        elif self.base is not None:
            return self.base.get_var_or_getter(name)
        else:
            return None
    
    AccessorNode get_var_or_setter(self, str name):
        # TODO setter
        if name in self.vars:
            return self.vars[name]
        elif self.base is not None:
            return self.base.get_var_or_setter(name)
        else:
            return None
    
    FuncBase get_method(self, str name):
        if name in self.methods:
            return self.methods[name]
        elif self.base is not None:
            return self.base.get_method(name)
        else:
            return None
    
    
    # Set the base class.
    void set_base(self, TypeInfo base):
        self.base = base
        base.subtypes.add(self)
    
    # Return True if type has a basetype with the specified name, either via
    # extension or via implementation.
    bool has_base(self, str full_name):
        if self.full_name == full_name or (self.base is not None and self.base.has_base(full_name)):
            return True
        for iface in self.interfaces:
            if iface.full_name == full_name or iface.has_base(full_name):
                return True
        return False
    
    # Return TypeInfos of all subtypes, including this type, as a set.
    set<TypeInfo> all_subtypes(self):
        set = set([self])
        for subt in self.subtypes:
            for t in subt.all_subtypes():
                set.add(t)
        return set
    
    
    # Add a base interface.
    void add_interface(self, TypeInfo base):
        self.interfaces.append(base)
    
    # Return an Array of interfaces that are either directly implemented by the
    # type or that are the supertypes of other interfaces in the array.
    list<TypeInfo> all_directly_implemented_interfaces(self):
        # Interfaces never implement interfaces.
        if self.is_interface:
            return []
        list<TypeInfo> a = []
        for i in range(len(self.interfaces)):
            iface = self.interfaces[i]
            if iface not in a:
                a.append(iface)
            ifa = iface
            while ifa.base is not None:
                ifa = ifa.base
                if ifa not in a:
                    a.append(ifa)
        return a
    
    # Return an array of directly implemented interfaces. Omit inherited
    # interfaces.
    list<TypeInfo> directly_implemented_interfaces(self):
        return self.interfaces[:]
    
    
    # Return a string representation of the type, which includes the most
    # important information about the type.
    str __str__(self):
        list<str> interfaces = []
        for i in self.interfaces:
            interfaces.append(i.full_name)
        str base = None
        if self.base is not None:
            base = 'Base({})'.format(self.base.full_name)
        str iface = None
        if self.is_interface:
            iface = 'Interface'
        return dump_tagged(['Name({})'.format(self.full_name),
                            iface,
                            base,
                            ('Interfaces', interfaces),
                            ('Vars', self.vars.keys()),
                            ('Methods', self.methods.keys())],
                           'TypeInfo')
