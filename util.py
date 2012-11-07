

# Return the last component of the type name of an object. If obj is None,
# return 'nil'. For example, if obj is 1, return 'int'.
str short_type(object obj):
    if obj is None:
        return 'nil'
    t = str(type(obj))
    return t.split('.')[-1].rstrip("'>")


# Indent all the lines in s (separated by Newlines) by n spaces.
str indent(str s, int n):
    s = ' ' * n + s
    s = s.replace('\n', '\n' + ' ' * n)
    return s


# Return the items of an array converted to strings using Repr.
list<str> array_repr<T>(list<T> a):
    list<str> aa = []
    for x in a:
        aa.append(repr(x))
    return aa


# Convert an array into a pretty-printed multiline string representation.
# The format is
#   tag(
#     item1..
#     itemN)
# Individual items are formatted like this:
#  - arrays are flattened
#  - pairs (str : array) are converted recursively, so that str is the tag
#  - other items are converted to strings and indented
str dump_tagged(list<any> nodes, str tag):
    list<str> a = []
    if tag is not None:
        a.append(tag + '(')
    for n in nodes:
        if isinstance(n, list):
            a.append(dump_tagged(n, None))
        elif isinstance(n, tuple):
            s = dump_tagged(n[1], n[0])
            a.append(indent(s, 2))
        elif n is not None:
            a.append(indent(str(n), 2))
    if tag is not None:
        a[-1] += ')'
    return '\n'.join(a)
