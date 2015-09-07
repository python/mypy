from typing import Callable, Any, Tuple, Union

SIG_DFL = 0
SIG_IGN = 0

SIGABRT = 0
SIGALRM = 0
SIGBUS = 0
SIGCHLD = 0
SIGCLD = 0
SIGCONT = 0
SIGFPE = 0
SIGHUP = 0
SIGILL = 0
SIGINT = 0
SIGIO = 0
SIGIOT = 0
SIGKILL = 0
SIGPIPE = 0
SIGPOLL = 0
SIGPROF = 0
SIGPWR = 0
SIGQUIT = 0
SIGRTMAX = 0
SIGRTMIN = 0
SIGSEGV = 0
SIGSTOP = 0
SIGSYS = 0
SIGTERM = 0
SIGTRAP = 0
SIGTSTP = 0
SIGTTIN = 0
SIGTTOU = 0
SIGURG = 0
SIGUSR1 = 0
SIGUSR2 = 0
SIGVTALRM = 0
SIGWINCH = 0
SIGXCPU = 0
SIGXFSZ = 0

CTRL_C_EVENT = 0
CTRL_BREAK_EVENT = 0
GSIG = 0
ITIMER_REAL = 0
ITIMER_VIRTUAL = 0
ITIMER_PROF = 0

class ItimerError(IOError): ...

_HANDLER = Union[Callable[[int, Any], Any], int, None]

def alarm(time: float) -> int: ...
def getsignal(signalnum: int) -> _HANDLER: ...
def pause() -> None: ...
def setitimer(which: int, seconds: float, interval: float = None) -> Tuple[float, float]: ...
def getitimer(which: int) -> Tuple[float, float]: ...
def set_wakeup_fd(fd: int) -> None: ...
def siginterrupt(signalnum: int, flag: bool) -> None: ...
def signal(signalnum: int, handler: _HANDLER) -> None: ...
