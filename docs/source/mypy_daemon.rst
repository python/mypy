.. _mypy_daemon:

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

    The mypy daemon currently supports macOS and Linux only.

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
   You'll need to use either the ``--follow-imports=error`` or the
   ``--follow-imports=skip`` option with dmypy because the current
   implementation can't follow imports.
   See :ref:`follow-imports` for details on how these work.
   You can also define these using a
   :ref:`configuration file <config-file>`.

``dmypy run`` will automatically restart the daemon if the
configuration or mypy version changes.

You need to provide all files or directories you want to type check
(other than stubs) as arguments. This is a result of the
``--follow-imports`` restriction mentioned above.

The initial run will process all the code and may take a while to
finish, but subsequent runs will be quick, especially if you've only
changed a few files. You can use :ref:`remote caching <remote-cache>`
to speed up the initial run. The speedup can be significant if
you have a large codebase.

Additional features
*******************

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

Limitations
***********

* You have to use either the ``--follow-imports=error`` or
  the ``--follow-imports=skip`` option because of an implementation
  limitation. This can be defined
  through the command line or through a
  :ref:`configuration file <config-file>`.

* Windows is not supported.
