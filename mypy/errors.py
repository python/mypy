import os.path
import sys
import traceback
from collections import OrderedDict, defaultdict
from contextlib import contextmanager

from typing import Tuple, List, TypeVar, Set, Dict, Iterator, Optional, cast

from mypy.options import Options
from mypy.version import __version__ as mypy_version


T = TypeVar('T')
allowed_duplicates = ['@overload', 'Got:', 'Expected:']


class ErrorInfo:
    """Representation of a single error message."""

    # Description of a sequence of imports that refer to the source file
    # related to this error. Each item is a (path, line number) tuple.
    import_ctx = None  # type: List[Tuple[str, int]]

    # The source file that was the source of this error.
    file = ''

    # The fully-qualified id of the source module for this error.
    module = None  # type: Optional[str]

    # The name of the type in which this error is located at.
    type = ''  # type: Optional[str]   # Unqualified, may be None

    # The name of the function or member in which this error is located at.
    function_or_member = ''  # type: Optional[str]   # Unqualified, may be None

    # The line number related to this error within file.
    line = 0     # -1 if unknown

    # The column number related to this error with file.
    column = 0   # -1 if unknown

    # Either 'error', 'note', or 'warning'.
    severity = ''

    # The error message.
    message = ''

    # If True, we should halt build after the file that generated this error.
    blocker = False

    # Only report this particular messages once per program.
    only_once = False

    # Fine-grained incremental target where this was reported
    target = None  # type: Optional[str]

    def __init__(self,
                 import_ctx: List[Tuple[str, int]],
                 file: str,
                 module: Optional[str],
                 typ: Optional[str],
                 function_or_member: Optional[str],
                 line: int,
                 column: int,
                 severity: str,
                 message: str,
                 blocker: bool,
                 only_once: bool,
                 origin: Optional[Tuple[str, int]] = None,
                 target: Optional[str] = None) -> None:
        self.import_ctx = import_ctx
        self.file = file
        self.module = module
        self.type = typ
        self.function_or_member = function_or_member
        self.line = line
        self.column = column
        self.severity = severity
        self.message = message
        self.blocker = blocker
        self.only_once = only_once
        self.origin = origin or (file, line)
        self.target = target


class Errors:
    """Container for compile errors.

    This class generates and keeps tracks of compile errors and the
    current error context (nested imports).
    """

    # List of generated error messages.
    error_info = None  # type: List[ErrorInfo]

    # Current error context: nested import context/stack, as a list of (path, line) pairs.
    import_ctx = None  # type: List[Tuple[str, int]]

    # Set of files with errors.
    error_files = None  # type: Set[str]

    # Path name prefix that is removed from all paths, if set.
    ignore_prefix = None  # type: str

    # Path to current file.
    file = None  # type: str

    # Stack of short names of currents types (or None).
    type_name = None  # type: List[Optional[str]]

    # Stack of short names of current functions or members (or None).
    function_or_member = None  # type: List[Optional[str]]

    # Ignore errors on these lines of each file.
    ignored_lines = None  # type: Dict[str, Set[int]]

    # Lines on which an error was actually ignored.
    used_ignored_lines = None  # type: Dict[str, Set[int]]

    # Files where all errors should be ignored.
    ignored_files = None  # type: Set[str]

    # Collection of reported only_once messages.
    only_once_messages = None  # type: Set[str]

    # Set to True to show "In function "foo":" messages.
    show_error_context = False  # type: bool

    # Set to True to show column numbers in error messages.
    show_column_numbers = False  # type: bool

    # Stack of active fine-grained incremental checking targets within
    # a module. The first item is always the current module id.
    # (See mypy.server.update for more about targets.)
    target = None  # type: List[str]

    def __init__(self, show_error_context: bool = False,
                 show_column_numbers: bool = False) -> None:
        self.show_error_context = show_error_context
        self.show_column_numbers = show_column_numbers
        self.initialize()

    def initialize(self) -> None:
        self.error_info = []
        self.import_ctx = []
        self.error_files = set()
        self.type_name = [None]
        self.function_or_member = [None]
        self.ignored_lines = OrderedDict()
        self.used_ignored_lines = defaultdict(set)
        self.ignored_files = set()
        self.only_once_messages = set()
        self.target = []

    def reset(self) -> None:
        self.initialize()

    def copy(self) -> 'Errors':
        new = Errors(self.show_error_context, self.show_column_numbers)
        new.file = self.file
        new.import_ctx = self.import_ctx[:]
        new.type_name = self.type_name[:]
        new.function_or_member = self.function_or_member[:]
        new.target = self.target[:]
        return new

    def set_ignore_prefix(self, prefix: str) -> None:
        """Set path prefix that will be removed from all paths."""
        prefix = os.path.normpath(prefix)
        # Add separator to the end, if not given.
        if os.path.basename(prefix) != '':
            prefix += os.sep
        self.ignore_prefix = prefix

    def simplify_path(self, file: str) -> str:
        file = os.path.normpath(file)
        return remove_path_prefix(file, self.ignore_prefix)

    def set_file(self, file: str,
                 module: Optional[str],
                 ignored_lines: Optional[Set[int]] = None) -> None:
        """Set the path and module id of the current file."""
        # The path will be simplified later, in render_messages. That way
        #  * 'file' is always a key that uniquely identifies a source file
        #    that mypy read (simplified paths might not be unique); and
        #  * we only have to simplify in one place, while still supporting
        #    reporting errors for files other than the one currently being
        #    processed.
        self.file = file
        if module:
            self.target = [module]

    def set_file_ignored_lines(self, file: str,
                               ignored_lines: Set[int],
                               ignore_all: bool = False) -> None:
        self.ignored_lines[file] = ignored_lines
        if ignore_all:
            self.ignored_files.add(file)

    def push_function(self, name: str) -> None:
        """Set the current function or member short name (it can be None)."""
        self.push_target_component(name)
        self.function_or_member.append(name)

    def pop_function(self) -> None:
        self.function_or_member.pop()
        self.pop_target_component()

    @contextmanager
    def enter_function(self, name: str) -> Iterator[None]:
        self.push_function(name)
        yield
        self.pop_function()

    def push_type(self, name: str) -> None:
        """Set the short name of the current type (it can be None)."""
        self.push_target_component(name)
        self.type_name.append(name)

    def pop_type(self) -> None:
        self.type_name.pop()
        self.pop_target_component()

    def push_target_component(self, name: str) -> None:
        if self.target and not self.function_or_member[-1]:
            self.target.append('{}.{}'.format(self.target[-1], name))

    def pop_target_component(self) -> None:
        if self.target and not self.function_or_member[-1]:
            self.target.pop()

    def current_target(self) -> Optional[str]:
        if self.target:
            return self.target[-1]
        return None

    def current_module(self) -> Optional[str]:
        if self.target:
            return self.target[0]
        return None

    @contextmanager
    def enter_type(self, name: str) -> Iterator[None]:
        """Set the short name of the current type (it can be None)."""
        self.push_type(name)
        yield
        self.pop_type()

    def import_context(self) -> List[Tuple[str, int]]:
        """Return a copy of the import context."""
        return self.import_ctx[:]

    def set_import_context(self, ctx: List[Tuple[str, int]]) -> None:
        """Replace the entire import context with a new value."""
        self.import_ctx = ctx[:]

    def report(self,
               line: int,
               column: int,
               message: str,
               blocker: bool = False,
               severity: str = 'error',
               file: Optional[str] = None,
               only_once: bool = False,
               origin_line: Optional[int] = None,
               offset: int = 0) -> None:
        """Report message at the given line using the current error context.

        Args:
            line: line number of error
            message: message to report
            blocker: if True, don't continue analysis after this error
            severity: 'error', 'note' or 'warning'
            file: if non-None, override current file as context
            only_once: if True, only report this exact message once per build
            origin_line: if non-None, override current context as origin
        """
        type = self.type_name[-1]  # type: Optional[str]
        if len(self.function_or_member) > 2:
            type = None  # Omit type context if nested function
        if file is None:
            file = self.file
        if offset:
            message = " " * offset + message
        info = ErrorInfo(self.import_context(), file, self.current_module(), type,
                         self.function_or_member[-1], line, column, severity, message,
                         blocker, only_once,
                         origin=(self.file, origin_line) if origin_line else None,
                         target=self.current_target())
        self.add_error_info(info)

    def add_error_info(self, info: ErrorInfo) -> None:
        (file, line) = cast(Tuple[str, int], info.origin)  # see issue 1855
        if not info.blocker:  # Blockers cannot be ignored
            if file in self.ignored_lines and line in self.ignored_lines[file]:
                # Annotation requests us to ignore all errors on this line.
                self.used_ignored_lines[file].add(line)
                return
            if file in self.ignored_files:
                return
        if info.only_once:
            if info.message in self.only_once_messages:
                return
            self.only_once_messages.add(info.message)
        self.error_info.append(info)
        self.error_files.add(file)

    def generate_unused_ignore_notes(self) -> None:
        for file, ignored_lines in self.ignored_lines.items():
            if not self.is_typeshed_file(file):
                for line in ignored_lines - self.used_ignored_lines[file]:
                    # Don't use report since add_error_info will ignore the error!
                    info = ErrorInfo(self.import_context(), file, self.current_module(), None,
                                     None, line, -1, 'note', "unused 'type: ignore' comment",
                                     False, False)
                    self.error_info.append(info)

    def is_typeshed_file(self, file: str) -> bool:
        # gross, but no other clear way to tell
        return 'typeshed' in os.path.normpath(file).split(os.sep)

    def num_messages(self) -> int:
        """Return the number of generated messages."""
        return len(self.error_info)

    def is_errors(self) -> bool:
        """Are there any generated errors?"""
        return bool(self.error_info)

    def is_blockers(self) -> bool:
        """Are the any errors that are blockers?"""
        return any(err for err in self.error_info if err.blocker)

    def is_errors_for_file(self, file: str) -> bool:
        """Are there any errors for the given file?"""
        return file in self.error_files

    def raise_error(self) -> None:
        """Raise a CompileError with the generated messages.

        Render the messages suitable for displaying.
        """
        raise CompileError(self.messages(), use_stdout=True)

    def messages(self) -> List[str]:
        """Return a string list that represents the error messages.

        Use a form suitable for displaying to the user.
        """
        a = []  # type: List[str]
        errors = self.render_messages(self.sort_messages(self.error_info))
        errors = self.remove_duplicates(errors)
        for file, line, column, severity, message in errors:
            s = ''
            if file is not None:
                if self.show_column_numbers and line is not None and line >= 0 \
                        and column is not None and column >= 0:
                    srcloc = '{}:{}:{}'.format(file, line, column)
                elif line is not None and line >= 0:
                    srcloc = '{}:{}'.format(file, line)
                else:
                    srcloc = file
                s = '{}: {}: {}'.format(srcloc, severity, message)
            else:
                s = message
            a.append(s)
        return a

    def targets(self) -> Set[str]:
        """Return a set of all targets that contain errors."""
        # TODO: Make sure that either target is always defined or that not being defined
        #       is okay for fine-grained incremental checking.
        return set(info.target
                   for info in self.error_info
                   if info.target)

    def render_messages(self, errors: List[ErrorInfo]) -> List[Tuple[Optional[str], int, int,
                                                                     str, str]]:
        """Translate the messages into a sequence of tuples.

        Each tuple is of form (path, line, col, message.  The rendered
        sequence includes information about error contexts. The path
        item may be None. If the line item is negative, the line
        number is not defined for the tuple.
        """
        result = []  # type: List[Tuple[Optional[str], int, int, str, str]]
        # (path, line, column, severity, message)

        prev_import_context = []  # type: List[Tuple[str, int]]
        prev_function_or_member = None  # type: Optional[str]
        prev_type = None  # type: Optional[str]

        for e in errors:
            # Report module import context, if different from previous message.
            if not self.show_error_context:
                pass
            elif e.import_ctx != prev_import_context:
                last = len(e.import_ctx) - 1
                i = last
                while i >= 0:
                    path, line = e.import_ctx[i]
                    fmt = '{}:{}: note: In module imported here'
                    if i < last:
                        fmt = '{}:{}: note: ... from here'
                    if i > 0:
                        fmt += ','
                    else:
                        fmt += ':'
                    # Remove prefix to ignore from path (if present) to
                    # simplify path.
                    path = remove_path_prefix(path, self.ignore_prefix)
                    result.append((None, -1, -1, 'note', fmt.format(path, line)))
                    i -= 1

            file = self.simplify_path(e.file)

            # Report context within a source file.
            if not self.show_error_context:
                pass
            elif (e.function_or_member != prev_function_or_member or
                    e.type != prev_type):
                if e.function_or_member is None:
                    if e.type is None:
                        result.append((file, -1, -1, 'note', 'At top level:'))
                    else:
                        result.append((file, -1, -1, 'note', 'In class "{}":'.format(
                            e.type)))
                else:
                    if e.type is None:
                        result.append((file, -1, -1, 'note',
                                       'In function "{}":'.format(
                                           e.function_or_member)))
                    else:
                        result.append((file, -1, -1, 'note',
                                       'In member "{}" of class "{}":'.format(
                                           e.function_or_member, e.type)))
            elif e.type != prev_type:
                if e.type is None:
                    result.append((file, -1, -1, 'note', 'At top level:'))
                else:
                    result.append((file, -1, -1, 'note',
                                   'In class "{}":'.format(e.type)))

            result.append((file, e.line, e.column, e.severity, e.message))

            prev_import_context = e.import_ctx
            prev_function_or_member = e.function_or_member
            prev_type = e.type

        return result

    def sort_messages(self, errors: List[ErrorInfo]) -> List[ErrorInfo]:
        """Sort an array of error messages locally by line number.

        I.e., sort a run of consecutive messages with the same file
        context by line number, but otherwise retain the general
        ordering of the messages.
        """
        result = []  # type: List[ErrorInfo]
        i = 0
        while i < len(errors):
            i0 = i
            # Find neighbouring errors with the same context and file.
            while (i + 1 < len(errors) and
                    errors[i + 1].import_ctx == errors[i].import_ctx and
                    errors[i + 1].file == errors[i].file):
                i += 1
            i += 1

            # Sort the errors specific to a file according to line number and column.
            a = sorted(errors[i0:i], key=lambda x: (x.line, x.column))
            result.extend(a)
        return result

    def remove_duplicates(self, errors: List[Tuple[Optional[str], int, int, str, str]]
                          ) -> List[Tuple[Optional[str], int, int, str, str]]:
        """Remove duplicates from a sorted error list."""
        res = []  # type: List[Tuple[Optional[str], int, int, str, str]]
        i = 0
        while i < len(errors):
            dup = False
            j = i - 1
            while (j >= 0 and errors[j][0] == errors[i][0] and
                    errors[j][1] == errors[i][1]):
                if (errors[j][3] == errors[i][3] and
                        # Allow duplicate notes in overload conficts reporting
                        not (errors[i][3] == 'note' and
                             errors[i][4].strip() in allowed_duplicates
                             or errors[i][4].strip().startswith('def ')) and
                        errors[j][4] == errors[i][4]):  # ignore column
                    dup = True
                    break
                j -= 1
            if not dup:
                res.append(errors[i])
            i += 1
        return res


class CompileError(Exception):
    """Exception raised when there is a compile error.

    It can be a parse, semantic analysis, type check or other
    compilation-related error.
    """

    messages = None  # type: List[str]
    use_stdout = False

    def __init__(self, messages: List[str], use_stdout: bool = False) -> None:
        super().__init__('\n'.join(messages))
        self.messages = messages
        self.use_stdout = use_stdout


class DecodeError(Exception):
    """Exception raised when a file cannot be decoded due to an unknown encoding type.

    Essentially a wrapper for the LookupError raised by `bytearray.decode`
    """


def remove_path_prefix(path: str, prefix: str) -> str:
    """If path starts with prefix, return copy of path with the prefix removed.
    Otherwise, return path. If path is None, return None.
    """
    if prefix is not None and path.startswith(prefix):
        return path[len(prefix):]
    else:
        return path


def report_internal_error(err: Exception, file: Optional[str], line: int,
                          errors: Errors, options: Options) -> None:
    """Report internal error and exit.

    This optionally starts pdb or shows a traceback.
    """
    # Dump out errors so far, they often provide a clue.
    # But catch unexpected errors rendering them.
    try:
        for msg in errors.messages():
            print(msg)
    except Exception as e:
        print("Failed to dump errors:", repr(e), file=sys.stderr)

    # Compute file:line prefix for official-looking error messages.
    if file:
        if line:
            prefix = '{}:{}: '.format(file, line)
        else:
            prefix = '{}: '.format(file)
    else:
        prefix = ''

    # Print "INTERNAL ERROR" message.
    print('{}error: INTERNAL ERROR --'.format(prefix),
          'please report a bug at https://github.com/python/mypy/issues',
          'version: {}'.format(mypy_version),
          file=sys.stderr)

    # If requested, drop into pdb. This overrides show_tb.
    if options.pdb:
        print('Dropping into pdb', file=sys.stderr)
        import pdb
        pdb.post_mortem(sys.exc_info()[2])

    # If requested, print traceback, else print note explaining how to get one.
    if not options.show_traceback:
        if not options.pdb:
            print('{}: note: please use --show-traceback to print a traceback '
                  'when reporting a bug'.format(prefix),
                  file=sys.stderr)
    else:
        tb = traceback.extract_stack()[:-2]
        tb2 = traceback.extract_tb(sys.exc_info()[2])
        print('Traceback (most recent call last):')
        for s in traceback.format_list(tb + tb2):
            print(s.rstrip('\n'))
        print('{}: {}'.format(type(err).__name__, err))
        print('{}: note: use --pdb to drop into pdb'.format(prefix), file=sys.stderr)

    # Exit.  The caller has nothing more to say.
    raise SystemExit(1)
