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
  * Basic integer arithmetic: `+` `-` `*` `//` `%` (but no unary `-`)
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
* `and` and `or` in a boolean context.
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

## Type-checking Mypyc

One of the tests (`test_self_type_check`) type checks mypyc using mypy.

## Overview of Generated C

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

The generated code uses various helpers defined in `lib-rt/CPy.h`.
The header should only contain inline or static functions, since
we don't compile the C helpers into a separate object file.

## Other Important Limitations

All of these limitations will likely be fixed in the future:

* There's currently no way to run the compiler other than through
  tests (`test-data/run.test` has end-to-end tests -- use these
  sparingly since they are expensive to run).

* If something goes wrong, we detect the error but instead of
  raising an exception the compiled program just calls `abort()`.

* We don't detect infinite recursion.

* We don't handle Ctrl-C in compiled code.

* We don't detect undefined local variables.

* There's no way to access most stdlib functionality.

## Hints for Implementing Typical Mypyc Features

This section gives an overview of where to look for and
what to do to implement specific kinds of mypyc features.

### Syntactic Sugar

Syntactic sugar that doesn't need additional IR operations typically
only requires changes to `mypyc.genops`. Test cases are located in
`test-data/genops-*.test` and the test driver is in
`mypyc.test.test_genops`.

You may also need to add some definitions to the stubs used for
builtins during tests (`test-data/fixtures/ir.py`). We don't use full
typeshed stubs to run tests since they would seriously slow down
tests.

### Built-in Operation for an Already Supported Type

If you want to add support for a new primitive operation for
a type that mypyc already supports in some fashion, you generally
have to do at least these steps:

* Add a new operation to `mypyc.ops`. Often you only need to add a
  suboperation to `PrimitiveOp` or `Branch` instead of defining a new
  `Op` subclass. We don't have test cases specifically for operations.

* Generate the new operation in `mypyc.genops`. Also add test cases
  (see Syntactic Sugar for more information).

* Implement C generation for the new operation in
  `mypyc.emitter`. Test cases are located in
  `mypyc.test.test_emitter`. They are normal Python unit tests instead
  of data-driven test cases.

* Test that your new operation works by adding a test case to
  `test-data/run.test` and verifying that it passes. You don't always
  need to commit the new test. If your operation is pretty
  straightforward, you can omit a test in `run.test` and just add a
  note with your PR mentioning that you've verified that your change
  works end-to-end.

If your operation compiles into a lot of C code, you may also want to
add a C helper function for the operation to make the generated code
smaller. Here is how to do this:

* Add the operation to `lib-rt/CPy.h`. Usually defining a static
  function is the right thing to do, but feel free to also define
  inline functions for very simple and performance-critical
  operations. We avoid macros since they are error-prone.

* Add unit test for your C helper in `lib-rt/test_capi.cc`. We use
  [Google Test](https://github.com/google/googletest) for writing
  tests in C++. The framework is included in the repository under the
  directory `googletest/`. The C unit tests are run as part of the
  pytest test suite (`test_c_unit_tests`).

### A New Primitive Type

Some types such as `int` and `list` are special cased in mypyc to
generate operations specific to these types (actually currently this
is the only way to support new types).

Here are some hints about how to add support for a new primitive type
(this may be incomplete):

* Decide whether the primitive type has an "unboxed" representation
  (a representation that is not just `PyObject *`).

* Update `RTType` to support the primitive type. Make sure
  `supports_unbox` and `ctype` work correctly for the new type.

* Add a wrapper function argument type check to
  `mypyc.emitter.generate_arg_check`.

* Add return value boxing to `generate_wrapper_function` for unboxed
  types (TODO: refactor).

* Update `visit_return` in `mypyc.emitter` (TODO: refactor).

* Update `visit_box` and `visit_unbox` in `mypyc.emitter` if the type
  is unboxed.

* Update `visit_inc_ref` and `visit_dec_ref` in `mypypc.emitter` if
  needed. If the unboxed representation does not need reference
  counting, these can be no-ops. If the representation is not unboxed
  these will already work.

* Update `myypc.genops.type_to_rttype()`.

The above may be enough to allow you to declare variables with the
type and pass values around. You likely also want to add support for
some primitive operations for the type (see Built-in Operation for an
Already Supported Type for how to do this).

If you want to just test C generation, you can add a test case with
dummy output to `test-data/compiler-output.test` and manually inspect
the generated code. You probably don't want to add a new test case
there since these test cases are very fragile, however.

Add a test case to `test-data/run.test` to test compilation and
running compiled code. Ideas for things to test:

* Test using the type for an argument.

* Test using the type for a return value.

* Test passing a value of the type to a function both within
  compiled code and from regular Python code. Also test this
  for return values.

* Test using the type as list item type. Test both getting a list item
  and setting a list item.
