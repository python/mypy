from typing import Optional
from typing_extensions import Final


class StubInfo:
    def __init__(self, name: str, py_version: Optional[int] = None) -> None:
        self.name = name
        # If None, compatible with py2+py3, if 2/3, only compatible with py2/py3
        self.py_version = py_version


def is_legacy_bundled_package(prefix: str, py_version: int) -> bool:
    if prefix not in legacy_bundled_packages:
        return False
    package_ver = legacy_bundled_packages[prefix].py_version
    return package_ver is None or package_ver == py_version


# Stubs for these third-party packages used to be shipped with mypy.
#
# Map package name to PyPI stub distribution name.
#
# Package name can have one or two components ('a' or 'a.b').
legacy_bundled_packages = {
    'aiofiles': StubInfo('types-aiofiles'),
    'atomicwrites': StubInfo('types-atomicwrites'),
    'attr': StubInfo('types-attrs'),
    'backports': StubInfo('types-backports'),
    'backports_abc': StubInfo('types-backports_abc'),
    'bleach': StubInfo('types-bleach'),
    'boto': StubInfo('types-boto'),
    'cachetools': StubInfo('types-cachetools'),
    'certifi': StubInfo('types-certifi'),
    'characteristic': StubInfo('types-characteristic'),
    'chardet': StubInfo('types-chardet'),
    'click': StubInfo('types-click'),
    'click_spinner': StubInfo('types-click-spinner'),
    'concurrent': StubInfo('types-futures'),
    'contextvars': StubInfo('types-contextvars'),
    'croniter': StubInfo('types-croniter'),
    'cryptography': StubInfo('types-cryptography'),
    'dataclasses': StubInfo('types-dataclasses'),
    'dateparser': StubInfo('types-dateparser'),
    'datetimerange': StubInfo('types-DateTimeRange'),
    'dateutil': StubInfo('types-python-dateutil'),
    'decorator': StubInfo('types-decorator'),
    'deprecated': StubInfo('types-Deprecated'),
    'docutils': StubInfo('types-docutils'),
    'emoji': StubInfo('types-emoji'),
    'enum': StubInfo('types-enum34'),
    'fb303': StubInfo('types-fb303'),
    'filelock': StubInfo('types-filelock'),
    'first': StubInfo('types-first'),
    'flask': StubInfo('types-Flask'),
    'freezegun': StubInfo('types-freezegun'),
    'frozendict': StubInfo('types-frozendict'),
    'geoip2': StubInfo('types-geoip2'),
    'gflags': StubInfo('types-python-gflags'),
    'google.protobuf': StubInfo('types-protobuf'),
    'ipaddress': StubInfo('types-ipaddress'),
    'itsdangerous': StubInfo('types-itsdangerous'),
    'jinja2': StubInfo('types-Jinja2'),
    'jwt': StubInfo('types-jwt'),
    'kazoo': StubInfo('types-kazoo'),
    'markdown': StubInfo('types-Markdown'),
    'markupsafe': StubInfo('types-MarkupSafe'),
    'maxminddb': StubInfo('types-maxminddb'),
    'mock': StubInfo('types-mock'),
    'OpenSSL': StubInfo('types-openssl-python'),
    'orjson': StubInfo('types-orjson'),
    'paramiko': StubInfo('types-paramiko'),
    'pathlib2': StubInfo('types-pathlib2'),
    'pkg_resources': StubInfo('types-pkg_resources'),
    'polib': StubInfo('types-polib'),
    'pycurl': StubInfo('types-pycurl'),
    'pymssql': StubInfo('types-pymssql'),
    'pymysql': StubInfo('types-PyMySQL'),
    'pyrfc3339': StubInfo('types-pyRFC3339'),
    'python2': StubInfo('types-six'),
    'pytz': StubInfo('types-pytz'),
    'pyVmomi': StubInfo('types-pyvmomi'),
    'redis': StubInfo('types-redis'),
    'requests': StubInfo('types-requests'),
    'retry': StubInfo('types-retry'),
    'routes': StubInfo('types-Routes'),
    'scribe': StubInfo('types-scribe'),
    'simplejson': StubInfo('types-simplejson'),
    'singledispatch': StubInfo('types-singledispatch'),
    'six': StubInfo('types-six'),
    'slugify': StubInfo('types-python-slugify'),
    'tabulate': StubInfo('types-tabulate'),
    'termcolor': StubInfo('types-termcolor'),
    'toml': StubInfo('types-toml'),
    'tornado': StubInfo('types-tornado'),
    'typed_ast': StubInfo('types-typed-ast'),
    'tzlocal': StubInfo('types-tzlocal'),
    'ujson': StubInfo('types-ujson'),
    'waitress': StubInfo('types-waitress'),
    'werkzeug': StubInfo('types-Werkzeug'),
    'yaml': StubInfo('types-PyYAML'),
}
