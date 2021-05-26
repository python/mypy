import sys
from _typeshed import FileDescriptor, StrOrBytesPath, SupportsWrite
from typing import (
    IO,
    Any,
    Callable,
    Dict,
    Generator,
    ItemsView,
    Iterable,
    Iterator,
    KeysView,
    List,
    MutableSequence,
    Optional,
    Sequence,
    Tuple,
    TypeVar,
    Union,
    overload,
)
from typing_extensions import Literal

_T = TypeVar("_T")
_File = Union[StrOrBytesPath, FileDescriptor, IO[Any]]

VERSION: str

class ParseError(SyntaxError):
    code: int
    position: Tuple[int, int]

def iselement(element: object) -> bool: ...

if sys.version_info >= (3, 8):
    @overload
    def canonicalize(
        xml_data: Optional[Union[str, bytes]] = ...,
        *,
        out: None = ...,
        from_file: Optional[_File] = ...,
        with_comments: bool = ...,
        strip_text: bool = ...,
        rewrite_prefixes: bool = ...,
        qname_aware_tags: Optional[Iterable[str]] = ...,
        qname_aware_attrs: Optional[Iterable[str]] = ...,
        exclude_attrs: Optional[Iterable[str]] = ...,
        exclude_tags: Optional[Iterable[str]] = ...,
    ) -> str: ...
    @overload
    def canonicalize(
        xml_data: Optional[Union[str, bytes]] = ...,
        *,
        out: SupportsWrite[str],
        from_file: Optional[_File] = ...,
        with_comments: bool = ...,
        strip_text: bool = ...,
        rewrite_prefixes: bool = ...,
        qname_aware_tags: Optional[Iterable[str]] = ...,
        qname_aware_attrs: Optional[Iterable[str]] = ...,
        exclude_attrs: Optional[Iterable[str]] = ...,
        exclude_tags: Optional[Iterable[str]] = ...,
    ) -> None: ...

class Element(MutableSequence[Element]):
    tag: str
    attrib: Dict[str, str]
    text: Optional[str]
    tail: Optional[str]
    def __init__(self, tag: Union[str, Callable[..., Element]], attrib: Dict[str, str] = ..., **extra: str) -> None: ...
    def append(self, __subelement: Element) -> None: ...
    def clear(self) -> None: ...
    def extend(self, __elements: Iterable[Element]) -> None: ...
    def find(self, path: str, namespaces: Optional[Dict[str, str]] = ...) -> Optional[Element]: ...
    def findall(self, path: str, namespaces: Optional[Dict[str, str]] = ...) -> List[Element]: ...
    @overload
    def findtext(self, path: str, default: None = ..., namespaces: Optional[Dict[str, str]] = ...) -> Optional[str]: ...
    @overload
    def findtext(self, path: str, default: _T, namespaces: Optional[Dict[str, str]] = ...) -> Union[_T, str]: ...
    @overload
    def get(self, key: str, default: None = ...) -> Optional[str]: ...
    @overload
    def get(self, key: str, default: _T) -> Union[str, _T]: ...
    def insert(self, __index: int, __subelement: Element) -> None: ...
    def items(self) -> ItemsView[str, str]: ...
    def iter(self, tag: Optional[str] = ...) -> Generator[Element, None, None]: ...
    def iterfind(self, path: str, namespaces: Optional[Dict[str, str]] = ...) -> Generator[Element, None, None]: ...
    def itertext(self) -> Generator[str, None, None]: ...
    def keys(self) -> KeysView[str]: ...
    def makeelement(self, __tag: str, __attrib: Dict[str, str]) -> Element: ...
    def remove(self, __subelement: Element) -> None: ...
    def set(self, __key: str, __value: str) -> None: ...
    def __delitem__(self, i: Union[int, slice]) -> None: ...
    @overload
    def __getitem__(self, i: int) -> Element: ...
    @overload
    def __getitem__(self, s: slice) -> MutableSequence[Element]: ...
    def __len__(self) -> int: ...
    @overload
    def __setitem__(self, i: int, o: Element) -> None: ...
    @overload
    def __setitem__(self, s: slice, o: Iterable[Element]) -> None: ...
    if sys.version_info < (3, 9):
        def getchildren(self) -> List[Element]: ...
        def getiterator(self, tag: Optional[str] = ...) -> List[Element]: ...

def SubElement(parent: Element, tag: str, attrib: Dict[str, str] = ..., **extra: str) -> Element: ...
def Comment(text: Optional[str] = ...) -> Element: ...
def ProcessingInstruction(target: str, text: Optional[str] = ...) -> Element: ...

PI: Callable[..., Element]

class QName:
    text: str
    def __init__(self, text_or_uri: str, tag: Optional[str] = ...) -> None: ...

class ElementTree:
    def __init__(self, element: Optional[Element] = ..., file: Optional[_File] = ...) -> None: ...
    def getroot(self) -> Element: ...
    def parse(self, source: _File, parser: Optional[XMLParser] = ...) -> Element: ...
    def iter(self, tag: Optional[str] = ...) -> Generator[Element, None, None]: ...
    if sys.version_info < (3, 9):
        def getiterator(self, tag: Optional[str] = ...) -> List[Element]: ...
    def find(self, path: str, namespaces: Optional[Dict[str, str]] = ...) -> Optional[Element]: ...
    @overload
    def findtext(self, path: str, default: None = ..., namespaces: Optional[Dict[str, str]] = ...) -> Optional[str]: ...
    @overload
    def findtext(self, path: str, default: _T, namespaces: Optional[Dict[str, str]] = ...) -> Union[_T, str]: ...
    def findall(self, path: str, namespaces: Optional[Dict[str, str]] = ...) -> List[Element]: ...
    def iterfind(self, path: str, namespaces: Optional[Dict[str, str]] = ...) -> Generator[Element, None, None]: ...
    def write(
        self,
        file_or_filename: _File,
        encoding: Optional[str] = ...,
        xml_declaration: Optional[bool] = ...,
        default_namespace: Optional[str] = ...,
        method: Optional[str] = ...,
        *,
        short_empty_elements: bool = ...,
    ) -> None: ...
    def write_c14n(self, file: _File) -> None: ...

def register_namespace(prefix: str, uri: str) -> None: ...

if sys.version_info >= (3, 8):
    @overload
    def tostring(
        element: Element,
        encoding: None = ...,
        method: Optional[str] = ...,
        *,
        xml_declaration: Optional[bool] = ...,
        default_namespace: Optional[str] = ...,
        short_empty_elements: bool = ...,
    ) -> bytes: ...
    @overload
    def tostring(
        element: Element,
        encoding: Literal["unicode"],
        method: Optional[str] = ...,
        *,
        xml_declaration: Optional[bool] = ...,
        default_namespace: Optional[str] = ...,
        short_empty_elements: bool = ...,
    ) -> str: ...
    @overload
    def tostring(
        element: Element,
        encoding: str,
        method: Optional[str] = ...,
        *,
        xml_declaration: Optional[bool] = ...,
        default_namespace: Optional[str] = ...,
        short_empty_elements: bool = ...,
    ) -> Any: ...
    @overload
    def tostringlist(
        element: Element,
        encoding: None = ...,
        method: Optional[str] = ...,
        *,
        xml_declaration: Optional[bool] = ...,
        default_namespace: Optional[str] = ...,
        short_empty_elements: bool = ...,
    ) -> List[bytes]: ...
    @overload
    def tostringlist(
        element: Element,
        encoding: Literal["unicode"],
        method: Optional[str] = ...,
        *,
        xml_declaration: Optional[bool] = ...,
        default_namespace: Optional[str] = ...,
        short_empty_elements: bool = ...,
    ) -> List[str]: ...
    @overload
    def tostringlist(
        element: Element,
        encoding: str,
        method: Optional[str] = ...,
        *,
        xml_declaration: Optional[bool] = ...,
        default_namespace: Optional[str] = ...,
        short_empty_elements: bool = ...,
    ) -> List[Any]: ...

else:
    @overload
    def tostring(
        element: Element, encoding: None = ..., method: Optional[str] = ..., *, short_empty_elements: bool = ...
    ) -> bytes: ...
    @overload
    def tostring(
        element: Element, encoding: Literal["unicode"], method: Optional[str] = ..., *, short_empty_elements: bool = ...
    ) -> str: ...
    @overload
    def tostring(element: Element, encoding: str, method: Optional[str] = ..., *, short_empty_elements: bool = ...) -> Any: ...
    @overload
    def tostringlist(
        element: Element, encoding: None = ..., method: Optional[str] = ..., *, short_empty_elements: bool = ...
    ) -> List[bytes]: ...
    @overload
    def tostringlist(
        element: Element, encoding: Literal["unicode"], method: Optional[str] = ..., *, short_empty_elements: bool = ...
    ) -> List[str]: ...
    @overload
    def tostringlist(
        element: Element, encoding: str, method: Optional[str] = ..., *, short_empty_elements: bool = ...
    ) -> List[Any]: ...

def dump(elem: Element) -> None: ...

if sys.version_info >= (3, 9):
    def indent(tree: Union[Element, ElementTree], space: str = ..., level: int = ...) -> None: ...

def parse(source: _File, parser: Optional[XMLParser] = ...) -> ElementTree: ...
def iterparse(
    source: _File, events: Optional[Sequence[str]] = ..., parser: Optional[XMLParser] = ...
) -> Iterator[Tuple[str, Any]]: ...

class XMLPullParser:
    def __init__(self, events: Optional[Sequence[str]] = ..., *, _parser: Optional[XMLParser] = ...) -> None: ...
    def feed(self, data: bytes) -> None: ...
    def close(self) -> None: ...
    def read_events(self) -> Iterator[Tuple[str, Element]]: ...

def XML(text: Union[str, bytes], parser: Optional[XMLParser] = ...) -> Element: ...
def XMLID(text: Union[str, bytes], parser: Optional[XMLParser] = ...) -> Tuple[Element, Dict[str, Element]]: ...

# This is aliased to XML in the source.
fromstring = XML

def fromstringlist(sequence: Sequence[Union[str, bytes]], parser: Optional[XMLParser] = ...) -> Element: ...

# This type is both not precise enough and too precise. The TreeBuilder
# requires the elementfactory to accept tag and attrs in its args and produce
# some kind of object that has .text and .tail properties.
# I've chosen to constrain the ElementFactory to always produce an Element
# because that is how almost everyone will use it.
# Unfortunately, the type of the factory arguments is dependent on how
# TreeBuilder is called by client code (they could pass strs, bytes or whatever);
# but we don't want to use a too-broad type, or it would be too hard to write
# elementfactories.
_ElementFactory = Callable[[Any, Dict[Any, Any]], Element]

class TreeBuilder:
    def __init__(self, element_factory: Optional[_ElementFactory] = ...) -> None: ...
    def close(self) -> Element: ...
    def data(self, __data: Union[str, bytes]) -> None: ...
    def start(self, __tag: Union[str, bytes], __attrs: Dict[Union[str, bytes], Union[str, bytes]]) -> Element: ...
    def end(self, __tag: Union[str, bytes]) -> Element: ...

if sys.version_info >= (3, 8):
    class C14NWriterTarget:
        def __init__(
            self,
            write: Callable[[str], Any],
            *,
            with_comments: bool = ...,
            strip_text: bool = ...,
            rewrite_prefixes: bool = ...,
            qname_aware_tags: Optional[Iterable[str]] = ...,
            qname_aware_attrs: Optional[Iterable[str]] = ...,
            exclude_attrs: Optional[Iterable[str]] = ...,
            exclude_tags: Optional[Iterable[str]] = ...,
        ) -> None: ...

class XMLParser:
    parser: Any
    target: Any
    # TODO-what is entity used for???
    entity: Any
    version: str
    if sys.version_info >= (3, 8):
        def __init__(self, *, target: Any = ..., encoding: Optional[str] = ...) -> None: ...
    else:
        def __init__(self, html: int = ..., target: Any = ..., encoding: Optional[str] = ...) -> None: ...
        def doctype(self, __name: str, __pubid: str, __system: str) -> None: ...
    def close(self) -> Any: ...
    def feed(self, __data: Union[str, bytes]) -> None: ...
