.. _python2:

Type checking Python 2 code
===========================

For code that needs to be Python 2.7 compatible, function type
annotations are given in comments, since the function annotation
syntax was introduced in Python 3. The comment-based syntax is
specified in :pep:`484`.

Run mypy in Python 2 mode by using the :option:`--py2 <mypy --py2>` option::

    $ mypy --py2 program.py

To run your program, you must have the ``typing`` module in your
Python 2 module search path. Use ``pip install typing`` to install the
module. This also works for Python 3 versions prior to 3.5 that don't
include :py:mod:`typing` in the standard library.

The example below illustrates the Python 2 function type annotation
syntax. This syntax is also valid in Python 3 mode:

.. code-block:: python

    from typing import List

    def hello(): # type: () -> None
        print 'hello'

    class Example:
        def method(self, lst, opt=0, *args, **kwargs):
            # type: (List[str], int, *str, **bool) -> int
            """Docstring comes after type comment."""
            ...

It's worth going through these details carefully to avoid surprises:

- You don't provide an annotation for the ``self`` / ``cls`` variable of
  methods.

- Docstring always comes *after* the type comment.

- For ``*args`` and ``**kwargs`` the type should be prefixed with
  ``*`` or ``**``, respectively (except when using the multi-line
  annotation syntax described below). Again, the above example
  illustrates this.

- Things like ``Any`` must be imported from ``typing``, even if they
  are only used in comments.

- In Python 2 mode ``str`` is implicitly promoted to ``unicode``, similar
  to how ``int`` is compatible with ``float``. This is unlike ``bytes`` and
  ``str`` in Python 3, which are incompatible. ``bytes`` in Python 2 is
  equivalent to ``str``. (This might change in the future.)

.. _multi_line_annotation:

Multi-line Python 2 function annotations
----------------------------------------

Mypy also supports a multi-line comment annotation syntax. You
can provide a separate annotation for each argument using the variable
annotation syntax. When using the single-line annotation syntax
described above, functions with long argument lists tend to result in
overly long type comments and it's often tricky to see which argument
type corresponds to which argument. The alternative, multi-line
annotation syntax makes long annotations easier to read and write.

Here is an example (from :pep:`484`):

.. code-block:: python

    def send_email(address,     # type: Union[str, List[str]]
                   sender,      # type: str
                   cc,          # type: Optional[List[str]]
                   bcc,         # type: Optional[List[str]]
                   subject='',
                   body=None    # type: List[str]
                   ):
        # type: (...) -> bool
        """Send an email message.  Return True if successful."""
        <code>

You write a separate annotation for each function argument on the same
line as the argument. Each annotation must be on a separate line. If
you leave out an annotation for an argument, it defaults to
``Any``. You provide a return type annotation in the body of the
function using the form ``# type: (...) -> rt``, where ``rt`` is the
return type. Note that the  return type annotation contains literal
three dots.

When using multi-line comments, you do not need to prefix the
types of your ``*arg`` and ``**kwarg`` parameters with ``*`` or ``**``.
For example, here is how you would annotate the first example using
multi-line comments:

.. code-block:: python

    from typing import List

    class Example:
        def method(self,
                   lst,      # type: List[str]
                   opt=0,    # type: int
                   *args,    # type: str
                   **kwargs  # type: bool
                   ):
            # type: (...) -> int
            """Docstring comes after type comment."""
            ...


Additional notes
----------------

- You should include types for arguments with default values in the
  annotation. The ``opt`` argument of ``method`` in the example at the
  beginning of this section is an example of this.

- The annotation can be on the same line as the function header or on
  the following line.

- Variables use a comment-based type syntax (explained in
  :ref:`explicit-var-types`).

- You don't need to use string literal escapes for forward references
  within comments (string literal escapes are explained later).

- Mypy uses a separate set of library stub files in `typeshed
  <https://github.com/python/typeshed>`_ for Python 2. Library support
  may vary between Python 2 and Python 3.
