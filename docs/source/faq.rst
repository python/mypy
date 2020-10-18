Frequently Asked Questions
==========================

Why have both dynamic and static typing?
****************************************

Dynamic typing can be flexible, powerful, convenient and easy. But
it's not always the best approach; there are good reasons why many
developers choose to use statically typed languages or static typing
for Python.

Here are some potential benefits of mypy-style static typing:

- Static typing can make programs easier to understand and
  maintain. Type declarations can serve as machine-checked
  documentation. This is important as code is typically read much more
  often than modified, and this is especially important for large and
  complex programs.

- Static typing can help you find bugs earlier and with less testing
  and debugging. Especially in large and complex projects this can be
  a major time-saver.

- Static typing can help you find difficult-to-find bugs before your
  code goes into production. This can improve reliability and reduce
  the number of security issues.

- Static typing makes it practical to build very useful development
  tools that can improve programming productivity or software quality,
  including IDEs with precise and reliable code completion, static
  analysis tools, etc.

- You can get the benefits of both dynamic and static typing in a
  single language. Dynamic typing can be perfect for a small project
  or for writing the UI of your program, for example. As your program
  grows, you can adapt tricky application logic to static typing to
  help maintenance.

See also the `front page <http://www.mypy-lang.org>`_ of the mypy web
site.

Would my project benefit from static typing?
********************************************

For many projects dynamic typing is perfectly fine (we think that
Python is a great language). But sometimes your projects demand bigger
guns, and that's when mypy may come in handy.

If some of these ring true for your projects, mypy (and static typing)
may be useful:

- Your project is large or complex.

- Your codebase must be maintained for a long time.

- Multiple developers are working on the same code.

- Running tests takes a lot of time or work (type checking helps
  you find errors quickly early in development, reducing the number of
  testing iterations).

- Some project members (devs or management) don't like dynamic typing,
  but others prefer dynamic typing and Python syntax. Mypy could be a
  solution that everybody finds easy to accept.

- You want to future-proof your project even if currently none of the
  above really apply. The earlier you start, the easier it will be to
  adopt static typing.

Can I use mypy to type check my existing Python code?
*****************************************************

Mypy supports most Python features and idioms, and many large Python
projects are using mypy successfully. Code that uses complex
introspection or metaprogramming may be impractical to type check, but
it should still be possible to use static typing in other parts of a
codebase that are less dynamic.

Will static typing make my programs run faster?
***********************************************

Mypy only does static type checking and it does not improve
performance. It has a minimal performance impact. In the future, there
could be other tools that can compile statically typed mypy code to C
modules or to efficient JVM bytecode, for example, but this is outside
the scope of the mypy project.

How do I type check my Python 2 code?
*************************************

You can use a :pep:`comment-based function annotation syntax
<484#suggested-syntax-for-python-2-7-and-straddling-code>`
and use the :option:`--py2 <mypy --py2>` command-line option to type check your Python 2 code.
You'll also need to install ``typing`` for Python 2 via ``pip install typing``.

Is mypy free?
*************

Yes. Mypy is free software, and it can also be used for commercial and
proprietary projects. Mypy is available under the MIT license.

Can I use duck typing with mypy?
********************************

Mypy provides support for both `nominal subtyping
<https://en.wikipedia.org/wiki/Nominative_type_system>`_ and
`structural subtyping
<https://en.wikipedia.org/wiki/Structural_type_system>`_.
Structural subtyping can be thought of as "static duck typing".
Some argue that structural subtyping is better suited for languages with duck
typing such as Python. Mypy however primarily uses nominal subtyping,
leaving structural subtyping mostly opt-in (except for built-in protocols
such as :py:class:`~typing.Iterable` that always support structural subtyping). Here are some
reasons why:

1. It is easy to generate short and informative error messages when
   using a nominal type system. This is especially important when
   using type inference.

2. Python provides built-in support for nominal :py:func:`isinstance` tests and
   they are widely used in programs. Only limited support for structural
   :py:func:`isinstance` is available, and it's less type safe than nominal type tests.

3. Many programmers are already familiar with static, nominal subtyping and it
   has been successfully used in languages such as Java, C++ and
   C#. Fewer languages use structural subtyping.

However, structural subtyping can also be useful. For example, a "public API"
may be more flexible if it is typed with protocols. Also, using protocol types
removes the necessity to explicitly declare implementations of ABCs.
As a rule of thumb, we recommend using nominal classes where possible, and
protocols where necessary. For more details about protocol types and structural
subtyping see :ref:`protocol-types` and :pep:`544`.

I like Python and I have no need for static typing
**************************************************

The aim of mypy is not to convince everybody to write statically typed
Python -- static typing is entirely optional, now and in the
future. The goal is to give more options for Python programmers, to
make Python a more competitive alternative to other statically typed
languages in large projects, to improve programmer productivity, and
to improve software quality.

How are mypy programs different from normal Python?
***************************************************

Since you use a vanilla Python implementation to run mypy programs,
mypy programs are also Python programs. The type checker may give
warnings for some valid Python code, but the code is still always
runnable. Also, some Python features and syntax are still not
supported by mypy, but this is gradually improving.

The obvious difference is the availability of static type
checking. The section :ref:`common_issues` mentions some
modifications to Python code that may be required to make code type
check without errors. Also, your code must make attributes explicit.

Mypy supports modular, efficient type checking, and this seems to
rule out type checking some language features, such as arbitrary
monkey patching of methods.

How is mypy different from Cython?
**********************************

:doc:`Cython <cython:index>` is a variant of Python that supports
compilation to CPython C modules. It can give major speedups to
certain classes of programs compared to CPython, and it provides
static typing (though this is different from mypy). Mypy differs in
the following aspects, among others:

- Cython is much more focused on performance than mypy. Mypy is only
  about static type checking, and increasing performance is not a
  direct goal.

- The mypy syntax is arguably simpler and more "Pythonic" (no cdef/cpdef, etc.) for statically typed code.

- The mypy syntax is compatible with Python. Mypy programs are normal
  Python programs that can be run using any Python
  implementation. Cython has many incompatible extensions to Python
  syntax, and Cython programs generally cannot be run without first
  compiling them to CPython extension modules via C. Cython also has a
  pure Python mode, but it seems to support only a subset of Cython
  functionality, and the syntax is quite verbose.

- Mypy has a different set of type system features. For example, mypy
  has genericity (parametric polymorphism), function types and
  bidirectional type inference, which are not supported by
  Cython. (Cython has fused types that are different but related to
  mypy generics. Mypy also has a similar feature as an extension of
  generics.)

- The mypy type checker knows about the static types of many Python
  stdlib modules and can effectively type check code that uses them.

- Cython supports accessing C functions directly and many features are
  defined in terms of translating them to C or C++. Mypy just uses
  Python semantics, and mypy does not deal with accessing C library
  functionality.

Mypy is a cool project. Can I help?
***********************************

Any help is much appreciated! `Contact
<http://www.mypy-lang.org/contact.html>`_ the developers if you would
like to contribute. Any help related to development, design,
publicity, documentation, testing, web site maintenance, financing,
etc. can be helpful. You can learn a lot by contributing, and anybody
can help, even beginners! However, some knowledge of compilers and/or
type systems is essential if you want to work on mypy internals.
