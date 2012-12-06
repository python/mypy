# Stubs for signal

# Based on http://docs.python.org/3.2/library/signal.html

int SIG_DFL
int SIG_IGN

# TODO more SIG* constants (these should be platform specific?)
int SIGHUP
int SIGINT
int SIGQUIT
int SIGABRT
int SIGKILL
int SIGALRM
int SIGTERM

int SIGUSR1
int SIGUSR2
int SIGCONT
int SIGSTOP

int SIGPOLL
int SIGVTALRM

# CTRL_C_EVENT
# CTRL_BREAK_EVENT

int NSIG
int ITIMER_REAL
int ITIMER_VIRTUAL
int ITIMER_PROF

class ItimerError(IOError): pass

#int alarm(int time): pass # Unix
any getsignal(int signalnum): pass
#void pause(): pass # Unix
#tuple<float, float> setitimer(int which, float seconds,
#                              float interval=None): pass # Unix
#def getitimer(int which): pass # Unix
void set_wakeup_fd(int fd): pass
void siginterrupt(int signalnum, bool flag): pass
any signal(int signalnum,
           func<void(int, any)> handler): pass # TODO frame object
