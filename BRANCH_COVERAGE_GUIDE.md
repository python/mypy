## Add Branch Coverage

### Step 1: Register in `mypy/branch_coverage.py`

```python
BRANCH_COVERAGE = {
    'check_return_stmt': set(),
    'your_function_name': set(),  # Add your function
}

BRANCH_DESCRIPTIONS = {
    'your_function_name': {
        1: 'Function entry',
        2: 'if condition_x - TRUE',
        3: 'if condition_x - FALSE',
        4: 'elif condition_y - TRUE',
        5: 'else branch',
    }
}
```

### Step 2: Instrument Your Function

```python
def your_function_name(self, param):
    from mypy.branch_coverage import record_branch
    record_branch('your_function_name', 1)  # Function entry

    if condition_x:
        record_branch('your_function_name', 2)  # TRUE
        # code...
    elif condition_y:
        record_branch('your_function_name', 3)  # FALSE from if
        record_branch('your_function_name', 4)  # TRUE for elif
        # code...
    else:
        record_branch('your_function_name', 3)  # FALSE from if
        record_branch('your_function_name', 5)  # else
        # code...
```

**Important:** Import `record_branch` inside the function to avoid circular imports.

## Run Tests

**CRITICAL**: Must use `-n0` to disable parallel execution, or coverage data will not be collected!

```bash
# Activate virtual environment first
source venv/bin/activate

# Run all tests
pytest mypy/test/testcheck.py -n0

# Run specific test file
pytest mypy/test/testcheck.py::TypeCheckSuite::::check-basic.test::testInvalidReturn -n0
```

## View Reports

Reports are automatically saved in the project root directory:`branch_coverage_report.txt`
