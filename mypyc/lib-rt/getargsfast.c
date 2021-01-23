/* getargskeywordsfast implementation copied from Python 3.9 and stripped down to
 * only include the functionality we need.
 *
 * We also add support for required kwonly args and accepting *args / **kwargs.
 *
 * DOCUMENTATION OF THE EXTENSIONS:
 *  - Arguments given after a @ format specify required keyword-only arguments.
 *    The | and $ specifiers must both appear before @.
 *  - If the first character of a format string is %, then the function can support
 *    *args and/or **kwargs. In this case the parser will consume two arguments,
 *    which should be pointers to variables to store the *args and **kwargs, respectively.
 *    Either pointer can be NULL, in which case the function doesn't take that
 *    variety of vararg.
 *    Unlike most format specifiers, the caller takes ownership of these objects
 *    and is responsible for decrefing them.
 */

#include <Python.h>
#include "CPy.h"

/* None of this is supported on Python 3.6 or earlier */
#if PY_VERSION_HEX >= 0x03070000

#define FLAG_SIZE_T 2

typedef int (*destr_t)(PyObject *, void *);

/* Keep track of "objects" that have been allocated or initialized and
   which will need to be deallocated or cleaned up somehow if overall
   parsing fails.
*/
typedef struct {
  void *item;
  destr_t destructor;
} freelistentry_fast_t;

typedef struct {
  freelistentry_fast_t *entries;
  int first_available;
  int entries_malloced;
} freelist_fast_t;

#define STATIC_FREELIST_ENTRIES 8

/* Forward */
static int
vgetargskeywordsfast_impl(PyObject *const *args, Py_ssize_t nargs,
                          PyObject *kwargs, PyObject *kwnames,
                          CPyArg_Parser *parser,
                          va_list *p_va, int flags);
static const char *skipitem_fast(const char **, va_list *, int);
static void seterror_fast(Py_ssize_t, const char *, int *, const char *, const char *);
static const char *convertitem_fast(PyObject *, const char **, va_list *, int, int *,
                                    char *, size_t, freelist_fast_t *);
static const char *convertsimple_fast(PyObject *, const char **, va_list *, int,
                                      char *, size_t, freelist_fast_t *);

/* Parse args for an arbitrary signature */
int
CPyArg_ParseStackAndKeywords(PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames,
                             CPyArg_Parser *parser, ...)
{
    int retval;
    va_list va;

    va_start(va, parser);
    retval = vgetargskeywordsfast_impl(args, nargs, NULL, kwnames, parser, &va, 0);
    va_end(va);
    return retval;
}

/* Parse args for a function that takes no args */
int
CPyArg_ParseStackAndKeywordsNoArgs(PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames,
                                   CPyArg_Parser *parser, ...)
{
    int retval;
    va_list va;

    va_start(va, parser);
    if (nargs == 0 && kwnames == NULL) {
        // Fast path: no arguments
        retval = 1;
    } else {
        retval = vgetargskeywordsfast_impl(args, nargs, NULL, kwnames, parser, &va, 0);
    }
    va_end(va);
    return retval;
}

/* Parse args for a function that takes one arg */
int
CPyArg_ParseStackAndKeywordsOneArg(PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames,
                                   CPyArg_Parser *parser, ...)
{
    int retval;
    va_list va;

    va_start(va, parser);
    if (kwnames == NULL && nargs == 1) {
        // Fast path: one positional argument
        PyObject **p;
        p = va_arg(va, PyObject **);
        *p = args[0];
        retval = 1;
    } else {
        retval = vgetargskeywordsfast_impl(args, nargs, NULL, kwnames, parser, &va, 0);
    }
    va_end(va);
    return retval;
}

/* Parse args for a function that takes no keyword-only args, *args or **kwargs */
int
CPyArg_ParseStackAndKeywordsSimple(PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames,
                                   CPyArg_Parser *parser, ...)
{
    int retval;
    va_list va;

    va_start(va, parser);
    if (kwnames == NULL && nargs >= parser->min && nargs <= parser->max) {
        // Fast path: correct number of positional arguments only
        PyObject **p;
        for (Py_ssize_t i = 0; i < nargs; i++) {
            p = va_arg(va, PyObject **);
            *p = args[i];
        }
        retval = 1;
    } else {
        retval = vgetargskeywordsfast_impl(args, nargs, NULL, kwnames, parser, &va, 0);
    }
    va_end(va);
    return retval;
}

static int
cleanreturn_fast(int retval, freelist_fast_t *freelist)
{
    int index;

    if (retval == 0) {
      /* A failure occurred, therefore execute all of the cleanup
         functions.
      */
      for (index = 0; index < freelist->first_available; ++index) {
          freelist->entries[index].destructor(NULL,
                                              freelist->entries[index].item);
      }
    }
    if (freelist->entries_malloced)
        PyMem_FREE(freelist->entries);
    return retval;
}

#define IS_END_OF_FORMAT(c) (c == '\0' || c == ';' || c == ':')


/* List of static parsers. */
static struct CPyArg_Parser *static_arg_parsers = NULL;

static int
parser_init(CPyArg_Parser *parser)
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

    parser->required_kwonly_start = INT_MAX;
    if (*parser->format == '%') {
        parser->format++;
        parser->varargs = 1;
    }

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
            if (*format == '@') {
                if (parser->required_kwonly_start != INT_MAX) {
                    PyErr_SetString(PyExc_SystemError,
                                    "Invalid format string (@ specified twice)");
                    return 0;
                }
                if (min == INT_MAX && max == INT_MAX) {
                    PyErr_SetString(PyExc_SystemError,
                                    "Invalid format string "
                                    "(@ without preceding | and $)");
                    return 0;
                }
                format++;
                parser->has_required_kws = 1;
                parser->required_kwonly_start = i;
            }
            if (IS_END_OF_FORMAT(*format)) {
                PyErr_Format(PyExc_SystemError,
                            "More keyword list entries (%d) than "
                            "format specifiers (%d)", len, i);
                return 0;
            }

            msg = skipitem_fast(&format, NULL, 0);
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
                          CPyArg_Parser *parser,
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
    freelistentry_fast_t static_entries[STATIC_FREELIST_ENTRIES];
    freelist_fast_t freelist;
    PyObject *const *kwstack = NULL;
    int bound_pos_args;
    PyObject **p_args = NULL, **p_kwargs = NULL;

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

    if (parser->varargs) {
        p_args = va_arg(*p_va, PyObject **);
        p_kwargs = va_arg(*p_va, PyObject **);
    }

    if (len > STATIC_FREELIST_ENTRIES) {
        freelist.entries = PyMem_NEW(freelistentry_fast_t, len);
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
    if (nargs + nkwargs > len && !p_args && !p_kwargs) {
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
        return cleanreturn_fast(0, &freelist);
    }
    if (parser->max < nargs && !p_args) {
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
        return cleanreturn_fast(0, &freelist);
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
        if (*format == '@') {
            format++;
        }
        assert(!IS_END_OF_FORMAT(*format));

        if (i < nargs && i < parser->max) {
            current_arg = args[i];
        }
        else if (nkwargs && i >= pos) {
            keyword = PyTuple_GET_ITEM(kwtuple, i - pos);
            if (kwargs != NULL) {
                current_arg = PyDict_GetItemWithError(kwargs, keyword);
                if (!current_arg && PyErr_Occurred()) {
                    return cleanreturn_fast(0, &freelist);
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
            msg = convertitem_fast(current_arg, &format, p_va, flags,
                levels, msgbuf, sizeof(msgbuf), &freelist);
            if (msg) {
                seterror_fast(i+1, msg, levels, parser->fname, parser->custom_msg);
                return cleanreturn_fast(0, &freelist);
            }
            continue;
        }

        if (i < parser->min || i >= parser->required_kwonly_start) {
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
                if (i >= parser->max) {
                    PyErr_Format(PyExc_TypeError,  "%.200s%s missing required "
                                 "keyword-only argument '%U'",
                                 (parser->fname == NULL) ? "function" : parser->fname,
                                 (parser->fname == NULL) ? "" : "()",
                                 keyword);
                }
                else {
                    PyErr_Format(PyExc_TypeError,  "%.200s%s missing required "
                                 "argument '%U' (pos %d)",
                                 (parser->fname == NULL) ? "function" : parser->fname,
                                 (parser->fname == NULL) ? "" : "()",
                                 keyword, i+1);
                }
            }
            return cleanreturn_fast(0, &freelist);
        }
        /* current code reports success when all required args
         * fulfilled and no keyword args left, with no further
         * validation. XXX Maybe skip this in debug build ?
         */
        if (!nkwargs && !parser->has_required_kws && !p_args && !p_kwargs) {
            return cleanreturn_fast(1, &freelist);
        }

        /* We are into optional args, skip through to any remaining
         * keyword args */
        msg = skipitem_fast(&format, p_va, flags);
        assert(msg == NULL);
    }

    assert(IS_END_OF_FORMAT(*format) || (*format == '|') || (*format == '$'));

    bound_pos_args = Py_MIN(nargs, Py_MIN(parser->max, len));
    if (p_args) {
        *p_args = PyTuple_New(nargs - bound_pos_args);
        if (!*p_args) {
            return cleanreturn_fast(0, &freelist);
        }
        for (i = bound_pos_args; i < nargs; i++) {
            PyObject *arg = args[i];
            Py_INCREF(arg);
            PyTuple_SET_ITEM(*p_args, i - bound_pos_args, arg);
        }
    }

    if (p_kwargs) {
        /* This unfortunately needs to be special cased because if len is 0 then we
         * never go through the main loop. */
        if (nargs > 0 && len == 0 && !p_args) {
            PyErr_Format(PyExc_TypeError,
                         "%.200s%s takes no positional arguments",
                         (parser->fname == NULL) ? "function" : parser->fname,
                         (parser->fname == NULL) ? "" : "()");

            return cleanreturn_fast(0, &freelist);
        }

        *p_kwargs = PyDict_New();
        if (!*p_kwargs) {
            goto latefail;
        }
    }

    if (nkwargs > 0) {
        Py_ssize_t j;
        PyObject *value;
        /* make sure there are no arguments given by name and position */
        for (i = pos; i < bound_pos_args; i++) {
            keyword = PyTuple_GET_ITEM(kwtuple, i - pos);
            if (kwargs != NULL) {
                current_arg = PyDict_GetItemWithError(kwargs, keyword);
                if (!current_arg && PyErr_Occurred()) {
                    goto latefail;
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
                goto latefail;
            }
        }
        /* make sure there are no extraneous keyword arguments */
        j = 0;
        while (1) {
            int match;
            if (kwargs != NULL) {
                if (!PyDict_Next(kwargs, &j, &keyword, &value))
                    break;
            }
            else {
                if (j >= PyTuple_GET_SIZE(kwnames))
                    break;
                keyword = PyTuple_GET_ITEM(kwnames, j);
                value = kwstack[j];
                j++;
            }

            match = PySequence_Contains(kwtuple, keyword);
            if (match <= 0) {
                if (!match) {
                    if (!p_kwargs) {
                        PyErr_Format(PyExc_TypeError,
                                     "'%S' is an invalid keyword "
                                     "argument for %.200s%s",
                                     keyword,
                                     (parser->fname == NULL) ? "this function" : parser->fname,
                                     (parser->fname == NULL) ? "" : "()");
                        goto latefail;
                    } else {
                        if (PyDict_SetItem(*p_kwargs, keyword, value) < 0) {
                            goto latefail;
                        }
                    }
                } else {
                    goto latefail;
                }
            }
        }
    }

    return cleanreturn_fast(1, &freelist);
    /* Handle failures that have happened after we have tried to
     * create *args and **kwargs, if they exist. */
latefail:
    if (p_args) {
        Py_XDECREF(*p_args);
    }
    if (p_kwargs) {
        Py_XDECREF(*p_kwargs);
    }
    return cleanreturn_fast(0, &freelist);
}

static const char *
skipitem_fast(const char **p_format, va_list *p_va, int flags)
{
    const char *format = *p_format;
    char c = *format++;

    switch (c) {
    case 'O': /* object */
        {
            if (p_va != NULL) {
                (void) va_arg(*p_va, PyObject **);
            }
            break;
        }

    default:
err:
        return "impossible<bad format char>";
    }

    *p_format = format;
    return NULL;
}

static void
seterror_fast(Py_ssize_t iarg, const char *msg, int *levels, const char *fname,
              const char *message)
{
    char buf[512];
    int i;
    char *p = buf;

    if (PyErr_Occurred())
        return;
    else if (message == NULL) {
        if (fname != NULL) {
            PyOS_snprintf(p, sizeof(buf), "%.200s() ", fname);
            p += strlen(p);
        }
        if (iarg != 0) {
            PyOS_snprintf(p, sizeof(buf) - (p - buf),
                          "argument %" PY_FORMAT_SIZE_T "d", iarg);
            i = 0;
            p += strlen(p);
            while (i < 32 && levels[i] > 0 && (int)(p-buf) < 220) {
                PyOS_snprintf(p, sizeof(buf) - (p - buf),
                              ", item %d", levels[i]-1);
                p += strlen(p);
                i++;
            }
        }
        else {
            PyOS_snprintf(p, sizeof(buf) - (p - buf), "argument");
            p += strlen(p);
        }
        PyOS_snprintf(p, sizeof(buf) - (p - buf), " %.256s", msg);
        message = buf;
    }
    if (msg[0] == '(') {
        PyErr_SetString(PyExc_SystemError, message);
    }
    else {
        PyErr_SetString(PyExc_TypeError, message);
    }
}


/* Convert a single item. */

static const char *
convertitem_fast(PyObject *arg, const char **p_format, va_list *p_va, int flags,
                 int *levels, char *msgbuf, size_t bufsize, freelist_fast_t *freelist)
{
    const char *msg;
    const char *format = *p_format;

    msg = convertsimple_fast(arg, &format, p_va, flags,
                        msgbuf, bufsize, freelist);
    if (msg != NULL)
        levels[0] = 0;
    if (msg == NULL)
        *p_format = format;
    return msg;
}

static const char *
converterr_fast(const char *expected, PyObject *arg, char *msgbuf, size_t bufsize)
{
    assert(expected != NULL);
    assert(arg != NULL);
    if (expected[0] == '(') {
        PyOS_snprintf(msgbuf, bufsize,
                      "%.100s", expected);
    }
    else {
        PyOS_snprintf(msgbuf, bufsize,
                      "must be %.50s, not %.50s", expected,
                      arg == Py_None ? "None" : Py_TYPE(arg)->tp_name);
    }
    return msgbuf;
}

/* Convert a non-tuple argument.  Return NULL if conversion went OK,
   or a string with a message describing the failure.  The message is
   formatted as "must be <desired type>, not <actual type>".
   When failing, an exception may or may not have been raised.
   Don't call if a tuple is expected.

   When you add new format codes, please don't forget poor skipitem_fast().
*/

static const char *
convertsimple_fast(PyObject *arg, const char **p_format, va_list *p_va, int flags,
                   char *msgbuf, size_t bufsize, freelist_fast_t *freelist)
{
    const char *format = *p_format;
    char c = *format++;
    const char *sarg;

    switch (c) {
    case 'O': { /* object */
        PyTypeObject *type;
        PyObject **p;
        p = va_arg(*p_va, PyObject **);
        *p = arg;
        break;
    }

    default:
        return converterr_fast("(impossible<bad format char>)", arg, msgbuf, bufsize);
    }

    *p_format = format;
    return NULL;
}

#endif
