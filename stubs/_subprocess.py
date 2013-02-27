# Stubs for _subprocess

# NOTE: These are incomplete!

int CREATE_NEW_CONSOLE
int CREATE_NEW_PROCESS_GROUP
int STD_INPUT_HANDLE
int STD_OUTPUT_HANDLE
int STD_ERROR_HANDLE
int SW_HIDE
int STARTF_USESTDHANDLES
int STARTF_USESHOWWINDOW
int INFINITE
int DUPLICATE_SAME_ACCESS
int WAIT_OBJECT_0

# TODO not exported by the Python module
class Handle:
    void Close(self): pass

int GetVersion(): pass
int GetExitCodeProcess(Handle handle): pass
int WaitForSingleObject(Handle handle, int timeout): pass
tuple<any, Handle, int, int> CreateProcess(str executable, str cmd_line,
                                           proc_attrs, thread_attrs,
                                           int inherit, int flags,
                                           Mapping<str, str> env_mapping,
                                           str curdir, any startupinfo): pass
str GetModuleFileName(int module): pass
Handle GetCurrentProcess(): pass
int DuplicateHandle(Handle source_proc, Handle source, Handle target_proc,
                    any target, int access, int inherit): pass
tuple<Handle, Handle> CreatePipe(pipe_attrs, int size): pass
int GetStdHandle(int arg): pass
void TerminateProcess(Handle handle, int exit_code): pass
