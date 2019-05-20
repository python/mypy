import argparse
import configparser
import glob as fileglob
import os
import re
import sys

from mypy import defaults
from mypy.options import Options, PER_MODULE_OPTIONS

from typing import Any, Dict, List, Mapping, Optional, Tuple, TextIO


MYPY = False
if MYPY:
    from typing_extensions import Final


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


def split_and_match_files(paths: str) -> List[str]:
    """Take a string representing a list of files/directories (with support for globbing
    through the glob library).

    Where a path/glob matches no file, we still include the raw path in the resulting list.

    Returns a list of file paths
    """
    expanded_paths = []

    for path in paths.split(','):
        path = path.strip()
        globbed_files = fileglob.glob(path, recursive=True)
        if globbed_files:
            expanded_paths.extend(globbed_files)
        else:
            expanded_paths.append(path)

    return expanded_paths


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
    'files': split_and_match_files,
    'quickstart_file': str,
    'junit_xml': str,
    # These two are for backwards compatibility
    'silent_imports': bool,
    'almost_silent': bool,
    'plugins': lambda s: [p.strip() for p in s.split(',')],
    'always_true': lambda s: [p.strip() for p in s.split(',')],
    'always_false': lambda s: [p.strip() for p in s.split(',')],
    'package_root': lambda s: [p.strip() for p in s.split(',')],
}  # type: Final


def parse_config_file(options: Options, filename: Optional[str],
                      stdout: Optional[TextIO] = None,
                      stderr: Optional[TextIO] = None) -> None:
    """Parse a config file into an Options object.

    Errors are written to stderr but are not fatal.

    If filename is None, fall back to default config files.
    """
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr

    if filename is not None:
        config_files = (filename,)  # type: Tuple[str, ...]
    else:
        config_files = tuple(map(os.path.expanduser, defaults.CONFIG_FILES))

    parser = configparser.RawConfigParser()

    for config_file in config_files:
        if not os.path.exists(config_file):
            continue
        try:
            parser.read(config_file)
        except configparser.Error as err:
            print("%s: %s" % (config_file, err), file=stderr)
        else:
            file_read = config_file
            options.config_file = file_read
            break
    else:
        return

    if 'mypy' not in parser:
        if filename or file_read not in defaults.SHARED_CONFIG_FILES:
            print("%s: No [mypy] section in config file" % file_read, file=stderr)
    else:
        section = parser['mypy']
        prefix = '%s: [%s]' % (file_read, 'mypy')
        updates, report_dirs = parse_section(prefix, options, section,
                                             stdout, stderr)
        for k, v in updates.items():
            setattr(options, k, v)
        options.report_dirs.update(report_dirs)

    for name, section in parser.items():
        if name.startswith('mypy-'):
            prefix = '%s: [%s]' % (file_read, name)
            updates, report_dirs = parse_section(prefix, options, section,
                                                 stdout, stderr)
            if report_dirs:
                print("%s: Per-module sections should not specify reports (%s)" %
                      (prefix, ', '.join(s + '_report' for s in sorted(report_dirs))),
                      file=stderr)
            if set(updates) - PER_MODULE_OPTIONS:
                print("%s: Per-module sections should only specify per-module flags (%s)" %
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
                    print("%s: Patterns must be fully-qualified module names, optionally "
                          "with '*' in some components (e.g spam.*.eggs.*)"
                          % prefix,
                          file=stderr)
                else:
                    options.per_module_options[glob] = updates


def parse_section(prefix: str, template: Options,
                  section: Mapping[str, str],
                  stdout: TextIO = sys.stdout,
                  stderr: TextIO = sys.stderr
                  ) -> Tuple[Dict[str, object], Dict[str, str]]:
    """Parse one section of a config file.

    Returns a dict of option values encountered, and a dict of report directories.
    """
    results = {}  # type: Dict[str, object]
    report_dirs = {}  # type: Dict[str, str]
    for key in section:
        if key in config_types:
            ct = config_types[key]
        else:
            dv = getattr(template, key, None)
            if dv is None:
                if key.endswith('_report'):
                    report_type = key[:-7].replace('_', '-')
                    if report_type in defaults.REPORTER_NAMES:
                        report_dirs[report_type] = section[key]
                    else:
                        print("%s: Unrecognized report type: %s" % (prefix, key),
                              file=stderr)
                    continue
                if key.startswith('x_'):
                    continue  # Don't complain about `x_blah` flags
                elif key == 'strict':
                    print("%s: Strict mode is not supported in configuration files: specify "
                          "individual flags instead (see 'mypy -h' for the list of flags enabled "
                          "in strict mode)" % prefix, file=stderr)
                else:
                    print("%s: Unrecognized option: %s = %s" % (prefix, key, section[key]),
                          file=stderr)
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
                    print("%s: %s: %s" % (prefix, key, err), file=stderr)
                    continue
            else:
                print("%s: Don't know what type %s should have" % (prefix, key), file=stderr)
                continue
        except ValueError as err:
            print("%s: %s: %s" % (prefix, key, err), file=stderr)
            continue
        if key == 'cache_dir':
            v = os.path.expanduser(v)
        if key == 'silent_imports':
            print("%s: silent_imports has been replaced by "
                  "ignore_missing_imports=True; follow_imports=skip" % prefix, file=stderr)
            if v:
                if 'ignore_missing_imports' not in results:
                    results['ignore_missing_imports'] = True
                if 'follow_imports' not in results:
                    results['follow_imports'] = 'skip'
        if key == 'almost_silent':
            print("%s: almost_silent has been replaced by "
                  "follow_imports=error" % prefix, file=stderr)
            if v:
                if 'follow_imports' not in results:
                    results['follow_imports'] = 'error'
        results[key] = v
    return results, report_dirs
