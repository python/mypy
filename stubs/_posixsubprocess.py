# Stubs for _posixsubprocess

# NOTE: These are incomplete!

tuple<int, int> cloexec_pipe(): pass
int fork_exec(Sequence<str> args,
              executable_list, close_fds, fds_to_keep, str cwd, env_list,
              int p2cread, int p2cwrite, int c2pred, int c2pwrite, int errread,
              int errwrite, int errpipe_read, int errpipe_write,
              restore_signals, start_new_session, preexec_fn): pass
