.. _mypy_daemon:

Mypy daemon (mypy server)
=========================

Instead of running mypy as a command-line tool, you can also run it as
a long-running daemon (server) process and use a command-line client to
control the server.  This way mypy can perform type checking much faster,
since program state cached from previous runs is kept in memory and doesn't
have to be read from the file system on each run. The server also uses
finer-grained dependency tracking to reduce the amount of work that needs
to be done.

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

Basic usage
***********

The client utility ``dmypy`` is used to control the mypy daemon.
Use ``dmypy start -- <flags>`` to start the daemon. You can use almost
arbitrary mypy flags after ``--``.  The daemon will always run on the
current host. Example::

    dmypy start -- --follow-imports=skip

.. note::
   You'll need to use either the ``--follow-imports=skip`` or the
   ``--follow-imports=error`` option with dmypy.
   See :ref:`follow-imports` for details on how these work.

The daemon will not type check anything after the start command.
Use ``dmypy check <files>`` to check some files (or directories)::

    dmypy check prog.py pkg1/ pkg2/

You need to provide all files or directories you want to type check
(other than stubs) as arguments.

The initial run will process all the code and may take a while to
finish, but subsequent runs will be quick, especially if you've only
changed a few files.

Additional features
*******************

You have precise control over the lifetime of the daemon process:

* ``dymypy stop`` stops the daemon.

* ``dmypy restart -- <flags>`` restarts the daemon. The flags are the same
  as with ``dmypy start``.

* Use ``dmypy start --timeout SECONDS -- <flags>`` (or
  ``dmypy restart --timeout SECONDS -- <flags>``) to automatically
  shut down the daemon after inactivity.

Use ``dmypy --help`` for help on additional commands and command-line
options not discussed here, and ``dmypy <command> --help`` for help on
command-specific options.

You can use a :ref:`remote cache <remote-cache>` to speed up the
initial ``dmypy check`` run. The speedup can be significant if
you have a large codebase.

Limitations
***********

* Changes related to protocol classes are not reliably propagated.

* You have to use either the ``--follow-imports=skip`` or
  the ``--follow-imports=error`` option. This can be defined
  through the command line or through a
  :ref:`configuration file <config-file>`.

* Windows is not supported.
