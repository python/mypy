"""Test cases for the type checker: exporting inferred types"""

import os.path
import re

import build
from myunit import Suite, run_test
import testconfig
from testdata import parse_test_cases
from testhelpers import assert_string_arrays_equal
from util import short_type
from nodes import NameExpr
from errors import CompileError


class TypeExportSuite(Suite):
    # List of files that contain test case descriptions.
    files = ['typexport-basic.test']
    
    def cases(self):
        c = []
        for f in self.files:
            c += parse_test_cases(os.path.join(testconfig.test_data_prefix, f),
                                  self.run_test, testconfig.test_temp_dir)
        return c
    
    def run_test(self, testcase):
        a = []
        try:
            line = testcase.input[0]
            mask = ''
            if line.startswith('##'):
                mask = '(' + line[2:].strip() + ')$'
            
            src = '\n'.join(testcase.input)
            map = build.build(src, 'main',
                              target=build.TYPE_CHECK,
                              test_builtins=True,
                              alt_lib_path=testconfig.test_temp_dir)[2]
            kk = map.keys()
            keys = []
            for k in kk:
                if k.line is not None and k.line != -1 and map[k]:
                    if (re.match(mask, short_type(k))
                            or (isinstance(k, NameExpr)
                                and re.match(mask, k.name))):
                        keys.append(k)
            for key in sorted(keys,
                              key=lambda n: (n.line, short_type(n),
                                             str(n) + str(map[n]))):
                ts = str(map[key]).replace('*', '') # Remove erased tags
                ts = ts.replace('__main__.', '')
                a.append('{}({}) : {}'.format(short_type(key), key.line, ts))
        except CompileError as e:
            a = e.messages
        assert_string_arrays_equal(
            testcase.output, a,
            'Invalid type checker output ({}, line {})'.format(testcase.file,
                                                               testcase.line))


import sys

if __name__ == '__main__':
    run_test(TypeExportSuite(), sys.argv[1:])
