"""Prototype for using fine-grained incremental checking interactively.

Usage:

- first start it
  $ finegrained.py <dir>
- it now waits for user input
  - an empty line performs an incremental step
  - 'q' exits
"""

import sys
import os
from typing import Tuple, List

from mypy import build
from mypy.build import BuildManager, Graph
from mypy.main import expand_dir
from mypy.options import Options
from mypy.errors import CompileError
from mypy.server.update import FineGrainedBuildManager


def main() -> None:
    if len(sys.argv) != 2 or not os.path.isdir(sys.argv[1]):
        usage()
    target_dir = sys.argv[1]
    messages, manager, graph = build_dir(target_dir)
    sys.stdout.writelines(messages)
    fine_grained_manager = FineGrainedBuildManager(manager, graph)
    while True:
        print('[ready]')
        inp = input().strip()
        if inp.startswith('q'):
            sys.exit(0)
        if inp != '':
            print("Press enter to perform type checking; enter 'q' to quit")
            continue
        messages = fine_grained_manager.update(['mypy.stubgen'])
        sys.stdout.writelines(messages)


def build_dir(target_dir: str) -> Tuple[List[str], BuildManager, Graph]:
    sources = expand_dir(target_dir)
    options = Options()
    options.show_traceback = True
    options.cache_dir = os.devnull
    try:
        result = build.build(sources=sources,
                             options=options)
    except CompileError as e:
        # TODO: We need a manager and a graph in this case as well
        assert False, str('\n'.join(e.messages))
        return e.messages, None, None
    return result.errors, result.manager, result.graph


def usage() -> None:
    print('usage: finegrained.py DIRECTORY')
    sys.exit(1)


if __name__ == '__main__':
    main()
