# Introduction for Mypyc Contributors

## Supported Features

Mypyc supports a subset of Python. If you try to compile something
that is not supported, you may not always get a very good error
message.

Here are some major things that aren't supported in compiled code:

* Many dunder methods (only some work, such as `__init__` and `__eq__`)
* Monkey patching compiled functions or classes
* General multiple inheritance (a limited form is supported)
* Named tuple defined using the class-based syntax
* Defining protocols

We are generally happy to accept contributions that implement new Python
features.

## High-level Overview

Mypyc compiles a Python module to C, and compiles that to a Python C
extension module.

It has these passes:

* Type check the code using mypy and infer types for variables and expressions.
* Translate the mypy AST into a mypyc-specific intermediate representation (IR).
  * The IR is defined in `mypyc.ops`.
  * The translation happens in `mypyc.irbuild`.
* Insert checks for uses of potentially uninitialized variables (`mypyc.uninit`).
* Insert exception handling (`mypyc.exceptions`).
* Insert explicit reference count inc/dec opcodes (`mypyc.refcount`).
* Translate the IR into C (`mypyc.emit*`).
* Compile the generated C code using a C compiler.

## Tests

The test cases are defined in the same format (`.test`) as used in the
mypy project. Look at mypy developer documentation for a general
overview of how things work.  Test cases live under `test-data/`.

## Type-checking Mypyc

One of the tests (`test_self_type_check`) type checks mypyc using mypy.

## Overview of Generated C

Mypyc uses a tagged pointer representation for integers, `char` for
booleans, and C structs for tuples. For most other objects mypyc uses
the CPython `PyObject *`.

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
runtime type check (an unbox or a cast operation), since Python lists
can contain arbitrary objects.

The generated code uses various helpers defined in
`mypyc/lib-rt/CPy.h`.  The header must only contain static functions,
since it is included in many files. `mypyc/lib-rt/CPy.c` contains
definitions that must only occur once, but really most of `CPy.h`
should be moved into it.

## Other Important Limitations

All of these limitations will likely be fixed in the future:

* We don't detect stack overflow.

* We don't handle Ctrl-C in compiled code.

## Hints for Implementing Typical Mypyc Features

This section gives an overview of where to look for and
what to do to implement specific kinds of mypyc features.


### Syntactic Sugar

Syntactic sugar that doesn't need additional IR operations typically
only requires changes to `mypyc.irbuild`.


### Testing

For better or worse, our bread-and-butter testing strategy is
compiling code with mypyc and running it. There are downsides to this
(kind of slow, tests a huge number of components at once, insensitive
to the particular details of the IR), but there really is no
substitute for running code.

Run test cases are located in `test-data/run*.test` and the test
driver is in `mypyc.test.test_run`.

If the specifics of the generated IR of a change is important
(because, for example, you want to make sure a particular optimization
is triggering), you should add an irbuild test as well.  Test cases are
located in `test-data/irbuild-*.test` and the test driver is in
`mypyc.test.test_irbuild`. IR build tests do a direct comparison of the
IR output, so try to make the test as targeted as possible so as to
capture only the important details.
(Many of our existing IR build tests do not follow this advice, unfortunately!)

If you pass the `--update-data` flag to pytest, it will automatically
update the expected output of any tests to match the actual
output. This is very useful for changing or creating IR build tests, but
make sure to carefully inspect the diff!

You may also need to add some definitions to the stubs used for
builtins during tests (`test-data/fixtures/ir.py`). We don't use full
typeshed stubs to run tests since they would seriously slow down
tests.

### Adding C Helpers

If you add an operation that compiles into a lot of C code, you may
also want to add a C helper function for the operation to make the
generated code smaller. Here is how to do this:

* Add the operation to `mypyc/lib-rt/CPy.h`. Usually defining a static
  function is the right thing to do, but feel free to also define
  inline functions for very simple and performance-critical
  operations. We avoid macros since they are error-prone.

* Consider adding a unit test for your C helper in `mypyc/lib-rt/test_capi.cc`.
  We use
  [Google Test](https://github.com/google/googletest) for writing
  tests in C++. The framework is included in the repository under the
  directory `googletest/`. The C unit tests are run as part of the
  pytest test suite (`test_c_unit_tests`).

### A New Primitive Type

Some types such as `int` and `list` are special cased in mypyc to
generate operations specific to these types.

Here are some hints about how to add support for a new primitive type
(this may be incomplete):

* Decide whether the primitive type has an "unboxed" representation
  (a representation that is not just `PyObject *`).

* Create a new instance of `RPrimitive` to support the primitive type.
  Make sure all the attributes are set correctly and also define
  `<foo>_rprimitive` and `is_<foo>_rprimitive`.

* Update `mypyc.irbuild.mapper.Mapper.type_to_rtype()`.

* Update `emit_box` in `mypyc.emit`.

* Update `emit_unbox` or `emit_cast` in `mypyc.emit`.

* Update `emit_inc_ref` and `emit_dec_ref` in `mypypc.emit` if
  needed. If the unboxed representation does not need reference
  counting, these can be no-ops. If the representation is not unboxed
  these will already work.

* Update `emit_error_check` in `mypyc.emit` for unboxed types.

* Update `emit_gc_visit` and `emit_gc_clear` in `mypyc.emit` if the
  type has an unboxed representation with pointers.

The above may be enough to allow you to declare variables with the
type and pass values around. You likely also want to add support for
some primitive operations for the type (see Built-in Operation for an
Already Supported Type for how to do this).

If you want to just test C generation, you can add a test case with
dummy output to `test-data/module-output.test` and manually inspect
the generated code. You probably don't want to commit a new test case
there since these test cases are very fragile.

Add a test case to `test-data/run.test` to test compilation and
running compiled code. Ideas for things to test:

* Test using the type for an argument.

* Test using the type for a return value.

* Test passing a value of the type to a function both within
  compiled code and from regular Python code. Also test this
  for return values.

* Test using the type as list item type. Test both getting a list item
  and setting a list item.

### Other Hints

* This developer documentation is not very complete and might be out of
  date.

* It can be useful to look through some recent PRs to get an idea of
  what typical code changes, test cases, etc. look like.

* Feel free to open GitHub issues with questions if you need help when
  contributing, or ask questions in existing issues. Note that we only
  support contributors. Mypyc is not (yet) an end-user product.
