import os.path
import os
import re
from os import remove, rmdir
from unittest import TestCase, SkipTestCaseException


# Parse a file with test case descriptions. Return an array of test cases.
list<DataDrivenTestCase> parse_test_cases(
            str path,
            func<DataDrivenTestCase, void> perform,
            str base_path='.',
            bool optional_out=False,
            str include_path=None):
    if not include_path:
        include_path = os.path.dirname(path)
    l = open(path).readlines()
    for i in range(len(l)):
        l[i] = l[i].rstrip('\n')
    p = parse_test_data(l, path)
    list<DataDrivenTestCase> out = []
    
    # Process the parsed items. Each item has a header of form [id args],
    # optionally followed by lines of text.
    i = 0
    while i < len(p):
        ok = False
        i0 = i
        if p[i].id == 'case':
            i += 1
            
            list<tuple<str, str>> files = [] # path and contents
            while i < len(p) and p[i].id not in ['out', 'case']:
                if p[i].id == 'file':
                    # Record an extra file needed for the test case.
                    files.append((os.path.join(base_path, p[i].arg),
                                  '\n'.join(p[i].data)))
                elif p[i].id == 'builtins':
                    # Use a custom source file for the std module.
                    mpath = os.path.join(os.path.dirname(path), p[i].arg)
                    f = open(mpath)
                    files.append((os.path.join(base_path, 'builtins.py'),
                                  f.read()))
                    f.close()
                else:
                    raise ValueError(
                        'Invalid section header {} in {} at line {}'.format(
                            p[i].id, path, p[i].line))
                i += 1
            
            list<str> tcout = []
            if i < len(p) and p[i].id == 'out':
                tcout = p[i].data
                ok = True
                i += 1
            elif optional_out:
                ok = True
            
            if ok:
                input = expand_includes(p[i0].data, include_path)
                expand_errors(input, tcout, 'main')
                tc = DataDrivenTestCase(p[i0].arg, input, tcout, path,
                                        p[i0].line, perform, files)
                out.append(tc)
        if not ok:
            raise ValueError(
                '{}, line {}: Error in test case description'.format(
                    path, p[i0].line))
    
    return out


class DataDrivenTestCase(TestCase):
    list<str> input
    list<str> output
    str file
    int line
    func<DataDrivenTestCase, void> perform
    list<tuple<str, str>> files
    list<tuple<bool, str>> clean_up
    
    def __init__(self, name, input, output, file, line, perform, files):
        super().__init__(name)
        self.input = input
        self.output = output
        self.file = file
        self.line = line
        self.perform = perform
        self.files = files
    
    void set_up(self):
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
    
    # Add all subdirectories required to create dir. Return an array of the
    # created directories in the order of creation.
    list<str> add_dirs(self, str dir):
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
    
    void tear_down(self):
        for is_dir, path in reversed(self.clean_up):
            if is_dir:
                rmdir(path)
            else:
                remove(path)
        super().tear_down()


# Parsed item of the form
#   [id arg]
#   .. data ..
class TestItem:
    str id
    str arg
    list<str> data # Text data, array of 8-bit strings
    str file
    int line # Line number in file
    
    void __init__(self, str id, str arg, list<str> data, str file, int line):
        self.id = id
        self.arg = arg
        self.data = data
        self.file = file
        self.line = line


# Parse a list of lines that represent a sequence of test items.
list<TestItem> parse_test_data(list<str> l, str fnam):
    list<TestItem> ret = []
    
    str id = None
    str arg = None
    list<str> data = []
    
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
        ret.append(TestItem(id, arg, data, fnam, i + 1))
    
    return ret


# Return a stripped copy of l. Strip whitespace at the end of all lines, and
# strip all empty lines from the end of the array.
list<str> strip_list(list<str> l):
    list<str> r = []
    for s in l:
        # Strip spaces at end of line
        r.append(re.sub(r'\s+$', '', s))
    
    while len(r) > 0 and r[-1] == '':
        r.pop()
    
    return r


list<str> collapse_line_continuation(list<str> l):
    list<str> r = []
    cont = False
    for s in l:
        ss = re.sub(r'\\$', '', s)
        if cont:
            r[-1] += re.sub('^ +', '', ss)
        else:
            r.append(ss)
        cont = s.endswith('\\')
    return r


# Replace all lies starting with @include with the contents of the file name
# following the prefix. Look for the files in basePath.
list<str> expand_includes(list<str> a, str base_path):
    list<str> res = []
    for s in a:
        if s.startswith('@include '):
            fn = s.split(' ', 1)[1].strip()
            f = open(os.path.join(base_path, fn))
            res.extend(f.readlines())
            f.close()
        else:
            res.append(s)
    return res


# Transform comments such as "# E: message" in input to to lines like
# "fnam, line N: message" in the output.
def expand_errors(input, output, fnam):
    for i in range(len(input)):
        m = re.search('# E: (.*)$', input[i])
        if m:
            output.append('{}, line {}: {}'.format(fnam, i + 1, m.group(1)))
