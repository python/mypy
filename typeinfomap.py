from nodes import TypeInfo


class TypeInfoMap(dict<str, TypeInfo>):
    str __str__(self):
        list<str> a = ['TypeInfoMap(']
        for x, y in self.items():
            if isinstance(x, str) and not x.startswith('builtins.'):
                ti = ('\n' + '  ').join(str(y).split('\n'))
                a.append('  {} : {}'.format(x, ti))
        a[-1] += ')'
        return '\n'.join(a)
