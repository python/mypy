Introduction
============

Mypyc is a compiler for a strict, statically typed Python language
variant that produces CPython C extension modules. The goal of
mypyc is to speed up Python programs -- code compiled with mypyc is
often much faster than CPython. Mypyc uses Python type hints to
generate fast code, but it also restricts the use of some dynamic
Python features for more performance.

Mypyc uses mypy to perform type checking and type inference. Most type
checking features in the stdlib ``typing`` module are supported,
including generic types, tuple types, and type variables. Using type
hints is not necessary, but type annotations are often the key to
getting impressive performance gains.

Compiled modules can import arbitrary Python modules, including
third-party libraries, and compiled modules can be freely used from
other Python modules.  Typically you use mypyc to only compile modules
that contain performance bottlenecks.

You can run compiled modules also as normal, interpreted Python
modules, since mypyc compiles only valid Python code. This means that
all Python developer tools and debuggers can be used (though some only
fully work in interpreted mode).

How does mypyc work
-------------------

Mypyc can produce fast code through several key features:

* Mypyc uses *ahead-of-time compilation* to native code, which removes
  CPython interpreter overhead, which slows down performance.

* Mypyc enforces type annotations at runtime, raising ``TypeError`` if
  runtime types are incompatible with annotations. This allows mypyc
  to generate faster operations specialized to specific types.

* Mypyc uses *early binding* to resolve called functions and other
  references at compile time. Mypyc can omit many namespace dictionary
  lookups.

* Mypyc assumes that most compiled functions, compiled classes, and
  attributes declared ``Final`` are immutable (and tries to enforce
  this).

* Classes are usually compiled to *C extension classes*, which use a
  more efficient runtime representation than ordinary Python classes.
  Mypyc also uses vtables to perform efficient method calls and
  attribute access.

* Mypyc uses efficient (unboxed) representations for some primitive
  types, such as integers and booleans.

Why mypyc
---------

**High performance and high productivity.** Since code compiled with
mypyc can be run with CPython without compilation, and mypyc supports
most Python features, mypyc lets you improve performance of Python
with minimal changes to your workflows, and with minimal productivity
impact. In contrast, working with extensions written in C will
significantly limit your productivity.

**Migration path for existing Python code.** Existing Python code
often requires only minor changes to compile using mypyc, especially
if it's already using type annotations and mypy for type checking.

**Powerful Python types.** Mypyc leverages the standard Python types,
unlike other tools, such as Cython, which depend on lower-level C
types that provide a worse match to many Python idioms. Our aim is
that writing code feels natural and Pythonic. Mypyc supports a modern
type system with powerful features such as local type inference,
generics, optional types, tuple types and union types.

**Easy path to bona fide static typing.** Mypyc is an easy way to
start benefiting from statically typed language features, with only a
small set of concepts to learn beyond basic Python skills. Unlike with
a completely new language, such as Go, Rust, or C++, you can become
productive with mypyc in a matter of days (or even hours), since the
libraries, the tools and the ecosystem we all know and love are still
there for you.

**Runtime type safety.** Mypyc aims to protect you from segfaults and
memory corruption. We consider any runtime type safety violation as a bug.

**Fast program startup.** Python implementations using a JIT compiler,
such as PyPY, slow down program startup, sometimes significantly.
Mypyc uses ahead-of-time compilation, so program startup won't be
slowed.

Use cases for mypyc
-------------------

There are some use cases where mypyc could be a useful tool:

* You have some Python module or modules that you want to make
  faster. Add type annotations to these modules and compile them for
  performance gains.

* You are using mypy to type check your code and want to further
  take advantage of type annotations by compiling modules using mypyc.

* You want your entire program to be as efficient as possible, and
  you compile all modules (except tests) before releasing your code.
  You can still use intepreted mode during development, for a faster
  edit-run cycle.  (This is how mypy achieved a 4x end-to-end
  performance improvement by using mypyc!)

* You maintain a C extension, and you want to improve productivity and
  make maintenance easier by rewriting your module in Python. You may
  be able to use mypyc to get performance comparable to your original
  C extension.

* You are writing a new module that requires high performance. You
  write the module in Python, but only use primitives that mypyc can
  compile efficiently, getting close to maximum performance while
  still providing a much better developer experience compared to
  writing a C extension.

Development status
------------------

Mypyc is currently *alpha software*. It's only recommended for
production use cases if you are willing to contribute fixes or to work
around issues you will encounter.
