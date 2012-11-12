import os.path
from os import separator, dir_name


# Find and read the source file of a module. Return a pair
# (path, file contents). Return nil, nil if the module could not be imported.
#
# id is a string of form "foo" or "foo.bar" (module name)
tuple<str, str> module_source(str id, list<str> paths):
    path = find_module(id, paths)
    if path is not None:
        str text
        try:
            f = file(path)
            try:
                text = f.read()
            finally:
                f.close()
        except IoError:
            return None, None
        return path, text
    else:
        return None, None


# Return that path of the module source file, or nil if not found.
str find_module(str id, list<str> paths):
    for libpath in paths:
        comp = id.split('.')
        path = os.path.join(libpath, separator.join(comp[:-1]), comp[-1] + '.py')
        str text
        if not os.path.isfile(path):
            path = os.path.join(libpath, separator.join(comp), '__init__.py')
        if os.path.isfile(path) and verify_module(id, path):
            return path
    return None


def verify_module(id, path):
    # Check that all packages containing id have a __init__ file.
    if path.endswith('__init__.py'):
        path = dir_name(path)
    for i in range(id.count('.')):
        path = dir_name(path)
        if not os.path.isfile(os.path.join(path, '__init__.py')):
            return False
    return True


list<str> super_packages(str id):
    c = id.split('.')
    list<str> res = []
    for i in range(1, len(c)):
        res.append('.'.join(c[:i]))
    return res
