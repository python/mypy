from gzip import GzipFile
from io import FileIO, TextIOWrapper

TextIOWrapper(FileIO(""))
TextIOWrapper(FileIO(13))
TextIOWrapper(GzipFile(""))
