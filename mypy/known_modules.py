"""Known Python module names for fuzzy matching import suggestions.

This module provides a curated list of popular Python package import names
for suggesting corrections when a user mistypes an import statement.

Sources:
- Python standard library (typeshed/stdlib/VERSIONS)
- Top 200 PyPI packages by downloads (https://github.com/hugovk/top-pypi-packages)

Note: These are import names, not PyPI package names.
"""

from __future__ import annotations

from typing import Final

from mypy.modulefinder import StdlibVersions

POPULAR_THIRD_PARTY_MODULES: Final[frozenset[str]] = frozenset({
    # Cloud
    "boto3",
    "botocore",
    "aiobotocore",
    "s3transfer",
    "s3fs",
    "awscli",

    # HTTP / Networking
    "urllib3",
    "requests",
    "certifi",
    "idna",
    "charset_normalizer",
    "httpx",
    "httpcore",
    "aiohttp",
    "yarl",
    "multidict",
    "requests_oauthlib",
    "oauthlib",
    "websocket",
    "websockets",
    "h11",
    "sniffio",
    "requests_toolbelt",
    "httplib2",

    # Typing / Extensions
    "typing_extensions",
    "mypy_extensions",
    "annotated_types",
    "typing_inspection",

    # Core Utilities
    "setuptools",
    "packaging",
    "pip",
    "wheel",
    "virtualenv",
    "platformdirs",
    "filelock",
    "zipp",
    "importlib_metadata",
    "importlib_resources",
    "distlib",
    "distro",
    "appdirs",

    # Data Science / Numerical
    "numpy",
    "pandas",
    "scipy",
    "sklearn",
    "matplotlib",
    "pyarrow",
    "networkx",
    "joblib",
    "threadpoolctl",
    "kiwisolver",
    "fontTools",
    "dill",
    "cloudpickle",

    # Serialization / Config
    "yaml",
    "pydantic",
    "pydantic_core",
    "pydantic_settings",
    "attrs",
    "tomli",
    "tomlkit",
    "jsonschema",
    "jsonschema_specifications",
    "jsonpointer",
    "jmespath",
    "msgpack",
    "isodate",
    "ruamel",

    # Cryptography / Security
    "cryptography",
    "cffi",
    "pycparser",
    "rsa",
    "pyjwt",
    "jwt",
    "pyasn1",
    "pyasn1_modules",
    "OpenSSL",
    "nacl",
    "bcrypt",
    "asn1crypto",
    "paramiko",
    "secretstorage",
    "msal",
    "msal_extensions",
    "keyring",

    # Date / Time
    "dateutil",
    "pytz",
    "tzdata",
    "tzlocal",

    # Google
    "google",
    "google_auth_oauthlib",
    "google_auth_httplib2",
    "google_crc32c",
    "googleapiclient",
    "grpc",
    "grpc_status",
    "grpc_tools",
    "protobuf",
    "proto",
    "googleapis_common_protos",

    # Testing
    "pytest",
    "pluggy",
    "iniconfig",
    "coverage",
    "exceptiongroup",

    # CLI / Terminal
    "click",
    "typer",
    "colorama",
    "rich",
    "tqdm",
    "tabulate",
    "prompt_toolkit",
    "shellingham",
    "wcwidth",

    # Web Frameworks
    "flask",
    "werkzeug",
    "itsdangerous",
    "blinker",
    "fastapi",
    "starlette",
    "uvicorn",

    # Templates / Markup
    "jinja2",
    "markupsafe",
    "pygments",
    "markdown_it",
    "mdurl",
    "docutils",

    # Async
    "anyio",
    "greenlet",
    "aiosignal",
    "aiohappyeyeballs",
    "async_timeout",

    # Database
    "sqlalchemy",
    "alembic",
    "redis",
    "psycopg2",

    # Parsing / XML
    "lxml",
    "bs4",
    "soupsieve",
    "pyparsing",
    "regex",
    "et_xmlfile",

    # OpenTelemetry
    "opentelemetry",

    # Azure
    "azure",

    # Other Popular Modules
    "six",
    "fsspec",
    "wrapt",
    "propcache",
    "rpds",
    "pathspec",
    "PIL",
    "pillow",
    "psutil",
    "referencing",
    "trove_classifiers",
    "openpyxl",
    "tenacity",
    "more_itertools",
    "sortedcontainers",
    "decorator",
    "ptyprocess",
    "pexpect",
    "hatchling",
    "dotenv",
    "python_dotenv",
    "huggingface_hub",
    "transformers",
    "openai",
    "langsmith",
    "dns",
    "dnspython",
    "git",
    "gitdb",
    "smmap",
    "deprecated",
    "chardet",
    "backoff",
    "ruff",
    "setuptools_scm",
    "pyproject_hooks",
    "jiter",
    "yandexcloud",
    "aliyunsdkcore",
    "uritemplate",
    "kubernetes",
    "snowflake",
    "multipart",
})


def get_stdlib_modules(
    stdlib_versions: StdlibVersions,
    python_version: tuple[int, int] | None = None,
) -> frozenset[str]:
    modules: set[str] = set()
    for module, (min_ver, max_ver) in stdlib_versions.items():
        if python_version is not None:
            if python_version < min_ver:
                continue
            if max_ver is not None and python_version > max_ver:
                continue
        top_level = module.split(".")[0]
        modules.add(top_level)
    return frozenset(modules)


def get_known_modules(
    stdlib_versions: StdlibVersions | None = None,
    python_version: tuple[int, int] | None = None,
) -> frozenset[str]:
    modules: set[str] = set(POPULAR_THIRD_PARTY_MODULES)
    if stdlib_versions is not None:
        modules = modules.union(get_stdlib_modules(stdlib_versions, python_version))
    return frozenset(modules)
