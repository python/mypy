Differences from Python
=======================

Mypyc aims to be sufficiently compatible with Python semantics so that
migrating code to mypyc often doesn't require major changes to typical
code. There are various differences to enable performance gains that
you need to be aware of. This section documents notable deviations.

Running compiled code as module
-------------------------------

You can't use the CPython ``-m <module>`` command-line option to run compiled modules.
Use ``python3 -c "import <module>"`` instead, or write a wrapper script that imports
your module.

As a side effect, you can't rely on checking the ``__name__`` attribute in compiled
code, like this::

    if __name__ == "__main__":  # Can't be used in compiled code!
        main()

Native classes
--------------

Native classes are compiled to C extension classes, which have some important
differences from normal Python classes:

* Type object namespaces and attribute namespaces are immutable.

* Most metaclasses aren't supported, since their behavior is too
  dynamic.

* Most class decorators aren't supported, as they are usually too
  dynamic. (``@dataclass`` is supported, as an exception.)

* Only single inheritance is supported (except for traits).

If a class definition uses an unsupported metaclass or class
decorator, *mypyc instead compiles the class into a regular Python
class*.

More subtle differences include access to attributes. Here an attribute has
a fallback defined at the class body::

    class Thing:
        id = 0

In Python, if you modify the class attribute, it affects the attribute value
in already created instances::

    x = Thing()
    Thing.id = 1
    print(x.id)  # 1

In compiled code, the class-level fallback is copied to be the value of the
attribute during object construction. A change to the class-level attribute
only affects instances created after the assigned::

    x = Thing()
    Thing.id = 1
    y = Thing()
    print(x.id)  # 0
    print(y.id)  # 1

Runtime type checking
---------------------

Non-erased types in annotations will be type checked at runtime. For example,
consider this function::

    def twice(x: int) -> int:
        return x * 2

If you try to call this function with a ``float`` or ``str`` argument,
you'll get a type error on the call site, even if the call site is not
being type checked::

    twice(5)  # OK
    twice(2.2)  # TypeError
    twice("blah")  # TypeError

Also, values with *inferred* types will be type checked. For example,
consider a call the stdlib function ``socket.gethostname()`` in
compiled code. This function is not compiled (no stdlib modules are
compiled with mypyc), but mypyc uses a *library stub file* to infer
the return type as ``str``. Compiled code calling ``gethostname()``
will fail with ``TypeError`` if ``gethostname()`` would return an
incompatible value such as ``None``::

    import socket

    name = socket.gethostname()  # Fail return value is not str

``gethostname()`` is defined like this in the stub file for ``socket``
(in typeshed)::

    def gethostname() -> str: ...

Thus mypyc expects that library stub files and annotations in
non-compiled code to be correctly annotated. This adds an extra layer
of type safety.

Casts such as ``cast(str, x)`` will also result in strict type
checks. Consider this example::

    from typing import cast
    ...
    x = cast(str, y)

The last line is essentially equivalent to this Python code when compiled::

    if not isinstance(y, x):
        raise TypeError(...)
    x = y

Primitive types
---------------

Beyond strict runtime type checking, some primitive types have changes
differently in compiled code.

``int`` objects use an unboxed (non-heap-allocated) representation for small
integer values. A side effect of this is that the exact runtime type of
``int`` values is lost. For example, consider this simple function::

    def first_num(x: List[int]) -> int:
        return x[0]

    print(first_num([True]))  # Output is 1, instead of True!

``bool`` is a subclass of ``int`, so the above code is valid. However,
when the list value is converted to ``int``, ``True`` is converted to
the corresponding ``int`` value, which is ``1``.

Note that integers are still arbitrary-precision in compiled code,
similar to normal Python integers.

Fixed-length tuples are unboxed, similar to integers. Similar to
integers, the exact type and identity of fixed-length tuples is not
preserved, and you can't reliably use ``is`` checks to compare tuples
that are used in compiled code.

Early binding
-------------

References to functions, types, most attributes, and methods in the
same compilation unit use *early binding*: the target of the reference
is decided at compile time, whenever possible. This contrasts with
Python semantics use *late binding*, where the target is found by a
namespace lookup at runtime. Omitting these namespace lookups allow
improves performance, but some Python idioms require extra steps.

Note that non-final module-level attributes still use late binding.
These should be avoided in performance-critical code.

Monkey patching
---------------

Since mypyc function and class definitions are immutable, you can't
perform arbitrary monkey patching, such as replacing functions or
methods with mocks in tests.

.. note::

    Each compiled module has a Python namespace that is initialized to
    point to compiled functions and type objects. This namespace is a
    regular ``dict`` object, and it *can* be modified. However,
    compiled code generally doesn't use this namespace, so any changes
    will only be visible to non-compiled code.

Stack overflows
---------------

Compiled code currently doesn't check for stack overflows. Your
program may crash in an unrecoverable fashion if you have too nested
function calls, typically due to out-of-control recursion.

.. note::

   This is an implementation limitation that will be fixed in a future
   release.

Final values
------------

Compiled code replaced a reference to an attribute declared ``Final`` with
the value of the attribute computed at compile time. This is an example of
*early binding*, which we discussed earlier. Example::

    MAX: Final = 100

    def limit_to_max(x: int) -> int:
         if x > MAX:
             return MAX
         return x

The two references to ``MAX`` don't involve any module namespace lookups,
and are equivalent to this code::

    def limit_to_max(x: int) -> int:
         if x > 100:
             return 100
         return x

When run as interpreted, the first example will execute slower due to
the extra namespace lookups.

Unsupported features
--------------------

Some Python features are not supported by mypyc (yet). They can't be
used in compiled code, or there are some limitations. You can
partially work around some of these limitations by running your code
in interpreted mode.

Operator overloading
********************

Native classes can only use a few dunder methods to override operators:

* ``__eq__``
* ``__ne__``
* ``__getitem__``
* ``__setitem__``

.. note::

    This is an implementation limitation that will be lifted in the
    future.

Descriptors
***********

Descriptors can't be used in native classes.

Stack introspection
*******************

Frames of compiled functions can't be inspected using ``inspect``.

Pofiling hooks and tracing
**************************

Compiled functions don't trigger profiling and tracing hooks, such as
when using the ``profile``, ``cProfile``, or ``trace`` modules.

Debuggers
*********

You can't set breakpoints in compiled functions or step through
compiled functions using ``pdb``. Often you can debug your code in
interpreted mode instead.
