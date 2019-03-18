from collections import OrderedDict
import re
import pprint
import sys

from typing import Dict, List, Mapping, Optional, Pattern, Set, Tuple
MYPY = False
if MYPY:
    from typing_extensions import Final

from mypy import defaults
from mypy.util import get_class_descriptors, replace_object_state


class BuildType:
    STANDARD = 0  # type: Final[int]
    MODULE = 1  # type: Final[int]
    PROGRAM_TEXT = 2  # type: Final[int]


PER_MODULE_OPTIONS = {
    # Please keep this list sorted
    "allow_untyped_globals",
    "allow_redefinition",
    "strict_equality",
    "always_false",
    "always_true",
    "check_untyped_defs",
    "debug_cache",
    "disallow_any_decorated",
    "disallow_any_explicit",
    "disallow_any_expr",
    "disallow_any_generics",
    "disallow_any_unimported",
    "disallow_incomplete_defs",
    "disallow_subclassing_any",
    "disallow_untyped_calls",
    "disallow_untyped_decorators",
    "disallow_untyped_defs",
    "follow_imports",
    "follow_imports_for_stubs",
    "ignore_errors",
    "ignore_missing_imports",
    "local_partial_types",
    "mypyc",
    "no_implicit_optional",
    "no_implicit_reexport",
    "show_none_errors",
    "strict_optional",
    "strict_optional_whitelist",
    "warn_no_return",
    "warn_return_any",
    "warn_unused_ignores",
}  # type: Final

OPTIONS_AFFECTING_CACHE = ((PER_MODULE_OPTIONS |
                            {"platform", "bazel", "plugins", "new_semantic_analyzer"})
                           - {"debug_cache"})  # type: Final


class Options:
    """Options collected from flags."""

    def __init__(self) -> None:
        # Cache for clone_for_module()
        self.per_module_cache = None  # type: Optional[Dict[str, Options]]

        # -- build options --
        self.build_type = BuildType.STANDARD
        self.python_version = sys.version_info[:2]  # type: Tuple[int, int]
        # The executable used to search for PEP 561 packages. If this is None,
        # then mypy does not search for PEP 561 packages.
        self.python_executable = sys.executable  # type: Optional[str]
        self.platform = sys.platform
        self.custom_typing_module = None  # type: Optional[str]
        self.custom_typeshed_dir = None  # type: Optional[str]
        self.mypy_path = []  # type: List[str]
        self.report_dirs = {}  # type: Dict[str, str]
        # Show errors in PEP 561 packages/site-packages modules
        self.no_silence_site_packages = False
        self.ignore_missing_imports = False
        self.follow_imports = 'normal'  # normal|silent|skip|error
        # Whether to respect the follow_imports setting even for stub files.
        # Intended to be used for disabling specific stubs.
        self.follow_imports_for_stubs = False
        # PEP 420 namespace packages
        self.namespace_packages = False

        # Use the new semantic analyzer
        self.new_semantic_analyzer = False

        # disallow_any options
        self.disallow_any_generics = False
        self.disallow_any_unimported = False
        self.disallow_any_expr = False
        self.disallow_any_decorated = False
        self.disallow_any_explicit = False

        # Disallow calling untyped functions from typed ones
        self.disallow_untyped_calls = False

        # Disallow defining untyped (or incompletely typed) functions
        self.disallow_untyped_defs = False

        # Disallow defining incompletely typed functions
        self.disallow_incomplete_defs = False

        # Type check unannotated functions
        self.check_untyped_defs = False

        # Disallow decorating typed functions with untyped decorators
        self.disallow_untyped_decorators = False

        # Disallow subclassing values of type 'Any'
        self.disallow_subclassing_any = False

        # Also check typeshed for missing annotations
        self.warn_incomplete_stub = False

        # Warn about casting an expression to its inferred type
        self.warn_redundant_casts = False

        # Warn about falling off the end of a function returning non-None
        self.warn_no_return = True

        # Warn about returning objects of type Any when the function is
        # declared with a precise type
        self.warn_return_any = False

        # Warn about unused '# type: ignore' comments
        self.warn_unused_ignores = False

        # Warn about unused '[mypy-<pattern>] config sections
        self.warn_unused_configs = False

        # Files in which to ignore all non-fatal errors
        self.ignore_errors = False

        # Apply strict None checking
        self.strict_optional = True

        # Show "note: In function "foo":" messages.
        self.show_error_context = False

        # Files in which to allow strict-Optional related errors
        # TODO: Kill this in favor of show_none_errors
        self.strict_optional_whitelist = None   # type: Optional[List[str]]

        # Alternate way to show/hide strict-None-checking related errors
        self.show_none_errors = True

        # Don't assume arguments with default values of None are Optional
        self.no_implicit_optional = False

        # Don't re-export names unless they are imported with `from ... as ...`
        self.no_implicit_reexport = False

        # Suppress toplevel errors caused by missing annotations
        self.allow_untyped_globals = False

        # Allow variable to be redefined with an arbitrary type in the same block
        # and the same nesting level as the initialization
        self.allow_redefinition = False

        # Prohibit equality, identity, and container checks for non-overlapping types.
        # This makes 1 == '1', 1 in ['1'], and 1 is '1' errors.
        self.strict_equality = False

        # Variable names considered True
        self.always_true = []  # type: List[str]

        # Variable names considered False
        self.always_false = []  # type: List[str]

        # Use script name instead of __main__
        self.scripts_are_modules = False

        # Config file name
        self.config_file = None  # type: Optional[str]

        # A filename containing a JSON mapping from filenames to
        # mtime/size/hash arrays, used to avoid having to recalculate
        # source hashes as often.
        self.quickstart_file = None  # type: Optional[str]

        # A comma-separated list of files/directories for mypy to type check;
        # supports globbing
        self.files = None  # type: Optional[List[str]]

        # Write junit.xml to given file
        self.junit_xml = None  # type: Optional[str]

        # Caching and incremental checking options
        self.incremental = True
        self.cache_dir = defaults.CACHE_DIR
        self.sqlite_cache = False
        self.debug_cache = False
        self.skip_version_check = False
        self.skip_cache_mtime_checks = False
        self.fine_grained_incremental = False
        # Include fine-grained dependencies in written cache files
        self.cache_fine_grained = False
        # Read cache files in fine-grained incremental mode (cache must include dependencies)
        self.use_fine_grained_cache = False

        # Tune certain behaviors when being used as a front-end to mypyc. Set per-module
        # in modules being compiled. Not in the config file or command line.
        self.mypyc = False

        # Paths of user plugins
        self.plugins = []  # type: List[str]

        # Per-module options (raw)
        self.per_module_options = OrderedDict()  # type: OrderedDict[str, Dict[str, object]]
        self.glob_options = []  # type: List[Tuple[str, Pattern[str]]]
        self.unused_configs = set()  # type: Set[str]

        # -- development options --
        self.verbosity = 0  # More verbose messages (for troubleshooting)
        self.pdb = False
        self.show_traceback = False
        self.raise_exceptions = False
        self.dump_type_stats = False
        self.dump_inference_stats = False

        # -- test options --
        # Stop after the semantic analysis phase
        self.semantic_analysis_only = False

        # Use stub builtins fixtures to speed up tests
        self.use_builtins_fixtures = False

        # -- experimental options --
        self.shadow_file = None  # type: Optional[List[List[str]]]
        self.show_column_numbers = False  # type: bool
        self.dump_graph = False
        self.dump_deps = False
        self.logical_deps = False
        # If True, partial types can't span a module top level and a function
        self.local_partial_types = False
        # Some behaviors are changed when using Bazel (https://bazel.build).
        self.bazel = False
        # If True, export inferred types for all expressions as BuildResult.types
        self.export_types = False
        # List of package roots -- directories under these are packages even
        # if they don't have __init__.py.
        self.package_root = []  # type: List[str]
        self.cache_map = {}  # type: Dict[str, Tuple[str, str]]
        # Don't properly free objects on exit, just kill the current process.
        self.fast_exit = False

    def snapshot(self) -> object:
        """Produce a comparable snapshot of this Option"""
        # Under mypyc, we don't have a __dict__, so we need to do worse things.
        d = dict(getattr(self, '__dict__', ()))
        for k in get_class_descriptors(Options):
            if hasattr(self, k):
                d[k] = getattr(self, k)
        del d['per_module_cache']
        return d

    def __repr__(self) -> str:
        return 'Options({})'.format(pprint.pformat(self.snapshot()))

    def apply_changes(self, changes: Dict[str, object]) -> 'Options':
        new_options = Options()
        # Under mypyc, we don't have a __dict__, so we need to do worse things.
        replace_object_state(new_options, self, copy_dict=True)
        for key, value in changes.items():
            setattr(new_options, key, value)
        return new_options

    def build_per_module_cache(self) -> None:
        self.per_module_cache = {}

        # Config precedence is as follows:
        #  1. Concrete section names: foo.bar.baz
        #  2. "Unstructured" glob patterns: foo.*.baz, in the order
        #     they appear in the file (last wins)
        #  3. "Well-structured" wildcard patterns: foo.bar.*, in specificity order.

        # Since structured configs inherit from structured configs above them in the hierarchy,
        # we need to process per-module configs in a careful order.
        # We have to process foo.* before foo.bar.* before foo.bar,
        # and we need to apply *.bar to foo.bar but not to foo.bar.*.
        # To do this, process all well-structured glob configs before non-glob configs and
        # exploit the fact that foo.* sorts earlier ASCIIbetically (unicodebetically?)
        # than foo.bar.*.
        # (A section being "processed last" results in its config "winning".)
        # Unstructured glob configs are stored and are all checked for each module.
        unstructured_glob_keys = [k for k in self.per_module_options.keys()
                                  if '*' in k[:-1]]
        structured_keys = [k for k in self.per_module_options.keys()
                           if '*' not in k[:-1]]
        wildcards = sorted(k for k in structured_keys if k.endswith('.*'))
        concrete = [k for k in structured_keys if not k.endswith('.*')]

        for glob in unstructured_glob_keys:
            self.glob_options.append((glob, self.compile_glob(glob)))

        # We (for ease of implementation) treat unstructured glob
        # sections as used if any real modules use them or if any
        # concrete config sections use them. This means we need to
        # track which get used while constructing.
        self.unused_configs = set(unstructured_glob_keys)

        for key in wildcards + concrete:
            # Find what the options for this key would be, just based
            # on inheriting from parent configs.
            options = self.clone_for_module(key)
            # And then update it with its per-module options.
            self.per_module_cache[key] = options.apply_changes(self.per_module_options[key])

        # Add the more structured sections into unused configs, since
        # they only count as used if actually used by a real module.
        self.unused_configs.update(structured_keys)

    def clone_for_module(self, module: str) -> 'Options':
        """Create an Options object that incorporates per-module options.

        NOTE: Once this method is called all Options objects should be
        considered read-only, else the caching might be incorrect.
        """
        if self.per_module_cache is None:
            self.build_per_module_cache()
        assert self.per_module_cache is not None

        # If the module just directly has a config entry, use it.
        if module in self.per_module_cache:
            self.unused_configs.discard(module)
            return self.per_module_cache[module]

        # If not, search for glob paths at all the parents. So if we are looking for
        # options for foo.bar.baz, we search foo.bar.baz.*, foo.bar.*, foo.*,
        # in that order, looking for an entry.
        # This is technically quadratic in the length of the path, but module paths
        # don't actually get all that long.
        options = self
        path = module.split('.')
        for i in range(len(path), 0, -1):
            key = '.'.join(path[:i] + ['*'])
            if key in self.per_module_cache:
                self.unused_configs.discard(key)
                options = self.per_module_cache[key]
                break

        # OK and *now* we need to look for unstructured glob matches.
        # We only do this for concrete modules, not structured wildcards.
        if not module.endswith('.*'):
            for key, pattern in self.glob_options:
                if pattern.match(module):
                    self.unused_configs.discard(key)
                    options = options.apply_changes(self.per_module_options[key])

        # We could update the cache to directly point to modules once
        # they have been looked up, but in testing this made things
        # slower and not faster, so we don't bother.

        return options

    def compile_glob(self, s: str) -> Pattern[str]:
        # Compile one of the glob patterns to a regex so that '.*' can
        # match *zero or more* module sections. This means we compile
        # '.*' into '(\..*)?'.
        parts = s.split('.')
        expr = re.escape(parts[0]) if parts[0] != '*' else '.*'
        for part in parts[1:]:
            expr += re.escape('.' + part) if part != '*' else r'(\..*)?'
        return re.compile(expr + '\\Z')

    def select_options_affecting_cache(self) -> Mapping[str, object]:
        return {opt: getattr(self, opt) for opt in OPTIONS_AFFECTING_CACHE}
