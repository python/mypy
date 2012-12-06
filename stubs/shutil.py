# Stubs for shutil

# Based on http://docs.python.org/3.2/library/shutil.html

# TODO bytes paths?

void copyfileobj(IO fsrc, IO fdst, int length=None): pass
void copyfileobj(TextIO fsrc, TextIO fdst, int length=None): pass
void copyfile(str src, str dst): pass
void copymode(str src, str dst): pass
void copystat(str src, str dst): pass
void copy(str src, str dst): pass
void copy2(str src, str dst): pass
func<Iterable<str>(str, str[])> ignore_patterns(str *patterns): pass
void copytree(str src, str dst, bool symlinks=False,
              func<Iterable<str>(str, str[])> ignore=None,
              func<void(str, str)> copy_function=copy2,
              bool ignore_dangling_symlinks=False): pass
void rmtree(str path, bool ignore_errors=False,
            func<tuple<type, any, any>(any, str)> onerror=None): pass
void move(str src, str dst): pass

class Error(Exception): pass

void make_archive(str base_name, str format, str base_dir=None,
                  bool verbose=False, bool dry_run=False, str owner=None,
                  str group=None, any logger=None): pass
tuple<str, str>[] get_archive_formats(): pass
void register_archive_format(str name, any function,
                             Sequence<tuple<str, any>> extra_args=None,
                             str description=None): pass
void unregister_archive_format(str name): pass
void unpack_archive(str filename, str extract_dir=None, str format=None): pass
void register_unpack_format(str name, str[] extensions, any function,
                            Sequence<tuple<str, any>> extra_args=None,
                            str description=None): pass
void unregister_unpack_format(str name): pass
tuple<str, str[], str>[] get_unpack_formats(): pass
