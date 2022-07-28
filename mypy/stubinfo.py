from typing import Optional


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
    "aiofiles": StubInfo("types-aiofiles", py_version=3),
    "atomicwrites": StubInfo("types-atomicwrites"),
    "attr": StubInfo("types-attrs"),
    "backports": StubInfo("types-backports"),
    "backports_abc": StubInfo("types-backports_abc"),
    "bleach": StubInfo("types-bleach"),
    "boto": StubInfo("types-boto"),
    "cachetools": StubInfo("types-cachetools"),
    "chardet": StubInfo("types-chardet"),
    "click_spinner": StubInfo("types-click-spinner"),
    "contextvars": StubInfo("types-contextvars", py_version=3),
    "croniter": StubInfo("types-croniter"),
    "dataclasses": StubInfo("types-dataclasses", py_version=3),
    "dateparser": StubInfo("types-dateparser"),
    "datetimerange": StubInfo("types-DateTimeRange"),
    "dateutil": StubInfo("types-python-dateutil"),
    "decorator": StubInfo("types-decorator"),
    "deprecated": StubInfo("types-Deprecated"),
    "docutils": StubInfo("types-docutils", py_version=3),
    "emoji": StubInfo("types-emoji"),
    "first": StubInfo("types-first"),
    "geoip2": StubInfo("types-geoip2"),
    "gflags": StubInfo("types-python-gflags"),
    "google.protobuf": StubInfo("types-protobuf"),
    "markdown": StubInfo("types-Markdown"),
    "maxminddb": StubInfo("types-maxminddb"),
    "mock": StubInfo("types-mock"),
    "OpenSSL": StubInfo("types-pyOpenSSL"),
    "paramiko": StubInfo("types-paramiko"),
    "pkg_resources": StubInfo("types-setuptools", py_version=3),
    "polib": StubInfo("types-polib"),
    "pycurl": StubInfo("types-pycurl"),
    "pymysql": StubInfo("types-PyMySQL"),
    "pyrfc3339": StubInfo("types-pyRFC3339", py_version=3),
    "python2": StubInfo("types-six"),
    "pytz": StubInfo("types-pytz"),
    "pyVmomi": StubInfo("types-pyvmomi"),
    "redis": StubInfo("types-redis"),
    "requests": StubInfo("types-requests"),
    "retry": StubInfo("types-retry"),
    "simplejson": StubInfo("types-simplejson"),
    "singledispatch": StubInfo("types-singledispatch"),
    "six": StubInfo("types-six"),
    "slugify": StubInfo("types-python-slugify"),
    "tabulate": StubInfo("types-tabulate"),
    "termcolor": StubInfo("types-termcolor"),
    "toml": StubInfo("types-toml"),
    "typed_ast": StubInfo("types-typed-ast", py_version=3),
    "tzlocal": StubInfo("types-tzlocal"),
    "ujson": StubInfo("types-ujson"),
    "waitress": StubInfo("types-waitress", py_version=3),
    "yaml": StubInfo("types-PyYAML"),
}
