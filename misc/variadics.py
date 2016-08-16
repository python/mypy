"""Example of code generation approach to variadics.

See https://github.com/python/typing/issues/193#issuecomment-236383893
"""

LIMIT = 5
BOUND = 'object'

def prelude(limit: int, bound: str) -> None:
    print('from typing import Callable, Iterable, Iterator, Tuple, TypeVar, overload')
    print('Ts = TypeVar(\'Ts\', bound={bound})'.format(bound=bound))
    print('R = TypeVar(\'R\')')
    for i in range(LIMIT):
        print('T{i} = TypeVar(\'T{i}\', bound={bound})'.format(i=i+1, bound=bound))

def expand_template(template: str,
                    arg_template: str = 'arg{i}: {Ts}',
                    lower: int = 0,
                    limit: int = LIMIT) -> None:
    print()
    for i in range(lower, limit):
        tvs = ', '.join('T{i}'.format(i=j+1) for j in range(i))
        args = ', '.join(arg_template.format(i=j+1, Ts='T{}'.format(j+1))
                         for j in range(i))
        print('@overload')
        s = template.format(Ts=tvs, argsTs=args)
        s = s.replace('Tuple[]', 'Tuple[()]')
        print(s)
    args_l = [arg_template.format(i=j+1, Ts='Ts') for j in range(limit)]
    args_l.append('*' + (arg_template.format(i='s', Ts='Ts')))
    args = ', '.join(args_l)
    s = template.format(Ts='Ts, ...', argsTs=args)
    s = s.replace('Callable[[Ts, ...]', 'Callable[...')
    print('@overload')
    print(s)

def main():
    prelude(LIMIT, BOUND)

    # map()
    expand_template('def map(func: Callable[[{Ts}], R], {argsTs}) -> R: ...',
                    lower=1)
    # zip()
    expand_template('def zip({argsTs}) -> Tuple[{Ts}]: ...')

    # Naomi's examples
    expand_template('def my_zip({argsTs}) -> Iterator[Tuple[{Ts}]]: ...',
                    'arg{i}: Iterable[{Ts}]')
    expand_template('def make_check({argsTs}) -> Callable[[{Ts}], bool]: ...')
    expand_template('def my_map(f: Callable[[{Ts}], R], {argsTs}) -> Iterator[R]: ...',
                    'arg{i}: Iterable[{Ts}]')
                    

main()
