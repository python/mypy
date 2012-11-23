from mtypes import (
    TypeVar, Any, Void, ErrorType, NoneTyp, Instance, Callable, TypeVarDef,
    TypeVars
)
from checker import BasicTypes
from nodes import TypeInfo, TypeDef, Block


BASE = 0
VARS = 1
BASE_DEFS = 2
IS_INTERFACE = 3
INTERFACES = 4


class TypeFixture:
    """Helper class that is used as a fixture in type-related unit tests. The
    members are initialized to contain various type-related values.
    """
    def __init__(self):
        # Type variables

        self.t = TypeVar('T', 1)    # T`1 (type variable)
        self.tf = TypeVar('T', -1)  # T`-1 (type variable)
        self.tf2 = TypeVar('T', -2) # T`-2 (type variable)
        self.s = TypeVar('S', 2)    # S`2 (type variable)
        self.s1 = TypeVar('S', 1)   # S`1 (type variable)
        self.sf = TypeVar('S', -2)  # S`-2 (type variable)
        self.sf1 = TypeVar('S', -1) # S`-1 (type variable)

        # Simple types

        self.dyn = Any()
        self.void = Void()
        self.err = ErrorType()
        self.nilt = NoneTyp()

        # Interface TypeInfos

        # interface F
        self.fi = make_type_info('F', (IS_INTERFACE, True))

        # interface F2
        self.f2i = make_type_info('F2', (IS_INTERFACE, True))

        # interface F3 is F
        self.f3i = make_type_info('F3', (IS_INTERFACE, True), (BASE, self.fi))

        # Class TypeInfos

        self.oi = make_type_info('builtins.object')       # class object
        self.std_tuplei = make_type_info('builtins.tuple') # class tuple
        self.std_typei = make_type_info('builtins.type')   # class type
        self.std_functioni = make_type_info('std::Function') # Function TODO
        self.ai = make_type_info('A', (BASE, self.oi))       # class A
        self.bi = make_type_info('B', (BASE, self.ai))       # class B is A
        self.ci = make_type_info('C', (BASE, self.ai))       # class C is A
        self.di = make_type_info('D', (BASE, self.oi))       # class D

        # class E(F)
        self.ei = make_type_info('E', (INTERFACES, [self.fi]), (BASE, self.oi))

        # class E2(F2, F)
        self.e2i = make_type_info('E2', (INTERFACES, [self.f2i, self.fi]),
                                  (BASE, self.oi))

        # class E3(F, F2)
        self.e3i = make_type_info('E3', (INTERFACES, [self.fi, self.f2i]),
                                  (BASE, self.oi))

        # Generic class TypeInfos

        # class G<T>
        self.gi = make_type_info('G', (BASE, self.oi), (VARS, ['T']))
        # class G2<T>
        self.g2i = make_type_info('G2', (BASE, self.oi), (VARS, ['T']))
        # class H<S, T>
        self.hi = make_type_info('H', (BASE, self.oi), (VARS, ['S', 'T']))
        # class GS<T, S> is G<S>
        self.gsi = make_type_info('GS', (BASE, self.gi), (VARS, ['T', 'S']),
                                  (BASE_DEFS, [Instance(self.gi, [self.s])]))
        # class GS2<S> is G<S>
        self.gs2i = make_type_info('GS2', (BASE, self.gi), (VARS, ['S']),
                                   (BASE_DEFS, [Instance(self.gi, [self.s1])]))
        # class Array as <T>
        self.std_listi = make_type_info('builtins.list', (BASE, self.oi),
                                        (VARS, ['T']))

        # Instance types

        self.o = Instance(self.oi, [])                       # object
        self.std_tuple = Instance(self.std_tuplei, [])       # tuple
        self.std_type = Instance(self.std_typei, [])         # type
        self.std_function = Instance(self.std_functioni, []) # function TODO
        self.a = Instance(self.ai, [])          # A
        self.b = Instance(self.bi, [])          # B
        self.c = Instance(self.ci, [])          # C
        self.d = Instance(self.di, [])          # D

        self.e = Instance(self.ei, [])          # E
        self.e2 = Instance(self.e2i, [])        # E2
        self.e3 = Instance(self.e3i, [])        # E3

        self.f = Instance(self.fi, [])          # F
        self.f2 = Instance(self.f2i, [])        # F2
        self.f3 = Instance(self.f3i, [])        # F3

        # Generic instance types

        self.ga = Instance(self.gi, [self.a])        # G<A>
        self.gb = Instance(self.gi, [self.b])        # G<B>
        self.go = Instance(self.gi, [self.o])        # G<Object>
        self.gt = Instance(self.gi, [self.t])        # G<T`1>
        self.gtf = Instance(self.gi, [self.tf])      # G<T`-1>
        self.gtf2 = Instance(self.gi, [self.tf2])    # G<T`-2>
        self.gs = Instance(self.gi, [self.s])        # G<S>
        self.gdyn = Instance(self.gi, [self.dyn])    # G<dynamic>

        self.g2a = Instance(self.g2i, [self.a])      # G2<A>

        self.gsab = Instance(self.gsi, [self.a, self.b])  # GS<A, B>
        self.gsba = Instance(self.gsi, [self.b, self.a])  # GS<B, A>

        self.gs2a = Instance(self.gs2i, [self.a])    # GS2<A>

        self.hab = Instance(self.hi, [self.a, self.b])    # H<A, B>
        self.haa = Instance(self.hi, [self.a, self.a])    # H<A, A>
        self.hbb = Instance(self.hi, [self.b, self.b])    # H<B, B>
        self.hts = Instance(self.hi, [self.t, self.s])    # H<T, S>

        self.lsta = Instance(self.std_listi, [self.a])  # A[]
        self.lstb = Instance(self.std_listi, [self.b])  # B[]

        # Basic types
        self.basic = BasicTypes(self.o, self.std_type, self.std_tuple,
                                self.std_function)
    
    # Helper methods
    
    def callable(self, *a):
        """callable(a1, ..., an, r) constructs a callable with argument types
        a1, ... an and return type r.
        """
        return Callable(a[:-1], len(a) - 1, False, a[-1], False)
    
    def callable_type(self, *a):
        """typeCallable(a1, ..., an, r) constructs a callable with
        argument types a1, ... an and return type r, and which
        represents a type.
        """
        return Callable(a[:-1], len(a) - 1, False, a[-1], True)
    
    def callable_default(self, min_args, *a):
        """callableDefault(minArgs, a1, ..., an, r) constructs a
        callable with argument types a1, ... an and return type r,
        with minArgs mandatory fixed arguments.
        """
        return Callable(a[:-1], min_args, False, a[-1], False)
    
    def callable_var_arg(self, min_args, *a):
        """callableVarArg(minArgs, a1, ..., an, r) constructs a callable with
        argument types a1, ... *an and return type r.
        """
        return Callable(a[:-1], min_args, True, a[-1], False)


class InterfaceTypeFixture(TypeFixture):
    """Extension of TypeFixture that contains additional generic
    interface types."""
    def __init__(self):
        super().__init__()
        # interface GF<T>
        self.gfi = make_type_info('GF', (VARS, ['T']), (IS_INTERFACE, True))
    
        # class M1 implements GF<A>
        self.m1i = make_type_info('M1', (INTERFACES, [self.gfi]),
                                  (BASE_DEFS, [Instance(self.gfi, [self.a])]))

        self.gfa = Instance(self.gfi, [self.a]) # GF<A>
        self.gfb = Instance(self.gfi, [self.b]) # GF<B>

        self.m1 = Instance(self.m1i, []) # M1


TypeInfo make_type_info(any name, any *args):
    """Make a TypeInfo suitable for use in unit tests."""
    map = dict(args)
    
    type_def = TypeDef(name, Block([]), None, [])
    type_def.full_name = name
    
    if VARS in map:
        TypeVarDef[] v = []
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
