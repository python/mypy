# from Python 3's inspect.py
# Copyright (c) 2001, 2002, 2003, 2004, 2005, 2006, 2007, 2008, 2009, 2010,
# 2011, 2012, 2013, 2014 Python Software Foundation; All Rights Reserved
'''
provide getfullargspec() and getcallargs() for Python 2
'''

import sys
import inspect

if sys.version_info.major == 2:

    def getfullargspec(func):
        (args, varargs, keywords, defaults) = inspect.getargspec(func)
        return (args, varargs, keywords, defaults, [], [], {})


    def getcallargs(*func_and_positional, **named):
        """Get the mapping of arguments to values.

        A dict is returned, with keys the function argument names (including the
        names of the * and ** arguments, if any), and values the respective bound
        values from 'positional' and 'named'."""
        func = func_and_positional[0]
        positional = func_and_positional[1:]
        spec = getfullargspec(func)
        args, varargs, varkw, defaults, kwonlyargs, kwonlydefaults, ann = spec
        f_name = func.__name__
        arg2value = {}


        if inspect.ismethod(func) and func.__self__ is not None:
            # implicit 'self' (or 'cls' for classmethods) argument
            positional = (func.__self__,) + positional
        num_pos = len(positional)
        num_args = len(args)
        num_defaults = len(defaults) if defaults else 0

        n = min(num_pos, num_args)
        for i in range(n):
            arg2value[args[i]] = positional[i]
        if varargs:
            arg2value[varargs] = tuple(positional[n:])
        possible_kwargs = set(args + kwonlyargs)
        if varkw:
            arg2value[varkw] = {}
        for kw, value in named.items():
            if kw not in possible_kwargs:
                if not varkw:
                    raise TypeError("%s() got an unexpected keyword argument %r" %
                                    (f_name, kw))
                arg2value[varkw][kw] = value
                continue
            if kw in arg2value:
                raise TypeError("%s() got multiple values for argument %r" %
                                (f_name, kw))
            arg2value[kw] = value
        if num_pos > num_args and not varargs:
            _too_many(f_name, args, kwonlyargs, varargs, num_defaults,
                       num_pos, arg2value)
        if num_pos < num_args:
            req = args[:num_args - num_defaults]
            for arg in req:
                if arg not in arg2value:
                    _missing_arguments(f_name, req, True, arg2value)
            for i, arg in enumerate(args[num_args - num_defaults:]):
                if arg not in arg2value:
                    arg2value[arg] = defaults[i]
        missing = 0
        for kwarg in kwonlyargs:
            if kwarg not in arg2value:
                if kwonlydefaults and kwarg in kwonlydefaults:
                    arg2value[kwarg] = kwonlydefaults[kwarg]
                else:
                    missing += 1
        if missing:
            _missing_arguments(f_name, kwonlyargs, False, arg2value)
        return arg2value


    def _too_many(f_name, args, kwonly, varargs, defcount, given, values):
        atleast = len(args) - defcount
        kwonly_given = len([arg for arg in kwonly if arg in values])
        if varargs:
            plural = atleast != 1
            sig = "at least %d" % (atleast,)
        elif defcount:
            plural = True
            sig = "from %d to %d" % (atleast, len(args))
        else:
            plural = len(args) != 1
            sig = str(len(args))
        kwonly_sig = ""
        if kwonly_given:
            msg = " positional argument%s (and %d keyword-only argument%s)"
            kwonly_sig = (msg % ("s" if given != 1 else "", kwonly_given,
                                 "s" if kwonly_given != 1 else ""))
        raise TypeError("%s() takes %s positional argument%s but %d%s %s given" %
                (f_name, sig, "s" if plural else "", given, kwonly_sig,
                 "was" if given == 1 and not kwonly_given else "were"))


    def _missing_arguments(f_name, argnames, pos, values):
        names = [repr(name) for name in argnames if name not in values]
        missing = len(names)
        if missing == 1:
            s = names[0]
        elif missing == 2:
            s = "{} and {}".format(*names)
        else:
            tail = ", {} and {}".format(*names[-2:])
            del names[-2:]
            s = ", ".join(names) + tail
        raise TypeError("%s() missing %i required %s argument%s: %s" %
                        (f_name, missing,
                          "positional" if pos else "keyword-only",
                          "" if missing == 1 else "s", s))


else:
    getfullargspec = inspect.getfullargspec
    getcallargs = inspect.getcallargs
