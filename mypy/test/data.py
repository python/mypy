"""Utilities for processing .test files containing test case descriptions."""

import os.path
import os
import re
from os import remove, rmdir
import shutil

from typing import Callable, List, Tuple

from mypy.myunit import TestCase, SkipTestCaseException


def parse_test_cases(
        path: str,
        perform: Callable[['DataDrivenTestCase'], None],
        base_path: str = '.',
        optional_out: bool = False,
        include_path: str = None) -> List['DataDrivenTestCase']:
    """Parse a file with test case descriptions.

    Return an array of test cases.
    """

    if not include_path:
        include_path = os.path.dirname(path)
    l = open(path, encoding='utf-8').readlines()
    for i in range(len(l)):
        l[i] = l[i].rstrip('\n')
    p = parse_test_data(l, path)
    out = []  # type: List[DataDrivenTestCase]

    # Process the parsed items. Each item has a header of form [id args],
    # optionally followed by lines of text.
    i = 0
    while i < len(p):
        ok = False
        i0 = i
        if p[i].id == 'case':
            i += 1

            files = []  # type: List[Tuple[str, str]] # path and contents
            while i < len(p) and p[i].id not in ['out', 'case']:
                if p[i].id == 'file':
                    # Record an extra file needed for the test case.
                    files.append((os.path.join(base_path, p[i].arg),
                                  '\n'.join(p[i].data)))
                elif p[i].id in ('builtins', 'builtins_py2'):
                    # Use a custom source file for the std module.
                    mpath = os.path.join(os.path.dirname(path), p[i].arg)
                    f = open(mpath)
                    if p[i].id == 'builtins':
                        fnam = 'builtins.py'
                    else:
                        # Python 2
                        fnam = '__builtin__.py'
                    files.append((os.path.join(base_path, fnam), f.read()))
                    f.close()
                else:
                    raise ValueError(
                        'Invalid section header {} in {} at line {}'.format(
                            p[i].id, path, p[i].line))
                i += 1

            tcout = []  # type: List[str]
            if i < len(p) and p[i].id == 'out':
                tcout = p[i].data
                ok = True
                i += 1
            elif optional_out:
                ok = True

            if ok:
                input = expand_includes(p[i0].data, include_path)
                expand_errors(input, tcout, 'main')
                lastline = p[i].line if i < len(p) else p[i - 1].line + 9999
                tc = DataDrivenTestCase(p[i0].arg, input, tcout, path,
                                        p[i0].line, lastline, perform, files)
                out.append(tc)
        if not ok:
            raise ValueError(
                '{}, line {}: Error in test case description'.format(
                    path, p[i0].line))

    return out


class DataDrivenTestCase(TestCase):
    input = None  # type: List[str]
    output = None  # type: List[str]

    file = ''
    line = 0

    perform = None  # type: Callable[['DataDrivenTestCase'], None]

    # (file path, file content) tuples
    files = None  # type: List[Tuple[str, str]]

    clean_up = None  # type: List[Tuple[bool, str]]

    def __init__(self, name, input, output, file, line, lastline,
                 perform, files):
        super().__init__(name)
        self.input = input
        self.output = output
        self.lastline = lastline
        self.file = file
        self.line = line
        self.perform = perform
        self.files = files

    def set_up(self) -> None:
        super().set_up()
        self.clean_up = []
        for path, content in self.files:
            dir = os.path.dirname(path)
            for d in self.add_dirs(dir):
                self.clean_up.append((True, d))
            f = open(path, 'w')
            f.write(content)
            f.close()
            self.clean_up.append((False, path))

    def add_dirs(self, dir: str) -> List[str]:
        """Add all subdirectories required to create dir.

        Return an array of the created directories in the order of creation.
        """
        if dir == '' or os.path.isdir(dir):
            return []
        else:
            dirs = self.add_dirs(os.path.dirname(dir)) + [dir]
            os.mkdir(dir)
            return dirs

    def run(self):
        if self.name.endswith('-skip'):
            raise SkipTestCaseException()
        else:
            self.perform(self)

    def tear_down(self) -> None:
        # First remove files.
        for is_dir, path in reversed(self.clean_up):
            if not is_dir:
                remove(path)
        # Then remove directories.
        for is_dir, path in reversed(self.clean_up):
            if is_dir:
                pycache = os.path.join(path, '__pycache__')
                if os.path.isdir(pycache):
                    shutil.rmtree(pycache)
                try:
                    rmdir(path)
                except OSError as error:
                    print(' ** Error removing directory %s -- contents:' % path)
                    for item in os.listdir(path):
                        print('  ', item)
                    # Most likely, there are some files in the
                    # directory. Use rmtree to nuke the directory, but
                    # fail the test case anyway, since this seems like
                    # a bug in a test case -- we shouldn't leave
                    # garbage lying around. By nuking the directory,
                    # the next test run hopefully passes.
                    path = error.filename
                    # Be defensive -- only call rmtree if we're sure we aren't removing anything
                    # valuable.
                    if path.startswith('tmp/') and os.path.isdir(path):
                        shutil.rmtree(path)
                    raise
        super().tear_down()


class TestItem:
    """Parsed test caseitem.

    An item is of the form
      [id arg]
      .. data ..
    """

    id = ''
    arg = ''

    # Text data, array of 8-bit strings
    data = None  # type: List[str]

    file = ''
    line = 0  # Line number in file

    def __init__(self, id: str, arg: str, data: List[str], file: str,
                 line: int) -> None:
        self.id = id
        self.arg = arg
        self.data = data
        self.file = file
        self.line = line


def parse_test_data(l: List[str], fnam: str) -> List[TestItem]:
    """Parse a list of lines that represent a sequence of test items."""

    ret = []  # type: List[TestItem]
    data = []  # type: List[str]

    id = None  # type: str
    arg = None  # type: str

    i = 0
    i0 = 0
    while i < len(l):
        s = l[i].strip()

        if l[i].startswith('[') and s.endswith(']') and not s.startswith('[['):
            if id:
                data = collapse_line_continuation(data)
                data = strip_list(data)
                ret.append(TestItem(id, arg, strip_list(data), fnam, i0 + 1))
            i0 = i
            id = s[1:-1]
            arg = None
            if ' ' in id:
                arg = id[id.index(' ') + 1:]
                id = id[:id.index(' ')]
            data = []
        elif l[i].startswith('[['):
            data.append(l[i][1:])
        elif not l[i].startswith('--'):
            data.append(l[i])
        elif l[i].startswith('----'):
            data.append(l[i][2:])
        i += 1

    # Process the last item.
    if id:
        data = collapse_line_continuation(data)
        data = strip_list(data)
        ret.append(TestItem(id, arg, data, fnam, i0 + 1))

    return ret


def strip_list(l: List[str]) -> List[str]:
    """Return a stripped copy of l.

    Strip whitespace at the end of all lines, and strip all empty
    lines from the end of the array.
    """

    r = []  # type: List[str]
    for s in l:
        # Strip spaces at end of line
        r.append(re.sub(r'\s+$', '', s))

    while len(r) > 0 and r[-1] == '':
        r.pop()

    return r


def collapse_line_continuation(l: List[str]) -> List[str]:
    r = []  # type: List[str]
    cont = False
    for s in l:
        ss = re.sub(r'\\$', '', s)
        if cont:
            r[-1] += re.sub('^ +', '', ss)
        else:
            r.append(ss)
        cont = s.endswith('\\')
    return r


def expand_includes(a: List[str], base_path: str) -> List[str]:
    """Expand @includes within a list of lines.

    Replace all lies starting with @include with the contents of the
    file name following the prefix. Look for the files in base_path.
    """

    res = []  # type: List[str]
    for s in a:
        if s.startswith('@include '):
            fn = s.split(' ', 1)[1].strip()
            f = open(os.path.join(base_path, fn))
            res.extend(f.readlines())
            f.close()
        else:
            res.append(s)
    return res


def expand_errors(input, output, fnam):
    """Transform comments such as '# E: message' in input.

    The result is lines like 'fnam:line: error: message'.
    """

    for i in range(len(input)):
        m = re.search('# ([EN]): (.*)$', input[i])
        if m:
            severity = 'error' if m.group(1) == 'E' else 'note'
            output.append('{}:{}: {}: {}'.format(fnam, i + 1, severity, m.group(2)))
