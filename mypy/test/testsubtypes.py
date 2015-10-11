from mypy.myunit import Suite, assert_true
from mypy.nodes import CONTRAVARIANT, INVARIANT, COVARIANT
from mypy.subtypes import is_subtype
from mypy.typefixture import TypeFixture, InterfaceTypeFixture


class SubtypingSuite(Suite):
    def set_up(self):
        self.fx = TypeFixture(INVARIANT)
        self.fx_contra = TypeFixture(CONTRAVARIANT)
        self.fx_co = TypeFixture(COVARIANT)

    def test_trivial_cases(self):
        for simple in self.fx_co.void, self.fx_co.a, self.fx_co.o, self.fx_co.b:
            self.assert_subtype(simple, simple)

    def test_instance_subtyping(self):
        self.assert_strict_subtype(self.fx.a, self.fx.o)
        self.assert_strict_subtype(self.fx.b, self.fx.o)
        self.assert_strict_subtype(self.fx.b, self.fx.a)

        self.assert_not_subtype(self.fx.a, self.fx.d)
        self.assert_not_subtype(self.fx.b, self.fx.c)

    def test_simple_generic_instance_subtyping_invariant(self):
        self.assert_subtype(self.fx.ga, self.fx.ga)
        self.assert_subtype(self.fx.hab, self.fx.hab)

        self.assert_not_subtype(self.fx.ga, self.fx.g2a)
        self.assert_not_subtype(self.fx.ga, self.fx.gb)
        self.assert_not_subtype(self.fx.gb, self.fx.ga)

    def test_simple_generic_instance_subtyping_covariant(self):
        self.assert_subtype(self.fx_co.ga, self.fx_co.ga)
        self.assert_subtype(self.fx_co.hab, self.fx_co.hab)

        self.assert_not_subtype(self.fx_co.ga, self.fx_co.g2a)
        self.assert_not_subtype(self.fx_co.ga, self.fx_co.gb)
        self.assert_subtype(self.fx_co.gb, self.fx_co.ga)

    def test_simple_generic_instance_subtyping_contravariant(self):
        self.assert_subtype(self.fx_contra.ga, self.fx_contra.ga)
        self.assert_subtype(self.fx_contra.hab, self.fx_contra.hab)

        self.assert_not_subtype(self.fx_contra.ga, self.fx_contra.g2a)
        self.assert_subtype(self.fx_contra.ga, self.fx_contra.gb)
        self.assert_not_subtype(self.fx_contra.gb, self.fx_contra.ga)

    def test_generic_subtyping_with_inheritance_invariant(self):
        self.assert_subtype(self.fx.gsab, self.fx.gb)
        self.assert_not_subtype(self.fx.gsab, self.fx.ga)
        self.assert_not_subtype(self.fx.gsaa, self.fx.gb)

    def test_generic_subtyping_with_inheritance_covariant(self):
        self.assert_subtype(self.fx_co.gsab, self.fx_co.gb)
        self.assert_subtype(self.fx_co.gsab, self.fx_co.ga)
        self.assert_not_subtype(self.fx_co.gsaa, self.fx_co.gb)

    def test_generic_subtyping_with_inheritance_contravariant(self):
        self.assert_subtype(self.fx_contra.gsab, self.fx_contra.gb)
        self.assert_not_subtype(self.fx_contra.gsab, self.fx_contra.ga)
        self.assert_subtype(self.fx_contra.gsaa, self.fx_contra.gb)

    def test_interface_subtyping(self):
        self.assert_subtype(self.fx.e, self.fx.f)
        self.assert_equivalent(self.fx.f, self.fx.f)
        self.assert_not_subtype(self.fx.a, self.fx.f)

    def test_generic_interface_subtyping(self):
        # TODO make this work
        self.skip()

        fx2 = InterfaceTypeFixture()

        self.assert_subtype(fx2.m1, fx2.gfa)
        self.assert_not_subtype(fx2.m1, fx2.gfb)

        self.assert_equivalent(fx2.gfa, fx2.gfa)

    def test_basic_callable_subtyping(self):
        self.assert_strict_subtype(self.fx.callable(self.fx.o, self.fx.d),
                                   self.fx.callable(self.fx.a, self.fx.d))
        self.assert_strict_subtype(self.fx.callable(self.fx.d, self.fx.b),
                                   self.fx.callable(self.fx.d, self.fx.a))

        self.assert_unrelated(self.fx.callable(self.fx.a, self.fx.a),
                              self.fx.callable(self.fx.a, self.fx.void))

        self.assert_unrelated(
            self.fx.callable(self.fx.a, self.fx.a, self.fx.a),
            self.fx.callable(self.fx.a, self.fx.a))

    def test_default_arg_callable_subtyping(self):
        self.assert_strict_subtype(
            self.fx.callable_default(1, self.fx.a, self.fx.d, self.fx.a),
            self.fx.callable(self.fx.a, self.fx.d, self.fx.a))

        self.assert_strict_subtype(
            self.fx.callable_default(1, self.fx.a, self.fx.d, self.fx.a),
            self.fx.callable(self.fx.a, self.fx.a))

        self.assert_strict_subtype(
            self.fx.callable_default(0, self.fx.a, self.fx.d, self.fx.a),
            self.fx.callable_default(1, self.fx.a, self.fx.d, self.fx.a))

        self.assert_unrelated(
            self.fx.callable_default(1, self.fx.a, self.fx.d, self.fx.a),
            self.fx.callable(self.fx.d, self.fx.d, self.fx.a))

        self.assert_unrelated(
            self.fx.callable_default(0, self.fx.a, self.fx.d, self.fx.a),
            self.fx.callable_default(1, self.fx.a, self.fx.a, self.fx.a))

        self.assert_unrelated(
            self.fx.callable_default(1, self.fx.a, self.fx.a),
            self.fx.callable(self.fx.a, self.fx.a, self.fx.a))

    def test_var_arg_callable_subtyping_1(self):
        self.assert_strict_subtype(
            self.fx.callable_var_arg(0, self.fx.a, self.fx.a),
            self.fx.callable_var_arg(0, self.fx.b, self.fx.a))

    def test_var_arg_callable_subtyping_2(self):
        self.assert_strict_subtype(
            self.fx.callable_var_arg(0, self.fx.a, self.fx.a),
            self.fx.callable(self.fx.b, self.fx.a))

    def test_var_arg_callable_subtyping_3(self):
        self.assert_strict_subtype(
            self.fx.callable_var_arg(0, self.fx.a, self.fx.a),
            self.fx.callable(self.fx.a))

    def test_var_arg_callable_subtyping_4(self):
        self.assert_strict_subtype(
            self.fx.callable_var_arg(1, self.fx.a, self.fx.d, self.fx.a),
            self.fx.callable(self.fx.b, self.fx.a))

    def test_var_arg_callable_subtyping_5(self):
        self.assert_strict_subtype(
            self.fx.callable_var_arg(0, self.fx.a, self.fx.d, self.fx.a),
            self.fx.callable(self.fx.b, self.fx.a))

    def test_var_arg_callable_subtyping_6(self):
        self.assert_strict_subtype(
            self.fx.callable_var_arg(0, self.fx.a, self.fx.f, self.fx.d),
            self.fx.callable_var_arg(0, self.fx.b, self.fx.e, self.fx.d))

    def test_var_arg_callable_subtyping_7(self):
        self.assert_not_subtype(
            self.fx.callable_var_arg(0, self.fx.b, self.fx.d),
            self.fx.callable(self.fx.a, self.fx.d))

    def test_var_arg_callable_subtyping_8(self):
        self.assert_not_subtype(
            self.fx.callable_var_arg(0, self.fx.b, self.fx.d),
            self.fx.callable_var_arg(0, self.fx.a, self.fx.a, self.fx.d))
        self.assert_subtype(
            self.fx.callable_var_arg(0, self.fx.a, self.fx.d),
            self.fx.callable_var_arg(0, self.fx.b, self.fx.b, self.fx.d))

    def test_var_arg_callable_subtyping_9(self):
        self.assert_not_subtype(
            self.fx.callable_var_arg(0, self.fx.b, self.fx.b, self.fx.d),
            self.fx.callable_var_arg(0, self.fx.a, self.fx.d))
        self.assert_subtype(
            self.fx.callable_var_arg(0, self.fx.a, self.fx.a, self.fx.d),
            self.fx.callable_var_arg(0, self.fx.b, self.fx.d))

    def test_type_callable_subtyping(self):
        self.assert_strict_subtype(
            self.fx.callable_type(self.fx.d, self.fx.a), self.fx.type_type)

        self.assert_strict_subtype(
            self.fx.callable_type(self.fx.d, self.fx.b),
            self.fx.callable(self.fx.d, self.fx.a))

        self.assert_strict_subtype(self.fx.callable_type(self.fx.a, self.fx.b),
                                   self.fx.callable(self.fx.a, self.fx.b))

    # IDEA: Maybe add these test cases (they are tested pretty well in type
    #       checker tests already):
    #  * more interface subtyping test cases
    #  * more generic interface subtyping test cases
    #  * type variables
    #  * tuple types
    #  * void type
    #  * None type
    #  * any type
    #  * generic function types

    def assert_subtype(self, s, t):
        assert_true(is_subtype(s, t), '{} not subtype of {}'.format(s, t))

    def assert_not_subtype(self, s, t):
        assert_true(not is_subtype(s, t), '{} subtype of {}'.format(s, t))

    def assert_strict_subtype(self, s, t):
        self.assert_subtype(s, t)
        self.assert_not_subtype(t, s)

    def assert_equivalent(self, s, t):
        self.assert_subtype(s, t)
        self.assert_subtype(t, s)

    def assert_unrelated(self, s, t):
        self.assert_not_subtype(s, t)
        self.assert_not_subtype(t, s)
