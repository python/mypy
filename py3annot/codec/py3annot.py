from __future__ import absolute_import

import codecs
import cStringIO
import traceback
from encodings import utf_8

from .tokenizer import py3annot_tokenize, py3annot_untokenize

def py3annot_transform(stream):
    try:
        output = py3annot_untokenize(py3annot_tokenize(stream.readline))
    except Exception, ex:
        print ex
        traceback.print_exc()
        raise

    return output

def py3annot_transform_string(text):
    stream = cStringIO.StringIO(text)
    return py3annot_transform(stream)

def py3annot_decode(input, errors='strict'):
    return utf_8.decode(py3annot_transform_string(input), errors)

class Py3annotIncrementalDecoder(utf_8.IncrementalDecoder):
    def decode(self, input, final=False):
        self.buffer += input
        if final:
            buff = self.buffer
            self.buffer = ''
            return super(Py3annotIncrementalDecoder, self).decode(
                py3annot_transform_string(buff), final=True)

class Py3annotStreamReader(utf_8.StreamReader):
    def __init__(self, *args, **kwargs):
        codecs.StreamReader.__init__(self, *args, **kwargs)
        self.stream = cStringIO.StringIO(py3annot_transform(self.stream))
