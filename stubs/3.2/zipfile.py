# TODO these are incomplete

from typing import List, Undefined, Tuple, BinaryIO, Union

ZIP_STORED = 0
ZIP_DEFLATED = 0

def is_zipfile(filename: Union[str, BinaryIO]) -> bool: pass

class ZipInfo:
    filename = ''
    date_time = Undefined(Tuple[int, int, int, int, int, int])
    compressed_size = 0
    file_size = 0

class ZipFile:
    def __init__(self, file: Union[str, BinaryIO], mode: str = 'r',
                 compression: int = ZIP_STORED,
                 allowZip64: bool = False) -> None: pass
    def close(self) -> None: pass
    def getinfo(name: str) -> ZipInfo: pass
    def infolist(self) -> List[ZipInfo]: pass
    def namelist(self) -> List[str]: pass
    def read(self, name: Union[str, ZipInfo], pwd: str = None) -> bytes: pass
    def write(self, filename: str, arcname: str = None,
              compress_type: int = None) -> None: pass

    def __enter__(self) -> 'ZipFile': pass
    def __exit__(self, type, value, traceback) -> bool: pass
