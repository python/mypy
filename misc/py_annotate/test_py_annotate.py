import os
import re
import difflib
import logging

import py_annotate

PY, PYI = 'py', 'pyi'


def main():
    logging.basicConfig(level=logging.CRITICAL)  # hide fixer's messages
    tr = TestRunner('testdata')
    tr.run()


class Args(object):
    def __init__(self, use_pyi=False, pep484=False):
        self.use_pyi = use_pyi
        self.pep484 = pep484

    def __str__(self):
        pairs = sorted(list(vars(self).iteritems()))
        return ', '.join(['%s=%s' % pair for pair in pairs])

    @property
    def expected_ext(self):
        """Extension of expected filename."""
        exts = {
            (1, 1): 'pep484',
            (1, 0): 'comment',
            (0, 0): 'nopyi'
        }
        key = int(self.use_pyi), int(self.pep484)
        return exts[key] + '.py'

class TestRunner(object):
    file_pat = re.compile(r'(?P<filename>(?P<base>.+?)\.(?P<ext>.*))$')
    overwrite_expected = 0
    print_diff = 0
    logger = logging.getLogger("TestRunner")
    logger.setLevel(logging.DEBUG)

    def __init__(self, test_data_dir):
        self.results = None
        self.test_data_dir = test_data_dir

        # py_annotate args
        self.args = None

    def run(self):
        files = os.listdir(self.test_data_dir)

        matches = [m for m in map(self.file_pat.match, files) if m]
        files_by_base = {}
        for m in matches:
            base, ext, filename = m.group('base'), m.group('ext'), m.group('filename')
            if base not in files_by_base:
                files_by_base[base] = {}
            files_by_base[base][ext] = filename

        self.results = {True: 0, False: 0}

        # "use_pyi" doesn't mean anything to py_annotate, only to us
        args_list = [
            Args(use_pyi=1, pep484=1),
            Args(use_pyi=1, pep484=0),
            Args(use_pyi=0, pep484=0),
            ]

        for args in args_list:
            args.futures = []

            self.args = args
            self.logger.info("setting args: %s", args)
            for base, files_by_ext in sorted(files_by_base.iteritems()):
                if PY not in files_by_ext:
                    continue

                self.test_option_permutations(base, files_by_ext)

        self.logger.info("Test results: %s", self.results)

    def read_file(self, filename):
        filename = os.path.join(self.test_data_dir, filename)
        with open(filename) as f:
            return f.read()

    def test_option_permutations(self, base, files_by_ext):
        """Run tests over various option permutations"""
        expected_ext = self.args.expected_ext

        if not self.overwrite_expected and expected_ext not in files_by_ext:
            return

        if self.args.use_pyi and PYI not in files_by_ext:
            return

        ret = self._dotest(base, files_by_ext, expected_ext)

        self.logger.info("%s %s", "PASS" if ret else "FAIL", base)
        self.results[ret] += 1

    def _dotest(self, base, files_by_ext, expected_ext):
        py_input = self.read_file(files_by_ext[PY])

        pyi_src = None
        if self.args.use_pyi:
            pyi_src = self.read_file(files_by_ext[PYI])

        try:
            output = py_annotate.annotate_string(self.args, py_input, pyi_src)
        except Exception as e:
            self.logger.info("Failed with exception %s", repr(e))
            return False

        if self.print_diff:
            self.logger.info("Diff\n%s", _get_diff(py_input, output))

        if self.overwrite_expected:
            # write output to file, for future runs
            filename = os.path.join(self.test_data_dir, base + '.' + expected_ext)

            with open(filename, 'w') as f:
                f.write(output)
        else:
            expected = self.read_file(files_by_ext[expected_ext])

            if expected != output:
                self.logger.info("Failed. Diff:\n%s",
                                 _get_diff(expected, output))
                return False
        return True


def _get_diff(a, b):
    a, b = a.split('\n'), b.split('\n')

    diff = difflib.Differ().compare(a, b)
    return '\n'.join(diff)


if __name__ == '__main__':
    main()
