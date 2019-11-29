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

    The command-line of interface of mypy daemon may change in future mypy
    releases.

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

* ``dmypy recheck`` checks the same set of files as the most recent
  ``check`` or ``recheck`` command. (You can also use the :option:`--update`
  and :option:`--remove` options to alter the set of files, and to define
  which files should be processed.)

* ``dmypy status`` checks whether a daemon is running. It prints a
  diagnostic and exits with ``0`` if there is a running daemon.

Use ``dmypy --help`` for help on additional commands and command-line
options not discussed here, and ``dmypy <command> --help`` for help on
command-specific options.

Additional daemon flags
***********************

.. option:: --status-file FILE

   Use ``FILE`` as the status file for storing daemon runtime state. This is
   normally a JSON file that contains information about daemon process and
   connection. The default path is ``.dmypy.json`` in the current working
   directory.

.. option:: --log-file FILE

   Direct daemon stdout/stderr to ``FILE``. This is useful for debugging daemon
   crashes, since the server traceback is not always printed by the client.
   This is available for the ``start``, ``restart``, and ``run`` commands.

.. option:: --timeout TIMEOUT

   Automatically shut down server after ``TIMEOUT`` seconds of inactivity.
   This is available for the ``start``, ``restart``, and ``run`` commands.

.. option:: --update FILE

   Re-check ``FILE``, or add it to the set of files being
   checked (and check it). This option may be repeated, and it's only available for
   the ``recheck`` command.  By default, mypy finds and checks all files changed
   since the previous run and files that depend on them.  However, if you use this option
   (and/or :option:`--remove`), mypy assumes that only the explicitly
   specified files have changed. This is only useful to
   speed up mypy if you type check a very large number of files, and use an
   external, fast file system watcher, such as `watchman`_ or
   `watchdog`_, to determine which files got edited or deleted.
   *Note:* This option is never required and is only available for
   performance tuning.

.. option:: --remove FILE

   Remove ``FILE`` from the set of files being checked. This option may be
   repeated. This is only available for the
   ``recheck`` command. See :option:`--update` above for when this may be useful.
   *Note:* This option is never required and is only available for performance
   tuning.

.. option:: --fswatcher-dump-file FILE

   Collect information about the current internal file state. This is
   only available for the ``status`` command. This will dump JSON to
   ``FILE`` in the format ``{path: [modification_time, size,
   content_hash]}``. This is useful for debugging the built-in file
   system watcher. *Note:* This is an internal flag and the format may
   change.

.. option:: --perf-stats-file FILE

   Write performance profiling information to ``FILE``. This is only available
   for the ``check``, ``recheck``, and ``run`` commands.

Static inference of annotations
*******************************

The mypy daemon supports (as an experimental feature) statically inferring
draft function and method type annotations. Use ``dmypy suggest FUNCTION`` to
generate a draft signature in the format
``(param_type_1, param_type_2, ...) -> ret_type`` (types are included for all
arguments, including keyword-only arguments, ``*args`` and ``**kwargs``).

This is a low-level feature intended to be used by editor integrations,
IDEs, and other tools (for example, the `mypy plugin for PyCharm`_),
to automatically add annotations to source files, or to propose function
signatures.

In this example, the function ``format_id()`` has no annotation:

.. code-block:: python

   def format_id(user):
       return "User: {}".format(user)

   root = format_id(0)

``dymypy suggest`` uses call sites, return statements, and other heuristics (such as
looking for signatures in base classes) to infer that ``format_id()`` accepts
an ``int`` argument and returns a ``str``. Use ``dmypy suggest module.format_id`` to
print the suggested signature for the function.

More generally, the target function may be specified in two ways:

* By its fully qualified name, i.e. ``[package.]module.[class.]function``.

* By its location in a source file, i.e. ``/path/to/file.py:line``. The path can be
  absolute or relative, and ``line`` can refer to any line number within
  the function body.

This command can also be used to find a more precise alternative for an existing,
imprecise annotation with some ``Any`` types.

The following flags customize various aspects of the ``dmypy suggest``
command.

.. option:: --json

   Output the signature as JSON, so that `PyAnnotate`_ can read it and add
   the signature to the source file. Here is what the JSON looks like:

   .. code-block:: python

      [{"func_name": "example.format_id",
        "line": 1,
        "path": "/absolute/path/to/example.py",
        "samples": 0,
        "signature": {"arg_types": ["int"], "return_type": "str"}}]

.. option:: --no-errors

   Only produce suggestions that cause no errors in the checked code. By default,
   mypy will try to find the most precise type, even if it causes some type errors.

.. option:: --no-any

   Only produce suggestions that don't contain ``Any`` types. By default mypy
   proposes the most precise signature found, even if it contains ``Any`` types.

.. option:: --flex-any FRACTION

   Only allow some fraction of types in the suggested signature to be ``Any`` types.
   The fraction ranges from ``0`` (same as ``--no-any``) to ``1``.

.. option:: --try-text

   Try also using ``unicode`` wherever ``str`` is inferred. This flag may be useful
   for annotating Python 2/3 straddling code.

.. option:: --callsites

   Only find call sites for a given function instead of suggesting a type.
   This will produce a list with line numbers and types of actual
   arguments for each call: ``/path/to/file.py:line: (arg_type_1, arg_type_2, ...)``.

.. option:: --use-fixme NAME

   Use a dummy name instead of plain ``Any`` for types that cannot
   be inferred. This may be useful to emphasize to a user that a given type
   couldn't be inferred and needs to be entered manually.

.. option:: --max-guesses NUMBER

   Set the maximum number of types to try for a function (default: ``64``).

.. TODO: Add similar sections about go to definition, find usages, and
   reveal type when added, and then move this to a separate file.

Limitations
***********

* You have to use either the :option:`--follow-imports=error <mypy --follow-imports>` or
  the :option:`--follow-imports=skip <mypy --follow-imports>` option because of an implementation
  limitation. This can be defined
  through the command line or through a
  :ref:`configuration file <config-file>`.

.. _watchman: https://facebook.github.io/watchman/
.. _watchdog: https://pypi.org/project/watchdog/
.. _PyAnnotate: https://github.com/dropbox/pyannotate
.. _mypy plugin for PyCharm: https://github.com/dropbox/mypy-PyCharm-plugin
