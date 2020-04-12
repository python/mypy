Performance tips and tricks
===========================

Improving efficient is both an art and a science. Just using mypyc in
a naive manner will likely give you some benefits, but getting the
most out of mypyc requires the use of some performance engineering
techniques we'll summarize below.

Profiling
---------

If you speeding up existing code, understanding where time is spent is
important. Mypyc speeds up code that you compile. If most of the time
is spent elsewhere, you may come back disappointed. If you spend 20%
of time outside compiled code, even if the performance improvement
would be infinite, overall performance will up to 5x faster.

A simple (but often effective) approach is to record the time in
various points of program execution using ``time.time()``.

The stdlib modules ``profile`` or ``cProfile`` can provide much more
detailed data. (But these only properly work with non-compiled code.)

Avoiding slow libraries
-----------------------

If profiling indicates that a lot of time is spent in the stdlib or
third-party libraries, you still have several options.

First, if most time is spent in a few library features, you can
perhaps easily reimplement them in type-annotated Python, or extract
the relevant code and annotate it. Now it may be easy to compile the
code for speedups.

Second, you may be able to avoid the library altogether, or use an
alternative, more efficient library to achieve the same purpose.

Type annotations
----------------

As discussed earlier, type annotations are key to major performance
gains. This includes adding annotations to any performance-critical
code.  It may also be helpful annotate code called by this code, even
if it's not compiled, since this may help mypy infer better types in
the compile code. If you use some libraries, ensure they have stub
files with good type coverage. Writing a stub files is often easy, and
you only need to annotate features you use a lot.

If annotating external code or writing stubs feel like too much work,
a simple workaround is to annotate the return values explicitly. For
example, assume we that call the ``acme.get_stuff()`` function a lot,
but there is no type annotation for it. We can use an explicit type
annotation::

    from typing import List, Tuple
    import acme

    def work() -> None:
        items: List[Tuple[int, str]] = acme.get_stuff()
        for item in items:
            ...  # Process item

Without the annotation on ``items``, the type would be ``Any`` (since
``acme`` has no type annotations), resulting in slow, generic
operations being used.

Avoiding slow Python features
-----------------------------

Mypyc can optimize some features more effectively than others. Here
the difference is sometimes big -- some times only get marginally faster,
while other can get 10x faster, or more. Avoiding these slow features in
performance-critical parts of your code can help a lot.

Here's a summary of things that tend to be relatively slow:

* Calling decorated functions

* Calling nested functions

* Using Python classes and instances of Python classes

* Using interpreted libraries written in Python

* Using erased types, including callable values (i.e. not leveraging
  early binding to call functions or methods)

* Using class decorators or metaclasses (that aren't properly
  supported by mypyc)

Using fast native features
--------------------------

Some native operations are particularly quick relative to the
corresponding interpreted operations. Using them as much as possible
may allow you to see 10x or more in performance gains.

The key thing to understand is that some things that are pretty fast
in interpreted code, such as getting a dictionary item, are
not much faster in compiled code. Some things that are pretty slow
in interpreted code, such creating a class instance, are much faster
in compiled code.
