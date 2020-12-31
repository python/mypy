#include <Python.h>

static int
vgetargskeywordsfast_impl(PyObject *const *args, Py_ssize_t nargs,
                          PyObject *kwargs, PyObject *kwnames,
                          struct _PyArg_Parser *parser,
                          va_list *p_va, int flags);

int
CPyArg_ParseStackAndKeywords(PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames,
                             struct _PyArg_Parser *parser, ...)
{
    int retval;
    va_list va;

    va_start(va, parser);
    retval = vgetargskeywordsfast_impl(args, nargs, NULL, kwnames, parser, &va, 0);
    va_end(va);
    return retval;
}


/* List of static parsers. */
static struct _PyArg_Parser *static_arg_parsers = NULL;

static int
parser_init(struct _PyArg_Parser *parser)
{
    const char * const *keywords;
    const char *format, *msg;
    int i, len, min, max, nkw;
    PyObject *kwtuple;

    assert(parser->keywords != NULL);
    if (parser->kwtuple != NULL) {
        return 1;
    }

    keywords = parser->keywords;
    /* scan keywords and count the number of positional-only parameters */
    for (i = 0; keywords[i] && !*keywords[i]; i++) {
    }
    parser->pos = i;
    /* scan keywords and get greatest possible nbr of args */
    for (; keywords[i]; i++) {
        if (!*keywords[i]) {
            PyErr_SetString(PyExc_SystemError,
                            "Empty keyword parameter name");
            return 0;
        }
    }
    len = i;

    format = parser->format;
    if (format) {
        /* grab the function name or custom error msg first (mutually exclusive) */
        parser->fname = strchr(parser->format, ':');
        if (parser->fname) {
            parser->fname++;
            parser->custom_msg = NULL;
        }
        else {
            parser->custom_msg = strchr(parser->format,';');
            if (parser->custom_msg)
                parser->custom_msg++;
        }

        min = max = INT_MAX;
        for (i = 0; i < len; i++) {
            if (*format == '|') {
                if (min != INT_MAX) {
                    PyErr_SetString(PyExc_SystemError,
                                    "Invalid format string (| specified twice)");
                    return 0;
                }
                if (max != INT_MAX) {
                    PyErr_SetString(PyExc_SystemError,
                                    "Invalid format string ($ before |)");
                    return 0;
                }
                min = i;
                format++;
            }
            if (*format == '$') {
                if (max != INT_MAX) {
                    PyErr_SetString(PyExc_SystemError,
                                    "Invalid format string ($ specified twice)");
                    return 0;
                }
                if (i < parser->pos) {
                    PyErr_SetString(PyExc_SystemError,
                                    "Empty parameter name after $");
                    return 0;
                }
                max = i;
                format++;
            }
            if (IS_END_OF_FORMAT(*format)) {
                PyErr_Format(PyExc_SystemError,
                            "More keyword list entries (%d) than "
                            "format specifiers (%d)", len, i);
                return 0;
            }

            msg = skipitem(&format, NULL, 0);
            if (msg) {
                PyErr_Format(PyExc_SystemError, "%s: '%s'", msg,
                            format);
                return 0;
            }
        }
        parser->min = Py_MIN(min, len);
        parser->max = Py_MIN(max, len);

        if (!IS_END_OF_FORMAT(*format) && (*format != '|') && (*format != '$')) {
            PyErr_Format(PyExc_SystemError,
                "more argument specifiers than keyword list entries "
                "(remaining format:'%s')", format);
            return 0;
        }
    }

    nkw = len - parser->pos;
    kwtuple = PyTuple_New(nkw);
    if (kwtuple == NULL) {
        return 0;
    }
    keywords = parser->keywords + parser->pos;
    for (i = 0; i < nkw; i++) {
        PyObject *str = PyUnicode_FromString(keywords[i]);
        if (str == NULL) {
            Py_DECREF(kwtuple);
            return 0;
        }
        PyUnicode_InternInPlace(&str);
        PyTuple_SET_ITEM(kwtuple, i, str);
    }
    parser->kwtuple = kwtuple;

    assert(parser->next == NULL);
    parser->next = static_arg_parsers;
    static_arg_parsers = parser;
    return 1;
}

static PyObject*
find_keyword(PyObject *kwnames, PyObject *const *kwstack, PyObject *key)
{
    Py_ssize_t i, nkwargs;

    nkwargs = PyTuple_GET_SIZE(kwnames);
    for (i = 0; i < nkwargs; i++) {
        PyObject *kwname = PyTuple_GET_ITEM(kwnames, i);

        /* kwname == key will normally find a match in since keyword keys
           should be interned strings; if not retry below in a new loop. */
        if (kwname == key) {
            return kwstack[i];
        }
    }

    for (i = 0; i < nkwargs; i++) {
        PyObject *kwname = PyTuple_GET_ITEM(kwnames, i);
        assert(PyUnicode_Check(kwname));
        if (_PyUnicode_EQ(kwname, key)) {
            return kwstack[i];
        }
    }
    return NULL;
}

static int
vgetargskeywordsfast_impl(PyObject *const *args, Py_ssize_t nargs,
                          PyObject *kwargs, PyObject *kwnames,
                          struct _PyArg_Parser *parser,
                          va_list *p_va, int flags)
{
    PyObject *kwtuple;
    char msgbuf[512];
    int levels[32];
    const char *format;
    const char *msg;
    PyObject *keyword;
    int i, pos, len;
    Py_ssize_t nkwargs;
    PyObject *current_arg;
    freelistentry_t static_entries[STATIC_FREELIST_ENTRIES];
    freelist_t freelist;
    PyObject *const *kwstack = NULL;

    freelist.entries = static_entries;
    freelist.first_available = 0;
    freelist.entries_malloced = 0;

    assert(kwargs == NULL || PyDict_Check(kwargs));
    assert(kwargs == NULL || kwnames == NULL);
    assert(p_va != NULL);

    if (parser == NULL) {
        PyErr_BadInternalCall();
        return 0;
    }

    if (kwnames != NULL && !PyTuple_Check(kwnames)) {
        PyErr_BadInternalCall();
        return 0;
    }

    if (!parser_init(parser)) {
        return 0;
    }

    kwtuple = parser->kwtuple;
    pos = parser->pos;
    len = pos + (int)PyTuple_GET_SIZE(kwtuple);

    if (len > STATIC_FREELIST_ENTRIES) {
        freelist.entries = PyMem_NEW(freelistentry_t, len);
        if (freelist.entries == NULL) {
            PyErr_NoMemory();
            return 0;
        }
        freelist.entries_malloced = 1;
    }

    if (kwargs != NULL) {
        nkwargs = PyDict_GET_SIZE(kwargs);
    }
    else if (kwnames != NULL) {
        nkwargs = PyTuple_GET_SIZE(kwnames);
        kwstack = args + nargs;
    }
    else {
        nkwargs = 0;
    }
    if (nargs + nkwargs > len) {
        /* Adding "keyword" (when nargs == 0) prevents producing wrong error
           messages in some special cases (see bpo-31229). */
        PyErr_Format(PyExc_TypeError,
                     "%.200s%s takes at most %d %sargument%s (%zd given)",
                     (parser->fname == NULL) ? "function" : parser->fname,
                     (parser->fname == NULL) ? "" : "()",
                     len,
                     (nargs == 0) ? "keyword " : "",
                     (len == 1) ? "" : "s",
                     nargs + nkwargs);
        return cleanreturn(0, &freelist);
    }
    if (parser->max < nargs) {
        if (parser->max == 0) {
            PyErr_Format(PyExc_TypeError,
                         "%.200s%s takes no positional arguments",
                         (parser->fname == NULL) ? "function" : parser->fname,
                         (parser->fname == NULL) ? "" : "()");
        }
        else {
            PyErr_Format(PyExc_TypeError,
                         "%.200s%s takes %s %d positional argument%s (%zd given)",
                         (parser->fname == NULL) ? "function" : parser->fname,
                         (parser->fname == NULL) ? "" : "()",
                         (parser->min < parser->max) ? "at most" : "exactly",
                         parser->max,
                         parser->max == 1 ? "" : "s",
                         nargs);
        }
        return cleanreturn(0, &freelist);
    }

    format = parser->format;
    /* convert tuple args and keyword args in same loop, using kwtuple to drive process */
    for (i = 0; i < len; i++) {
        if (*format == '|') {
            format++;
        }
        if (*format == '$') {
            format++;
        }
        assert(!IS_END_OF_FORMAT(*format));

        if (i < nargs) {
            current_arg = args[i];
        }
        else if (nkwargs && i >= pos) {
            keyword = PyTuple_GET_ITEM(kwtuple, i - pos);
            if (kwargs != NULL) {
                current_arg = PyDict_GetItemWithError(kwargs, keyword);
                if (!current_arg && PyErr_Occurred()) {
                    return cleanreturn(0, &freelist);
                }
            }
            else {
                current_arg = find_keyword(kwnames, kwstack, keyword);
            }
            if (current_arg) {
                --nkwargs;
            }
        }
        else {
            current_arg = NULL;
        }

        if (current_arg) {
            msg = convertitem(current_arg, &format, p_va, flags,
                levels, msgbuf, sizeof(msgbuf), &freelist);
            if (msg) {
                seterror(i+1, msg, levels, parser->fname, parser->custom_msg);
                return cleanreturn(0, &freelist);
            }
            continue;
        }

        if (i < parser->min) {
            /* Less arguments than required */
            if (i < pos) {
                Py_ssize_t min = Py_MIN(pos, parser->min);
                PyErr_Format(PyExc_TypeError,
                             "%.200s%s takes %s %d positional argument%s"
                             " (%zd given)",
                             (parser->fname == NULL) ? "function" : parser->fname,
                             (parser->fname == NULL) ? "" : "()",
                             min < parser->max ? "at least" : "exactly",
                             min,
                             min == 1 ? "" : "s",
                             nargs);
            }
            else {
                keyword = PyTuple_GET_ITEM(kwtuple, i - pos);
                PyErr_Format(PyExc_TypeError,  "%.200s%s missing required "
                             "argument '%U' (pos %d)",
                             (parser->fname == NULL) ? "function" : parser->fname,
                             (parser->fname == NULL) ? "" : "()",
                             keyword, i+1);
            }
            return cleanreturn(0, &freelist);
        }
        /* current code reports success when all required args
         * fulfilled and no keyword args left, with no further
         * validation. XXX Maybe skip this in debug build ?
         */
        if (!nkwargs) {
            return cleanreturn(1, &freelist);
        }

        /* We are into optional args, skip through to any remaining
         * keyword args */
        msg = skipitem(&format, p_va, flags);
        assert(msg == NULL);
    }

    assert(IS_END_OF_FORMAT(*format) || (*format == '|') || (*format == '$'));

    if (nkwargs > 0) {
        Py_ssize_t j;
        /* make sure there are no arguments given by name and position */
        for (i = pos; i < nargs; i++) {
            keyword = PyTuple_GET_ITEM(kwtuple, i - pos);
            if (kwargs != NULL) {
                current_arg = PyDict_GetItemWithError(kwargs, keyword);
                if (!current_arg && PyErr_Occurred()) {
                    return cleanreturn(0, &freelist);
                }
            }
            else {
                current_arg = find_keyword(kwnames, kwstack, keyword);
            }
            if (current_arg) {
                /* arg present in tuple and in dict */
                PyErr_Format(PyExc_TypeError,
                             "argument for %.200s%s given by name ('%U') "
                             "and position (%d)",
                             (parser->fname == NULL) ? "function" : parser->fname,
                             (parser->fname == NULL) ? "" : "()",
                             keyword, i+1);
                return cleanreturn(0, &freelist);
            }
        }
        /* make sure there are no extraneous keyword arguments */
        j = 0;
        while (1) {
            int match;
            if (kwargs != NULL) {
                if (!PyDict_Next(kwargs, &j, &keyword, NULL))
                    break;
            }
            else {
                if (j >= PyTuple_GET_SIZE(kwnames))
                    break;
                keyword = PyTuple_GET_ITEM(kwnames, j);
                j++;
            }

            match = PySequence_Contains(kwtuple, keyword);
            if (match <= 0) {
                if (!match) {
                    PyErr_Format(PyExc_TypeError,
                                 "'%S' is an invalid keyword "
                                 "argument for %.200s%s",
                                 keyword,
                                 (parser->fname == NULL) ? "this function" : parser->fname,
                                 (parser->fname == NULL) ? "" : "()");
                }
                return cleanreturn(0, &freelist);
            }
        }
    }

    return cleanreturn(1, &freelist);
}
