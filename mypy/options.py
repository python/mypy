from collections import OrderedDict
import fnmatch
import pprint
import sys

from typing import Dict, List, Mapping, MutableMapping, Optional, Pattern, Set, Tuple

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
        "disallow_any",
        "disallow_subclassing_any",
        "disallow_untyped_calls",
        "disallow_untyped_defs",
        "check_untyped_defs",
        "debug_cache",
        "strict_optional_whitelist",
        "show_none_errors",
        "warn_no_return",
        "warn_return_any",
        "ignore_errors",
        "strict_boolean",
        "no_implicit_optional",
        "strict_optional",
        "disallow_untyped_decorators",
    }

    OPTIONS_AFFECTING_CACHE = ((PER_MODULE_OPTIONS | {"quick_and_dirty", "platform"})
                               - {"debug_cache"})

    def __init__(self) -> None:
        # -- build options --
        self.build_type = BuildType.STANDARD
        self.python_version = defaults.PYTHON3_VERSION
        self.platform = sys.platform
        self.custom_typing_module = None  # type: Optional[str]
        self.custom_typeshed_dir = None  # type: Optional[str]
        self.mypy_path = []  # type: List[str]
        self.report_dirs = {}  # type: Dict[str, str]
        self.ignore_missing_imports = False
        self.follow_imports = 'normal'  # normal|silent|skip|error
        self.disallow_any = []  # type: List[str]

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

        # Use script name instead of __main__
        self.scripts_are_modules = False

        # Config file name
        self.config_file = None  # type: Optional[str]

        # Write junit.xml to given file
        self.junit_xml = None  # type: Optional[str]

        # Caching options
        self.incremental = False
        self.cache_dir = defaults.CACHE_DIR
        self.debug_cache = False
        self.quick_and_dirty = False
        self.skip_version_check = False

        # Paths of user plugins
        self.plugins = []  # type: List[str]

        # Per-module options (raw)
        pm_opts = OrderedDict()  # type: OrderedDict[Pattern[str], Dict[str, object]]
        self.per_module_options = pm_opts
        # Map pattern back to glob
        self.unused_configs = OrderedDict()  # type: OrderedDict[Pattern[str], str]

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

    def __eq__(self, other: object) -> bool:
        return self.__class__ == other.__class__ and self.__dict__ == other.__dict__

    def __ne__(self, other: object) -> bool:
        return not self == other

    def __repr__(self) -> str:
        return 'Options({})'.format(pprint.pformat(self.__dict__))

    def clone_for_module(self, module: str) -> 'Options':
        updates = {}
        for pattern in self.per_module_options:
            if self.module_matches_pattern(module, pattern):
                if pattern in self.unused_configs:
                    del self.unused_configs[pattern]
                updates.update(self.per_module_options[pattern])
        if not updates:
            return self
        new_options = Options()
        new_options.__dict__.update(self.__dict__)
        new_options.__dict__.update(updates)
        return new_options

    def module_matches_pattern(self, module: str, pattern: Pattern[str]) -> bool:
        # If the pattern is 'mod.*', we want 'mod' to match that too.
        # (That's so that a pattern specifying a package also matches
        # that package's __init__.)
        return pattern.match(module) is not None or pattern.match(module + '.') is not None

    def select_options_affecting_cache(self) -> Mapping[str, bool]:
        return {opt: getattr(self, opt) for opt in self.OPTIONS_AFFECTING_CACHE}
