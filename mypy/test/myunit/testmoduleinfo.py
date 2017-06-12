from mypy import moduleinfo
from mypy.myunit import (
    Suite, assert_equal, assert_true, assert_false
)


class ModuleInfoSuite(Suite):
    def test_is_in_module_collection(self) -> None:
        assert_true(moduleinfo.is_in_module_collection({'foo'}, 'foo'))
        assert_true(moduleinfo.is_in_module_collection({'foo'}, 'foo.bar'))
        assert_false(moduleinfo.is_in_module_collection({'foo'}, 'fo'))
        assert_true(moduleinfo.is_in_module_collection({'foo.bar'}, 'foo.bar'))
        assert_true(moduleinfo.is_in_module_collection({'foo.bar'}, 'foo.bar.zar'))
        assert_false(moduleinfo.is_in_module_collection({'foo.bar'}, 'foo'))
