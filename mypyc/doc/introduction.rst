Introduction
============

Mypyc is a compiler for a strict, statically typed Python variant that
creates CPython C extension modules. The goal of mypyc is to speed up
Python modules -- code compiled with mypyc is often much faster than
CPython. Mypyc uses Python type hints to generate fast code, but it
also restricts the use of some dynamic Python features to gain
performance.

Mypyc uses `mypy <http://www.mypy-lang.org/>`_ to perform type
checking and type inference. Most type checking features in the stdlib
`typing <https://docs.python.org/3/library/typing.html>`_ module are
supported, including generic types, optional and union types, tuple
types, and type variables. Using type hints is not necessary, but type
annotations are often the key to getting impressive performance gains.

Compiled modules can import arbitrary Python modules, including
third-party libraries, and compiled modules can be freely used from
other Python modules.  Typically you use mypyc to only compile modules
that contain performance bottlenecks.

You can run compiled modules also as normal, interpreted Python
modules, since mypyc only compiles valid Python code. This means that
all Python developer tools and debuggers can be used (though some only
fully work in interpreted mode).

How fast is mypyc
-----------------

The speed improvement from compilation depends on many factors.
Certain operations will be a lot faster, while other things will
remain the same.

These estimates give a rough idea of what to expect (2x improvement
halves the runtime):

* Existing code with type annotations may get **1.5x to 5x** better
  performance.

* Existing code with *no* type annotations can expect **1.0x to 1.3x**
  better performance.

* Code optimized for mypyc may see **5x to 10x** performance
  improvement.

Only performance of compiled modules improves. Time spent in libraries
or on I/O will not change (unless you also compile libraries).

Why does speed matter
---------------------

Here are reasons why speed can be important:

* It can lower hardware costs. If a server application is 2x faster,
  it may only need half as much hardware to run.

* It can improve user experience. If a request can be served in half
  the time, it can help you attract more users.

* It can make your library or tool more popular. If there are two
  options, and one of them is 2x faster, many users will pick the
  faster one.

* More efficient code uses less energy to run.

* Compiled code may make your tests run faster, or allow batch jobs to
  complete quicker, reducing wasted time. (This needs to offset
  compilation time.)

* Python is popular. Even a small efficiency gain across the Python
  community can have a big impact (say, in a popular library).

How does mypyc work
-------------------

Mypyc can produce fast code through several features:

* Mypyc uses *ahead-of-time compilation* to native code. This removes
  CPython interpreter overhead.

* Mypyc enforces type annotations (and type comments) at runtime,
  raising ``TypeError`` if runtime types don't match annotations. This
  lets mypyc use operations specialized to specific types.

* Mypyc uses *early binding* to resolve called functions and other
  references at compile time. Mypyc avoids many namespace dictionary
  lookups.

* Mypyc assumes that most compiled functions, compiled classes, and
  attributes declared ``Final`` are immutable (and tries to enforce
  this).

* Classes are usually compiled to *C extension classes*. They use
  `vtables <https://en.wikipedia.org/wiki/Virtual_method_table>`_ for
  efficient method calls and attribute accesses.

* Mypyc uses efficient (unboxed) representations for some primitive
  types, such as integers and booleans.

Why mypyc
---------

**High performance and high productivity.** Since code compiled with
mypyc can be run with CPython without compilation, and mypyc supports
most Python features, mypyc improves performance of Python with minor
changes to workflows, and with minimal productivity impact.

**Migration path for existing Python code.** Existing Python code
often requires only minor changes to compile using mypyc, especially
if it's already using type annotations and mypy for type checking.

**Powerful Python types.** Mypyc leverages most features of standard
Python type hint syntax, unlike tools such as Cython, which focus on
lower-level types. Our aim is that writing code feels natural and
Pythonic. Mypyc supports a modern type system with powerful features
such as local type inference, generics, optional types, tuple types
and union types. Type hints act as machine-checked documentation,
making code easier to understand and modify.

**Static and runtime type safety.** Mypyc aims to protect you from
segfaults and memory corruption. We consider any unexpected runtime
type safety violation as a bug. Mypyc uses mypy for powerful type
checking that will catch many bugs, saving you from a lot of
debugging.

**Fast program startup.** Python implementations using a JIT compiler,
such as PyPy, slow down program startup, sometimes significantly.
Mypyc uses ahead-of-time compilation, so compilation does not
happen during program startup.

**Ecosystem compatibility.** Since mypyc uses unmodified CPython as
the runtime, the stdlib and all existing third-party libraries,
including C extensions, continue to work.

**Easy path to "real" static typing.** Mypyc is an easy way to get
started with a statically typed language, with only a small set of
concepts to learn beyond Python skills. Unlike with a completely new
language, such as Go, Rust, or C++, you can become productive with
mypyc in a matter of hours, since the libraries, the tools and the
Python ecosystem are still there for you.

Use cases for mypyc
-------------------

Here are examples of use cases where mypyc can be effective:

* Your project has a particular module that is critical for
  performance. Add type annotations and compile it for quick
  performance gains.

* You've been using mypy to type check your code. Using mypyc is now
  easy since your code is already annotated.

* You want your entire program to be as fast as possible.  You compile
  all modules (except tests) for each release.  You continue to use
  interpreted mode during development, for a faster edit-run cycle.
  (This is how mypy achieved a 4x end-to-end performance improvement
  through mypyc.)

* You are writing a new module that must be fast. You write the module
  in Python, and focus on primitives that mypyc can optimize well. The
  module is much faster when compiled, and you've saved a lot of
  effort compared to writing an extension in C (and you don't need to
  know C).

* You've written a C extension, but you are unhappy with it, and would
  prefer to maintain Python code. In some cases you can switch to
  Python and use mypyc to get performance comparable to the
  original C.

Development status
------------------

Mypyc is currently *alpha software*. It's only recommended for
production use cases if you are willing to contribute fixes or to work
around issues you will encounter.
