"""Tools for runtime type inference"""

import inspect
import types
import codecs
import tokenize
try:
    from StringIO import StringIO
    from unparse import Unparser
except:
    from io import StringIO
    from unparse3 import Unparser
import ast


MAX_INFERRED_TUPLE_LENGTH = 10
PREFERRED_LINE_LENGTH = 79


var_db = {} # (location, variable) -> type
func_argid_db = {} # funcname -> set of (argindex, name)
func_arg_db = {} # (funcname, argindex/name) -> type
func_return_db = {} # funcname -> type
func_source_db = {} # funcid -> source string

# The type inferencing wrapper should not be reentrant.  It's not, in theory, calling
# out to any external code which we would want to infer the types of.  However, 
# sometimes we do something like infer_type(arg.keys()) or infer_type(arg.values()) if
# the arg is a collection, and we want to know about the types of its elements.  .keys(),
# .values(), etc. can be overloaded, possibly to a method we've wrapped.  This can become 
# infinitely recursive, particuarly because on something like arg.keys(), keys() gets passed
# arg as the first parameter, so if we've wrapped keys() we'll try to infer_type(arg),
# which will detect it's a dictionary, call infer_type(arg.keys()), recurse and so on.
# We ran in to this problem with collections.OrderedDict.
# To prevent reentrancy, we set is_performing_inference = True iff we're in the middle of
# inferring the types of a function.  If we try to run another function we've wrapped,
# we skip type inferencing so we can't accidentally infinitely recurse.
is_performing_inference = False


def reset():
    global var_db, func_argid_db, func_arg_db, func_return_db, func_source_db
    global is_performing_inference
    var_db = {}
    func_argid_db = {}
    func_arg_db = {}
    func_return_db = {}
    func_source_db = {}
    is_performing_inference = False


def format_state(pretty=False):
    lines = []
    for loc, var in sorted(var_db.keys()):
        lines.append('%s: %s' % (var, var_db[(loc, var)]))
    funcnames = sorted(set(name for name, arg in func_arg_db))
    prevclass = ''
    indent = ''
    for funcid in funcnames:
        name, sourcefile, sourceline = funcid.split(':')

        if '.' in name:
            curclass, shortname = name.split('.', 1)
        else:
            curclass, shortname = '', name
        if curclass != prevclass:
            if curclass:
                lines.append('class %s(...):' % curclass)
                indent = ' ' * 4
            else:
                indent = ''
            prevclass = curclass

        lines.append(format_sig(funcid, shortname, indent, pretty))
    return '\n'.join(lines)


def format_sig(funcid, fname, indent, pretty, defaults=[]):
    # to get defaults, parse the function, get the nodes for the
    # defaults, then unparse them
    fn_ast = ast.parse(func_source_db[funcid].strip()).body[0]
    defaults_nodes = fn_ast.args.defaults
    # for now, we're not going to care about kw_only args

    def unparse(node):
        buf = StringIO()
        Unparser(node, buf)
        return buf.getvalue().strip()

    defaults = [unparse(dn) for dn in defaults_nodes]

    lines = []
    args = []
    kwargs = []

    # Sort argid set by index.
    argids = sorted(func_argid_db[funcid], key=lambda x: x[0])

    # pad defaults to match the length of args
    defaults = ([None] * (len(argids) - len(defaults))) + defaults

    for (i, arg), default in zip(argids, defaults):
        if i == 0 and arg == 'self':
            # Omit type of self argument.
            t = ''
        else:
            t = ': %s' % func_arg_db[(funcid, i)]
        argstr = '%s%s' % (arg, t)
        if default:
            argstr += ' = %s' % default
        if i >= 0:
            args.append(argstr)
        else:
            kwargs.append(argstr)
    ret = str(func_return_db.get(funcid, Unknown()))

    sig = 'def %s(%s) -> %s' % (fname, ', '.join(args + kwargs), ret)
    if not pretty or len(sig) <= PREFERRED_LINE_LENGTH or not args:
        lines.append(indent + sig)
    else:
        # Format into multiple lines to conserve horizontal space.
        first = 'def %s(' % fname
        if args[0] == 'self':
            first += 'self,'
            args = args[1:]
        lines.append(indent + first)
        for arg in args:
            lines.append(indent + ' ' * 8 + '%s,' % arg)
        if len(lines[-1]) + 4 + len(ret) <= PREFERRED_LINE_LENGTH:
            lines[-1] = lines[-1][:-1] + ') -> %s' % ret
        else:
            lines.append(indent + ' ' * 8 + ') -> %s' % ret)
    return '\n'.join(lines)

def annotate_file(path):
    # this should be documented somewhere...
    INDENT_TOKEN = 5

    with open(path, 'r') as targetfile:
        source = targetfile.read()

    line_offsets = []
    source_length = 0
    for line in source.split('\n'):
        line_offsets.append(source_length)
        source_length = source_length + len(line) + 1

    funcids = set(funcid for funcid, arg in func_arg_db)
    funcid_components = ((funcid, funcid.split(':')) for funcid in funcids)
    funcs = (
        (funcid, name.split('.')[-1], int(sourceline), func_source_db[funcid])
        for (funcid, (name, sourcefile, sourceline)) in funcid_components
        if sourcefile == path
    )

    # list of (oldstart, oldend, replacement)
    replacements = [] # type: List[Tuple[Int, Int, String]]

    for (funcid, name, def_start_line, func_source) in funcs:
        tokens = list(tokenize.generate_tokens(StringIO(func_source).readline))
        assert len(tokens) > 0

        # we're making the assumption that the def at least gets to start on
        # it's own line, which is fine for non-lambdas

        if tokens[0][0] == INDENT_TOKEN:
            indent = tokens[0][1]
            del tokens[0]
        else:
            indent = ''

        # Find the first indent, which should be between the end of the def
        # and before the start of the body.  Then find the preceding colon,
        # which should be at the end of the def.

        for indent_loc in range(len(tokens)):
            if tokens[indent_loc][0] == INDENT_TOKEN:
                function_is_one_line = False
                break
            else:
                function_is_one_line = True

        if function_is_one_line:
            # we're also making the assumption that the def has an indent on the
            # line following the signature, which is true almost all of the time.
            # If this is not the case, we should just leave a comment above the
            # function, although I might not have time to do that now.
            continue

        for def_end_loc in range(indent_loc, -1, -1):
            if tokens[def_end_loc][1] == ':':
                break

        assert def_end_loc > 0

        def_end_line, def_end_col = tokens[def_end_loc][2]
        def_end_line -= 1 # the tokenizer apparently 1-indexes lines
        def_end_line += def_start_line

        def_start_offset = line_offsets[def_start_line]
        def_end_offset = line_offsets[def_end_line] + def_end_col

        annotated_def = format_sig(funcid, name, indent, True)

        replacements.append((def_start_offset, def_end_offset, annotated_def))

    # ideally, we'd put this after the docstring
    replacements.append((0, 0, "from typing import List, Dict, Set, Tuple, Function, Pattern, Match, Union, Optional\n"))

    # absurdly inefficient algorithm: replace with O(n) writer

    for (start, end, replacement) in sorted(replacements, key=lambda r:r[0], reverse=True):
        source = source[0:start] + replacement + source[end:]

    return source


def dump():
    s = format_state(pretty=True)
    if s:
        print()
        print('INFERRED TYPES:')
        print(s)
    reset()


def dump_at_exit():
    import atexit
    atexit.register(dump)


def infer_var(name, value):
    key = (None, name)
    update_var_db(key, value)


def infer_attrs(x):
    if hasattr(x, '__class__'):
        t = x.__class__
    else:
        t = type(x)
    cls = t.__name__
    typedict = t.__dict__
    for dict in x.__dict__, typedict:
        for attr, value in dict.items():
            if attr in ('__dict__', '__doc__', '__module__', '__weakref__'):
                continue
            if type(value) is type(infer_attrs) and dict is typedict:
                # Skip methods.
                continue
            key = (None, '%s.%s' % (cls, attr))
            update_var_db(key, value)


def infer_signature(func):
    """Decorator that infers the signature of a function."""
    return infer_method_signature('')(func)

def infer_method_signature(class_name):
    """Construct a function decorator that infer the signature of a function.
    """
    def outer_wrapper(func):
        # infer_method_signature should be idempotent
        if hasattr(func, '__is_inferring_sig'):
            return func

        assert func.__module__ != infer_method_signature.__module__

        try:
            funcfile = inspect.getfile(func)
            funcsource, sourceline = inspect.getsourcelines(func)
            sourceline -= 1  # getsourcelines is apparently 1-indexed
        except:
            return func

        name = func.__name__
        if class_name:
            name = '%s.%s' % (class_name, name)

        name = ':'.join([name, funcfile, str(sourceline)])
        func_source_db[name] = ''.join(funcsource)

        try:
            if hasattr(inspect, 'getfullargspec'):
                argspec = inspect.getfullargspec(func)
                argnames = argspec.args
                varargs = argspec.varargs
                varkw = argspec.varkw
                defaults = argspec.defaults
                kwonlyargs = argspec.kwonlyargs

            else:
                argspec = inspect.getargspec(func)
                argnames = argspec.args
                varargs = argspec.varargs
                varkw = argspec.keywords
                defaults = argspec.defaults
                kwonlyargs = []

        except TypeError:
            # Not supported.
            return func
        min_arg_count = len(argnames)
        if defaults:
            min_arg_count -= len(defaults)

        def wrapper(*args, **kwargs):
            global is_performing_inference
            # If we're already doing inference, we should be in our own code, not code we're checking.
            # Not doing this check sometimes results in infinite recursion.

            if is_performing_inference:
                return func(*args, **kwargs)

            is_performing_inference = True

            got_type_error, got_exception = False, False
            try:
                # collect arg ids and types
                argids = set()
                arg_db = {}
                expecting_type_error = False

                used_kwargs = set()
                for i, arg in enumerate(argnames):
                    if i < len(args):
                        argvalue = args[i]
                    elif arg in kwargs:
                        argvalue = kwargs[arg]
                        used_kwargs.add(arg)
                    elif i >= min_arg_count:
                        argvalue = defaults[i - min_arg_count]
                    else:
                        # we should get here when we call a function with fewer arguments
                        # than min_arg_count, and no keyword arguments to cover the required
                        # unpassed positional arguments.
                        # We should get a TypeError when we do the call
                        expecting_type_error = True
                        continue
                    key = (name, i)
                    update_db(arg_db, key, argvalue)
                    argids.add((i, arg))
                if varargs:
                    for i in range(len(argnames), len(args)):
                        key = (name, len(argnames))
                        update_db(arg_db, key, args[i])
                        argids.add((len(argnames), varargs))
                if kwonlyargs:
                    used_kwonlyargs = set()
                    for arg, value in kwargs.items():
                        if arg in kwonlyargs:
                            index = len(argnames) + kwonlyargs.index(arg)
                            key = (name, index)
                            update_db(arg_db, key, value)
                            argids.add((index, arg))
                            used_kwargs.add(arg)
                            used_kwonlyargs.add(arg)
                    for i, arg in enumerate(kwonlyargs):
                        if arg not in used_kwonlyargs:
                            index = len(argnames) + i
                            key = (name, index)
                            update_db(arg_db, key,
                                      argspec.kwonlydefaults[arg])
                            argids.add((index, arg))
                if kwargs:
                    for arg, value in kwargs.items():
                        if arg not in used_kwargs:
                            key = (name, -1)
                            update_db(arg_db, key, value)
                            argids.add((-1, varkw))
            except:
                got_type_error = got_exception = True
            finally:
                is_performing_inference = False

            try:
                ret = func(*args, **kwargs)
            except TypeError:
                got_type_error = got_exception = True
                raise
            except:
                got_exception = True
                raise
            finally:
                if not got_exception:
                    assert (not got_type_error) or expecting_type_error

                    # if we didn't get a TypeError, update the actual databases
                    func_argid_db.setdefault(name, set()).update(argids)
                    merge_db(func_arg_db, arg_db)

                    # if we got an exception, we don't have a ret
                    if not got_exception:
                        is_performing_inference = True
                        try:
                            update_db(func_return_db, name, ret)
                        except:
                            pass
                        finally:
                            is_performing_inference = False

            return ret

        if hasattr(func, '__name__'):
            wrapper.__name__ = func.__name__
        wrapper.__is_inferring_sig = True
        return wrapper
    return outer_wrapper


def infer_class(cls):
    """Class decorator for inferring signatures of all methods of the class."""
    for attr, value in cls.__dict__.items():
        if type(value) is type(infer_class):
            setattr(cls, attr, infer_method_signature(cls.__name__)(value))
    return cls


def infer_module(namespace):
    if hasattr(namespace, '__dict__'):
        namespace = namespace.__dict__
    for name, value in list(namespace.items()):
        if inspect.isfunction(value):
            namespace[name] = infer_signature(value)
        elif inspect.isclass(value):
            namespace[name] = infer_class(value)


def update_var_db(key, value):
    update_db(var_db, key, value)


def update_db(db, key, value):
    type = infer_value_type(value)
    if key not in db:
        db[key] = type
    else:
        db[key] = combine_types(db[key], type)

def merge_db(db, other):
    assert id(db) != id(other)
    for key in other.keys():
        if key not in db:
            db[key] = other[key]
        else:
            db[key] = combine_types(db[key], other[key])


def infer_value_type(value, depth=0):
    # Prevent infinite recursion
    if depth > 5:
        return Unknown()
    depth += 1

    if value is None:
        return None
    elif isinstance(value, list):
        return Generic('List', [infer_value_types(value, depth)])
    elif isinstance(value, dict):
        keytype = infer_value_types(value.keys(), depth)
        valuetype = infer_value_types(value.values(), depth)
        return Generic('Dict', (keytype, valuetype))
    elif isinstance(value, tuple):
        if len(value) <= MAX_INFERRED_TUPLE_LENGTH:
            return Tuple(infer_value_type(item, depth)
                         for item in value)
        else:
            return Generic('TupleSequence', [infer_value_types(value, depth)])
    elif isinstance(value, set):
        return Generic('Set', [infer_value_types(value, depth)])
    elif isinstance(value, types.MethodType) or isinstance(value, types.FunctionType):
        return Instance(Function)
    else:
        return Instance(type(value))


def infer_value_types(values, depth=0):
    """Infer a single type for an iterable of values.

    >>> infer_value_types((1, 'x'))
    Union(int, str)
    >>> infer_value_types([])
    Unknown
    """
    inferred = Unknown()
    for value in sample(values):
        type = infer_value_type(value, depth)
        inferred = combine_types(inferred, type)
    return inferred


def sample(values):
    # TODO only return a sample of values
    return list(values)


def combine_types(x, y):
    """Perform a union of two types.

    >>> combine_types(Instance(int), None)
    Optional[int]
    """
    if isinstance(x, Unknown):
        return y
    if isinstance(y, Unknown):
        return x
    if isinstance(x, Union):
        return combine_either(x, y)
    if isinstance(y, Union):
        return combine_either(y, x)
    if x == y:
        return x
    return simplify_either([x], [y])


def combine_either(either, x):
    if isinstance(x, Union):
        xtypes = x.types
    else:
        xtypes = [x]
    return simplify_either(either.types, xtypes)

def simplify_either(x, y):
    numerics = [Instance(int), Instance(float), Instance(complex)]

    # TODO this is O(n**2); use an O(n) algorithm instead
    result = list(x)
    for type in y:
        if isinstance(type, Generic):
            for i, rt in enumerate(result):
                if isinstance(rt, Generic) and type.typename == rt.typename:
                    result[i] = Generic(rt.typename,
                                        (combine_types(t, s)
                                         for t, s in zip(type.args, rt.args)))
                    break
            else:
                result.append(type)
        elif isinstance(type, Tuple):
            for i, rt in enumerate(result):
                if isinstance(rt, Tuple) and len(type) == len(rt):
                    result[i] = Tuple(combine_types(t, s)
                                      for t, s in zip(type.itemtypes,
                                                      rt.itemtypes))
                    break
            else:
                result.append(type)
        elif type in numerics:
            for i, rt in enumerate(result):
                if rt in numerics:
                    result[i] = numerics[max(numerics.index(rt), numerics.index(type))]
                    break
            else:
                result.append(type)
        elif isinstance(type, Instance):
            for i, rt in enumerate(result):
                if isinstance(rt, Instance):
                    # Union[A, SubclassOfA] -> A
                    # Union[A, A] -> A, because issubclass(A, A) == True,
                    if issubclass(type.typeobj, rt.typeobj):
                        break
                    elif issubclass(rt.typeobj, type.typeobj):
                        result[i] = type
                        break
            else:
                result.append(type)
        elif type not in result:
            result.append(type)

    if len(result) > 1:
        return Union(result)
    else:
        return result[0]


class TypeBase(object):
    """Abstract base class of all type objects.

    Type objects use isinstance tests librarally -- they don't support duck
    typing well.
    """
    
    def __eq__(self, other):
        if type(other) is not type(self):
            return False
        for attr in self.__dict__:
            if getattr(other, attr) != getattr(self, attr):
                return False
        return True
    
    def __ne__(self, other):
        return not self == other

    def __repr__(self):
        return str(self)


class Instance(TypeBase):
    def __init__(self, typeobj):
        assert not inspect.isclass(typeobj) or not issubclass(typeobj, TypeBase)
        self.typeobj = typeobj

    def __str__(self):
        # cheat on regular expression objects which have weird class names
        # to be consistent with typing.py
        if self.typeobj == Pattern:
            return "Pattern"
        elif self.typeobj == Match:
            return "Match"
        else:
            return self.typeobj.__name__

    def __repr__(self):
        return 'Instance(%s)' % self


class Generic(TypeBase):
    def __init__(self, typename, args):
        self.typename = typename
        self.args = tuple(args)

    def __str__(self):
        return '%s[%s]' % (self.typename, ', '.join(str(t)
                                                    for t in self.args))


class Tuple(TypeBase):
    def __init__(self, itemtypes):
        self.itemtypes = tuple(itemtypes)

    def __len__(self):
        return len(self.itemtypes)

    def __str__(self):
        return 'Tuple[%s]' % (', '.join(str(t) for t in self.itemtypes))


class Union(TypeBase):
    def __init__(self, types):
        assert len(types) > 1
        self.types = tuple(types)

    def __eq__(self, other):
        if type(other) is not Union:
            return False
        # TODO this is O(n**2); use an O(n) algorithm instead
        for t in self.types:
            if t not in other.types:
                return False
        for t in other.types:
            if t not in self.types:
                return False
        return True

    def __str__(self):
        types = list(self.types)
        if str != bytes: # on Python 2 str == bytes
            if Instance(bytes) in types and Instance(str) in types:
                # we Union[bytes, str] -> AnyStr as late as possible so we avoid
                # corner cases like subclasses of bytes or str
                types.remove(Instance(bytes))
                types.remove(Instance(str))
                types.append(Instance(AnyStr))
        if len(types) == 1:
            return str(types[0])
        elif len(types) == 2 and None in types:
            type = [t for t in types if t is not None][0]
            return 'Optional[%s]' % type
        else:
            return 'Union[%s]' % (', '.join(sorted(str(t) for t in types)))


class Unknown(TypeBase):
    def __str__(self):
        return 'Unknown'

    def __repr__(self):
        return 'Unknown()'


class AnyStr(object): pass
class Function(object): pass
import re
Pattern = type(re.compile(u''))
Match = type(re.match(u'', u''))
