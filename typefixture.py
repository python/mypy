import alore
from types import TypeVar, Any, Void, ErrorType, NoneType, Instance, Callable, TypeVarDef, TypeVars
from checker import BasicTypes
from nodes import TypeInfo, TypeDef, Block


any BASE, any VARS, any BASE_DEFS, any IS_INTERFACE, any INTERFACES


# Helper class that is used as a fixture in type-related unit tests. The
# members are initialized to contain various type-related values.
class TypeFixture:
    # Type variables
    
    t = TypeVar('T', 1)    # T`1 (type variable)
    tf = TypeVar('T', -1)  # T`-1 (type variable)
    tf2 = TypeVar('T', -2) # T`-2 (type variable)
    s = TypeVar('S', 2)    # S`2 (type variable)
    s1 = TypeVar('S', 1)   # S`1 (type variable)
    sf = TypeVar('S', -2)  # S`-2 (type variable)
    sf1 = TypeVar('S', -1) # S`-1 (type variable)
    
    # Simple types
    
    dyn = Any()    # dynamic
    void = Void()      # void
    err = ErrorType()  # (error)
    nilt = NoneType()   # nil
    
    # Interface TypeInfos
    
    # interface F
    fi = make_type_info('F', alore.pair(IS_INTERFACE, True))
    
    # interface F2
    f2i = make_type_info('F2', alore.pair(IS_INTERFACE, True))
    
    # interface F3 is F
    f3i = make_type_info('F3', alore.pair(IS_INTERFACE, True), alore.pair(BASE, self.fi))
    
    # Class TypeInfos
    
    oi = make_type_info('builtins.object')       # class object
    std_tuplei = make_type_info('builtins.tuple') # class tuple
    std_typei = make_type_info('builtins.type')   # class type
    std_functioni = make_type_info('std::Function') # class Function TODO
    ai = make_type_info('A', alore.pair(BASE, self.oi))       # class A
    bi = make_type_info('B', alore.pair(BASE, self.ai))       # class B is A
    ci = make_type_info('C', alore.pair(BASE, self.ai))       # class C is A
    di = make_type_info('D', alore.pair(BASE, self.oi))       # class D
    
    # class E implements F
    ei = make_type_info('E', alore.pair(INTERFACES, [self.fi]), alore.pair(BASE, self.oi))
    
    # class E2 implements F2, F
    e2i = make_type_info('E2', alore.pair(INTERFACES, [self.f2i, self.fi]), alore.pair(BASE, self.oi))
    
    # class E3 implements F, F2
    e3i = make_type_info('E3', alore.pair(INTERFACES, [self.fi, self.f2i]), alore.pair(BASE, self.oi))
    
    # Generic class TypeInfos
    
    # class G<T>
    gi = make_type_info('G', alore.pair(BASE, self.oi), alore.pair(VARS, ['T']))
    # class G2<T>
    g2i = make_type_info('G2', alore.pair(BASE, self.oi), alore.pair(VARS, ['T']))
    # class H<S, T>
    hi = make_type_info('H', alore.pair(BASE, self.oi), alore.pair(VARS, ['S', 'T']))
    # class GS<T, S> is G<S>
    gsi = make_type_info('GS', alore.pair(BASE, self.gi), alore.pair(VARS, ['T', 'S']), alore.pair(BASE_DEFS, [Instance(self.gi, [self.s])]))
    # class GS2<S> is G<S>
    gs2i = make_type_info('GS2', alore.pair(BASE, self.gi), alore.pair(VARS, ['S']), alore.pair(BASE_DEFS, [Instance(self.gi, [self.s1])]))
    # class Array as <T>
    std_listi = make_type_info('builtins.list', alore.pair(BASE, self.oi), alore.pair(VARS, ['T']))
    
    # Instance types
    
    o = Instance(self.oi, [])          # Object
    std_tuple = Instance(self.std_tuplei, [])       # Tuple
    std_type = Instance(self.std_typei, [])         # Type
    std_function = Instance(self.std_functioni, []) # Function
    a = Instance(self.ai, [])          # A
    b = Instance(self.bi, [])          # B
    c = Instance(self.ci, [])          # C
    d = Instance(self.di, [])          # D
    
    e = Instance(self.ei, [])          # E
    e2 = Instance(self.e2i, [])        # E2
    e3 = Instance(self.e3i, [])        # E3
    
    f = Instance(self.fi, [])          # F
    f2 = Instance(self.f2i, [])        # F2
    f3 = Instance(self.f3i, [])        # F3
    
    # Generic instance types
    
    ga = Instance(self.gi, [self.a])        # G<A>
    gb = Instance(self.gi, [self.b])        # G<B>
    go = Instance(self.gi, [self.o])        # G<Object>
    gt = Instance(self.gi, [self.t])        # G<T`1>
    gtf = Instance(self.gi, [self.tf])      # G<T`-1>
    gtf2 = Instance(self.gi, [self.tf2])    # G<T`-2>
    gs = Instance(self.gi, [self.s])        # G<S>
    gdyn = Instance(self.gi, [self.dyn])    # G<dynamic>
    
    g2a = Instance(self.g2i, [self.a])      # G2<A>
    
    gsab = Instance(self.gsi, [self.a, self.b])  # GS<A, B>
    gsba = Instance(self.gsi, [self.b, self.a])  # GS<B, A>
    
    gs2a = Instance(self.gs2i, [self.a])    # GS2<A>
    
    hab = Instance(self.hi, [self.a, self.b])    # H<A, B>
    haa = Instance(self.hi, [self.a, self.a])    # H<A, A>
    hbb = Instance(self.hi, [self.b, self.b])    # H<B, B>
    hts = Instance(self.hi, [self.t, self.s])    # H<T, S>
    
    lsta = Instance(self.std_listi, [self.a])  # list<A>
    lstb = Instance(self.std_listi, [self.b])  # list<B>
    
    # Basic types
    basic = BasicTypes(self.o, self.std_type, self.std_tuple, self.std_function)
    
    # Helper methods
    
    # callable(a1, ..., an, r) constructs a callable with argument types
    # a1, ... an and return type r.
    def callable(self, *a):
        return Callable(a[:-1], len(a) - 1, False, a[-1], False)
    
    # typeCallable(a1, ..., an, r) constructs a callable with argument types
    # a1, ... an and return type r, and which represents a type.
    def callable_type(self, *a):
        return Callable(a[:-1], len(a) - 1, False, a[-1], True)
    
    # callableDefault(minArgs, a1, ..., an, r) constructs a callable with
    # argument types a1, ... an and return type r, with minArgs mandatory fixed
    # arguments.
    def callable_default(self, min_args, *a):
        return Callable(a[:-1], min_args, False, a[-1], False)
    
    # callableVarArg(minArgs, a1, ..., an, r) constructs a callable with
    # argument types a1, ... *an and return type r.
    def callable_var_arg(self, min_args, *a):
        return Callable(a[:-1], min_args, True, a[-1], False)


# Extensino of TypeFixture that contains additional generic interface types.
class InterfaceTypeFixture(TypeFixture):
    # interface GF<T>
    gfi = make_type_info('GF', alore.pair(VARS, ['T']), alore.pair(IS_INTERFACE, True))
    
    # class M1 implements GF<A>
    m1i = make_type_info('M1', alore.pair(INTERFACES, [self.gfi]), alore.pair(BASE_DEFS, [Instance(self.gfi, [self.a])]))
    
    gfa = Instance(self.gfi, [self.a]) # GF<A>
    gfb = Instance(self.gfi, [self.b]) # GF<B>
    
    m1 = Instance(self.m1i, []) # M1


# Make a TypeInfo suitable for use in unit tests.
TypeInfo make_type_info(any name, any *args):
    map = {args}
    
    type_def = TypeDef(name, Block([]), None, [])
    type_def.full_name = name
    
    if map.has_key(VARS):
        list<TypeVarDef> v = []
        id = 1
        for n in map[VARS]:
            v.append(TypeVarDef(n, id))
            id += 1
        type_def.type_vars = TypeVars(v)
    
    info = TypeInfo({}, {}, type_def)
    info.base = map.get(BASE, None)
    info.bases = map.get(BASE_DEFS, [])
    info.interfaces = map.get(INTERFACES, []) # TODO fix
    
    return info
