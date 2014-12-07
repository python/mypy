#!/usr/bin/env python3
import os
import shutil
from typing import Tuple, Any
try:
    import click
except ImportError:
    print("You need the module \'click\'")
    exit(1)

base_path = os.getcwd()

# I don't know how to set callables with different args
def apply_all(func: Any, directory: str, extension: str,
            to_extension: str='', exclude: Tuple[str]=('',),
            recursive: bool=True, debug: bool=False) -> None:
    excluded = [x+extension for x in exclude] if exclude else []
    for p, d, files in os.walk(os.path.join(base_path,directory)):
        for f in files:
            if "{}".format(f) in excluded:
                continue
            inner_path = os.path.join(p,f)
            if not inner_path.endswith(extension):
                continue
            if to_extension:
                new_path = "{}{}".format(inner_path[:-len(extension)],to_extension)
                func(inner_path,new_path)
            else:
                func(inner_path)
        if not recursive:
            break

def confirm(resp: bool=False, **kargs) -> bool:
    kargs['rest'] = "to this {f2}/*{e2}".format(**kargs) if kargs.get('f2') else ''
    prompt = "{act} all files {rec}matching this expression {f1}/*{e1} {rest}".format(**kargs)
    prompt.format(**kargs)
    prompt = "{} [{}]|{}: ".format(prompt, 'Y' if resp else 'N', 'n' if resp else 'y')
    while True:
        ans = input(prompt).lower()
        if not ans:
            return resp
        if ans not in ['y','n']:
            print( 'Please, enter (y) or (n).')
            continue
        if ans == 'y':
            return True
        else:
            return False

actions = ['cp', 'mv', 'rm']
@click.command(context_settings=dict(help_option_names=['-h', '--help']))
@click.option('--action', '-a', type=click.Choice(actions), required=True, help="What do I have to do :-)")
@click.option('--dir', '-d', 'directory', default='stubs', help="Directory to start search!")
@click.option('--ext', '-e', 'extension', default='.py', help="Extension \"from\" will be applied the action. Default .py")
@click.option('--to', '-t', 'to_extension', default='.pyi', help="Extension \"to\" will be applied the action if can. Default .pyi")
@click.option('--exclude', '-x', multiple=True, default=('__init__',), help="For every appear, will ignore this files. (can set multiples times)")
@click.option('--not-recursive', '-n', default=True, is_flag=True, help="Set if don't want to walk recursively.")
def main(action: str, directory: str, extension: str, to_extension: str,
    exclude: Tuple[str], not_recursive: bool) -> None:
    """
    This script helps to copy/move/remove files based on their extension.

    The three actions will ask you for confirmation.

    Examples (by default the script search in stubs directory):

    - Change extension of all stubs from .py to .pyi:

        python <script.py> -a mv

    - Revert the previous action.

        python <script.py> -a mv -e .pyi -t .py

    - If you want to ignore "awesome.py" files.

        python <script.py> -a [cp|mv|rm] -x awesome

    - If you want to ignore "awesome.py" and "__init__.py" files.

        python <script.py> -a [cp|mv|rm] -x awesome -x __init__

    - If you want to remove all ".todo" files in "todo" directory, but not recursively:

        python <script.py> -a rm -e .todo -d todo -r

    """
    if action not in actions:
        print("Your action have to be one of this: {}".format(', '.join(actions)))
        return

    rec = "[Recursively] " if not_recursive else ''
    if not extension.startswith('.'):
        extension = ".{}".format(extension)
    if not to_extension.startswith('.'):
        to_extension = ".{}".format(to_extension)
    if directory.endswith('/'):
        directory = directory[:-1]
    if action == 'cp':
        if confirm(act='Copy',rec=rec, f1=directory, e1=extension, f2=directory, e2=to_extension):
            apply_all(shutil.copy, directory, extension, to_extension, exclude, not_recursive)
    elif action == 'rm':
        if confirm(act='Remove',rec=rec, f1=directory, e1=extension):
            apply_all(os.remove, directory, extension, exclude=exclude, recursive=not_recursive)
    elif action == 'mv':
        if confirm(act='Move',rec=rec, f1=directory, e1=extension, f2=directory, e2=to_extension):
            apply_all(shutil.move, directory, extension, to_extension, exclude, not_recursive)


if __name__ == '__main__':
    main()
