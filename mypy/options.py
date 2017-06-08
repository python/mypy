import argparse
from configparser import RawConfigParser
import fnmatch
import os
import pprint
import re
import sys

from typing import Mapping, Optional, Tuple, List, Pattern, Dict

from mypy import defaults
from mypy.report import reporter_classes


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
    }

    OPTIONS_AFFECTING_CACHE = PER_MODULE_OPTIONS | {"strict_optional", "quick_and_dirty"}

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

        # Type check unannotated functions
        self.check_untyped_defs = False

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

        # Per-module options (raw)
        self.per_module_options = {}  # type: Dict[Pattern[str], Dict[str, object]]

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

    def clone_for_module(self, module: str, path: Optional[str]) -> 'Options':
        updates = {}
        for pattern in self.per_module_options:
            if self.module_matches_pattern(module, pattern):
                updates.update(self.per_module_options[pattern])

        new_options = Options()

        if path and os.path.exists(path):
            options_section = []
            found_options = False
            with open(path) as file_contents:
                for line in file_contents:
                    if not re.match('\s*#', line):
                        break

                    if re.match('\s*#\s*\[mypy\]', line):
                        options_section.append(line.strip().strip('#'))
                        found_options = True
                        continue

                    if found_options:
                        options_section.append(line.strip().strip('#'))

            if found_options:
                parser = RawConfigParser()
                parser.read_string("\n".join(options_section))
                updates, report_dirs = parse_section(
                    "%s [mypy]" % path,
                    new_options,
                    parser['mypy']
                )
                if report_dirs:
                    print("Warning: can't specify new mypy reports "
                          "in a per-file override (from {})".format(path))

                for option, file_override in updates.items():
                    if file_override == getattr(new_options, option):
                        # Skip options that are set to the defaults
                        continue

                    if option not in self.PER_MODULE_OPTIONS:
                        print("Warning: {!r} in {} is not a valid "
                              "per-module option".format(option, path))
                    else:
                        updates[option] = file_override

        if not updates:
            return self
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


def parse_version(v: str) -> Tuple[int, int]:
    m = re.match(r'\A(\d)\.(\d+)\Z', v)
    if not m:
        raise argparse.ArgumentTypeError(
            "Invalid python version '{}' (expected format: 'x.y')".format(v))
    major, minor = int(m.group(1)), int(m.group(2))
    if major == 2:
        if minor != 7:
            raise argparse.ArgumentTypeError(
                "Python 2.{} is not supported (must be 2.7)".format(minor))
    elif major == 3:
        if minor <= 2:
            raise argparse.ArgumentTypeError(
                "Python 3.{} is not supported (must be 3.3 or higher)".format(minor))
    else:
        raise argparse.ArgumentTypeError(
            "Python major version '{}' out of range (must be 2 or 3)".format(major))
    return major, minor


# For most options, the type of the default value set in options.py is
# sufficient, and we don't have to do anything here.  This table
# exists to specify types for values initialized to None or container
# types.
config_types = {
    'python_version': parse_version,
    'strict_optional_whitelist': lambda s: s.split(),
    'custom_typing_module': str,
    'custom_typeshed_dir': str,
    'mypy_path': lambda s: [p.strip() for p in re.split('[,:]', s)],
    'junit_xml': str,
    # These two are for backwards compatibility
    'silent_imports': bool,
    'almost_silent': bool,
}


def parse_section(prefix: str, template: Options,
                  section: Mapping[str, str]) -> Tuple[Dict[str, object], Dict[str, str]]:
    """Parse one section of a config file.

    Returns a dict of option values encountered, and a dict of report directories.
    """
    results = {}  # type: Dict[str, object]
    report_dirs = {}  # type: Dict[str, str]
    for key in section:
        key = key.replace('-', '_')
        if key in config_types:
            ct = config_types[key]
        else:
            dv = getattr(template, key, None)
            if dv is None:
                if key.endswith('_report'):
                    report_type = key[:-7].replace('_', '-')
                    if report_type in reporter_classes:
                        report_dirs[report_type] = section.get(key)
                    else:
                        print("%s: Unrecognized report type: %s" % (prefix, key),
                              file=sys.stderr)
                    continue
                print("%s: Unrecognized option: %s = %s" % (prefix, key, section[key]),
                      file=sys.stderr)
                continue
            ct = type(dv)
        v = None  # type: Any
        try:
            if ct is bool:
                v = section.getboolean(key)  # type: ignore  # Until better stub
            elif callable(ct):
                try:
                    v = ct(section.get(key))
                except argparse.ArgumentTypeError as err:
                    print("%s: %s: %s" % (prefix, key, err), file=sys.stderr)
                    continue
            else:
                print("%s: Don't know what type %s should have" % (prefix, key), file=sys.stderr)
                continue
        except ValueError as err:
            print("%s: %s: %s" % (prefix, key, err), file=sys.stderr)
            continue
        if key == 'silent_imports':
            print("%s: silent_imports has been replaced by "
                  "ignore_missing_imports=True; follow_imports=skip" % prefix, file=sys.stderr)
            if v:
                if 'ignore_missing_imports' not in results:
                    results['ignore_missing_imports'] = True
                if 'follow_imports' not in results:
                    results['follow_imports'] = 'skip'
        if key == 'almost_silent':
            print("%s: almost_silent has been replaced by "
                  "follow_imports=error" % prefix, file=sys.stderr)
            if v:
                if 'follow_imports' not in results:
                    results['follow_imports'] = 'error'
        results[key] = v
    return results, report_dirs
