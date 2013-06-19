# Stubs for getopt

# Based on http://docs.python.org/3.2/library/getopt.html

from typing import List, Tuple

def getopt(args: List[str], shortopts: str,
           longopts: List[str]) -> Tuple[List[Tuple[str, str]],
                                         List[str]]: pass

def gnu_getopt(args: List[str], shortopts: str,
               longopts: List[str]) -> Tuple[List[Tuple[str, str]],
                                             List[str]]: pass

class GetoptError(Exception):
    msg = ''
    opt = ''

error = GetoptError
