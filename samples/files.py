# indent your Python code to put into an email
import glob
import typing
# glob supports Unix style pathname extensions
python_files = glob.glob('*.py')
for file_name in sorted(python_files):
    print('    ------' + file_name)

    f = open(file_name)
    for line in f:
        print('    ' + line.rstrip())
    f.close()

    print()
