"""Performance benchmarking utilities for JSON serialization.

This module provides utilities to benchmark and compare the performance of
orjson vs standard json serialization in mypy's caching operations.
"""

from __future__ import annotations

import time
from typing import Any, Callable

from mypy.util import json_dumps, json_loads

try:
    import orjson

    HAS_ORJSON = True
except ImportError:
    HAS_ORJSON = False


def benchmark_json_operation(
    operation: Callable[[], Any], iterations: int = 1000, warmup: int = 100
) -> float:
    """Benchmark a JSON operation.

    Args:
        operation: The operation to benchmark (should be a callable with no args).
        iterations: Number of iterations to run for timing.
        warmup: Number of warmup iterations before timing.

    Returns:
        Average time per operation in milliseconds.
    """
    # Warmup
    for _ in range(warmup):
        operation()

    # Actual benchmark
    start = time.perf_counter()
    for _ in range(iterations):
        operation()
    end = time.perf_counter()

    total_time = end - start
    avg_time_ms = (total_time / iterations) * 1000
    return avg_time_ms


def compare_serialization_performance(test_object: Any, iterations: int = 1000) -> dict[str, Any]:
    """Compare serialization performance between orjson and standard json.

    Args:
        test_object: The object to serialize for benchmarking.
        iterations: Number of iterations for the benchmark.

    Returns:
        Dictionary containing benchmark results and statistics.
    """
    results: dict[str, Any] = {
        "has_orjson": HAS_ORJSON,
        "iterations": iterations,
        "object_type": type(test_object).__name__,
    }

    # Benchmark json_dumps
    dumps_time = benchmark_json_operation(lambda: json_dumps(test_object), iterations)
    results["dumps_avg_ms"] = dumps_time

    # Benchmark json_loads
    serialized = json_dumps(test_object)
    loads_time = benchmark_json_operation(lambda: json_loads(serialized), iterations)
    results["loads_avg_ms"] = loads_time

    # Calculate total roundtrip time
    results["roundtrip_avg_ms"] = dumps_time + loads_time

    # Add size information
    results["serialized_size_bytes"] = len(serialized)

    return results


def print_benchmark_results(results: dict[str, Any]) -> None:
    """Pretty print benchmark results.

    Args:
        results: Results dictionary from compare_serialization_performance.
    """
    print("\n" + "=" * 60)
    print("JSON Serialization Performance Benchmark")
    print("=" * 60)
    print(f"Using orjson: {results['has_orjson']}")
    print(f"Iterations: {results['iterations']}")
    print(f"Object type: {results['object_type']}")
    print(f"Serialized size: {results['serialized_size_bytes']:,} bytes")
    print("-" * 60)
    print(f"json_dumps avg: {results['dumps_avg_ms']:.4f} ms")
    print(f"json_loads avg: {results['loads_avg_ms']:.4f} ms")
    print(f"Roundtrip avg:  {results['roundtrip_avg_ms']:.4f} ms")
    print("=" * 60 + "\n")


def run_standard_benchmarks() -> None:
    """Run a set of standard benchmarks with common data structures."""
    print("\nRunning standard JSON serialization benchmarks...\n")

    # Benchmark 1: Small dictionary
    small_dict = {"key": "value", "number": 42, "list": [1, 2, 3]}
    print("Benchmark 1: Small dictionary")
    results1 = compare_serialization_performance(small_dict, iterations=10000)
    print_benchmark_results(results1)

    # Benchmark 2: Medium dictionary (simulating cache metadata)
    medium_dict = {
        f"module_{i}": {
            "path": f"/path/to/module_{i}.py",
            "mtime": 1234567890.123 + i,
            "size": 1024 * i,
            "dependencies": [f"dep_{j}" for j in range(10)],
            "hash": f"abc123def456_{i}",
        }
        for i in range(100)
    }
    print("Benchmark 2: Medium dictionary (100 modules)")
    results2 = compare_serialization_performance(medium_dict, iterations=1000)
    print_benchmark_results(results2)

    # Benchmark 3: Large dictionary (simulating large cache)
    large_dict = {
        f"key_{i}": {"nested": {"value": i, "data": f"string_{i}" * 10}} for i in range(1000)
    }
    print("Benchmark 3: Large dictionary (1000 entries)")
    results3 = compare_serialization_performance(large_dict, iterations=100)
    print_benchmark_results(results3)

    # Benchmark 4: Deeply nested structure
    nested: dict[str, Any] = {"value": 0}
    current = nested
    for i in range(50):
        current["nested"] = {"value": i + 1, "data": f"level_{i}"}
        current = current["nested"]
    print("Benchmark 4: Deeply nested structure (50 levels)")
    results4 = compare_serialization_performance(nested, iterations=1000)
    print_benchmark_results(results4)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    if HAS_ORJSON:
        print("[OK] orjson is installed and being used for optimization")
        print("     Install command: pip install mypy[faster-cache]")
    else:
        print("[INFO] orjson is NOT installed, using standard json")
        print("       For better performance, install with: pip install mypy[faster-cache]")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    run_standard_benchmarks()
