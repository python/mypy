from __future__ import annotations

from mypy.constraints import SUBTYPE_OF, SUPERTYPE_OF, Constraint, infer_constraints
from mypy.test.helpers import Suite
from mypy.test.typefixture import TypeFixture
from mypy.typeops import make_simplified_union
from mypy.types import Instance, TupleType, UnionType, UnpackType


class ConstraintsSuite(Suite):
    def setUp(self) -> None:
        self.fx = TypeFixture()

    def test_no_type_variables(self) -> None:
        assert not infer_constraints(self.fx.o, self.fx.o, SUBTYPE_OF)

    def test_basic_type_variable(self) -> None:
        fx = self.fx
        for direction in [SUBTYPE_OF, SUPERTYPE_OF]:
            assert infer_constraints(fx.gt, fx.ga, direction) == [
                Constraint(type_var=fx.t, op=direction, target=fx.a)
            ]

    def test_basic_type_var_tuple_subtype(self) -> None:
        fx = self.fx
        # Note: B <: A, so fallback for tuple[A, B] is tuple[A, ...]
        fallback = Instance(fx.std_tuplei, [fx.a])
        target = TupleType([fx.a, fx.b], fallback=fallback)
        assert infer_constraints(
            Instance(fx.gvi, [UnpackType(fx.ts)]), Instance(fx.gvi, [fx.a, fx.b]), SUBTYPE_OF
        ) == [Constraint(type_var=fx.ts, op=SUBTYPE_OF, target=target)]

    def test_basic_type_var_tuple(self) -> None:
        # 1. create class A[T](NamedTuple): a: T; b: T; c: T
        namedtuplei = self.fx.make_type_info("NamedTuple", module_name="typing")
        ai = self.fx.make_type_info(
            "A", typevars=[self.fx.t.name], mro=[namedtuplei, self.fx.std_tuplei, self.fx.oi]
        )
        # 2. Create a class MyTuple[T](tuple[T, ...])
        bi = self.fx.make_type_info(
            "MyTuple", typevars=[self.fx.t.name], mro=[self.fx.std_tuplei, self.fx.oi]
        )

        infer_constraints(Instance(ai, [self.fx.t]), Instance(bi, [self.fx.t]), SUBTYPE_OF)

    def test_type_var_tuple_with_prefix_and_suffix(self) -> None:
        fx = self.fx
        # Note: B <: A and C <: A, so fallback for tuple[B, C] is tuple[B | C, ...]
        fallback = Instance(fx.std_tuplei, [make_simplified_union([fx.b, fx.c])])
        target = TupleType([fx.b, fx.c], fallback=fallback)
        assert set(
            infer_constraints(
                # GV[T, *TS, S]
                Instance(fx.gv2i, [fx.t, UnpackType(fx.ts), fx.s]),
                Instance(fx.gv2i, [fx.a, fx.b, fx.c, fx.d]),
                SUPERTYPE_OF,
            )
        ) == {
            Constraint(type_var=fx.t, op=SUPERTYPE_OF, target=fx.a),
            Constraint(type_var=fx.ts, op=SUPERTYPE_OF, target=target),
            Constraint(type_var=fx.ts, op=SUBTYPE_OF, target=target),
            Constraint(type_var=fx.s, op=SUPERTYPE_OF, target=fx.d),
        }

    def test_wrapped_tuple_identical_results(self) -> None:
        # test inferred constraints of tuple[T, ...] <: tuple[B, C]
        # vs inferred constraints of tuple[*tuple[T, ...]] <: tuple[B, C]
        fx = self.fx
        t = Instance(fx.std_tuplei, [fx.t])

        # check subtype constraints
        assert (
            set(
                infer_constraints(
                    t, TupleType([self.fx.b, self.fx.c], fallback=self.fx.std_tuple), SUBTYPE_OF
                )
            )
            == set(
                infer_constraints(
                    TupleType([UnpackType(t)], fallback=self.fx.std_tuple),
                    TupleType([self.fx.b, self.fx.c], fallback=self.fx.std_tuple),
                    SUBTYPE_OF,
                )
            )
            == {Constraint(type_var=fx.t, op=SUBTYPE_OF, target=UnionType([fx.b, fx.c]))}
        )

        # check supertype constraints
        assert (
            set(
                infer_constraints(
                    t, TupleType([self.fx.b, self.fx.c], fallback=self.fx.std_tuple), SUPERTYPE_OF
                )
            )
            == set(
                infer_constraints(
                    TupleType([UnpackType(t)], fallback=self.fx.std_tuple),
                    TupleType([self.fx.b, self.fx.c], fallback=self.fx.std_tuple),
                    SUPERTYPE_OF,
                )
            )
            == {
                # TODO: replace with Intersection[B, C] once supported
                Constraint(type_var=fx.t, op=SUPERTYPE_OF, target=fx.b),
                Constraint(type_var=fx.t, op=SUPERTYPE_OF, target=fx.c),
            }
        )

    def test_unpack_homogeneous_tuple(self) -> None:
        fx = self.fx
        # class GV[*Ts]
        # template: GV[*tuple[T, ...]]
        # actual: GV[A, B]
        # So, T :> A and T :> B
        assert set(
            infer_constraints(
                Instance(fx.gvi, [UnpackType(Instance(fx.std_tuplei, [fx.t]))]),
                Instance(fx.gvi, [fx.b, fx.c]),
                SUPERTYPE_OF,
            )
        ) == {
            # TODO: replace with Intersection[B, C] once supported
            Constraint(type_var=fx.t, op=SUPERTYPE_OF, target=fx.b),
            Constraint(type_var=fx.t, op=SUPERTYPE_OF, target=fx.c),
            # NOTE: TVTs are currently invariant, so we also get subtype constraints.
            Constraint(type_var=fx.t, op=SUBTYPE_OF, target=UnionType([fx.b, fx.c])),
        }

    def test_unpack_homogeneous_tuple_with_prefix_and_suffix(self) -> None:
        fx = self.fx
        # class GV2[T, *Ts, S]
        # classes A, B, C, D with A :> B and A :> C
        # template: GV2[T, *tuple[S, ...], U]
        # actual: GV2[A, B, C, D];
        # prefix matching implies T :> A
        # suffix matching implies U :> D
        # unpack matching implies S :> B and S :> C and S <: B and S <: C
        assert set(
            infer_constraints(
                Instance(fx.gv2i, [fx.t, UnpackType(Instance(fx.std_tuplei, [fx.s])), fx.u]),
                Instance(fx.gv2i, [fx.a, fx.b, fx.c, fx.d]),
                SUPERTYPE_OF,
            )
        ) == {
            Constraint(type_var=fx.t, op=SUPERTYPE_OF, target=fx.a),
            Constraint(type_var=fx.u, op=SUPERTYPE_OF, target=fx.d),
            # TODO: replace with Intersection[B, C] once supported
            Constraint(type_var=fx.s, op=SUPERTYPE_OF, target=fx.b),
            Constraint(type_var=fx.s, op=SUPERTYPE_OF, target=fx.c),
            # NOTE: TVTs are currently invariant, so we also get subtype constraints.
            Constraint(type_var=fx.s, op=SUBTYPE_OF, target=UnionType([fx.b, fx.c])),
        }

    def test_unpack_with_prefix_and_suffix(self) -> None:
        fx = self.fx
        assert set(
            infer_constraints(
                Instance(fx.gv2i, [fx.u, fx.t, fx.s, fx.u]),
                Instance(fx.gv2i, [fx.a, fx.b, fx.c, fx.d]),
                SUPERTYPE_OF,
            )
        ) == {
            Constraint(type_var=fx.u, op=SUPERTYPE_OF, target=fx.a),
            Constraint(type_var=fx.t, op=SUPERTYPE_OF, target=fx.b),
            Constraint(type_var=fx.t, op=SUBTYPE_OF, target=fx.b),
            Constraint(type_var=fx.s, op=SUPERTYPE_OF, target=fx.c),
            Constraint(type_var=fx.s, op=SUBTYPE_OF, target=fx.c),
            Constraint(type_var=fx.u, op=SUPERTYPE_OF, target=fx.d),
        }

    def test_unpack_tuple_length_non_match(self) -> None:
        fx = self.fx
        assert set(
            infer_constraints(
                Instance(fx.gv2i, [fx.u, fx.t, fx.s, fx.u]),
                Instance(fx.gv2i, [fx.a, fx.b, fx.d]),
                SUPERTYPE_OF,
            )
            # We still get constraints on the prefix/suffix in this case.
        ) == {
            Constraint(type_var=fx.u, op=SUPERTYPE_OF, target=fx.a),
            Constraint(type_var=fx.u, op=SUPERTYPE_OF, target=fx.d),
        }

    def test_var_length_tuple_with_fixed_length_tuple(self) -> None:
        fx = self.fx
        assert not infer_constraints(
            TupleType([fx.t, fx.s], fallback=Instance(fx.std_tuplei, [fx.o])),
            Instance(fx.std_tuplei, [fx.a]),
            SUPERTYPE_OF,
        )
