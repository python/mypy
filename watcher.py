# -*- coding: utf-8 -*-
#@+leo-ver=5-thin
#@+node:ekr.20220925072508.1: * @file watcher.py
#@@first

#@+<< Watcher: imports >>
#@+node:ekr.20220925074127.1: ** << Watcher: imports >>
import os
import pdb
import re
import sys
import traceback
import types
from typing import Any, Dict, List, Tuple
#@-<< Watcher: imports >>
#@+<< define LeoGlobals class >>
#@+node:ekr.20220925080508.1: ** << define LeoGlobals class >>
class LeoGlobals:  # pragma: no cover
    """
    Simplified version of functions in leoGlobals.py.
    """

    total_time = 0.0  # For unit testing.

    #@+others
    #@+node:ekr.20220925074638.2: *3* LeoGlobals.callerName
    def callerName(self, n: int) -> str:
        """Get the function name from the call stack."""
        try:
            f1 = sys._getframe(n)
            code1 = f1.f_code
            return code1.co_name
        except Exception:
            return ''
    #@+node:ekr.20220925074638.3: *3* LeoGlobals.callers
    def callers(self, n: int=4) -> str:
        """
        Return a string containing a comma-separated list of the callers
        of the function that called g.callerList.
        """
        i, result = 2, []
        while True:
            s = self.callerName(n=i)
            if s:
                result.append(s)
            if not s or len(result) >= n:
                break
            i += 1
        return ','.join(reversed(result))
    #@+node:ekr.20220925074638.4: *3* leoGlobals.es_exception & helper
    def es_exception(self, full: bool=True) -> Tuple[str, int]:
        typ, val, tb = sys.exc_info()
        for line in traceback.format_exception(typ, val, tb):
            print(line)
        fileName, n = self.getLastTracebackFileAndLineNumber()
        return fileName, n
    #@+node:ekr.20220925074638.5: *4* LeoGlobals.getLastTracebackFileAndLineNumber
    def getLastTracebackFileAndLineNumber(self) -> Tuple[str, int]:
        typ, val, tb = sys.exc_info()
        if typ == SyntaxError:
            # IndentationError is a subclass of SyntaxError.
            # SyntaxError *does* have 'filename' and 'lineno' attributes.
            return val.filename, val.lineno
        #
        # Data is a list of tuples, one per stack entry.
        # The tuples have the form (filename, lineNumber, functionName, text).
        data = traceback.extract_tb(tb)
        item = data[-1]  # Get the item at the top of the stack.
        filename, n, functionName, text = item
        return filename, n
    #@+node:ekr.20220925074638.6: *3* LeoGlobals.objToString
    def objToString(self, obj: Any, tag: str=None) -> str:
        """Simplified version of g.printObj."""
        result = []
        if tag:
            result.append(f"{tag}...")
        if isinstance(obj, str):
            obj = g.splitLines(obj)
        if isinstance(obj, list):
            result.append('[')
            for z in obj:
                result.append(f"  {z!r}")
            result.append(']')
        elif isinstance(obj, tuple):
            result.append('(')
            for z in obj:
                result.append(f"  {z!r}")
            result.append(')')
        else:
            result.append(repr(obj))
        result.append('')
        return '\n'.join(result)
    #@+node:ekr.20220925074638.7: *3* LeoGlobals.pdb
    def pdb(self) -> None:
        import pdb as _pdb
        # pylint: disable=forgotten-debug-statement
        _pdb.set_trace()
    #@+node:ekr.20220925074638.8: *3* LeoGlobals.plural
    def plural(self, obj: Any) -> str:
        """Return "s" or "" depending on n."""
        if isinstance(obj, (list, tuple, str)):
            n = len(obj)
        else:
            n = obj
        return '' if n == 1 else 's'
    #@+node:ekr.20220925074638.9: *3* LeoGlobals.printObj
    def printObj(self, obj: Any, tag: str=None) -> None:
        """Simplified version of g.printObj."""
        print(self.objToString(obj, tag))
    #@+node:ekr.20220925074638.10: *3* LeoGlobals.shortFileName
    def shortFileName(self, fileName: str) -> str:
        """Return the base name of a path."""
        return os.path.basename(fileName) if fileName else ''
    #@+node:ekr.20220925074638.11: *3* LeoGlobals.splitLines
    def splitLines(self, s: str) -> List[str]:
        """Split s into lines, preserving the number of lines and
        the endings of all lines, including the last line."""
        # g.stat()
        if s:
            return s.splitlines(True)  # This is a Python string function!
        return []
    #@+node:ekr.20220925074638.12: *3* LeoGlobals.toEncodedString
    def toEncodedString(self, s: Any, encoding: str='utf-8') -> bytes:
        """Convert unicode string to an encoded string."""
        if not isinstance(s, str):
            return s
        try:
            s = s.encode(encoding, "strict")
        except UnicodeError:
            s = s.encode(encoding, "replace")
            print(f"toEncodedString: Error converting {s!r} to {encoding}")
        return s
    #@+node:ekr.20220925074638.13: *3* LeoGlobals.toUnicode
    def toUnicode(self, s: Any, encoding: str='utf-8') -> str:
        """Convert bytes to unicode if necessary."""
        tag = 'g.toUnicode'
        if isinstance(s, str):
            return s
        if not isinstance(s, bytes):
            print(f"{tag}: bad s: {s!r}")
            return ''
        b: bytes = s
        try:
            s2 = b.decode(encoding, 'strict')
        except(UnicodeDecodeError, UnicodeError):
            s2 = b.decode(encoding, 'replace')
            print(f"{tag}: unicode error. encoding: {encoding!r}, s2:\n{s2!r}")
            g.trace(g.callers())
        except Exception:
            g.es_exception()
            print(f"{tag}: unexpected error! encoding: {encoding!r}, s2:\n{s2!r}")
            g.trace(g.callers())
        return s2
    #@+node:ekr.20220925074638.14: *3* LeoGlobals.trace
    def trace(self, *args: Any) -> None:
        """Print a tracing message."""
        # Compute the caller name.
        try:
            f1 = sys._getframe(1)
            code1 = f1.f_code
            name = code1.co_name
        except Exception:
            name = ''
        print(f"{name}: {' '.join(str(z) for z in args)}")
    #@+node:ekr.20220925074638.15: *3* LeoGlobals.truncate
    def truncate(self, s: str, n: int) -> str:
        """Return s truncated to n characters."""
        if len(s) <= n:
            return s
        s2 = s[: n - 3] + f"...({len(s)})"
        return s2 + '\n' if s.endswith('\n') else s2
    #@-others
#@-<< define LeoGlobals class >>
g = LeoGlobals()

#@+others
#@+node:ekr.20220925071140.1: ** class Watcher(pdb.Pdb)
class Watcher(pdb.Pdb):
    #@+<< Watcher: docstring >>
    #@+node:ekr.20220925073342.1: *3* << Watcher: docstring >>
    """
    A stand-alone tracer/analysis class.

    The arguments in the pattern lists determine which functions get traced
    or which stats get printed. Each pattern starts with "+", "-", "+:" or
    "-:", followed by a regular expression::

    "+x"  Enables tracing (or stats) for all functions/methods whose name
          matches the regular expression x.
    "-x"  Disables tracing for functions/methods.
    "+:x" Enables tracing for all functions in the **file** whose name matches x.
    "-:x" Disables tracing for an entire file.

    Enabling and disabling depends on the order of arguments in the pattern
    list. Consider the arguments for the Rope trace::

    patterns=['+.*','+:.*',
        '-:.*\\lib\\.*','+:.*rope.*','-:.*leoGlobals.py',
        '-:.*worder.py','-:.*prefs.py','-:.*resources.py',])

    This enables tracing for everything, then disables tracing for all
    library modules, except for all rope modules. Finally, it disables the
    tracing for Rope's worder, prefs and resources modules.

    Being able to zero in on the code of interest can be a big help in
    studying other people's code. This is a non-invasive method: no tracing
    code needs to be inserted anywhere.

    Usage:

    g.SherlockTracer(patterns).run()
    """
    #@-<< Watcher: docstring >>
    #@+others
    #@+node:ekr.20220925071140.2: *3* watcher.__init__
    def __init__(
        self,
        patterns: List[Any],
        indent: bool=True,
        show_args: bool=True,
        show_return: bool=True,
        verbose: bool=True,
    ) -> None:
        """SherlockTracer ctor."""
        self.bad_patterns: List[str] = []  # List of bad patterns.
        self.indent = indent  # True: indent calls and returns.
        self.contents_d: Dict[str, List] = {}  # Keys are file names, values are file lines.
        self.n = 0  # The frame level on entry to run.
        self.stats: Dict[str, Dict] = {}  # Keys are full file names, values are dicts.
        self.patterns: List[Any] = None  # A list of regex patterns to match.
        self.pattern_stack: List[str] = []
        self.show_args = show_args  # True: show args for each function call.
        self.show_return = show_return  # True: show returns from each function.
        self.trace_lines = True  # True: trace lines in enabled functions.
        self.verbose = verbose  # True: print filename:func
        self.set_patterns(patterns)
        try:  # Don't assume g.app exists.
            from leo.core.leoQt import QtCore
            if QtCore:
                # pylint: disable=no-member
                QtCore.pyqtRemoveInputHook()
        except Exception:
            pass
    #@+node:ekr.20220925071140.3: *3* watcher.__call__
    def __call__(self, frame: Any, event: Any, arg: Any) -> Any:
        """Exists so that self.dispatch can return self."""
        return self.dispatch(frame, event, arg)
    #@+node:ekr.20220925071140.4: *3* watcher.bad_pattern
    def bad_pattern(self, pattern: Any) -> None:
        """Report a bad Sherlock pattern."""
        if pattern not in self.bad_patterns:
            self.bad_patterns.append(pattern)
            print(f"\nignoring bad pattern: {pattern}\n")
    #@+node:ekr.20220925071140.5: *3* watcher.check_pattern
    def check_pattern(self, pattern: str) -> bool:
        """Give an error and return False for an invalid pattern."""
        try:
            for prefix in ('+:', '-:', '+', '-'):
                if pattern.startswith(prefix):
                    re.match(pattern[len(prefix) :], 'xyzzy')
                    return True
            self.bad_pattern(pattern)
            return False
        except Exception:
            self.bad_pattern(pattern)
            return False
    #@+node:ekr.20220925071140.6: *3* watcher.dispatch
    def dispatch(self, frame: Any, event: Any, arg: Any) -> Any:
        """The dispatch method."""
        if event == 'call':
            self.do_call(frame, arg)
        elif event == 'return' and self.show_return:
            self.do_return(frame, arg)
        elif event == 'line' and self.trace_lines:
            self.do_line(frame, arg)
        # Queue the SherlockTracer instance again.
        return self
    #@+node:ekr.20220925071140.7: *3* watcher.do_call & helper
    def do_call(self, frame: Any, unused_arg: Any) -> None:
        """Trace through a function call."""
        frame1 = frame
        code = frame.f_code
        file_name = code.co_filename
        locals_ = frame.f_locals
        function_name = code.co_name
        try:
            full_name = self.get_full_name(locals_, function_name)
        except Exception:
            full_name = function_name
        if not self.is_enabled(file_name, full_name, self.patterns):
            # 2020/09/09: Don't touch, for example, __ methods.
            return
        n = 0  # The number of callers of this def.
        while frame:
            frame = frame.f_back
            n += 1
        indent = ' ' * max(0, n - self.n) if self.indent else ''
        path = f"{os.path.basename(file_name):>20}" if self.verbose else ''
        leadin = '+' if self.show_return else ''
        args_list = self.get_args(frame1)
        if self.show_args and args_list:
            args_s = ','.join(args_list)
            args_s2 = f"({args_s})"
            if len(args_s2) > 100:
                print(f"{path}:{indent}{leadin}{full_name}")
                g.printObj(args_list, indent=indent + ' ' * 22)
            else:
                print(f"{path}:{indent}{leadin}{full_name}{args_s2}")
        else:
            print(f"{path}:{indent}{leadin}{full_name}")
        # Always update stats.
        d = self.stats.get(file_name, {})
        d[full_name] = 1 + d.get(full_name, 0)
        self.stats[file_name] = d
    #@+node:ekr.20220925071140.8: *4* watcher.get_args
    def get_args(self, frame: Any) -> List[str]:
        """Return a List of string "name=val" for each arg in the function call."""
        code = frame.f_code
        locals_ = frame.f_locals
        name = code.co_name
        n = code.co_argcount
        if code.co_flags & 4:
            n = n + 1
        if code.co_flags & 8:
            n = n + 1
        result = []
        for i in range(n):
            name = code.co_varnames[i]
            if name != 'self':
                arg = locals_.get(name, '*undefined*')
                if arg:
                    if isinstance(arg, (list, tuple)):
                        val_s = ','.join([self.show(z) for z in arg if self.show(z)])
                        val = f"[{val_s}]"
                    elif isinstance(arg, str):
                        val = arg
                    else:
                        val = self.show(arg)
                    if val:
                        result.append(f"{name}={val}")
        return result
    #@+node:ekr.20220925071140.9: *3* watcher.do_line (not used)
    bad_fns: List[str] = []

    def do_line(self, frame: Any, arg: Any) -> None:
        """print each line of enabled functions."""
        if 1:
            return
        code = frame.f_code
        file_name = code.co_filename
        locals_ = frame.f_locals
        name = code.co_name
        full_name = self.get_full_name(locals_, name)
        if not self.is_enabled(file_name, full_name, self.patterns):
            return
        n = frame.f_lineno - 1  # Apparently, the first line is line 1.
        d = self.contents_d
        lines = d.get(file_name)
        if not lines:
            print(file_name)
            try:
                with open(file_name) as f:
                    s = f.read()
            except Exception:
                if file_name not in self.bad_fns:
                    self.bad_fns.append(file_name)
                    print(f"open({file_name}) failed")
                return
            lines = g.splitLines(s)
            d[file_name] = lines
        line = lines[n].rstrip() if n < len(lines) else '<EOF>'
        if 0:
            print(f"{name:3} {line}")
        else:
            print(f"{g.shortFileName(file_name)} {n} {full_name} {line}")
    #@+node:ekr.20220925071140.10: *3* watcher.do_return & helper
    def do_return(self, frame: Any, arg: Any) -> None:  # Arg *is* used below.
        """Trace a return statement."""
        code = frame.f_code
        fn = code.co_filename
        locals_ = frame.f_locals
        name = code.co_name
        self.full_name = self.get_full_name(locals_, name)
        if not self.is_enabled(fn, self.full_name, self.patterns):
            return
        n = 0
        while frame:
            frame = frame.f_back
            n += 1
        path = f"{os.path.basename(fn):>20}" if self.verbose else ''
        if name and name == '__init__':
            try:
                ret1 = locals_ and locals_.get('self', None)
                self.put_ret(ret1, n, path)
            except NameError:
                self.put_ret(f"<{ret1.__class__.__name__}>", n, path)
        else:
            self.put_ret(arg, n, path)
    #@+node:ekr.20220925071140.11: *4* watcher.put_ret
    def put_ret(self, arg: Any, n: int, path: str) -> None:
        """Print arg, the value returned by a "return" statement."""
        indent = ' ' * max(0, n - self.n + 1) if self.indent else ''
        try:
            if isinstance(arg, types.GeneratorType):
                ret = '<generator>'
            elif isinstance(arg, (tuple, list)):
                ret_s = ','.join([self.show(z) for z in arg])
                if len(ret_s) > 40:
                    g.printObj(arg, indent=indent)
                    ret = ''
                else:
                    ret = f"[{ret_s}]"
            elif arg:
                ret = self.show(arg)
                if len(ret) > 100:
                    ret = f"\n    {ret}"
            else:
                ret = '' if arg is None else repr(arg)
            print(f"{path}:{indent}-{self.full_name} -> {ret}")
        except Exception:
            exctype, value = sys.exc_info()[:2]
            try:  # Be extra careful.
                arg_s = f"arg: {arg!r}"
            except Exception:
                arg_s = ''  # arg.__class__.__name__
            print(
                f"{path}:{indent}-{self.full_name} -> "
                f"{exctype.__name__}, {value} {arg_s}"
            )
    #@+node:ekr.20220925071140.12: *3* watcher.fn_is_enabled
    def fn_is_enabled(self, func: Any, patterns: List[str]) -> bool:
        """Return True if tracing for the given function is enabled."""
        if func in self.ignored_functions:
            return False

        def ignore_function() -> None:
            if func not in self.ignored_functions:
                self.ignored_functions.append(func)
                print(f"Ignore function: {func}")
        #
        # New in Leo 6.3. Never trace dangerous functions.
        table = (
            '_deepcopy.*',
            # Unicode primitives.
            'encode\b', 'decode\b',
            # System functions
            '.*__next\b',
            '<frozen>', '<genexpr>', '<listcomp>',
            # '<decorator-gen-.*>',
            'get\b',
            # String primitives.
            'append\b', 'split\b', 'join\b',
            # File primitives...
            'access_check\b', 'expanduser\b', 'exists\b', 'find_spec\b',
            'abspath\b', 'normcase\b', 'normpath\b', 'splitdrive\b',
        )
        g.trace('=====', func)
        for z in table:
            if re.match(z, func):
                ignore_function()
                return False
        #
        # Legacy code.
        try:
            enabled, pattern = False, None
            for pattern in patterns:
                if pattern.startswith('+:'):
                    if re.match(pattern[2:], func):
                        enabled = True
                elif pattern.startswith('-:'):
                    if re.match(pattern[2:], func):
                        enabled = False
            return enabled
        except Exception:
            self.bad_pattern(pattern)
            return False
    #@+node:ekr.20220925071140.13: *3* watcher.get_full_name
    def get_full_name(self, locals_: Any, name: str) -> str:
        """Return class_name::name if possible."""
        full_name = name
        try:
            user_self = locals_ and locals_.get('self', None)
            if user_self:
                full_name = user_self.__class__.__name__ + '::' + name
        except Exception:
            pass
        return full_name
    #@+node:ekr.20220925071140.14: *3* watcher.is_enabled
    ignored_files: List[str] = []  # List of files.
    ignored_functions: List[str] = []  # List of files.

    def is_enabled(
        self,
        file_name: str,
        function_name: str,
        patterns: List[str]=None,
    ) -> bool:
        """Return True if tracing for function_name in the given file is enabled."""
        #
        # New in Leo 6.3. Never trace through some files.
        if not os:
            return False  # Shutting down.
        base_name = os.path.basename(file_name)
        if base_name in self.ignored_files:
            return False

        def ignore_file() -> None:
            if not base_name in self.ignored_files:
                self.ignored_files.append(base_name)

        def ignore_function() -> None:
            if function_name not in self.ignored_functions:
                self.ignored_functions.append(function_name)

        if f"{os.sep}lib{os.sep}" in file_name:
            ignore_file()
            return False
        if base_name.startswith('<') and base_name.endswith('>'):
            ignore_file()
            return False
        #
        # New in Leo 6.3. Never trace dangerous functions.
        table = (
            '_deepcopy.*',
            # Unicode primitives.
            'encode\b', 'decode\b',
            # System functions
            '.*__next\b',
            '<frozen>', '<genexpr>', '<listcomp>',
            # '<decorator-gen-.*>',
            'get\b',
            # String primitives.
            'append\b', 'split\b', 'join\b',
            # File primitives...
            'access_check\b', 'expanduser\b', 'exists\b', 'find_spec\b',
            'abspath\b', 'normcase\b', 'normpath\b', 'splitdrive\b',
        )
        for z in table:
            if re.match(z, function_name):
                ignore_function()
                return False
        #
        # Legacy code.
        enabled = False
        if patterns is None:
            patterns = self.patterns
        for pattern in patterns:
            try:
                if pattern.startswith('+:'):
                    if re.match(pattern[2:], file_name):
                        enabled = True
                elif pattern.startswith('-:'):
                    if re.match(pattern[2:], file_name):
                        enabled = False
                elif pattern.startswith('+'):
                    if re.match(pattern[1:], function_name):
                        enabled = True
                elif pattern.startswith('-'):
                    if re.match(pattern[1:], function_name):
                        enabled = False
                else:
                    self.bad_pattern(pattern)
            except Exception:
                self.bad_pattern(pattern)
        return enabled
    #@+node:ekr.20220925071140.15: *3* watcher.print_stats
    def print_stats(self, patterns: List[str]=None) -> None:
        """Print all accumulated statisitics."""
        print('\nSherlock statistics...')
        if not patterns:
            patterns = ['+.*', '+:.*',]
        for fn in sorted(self.stats.keys()):
            d = self.stats.get(fn)
            if self.fn_is_enabled(fn, patterns):
                result = sorted(d.keys())  # type:ignore
            else:
                result = [key for key in sorted(d.keys())  # type:ignore
                    if self.is_enabled(fn, key, patterns)]
            if result:
                print('')
                fn = fn.replace('\\', '/')
                parts = fn.split('/')
                print('/'.join(parts[-2:]))
                for key in result:
                    print(f"{d.get(key):4} {key}")
    #@+node:ekr.20220925071140.16: *3* watcher.run
    # Modified from pdb.Pdb.set_trace.

    def run(self, frame: Any=None) -> None:
        """Trace from the given frame or the caller's frame."""
        print("SherlockTracer.run:patterns:\n%s" % '\n'.join(self.patterns))
        if frame is None:
            frame = sys._getframe().f_back
        # Compute self.n, the number of frames to ignore.
        self.n = 0
        while frame:
            frame = frame.f_back
            self.n += 1
        # Pass self to sys.settrace to give easy access to all methods.
        sys.settrace(self)
    #@+node:ekr.20220925071140.17: *3* watcher.push & pop
    def push(self, patterns: List[str]) -> None:
        """Push the old patterns and set the new."""
        self.pattern_stack.append(self.patterns)  # type:ignore
        self.set_patterns(patterns)
        print(f"SherlockTracer.push: {self.patterns}")

    def pop(self) -> None:
        """Restore the pushed patterns."""
        if self.pattern_stack:
            self.patterns = self.pattern_stack.pop()  # type:ignore
            print(f"SherlockTracer.pop: {self.patterns}")
        else:
            print('SherlockTracer.pop: pattern stack underflow')
    #@+node:ekr.20220925071140.18: *3* watcher.set_patterns
    def set_patterns(self, patterns: List[str]) -> None:
        """Set the patterns in effect."""
        self.patterns = [z for z in patterns if self.check_pattern(z)]
    #@+node:ekr.20220925071140.19: *3* watcher.show
    def show(self, item: Any) -> str:
        """return the best representation of item."""
        if not item:
            return repr(item)
        if isinstance(item, dict):
            return 'dict'
        if isinstance(item, str):
            s = repr(item)
            if len(s) <= 20:
                return s
            return s[:17] + '...'
        s = repr(item)
        # A Hack for mypy:
        if s.startswith("<object object"):
            s = "_dummy"
        return s
    #@+node:ekr.20220925071140.20: *3* watcher.stop
    def stop(self) -> None:
        """Stop all tracing."""
        sys.settrace(None)
    #@-others
#@+node:ekr.20220925072732.1: ** function: watcher_main
def watcher_main():
    g.trace()
#@-others

if __name__ == '__main__':
    watcher_main()
#@-leo
