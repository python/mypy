# TODO these are incomplete

int ZIP_STORED
int ZIP_DEFLATED

bool is_zipfile(str filename): pass
bool is_zipfile(IO filename): pass

class ZipFile:
    void __init__(self, str file, str mode='r',
                  int compression=ZIP_STORED, bool allowZip64=False): pass
    void __init__(self, IO file, str mode='r',
                  int compression=ZIP_STORED, bool allowZip64=False): pass
    void close(self): pass
    ZipInfo getinfo(str name): pass
    ZipInfo[] infolist(self): pass
    str[] namelist(self): pass
    bytes read(self, str name, str pwd=None): pass
    bytes read(self, ZipInfo name, str pwd=None): pass
    void write(self, str filename, str arcname=None,
               int compress_type=None): pass
    
    ZipFile __enter__(self): pass
    void __exit__(self, type, value, traceback): pass

class ZipInfo:
    str filename
    tuple<int, int, int, int, int, int> date_time
    int compressed_size
    int file_size
