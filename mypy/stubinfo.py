from __future__ import annotations


def is_legacy_bundled_package(prefix: str) -> bool:
    return prefix in legacy_bundled_packages


# Stubs for these third-party packages used to be shipped with mypy.
#
# Map package name to PyPI stub distribution name.
#
# Package name can have one or two components ('a' or 'a.b').
legacy_bundled_packages = {
    "aiofiles": "types-aiofiles",
    "atomicwrites": "types-atomicwrites",
    "attr": "types-attrs",
    "backports": "types-backports",
    "backports_abc": "types-backports_abc",
    "bleach": "types-bleach",
    "boto": "types-boto",
    "cachetools": "types-cachetools",
    "chardet": "types-chardet",
    "click_spinner": "types-click-spinner",
    "contextvars": "types-contextvars",
    "croniter": "types-croniter",
    "dataclasses": "types-dataclasses",
    "dateparser": "types-dateparser",
    "datetimerange": "types-DateTimeRange",
    "dateutil": "types-python-dateutil",
    "decorator": "types-decorator",
    "deprecated": "types-Deprecated",
    "docutils": "types-docutils",
    "emoji": "types-emoji",
    "first": "types-first",
    "geoip2": "types-geoip2",
    "gflags": "types-python-gflags",
    "google.protobuf": "types-protobuf",
    "markdown": "types-Markdown",
    "maxminddb": "types-maxminddb",
    "mock": "types-mock",
    "OpenSSL": "types-pyOpenSSL",
    "paramiko": "types-paramiko",
    "pkg_resources": "types-setuptools",
    "polib": "types-polib",
    "pycurl": "types-pycurl",
    "pymysql": "types-PyMySQL",
    "pyrfc3339": "types-pyRFC3339",
    "python2": "types-six",
    "pytz": "types-pytz",
    "pyVmomi": "types-pyvmomi",
    "redis": "types-redis",
    "requests": "types-requests",
    "retry": "types-retry",
    "simplejson": "types-simplejson",
    "singledispatch": "types-singledispatch",
    "six": "types-six",
    "slugify": "types-python-slugify",
    "tabulate": "types-tabulate",
    "termcolor": "types-termcolor",
    "toml": "types-toml",
    "typed_ast": "types-typed-ast",
    "tzlocal": "types-tzlocal",
    "ujson": "types-ujson",
    "waitress": "types-waitress",
    "yaml": "types-PyYAML",
}
