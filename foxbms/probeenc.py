"""
:since:     Tue Mar 29 11:57:50 CEST 2016
:author:    Tim Fuehner <tim.fuehner@iisb.fraunhofer.de>
$Id$
"""

import codecs

def guessEncoding(fname):
    encodings = ['utf-8', 'iso-8859-1', 'ascii', 'windows-1250', 'windows-1252']
    for e in encodings:
        try:
            with codecs.open(fname, 'r', encoding=e) as f:
                _read = f.readlines()
        except UnicodeDecodeError:
            pass
        else:
            return e
    return None


if __name__ == '__main__':
    import sys
    print dir(codecs)
    print guessEncoding(sys.argv[1])
