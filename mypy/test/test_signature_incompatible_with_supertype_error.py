from __future__ import annotations

from unittest import TestCase

from mypy.util import get_qualified_name


class TestClassA:
    pass


class TestClassB:
    pass


class TestGetQualifiedName(TestCase):
    def test_existing_class_in_current_module(self):
        result = get_qualified_name("TestClassA")
        expected = f"{__name__}.TestClassA"
        self.assertEqual(result, expected)

    def test_existing_class_in_current_module_another(self):
        result = get_qualified_name("TestClassB")
        expected = f"{__name__}.TestClassB"
        self.assertEqual(result, expected)

    def test_non_existing_class(self):
        result = get_qualified_name("NonExistentClass")
        self.assertEqual(result, "NonExistentClass")

    def test_empty_class_name(self):
        result = get_qualified_name("")
        self.assertEqual(result, "")
