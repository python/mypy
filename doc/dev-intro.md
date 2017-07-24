# Introduction for Mypyc Contributors

## Supported Features

Only a small subset of Python is supported. If you try to compile
something that is not supported, you are not likely to get a good
error message.

Here's a summary of what should work:

* Top-level functions with required positional-only arguments.
* Calls to top-level functions defined in the same file.
* Types:
  * `int`
  * `List[...]`.
  * `None` as return type
* Some integer operations:
  * Basic integer arithmetic: + - * // %
  * Integer comparisons.
* Some list operations:
  * `[e, ...]` (construct list)
  * `l[n]`
  * `l[n] = x`
  * `l.append(x)`
  * `len(l)`
  * `l * n` (multiply list by integer)
* Simple assignment statement `var = x` (only local variables).
* If/else statement.
* While statement.
* Expression statement.
* Return statement.
* `for x in range(n): ...` (for convenience only).

## High-level Overview

Mypyc compiles a Python module to C, and compiles that to a Python C
extension module.

It has these passes:

* Type check the code using mypy and infer types for variables and expressions.
* Translate the mypy AST into a mypyc-specific intermediate representation (IR).
  * The IR is defined in `mypyc.ops`.
  * The translation happens in `mypyc.genops`.
* Insert explicit reference count inc/dec opcodes (`mypyc.refcount`).
* Translate the IR into C (`mypyc.emitter` and `mypyc.compiler`).
* Compile the generated C code using a C compiler.

## Tests

The test cases are defined in the same format (`.test`) as used in the
mypy project. Look at mypy developer documentation for a general
overview of how things work.  Test cases live under `test-data/`.

## Technical Details

Mypyc uses a tagged pointer representation for integers. For other
objects mypyc uses the CPython `PyObject *`.

Mypyc compiles a function into two functions:

* The native function takes a fixed number of C arguments with the
  correct C types. It assumes that all argument have correct types.
* The wrapper function conforms to the Python C API calling convention
  and takes an arbitrary set of arguments. It processes the arguments,
  checks their types, unboxes values with special representations and
  calls the native function. The return value from the native function
  is translated back to a Python object ("boxing").

Calls to other compiled functions don't go through the Python module
namespace but directly call the target native function. This makes
calls very fast compared to CPython.

The generated code does runtime checking so that it can assume that
values always have the declared types. Whenever accessing CPython
values which might have unexpected types we need to insert a type
check. For example, when getting a list item we need to insert a
runtime type check, since Python lists can contain arbitrary objects.

## Other Important Limitations

* There's currently no way to run the compiler other than through
  tests.

* If something goes wrong, we detect the error but instead of
  raising an exception the compiled program just calls `abort()`.
  (Obviously this will have to change.)
