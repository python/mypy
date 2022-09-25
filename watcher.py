# -*- coding: utf-8 -*-
#@+leo-ver=5-thin
#@+node:ekr.20220925072508.1: * @file watcher.py
#@@first

#@+<< Watcher: imports >>
#@+node:ekr.20220925074127.1: ** << Watcher: imports >>
import os
import pdb
# import re
import sys
import traceback
# import types
from typing import Any, List, Tuple
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
    
    pass  ###
    #@+others
    #@-others
#@+node:ekr.20220925072732.1: ** function: watcher_main
def watcher_main():
    import watcher_test
    assert watcher_test  ###
    g.trace(watcher_test)
#@-others

if __name__ == '__main__':
    watcher_main()
#@-leo
