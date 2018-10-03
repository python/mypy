"""Mypy type checker command line tool."""

from mypy.main import main


def console_entry() -> None:
    main(None)


if __name__ == '__main__':
    import cProfile
    import pstats

    cProfile.run('main(None)', 'profstats')
    p = pstats.Stats('profstats')
    p.sort_stats('time').print_stats(40)
    #main(None)
