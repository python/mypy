"""Tests for studying mypy."""

def test_add(i: int, j: int) -> int:
    return i + j
    
test_add(1, 2)
test_add('a', 'b')  # Should create error.
