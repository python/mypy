Introduction
============

Mypyc is a compiler for a strict, statically typed Python variant that
generates CPython C extension modules. Code compiled with mypyc is
often much faster than CPython. Mypyc uses Python `type hints
<https://mypy.readthedocs.io/en/stable/cheat_sheet_py3.html>`_ to
generate fast code, and it also restricts the use of some dynamic
Python features to gain performance.

Mypyc uses `mypy <http://www.mypy-lang.org/>`_ to perform type
checking and type inference. Most type checking features in the stdlib
`typing <https://docs.python.org/3/library/typing.html>`_ module are
supported, including generic types, optional and union types, tuple
types, and type variables. Using type hints is not necessary, but type
annotations are the key to impressive performance gains.

Compiled modules can import arbitrary Python modules, including
third-party libraries, and compiled modules can be freely used from
other Python modules. Often you'd use mypyc to only compile modules
with performance bottlenecks.

You can run the modules you compile also as normal, interpreted Python
modules. Mypyc only compiles valid Python code. This means that all
Python developer tools and debuggers can be used, though some only
fully work in interpreted mode.

How fast is mypyc
-----------------

The speed improvement from compilation depends on many factors.
Certain operations will be a lot faster, while others will get no
speedup.

These estimates give a rough idea of what to expect (2x improvement
halves the runtime):

* Typical code with type annotations may get **1.5x to 5x** faster.

* Typical code with *no* type annotations may get **1.0x to 1.3x**
  faster.

* Code optimized for mypyc may get **5x to 10x** faster.

Remember that only performance of compiled modules improves. Time
spent in libraries or on I/O will not change (unless you also compile
libraries).

Why speed matters
-----------------

Faster code has many benefits, some obvious and others less so:

* Users prefer efficient and responsive applications, tools and
  libraries.

* If your server application is faster, you need less hardware, which
  saves money.

* Faster code uses less energy, especially on servers that run 24/7.
  This lowers your environmental footprint.

* If tests or batch jobs run faster, you'll be more productive and
  save time.

How does mypyc work
-------------------

Mypyc produces fast code via several techniques:

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

* Most classes are compiled to *C extension classes*. They use
  `vtables <https://en.wikipedia.org/wiki/Virtual_method_table>`_ for
  fast method calls and attribute access.

* Mypyc uses efficient (unboxed) representations for some primitive
  types, such as integers and booleans.

Why mypyc
---------

Here are some mypyc properties and features that can be useful.

**Powerful Python types.** Mypyc leverages most features of standard
Python type hint syntax, unlike tools such as Cython, which focus on
lower-level types. Our aim is that writing code feels natural and
Pythonic. Mypyc supports a modern type system with powerful features
such as local type inference, generics, optional types, tuple types
and union types. Type hints act as machine-checked documentation,
making code easier to understand and modify.

**Fast program startup.** Python implementations using a JIT compiler,
such as PyPy, slow down program startup, sometimes significantly.
Mypyc uses ahead-of-time compilation, so compilation does not slow
down program startup.

**Python ecosystem compatibility.** Since mypyc uses the standard
CPython runtime, you can freely use the stdlib and use pip to install
arbitary third-party libraries, including C extensions.

**Migration path for existing Python code.** Existing Python code
often requires only minor changes to compile using mypyc.

**No need to wait for compilation.** Compiled code also runs as normal
Python code. You can use intepreted Python during development, with
familiar workflows.

**Runtime type safety.** Mypyc aims to protect you from segfaults and
memory corruption. We consider any unexpected runtime type safety
violation as a bug.

**Find errors statically.** Mypyc uses mypy for powerful static type
checking that will catch many bugs, saving you from a lot of
debugging.

**Easy path to static typing.** Mypyc lets Python developers easily
dip their toes into modern static typing, without having to learn all
new syntax, libraries and idioms.

Use cases for mypyc
-------------------

Here are examples of use cases where mypyc can be effective.

**Address a performance bottleneck.** Profiling shows that most time
is spent in a certain Python module. Add type annotations and compile
the module for performance gains.

**Leverage existing type hints.** You already use mypy to type check
your code. Using mypyc will now be easy, since you already use static
typing.

**Compile everything.** You want your whole application to be fast.
During development you use interpreted mode, for a quick edit-run
cycle, but in your releases all (non-test) code is compiled. This is
how mypy achieved a 4x performance improvement using mypyc.

**Alternative to C.** You are writing a new module that must be fast.
You write the module in Python, and try to use operations that mypyc
can optimize well. The module is much faster when compiled, and you've
saved a lot of effort compared to writing an extension in C (and you
don't need to know C).

**Rewriting a C extension.** You've written a C extension, but
maintaining C code is no fun. You might be able to switch to Python
and use mypyc to get performance comparable to the original C.

Development status
------------------

Mypyc is currently *alpha software*. It's only recommended for
production use cases if you are willing to contribute fixes or to work
around issues you will encounter.
