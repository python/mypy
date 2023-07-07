from __future__ import annotations

import pytest

from mypy.constraints import SUBTYPE_OF, SUPERTYPE_OF, Constraint, infer_constraints
from mypy.test.helpers import Suite
from mypy.test.typefixture import TypeFixture
from mypy.types import Instance, TupleType, UnpackType


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

    @pytest.mark.xfail
    def test_basic_type_var_tuple_subtype(self) -> None:
        fx = self.fx
        assert infer_constraints(
            Instance(fx.gvi, [UnpackType(fx.ts)]), Instance(fx.gvi, [fx.a, fx.b]), SUBTYPE_OF
        ) == [
            Constraint(type_var=fx.ts, op=SUBTYPE_OF, target=TupleType([fx.a, fx.b], fx.std_tuple))
        ]

    def test_basic_type_var_tuple(self) -> None:
        fx = self.fx
        assert infer_constraints(
            Instance(fx.gvi, [UnpackType(fx.ts)]), Instance(fx.gvi, [fx.a, fx.b]), SUPERTYPE_OF
        ) == [
            Constraint(
                type_var=fx.ts, op=SUPERTYPE_OF, target=TupleType([fx.a, fx.b], fx.std_tuple)
            )
        ]

    def test_type_var_tuple_with_prefix_and_suffix(self) -> None:
        fx = self.fx
        assert set(
            infer_constraints(
                Instance(fx.gv2i, [fx.t, UnpackType(fx.ts), fx.s]),
                Instance(fx.gv2i, [fx.a, fx.b, fx.c, fx.d]),
                SUPERTYPE_OF,
            )
        ) == {
            Constraint(type_var=fx.t, op=SUPERTYPE_OF, target=fx.a),
            Constraint(
                type_var=fx.ts, op=SUPERTYPE_OF, target=TupleType([fx.b, fx.c], fx.std_tuple)
            ),
            Constraint(type_var=fx.s, op=SUPERTYPE_OF, target=fx.d),
        }

    def test_unpack_homogenous_tuple(self) -> None:
        fx = self.fx
        assert set(
            infer_constraints(
                Instance(fx.gvi, [UnpackType(Instance(fx.std_tuplei, [fx.t]))]),
                Instance(fx.gvi, [fx.a, fx.b]),
                SUPERTYPE_OF,
            )
        ) == {
            Constraint(type_var=fx.t, op=SUPERTYPE_OF, target=fx.a),
            Constraint(type_var=fx.t, op=SUPERTYPE_OF, target=fx.b),
        }

    def test_unpack_homogenous_tuple_with_prefix_and_suffix(self) -> None:
        fx = self.fx
        assert set(
            infer_constraints(
                Instance(fx.gv2i, [fx.t, UnpackType(Instance(fx.std_tuplei, [fx.s])), fx.u]),
                Instance(fx.gv2i, [fx.a, fx.b, fx.c, fx.d]),
                SUPERTYPE_OF,
            )
        ) == {
            Constraint(type_var=fx.t, op=SUPERTYPE_OF, target=fx.a),
            Constraint(type_var=fx.s, op=SUPERTYPE_OF, target=fx.b),
            Constraint(type_var=fx.s, op=SUPERTYPE_OF, target=fx.c),
            Constraint(type_var=fx.u, op=SUPERTYPE_OF, target=fx.d),
        }

    def test_unpack_tuple(self) -> None:
        fx = self.fx
        assert set(
            infer_constraints(
                Instance(
                    fx.gvi,
                    [
                        UnpackType(
                            TupleType([fx.t, fx.s], fallback=Instance(fx.std_tuplei, [fx.o]))
                        )
                    ],
                ),
                Instance(fx.gvi, [fx.a, fx.b]),
                SUPERTYPE_OF,
            )
        ) == {
            Constraint(type_var=fx.t, op=SUPERTYPE_OF, target=fx.a),
            Constraint(type_var=fx.s, op=SUPERTYPE_OF, target=fx.b),
        }

    def test_unpack_with_prefix_and_suffix(self) -> None:
        fx = self.fx
        assert set(
            infer_constraints(
                Instance(
                    fx.gv2i,
                    [
                        fx.u,
                        UnpackType(
                            TupleType([fx.t, fx.s], fallback=Instance(fx.std_tuplei, [fx.o]))
                        ),
                        fx.u,
                    ],
                ),
                Instance(fx.gv2i, [fx.a, fx.b, fx.c, fx.d]),
                SUPERTYPE_OF,
            )
        ) == {
            Constraint(type_var=fx.u, op=SUPERTYPE_OF, target=fx.a),
            Constraint(type_var=fx.t, op=SUPERTYPE_OF, target=fx.b),
            Constraint(type_var=fx.s, op=SUPERTYPE_OF, target=fx.c),
            Constraint(type_var=fx.u, op=SUPERTYPE_OF, target=fx.d),
        }

    def test_unpack_tuple_length_non_match(self) -> None:
        fx = self.fx
        assert set(
            infer_constraints(
                Instance(
                    fx.gv2i,
                    [
                        fx.u,
                        UnpackType(
                            TupleType([fx.t, fx.s], fallback=Instance(fx.std_tuplei, [fx.o]))
                        ),
                        fx.u,
                    ],
                ),
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

    def test_paramspec_constrained_with_concatenate(self) -> None:
        # for legibility (and my own understanding), `Tester.normal()` is `Tester[P]`
        #  and `Tester.concatenate()` is `Tester[Concatenate[A, P]]`
        #  ... and 2nd arg to infer_constraints ends up on LHS of equality
        fx = self.fx

        # equiv to: x: Tester[Q] = Tester.normal()
        assert set(
            infer_constraints(Instance(fx.gpsi, [fx.p]), Instance(fx.gpsi, [fx.q]), SUBTYPE_OF)
        ) == {Constraint(type_var=fx.p, op=SUPERTYPE_OF, target=fx.q)}

        # equiv to: x: Tester[Q] = Tester.concatenate()
        assert set(
            infer_constraints(
                Instance(fx.gpsi, [fx.p_concatenate]), Instance(fx.gpsi, [fx.q]), SUBTYPE_OF
            )
        ) == {
            # TODO: this is obviously wrong, I think?
            Constraint(type_var=fx.p, op=SUPERTYPE_OF, target=fx.q)
        }

        # equiv to: x: Tester[Concatenate[B, Q]] = Tester.normal()
        assert set(
            infer_constraints(
                Instance(fx.gpsi, [fx.p]), Instance(fx.gpsi, [fx.q_concatenate]), SUBTYPE_OF
            )
        ) == {Constraint(type_var=fx.p, op=SUPERTYPE_OF, target=fx.q_concatenate)}

        # equiv to: x: Tester[Concatenate[B, Q]] = Tester.concatenate()
        assert set(
            infer_constraints(
                Instance(fx.gpsi, [fx.p_concatenate]),
                Instance(fx.gpsi, [fx.q_concatenate]),
                SUBTYPE_OF,
            )
        ) == {
            # this is correct as we assume other parts of mypy will warn that [B] != [A]
            Constraint(type_var=fx.p, op=SUPERTYPE_OF, target=fx.q)
        }

        # equiv to: x: Tester[Concatenate[A, Q]] = Tester.concatenate()
        assert set(
            infer_constraints(
                Instance(fx.gpsi, [fx.p_concatenate]),
                Instance(fx.gpsi, [fx.q_concatenate]),
                SUBTYPE_OF,
            )
        ) == {Constraint(type_var=fx.p, op=SUPERTYPE_OF, target=fx.q)}
