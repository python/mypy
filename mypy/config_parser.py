import argparse
import configparser
import glob as fileglob
from io import StringIO
import os
import re
import sys

import toml
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple, TextIO, MutableMapping
from typing_extensions import Final

from mypy import defaults
from mypy.options import Options, PER_MODULE_OPTIONS


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
        if minor < defaults.PYTHON3_VERSION_MIN[1]:
            raise argparse.ArgumentTypeError(
                "Python 3.{0} is not supported (must be {1}.{2} or higher)".format(minor,
                                                                    *defaults.PYTHON3_VERSION_MIN))
    else:
        raise argparse.ArgumentTypeError(
            "Python major version '{}' out of range (must be 2 or 3)".format(major))
    return major, minor


def expand_path(path: str) -> str:
    """Expand the user home directory and any environment variables contained within
    the provided path.
    """

    return os.path.expandvars(os.path.expanduser(path))


def split_and_match_files(paths: str) -> List[str]:
    """Take a string representing a list of files/directories (with support for globbing
    through the glob library).

    Where a path/glob matches no file, we still include the raw path in the resulting list.

    Returns a list of file paths
    """

    return match_files(paths.split(','))


def match_files(paths: List[str]) -> List[str]:
    """Take list of files/directories (with support for globbing through the glob library).

    Where a path/glob matches no file, we still include the raw path in the resulting list.

    Returns a list of file paths
    """
    expanded_paths = []

    for path in paths:
        path = expand_path(path.strip())
        globbed_files = fileglob.glob(path, recursive=True)
        if globbed_files:
            expanded_paths.extend(globbed_files)
        else:
            expanded_paths.append(path)

    return expanded_paths


def check_follow_imports(choice: str) -> str:
    choices = ['normal', 'silent', 'skip', 'error']
    if choice not in choices:
        raise argparse.ArgumentTypeError(
            "invalid choice '{}' (choose from {})".format(
                choice,
                ', '.join("'{}'".format(x) for x in choices)))
    return choice


# For most options, the type of the default value set in options.py is
# sufficient, and we don't have to do anything here.  This table
# exists to specify types for values initialized to None or container
# types.
ini_type_converters = {
    'python_version': parse_version,
    'strict_optional_whitelist': lambda s: s.split(),
    'custom_typing_module': str,
    'custom_typeshed_dir': expand_path,
    'mypy_path': lambda s: [expand_path(p.strip()) for p in re.split('[,:]', s)],
    'files': split_and_match_files,
    'quickstart_file': expand_path,
    'junit_xml': expand_path,
    # These two are for backwards compatibility
    'silent_imports': bool,
    'almost_silent': bool,
    'follow_imports': check_follow_imports,
    'no_site_packages': bool,
    'plugins': lambda s: [p.strip() for p in s.split(',')],
    'always_true': lambda s: [p.strip() for p in s.split(',')],
    'always_false': lambda s: [p.strip() for p in s.split(',')],
    'disable_error_code': lambda s: [p.strip() for p in s.split(',')],
    'enable_error_code': lambda s: [p.strip() for p in s.split(',')],
    'package_root': lambda s: [p.strip() for p in s.split(',')],
    'cache_dir': expand_path,
    'python_executable': expand_path,
    'strict': bool,
}  # type: Final


toml_type_converters = {
    'python_version': parse_version,
    'custom_typeshed_dir': expand_path,
    'mypy_path': lambda l: [expand_path(p) for p in l],
    'files': match_files,
    'cache_dir': expand_path,
    'python_executable': expand_path,
}  # type: Final


def parse_config_file(options: Options, set_strict_flags: Callable[[], None],
                      filename: Optional[str],
                      stdout: Optional[TextIO] = None,
                      stderr: Optional[TextIO] = None) -> None:
    """Parse a config file into an Options object.

    Errors are written to stderr but are not fatal.

    If filename is None, fall back to default config files.
    """
    if filename is not None:
        filename = os.path.expanduser(filename)
        if os.path.splitext(filename)[1] == '.toml':
            parse_toml_config_file(
                options, set_strict_flags, filename, stdout, stderr, explicit=True)
        else:
            parse_ini_config_file(
                options, set_strict_flags, filename, stdout, stderr, explicit=True)
    else:
        for filename in defaults.CONFIG_FILES:
            filename = os.path.expanduser(filename)
            if not os.path.isfile(filename):
                continue
            if os.path.splitext(filename)[1] == '.toml':
                parsed = parse_toml_config_file(
                    options, set_strict_flags, filename, stdout, stderr, explicit=False)
            else:
                parsed = parse_ini_config_file(
                    options, set_strict_flags, filename, stdout, stderr, explicit=False)
            if parsed:
                break


def parse_toml_config_file(options: Options, set_strict_flags: Callable[[], None],
                           filename: str,
                           stdout: Optional[TextIO] = None,
                           stderr: Optional[TextIO] = None,
                           *,
                           explicit: bool) -> bool:
    stderr = stderr or sys.stderr

    # Load the toml config file.
    try:
        table = toml.load(filename)  # type: MutableMapping[str, Any]
    except (TypeError, toml.TomlDecodeError, IOError) as err:
        print("%s: %s" % (filename, err), file=stderr)
        return False
    else:
        options.config_file = filename

    if 'tool' not in table or 'mypy' not in table['tool']:
        if explicit:
            print("%s: No 'tool.mypy' table in config file" % filename, file=stderr)
        return False

    # Handle the mypy table.
    for key, value in table['tool']['mypy'].items():

        # Is an option.
        if key != 'overrides':

            # Is a report directory.
            if key.endswith('_report'):
                report_type = key[:-7].replace('_', '-')
                if report_type in defaults.REPORTER_NAMES:
                    options.report_dirs[report_type] = table['mypy'][key]
                else:
                    print("%s: Unrecognized report type: %s" %
                          (filename, key),
                          file=stderr)
            elif key == 'strict':
                set_strict_flags()
            else:
                if key in toml_type_converters:
                    value = toml_type_converters[key](value)  # type: ignore
                setattr(options, key, value)

        # Read the per-module override sub-tables.
        else:
            for glob, override in value.items():
                if (any(c in glob for c in '?[]!') or
                        any('*' in x and x != '*' for x in glob.split('.'))):
                    print("%s: Patterns must be fully-qualified module names, optionally "
                          "with '*' in some components (e.g spam.*.eggs.*)"
                          % filename, file=stderr)

                values = {}
                for subkey, subvalue in override.items():
                    if subkey.endswith('_report'):
                        print("Per-module override [%s] should not specify reports (%s)" %
                              (glob, subkey), file=stderr)
                        continue
                    elif subkey not in PER_MODULE_OPTIONS:
                        print("Per-module tables [%s] should only specify per-module flags (%s)" %
                              (key, subkey), file=stderr)
                        continue

                    if subkey in toml_type_converters:
                        subvalue = toml_type_converters[subkey](subvalue)  # type: ignore
                    values[subkey] = subvalue

                options.per_module_options[glob] = values
    return True


def parse_ini_config_file(options: Options, set_strict_flags: Callable[[], None],
                          filename: str,
                          stdout: Optional[TextIO] = None,
                          stderr: Optional[TextIO] = None,
                          *,
                          explicit: bool) -> bool:
    stderr = stderr or sys.stderr
    parser = configparser.RawConfigParser()
    retv = False

    try:
        parser.read(filename)
    except configparser.Error as err:
        print("%s: %s" % (filename, err), file=stderr)
        return retv
    else:
        options.config_file = filename

    os.environ['MYPY_CONFIG_FILE_DIR'] = os.path.dirname(
            os.path.abspath(filename))

    if 'mypy' not in parser:
        if not explicit and filename not in defaults.SHARED_CONFIG_FILES:
            print("%s: No [mypy] section in config file" % filename, file=stderr)
    else:
        retv = True
        section = parser['mypy']
        prefix = '%s: [%s]: ' % (filename, 'mypy')
        updates, report_dirs = parse_ini_section(
            prefix, options, set_strict_flags, section, stderr)
        for k, v in updates.items():
            setattr(options, k, v)
        options.report_dirs.update(report_dirs)

    for name, section in parser.items():
        if name.startswith('mypy-'):
            retv = True
            prefix = '%s: [%s]: ' % (filename, name)
            updates, report_dirs = parse_ini_section(
                prefix, options, set_strict_flags, section, stderr)
            if report_dirs:
                print("%sPer-module sections should not specify reports (%s)" %
                      (prefix, ', '.join(s + '_report' for s in sorted(report_dirs))),
                      file=stderr)
            if set(updates) - PER_MODULE_OPTIONS:
                print("%sPer-module sections should only specify per-module flags (%s)" %
                      (prefix, ', '.join(sorted(set(updates) - PER_MODULE_OPTIONS))),
                      file=stderr)
                updates = {k: v for k, v in updates.items() if k in PER_MODULE_OPTIONS}
            globs = name[5:]
            for glob in globs.split(','):
                # For backwards compatibility, replace (back)slashes with dots.
                glob = glob.replace(os.sep, '.')
                if os.altsep:
                    glob = glob.replace(os.altsep, '.')

                if (any(c in glob for c in '?[]!') or
                        any('*' in x and x != '*' for x in glob.split('.'))):
                    print("%sPatterns must be fully-qualified module names, optionally "
                          "with '*' in some components (e.g spam.*.eggs.*)"
                          % prefix,
                          file=stderr)
                else:
                    options.per_module_options[glob] = updates
    return retv


def parse_ini_section(prefix: str, template: Options,
                      set_strict_flags: Callable[[], None],
                      section: Mapping[str, str],
                      stderr: TextIO = sys.stderr
                      ) -> Tuple[Dict[str, object], Dict[str, str]]:
    """Parse one section of a config file.

    Returns a dict of option values encountered, and a dict of report directories.
    """
    results = {}  # type: Dict[str, object]
    report_dirs = {}  # type: Dict[str, str]
    for key in section:
        invert = False
        options_key = key
        if key in ini_type_converters:
            ct = ini_type_converters[key]
        else:
            dv = None
            # We have to keep new_semantic_analyzer in Options
            # for plugin compatibility but it is not a valid option anymore.
            assert hasattr(template, 'new_semantic_analyzer')
            if key != 'new_semantic_analyzer':
                dv = getattr(template, key, None)
            if dv is None:
                if key.endswith('_report'):
                    report_type = key[:-7].replace('_', '-')
                    if report_type in defaults.REPORTER_NAMES:
                        report_dirs[report_type] = section[key]
                    else:
                        print("%sUnrecognized report type: %s" % (prefix, key),
                              file=stderr)
                    continue
                if key.startswith('x_'):
                    pass  # Don't complain about `x_blah` flags
                elif key.startswith('no_') and hasattr(template, key[3:]):
                    options_key = key[3:]
                    invert = True
                elif key.startswith('allow') and hasattr(template, 'dis' + key):
                    options_key = 'dis' + key
                    invert = True
                elif key.startswith('disallow') and hasattr(template, key[3:]):
                    options_key = key[3:]
                    invert = True
                elif key == 'strict':
                    pass  # Special handling below
                else:
                    print("%sUnrecognized option: %s = %s" % (prefix, key, section[key]),
                          file=stderr)
                if invert:
                    dv = getattr(template, options_key, None)
                else:
                    continue
            ct = type(dv)
        v = None  # type: Any
        try:
            if ct is bool:
                v = section.getboolean(key)  # type: ignore[attr-defined]  # Until better stub
                if invert:
                    v = not v
            elif callable(ct):
                if invert:
                    print("%sCan not invert non-boolean key %s" % (prefix, options_key),
                          file=stderr)
                    continue
                try:
                    v = ct(section.get(key))
                except argparse.ArgumentTypeError as err:
                    print("%s%s: %s" % (prefix, key, err), file=stderr)
                    continue
            else:
                print("%sDon't know what type %s should have" % (prefix, key), file=stderr)
                continue
        except ValueError as err:
            print("%s%s: %s" % (prefix, key, err), file=stderr)
            continue
        if key == 'strict':
            if v:
                set_strict_flags()
            continue
        if key == 'silent_imports':
            print("%ssilent_imports has been replaced by "
                  "ignore_missing_imports=True; follow_imports=skip" % prefix, file=stderr)
            if v:
                if 'ignore_missing_imports' not in results:
                    results['ignore_missing_imports'] = True
                if 'follow_imports' not in results:
                    results['follow_imports'] = 'skip'
        if key == 'almost_silent':
            print("%salmost_silent has been replaced by "
                  "follow_imports=error" % prefix, file=stderr)
            if v:
                if 'follow_imports' not in results:
                    results['follow_imports'] = 'error'
        results[options_key] = v
    return results, report_dirs


def split_directive(s: str) -> Tuple[List[str], List[str]]:
    """Split s on commas, except during quoted sections.

    Returns the parts and a list of error messages."""
    parts = []
    cur = []  # type: List[str]
    errors = []
    i = 0
    while i < len(s):
        if s[i] == ',':
            parts.append(''.join(cur).strip())
            cur = []
        elif s[i] == '"':
            i += 1
            while i < len(s) and s[i] != '"':
                cur.append(s[i])
                i += 1
            if i == len(s):
                errors.append("Unterminated quote in configuration comment")
                cur.clear()
        else:
            cur.append(s[i])
        i += 1
    if cur:
        parts.append(''.join(cur).strip())

    return parts, errors


def mypy_comments_to_config_map(line: str,
                                template: Options) -> Tuple[Dict[str, str], List[str]]:
    """Rewrite the mypy comment syntax into ini file syntax.

    Returns
    """
    options = {}
    entries, errors = split_directive(line)
    for entry in entries:
        if '=' not in entry:
            name = entry
            value = None
        else:
            name, value = [x.strip() for x in entry.split('=', 1)]

        name = name.replace('-', '_')
        if value is None:
            value = 'True'
        options[name] = value

    return options, errors


def parse_mypy_comments(
        args: List[Tuple[int, str]],
        template: Options) -> Tuple[Dict[str, object], List[Tuple[int, str]]]:
    """Parse a collection of inline mypy: configuration comments.

    Returns a dictionary of options to be applied and a list of error messages
    generated.
    """

    errors = []  # type: List[Tuple[int, str]]
    sections = {}

    for lineno, line in args:
        # In order to easily match the behavior for bools, we abuse configparser.
        # Oddly, the only way to get the SectionProxy object with the getboolean
        # method is to create a config parser.
        parser = configparser.RawConfigParser()
        options, parse_errors = mypy_comments_to_config_map(line, template)
        parser['dummy'] = options
        errors.extend((lineno, x) for x in parse_errors)

        stderr = StringIO()
        strict_found = False

        def set_strict_flags() -> None:
            nonlocal strict_found
            strict_found = True

        new_sections, reports = parse_ini_section(
            '', template, set_strict_flags, parser['dummy'], stderr=stderr)
        errors.extend((lineno, x) for x in stderr.getvalue().strip().split('\n') if x)
        if reports:
            errors.append((lineno, "Reports not supported in inline configuration"))
        if strict_found:
            errors.append((lineno,
                           "Setting 'strict' not supported in inline configuration: specify it in "
                           "a configuration file instead, or set individual inline flags "
                           "(see 'mypy -h' for the list of flags enabled in strict mode)"))

        sections.update(new_sections)

    return sections, errors
