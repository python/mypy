.. _getting-started:

Getting started
===============

This chapter introduces some core concepts of mypy, including function
annotations, the :py:mod:`typing` module, stub files, and more.

If you're looking for a quick intro, see the
:ref:`mypy cheatsheet <cheat-sheet-py3>`.

If you're unfamiliar with the concepts of static and dynamic type checking,
be sure to read this chapter carefully, as the rest of the documentation
may not make much sense otherwise.

Installing and running mypy
***************************

Mypy requires Python 3.9 or later to run.  You can install mypy using pip:

.. code-block:: shell

    $ python3 -m pip install mypy

Once mypy is installed, run it by using the ``mypy`` tool:

.. code-block:: shell

    $ mypy program.py

This command makes mypy *type check* your ``program.py`` file and print
out any errors it finds. Mypy will type check your code *statically*: this
means that it will check for errors without ever running your code, just
like a linter.

This also means that you are always free to ignore the errors mypy reports,
if you so wish. You can always use the Python interpreter to run your code,
even if mypy reports errors.

However, if you try directly running mypy on your existing Python code, it
will most likely report little to no errors. This is a feature! It makes it
easy to adopt mypy incrementally.

In order to get useful diagnostics from mypy, you must add *type annotations*
to your code. See the section below for details.

.. _getting-started-dynamic-vs-static:

Dynamic vs static typing
************************

A function without type annotations is considered to be *dynamically typed* by mypy:

.. code-block:: python

   def greeting(name):
       return 'Hello ' + name

By default, mypy will **not** type check dynamically typed functions. This means
that with a few exceptions, mypy will not report any errors with regular unannotated Python.

This is the case even if you misuse the function!

.. code-block:: python

   def greeting(name):
       return 'Hello ' + name

   # These calls will fail when the program runs, but mypy does not report an error
   # because "greeting" does not have type annotations.
   greeting(123)
   greeting(b"Alice")

We can get mypy to detect these kinds of bugs by adding *type annotations* (also
known as *type hints*). For example, you can tell mypy that ``greeting`` both accepts
and returns a string like so:

.. code-block:: python

   # The "name: str" annotation says that the "name" argument should be a string
   # The "-> str" annotation says that "greeting" will return a string
   def greeting(name: str) -> str:
       return 'Hello ' + name

This function is now *statically typed*: mypy will use the provided type hints
to detect incorrect use of the ``greeting`` function and incorrect use of
variables within the ``greeting`` function. For example:

.. code-block:: python

   def greeting(name: str) -> str:
       return 'Hello ' + name

   greeting(3)         # Argument 1 to "greeting" has incompatible type "int"; expected "str"
   greeting(b'Alice')  # Argument 1 to "greeting" has incompatible type "bytes"; expected "str"
   greeting("World!")  # No error

   def bad_greeting(name: str) -> str:
       return 'Hello ' * name  # Unsupported operand types for * ("str" and "str")

Being able to pick whether you want a function to be dynamically or statically
typed can be very helpful. For example, if you are migrating an existing
Python codebase to use static types, it's usually easier to migrate by incrementally
adding type hints to your code rather than adding them all at once. Similarly,
when you are prototyping a new feature, it may be convenient to initially implement
the code using dynamic typing and only add type hints later once the code is more stable.

Once you are finished migrating or prototyping your code, you can make mypy warn you
if you add a dynamic function by mistake by using the :option:`--disallow-untyped-defs <mypy --disallow-untyped-defs>`
flag. You can also get mypy to provide some limited checking of dynamically typed
functions by using the :option:`--check-untyped-defs <mypy --check-untyped-defs>` flag.
See :ref:`command-line` for more information on configuring mypy.

Strict mode and configuration
*****************************

Mypy has a *strict mode* that enables a number of additional checks,
like :option:`--disallow-untyped-defs <mypy --disallow-untyped-defs>`.

If you run mypy with the :option:`--strict <mypy --strict>` flag, you
will basically never get a type related error at runtime without a corresponding
mypy error, unless you explicitly circumvent mypy somehow.

However, this flag will probably be too aggressive if you are trying
to add static types to a large, existing codebase. See :ref:`existing-code`
for suggestions on how to handle that case.

Mypy is very configurable, so you can start with using ``--strict``
and toggle off individual checks. For instance, if you use many third
party libraries that do not have types,
:option:`--ignore-missing-imports <mypy --ignore-missing-imports>`
may be useful. See :ref:`getting-to-strict` for how to build up to ``--strict``.

See :ref:`command-line` and :ref:`config-file` for a complete reference on
configuration options.

More complex types
******************

So far, we've added type hints that use only basic concrete types like
``str`` and ``float``. What if we want to express more complex types,
such as "a list of strings" or "an iterable of ints"?

For example, to indicate that some function can accept a list of
strings, use the ``list[str]`` type (Python 3.9 and later):

.. code-block:: python

   def greet_all(names: list[str]) -> None:
       for name in names:
           print('Hello ' + name)

   names = ["Alice", "Bob", "Charlie"]
   ages = [10, 20, 30]

   greet_all(names)   # Ok!
   greet_all(ages)    # Error due to incompatible types

The :py:class:`list` type is an example of something called a *generic type*: it can
accept one or more *type parameters*. In this case, we *parameterized* :py:class:`list`
by writing ``list[str]``. This lets mypy know that ``greet_all`` accepts specifically
lists containing strings, and not lists containing ints or any other type.

In the above examples, the type signature is perhaps a little too rigid.
After all, there's no reason why this function must accept *specifically* a list --
it would run just fine if you were to pass in a tuple, a set, or any other custom iterable.

You can express this idea using :py:class:`collections.abc.Iterable`:

.. code-block:: python

   from collections.abc import Iterable  # or "from typing import Iterable"

   def greet_all(names: Iterable[str]) -> None:
       for name in names:
           print('Hello ' + name)

This behavior is actually a fundamental aspect of the PEP 484 type system: when
we annotate some variable with a type ``T``, we are actually telling mypy that
variable can be assigned an instance of ``T``, or an instance of a *subtype* of ``T``.
That is, ``list[str]`` is a subtype of ``Iterable[str]``.

This also applies to inheritance, so if you have a class ``Child`` that inherits from
``Parent``, then a value of type ``Child`` can be assigned to a variable of type ``Parent``.
For example, a ``RuntimeError`` instance can be passed to a function that is annotated
as taking an ``Exception``.

As another example, suppose you want to write a function that can accept *either*
ints or strings, but no other types. You can express this using a
union type. For example, ``int`` is a subtype of ``int | str``:

.. code-block:: python

   def normalize_id(user_id: int | str) -> str:
       if isinstance(user_id, int):
           return f'user-{100_000 + user_id}'
       else:
           return user_id

.. note::

    If using Python 3.9 or earlier, use ``typing.Union[int, str]`` instead of
    ``int | str``, or use ``from __future__ import annotations`` at the top of
    the file (see :ref:`runtime_troubles`).

The :py:mod:`typing` module contains many other useful types.

For a quick overview, look through the :ref:`mypy cheatsheet <cheat-sheet-py3>`.

For a detailed overview (including information on how to make your own
generic types or your own type aliases), look through the
:ref:`type system reference <overview-type-system-reference>`.

.. note::

   When adding types, the convention is to import types
   using the form ``from typing import <name>`` (as opposed to doing
   just ``import typing`` or ``import typing as t`` or ``from typing import *``).

   For brevity, we often omit imports from :py:mod:`typing` or :py:mod:`collections.abc`
   in code examples, but mypy will give an error if you use types such as
   :py:class:`~collections.abc.Iterable` without first importing them.

.. note::

   In some examples we use capitalized variants of types, such as
   ``List``, and sometimes we use plain ``list``. They are equivalent,
   but the prior variant is needed if you are using Python 3.8 or earlier.

Local type inference
********************

Once you have added type hints to a function (i.e. made it statically typed),
mypy will automatically type check that function's body. While doing so,
mypy will try and *infer* as many details as possible.

We saw an example of this in the ``normalize_id`` function above -- mypy understands
basic :py:func:`isinstance <isinstance>` checks and so can infer that the ``user_id`` variable was of
type ``int`` in the if-branch and of type ``str`` in the else-branch.

As another example, consider the following function. Mypy can type check this function
without a problem: it will use the available context and deduce that ``output`` must be
of type ``list[float]`` and that ``num`` must be of type ``float``:

.. code-block:: python

   def nums_below(numbers: Iterable[float], limit: float) -> list[float]:
       output = []
       for num in numbers:
           if num < limit:
               output.append(num)
       return output

For more details, see :ref:`type-inference-and-annotations`.

Types from libraries
********************

Mypy can also understand how to work with types from libraries that you use.

For instance, mypy comes out of the box with an intimate knowledge of the
Python standard library. For example, here is a function which uses the
``Path`` object from the :doc:`pathlib standard library module <python:library/pathlib>`:

.. code-block:: python

    from pathlib import Path

    def load_template(template_path: Path, name: str) -> str:
        # Mypy knows that `template_path` has a `read_text` method that returns a str
        template = template_path.read_text()
        # ...so it understands this line type checks
        return template.replace('USERNAME', name)

If a third party library you use :ref:`declares support for type checking <installed-packages>`,
mypy will type check your use of that library based on the type hints
it contains.

However, if the third party library does not have type hints, mypy will
complain about missing type information.

.. code-block:: text

  prog.py:1: error: Library stubs not installed for "yaml"
  prog.py:1: note: Hint: "python3 -m pip install types-PyYAML"
  prog.py:2: error: Library stubs not installed for "requests"
  prog.py:2: note: Hint: "python3 -m pip install types-requests"
  ...

In this case, you can provide mypy a different source of type information,
by installing a *stub* package. A stub package is a package that contains
type hints for another library, but no actual code.

.. code-block:: shell

  $ python3 -m pip install types-PyYAML types-requests

Stubs packages for a distribution are often named ``types-<distribution>``.
Note that a distribution name may be different from the name of the package that
you import. For example, ``types-PyYAML`` contains stubs for the ``yaml``
package.

For more discussion on strategies for handling errors about libraries without
type information, refer to :ref:`fix-missing-imports`.

For more information about stubs, see :ref:`stub-files`.

Next steps
**********

If you are in a hurry and don't want to read lots of documentation
before getting started, here are some pointers to quick learning
resources:

* Read the :ref:`mypy cheatsheet <cheat-sheet-py3>`.

* Read :ref:`existing-code` if you have a significant existing
  codebase without many type annotations.

* Read the `blog post <https://blog.zulip.org/2016/10/13/static-types-in-python-oh-mypy/>`_
  about the Zulip project's experiences with adopting mypy.

* If you prefer watching talks instead of reading, here are
  some ideas:

  * Carl Meyer:
    `Type Checked Python in the Real World <https://www.youtube.com/watch?v=pMgmKJyWKn8>`_
    (PyCon 2018)

  * Greg Price:
    `Clearer Code at Scale: Static Types at Zulip and Dropbox <https://www.youtube.com/watch?v=0c46YHS3RY8>`_
    (PyCon 2018)

* Look at :ref:`solutions to common issues <common_issues>` with mypy if
  you encounter problems.

* You can ask questions about mypy in the
  `mypy issue tracker <https://github.com/python/mypy/issues>`_ and
  typing `Gitter chat <https://gitter.im/python/typing>`_.

* For general questions about Python typing, try posting at
  `typing discussions <https://github.com/python/typing/discussions>`_.

You can also continue reading this document and skip sections that
aren't relevant for you. You don't need to read sections in order.
