"""Support for building extensions using mypyc with distutils or setuptools

The main entry point is mypycify, which produces a list of extension
modules to be passed to setup. A trivial setup.py for a mypyc built
project, then, looks like:

    from distutils.core import setup
    from mypyc.build import mypycify

    setup(name='test_module',
          ext_modules=mypycify(['foo.py']),
    )

See the mypycify docs for additional arguments.

mypycify can integrate with either distutils or setuptools, but needs
to know at import-time whether it is using distutils or setuputils. We
hackily decide based on whether setuptools has been imported already.
"""

import glob
import sys
import os.path
import hashlib
import time
import re

from typing import List, Tuple, Any, Optional, Dict, Union, Set, cast
from typing_extensions import TYPE_CHECKING, NoReturn, Type

from mypy.main import process_options
from mypy.errors import CompileError
from mypy.options import Options
from mypy.build import BuildSource
from mypyc.namegen import exported_name
from mypyc.options import CompilerOptions
from mypyc.errors import Errors
from mypyc.common import shared_lib_name
from mypyc.ops import format_modules

from mypyc import emitmodule

if TYPE_CHECKING:
    from distutils.core import Extension  # noqa

from distutils import sysconfig, ccompiler


def get_extension() -> Type['Extension']:
    # We can work with either setuptools or distutils, and pick setuptools
    # if it has been imported.
    use_setuptools = 'setuptools' in sys.modules

    if not use_setuptools:
        from distutils.core import Extension
    else:
        from setuptools import Extension  # type: ignore  # noqa

    return Extension


def setup_mypycify_vars() -> None:
    """Rewrite a bunch of config vars in pretty dubious ways."""
    # There has to be a better approach to this.

    # The vars can contain ints but we only work with str ones
    vars = cast(Dict[str, str], sysconfig.get_config_vars())
    if sys.platform == 'darwin':
        # Disable building 32-bit binaries, since we generate too much code
        # for a 32-bit Mach-O object. There has to be a better way to do this.
        vars['LDSHARED'] = vars['LDSHARED'].replace('-arch i386', '')
        vars['LDFLAGS'] = vars['LDFLAGS'].replace('-arch i386', '')
        vars['CFLAGS'] = vars['CFLAGS'].replace('-arch i386', '')


def fail(message: str) -> NoReturn:
    # TODO: Is there something else we should do to fail?
    sys.exit(message)


def get_mypy_config(paths: List[str],
                    mypy_options: Optional[List[str]]) -> Tuple[List[BuildSource], Options]:
    """Construct mypy BuildSources and Options from file and options lists"""
    # It is kind of silly to do this but oh well
    mypy_options = mypy_options or []
    mypy_options.append('--')
    mypy_options.extend(paths)

    sources, options = process_options(mypy_options)

    # Override whatever python_version is inferred from the .ini file,
    # and set the python_version to be the currently used version.
    options.python_version = sys.version_info[:2]

    if options.python_version[0] == 2:
        fail('Python 2 not supported')
    if not options.strict_optional:
        fail('Disabling strict optional checking not supported')
    options.show_traceback = True
    # Needed to get types for all AST nodes
    options.export_types = True
    # TODO: Support incremental checking
    options.incremental = False
    options.preserve_asts = True

    for source in sources:
        options.per_module_options.setdefault(source.module, {})['mypyc'] = True

    return sources, options


shim_template = """\
#include <Python.h>

PyMODINIT_FUNC
PyInit_{modname}(void)
{{
    if (!PyImport_ImportModule("{libname}")) return NULL;
    void *init_func = PyCapsule_Import("{libname}.init_{full_modname}", 0);
    if (!init_func) {{
        return NULL;
    }}
    return ((PyObject *(*)(void))init_func)();
}}

// distutils sometimes spuriously tells cl to export CPyInit___init__,
// so provide that so it chills out
PyMODINIT_FUNC PyInit___init__(void) {{ return PyInit_{modname}(); }}
"""


def generate_c_extension_shim(
        full_module_name: str, module_name: str, dir_name: str, group_name: str) -> str:
    """Create a C extension shim with a passthrough PyInit function.

    Arguments:
        full_module_name: the dotted full module name
        module_name: the final component of the module name
        dir_name: the directory to place source code
        group_name: the name of the group
    """
    cname = '%s.c' % exported_name(full_module_name)
    cpath = os.path.join(dir_name, cname)

    write_file(
        cpath,
        shim_template.format(modname=module_name,
                             libname=shared_lib_name(group_name),
                             full_modname=exported_name(full_module_name)))

    return cpath


def group_name(modules: List[str]) -> str:
    """Produce a probably unique name for a group from a list of module names."""
    if len(modules) == 1:
        return exported_name(modules[0])

    h = hashlib.sha1()
    h.update(','.join(modules).encode())
    return h.hexdigest()[:20]


def include_dir() -> str:
    """Find the path of the lib-rt dir that needs to be included"""
    return os.path.join(os.path.abspath(os.path.dirname(__file__)), 'lib-rt')


def generate_c(sources: List[BuildSource],
               options: Options,
               groups: emitmodule.Groups,
               compiler_options: Optional[CompilerOptions] = None
               ) -> Tuple[List[List[Tuple[str, str]]], str]:
    """Drive the actual core compilation step.

    The groups argument describes how modules are assigned to C
    extension modules. See the comments on the Groups type in
    mypyc.emitmodule for details.

    Returns the C source code and (for debugging) the pretty printed IR.
    """
    compiler_options = compiler_options or CompilerOptions()

    # Do the actual work now
    t0 = time.time()
    try:
        result = emitmodule.parse_and_typecheck(sources, options)
    except CompileError as e:
        for line in e.messages:
            print(line)
        fail('Typechecking failure')

    t1 = time.time()
    if compiler_options.verbose:
        print("Parsed and typechecked in {:.3f}s".format(t1 - t0))

    all_module_names = []
    for group_sources, _ in groups:
        all_module_names.extend([source.module for source in group_sources])

    errors = Errors()

    modules, ctext = emitmodule.compile_modules_to_c(result,
                                                     compiler_options=compiler_options,
                                                     errors=errors,
                                                     groups=groups)
    if errors.num_errors:
        errors.flush_errors()
        sys.exit(1)

    t2 = time.time()
    if compiler_options.verbose:
        print("Compiled to C in {:.3f}s".format(t2 - t1))

    return ctext, '\n'.join(format_modules(modules))


def build_using_shared_lib(sources: List[BuildSource],
                           group_name: str,
                           cfiles: List[str],
                           deps: List[str],
                           build_dir: str,
                           extra_compile_args: List[str],
                           ) -> List['Extension']:
    """Produce the list of extension modules when a shared library is needed.

    This creates one shared library extension module that all of the
    others import and then one shim extension module for each
    module in the build, that simply calls an initialization function
    in the shared library.

    The shared library (which lib_name is the name of) is a python
    extension module that exports the real initialization functions in
    Capsules stored in module attributes.
    """
    extensions = [get_extension()(
        shared_lib_name(group_name),
        sources=cfiles,
        include_dirs=[include_dir()],
        depends=deps,
        extra_compile_args=extra_compile_args,
    )]

    for source in sources:
        module_name = source.module.split('.')[-1]
        shim_file = generate_c_extension_shim(source.module, module_name, build_dir, group_name)

        # We include the __init__ in the "module name" we stick in the Extension,
        # since this seems to be needed for it to end up in the right place.
        full_module_name = source.module
        assert source.path
        if os.path.split(source.path)[1] == '__init__.py':
            full_module_name += '.__init__'
        extensions.append(get_extension()(
            full_module_name,
            sources=[shim_file],
            extra_compile_args=extra_compile_args,
        ))

    return extensions


def build_single_module(sources: List[BuildSource],
                        cfiles: List[str],
                        extra_compile_args: List[str],
                        ) -> List['Extension']:
    """Produce the list of extension modules for a standalone extension.

    This contains just one module, since there is no need for a shared module.
    """
    return [get_extension()(
        sources[0].module,
        sources=cfiles,
        include_dirs=[include_dir()],
        extra_compile_args=extra_compile_args,
    )]


def write_file(path: str, contents: str) -> None:
    """Write data into a file.

    If the file already exists and has the same contents we
    want to write, skip writing so as to preserve the mtime
    and avoid triggering recompilation.
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            old_contents = f.read()  # type: Optional[str]
    except IOError:
        old_contents = None
    if old_contents != contents:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(contents)

        # Fudge the mtime forward because otherwise when two builds happen close
        # together (like in a test) setuptools might not realize the source is newer
        # than the new artifact.
        # XXX: This is bad though.
        new_mtime = os.stat(path).st_mtime + 1
        os.utime(path, times=(new_mtime, new_mtime))


def construct_groups(
    sources: List[BuildSource],
    separate: Union[bool, List[Tuple[List[str], Optional[str]]]],
    use_shared_lib: bool,
) -> emitmodule.Groups:
    """Compute Groups given the input source list and separate configs.

    separate is the user-specified configuration for how to assign
    modules to compilation groups (see mypycify docstring for details).

    This takes that and expands it into our internal representation of
    group configuration, documented in mypyc.emitmodule's definition
    of Group.
    """

    if separate is True:
        groups = [
            ([source], None) for source in sources
        ]  # type: emitmodule.Groups
    elif isinstance(separate, list):
        groups = []
        used_sources = set()
        for files, name in separate:
            group_sources = [src for src in sources if src.path in files]
            groups.append((group_sources, name))
            used_sources.update(group_sources)
        unused_sources = [src for src in sources if src not in used_sources]
        if unused_sources:
            groups.extend([([source], None) for source in unused_sources])
    else:
        groups = [(sources, None)]

    # Generate missing names
    for i, (group, name) in enumerate(groups):
        if use_shared_lib and not name:
            name = group_name([source.module for source in group])
        groups[i] = (group, name)

    return groups


def get_header_deps(cfiles: List[Tuple[str, str]]) -> List[str]:
    """Find all the headers used by a group of cfiles.

    We do this by just regexping the source, which is a bit simpler than
    properly plumbing the data through.

    Arguments:
        cfiles: A list of (file name, file contents) pairs.
    """
    headers = set()  # type: Set[str]
    for _, contents in cfiles:
        headers.update(re.findall(r'#include "(.*)"', contents))

    return sorted(headers)


def mypycify(
    paths: List[str],
    mypy_options: Optional[List[str]] = None,
    *,
    verbose: bool = False,
    opt_level: str = '3',
    strip_asserts: bool = False,
    multi_file: bool = False,
    separate: Union[bool, List[Tuple[List[str], Optional[str]]]] = False,
    skip_cgen_input: Optional[Any] = None
) -> List['Extension']:
    """Main entry point to building using mypyc.

    This produces a list of Extension objects that should be passed as the
    ext_modules parameter to setup.

    Arguments:
        paths: A list of file paths to build. It may contain globs.
        mypy_options: Optionally, a list of command line flags to pass to mypy.
                      (This can also contain additional files, for compatibility reasons.)
        verbose: Should mypyc be more verbose. Defaults to false.

        opt_level: The optimization level, as a string. Defaults to '3' (meaning '-O3').
        strip_asserts: Should asserts be stripped from the generated code.

        multi_file: Should each Python module be compiled into its own C source file.
                    This can reduce compile time and memory requirements at the likely
                    cost of runtime performance of compiled code. Defaults to false.
        separate: Should compiled modules be placed in separate extension modules.
                  If False, all modules are placed in a single shared library.
                  If True, every module is placed in its own library.
                  Otherwise separate should be a list of
                  (file name list, optional shared library name) pairs specifying
                  groups of files that should be placed in the same shared library
                  (while all other modules will be placed in its own library).

                  Each group can be compiled independently, which can
                  speed up compilation, but calls between groups can
                  be slower than calls within a group and can't be
                  inlined.
    """

    setup_mypycify_vars()
    compiler_options = CompilerOptions(strip_asserts=strip_asserts,
                                       multi_file=multi_file, verbose=verbose)

    # Create a compiler object so we can make decisions based on what
    # compiler is being used. typeshed is missing some attribues on the
    # compiler object so we give it type Any
    compiler = ccompiler.new_compiler()  # type: Any
    sysconfig.customize_compiler(compiler)

    expanded_paths = []
    for path in paths:
        expanded_paths.extend(glob.glob(path))

    build_dir = 'build'  # TODO: can this be overridden??
    try:
        os.mkdir(build_dir)
    except FileExistsError:
        pass

    sources, options = get_mypy_config(expanded_paths, mypy_options)
    # We generate a shared lib if there are multiple modules or if any
    # of the modules are in package. (Because I didn't want to fuss
    # around with making the single module code handle packages.)
    use_shared_lib = len(sources) > 1 or any('.' in x.module for x in sources)

    groups = construct_groups(sources, separate, use_shared_lib)

    # We let the test harness just pass in the c file contents instead
    # so that it can do a corner-cutting version without full stubs.
    if not skip_cgen_input:
        group_cfiles, ops_text = generate_c(sources, options, groups,
                                            compiler_options=compiler_options)
        # TODO: unique names?
        with open(os.path.join(build_dir, 'ops.txt'), 'w') as f:
            f.write(ops_text)
    else:
        group_cfiles = skip_cgen_input

    # Write out the generated C and collect the files for each group
    group_cfilenames = []  # type: List[Tuple[List[str], List[str]]]
    for cfiles in group_cfiles:
        cfilenames = []
        for cfile, ctext in cfiles:
            cfile = os.path.join(build_dir, cfile)
            write_file(cfile, ctext)
            if os.path.splitext(cfile)[1] == '.c':
                cfilenames.append(cfile)

        deps = [os.path.join(build_dir, dep) for dep in get_header_deps(cfiles)]
        group_cfilenames.append((cfilenames, deps))

    cflags = []  # type: List[str]
    if compiler.compiler_type == 'unix':
        cflags += [
            '-O{}'.format(opt_level), '-Werror', '-Wno-unused-function', '-Wno-unused-label',
            '-Wno-unreachable-code', '-Wno-unused-variable', '-Wno-trigraphs',
            '-Wno-unused-command-line-argument', '-Wno-unknown-warning-option',
        ]
        if 'gcc' in compiler.compiler[0]:
            # This flag is needed for gcc but does not exist on clang.
            cflags += ['-Wno-unused-but-set-variable']
    elif compiler.compiler_type == 'msvc':
        if opt_level == '3':
            opt_level = '2'
        cflags += [
            '/O{}'.format(opt_level),
            '/wd4102',  # unreferenced label
            '/wd4101',  # unreferenced local variable
            '/wd4146',  # negating unsigned int
        ]
        if multi_file:
            # Disable whole program optimization in multi-file mode so
            # that we actually get the compilation speed and memory
            # use wins that multi-file mode is intended for.
            cflags += [
                '/GL-',
                '/wd9025',  # warning about overriding /GL
            ]

    # In multi-file mode, copy the runtime library in.
    # Otherwise it just gets #included to save on compiler invocations
    shared_cfilenames = []
    if multi_file:
        for name in ['CPy.c', 'getargs.c']:
            rt_file = os.path.join(build_dir, name)
            with open(os.path.join(include_dir(), name), encoding='utf-8') as f:
                write_file(rt_file, f.read())
            shared_cfilenames.append(rt_file)

    extensions = []
    for (group_sources, lib_name), (cfilenames, deps) in zip(groups, group_cfilenames):
        if use_shared_lib:
            assert lib_name
            extensions.extend(build_using_shared_lib(
                group_sources, lib_name, cfilenames + shared_cfilenames, deps, build_dir, cflags))
        else:
            extensions.extend(build_single_module(
                group_sources, cfilenames + shared_cfilenames, cflags))

    return extensions
