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
    generate_stubs, parse_options, walk_packages, Options, collect_build_targets,
    mypy_options
)
from mypy.stubgenc import generate_c_type_stub, infer_method_sig, generate_c_function_stub
from mypy.stubdoc import (
    parse_signature, parse_all_signatures, build_signature, find_unique_signatures,
    infer_sig_from_docstring, infer_prop_type_from_docstring, FunctionSig, ArgSig,
    infer_arg_sig_from_docstring
)


class StubgenCmdLineSuite(Suite):
    def test_files_found(self) -> None:
        current = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            try:
                os.chdir(tmp)
                os.mkdir('subdir')
                self.make_file('subdir', 'a.py')
                self.make_file('subdir', 'b.py')
                os.mkdir(os.path.join('subdir', 'pack'))
                self.make_file('subdir', 'pack', '__init__.py')
                opts = parse_options(['subdir'])
                py_mods, c_mods = collect_build_targets(opts, mypy_options(opts))
                assert_equal(c_mods, [])
                files = {mod.path for mod in py_mods}
                assert_equal(files, {os.path.join('subdir', 'pack', '__init__.py'),
                                     os.path.join('subdir', 'a.py'),
                                     os.path.join('subdir', 'b.py')})
            finally:
                os.chdir(current)

    def test_packages_found(self) -> None:
        current = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            try:
                os.chdir(tmp)
                os.mkdir('pack')
                self.make_file('pack', '__init__.py', content='from . import a, b')
                self.make_file('pack', 'a.py')
                self.make_file('pack', 'b.py')
                opts = parse_options(['-p', 'pack'])
                py_mods, c_mods = collect_build_targets(opts, mypy_options(opts))
                assert_equal(c_mods, [])
                files = {os.path.relpath(mod.path or 'FAIL') for mod in py_mods}
                assert_equal(files, {os.path.join('pack', '__init__.py'),
                                     os.path.join('pack', 'a.py'),
                                     os.path.join('pack', 'b.py')})
            finally:
                os.chdir(current)

    def make_file(self, *path: str, content: str = '') -> None:
        file = os.path.join(*path)
        with open(file, 'w') as f:
            f.write(content)


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
        assert_equal(infer_sig_from_docstring('\nfunc(x) - y', 'func'),
                     [FunctionSig(name='func', args=[ArgSig(name='x')], ret_type='Any')])

        assert_equal(infer_sig_from_docstring('\nfunc(x, Y_a=None)', 'func'),
                     [FunctionSig(name='func',
                                  args=[ArgSig(name='x'), ArgSig(name='Y_a', default=True)],
                                  ret_type='Any')])

        assert_equal(infer_sig_from_docstring('\nfunc(x, Y_a=3)', 'func'),
                     [FunctionSig(name='func',
                                  args=[ArgSig(name='x'), ArgSig(name='Y_a', default=True)],
                                  ret_type='Any')])

        assert_equal(infer_sig_from_docstring('\nfunc(x, Y_a=[1, 2, 3])', 'func'),
                     [FunctionSig(name='func',
                                  args=[ArgSig(name='x'), ArgSig(name='Y_a', default=True)],
                                  ret_type='Any')])

        assert_equal(infer_sig_from_docstring('\nafunc(x) - y', 'func'), [])
        assert_equal(infer_sig_from_docstring('\nfunc(x, y', 'func'), [])
        assert_equal(infer_sig_from_docstring('\nfunc(x=z(y))', 'func'),
                     [FunctionSig(name='func', args=[ArgSig(name='x', default=True)],
                                  ret_type='Any')])

        assert_equal(infer_sig_from_docstring('\nfunc x', 'func'), [])
        # Try to infer signature from type annotation.
        assert_equal(infer_sig_from_docstring('\nfunc(x: int)', 'func'),
                     [FunctionSig(name='func', args=[ArgSig(name='x', type='int')],
                                  ret_type='Any')])
        assert_equal(infer_sig_from_docstring('\nfunc(x: int=3)', 'func'),
                     [FunctionSig(name='func', args=[ArgSig(name='x', type='int', default=True)],
                                  ret_type='Any')])

        assert_equal(infer_sig_from_docstring('\nfunc(x: int=3) -> int', 'func'),
                     [FunctionSig(name='func', args=[ArgSig(name='x', type='int', default=True)],
                                  ret_type='int')])

        assert_equal(infer_sig_from_docstring('\nfunc(x: int=3) -> int   \n', 'func'),
                     [FunctionSig(name='func', args=[ArgSig(name='x', type='int', default=True)],
                                  ret_type='int')])

        assert_equal(infer_sig_from_docstring('\nfunc(x: Tuple[int, str]) -> str', 'func'),
                     [FunctionSig(name='func', args=[ArgSig(name='x', type='Tuple[int,str]')],
                                  ret_type='str')])

        assert_equal(
            infer_sig_from_docstring('\nfunc(x: Tuple[int, Tuple[str, int], str], y: int) -> str',
                                     'func'),
            [FunctionSig(name='func',
                         args=[ArgSig(name='x', type='Tuple[int,Tuple[str,int],str]'),
                               ArgSig(name='y', type='int')],
                         ret_type='str')])

        assert_equal(infer_sig_from_docstring('\nfunc(x: foo.bar)', 'func'),
                     [FunctionSig(name='func', args=[ArgSig(name='x', type='foo.bar')],
                                  ret_type='Any')])

        assert_equal(infer_sig_from_docstring('\nfunc(x: list=[1,2,[3,4]])', 'func'),
                     [FunctionSig(name='func', args=[ArgSig(name='x', type='list', default=True)],
                                  ret_type='Any')])

        assert_equal(infer_sig_from_docstring('\nfunc(x: str="nasty[")', 'func'),
                     [FunctionSig(name='func', args=[ArgSig(name='x', type='str', default=True)],
                                  ret_type='Any')])

        assert_equal(infer_sig_from_docstring('\nfunc[(x: foo.bar, invalid]', 'func'), [])

    def test_infer_arg_sig_from_docstring(self) -> None:
        assert_equal(infer_arg_sig_from_docstring("(*args, **kwargs)"),
                     [ArgSig(name='*args'), ArgSig(name='**kwargs')])

        assert_equal(
            infer_arg_sig_from_docstring(
                "(x: Tuple[int, Tuple[str, int], str]=(1, ('a', 2), 'y'), y: int=4)"),
            [ArgSig(name='x', type='Tuple[int,Tuple[str,int],str]', default=True),
             ArgSig(name='y', type='int', default=True)])

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
        extra = []
        mods = []
        source = '\n'.join(testcase.input)
        for file, content in testcase.files + [('./main.py', source)]:
            mod = os.path.basename(file)[:-3]
            mods.append(mod)
            extra.extend(['-m', mod])
            with open(file, 'w') as f:
                f.write(content)

        options = self.parse_flags(source, extra)
        out_dir = 'out'
        try:
            try:
                if not testcase.name.endswith('_import'):
                    options.no_import = True
                if not testcase.name.endswith('_semanal'):
                    options.parse_only = True
                generate_stubs(options, quiet=True, add_header=False)
                a = []  # type: List[str]
                self.add_file(os.path.join(out_dir, 'main.pyi'), a)
            except CompileError as e:
                a = e.messages
            assert_string_arrays_equal(testcase.output, a,
                                       'Invalid output ({}, line {})'.format(
                                           testcase.file, testcase.line))
        finally:
            for mod in mods:
                if mod in sys.modules:
                    del sys.modules[mod]
            shutil.rmtree(out_dir)

    def parse_flags(self, program_text: str, extra: List[str]) -> Options:
        flags = re.search('# flags: (.*)$', program_text, flags=re.MULTILINE)
        if flags:
            flag_list = flags.group(1).split()
        else:
            flag_list = []
        return parse_options(flag_list + extra)

    def add_file(self, path: str, result: List[str]) -> None:
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
        """Test that if argument references type from same module but using full path, no module
        will be imported, and type specification will be striped to local reference.
        """
        # Provide different type in python spec than in docstring to make sure, that docstring
        # information is used.
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
        """Test that if return type references type from other module, module will be imported."""
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
        """Test that if return type references type from same module but using full path,
        no module will be imported, and type specification will be striped to local reference.
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
            'def __init__(*args, **kwargs) -> Any: ...'])
        assert_equal(set(imports), {'from typing import overload'})


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
