.. _stubtest:

.. program:: stubtest

Automatic stub testing (stubtest)
=================================

Stub files are files containing type annotations. See
`PEP 484 <https://www.python.org/dev/peps/pep-0484/#stub-files>`_
for more motivation and details.

A common problem with stub files is that they tend to diverge from the
actual implementation. Mypy includes the ``stubtest`` tool that can
automatically check for discrepancies between the stubs and the
implementation at runtime.

What stubtest does and does not do
**********************************

Stubtest will import your code and introspect your code objects at runtime, for
example, by using the capabilities of the :py:mod:`inspect` module. Stubtest
will then analyse the stub files, and compare the two, pointing out things that
differ between stubs and the implementation at runtime.

It's important to be aware of the limitations of this comparison. Stubtest will
not make any attempt to statically analyse your actual code and relies only on
dynamic runtime introspection (in particular, this approach means stubtest works
well with extension modules). However, this means that stubtest has limited
visibility; for instance, it cannot tell if a return type of a function is
accurately typed in the stubs.

For clarity, here are some additional things stubtest can't do:

* Type check your code -- use ``mypy`` instead
* Generate stubs -- use ``stubgen`` or ``pyright --createstub`` instead
* Generate stubs based on running your application or test suite -- use ``monkeytype`` instead
* Apply stubs to code to produce inline types -- use ``retype`` or ``libcst`` instead

In summary, stubtest works very well for ensuring basic consistency between
stubs and implementation or to check for stub completeness. It's used to
test Python's official collection of library stubs,
`typeshed <https://github.com/python/typeshed>`_.

Example
*******

Here's a quick example of what stubtest can do:

.. code-block:: shell

    $ python3 -m pip install mypy

    $ cat library.py
    x = "hello, stubtest"

    def foo(x=None):
        print(x)

    $ cat library.pyi
    x: int

    def foo(x: int) -> None: ...

    $ python3 -m mypy.stubtest library
    error: library.foo is inconsistent, runtime argument "x" has a default value but stub argument does not
    Stub: at line 3
    def (x: builtins.int)
    Runtime: at line 3 in file ~/library.py
    def (x=None)

    error: library.x variable differs from runtime type Literal['hello, stubtest']
    Stub: at line 1
    builtins.int
    Runtime:
    hello, stubtest


Usage
*****

Running stubtest can be as simple as ``stubtest module_to_check``.
Run :option:`stubtest --help` for a quick summary of options.

Subtest must be able to import the code to be checked, so make sure that mypy
is installed in the same environment as the library to be tested. In some
cases, setting ``PYTHONPATH`` can help stubtest find the code to import.

Similarly, stubtest must be able to find the stubs to be checked. Stubtest
respects the ``MYPYPATH`` environment variable.

If you wish to ignore some of stubtest's complaints, stubtest supports a
pretty handy allowlist system.

The rest of this section documents the command line interface of stubtest.

.. option:: --concise

    Makes stubtest's output more concise, one line per error

.. option:: --ignore-missing-stub

    Ignore errors for stub missing things that are present at runtime

.. option:: --ignore-positional-only

    Ignore errors for whether an argument should or shouldn't be positional-only

.. option:: --allowlist FILE

    Use file as an allowlist. Can be passed multiple times to combine multiple
    allowlists. Allowlists can be created with --generate-allowlist. Allowlists
    support regular expressions.

.. option:: --generate-allowlist

    Print an allowlist (to stdout) to be used with --allowlist

.. option:: --ignore-unused-allowlist

    Ignore unused allowlist entries

.. option:: --mypy-config-file FILE

    Use specified mypy config file to determine mypy plugins and mypy path

.. option:: --custom-typeshed-dir DIR

    Use the custom typeshed in DIR

.. option:: --check-typeshed

    Check all stdlib modules in typeshed

.. option:: --help

    Show a help message :-)
