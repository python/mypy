# Stubs for signal

# Based on http://docs.python.org/3.2/library/signal.html

from typing import Any, overload, Function

SIG_DFL = 0
SIG_IGN = 0

# TODO more SIG* constants (these should be platform specific?)
SIGHUP = 0
SIGINT = 0
SIGQUIT = 0
SIGABRT = 0
SIGKILL = 0
SIGALRM = 0
SIGTERM = 0

SIGUSR1 = 0
SIGUSR2 = 0
SIGCONT = 0
SIGSTOP = 0

SIGPOLL = 0
SIGVTALRM = 0

CTRL_C_EVENT = 0 # Windows
CTRL_BREAK_EVENT = 0 # Windows

NSIG = 0
ITIMER_REAL = 0
ITIMER_VIRTUAL = 0
ITIMER_PROF = 0

class ItimerError(IOError): pass

def alarm(time: int) -> int: pass # Unix
def getsignal(signalnum: int) -> Any: pass
def pause() -> None: pass # Unix
#def setitimer(which: int, seconds: float,
#              internval: float = None) -> Tuple[float, float]: pass # Unix
#def getitimer(int which): pass # Unix
def set_wakeup_fd(fd: int) -> None: pass
def siginterrupt(signalnum: int, flag: bool) -> None: pass

@overload
def signal(signalnum: int, handler: int) -> Any: pass
@overload
def signal(signalnum: int,
           handler: Function[[int, Any], None]) -> Any:
    pass # TODO frame object type
