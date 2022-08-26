from mypy.constraints import SUBTYPE_OF, SUPERTYPE_OF, Constraint, infer_constraints
from mypy.test.helpers import Suite
from mypy.test.typefixture import TypeFixture


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
