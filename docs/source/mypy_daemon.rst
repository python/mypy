.. _mypy_daemon:

.. program:: dmypy

Mypy daemon (mypy server)
=========================

Instead of running mypy as a command-line tool, you can also run it as
a long-running daemon (server) process and use a command-line client to
send type-checking requests to the server.  This way mypy can perform type
checking much faster, since program state cached from previous runs is kept
in memory and doesn't have to be read from the file system on each run.
The server also uses finer-grained dependency tracking to reduce the amount
of work that needs to be done.

If you have a large codebase to check, running mypy using the mypy
daemon can be *10 or more times faster* than the regular command-line
``mypy`` tool, especially if your workflow involves running mypy
repeatedly after small edits -- which is often a good idea, as this way
you'll find errors sooner.

.. note::

    The mypy daemon is experimental. In particular, the command-line
    interface may change in future mypy releases.

.. note::

    Each mypy daemon process supports one user and one set of source files,
    and it can only process one type checking request at a time. You can
    run multiple mypy daemon processes to type check multiple repositories.


Basic usage
***********

The client utility ``dmypy`` is used to control the mypy daemon.
Use ``dmypy run -- <flags> <files>`` to typecheck a set of files
(or directories). This will launch the daemon if it is not running.
You can use almost arbitrary mypy flags after ``--``.  The daemon
will always run on the current host. Example::

    dmypy run -- --follow-imports=error prog.py pkg1/ pkg2/

.. note::
   You'll need to use either the :option:`--follow-imports=error <mypy --follow-imports>` or the
   :option:`--follow-imports=skip <mypy --follow-imports>` option with dmypy because the current
   implementation can't follow imports.
   See :ref:`follow-imports` for details on how these work.
   You can also define these using a
   :ref:`configuration file <config-file>`.

``dmypy run`` will automatically restart the daemon if the
configuration or mypy version changes.

You need to provide all files or directories you want to type check
(other than stubs) as arguments. This is a result of the
:option:`--follow-imports <mypy --follow-imports>` restriction mentioned above.

The initial run will process all the code and may take a while to
finish, but subsequent runs will be quick, especially if you've only
changed a few files. You can use :ref:`remote caching <remote-cache>`
to speed up the initial run. The speedup can be significant if
you have a large codebase.

Daemon client commands
**********************

While ``dmypy run`` is sufficient for most uses, some workflows
(ones using :ref:`remote caching <remote-cache>`, perhaps),
require more precise control over the lifetime of the daemon process:

* ``dmypy stop`` stops the daemon.

* ``dmypy start -- <flags>`` starts the daemon but does not check any files.
  You can use almost arbitrary mypy flags after ``--``.

* ``dmypy restart -- <flags>`` restarts the daemon. The flags are the same
  as with ``dmypy start``. This is equivalent to a stop command followed
  by a start.

* Use ``dmypy run --timeout SECONDS -- <flags>`` (or
  ``start`` or ``restart``) to automatically
  shut down the daemon after inactivity. By default, the daemon runs
  until it's explicitly stopped.

* ``dmypy check <files>`` checks a set of files using an already
  running daemon.

* ``dmypy status`` checks whether a daemon is running. It prints a
  diagnostic and exits with ``0`` if there is a running daemon.

Use ``dmypy --help`` for help on additional commands and command-line
options not discussed here, and ``dmypy <command> --help`` for help on
command-specific options.

Additional daemon flags
***********************

.. option:: --status-file FILE

   Status file to retrieve daemon details. This is normally a JSON file
   that contains information about daemon process and connection. Default is
   ``.dmypy.json``.

.. option:: --log-file FILE

   Direct daemon stdout/stderr to ``FILE``. This is useful for debugging daemon
   crashes, since the server traceback may be not printed to client stderr. Only
   available for ``start``, ``restart``, and ``run`` commands.

.. option:: --timeout TIMEOUT

   Server shutdown timeout (in seconds). Only available for ``start``,
   ``restart``, and ``run`` commands.

.. option:: --fswatcher-dump-file FILE

   Collect information about the current file state. Only available for
   ``status`` command.

.. option:: --perf-stats-file FILE

   Write performance telemetry information to the given file. Only available
   for ``check``, ``recheck``, and ``run`` commands.

.. option:: --update FILE

   Files in the run to add or check again, may be repeated. Default: all
   files from the previous run. Only available for ``recheck`` command.

.. option:: --remove FILE

   Files to remove from the run, may be repeated. Only available for
   ``recheck`` command.

Static inference of annotations
*******************************

Mypy daemon supports (as experimental feature) statically inferring draft type
annotation for a given function or method. For example, given this program:

.. code-block:: python

   def format_id(user):
       return "User: {}".format(user)

   root = format_id(0)

Mypy can infer that ``format_id()`` takes an ``int`` and returns a ``str``.
To get a suggested signature for a function, use ``dmypy suggest FUNCTION``,
where the function may be specified in either of two forms:

* By its fully qualified name, i.e. ``[package.]module.[class.]function``

* By its textual location, i.e. ``/path/to/file.py:line``

Running this command will produce a suggested signature in the format
``(param_type_1, param_type_2, ...) -> ret_type``. This may be used by IDEs
or similar tools to propose to user and/or insert the annotation into file.

This command can also be used to find an improvement for an existing (imprecise)
annotation. The following flags customize various aspects of the ``dmypy suggest``
command.

.. option:: --json

   Use JSON format to output the signature, so that `PyAnnotate`_ can use it
   to apply a suggestion to file.

.. option:: --no-errors

   Only produce suggestions that cause no errors in the checked code. By default
   mypy will try to find the most precise type, even if it causes some type errors.

.. option:: --no-any

   Only produce suggestions that don't contain ``Any`` types. By default mypy
   proposes the most precise signature found, even if it contains ``Any`` types.

.. option:: --flex-any PERCENTAGE

   Allow ``Any`` types in suggested signature if they go above a certain score.
   Scores are from ``0`` (same as ``--no-any``) to ``1``.

.. option:: --try-text

   Try using ``unicode`` wherever ``str`` is inferred. This flag may be useful
   for annotating Python 2/3 straddling code.

.. option:: --callsites

   Only find call sites for a given function instead of suggesting a type.
   This will produce a list including textual locations and types of actual
   arguments for each call: ``/path/to/file.py:line: (arg_type_1, arg_type_2, ...)``.

.. option:: --use-fixme NAME

   A dummy name to use instead of plain ``Any`` for types that cannot
   be inferred.

.. option:: --max-guesses NUMBER

   Set the maximum number of types to try for a function (default ``64``).

.. TODO: Add similar sections about go to definition, find usages, and
   reveal type when added.

Limitations
***********

* You have to use either the :option:`--follow-imports=error <mypy --follow-imports>` or
  the :option:`--follow-imports=skip <mypy --follow-imports>` option because of an implementation
  limitation. This can be defined
  through the command line or through a
  :ref:`configuration file <config-file>`.

.. _PyAnnotate: https://github.com/dropbox/pyannotate
