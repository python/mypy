.. _python2:

Type checking Python 2 code
===========================

For code that needs to be Python 2.7 compatible, function type
annotations are given in comments, since the function annotation
syntax was introduced in Python 3. The comment-based syntax is
specified in `PEP 484 <https://www.python.org/dev/peps/pep-0484>`_.

Run mypy in Python 2 mode by using the ``--py2`` option::

    $ mypy --py2 program.py

To run your program, you must have the ``typing`` module in your module
search path. Use ``pip install typing`` to install the module (this also
works for Python 3).

The example below illustrates Python 2 function type annotation
syntax. This is also valid in Python 3 mode:

.. code-block:: python

    from typing import List

    def hello(): # type: () -> None
        print 'hello'

    class Example:
        def method(self, lst, opt=0, *args, **kwargs):
            # type: (List[str], int, *str, **bool) -> int
            ...

Here are more specifics:

- You should include types for arguments with default values in the
  annotation. The ``opt`` argument of ``method`` above is an example
  of this.

- For ``*args`` and ``**kwargs`` the type should be prefixed with
  ``*`` or ``**``, respectively. Again, the above example illustrates
  this.

- The type syntax for variables is the same as for Python 3.

- Things like ``Any`` must be imported from ``typing``, even if they
  are only used in comments.

- You don't provide an annotation for the ``self``/``cls`` variable of
  methods.

- The annotation can be on the same line as the function header or on
  the following line.

- You don't need to use string literal escapes for forward references
  within comments.

- Mypy uses a separate set of library stub files in `typeshed
  <http://github.com/python/typeshed>`_ for Python 2. Library support
  may vary between Python 2 and Python 3.

- In Python 2 mode ``str`` is implicitly promoted to ``unicode``, similar
  to how ``int`` is compatible with ``float``. This is unlike ``bytes`` and
  ``str`` in Python 3, which are incompatible. ``bytes`` in Python 2 is
  equivalent to ``str``.

.. note::

    Currently there's no support for splitting an annotation to multiple
    lines. This will likely change in the future. (PEP 484 already defines
    the syntax to use; we just have to implement it.)
