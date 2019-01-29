import glob
import os.path
import shutil
import sys
import tempfile
import re
from types import ModuleType

from typing import List, Tuple

from mypy.test.helpers import Suite, assert_equal, assert_string_arrays_equal
from mypy.test.data import DataSuite, DataDrivenTestCase
from mypy.errors import CompileError
from mypy.stubgen import (
    generate_stub, generate_stub_for_module, parse_options, walk_packages, Options
)
from mypy.stubgenc import generate_c_type_stub, infer_method_sig, generate_c_function_stub
from mypy.stubutil import (
    parse_signature, parse_all_signatures, build_signature, find_unique_signatures,
    infer_sig_from_docstring, infer_prop_type_from_docstring, FunctionSig, ArgSig,
    infer_arg_sig_from_docstring
)


class StubgenCliParseSuite(Suite):
    def test_walk_packages(self) -> None:
        assert_equal(
            set(walk_packages(["mypy.errors"])),
            {"mypy.errors"})

        assert_equal(
            set(walk_packages(["mypy.errors", "mypy.stubgen"])),
            {"mypy.errors", "mypy.stubgen"})

        all_mypy_packages = set(walk_packages(["mypy"]))
        self.assertTrue(all_mypy_packages.issuperset({
            "mypy",
            "mypy.errors",
            "mypy.stubgen",
            "mypy.test",
            "mypy.test.helpers",
        }))


class StubgenUtilSuite(Suite):
    def test_parse_signature(self) -> None:
        self.assert_parse_signature('func()', ('func', [], []))

    def test_parse_signature_with_args(self) -> None:
        self.assert_parse_signature('func(arg)', ('func', ['arg'], []))
        self.assert_parse_signature('do(arg, arg2)', ('do', ['arg', 'arg2'], []))

    def test_parse_signature_with_optional_args(self) -> None:
        self.assert_parse_signature('func([arg])', ('func', [], ['arg']))
        self.assert_parse_signature('func(arg[, arg2])', ('func', ['arg'], ['arg2']))
        self.assert_parse_signature('func([arg[, arg2]])', ('func', [], ['arg', 'arg2']))

    def test_parse_signature_with_default_arg(self) -> None:
        self.assert_parse_signature('func(arg=None)', ('func', [], ['arg']))
        self.assert_parse_signature('func(arg, arg2=None)', ('func', ['arg'], ['arg2']))
        self.assert_parse_signature('func(arg=1, arg2="")', ('func', [], ['arg', 'arg2']))

    def test_parse_signature_with_qualified_function(self) -> None:
        self.assert_parse_signature('ClassName.func(arg)', ('func', ['arg'], []))

    def test_parse_signature_with_kw_only_arg(self) -> None:
        self.assert_parse_signature('ClassName.func(arg, *, arg2=1)',
                                    ('func', ['arg', '*'], ['arg2']))

    def test_parse_signature_with_star_arg(self) -> None:
        self.assert_parse_signature('ClassName.func(arg, *args)',
                                    ('func', ['arg', '*args'], []))

    def test_parse_signature_with_star_star_arg(self) -> None:
        self.assert_parse_signature('ClassName.func(arg, **args)',
                                    ('func', ['arg', '**args'], []))

    def assert_parse_signature(self, sig: str, result: Tuple[str, List[str], List[str]]) -> None:
        assert_equal(parse_signature(sig), result)

    def test_build_signature(self) -> None:
        assert_equal(build_signature([], []), '()')
        assert_equal(build_signature(['arg'], []), '(arg)')
        assert_equal(build_signature(['arg', 'arg2'], []), '(arg, arg2)')
        assert_equal(build_signature(['arg'], ['arg2']), '(arg, arg2=...)')
        assert_equal(build_signature(['arg'], ['arg2', '**x']), '(arg, arg2=..., **x)')

    def test_parse_all_signatures(self) -> None:
        assert_equal(parse_all_signatures(['random text',
                                           '.. function:: fn(arg',
                                           '.. function:: fn()',
                                           '  .. method:: fn2(arg)']),
                     ([('fn', '()'),
                       ('fn2', '(arg)')], []))

    def test_find_unique_signatures(self) -> None:
        assert_equal(find_unique_signatures(
            [('func', '()'),
             ('func', '()'),
             ('func2', '()'),
             ('func2', '(arg)'),
             ('func3', '(arg, arg2)')]),
            [('func', '()'),
             ('func3', '(arg, arg2)')])

    def test_infer_sig_from_docstring(self) -> None:
        assert_equal(
            infer_sig_from_docstring('\nfunc(x) - y', 'func'),
            [FunctionSig(name='func', args=[ArgSig(name='x')], ret_type='Any')]
        )

        assert_equal(
            infer_sig_from_docstring('\nfunc(x, Y_a=None)', 'func'),
            [FunctionSig(name='func',
                         args=[ArgSig(name='x'), ArgSig(name='Y_a', default=True)],
                         ret_type='Any')]
        )
        assert_equal(
            infer_sig_from_docstring('\nfunc(x, Y_a=3)', 'func'),
            [FunctionSig(name='func',
                         args=[ArgSig(name='x'), ArgSig(name='Y_a', default=True)],
                         ret_type='Any')]
        )

        assert_equal(
            infer_sig_from_docstring('\nfunc(x, Y_a=[1, 2, 3])', 'func'),
            [FunctionSig(name='func',
                         args=[ArgSig(name='x'), ArgSig(name='Y_a', default=True)],
                         ret_type='Any')]
        )

        assert_equal(infer_sig_from_docstring('\nafunc(x) - y', 'func'), [])
        assert_equal(infer_sig_from_docstring('\nfunc(x, y', 'func'), [])
        assert_equal(
            infer_sig_from_docstring('\nfunc(x=z(y))', 'func'),
            [FunctionSig(name='func', args=[ArgSig(name='x', default=True)], ret_type='Any')]
        )
        assert_equal(infer_sig_from_docstring('\nfunc x', 'func'), [])
        # try to infer signature from type annotation
        assert_equal(
            infer_sig_from_docstring('\nfunc(x: int)', 'func'),
            [FunctionSig(name='func', args=[ArgSig(name='x', type='int')], ret_type='Any')]
        )
        assert_equal(
            infer_sig_from_docstring('\nfunc(x: int=3)', 'func'),
            [FunctionSig(name='func',
                         args=[ArgSig(name='x', type='int', default=True)],
                         ret_type='Any')]
        )
        assert_equal(
            infer_sig_from_docstring('\nfunc(x: int=3) -> int', 'func'),
            [FunctionSig(name='func',
                         args=[ArgSig(name='x', type='int', default=True)],
                         ret_type='int')]
        )
        assert_equal(
            infer_sig_from_docstring('\nfunc(x: int=3) -> int   \n', 'func'),
            [FunctionSig(name='func',
                         args=[ArgSig(name='x', type='int', default=True)],
                         ret_type='int')]
        )
        assert_equal(
            infer_sig_from_docstring('\nfunc(x: Tuple[int, str]) -> str', 'func'),
            [FunctionSig(name='func',
                         args=[ArgSig(name='x', type='Tuple[int,str]')],
                         ret_type='str')]
        )
        assert_equal(
            infer_sig_from_docstring('\nfunc(x: Tuple[int, Tuple[str, int], str], y: int) -> str',
                                     'func'),
            [FunctionSig(name='func',
                         args=[ArgSig(name='x', type='Tuple[int,Tuple[str,int],str]'),
                               ArgSig(name='y', type='int')],
                         ret_type='str')]
        )
        assert_equal(
            infer_sig_from_docstring('\nfunc(x: foo.bar)', 'func'),
            [FunctionSig(name='func',
                         args=[ArgSig(name='x', type='foo.bar')],
                         ret_type='Any')]
        )

        assert_equal(
            infer_sig_from_docstring('\nfunc(x: list=[1,2,[3,4]])', 'func'),
            [FunctionSig(name='func',
                         args=[ArgSig(name='x', type='list', default=True)],
                         ret_type='Any')]
        )

        assert_equal(
            infer_sig_from_docstring('\nfunc(x: str="nasty[")', 'func'),
            [FunctionSig(name='func',
                         args=[ArgSig(name='x', type='str', default=True)],
                         ret_type='Any')]
        )

        assert_equal(
            infer_sig_from_docstring('\nfunc[(x: foo.bar, invalid]', 'func'),
            []
        )

    def test_infer_arg_sig_from_docstring(self) -> None:
        assert_equal(
            infer_arg_sig_from_docstring("(*args, **kwargs)"),
            [ArgSig(name='*args'), ArgSig(name='**kwargs')]
        )

        assert_equal(
            infer_arg_sig_from_docstring(
                "(x: Tuple[int, Tuple[str, int], str]=(1, ('a', 2), 'y'), y: int=4)"
            ),
            [ArgSig(name='x', type='Tuple[int,Tuple[str,int],str]', default=True),
             ArgSig(name='y', type='int', default=True)]
        )

    def test_infer_prop_type_from_docstring(self) -> None:
        assert_equal(infer_prop_type_from_docstring('str: A string.'), 'str')
        assert_equal(infer_prop_type_from_docstring('Optional[int]: An int.'), 'Optional[int]')
        assert_equal(infer_prop_type_from_docstring('Tuple[int, int]: A tuple.'),
                     'Tuple[int, int]')
        assert_equal(infer_prop_type_from_docstring('\nstr: A string.'), None)


class StubgenPythonSuite(DataSuite):
    required_out_section = True
    base_path = '.'
    files = ['stubgen.test']

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        test_stubgen(testcase)


def parse_flags(program_text: str) -> Options:
    flags = re.search('# flags: (.*)$', program_text, flags=re.MULTILINE)
    if flags:
        flag_list = flags.group(1).split()
    else:
        flag_list = []
    return parse_options(flag_list + ['dummy.py'])


def test_stubgen(testcase: DataDrivenTestCase) -> None:
    if 'stubgen-test-path' not in sys.path:
        sys.path.insert(0, 'stubgen-test-path')
    os.mkdir('stubgen-test-path')
    source = '\n'.join(testcase.input)
    options = parse_flags(source)
    handle = tempfile.NamedTemporaryFile(prefix='prog_', suffix='.py', dir='stubgen-test-path',
                                         delete=False)
    assert os.path.isabs(handle.name)
    path = os.path.basename(handle.name)
    name = path[:-3]
    path = os.path.join('stubgen-test-path', path)
    out_dir = '_out'
    os.mkdir(out_dir)
    try:
        handle.write(bytes(source, 'ascii'))
        handle.close()
        # Without this we may sometimes be unable to import the module below, as importlib
        # caches os.listdir() results in Python 3.3+ (Guido explained this to me).
        reset_importlib_cache('stubgen-test-path')
        try:
            if testcase.name.endswith('_import'):
                generate_stub_for_module(name, out_dir, quiet=True,
                                         no_import=options.no_import,
                                         include_private=options.include_private)
            else:
                generate_stub(path, out_dir, include_private=options.include_private)
            a = load_output(out_dir)
        except CompileError as e:
            a = e.messages
        assert_string_arrays_equal(testcase.output, a,
                                   'Invalid output ({}, line {})'.format(
                                       testcase.file, testcase.line))
    finally:
        handle.close()
        os.unlink(handle.name)
        shutil.rmtree(out_dir)


def reset_importlib_cache(entry: str) -> None:
    # importlib.invalidate_caches() is insufficient, since it doesn't
    # clear cache entries that indicate that a directory on the path
    # does not exist, which can cause failures.  Just directly clear
    # the sys.path_importer_cache entry ourselves.  Other possible
    # workarounds include always using different paths in the sys.path
    # (perhaps by using the full path name) or removing the entry from
    # sys.path after each run.
    if entry in sys.path_importer_cache:
        del sys.path_importer_cache[entry]


def load_output(dirname: str) -> List[str]:
    result = []  # type: List[str]
    entries = glob.glob('%s/*' % dirname)
    assert entries, 'No files generated'
    if len(entries) == 1:
        add_file(entries[0], result)
    else:
        for entry in entries:
            result.append('## %s ##' % entry)
            add_file(entry, result)
    return result


def add_file(path: str, result: List[str]) -> None:
    with open(path, encoding='utf8') as file:
        result.extend(file.read().splitlines())


class StubgencSuite(Suite):
    def test_infer_hash_sig(self) -> None:
        assert_equal(infer_method_sig('__hash__'), [])

    def test_infer_getitem_sig(self) -> None:
        assert_equal(infer_method_sig('__getitem__'), [ArgSig(name='index')])

    def test_infer_setitem_sig(self) -> None:
        assert_equal(infer_method_sig('__setitem__'),
                     [ArgSig(name='index'), ArgSig(name='object')])

    def test_infer_binary_op_sig(self) -> None:
        for op in ('eq', 'ne', 'lt', 'le', 'gt', 'ge',
                   'add', 'radd', 'sub', 'rsub', 'mul', 'rmul'):
            assert_equal(infer_method_sig('__%s__' % op), [ArgSig(name='other')])

    def test_infer_unary_op_sig(self) -> None:
        for op in ('neg', 'pos'):
            assert_equal(infer_method_sig('__%s__' % op), [])

    def test_generate_c_type_stub_no_crash_for_object(self) -> None:
        output = []  # type: List[str]
        mod = ModuleType('module', '')  # any module is fine
        imports = []  # type: List[str]
        generate_c_type_stub(mod, 'alias', object, output, imports)
        assert_equal(imports, [])
        assert_equal(output[0], 'class alias:')

    def test_generate_c_type_stub_variable_type_annotation(self) -> None:
        # This class mimics the stubgen unit test 'testClassVariable'
        class TestClassVariableCls:
            x = 1

        output = []  # type: List[str]
        imports = []  # type: List[str]
        mod = ModuleType('module', '')  # any module is fine
        generate_c_type_stub(mod, 'C', TestClassVariableCls, output, imports)
        assert_equal(imports, [])
        assert_equal(output, ['class C:', '    x: Any = ...'])

    def test_generate_c_type_inheritance(self) -> None:
        class TestClass(KeyError):
            pass

        output = []  # type: List[str]
        imports = []  # type: List[str]
        mod = ModuleType('module, ')
        generate_c_type_stub(mod, 'C', TestClass, output, imports)
        assert_equal(output, ['class C(KeyError): ...', ])
        assert_equal(imports, [])

    def test_generate_c_type_inheritance_same_module(self) -> None:
        class TestBaseClass:
            pass

        class TestClass(TestBaseClass):
            pass

        output = []  # type: List[str]
        imports = []  # type: List[str]
        mod = ModuleType(TestBaseClass.__module__, '')
        generate_c_type_stub(mod, 'C', TestClass, output, imports)
        assert_equal(output, ['class C(TestBaseClass): ...', ])
        assert_equal(imports, [])

    def test_generate_c_type_inheritance_other_module(self) -> None:
        import argparse

        class TestClass(argparse.Action):
            pass

        output = []  # type: List[str]
        imports = []  # type: List[str]
        mod = ModuleType('module', '')
        generate_c_type_stub(mod, 'C', TestClass, output, imports)
        assert_equal(output, ['class C(argparse.Action): ...', ])
        assert_equal(imports, ['import argparse'])

    def test_generate_c_type_with_docstring(self) -> None:
        class TestClass:
            def test(self, arg0: str) -> None:
                """
                test(self: TestClass, arg0: int)
                """
                pass
        output = []  # type: List[str]
        imports = []  # type: List[str]
        mod = ModuleType(TestClass.__module__, '')
        generate_c_function_stub(mod, 'test', TestClass.test, output, imports,
                                 self_var='self', class_name='TestClass')
        assert_equal(output, ['def test(self, arg0: int) -> Any: ...'])
        assert_equal(imports, [])

    def test_generate_c_function_other_module_arg(self) -> None:
        """Test that if argument references type from other module, module will be imported."""
        # Provide different type in python spec than in docstring to make sure, that docstring
        # information is used.
        def test(arg0: str) -> None:
            """
            test(arg0: argparse.Action)
            """
            pass
        output = []  # type: List[str]
        imports = []  # type: List[str]
        mod = ModuleType(self.__module__, '')
        generate_c_function_stub(mod, 'test', test, output, imports)
        assert_equal(output, ['def test(arg0: argparse.Action) -> Any: ...'])
        assert_equal(imports, ['import argparse'])

    def test_generate_c_function_same_module_arg(self) -> None:
        """
        Test that if argument references type from same module but using full path, no module will
        be imported, and type specification will be striped to local reference.
        """
        # provide different type in python spec than in docstring to make sure, that docstring
        # information is used
        def test(arg0: str) -> None:
            """
            test(arg0: argparse.Action)
            """
            pass
        output = []  # type: List[str]
        imports = []  # type: List[str]
        mod = ModuleType('argparse', '')
        generate_c_function_stub(mod, 'test', test, output, imports)
        assert_equal(output, ['def test(arg0: Action) -> Any: ...'])
        assert_equal(imports, [])

    def test_generate_c_function_other_module_ret(self) -> None:
        """
        Test that if return type references type from other module, module will be imported.
        """
        def test(arg0: str) -> None:
            """
            test(arg0: str) -> argparse.Action
            """
            pass
        output = []  # type: List[str]
        imports = []  # type: List[str]
        mod = ModuleType(self.__module__, '')
        generate_c_function_stub(mod, 'test', test, output, imports)
        assert_equal(output, ['def test(arg0: str) -> argparse.Action: ...'])
        assert_equal(imports, ['import argparse'])

    def test_generate_c_function_same_module_ret(self) -> None:
        """
        Test that if return type references type from same module but using full path, no module
        will be imported, and type specification will be striped to local reference.
        """
        def test(arg0: str) -> None:
            """
            test(arg0: str) -> argparse.Action
            """
            pass
        output = []  # type: List[str]
        imports = []  # type: List[str]
        mod = ModuleType('argparse', '')
        generate_c_function_stub(mod, 'test', test, output, imports)
        assert_equal(output, ['def test(arg0: str) -> Action: ...'])
        assert_equal(imports, [])

    def test_generate_c_type_with_overload_pybind11(self) -> None:
        class TestClass:
            def __init__(self, arg0: str) -> None:
                """
                __init__(*args, **kwargs)
                Overloaded function.

                1. __init__(self: TestClass, arg0: str) -> None

                2. __init__(self: TestClass, arg0: str, arg1: str) -> None
                """
                pass
        output = []  # type: List[str]
        imports = []  # type: List[str]
        mod = ModuleType(TestClass.__module__, '')
        generate_c_function_stub(mod, '__init__', TestClass.__init__, output, imports,
                                 self_var='self', class_name='TestClass')
        assert_equal(output, [
            '@overload',
            'def __init__(self, arg0: str) -> None: ...',
            '@overload',
            'def __init__(self, arg0: str, arg1: str) -> None: ...',
            '@overload',
            'def __init__(*args, **kwargs) -> Any: ...',
        ])
        assert_equal(set(imports), {
            'from typing import overload'
        })


class ArgSigSuite(Suite):
    def test_repr(self) -> None:
        assert_equal(repr(ArgSig(name='asd"dsa')),
                     "ArgSig(name='asd\"dsa', type=None, default=False)")
        assert_equal(repr(ArgSig(name="asd'dsa")),
                     'ArgSig(name="asd\'dsa", type=None, default=False)')
        assert_equal(repr(ArgSig("func", 'str')),
                     "ArgSig(name='func', type='str', default=False)")
        assert_equal(repr(ArgSig("func", 'str', default=True)),
                     "ArgSig(name='func', type='str', default=True)")
