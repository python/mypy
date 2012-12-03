# Stubs for subprocess

# Based on http://docs.python.org/3.2/library/subprocess.html

# TODO force keyword arguments
# TODO more keyword arguments
int call(Sequence<str> args, *, any stdin=None, any stdout=None,
         any stderr=None, bool shell=False): pass
int check_call(Sequence<str> args, *, any stdin=None, any stdout=None,
               any stderr=None, bool shell=False): pass
bytes check_output(Sequence<str> args, *, any stdin=None, any stderr=None,
                   bool shell=False, bool universal_newlines=False): pass

# TODO types
any PIPE
any STDOUT

class CalledProcessError(Exception):
    int returncode
    str cmd
    bytes output # May be None

class Popen:
    IO stdin
    IO stdout
    IO stderr
    int pid
    int returncode
    
    void __init__(self,
                  Sequence<str> args,
                  int bufsize=0,
                  str executable=None,
                  any stdin=None,
                  any stdout=None,
                  any stderr=None,
                  func<any> preexec_fn=None,
                  bool close_fds=True,
                  bool shell=False,
                  str cwd=None,
                  Mapping<str, str> env=None,
                  bool universal_newlines=False,
                  any startupinfo=None,
                  int creationflags=0,
                  bool restore_signals=True,
                  bool start_new_session=False,
                  any pass_fds=()): pass
    
    int poll(self): pass
    int wait(self): pass
    tuple<bytes, bytes> communicate(self, input=None): pass
    void send_signal(self, int signal): pass
    void terminatate(self): pass
    void kill(self): pass
    void __enter__(self): pass
    void __exit__(self): pass

tuple<int, str> getstatusoutput(str cmd): pass
str getoutput(str cmd): pass

# Windows-only: STARTUPINFO etc.
