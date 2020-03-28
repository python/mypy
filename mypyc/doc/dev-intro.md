# Introduction for Mypyc Contributors

This is a short introduction aimed at anybody who is interested in
contributing to mypyc, or anybody who is curious to understand how
mypyc works internally.

## Key Differences from Python

Code compiled using mypyc is often much faster than CPython since it
does these things differently:

* Mypyc generates C that is compiled to native code, instead of
  compiling to interpreted byte code, which CPython uses. Interpreted
  byte code always has some interpreter overhead, which slows things
  down.

* Mypyc compiles classes to C extension classes, which are generally
  more efficient than normal Python classes. They use an efficient,
  fixed memory representation (essentially a C struct).

* Mypyc doesn't let you arbitrarily monkey patch classes and functions
  in compiled modules.  This allows *early binding* -- mypyc
  statically binds calls to compiled functions, instead of going
  through a namespace dictionary.  Mypyc can also call methods of
  compiled classes using vtables, which are more efficient than
  dictionary lookups used by CPython.

* As a result of early binding, compiled code can use C calls to call
  compiled functions. Keyword arguments can be translated to
  positional arguments during compilation. Thus most calls to native
  functions and methods directly map to simple C calls. CPython calls
  are quite expensive, since mapping of keyword arguments, `*args`,
  and so on has to mostly happen at runtime.

* Compiled code has runtime type checks to ensure that runtimes types
  match the declared static types. Compiled code can thus make
  assumptions about the types of expressions, resulting in both faster
  and smaller code, since many runtime type checks performed by the
  CPython interpreter can be omitted.

* Compiled code can often use unboxed (not heap allocated)
  representations for integers, booleans and tuples.

## Supported Python Features

Mypyc supports a large subset of Python. Note that if you try to
compile something that is not supported, you may not always get a very
good error message.

Here are some major things that aren't yet supported in compiled code:

* Many dunder methods (only some work, such as `__init__` and `__eq__`)
* Monkey patching compiled functions or classes
* General multiple inheritance (a limited form is supported)
* Named tuple defined using the class-based syntax
* Defining protocols

We are generally happy to accept contributions that implement new Python
features.

## Development Environment

First you should set up the mypy development environment as described in
the [mypy docs](https://github.com/python/mypy/blob/master/README.md).
macOS, Linux and Windows are supported.

## High-level Overview of Mypyc

Mypyc compiles a Python module (or a set of modules) to C, and
compiles the generated C to a Python C extension module (or
modules). You can compile only a subset of your program to C --
compiled and interpreted code can freely and transparently
interact. You can also freely use any Python libraries (including C
extensions) in compiled code.

Mypyc will only make compiled code faster. To see a significant
speedup, you must make sure that most of the time is spent in compiled
code -- and not in libraries, for example.

Mypyc has these passes:

* Type check the code using mypy and infer types for variables and
  expressions.  This produces a mypy AST (defined in `mypy.nodes`) and
  a type map that describes the inferred types (`mypy.types.Type`) of
  all expressions (as PEP 484 types).

* Translate the mypy AST into a mypyc-specific intermediate representation (IR).
  * The IR is defined in `mypyc.ir` (see below for an explanation of the IR).
  * Various primitive operations used in the IR are defined in `mypyc.primitives`.
  * The translation to IR happens in `mypyc.irbuild`. This has two passes.
    The top-level logic is in `mypyc.irbuild.main`.

* Insert checks for uses of potentially uninitialized variables
  (`mypyc.transform.uninit`).

* Insert exception handling (`mypyc.transform.exceptions`).

* Insert explicit reference count inc/dec opcodes (`mypyc.transform.refcount`).

* Translate the IR into C (`mypyc.codegen`).

* Compile the generated C code using a C compiler (`mypyc.build`).

## Useful Background Information

Beyond the mypy documentation, here are some things that are helpful to
know for mypyc contributors:

* Experience with C
  ([The C Programming Language](https://en.wikipedia.org/wiki/The_C_Programming_Language)
  is a classic book about C)
* Basic familiarity with the Python C API (see
  [Python C API documentation](https://docs.python.org/3/c-api/intro.html))
* Basics of compilers (see the
  [mypy wiki](https://github.com/python/mypy/wiki/Learning-Resources)
  for some ideas)

## Mypyc Intermediate Representation (IR)

The mypyc IR is defined in `mypyc.ir`. It covers several key concepts
that are essential to understand by all mypyc contributors:

* `mypyc.ir.ops.Op` is an Abstract Base Class for all IR
  operations. These are low-level and generally map to simple
  fragments of C each. Mypy expressions are translated to
  linear sequences of these ops.

* `mypyc.ir.ops.BasicBlock` is a container of a sequence of ops with a
  branch/goto/return at the end, and no branch/goto/return ops in the
  middle. Each function is compiled to a bunch of basic blocks.

* `mypyc.ir.rtypes.RType` and its subclasses are the types used for
  everything in the IR. These are lower-level and simpler than mypy or
  PEP 484 types. For example, there are no general-purpose generic
  types types here. Each `List[X]` type (for any `X`) is represented
  by a single `list` type, for example.

* Primitive types are special RTypes of which mypyc has some special
  understanding, and there are typically some specialized
  ops. Examples include `int` (referred to as `int_rprimitive` in the
  code) and `list` (`list_rprimitive`). Python types for which there
  is no specific RType type will be represented by the catch-all
  `object_rprimitive` type.

* Instances of compiled classes are generally represented using the
  `RInstance` type.  Classes are compiled to C extension classes and
  contain vtables for fast method calls and fast attribute access.

* IR representations of functions and classes live in
  `mypyc.ir.func_ir` and `mypyc.ir.class_ir`, respectively.

Look at the docstrings and comments in `mypyc.ir` for additional
information. See the test cases in
`mypyc/test-data/irbuild-basic.test` for examples of what the IR looks
like in a pretty-printed form.

## Tests

Mypyc test cases are defined in the same format (`.test`) as used for
test cases for mypy. Look at mypy developer documentation for a general
overview of how things work.  Test cases live under `mypyc/test-data/`,
and you can run all mypyc tests via `pytest mypyc`. If you don't make
changes to code under `mypy/`, it's not important to regularly run mypy
tests during development.

When you create a PR, we have Continuous Integration jobs set up that
compile mypy using mypyc and run the mypy test suite using the
compiled mypy. This will sometimes catch additional issues not caught
by the mypyc test suite. It's okay to not do this in your local
development environment.

## Type-checking Mypyc

`./runtests.py self` type checks mypy and mypyc. This is pretty slow,
however, since it's using an uncompiled mypy.

Installing a released version of mypy using `pip` (which is compiled)
and using `dmypy` (mypy daemon) is a much, much faster way to type
check mypyc during development.

## Overview of Generated C

Mypyc uses a tagged pointer representation for integers, `char` for
booleans, and C structs for tuples. For most other objects mypyc uses
the CPython `PyObject *`.

Mypyc compiles a function into two functions, a native function and
a wrapper function:

* The native function takes a fixed number of C arguments with the
  correct C types. It assumes that all argument have correct types.

* The wrapper function conforms to the Python C API calling convention
  and takes an arbitrary set of arguments. It processes the arguments,
  checks their types, unboxes values with special representations and
  calls the native function. The return value from the native function
  is translated back to a Python object ("boxing").

Calls to other compiled functions don't go through the Python module
namespace but directly call the target native C function. This makes
calls very fast compared to CPython.

The generated code does runtime checking so that it can assume that
values always have the declared types. Whenever accessing CPython
values which might have unexpected types we need to insert a runtime
type check operation. For example, when getting a list item we need to
insert a runtime type check (an unbox or a cast operation), since
Python lists can contain arbitrary objects.

The generated code uses various helpers defined in
`mypyc/lib-rt/CPy.h`.  The header must only contain static functions,
since it is included in many files. `mypyc/lib-rt/CPy.c` contains
definitions that must only occur once, but really most of `CPy.h`
should be moved into it.

## Other Important Limitations

All of these limitations will likely be fixed in the future:

* We don't detect stack overflows.

* We don't handle Ctrl-C in compiled code.

## Hints for Implementing Typical Mypyc Features

This section gives an overview of where to look for and
what to do to implement specific kinds of mypyc features.

### New Python Syntax

Support for syntactic sugar that doesn't need additional IR operations
typically only requires changes to `mypyc.irbuild`.

Some new syntax also needs new IR primitives to be added to
`mypyc.primitives`. See `mypyc.primitives.registry` for documentation
about how to do this.

### Testing

Our bread-and-butter testing strategy is compiling code with mypyc and
running it. There are downsides to this (kind of slow, tests a huge
number of components at once, insensitive to the particular details of
the IR), but there really is no substitute for running code.

Test cases that compile and run code are located in
`test-data/run*.test` and the test driver is in `mypyc.test.test_run`.

If the specifics of the generated IR of a change is important
(because, for example, you want to make sure a particular optimization
is triggering), you should add a `mypyc.irbuild` test as well.  Test
cases are located in `mypyc/test-data/irbuild-*.test` and the test
driver is in `mypyc.test.test_irbuild`. IR build tests do a direct
comparison of the IR output, so try to make the test as targeted as
possible so as to capture only the important details.  (Many of our
existing IR build tests do not follow this advice, unfortunately!)

If you pass the `--update-data` flag to pytest, it will automatically
update the expected output of any tests to match the actual
output. This is very useful for changing or creating IR build tests,
but make sure to carefully inspect the diff!

You may also need to add some definitions to the stubs used for
builtins during tests (`mypyc/test-data/fixtures/ir.py`). We don't use
full typeshed stubs to run tests since they would seriously slow down
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

### Adding a Specialized Primitive Operation

Mypyc speeds up operations on primitive types such as `list` and `int`
by having primitive operations specialized for specific types. These
operations are defined in `mypyc.primitives` (and
`mypyc/lib-rt/CPy.h`).  For example, `mypyc.primitives.list_ops`
contains primitives that target list objects.

The operation definitions are data driven: you specify the kind of
operation (such as a call to `builtins.len` or a binary addition) and
the operand types (such as `list_primitive`), and what code should be
generated for the operation. Mypyc does AST matching to find the most
suitable primitive operation automatically.

Look at the existing primitive definitions and the docstrings in
`mypyc.primitives.registry` for examples and more information.

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

* Update `emit_box` in `mypyc.codegen.emit`.

* Update `emit_unbox` or `emit_cast` in `mypyc.codegen.emit`.

* Update `emit_inc_ref` and `emit_dec_ref` in `mypypc.codegen.emit` if
  needed. If the unboxed representation does not need reference
  counting, these can be no-ops. If the representation is not unboxed
  these will already work.

* Update `emit_error_check` in `mypyc.codegen.emit` for unboxed types.

* Update `emit_gc_visit` and `emit_gc_clear` in `mypyc.codegen.emit`
  if the type has an unboxed representation with pointers.

The above may be enough to allow you to declare variables with the
type, pass values around, perform runtime type checks, and use generic
fallback primitive operations to perform method calls, binary
operations, and so on. You likely also want to add some faster,
specialized primitive operations for the type (see Adding a
Specialized Primitive Operation above for how to do this).

Add a test case to `mypyc/test-data/run.test` to test compilation and
running compiled code. Ideas for things to test:

* Test using the type as an argument.

* Test using the type as a return value.

* Test passing a value of the type to a function both within
  compiled code and from regular Python code. Also test this
  for return values.

* Test using the type as list item type. Test both getting a list item
  and setting a list item.

### Other Hints

* This developer documentation is not aimed to be very complete. Much
  of our documentation is in comments and docstring in the code. If
  something is unclear, study the code.

* It can be useful to look through some recent PRs to get an idea of
  what typical code changes, test cases, etc. look like.

* Feel free to open GitHub issues with questions if you need help when
  contributing, or ask questions in existing issues. Note that we only
  support contributors. Mypyc is not (yet) an end-user product.

## Undocumented Workflows

These workflows would be useful for mypyc contributors. We should add
them to mypyc developer documentation:

* How to manually compile and run a module.

* How to inspect the generated C code.

* How to inspect the generated IR (before/after various transform passes).

* How to measure the performance of code reliably.
