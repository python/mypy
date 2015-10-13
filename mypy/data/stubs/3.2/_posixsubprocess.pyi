# Stubs for _posixsubprocess

# NOTE: These are incomplete!

from typing import Tuple, Sequence

def cloexec_pipe() -> Tuple[int, int]: ...
def fork_exec(args: Sequence[str],
              executable_list, close_fds, fds_to_keep, cwd: str, env_list,
              p2cread: int, p2cwrite: int, c2pred: int, c2pwrite: int,
              errread: int, errwrite: int, errpipe_read: int,
              errpipe_write: int, restore_signals, start_new_session,
              preexec_fn) -> int: ...
