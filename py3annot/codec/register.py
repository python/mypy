from __future__ import absolute_import

import codecs
import encodings
import sys

def search_function(encoding):
    if encoding != 'py3annot':
        return None
    # Assume utf8 encoding
    utf8 = encodings.search_function('utf8')
    if sys.version_info[0] == 3:  # Python 3
        return utf8
    else:  # Python 2
        from .py3annot import py3annot_decode, Py3annotIncrementalDecoder, Py3annotStreamReader
        return codecs.CodecInfo(name='py3annot',
                                encode=utf8.encode,
                                decode=py3annot_decode,
                                incrementalencoder=utf8.incrementalencoder,
                                incrementaldecoder=Py3annotIncrementalDecoder,
                                streamreader=Py3annotStreamReader,
                                streamwriter=utf8.streamwriter)

codecs.register(search_function)

def main():
    fn = sys.argv[1]
    with open(fn) as fp:
        data = fp.read()
    print(codecs.decode(data, 'py3annot'))

if __name__ == '__main__':
    main()
