# Usage: find_type.py FILENAME START_LINE START_COL END_LINE END_COL MYPY_AND_ARGS
# Prints out the type of the expression in the given location if the mypy run
# succeeds cleanly.  Otherwise, prints out the errors encountered.
# Note: this only works on expressions, and not assignment targets.
#
#
# Example vim usage:
# function RevealType()
#   " Set this to the command you use to run mypy on your project.  Include the mypy invocation.
#   let mypycmd = 'python3 -m mypy mypy --incremental'
#   let [startline, startcol] = getpos("'<")[1:2]
#   let [endline, endcol] = getpos("'>")[1:2]
#   " Change this line to point to the find_type.py script.
#   execute '!python3 /path/to/mypy/scripts/find_type.py % ' . startline . ' ' . startcol . ' ' . endline . ' ' . endcol . ' ' . mypycmd
# endfunction
# vnoremap <Leader>t :call RevealType()<CR>

import subprocess
import sys
import tempfile

REVEAL_TYPE_START = 'reveal_type('
REVEAL_TYPE_END = ')'

def insert(line, s, pos):
    return line[:pos] + s + line[pos:]

def run_mypy(mypy_and_args, filename, tmp_name):
    proc = subprocess.run(mypy_and_args + ['--shadow-file', filename, tmp_name], stdout=subprocess.PIPE)
    return proc.stdout.decode(encoding="utf-8")

def process_output(output, filename, start_line):
    line_format = "{}:{}: error: Revealed type is '".format(filename, start_line + 1)
    error_found = False
    for line in output.splitlines():
        if line.startswith(line_format):
            return line[len(line_format):-1], error_found
        elif 'error:' in line:
            error_found = True
    return None, error_found

def main():
    filename, start_line, start_col, end_line, end_col, *mypy_and_args = sys.argv[1:]
    start_line = int(start_line) - 1  # 0 indexing
    start_col = int(start_col) - 1
    end_line = int(end_line) - 1  # 0 indexing
    end_col = int(end_col)
    with open(filename, 'r') as f:
        lines = f.readlines()
        lines[end_line] = insert(lines[end_line], REVEAL_TYPE_END, end_col)
        lines[start_line] = insert(lines[start_line], REVEAL_TYPE_START, start_col)
        with tempfile.NamedTemporaryFile(mode='w', prefix='mypy') as tmp_f:
            tmp_f.writelines(lines)
            tmp_f.flush()

            output = run_mypy(mypy_and_args, filename, tmp_f.name)
            revealed_type, error_found = process_output(output, filename, start_line)
            if revealed_type:
                print(revealed_type)
            if error_found:
                print(output)
            exit(int(error_found))



if __name__ == "__main__":
    main()
