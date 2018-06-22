from typing import List, Dict, Tuple, Set, Optional


class NameGenerator:
    """Utility for generating distinct C names from Python names.

    Since C names can't use '.' (or unicode), some care is required to
    make C names generated from Python names unique. Also, we want to
    avoid generating overly long C names since they make the generated
    code harder to read.

    Note that we don't restrict ourselves to a 32-character distinguishing
    prefix guaranteed by the C standard since all the compilers we care
    about at the moment support longer names without issues.

    For names that are exported in a shared library (not static) use
    exported_name() instead.

    Summary of the approach:

    * Generate a unique name prefix from suffix of fully-qualified
      module name used for static names. If only compiling a single
      module, this can be empty. For example, if the modules are
      'foo.bar' and 'foo.baz', the prefixes can be 'bar_' and 'baz_',
      respectively. If the modules are 'bar.foo' and 'baz.foo', the
      prefixes will be 'bar_foo_' and 'baz_foo_'.

    * Replace '.' in the Python name with '_' in the C name. This can
      obviously generate conflicts at C name level. If multiple Python
      names would map to the same C name using the basic algorithm,
      add suffixes _2, _3, etc. to make the C names unique.

    * Keep a dictionary of mappings so that we can translate each name
      consistently within a build.

    The generated should be internal to a build and thus the mapping is
    arbitrary. Just generating names '1', '2', ... would be correct,
    though not very usable.
    """

    def __init__(self, module_names: Optional[List[str]] = None) -> None:
        """Initialize with names of all modules in the compilation unit.

        The names of modules are used to shorten names referring to
        modules in the compilation unit, for convenience. Arbitary module
        names are supported for generated names, but modules not in the
        compilation unit will use long names.
        """
        module_names = module_names or []
        self.module_map = make_module_translation_map(module_names)
        self.translations = {}  # type: Dict[Tuple[str, str], str]
        self.used_names = set()  # type: Set[str]

    def private_name(self, module: str, partial_name: Optional[str] = None) -> str:
        """Return a C name usable for a static definition.

        Return a distinct result for each (module, partial_name) pair.

        The caller should add a suitable prefix to the name to avoid
        conflicts with other C names. Only ensure that the results of
        this function are unique, not that they aren't overlapping with
        arbitrary names.

        If a name is not specific to any module, the module argument can
        be an empty string.
        """
        # TODO: Support unicode
        if partial_name is None:
            return self.module_map[module].rstrip('_')
        if (module, partial_name) in self.translations:
            return self.translations[module, partial_name]
        if module in self.module_map:
            module_prefix = self.module_map[module]
        elif module:
            module_prefix = module.replace('.', '_') + '_'
        else:
            module_prefix = ''
        candidate = '{}{}'.format(module_prefix, partial_name.replace('.', '_'))
        actual = self.make_unique(candidate)
        self.translations[module, partial_name] = actual
        self.used_names.add(actual)
        return actual

    def make_unique(self, name: str) -> str:
        if name not in self.used_names:
            return name
        i = 2
        while True:
            candidate = '{}_{}'.format(name, i)
            if candidate not in self.used_names:
                return candidate
            i += 1


def exported_name(fullname: str) -> str:
    """Return a C name usable for an exported definition.

    This is like private_name(), but the output only depends on the
    'fullname' argument, so the names are distinct across multiple
    builds.
    """
    # TODO: Support unicode
    # TODO: Ensure that there are no conflicts?
    return fullname.replace('.', '___')


def make_module_translation_map(names: List[str]) -> Dict[str, str]:
    num_instances = {}  # type: Dict[str, int]
    for name in names:
        for suffix in candidate_suffixes(name):
            num_instances[suffix] = num_instances.get(suffix, 0) + 1
    result = {}
    for name in names:
        for suffix in candidate_suffixes(name):
            if num_instances[suffix] == 1:
                result[name] = suffix
                break
        else:
            assert False, names
    return result


def candidate_suffixes(fullname: str) -> List[str]:
    components = fullname.split('.')
    result = ['']
    for i in range(len(components)):
        result.append('_'.join(components[-i - 1:]) + '_')
    return result
