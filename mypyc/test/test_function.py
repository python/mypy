import unittest
from unittest.mock import MagicMock, call, patch

from mypy.nodes import TypeInfo
from mypy.types import UnboundType
from mypyc.ir.rtypes import object_rprimitive
from mypyc.irbuild.builder import IRBuilder
from mypyc.irbuild.function import load_type
from mypyc.irbuild.ll_builder import LowLevelIRBuilder
from mypyc.irbuild.mapper import Mapper


class TestFunction(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = MagicMock(spec=IRBuilder)
        self.builder.configure_mock(
            mapper=MagicMock(spec=Mapper), builder=MagicMock(spec=LowLevelIRBuilder)
        )
        self.builder.mapper.configure_mock(type_to_ir=[])
        self.typ = MagicMock(spec=TypeInfo)
        self.unbounded_type = MagicMock(spec=UnboundType)
        self.line = 10

    @patch("mypyc.irbuild.function.builtin_names", {})
    def test_load_type_from_imported_module(self) -> None:
        self.typ.fullname = "json.decoder.JSONDecoder"
        self.typ.name = "JSONDecoder"
        self.unbounded_type.name = "json.JSONDecoder"
        self.builder.imports = {"json": "json"}
        self.builder.load_module.return_value = "json_module"
        self.builder.builder.get_attr.return_value = "JSONDecoder_class"
        result = load_type(self.builder, self.typ, self.unbounded_type, self.line)
        self.builder.load_module.assert_called_once_with("json")
        self.builder.py_get_attr.assert_not_called()
        self.builder.builder.get_attr.assert_called_once_with(
            "json_module", "JSONDecoder", object_rprimitive, self.line, borrow=False
        )
        self.assertEqual(result, "JSONDecoder_class")

    @patch("mypyc.irbuild.function.builtin_names", {})
    def test_load_type_with_deep_nesting(self) -> None:
        self.typ.fullname = "mod1.mod2.mod3.OuterType.InnerType"
        self.typ.name = "InnerType"
        self.unbounded_type.name = "mod4.mod5.mod6.OuterType.InnerType"
        self.builder.imports = {"mod4.mod5": "mod4.mod5"}
        self.builder.load_module.return_value = "mod4.mod5_module"
        self.builder.py_get_attr.side_effect = ["mod4.mod5.mod6_module", "OuterType_class"]
        self.builder.builder.get_attr.return_value = "InnerType_class"
        result = load_type(self.builder, self.typ, self.unbounded_type, self.line)
        self.builder.load_module.assert_called_once_with("mod4.mod5")
        self.builder.py_get_attr.assert_has_calls(
            [
                call("mod4.mod5_module", "mod6", self.line),
                call("mod4.mod5.mod6_module", "OuterType", self.line),
            ]
        )
        self.builder.builder.get_attr.assert_called_once_with(
            "OuterType_class", "InnerType", object_rprimitive, self.line, borrow=False
        )
        self.assertEqual(result, "InnerType_class")
