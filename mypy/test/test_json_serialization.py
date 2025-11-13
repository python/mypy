"""Tests for JSON serialization utilities in mypy.util.

This module tests the json_dumps and json_loads functions with various
edge cases, error conditions, and performance characteristics.
"""

from __future__ import annotations

import unittest
from typing import Any

from mypy.util import json_dumps, json_loads

# Try to import orjson to test both code paths
try:
    import orjson

    HAS_ORJSON = True
except ImportError:
    HAS_ORJSON = False


class TestJsonSerialization(unittest.TestCase):
    """Test JSON serialization and deserialization functions."""

    def test_basic_serialization(self) -> None:
        """Test basic object serialization."""
        obj = {"key": "value", "number": 42, "list": [1, 2, 3]}
        serialized = json_dumps(obj)
        self.assertIsInstance(serialized, bytes)
        deserialized = json_loads(serialized)
        self.assertEqual(deserialized, obj)

    def test_sorted_keys(self) -> None:
        """Test that keys are always sorted for deterministic output."""
        obj = {"z": 1, "a": 2, "m": 3}
        serialized = json_dumps(obj)
        # Keys should be in alphabetical order
        self.assertIn(b'"a"', serialized)
        self.assertIn(b'"m"', serialized)
        self.assertIn(b'"z"', serialized)
        # Check that 'a' comes before 'm' and 'm' comes before 'z'
        a_pos = serialized.index(b'"a"')
        m_pos = serialized.index(b'"m"')
        z_pos = serialized.index(b'"z"')
        self.assertLess(a_pos, m_pos)
        self.assertLess(m_pos, z_pos)

    def test_debug_mode_indentation(self) -> None:
        """Test that debug mode produces indented output."""
        obj = {"key": "value"}
        serialized = json_dumps(obj, debug=True)
        # Debug output should contain newlines and spaces for indentation
        self.assertIn(b"\n", serialized)
        self.assertIn(b"  ", serialized)

    def test_compact_mode(self) -> None:
        """Test that non-debug mode produces compact output."""
        obj = {"key": "value", "number": 42}
        serialized = json_dumps(obj, debug=False)
        # Compact output should not have unnecessary whitespace
        # (may have newlines in orjson, but should be minimal)
        decoded = serialized.decode("utf-8")
        # Should not have indentation spaces
        self.assertNotIn("  ", decoded)

    def test_large_integer(self) -> None:
        """Test handling of integers that exceed 64-bit range."""
        # This is larger than 2^63-1 (max signed 64-bit integer)
        large_int = 2**70
        obj = {"large": large_int}
        # Should not raise an error, should fall back to standard json
        serialized = json_dumps(obj)
        deserialized = json_loads(serialized)
        self.assertEqual(deserialized["large"], large_int)

    def test_nested_structures(self) -> None:
        """Test deeply nested data structures."""
        obj = {"level1": {"level2": {"level3": {"level4": "deep"}}}}
        serialized = json_dumps(obj)
        deserialized = json_loads(serialized)
        self.assertEqual(deserialized, obj)

    def test_unicode_strings(self) -> None:
        """Test Unicode string handling."""
        obj = {"emoji": "🐍", "chinese": "你好", "arabic": "مرحبا"}
        serialized = json_dumps(obj)
        deserialized = json_loads(serialized)
        self.assertEqual(deserialized, obj)

    def test_special_values(self) -> None:
        """Test special JSON values."""
        obj = {"null": None, "true": True, "false": False, "empty_list": [], "empty_dict": {}}
        serialized = json_dumps(obj)
        deserialized = json_loads(serialized)
        self.assertEqual(deserialized, obj)

    def test_numeric_types(self) -> None:
        """Test various numeric types."""
        obj = {"int": 42, "float": 3.14159, "negative": -100, "zero": 0}
        serialized = json_dumps(obj)
        deserialized = json_loads(serialized)
        self.assertEqual(deserialized, obj)

    def test_list_serialization(self) -> None:
        """Test list serialization."""
        obj = [1, "two", 3.0, None, True, {"nested": "dict"}]
        serialized = json_dumps(obj)
        deserialized = json_loads(serialized)
        self.assertEqual(deserialized, obj)

    def test_invalid_json_loads(self) -> None:
        """Test that invalid JSON raises appropriate errors."""
        invalid_json = b"{invalid json}"
        with self.assertRaises(Exception):  # JSONDecodeError or ValueError
            json_loads(invalid_json)

    def test_non_serializable_object(self) -> None:
        """Test that non-serializable objects raise TypeError."""

        class CustomClass:
            pass

        obj = {"custom": CustomClass()}
        with self.assertRaises(TypeError):
            json_dumps(obj)

    def test_roundtrip_consistency(self) -> None:
        """Test that multiple serialize-deserialize cycles are consistent."""
        obj = {"key": "value", "nested": {"a": 1, "b": 2}}
        # First cycle
        serialized1 = json_dumps(obj)
        deserialized1 = json_loads(serialized1)
        # Second cycle
        serialized2 = json_dumps(deserialized1)
        deserialized2 = json_loads(serialized2)
        # All should be equal
        self.assertEqual(obj, deserialized1)
        self.assertEqual(obj, deserialized2)
        self.assertEqual(serialized1, serialized2)

    def test_empty_structures(self) -> None:
        """Test empty data structures."""
        empty_dict = {}
        empty_list: list[Any] = []
        self.assertEqual(json_loads(json_dumps(empty_dict)), empty_dict)
        self.assertEqual(json_loads(json_dumps(empty_list)), empty_list)

    @unittest.skipIf(not HAS_ORJSON, "orjson not installed")
    def test_orjson_available(self) -> None:
        """Test that orjson is being used when available."""
        obj = {"test": "orjson"}
        serialized = json_dumps(obj)
        # This test just ensures orjson path is exercised
        self.assertIsInstance(serialized, bytes)

    def test_deterministic_output(self) -> None:
        """Test that serialization is deterministic across multiple calls."""
        obj = {"z": 1, "a": 2, "m": 3, "b": 4}
        results = [json_dumps(obj) for _ in range(5)]
        # All results should be identical
        for result in results[1:]:
            self.assertEqual(results[0], result)


class TestJsonPerformance(unittest.TestCase):
    """Performance-related tests for JSON serialization."""

    def test_large_object_serialization(self) -> None:
        """Test serialization of large objects."""
        # Create a reasonably large object
        large_obj = {f"key_{i}": {"nested": i, "value": f"string_{i}"} for i in range(1000)}
        serialized = json_dumps(large_obj)
        deserialized = json_loads(serialized)
        self.assertEqual(len(deserialized), 1000)

    def test_deeply_nested_object(self) -> None:
        """Test handling of deeply nested objects."""
        # Create a deeply nested structure (but not too deep to avoid recursion limits)
        obj: dict[str, Any] = {"value": 0}
        current = obj
        for i in range(50):
            current["nested"] = {"value": i + 1}
            current = current["nested"]

        serialized = json_dumps(obj)
        deserialized = json_loads(serialized)
        self.assertEqual(deserialized["value"], 0)


if __name__ == "__main__":
    unittest.main()
