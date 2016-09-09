from mypy import defaults
import pprint
import sys
from typing import Any, Optional, Tuple, List


class BuildType:
    STANDARD = 0
    MODULE = 1
    PROGRAM_TEXT = 2


class Options:
    """Options collected from flags."""

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

        # Files in which to allow strict-Optional related errors
        self.strict_optional_whitelist = None   # type: Optional[List[str]]

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
        self.cache_dir = defaults.MYPY_CACHE
        self.debug_cache = False
        self.suppress_error_context = False  # Suppress "note: In function "foo":" messages.
        self.shadow_file = None  # type: Optional[Tuple[str, str]]

    def __eq__(self, other: object) -> bool:
        return self.__class__ == other.__class__ and self.__dict__ == other.__dict__

    def __ne__(self, other: object) -> bool:
        return not self == other

    def __repr__(self) -> str:
        return 'Options({})'.format(pprint.pformat(self.__dict__))
