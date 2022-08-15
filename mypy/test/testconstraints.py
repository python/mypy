from __future__ import annotations

import pytest

from mypy.constraints import SUBTYPE_OF, SUPERTYPE_OF, Constraint, infer_constraints
from mypy.test.helpers import Suite
from mypy.test.typefixture import TypeFixture
from mypy.types import Instance, TypeList, UnpackType


class ConstraintsSuite(Suite):
    def setUp(self) -> None:
        self.fx = TypeFixture()

    def test_no_type_variables(self) -> None:
        assert not infer_constraints(self.fx.o, self.fx.o, SUBTYPE_OF)

    def test_basic_type_variable(self) -> None:
        fx = self.fx
        for direction in [SUBTYPE_OF, SUPERTYPE_OF]:
            assert infer_constraints(fx.gt, fx.ga, direction) == [
                Constraint(type_var=fx.t.id, op=direction, target=fx.a)
            ]

    @pytest.mark.xfail
    def test_basic_type_var_tuple_subtype(self) -> None:
        fx = self.fx
        assert infer_constraints(
            Instance(fx.gvi, [UnpackType(fx.ts)]), Instance(fx.gvi, [fx.a, fx.b]), SUBTYPE_OF
        ) == [Constraint(type_var=fx.ts.id, op=SUBTYPE_OF, target=TypeList([fx.a, fx.b]))]

    def test_basic_type_var_tuple(self) -> None:
        fx = self.fx
        assert infer_constraints(
            Instance(fx.gvi, [UnpackType(fx.ts)]), Instance(fx.gvi, [fx.a, fx.b]), SUPERTYPE_OF
        ) == [Constraint(type_var=fx.ts.id, op=SUPERTYPE_OF, target=TypeList([fx.a, fx.b]))]

    def test_type_var_tuple_with_prefix_and_suffix(self) -> None:
        fx = self.fx
        assert set(
            infer_constraints(
                Instance(fx.gv2i, [fx.t, UnpackType(fx.ts), fx.s]),
                Instance(fx.gv2i, [fx.a, fx.b, fx.c, fx.d]),
                SUPERTYPE_OF,
            )
        ) == {
            Constraint(type_var=fx.t.id, op=SUPERTYPE_OF, target=fx.a),
            Constraint(type_var=fx.ts.id, op=SUPERTYPE_OF, target=TypeList([fx.b, fx.c])),
            Constraint(type_var=fx.s.id, op=SUPERTYPE_OF, target=fx.d),
        }
