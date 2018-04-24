from collections import OrderedDict
import pprint
import sys

from typing import Dict, List, Mapping, MutableMapping, Optional, Set, Tuple

from mypy import defaults


class BuildType:
    STANDARD = 0
    MODULE = 1
    PROGRAM_TEXT = 2


class Options:
    """Options collected from flags."""

    PER_MODULE_OPTIONS = {
        "ignore_missing_imports",
        "follow_imports",
        "follow_imports_for_stubs",
        "disallow_any_generics",
        "disallow_any_unimported",
        "disallow_any_expr",
        "disallow_any_decorated",
        "disallow_any_explicit",
        "disallow_subclassing_any",
        "disallow_untyped_calls",
        "disallow_untyped_defs",
        "check_untyped_defs",
        "debug_cache",
        "strict_optional_whitelist",
        "show_none_errors",
        "warn_no_return",
        "warn_return_any",
        "warn_unused_ignores",
        "ignore_errors",
        "strict_boolean",
        "no_implicit_optional",
        "always_true",
        "always_false",
        "strict_optional",
        "disallow_untyped_decorators",
    }

    OPTIONS_AFFECTING_CACHE = ((PER_MODULE_OPTIONS |
                                {"quick_and_dirty", "platform"})
                               - {"debug_cache"})

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
        self.ignore_missing_imports = False
        self.follow_imports = 'normal'  # normal|silent|skip|error
        # Whether to respect the follow_imports setting even for stub files.
        # Intended to be used for disabling specific stubs.
        self.follow_imports_for_stubs = False  # type: bool

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

        # Only allow booleans in conditions
        self.strict_boolean = False

        # Apply strict None checking
        self.strict_optional = False

        # Show "note: In function "foo":" messages.
        self.show_error_context = False

        # Files in which to allow strict-Optional related errors
        # TODO: Kill this in favor of show_none_errors
        self.strict_optional_whitelist = None   # type: Optional[List[str]]

        # Alternate way to show/hide strict-None-checking related errors
        self.show_none_errors = True

        # Don't assume arguments with default values of None are Optional
        self.no_implicit_optional = False

        # Variable names considered True
        self.always_true = []  # type: List[str]

        # Variable names considered False
        self.always_false = []  # type: List[str]

        # Use script name instead of __main__
        self.scripts_are_modules = False

        # Config file name
        self.config_file = None  # type: Optional[str]

        # Write junit.xml to given file
        self.junit_xml = None  # type: Optional[str]

        # Caching and incremental checking options
        self.incremental = True
        self.cache_dir = defaults.CACHE_DIR
        self.debug_cache = False
        self.quick_and_dirty = False
        self.skip_version_check = False
        self.fine_grained_incremental = False
        # Include fine-grained dependencies in written cache files
        self.cache_fine_grained = False
        # Read cache files in fine-grained incremental mode (cache must include dependencies)
        self.use_fine_grained_cache = False

        # Paths of user plugins
        self.plugins = []  # type: List[str]

        # Per-module options (raw)
        pm_opts = OrderedDict()  # type: OrderedDict[str, Dict[str, object]]
        self.per_module_options = pm_opts
        self.unused_configs = set()  # type: Set[str]

        # -- development options --
        self.verbosity = 0  # More verbose messages (for troubleshooting)
        self.pdb = False
        self.show_traceback = False
        self.dump_type_stats = False
        self.dump_inference_stats = False

        # -- test options --
        # Stop after the semantic analysis phase
        self.semantic_analysis_only = False

        # Use stub builtins fixtures to speed up tests
        self.use_builtins_fixtures = False

        # -- experimental options --
        self.shadow_file = None  # type: Optional[Tuple[str, str]]
        self.show_column_numbers = False  # type: bool
        self.dump_graph = False
        self.dump_deps = False
        # If True, partial types can't span a module top level and a function
        self.local_partial_types = False

    def __eq__(self, other: object) -> bool:
        return self.__class__ == other.__class__ and self.__dict__ == other.__dict__

    def __ne__(self, other: object) -> bool:
        return not self == other

    def __repr__(self) -> str:
        d = dict(self.__dict__)
        del d['per_module_cache']
        return 'Options({})'.format(pprint.pformat(d))

    def build_per_module_cache(self) -> None:
        self.per_module_cache = {}
        # Since configs inherit from glob configs above them in the hierarchy,
        # we need to process per-module configs in a careful order.
        # We have to process foo.* before foo.bar.* before foo.bar.
        # To do this, process all glob configs before non-glob configs and
        # exploit the fact that foo.* sorts earlier ASCIIbetically (unicodebetically?)
        # than foo.bar.*.
        keys = (sorted(k for k in self.per_module_options.keys() if k.endswith('.*')) +
                [k for k in self.per_module_options.keys() if not k.endswith('.*')])
        for key in keys:
            # Find what the options for this key would be, just based
            # on inheriting from parent configs.
            options = self.clone_for_module(key)
            # And then update it with its per-module options.
            new_options = Options()
            new_options.__dict__.update(options.__dict__)
            new_options.__dict__.update(self.per_module_options[key])
            self.per_module_cache[key] = new_options

        self.unused_configs = set(keys)

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
        path = module.split('.')
        for i in range(len(path), 0, -1):
            key = '.'.join(path[:i] + ['*'])
            if key in self.per_module_cache:
                self.unused_configs.discard(key)
                return self.per_module_cache[key]

        # We could update the cache to directly point to modules once
        # they have been looked up, but in testing this made things
        # slower and not faster, so we don't bother.

        return self

    def select_options_affecting_cache(self) -> Mapping[str, object]:
        return {opt: getattr(self, opt) for opt in self.OPTIONS_AFFECTING_CACHE}
