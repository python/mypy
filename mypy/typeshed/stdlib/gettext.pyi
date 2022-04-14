import sys
from _typeshed import StrPath
from typing import IO, Any, Container, Iterable, Sequence, TypeVar, overload
from typing_extensions import Literal

if sys.version_info >= (3, 11):
    __all__ = [
        "NullTranslations",
        "GNUTranslations",
        "Catalog",
        "bindtextdomain",
        "find",
        "translation",
        "install",
        "textdomain",
        "dgettext",
        "dngettext",
        "gettext",
        "ngettext",
        "pgettext",
        "dpgettext",
        "npgettext",
        "dnpgettext",
    ]
elif sys.version_info >= (3, 8):
    __all__ = [
        "NullTranslations",
        "GNUTranslations",
        "Catalog",
        "find",
        "translation",
        "install",
        "textdomain",
        "bindtextdomain",
        "bind_textdomain_codeset",
        "dgettext",
        "dngettext",
        "gettext",
        "lgettext",
        "ldgettext",
        "ldngettext",
        "lngettext",
        "ngettext",
        "pgettext",
        "dpgettext",
        "npgettext",
        "dnpgettext",
    ]
else:
    __all__ = [
        "NullTranslations",
        "GNUTranslations",
        "Catalog",
        "find",
        "translation",
        "install",
        "textdomain",
        "bindtextdomain",
        "bind_textdomain_codeset",
        "dgettext",
        "dngettext",
        "gettext",
        "lgettext",
        "ldgettext",
        "ldngettext",
        "lngettext",
        "ngettext",
    ]

class NullTranslations:
    def __init__(self, fp: IO[str] | None = ...) -> None: ...
    def _parse(self, fp: IO[str]) -> None: ...
    def add_fallback(self, fallback: NullTranslations) -> None: ...
    def gettext(self, message: str) -> str: ...
    def lgettext(self, message: str) -> str: ...
    def ngettext(self, msgid1: str, msgid2: str, n: int) -> str: ...
    def lngettext(self, msgid1: str, msgid2: str, n: int) -> str: ...
    if sys.version_info >= (3, 8):
        def pgettext(self, context: str, message: str) -> str: ...
        def npgettext(self, context: str, msgid1: str, msgid2: str, n: int) -> str: ...

    def info(self) -> Any: ...
    def charset(self) -> Any: ...
    if sys.version_info < (3, 11):
        def output_charset(self) -> Any: ...
        def set_output_charset(self, charset: str) -> None: ...

    def install(self, names: Container[str] | None = ...) -> None: ...

class GNUTranslations(NullTranslations):
    LE_MAGIC: int
    BE_MAGIC: int
    CONTEXT: str
    VERSIONS: Sequence[int]

@overload  # ignores incompatible overloads
def find(  # type: ignore[misc]
    domain: str, localedir: StrPath | None = ..., languages: Iterable[str] | None = ..., all: Literal[False] = ...
) -> str | None: ...
@overload
def find(
    domain: str, localedir: StrPath | None = ..., languages: Iterable[str] | None = ..., all: Literal[True] = ...
) -> list[str]: ...
@overload
def find(domain: str, localedir: StrPath | None = ..., languages: Iterable[str] | None = ..., all: bool = ...) -> Any: ...

_T = TypeVar("_T")

if sys.version_info >= (3, 11):
    @overload
    def translation(
        domain: str,
        localedir: StrPath | None = ...,
        languages: Iterable[str] | None = ...,
        class_: None = ...,
        fallback: bool = ...,
    ) -> NullTranslations: ...
    @overload
    def translation(
        domain: str,
        localedir: StrPath | None = ...,
        languages: Iterable[str] | None = ...,
        class_: type[_T] = ...,
        fallback: Literal[False] = ...,
    ) -> _T: ...
    @overload
    def translation(
        domain: str,
        localedir: StrPath | None = ...,
        languages: Iterable[str] | None = ...,
        class_: type[Any] = ...,
        fallback: Literal[True] = ...,
    ) -> Any: ...
    def install(domain: str, localedir: StrPath | None = ..., names: Container[str] | None = ...) -> None: ...

else:
    @overload
    def translation(
        domain: str,
        localedir: StrPath | None = ...,
        languages: Iterable[str] | None = ...,
        class_: None = ...,
        fallback: bool = ...,
        codeset: str | None = ...,
    ) -> NullTranslations: ...
    @overload
    def translation(
        domain: str,
        localedir: StrPath | None = ...,
        languages: Iterable[str] | None = ...,
        class_: type[_T] = ...,
        fallback: Literal[False] = ...,
        codeset: str | None = ...,
    ) -> _T: ...
    @overload
    def translation(
        domain: str,
        localedir: StrPath | None = ...,
        languages: Iterable[str] | None = ...,
        class_: type[Any] = ...,
        fallback: Literal[True] = ...,
        codeset: str | None = ...,
    ) -> Any: ...
    def install(
        domain: str, localedir: StrPath | None = ..., codeset: str | None = ..., names: Container[str] | None = ...
    ) -> None: ...

def textdomain(domain: str | None = ...) -> str: ...
def bindtextdomain(domain: str, localedir: StrPath | None = ...) -> str: ...
def dgettext(domain: str, message: str) -> str: ...
def dngettext(domain: str, msgid1: str, msgid2: str, n: int) -> str: ...
def gettext(message: str) -> str: ...
def ngettext(msgid1: str, msgid2: str, n: int) -> str: ...

if sys.version_info >= (3, 8):
    def pgettext(context: str, message: str) -> str: ...
    def dpgettext(domain: str, context: str, message: str) -> str: ...
    def npgettext(context: str, msgid1: str, msgid2: str, n: int) -> str: ...
    def dnpgettext(domain: str, context: str, msgid1: str, msgid2: str, n: int) -> str: ...

if sys.version_info < (3, 11):
    def lgettext(message: str) -> str: ...
    def ldgettext(domain: str, message: str) -> str: ...
    def lngettext(msgid1: str, msgid2: str, n: int) -> str: ...
    def ldngettext(domain: str, msgid1: str, msgid2: str, n: int) -> str: ...
    def bind_textdomain_codeset(domain: str, codeset: str | None = ...) -> str: ...

Catalog = translation
