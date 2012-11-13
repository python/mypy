import os.path


# Representation of a single error message.
class ErrorInfo:
    # Description of a sequence of imports that refer to the source file
    # related to this error. Each item is a (path, line number) tuple.
    list<tuple<str, int>> import_ctx
    # The source file that was the source of this error.
    str file
    # The name of the type in which this error is located at.
    str typ     # Unqualified, may be None
    # It the error located within an interface?
    bool is_interface
    # The name of the function or member in which this error is located at.
    str function_or_member     # Unqualified, may be None
    # The line number related to this error within file.
    int line     # -1 if unknown
    # The error message.
    str message
    
    # Return "interface" or "class" depending on the context of the error.
    # Call this method only if the type member != None.
    str type_id(self):
        if self.is_interface:
            return 'interface'
        else:
            return 'class'
    
    void __init__(self, list<tuple<str, int>> import_ctx, str file, str typ,
                  bool is_interface, str function_or_member, int line,
                  str message):
        self.import_ctx = import_ctx
        self.file = file
        self.typ = typ
        self.is_interface = is_interface
        self.function_or_member = function_or_member
        self.line = line
        self.message = message


# Container that generates and keeps tracks of compile errors and the current
# error context.
class Errors:
    # List of generated error messages.
    list<ErrorInfo> error_info
    
    # Current error context.
    # Import context, as a list of (path, line) pairs.
    list<tuple<str, int>> import_ctx
    # Path name prefix that is removed from all paths, if set.
    str ignore_prefix = None
    str file = None     # Path to current file.
    # Short name of current type (or None).
    str type_name = None
    # Is the current type an interface?
    bool is_interface = False
    # Short name of current function or member (or None).
    str function_or_member = None
    
    void __init__(self):
        self.error_info = []
        self.import_ctx = []
    
    # Set path prefix that will be removed from all paths.
    void set_ignore_prefix(self, str prefix):
        prefix = os.path.normpath(prefix)
        # Add separator to the end, if not given.
        if os.path.basename(prefix) != '':
            prefix += os.sep
        self.ignore_prefix = prefix
    
    # Set the path of the current file.
    void set_file(self, str file):
        file = os.path.normpath(file)
        self.file = remove_path_prefix(file, self.ignore_prefix)
    
    # Set the current function or member short name (it can be None).
    void set_function(self, str name):
        self.function_or_member = name
    
    # Set the short name of the current type (it can be None).
    void set_type(self, str name, bool is_interface):
        self.type_name = name
        self.is_interface = is_interface
    
    # Add a (file, line) tuple to the import context.
    void push_import_context(self, str path, int line):
        self.import_ctx.append((os.path.normpath(path), line))
    
    # Remove the topmost item from the import context.
    void pop_import_context(self):
        self.import_ctx.pop()
    
    # Return a copy of the import context.
    list<tuple<str, int>> import_context(self):
        return self.import_ctx[:]
    
    # Replace the entire import context with a new value.
    void set_import_context(self, list<tuple<str, int>> ctx):
        self.import_ctx = ctx[:]
    
    # Report a message at the given line using the current error context.
    void report(self, int line, str message):
        info = ErrorInfo(self.import_context(), self.file, self.type_name,
                         self.is_interface, self.function_or_member, line,
                         message)
        self.error_info.append(info)
    
    # Return the number of generated messages.
    int num_messages(self):
        return len(self.error_info)
    
    # Are there any generated errors?
    bool is_errors(self):
        return len(self.error_info) > 0
    
    # Raise a CompileError with the generated messages. Render the messages
    # suitable for displaying.
    void raise_error(self):
        raise CompileError(self.messages())
    
    # Return a string array that represents the error messages in a form
    # suitable for displaying to the user.
    list<str> messages(self):
        list<str> a = []
        errors = self.render_messages(self.sort_messages(self.error_info))
        errors = self.remove_duplicates(errors)
        for file, line, message in errors:
            str s
            if file is not None:
                if line is not None and line >= 0:
                    s = '{}, line {}: {}'.format(file, line, message)
                else:
                    s = '{}: {}'.format(file, message)
            else:
                s = message
            a.append(s)
        return a
    
    # Translate the messages into a sequence of (path, line, message) tuples.
    # The rendered sequence includes information about error contexts. The path
    # item may be None. If the line item is negative, the line number is not
    # defined for the tuple.
    list<tuple<str, int, str>> render_messages(self, list<ErrorInfo> errors):
        list<tuple<str, int, str>> result = [] # (path, line, message)
        
        list<tuple<str, int>> prev_import_context = []
        str prev_function_or_member = None
        str prev_type = None
        
        for e in errors:
            # Report module import context, if different from previous message.
            if e.import_ctx != prev_import_context:
                last = len(e.import_ctx) - 1
                i = last
                while i >= 0:
                    path, line = e.import_ctx[i]
                    fmt = 'In module imported in {}, line {}'
                    if i < last:
                        fmt = '                   in {}, line {}'
                    if i > 0:
                        fmt += ','
                    else:
                        fmt += ':'
                    # Remove prefix to ignore from path (if present) to
                    # simplify path.
                    path = remove_path_prefix(path, self.ignore_prefix)
                    result.append((None, -1, fmt.format(path, line)))
                    i -= 1
            
            # Report context within a source file.
            if (e.function_or_member != prev_function_or_member or
                    e.typ != prev_type):
                if e.function_or_member is None:
                    if e.typ is None:
                        result.append((e.file, -1, 'At top level:'))
                    else:
                        result.append((e.file, -1, 'In {} "{}":'.format(
                            e.type_id(), e.typ)))
                else:
                    if e.typ is None:
                        result.append((e.file, -1,
                                       'In function "{}":'.format(
                                           e.function_or_member)))
                    else:
                        result.append((e.file, -1,
                                       'In member "{}" of {} "{}":'.format(
                                           e.function_or_member, e.type_id(),
                                           e.typ)))
            elif e.typ != prev_type:
                if e.typ is None:
                    result.append((e.file, -1, 'At top level:'))
                else:
                    result.append((e.file, -1,
                                   'In {} "{}":'.format(e.type_id(), e.typ)))
            
            result.append((e.file, e.line, e.message))
            
            prev_import_context = e.import_ctx
            prev_function_or_member = e.function_or_member
            prev_type = e.typ
        
        return result
    
    # Sort an array of error messages locally by line number, i.e. sort a
    # run of consecutive messages with the same file context by line number,
    # but otherwise retain the general ordering of the messages.
    list<ErrorInfo> sort_messages(self, list<ErrorInfo> errors):
        list<ErrorInfo> result = []
        i = 0
        while i < len(errors):
            i0 = i
            # Find neighbouring errors with the same context and file.
            while (i + 1 < len(errors) and
                       errors[i + 1].import_ctx == errors[i].import_ctx and
                       errors[i + 1].file == errors[i].file):
                i += 1
            i += 1
            
            # Sort the errors specific to a file according to line number.
            a = stable_sort(errors[i0:i], lambda x: x.line)
            result.extend(a)
        return result
    
    # Remove duplicates from a sorted error list.
    list<tuple<str, int, str>> remove_duplicates(
                                  self, list<tuple<str, int, str>> errors):
        list<tuple<str, int, str>> res = []
        i = 0
        while i < len(errors):
            dup = False
            j = i - 1
            while (j >= 0 and errors[j][0] == errors[i][0] and
                       errors[j][1] == errors[i][1]):
                if errors[j] == errors[i]:
                    dup = True
                    break
                j -= 1
            if not dup:
                res.append(errors[i])
            i += 1
        return res


# Exception raised when there is a parse, semantic analysis, type check or
# other compilation-related error.
class CompileError(Exception):
    list<str> messages
    
    void __init__(self, list<str> messages):
        super().__init__()
        self.messages = messages


# Perform a stable sort of a sequence, i.e. if the original sequence has
# a[n] == a[n+m] (when comparing using the comparison function f), in the
# sorted sequence item a[n] will be at an earlier index than a[n + m].
list<T> stable_sort<T>(sequence<T> a, func<T, any> key):
    # TODO use sorted with key (need support for keyword arguments)
    l = <tuple<any, int, T>> []
    for i, x in enumerate(a):
        l.append((key(x), i, x))
    result = <T> []
    for k, j, y in sorted(l):
        result.append(y)        
    return result


# If path starts with prefix, return copy of path with the prefix removed.
# Otherwise, return path. If path is None, return None.
str remove_path_prefix(str path, str prefix):
    if prefix is not None and path.startswith(prefix):
        return path[len(prefix):]
    else:
        return path
