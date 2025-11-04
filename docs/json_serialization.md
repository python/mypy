# JSON Serialization Performance in Mypy

## Overview

Mypy uses JSON serialization extensively for caching type checking results, which is critical for incremental type checking performance. This document explains how mypy's JSON serialization works and how to optimize it.

## Basic Usage

Mypy provides two main functions for JSON serialization in `mypy.util`:

```python
from mypy.util import json_dumps, json_loads

# Serialize an object to JSON bytes
data = {"module": "mypy.main", "mtime": 1234567890.123}
serialized = json_dumps(data)

# Deserialize JSON bytes back to a Python object
deserialized = json_loads(serialized)
```

## Performance Optimization with orjson

By default, mypy uses Python's standard `json` module for serialization. However, you can significantly improve performance by installing `orjson`, a fast JSON library written in Rust.

### Installation

```bash
# Install mypy with the faster-cache optional dependency
pip install mypy[faster-cache]

# Or install orjson separately
pip install orjson
```

### Performance Benefits

When orjson is available, mypy automatically uses it for JSON operations. Based on benchmarks:

- **Small objects** (< 1KB): 2-3x faster serialization and deserialization
- **Medium objects** (10-100KB): 3-5x faster
- **Large objects** (> 100KB): 5-10x faster

For large projects with extensive caching, this can result in noticeable improvements in incremental type checking speed.

## Key Guarantees

### Deterministic Output

Both `json_dumps` and `json_loads` guarantee deterministic output:

1. **Sorted Keys**: Dictionary keys are always sorted alphabetically
2. **Consistent Encoding**: The same object always produces the same bytes
3. **Roundtrip Consistency**: `json_loads(json_dumps(obj)) == obj`

This is critical for:
- Cache invalidation (detecting when cached data has changed)
- Test reproducibility
- Comparing serialized output across different runs

### Error Handling

The functions include robust error handling:

1. **Large Integers**: Automatically falls back to standard json for integers exceeding 64-bit range
2. **orjson Errors**: Gracefully falls back to standard json if orjson encounters issues
3. **Invalid JSON**: Raises appropriate exceptions with clear error messages

## Debug Mode

For debugging purposes, you can enable pretty-printed output:

```python
# Compact output (default)
compact = json_dumps(data)
# Output: b'{"key":"value","number":42}'

# Pretty-printed output
pretty = json_dumps(data, debug=True)
# Output: b'{\n  "key": "value",\n  "number": 42\n}'
```

## Benchmarking

Mypy includes a benchmarking utility to measure JSON serialization performance:

```bash
# Run standard benchmarks
python -m mypy.json_bench
```

This will show:
- Whether orjson is installed and being used
- Performance metrics for various data sizes
- Comparison of serialization vs deserialization speed
- Serialized data sizes

Example output:
```
============================================================
JSON Serialization Performance Benchmark
============================================================
Using orjson: True
Iterations: 1000
Object type: dict
Serialized size: 20,260 bytes
------------------------------------------------------------
json_dumps avg: 0.0823 ms
json_loads avg: 0.0456 ms
Roundtrip avg:  0.1279 ms
============================================================
```

## Implementation Details

### Why Sorted Keys Matter

Mypy requires sorted keys for several reasons:

1. **Cache Consistency**: The cache system uses serialized JSON as part of cache keys. Unsorted keys would cause cache misses even when data hasn't changed.

2. **Test Stability**: Many tests (e.g., `testIncrementalInternalScramble`) rely on deterministic output to verify correct behavior.

3. **Diff-Friendly**: When debugging cache issues, having sorted keys makes it easier to compare JSON output.

### Fallback Behavior

The implementation includes multiple fallback layers:

```
Try orjson (if available)
  ├─> Success: Return result
  ├─> 64-bit integer overflow: Fall back to standard json
  ├─> Other TypeError: Re-raise (non-serializable object)
  └─> Other errors: Fall back to standard json

Use standard json module
  ├─> Success: Return result
  └─> Error: Propagate exception to caller
```

## Testing

Comprehensive tests are available in `mypy/test/test_json_serialization.py`:

```bash
# Run JSON serialization tests
python -m unittest mypy.test.test_json_serialization -v
```

Tests cover:
- Basic serialization and deserialization
- Edge cases (large integers, Unicode, nested structures)
- Error handling
- Deterministic output
- Performance with large objects

## Best Practices

1. **Install orjson for production**: For better performance in CI/CD and development
2. **Use debug mode sparingly**: Only enable when actively debugging
3. **Monitor cache sizes**: Large serialized objects can impact disk I/O
4. **Test with both backends**: Ensure your code works with and without orjson

## Troubleshooting

### "Integer exceeds 64-bit range" warnings

If you see this in logs, it means orjson encountered a very large integer and fell back to standard json. This is expected behavior and doesn't indicate a problem.

### Performance not improving after installing orjson

1. Verify orjson is installed: `python -c "import orjson; print(orjson.__version__)"`
2. Run benchmarks: `python -m mypy.json_bench`
3. Check that mypy is using the correct Python environment

### JSON decode errors

If you encounter JSON decode errors:
1. Check that the input is valid UTF-8 encoded bytes
2. Verify the JSON structure is valid
3. Try with `debug=True` to see the formatted output

## Contributing

When modifying JSON serialization code:

1. Run the test suite: `python -m unittest mypy.test.test_json_serialization`
2. Run benchmarks to verify performance: `python -m mypy.json_bench`
3. Test with and without orjson installed
4. Update this documentation if behavior changes
