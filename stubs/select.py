# Stubs for select

# NOTE: These are incomplete!

class error(Exception): pass

int POLLIN
int POLLPRI
int POLLOUT
int POLLERR
int POLLHUP
int POLLNVAL

class poll:
    void __init__(self): pass
    void register(self, any fd, int eventmask=POLLIN|POLLPRI|POLLOUT): pass
    void modify(self, any fd, int eventmask): pass
    void unregister(self, any fd): pass
    tuple<int, int>[] poll(self, int timeout=None): pass

tuple<int[], int[], int[]> select(Sequence rlist, Sequence wlist,
                                  Sequence xlist, float timeout=None): pass
