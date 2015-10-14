from yaml.reader import Reader
from yaml.scanner import Scanner
from yaml.parser import Parser
from yaml.composer import Composer
from yaml.constructor import BaseConstructor, SafeConstructor, Constructor
from yaml.resolver import BaseResolver, Resolver

class BaseLoader(Reader, Scanner, Parser, Composer, BaseConstructor, BaseResolver):
    def __init__(self, stream): ...

class SafeLoader(Reader, Scanner, Parser, Composer, SafeConstructor, Resolver):
    def __init__(self, stream): ...

class Loader(Reader, Scanner, Parser, Composer, Constructor, Resolver):
    def __init__(self, stream): ...

# This isn't how this class is actually defined, but it should get the types about right.
class CSafeLoader(Reader, Scanner, Parser, Composer, SafeConstructor, Resolver):
    def __init__(self, stream): ...
