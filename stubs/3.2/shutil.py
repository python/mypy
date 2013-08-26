# Stubs for shutil

# Based on http://docs.python.org/3.2/library/shutil.html

# 'bytes' paths are not properly supported: they don't work with all functions,
# sometimes they only work partially (broken exception messages), and the test
# cases don't use them.

from typing import (
    overload, List, Iterable, Function, Any, Tuple, Sequence, IO, AnyStr
)

def copyfileobj(fsrc: IO[AnyStr], fdst: IO[AnyStr],
                length: int = None) -> None: pass

def copyfile(src: str, dst: str) -> None: pass
def copymode(src: str, dst: str) -> None: pass
def copystat(src: str, dst: str) -> None: pass
def copy(src: str, dst: str) -> None: pass
def copy2(src: str, dst: str) -> None: pass
def ignore_patterns(*patterns: str) -> Function[[str, List[str]],
                                                Iterable[str]]: pass
def copytree(src: str, dst: str, symlinks: bool = False,
             ignore: Function[[str, List[str]], Iterable[str]] = None,
             copy_function: Function[[str, str], None] = copy2,
             ignore_dangling_symlinks: bool = False) -> None: pass
def rmtree(path: str, ignore_errors: bool = False,
           onerror: Function[[Any, str, Any], None] = None) -> None: pass
def move(src: str, dst: str) -> None: pass

class Error(Exception): pass

def make_archive(base_name: str, format: str, root_dir: str = None,
                 base_dir: str = None, verbose: bool = False,
                 dry_run: bool = False, owner: str = None, group: str = None,
                 logger: Any = None) -> str: pass
def get_archive_formats() -> List[Tuple[str, str]]: pass
def register_archive_format(name: str, function: Any,
                            extra_args: Sequence[Tuple[str, Any]] = None,
                            description: str = None) -> None: pass
def unregister_archive_format(name: str) -> None: pass
def unpack_archive(filename: str, extract_dir: str = None,
                   format: str = None) -> None: pass
def register_unpack_format(name: str, extensions: List[str], function: Any,
                           extra_args: Sequence[Tuple[str, Any]] = None,
                           description: str = None) -> None: pass
def unregister_unpack_format(name: str) -> None: pass
def get_unpack_formats() -> List[Tuple[str, List[str], str]]: pass
