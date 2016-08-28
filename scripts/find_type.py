#!/usr/bin/env python3
# Usage: find_type.py FILENAME START_LINE START_COL END_LINE END_COL MYPY_AND_ARGS
# Prints out the type of the expression in the given location if the mypy run
# succeeds cleanly.  Otherwise, prints out the errors encountered.
# Note: this only works on expressions, and not assignment targets.
# Note: MYPY_AND_ARGS is should be the remainder of argv, not a single
# spaces-included argument.
# NOTE: Line numbers are 1-based; column numbers are 0-based.
#
#
# Example vim usage:
# function RevealType()
#   " Set this to the command you use to run mypy on your project.  Include the mypy invocation.
#   let mypycmd = 'python3 -m mypy mypy --incremental'
#   let [startline, startcol] = getpos("'<")[1:2]
#   let [endline, endcol] = getpos("'>")[1:2]
#   " Convert to 0-based column offsets
#   let startcol = startcol - 1
#   " Change this line to point to the find_type.py script.
#   execute '!python3 /path/to/mypy/scripts/find_type.py % ' . startline . ' ' . startcol . ' ' . endline . ' ' . endcol . ' ' . mypycmd
# endfunction
# vnoremap <Leader>t :call RevealType()<CR>
#
# For an Emacs example, see misc/macs.el.

from typing import List, Tuple, Optional
import subprocess
import sys
import tempfile
import os.path
import re

REVEAL_TYPE_START = 'reveal_type('
REVEAL_TYPE_END = ')'

def update_line(line: str, s: str, pos: int) -> str:
    return line[:pos] + s + line[pos:]

def run_mypy(mypy_and_args: List[str], filename: str, tmp_name: str) -> str:
    proc = subprocess.run(mypy_and_args + ['--shadow-file', filename, tmp_name], stdout=subprocess.PIPE)
    assert(isinstance(proc.stdout, bytes))  # Guaranteed to be true because we called run with universal_newlines=False
    return proc.stdout.decode(encoding="utf-8")

def get_revealed_type(line: str, relevant_file: str, relevant_line: int) -> Optional[str]:
    m = re.match("(.+?):(\d+): error: Revealed type is '(.*)'$", line)
    if (m and
            int(m.group(2)) == relevant_line and
            os.path.samefile(relevant_file, m.group(1))):
        return m.group(3)
    else:
        return None

def process_output(output: str, filename: str, start_line: int) -> Tuple[Optional[str], bool]:
    error_found = False
    for line in output.splitlines():
        t = get_revealed_type(line, filename, start_line)
        if t:
            return t, error_found
        elif 'error:' in line:
            error_found = True
    return None, True  # finding no reveal_type is an error

def main():
    filename, start_line_str, start_col_str, end_line_str, end_col_str, *mypy_and_args = sys.argv[1:]
    start_line = int(start_line_str)
    start_col = int(start_col_str)
    end_line = int(end_line_str)
    end_col = int(end_col_str)
    with open(filename, 'r') as f:
        lines = f.readlines()
        lines[end_line - 1] = update_line(lines[end_line - 1], REVEAL_TYPE_END, end_col)  # insert after end_col
        lines[start_line - 1] = update_line(lines[start_line - 1], REVEAL_TYPE_START, start_col)
        with tempfile.NamedTemporaryFile(mode='w', prefix='mypy') as tmp_f:
            tmp_f.writelines(lines)
            tmp_f.flush()

            output = run_mypy(mypy_and_args, filename, tmp_f.name)
            revealed_type, error = process_output(output, filename, start_line)
            if revealed_type:
                print(revealed_type)
            if error:
                print(output)
            exit(int(error))


if __name__ == "__main__":
    main()
