import fnmatch
import pprint
import sys

from typing import Any, Mapping, Optional, Tuple, List

from mypy import defaults


class BuildType:
    STANDARD = 0
    MODULE = 1
    PROGRAM_TEXT = 2


class Options:
    """Options collected from flags."""

    PER_FILE_OPTIONS = {
        "silent_imports",
        "almost_silent",
        "disallow_untyped_calls",
        "disallow_untyped_defs",
        "check_untyped_defs",
        "debug_cache",
        "strict_optional_whitelist",
        "show_none_errors",
    }

    OPTIONS_AFFECTING_CACHE = PER_FILE_OPTIONS | {"strict_optional"}

    def __init__(self) -> None:
        # -- build options --
        self.build_type = BuildType.STANDARD
        self.python_version = defaults.PYTHON3_VERSION
        self.platform = sys.platform
        self.custom_typing_module = None  # type: str
        self.report_dirs = {}  # type: Dict[str, str]
        self.silent_imports = False
        self.almost_silent = False

        # Disallow calling untyped functions from typed ones
        self.disallow_untyped_calls = False

        # Disallow defining untyped (or incompletely typed) functions
        self.disallow_untyped_defs = False

        # Type check unannotated functions
        self.check_untyped_defs = False

        # Disallow subclassing values of type 'Any'
        self.disallow_subclassing_any = False

        # Also check typeshed for missing annotations
        self.warn_incomplete_stub = False

        # Warn about casting an expression to its inferred type
        self.warn_redundant_casts = False

        # Warn about unused '# type: ignore' comments
        self.warn_unused_ignores = False

        # Apply strict None checking
        self.strict_optional = False

        # Files in which to allow strict-Optional related errors
        # TODO: Kill this in favor of show_none_errors
        self.strict_optional_whitelist = None   # type: Optional[List[str]]

        # Alternate way to show/hide strict-None-checking related errors
        self.show_none_errors = True

        # Use script name instead of __main__
        self.scripts_are_modules = False

        # Config file name
        self.config_file = None  # type: Optional[str]

        # Per-file options (raw)
        self.per_file_options = {}  # type: Dict[str, Dict[str, object]]

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
        self.fast_parser = False
        self.incremental = False
        self.cache_dir = defaults.CACHE_DIR
        self.debug_cache = False
        self.hide_error_context = False  # Hide "note: In function "foo":" messages.
        self.shadow_file = None  # type: Optional[Tuple[str, str]]
        self.show_column_numbers = False  # type: bool

    def __eq__(self, other: object) -> bool:
        return self.__class__ == other.__class__ and self.__dict__ == other.__dict__

    def __ne__(self, other: object) -> bool:
        return not self == other

    def __repr__(self) -> str:
        return 'Options({})'.format(pprint.pformat(self.__dict__))

    def clone_for_file(self, filename: str) -> 'Options':
        updates = {}
        for glob in self.per_file_options:
            if fnmatch.fnmatch(filename, glob):
                updates.update(self.per_file_options[glob])
        if not updates:
            return self
        new_options = Options()
        new_options.__dict__.update(self.__dict__)
        new_options.__dict__.update(updates)
        return new_options

    def select_options_affecting_cache(self) -> Mapping[str, bool]:
        return {opt: getattr(self, opt) for opt in self.OPTIONS_AFFECTING_CACHE}
