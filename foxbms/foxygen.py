"""
:since:     Wed Jan 13 17:22:02 CET 2016
:author:    Tim Fuehner <tim.fuehner@iisb.fraunhofer.de>
$Id$
"""

import os
import sys
import re
import operator
import fnmatch
import shutil

def hfiles(root = '.'):
    for root, dirnames, filenames in os.walk(root):
        for filename in fnmatch.filter(filenames, '*.h'):
            yield os.path.join(root, filename)

class Macro(object):

    def __init__(self, name, value, comment, activated = True, linenr = 0):
        self.name = name
        self.value = value
        self.comment = comment
        self.activated = activated
        self.linenr = linenr

    def __str__(self):

        if self.activated:
            ret = ''
        else:
            ret = '//'

        _repl = {}

        _repl['name'] = self.name
        if self.__dict__['value'] is None:
            _repl['value'] = ''
        else: 
            if type(self.__dict__['value']) in [unicode, str]:
                _repl['value'] = ' "' + self.__dict__['value'] + '"'
            else:
                _repl['value'] = ' ' + repr(self.__dict__['value'])
        if self.__dict__['comment'] is None:
            _repl['comment'] = ''
        else: 
            _repl['comment'] = ' ' + self.__dict__['value']

        ret += "#define %(name)s%(value)s%(comment)s" % _repl
        return ret

class Variable(object):

    KEYS = ['variable', 'type', 'validator', 'unit', 'description',
            'level', 'group']
    LEVELS = ['user', 'advanced', 'devel', 'debug', 'read-only']
    functionRE = re.compile('^(\w+)\s*\((.*)\)$')

    def_deactRE1 = re.compile('^\s*//\s*#define\s+(\S+)(\s+(\S+))?\s*(//.*)?$')
    def_deactRE2 = re.compile('^\s*/\*\s*#define\s+(\S+)(\s+(\S+))?\s*\*/\s*(//.*)?$')
    defRE = re.compile('^\s*#define\s+(\S+)(\s+(\S+))?\s*(//.*)?$')
    lineCommentRE = re.compile('^\s*//.*')

    def __init__(self):
        self.position = [-1, -1]
        self.name = None
        self.type = None
        self.typeargs = []
        self.value = None
        self.validator = lambda x: True
        self.valid = None
        self.descrPos = None
        self.fname = None
        self.level = 'read-only'
        self.hint = None
        self.choices = []
        self.group = None
        self.changed = False
        self.unit = None

    def validate(self, x):
        if not self.type in [str, unicode]:
            if not isinstance(type(x), self.type):
                return False
        else:
            if self.type == 'select':
                if not isinstance(type(x), int):
                    return False
                if x < 0:
                    return False
                if x >= self.typeargs[0]:
                    return False
            elif self.type == 'toggle':
                if not isinstance(type(x), bool):
                    return False
            elif self.type == 'choice':
                if not x in self.typeargs:
                    return False
            else:
                raise NotImplementedError('type %s not implemented' % self.type)

        return self.validator(x)


    def addTag(self, key, value):
        if 'variable'.startswith(key):
            self.name = value
        elif key == 'type':
            self.setType(value)
        elif 'validator'.startswith(key):
            self.valid = value
            self.validator = eval('lambda x: %s' % value) 
        elif 'default'.startswith(key):
            self.default = eval(value) 
        else:
            for k in self.KEYS:
                if k.startswith(key):
                    self.__dict__[key] = value

    def setType(self, value):
        _match = self.functionRE.match(value.strip())
        if _match:
            self.type = _match.group(1)
            if self.type == 'switch':
                self.type = 'select'
            # FIXME recursive descent required
            self.typeargs = eval(_match.group(2))
            if not type(self.typeargs) in [list, tuple]:
                self.typeargs = [self.typeargs]
        else:
            print value.strip()
            if value in ['toggle', 'switch']:
                self.type = 'toggle'
            else:
                self.type = eval(value.strip())
            self.typeargs = []

    def setValue(self, value):
        if self.value != value:
            self.changed = True
            self.value = value

    def reset(self):
        self.setValue(self.default)

    def getCodeRange(self):
        if self.type == 'select':
            return self.typeargs[0]
        else:
            return 1

    def addMacro(self, _match, _lines, activated, linenr):
        self.macros += [Macro(_match.group(1), _match.group(3),
            _match.group(4), activated = activated, linenr = linenr)]
        self.code += ["%(" + str(_lines) + ")s"]
        if self.type == 'select': 
            self.choices += [_match.group(1)]
            if activated:
                self.value = _lines
            if _lines < (self.getCodeRange() - 1):
                return False
        elif self.type == 'toggle':
            self.value = activated
        else:
            self.value = self.type(_match.group(3))
        self.position[1] = linenr
        return True

    def parseCode(self, text, linenr):
        self.macros = []
        _lines = 0
        self.code = []
        self.position[0] = linenr + 1
        for i,l in enumerate(text):
            linenr += 1
            _match = self.defRE.match(l)
            if _match:
                if self.addMacro(_match, _lines, True, linenr):
                    break
                else:
                    _lines += 1
                    continue
            _match = self.def_deactRE1.match(l)
            if _match:
                if self.addMacro(_match, _lines, False, linenr):
                    break
                else:
                    _lines += 1
                    continue
            _match = self.def_deactRE2.match(l)
            if _match:
                if self.addMacro(_match, _lines, False, linenr):
                    break
                else:
                    _lines += 1
                    continue

            # ignore but store empty and comment lines
            _match = self.lineCommentRE.match(l)
            if _match:
                self.code += [l]
                continue

            if l.strip() == '':
                self.code += [l]
                continue

    def __str__(self):
        ret = ''
        for k,v in self.__dict__.iteritems():
            ret += '%s: %s\n' % (k,v)
        return ret[:-1]

    def getCode(self):

        if self.type == 'select':
            for i,m in enumerate(self.macros):
                if self.value == i:
                    m.activated = True
                else:
                    m.activated = False
        elif self.type == 'toggle':
            self.macros[0].activated = True
        else:
            self.macros[0].value = self.type(self.value)

        _d = []
        for i,c in enumerate(self.code):
            _d += [c % dict(zip([str(x) for x in range(len(self.macros))],
                self.macros))]
        return _d


class CommentExtractor(object):

    startRE = re.compile('/\*fox\s?(.*)')
    endRE = re.compile('(.*?)\*/(.*)')
    commentRE = re.compile('\s*\*\s*(.*)')
    atRE = re.compile('([^@]*)(@[^@]*)*?')
    varRE = re.compile('^\s*(@\S*)\s+(.*)')


    def __init__(self, txt, linenr = 0, fname = None):
        self.txtl = txt
        self.comment = []
        self.pushback = ''
        self.original = ''
        self.remainder = []
        self.pos = [-1, -1]
        self.linenr = linenr
        self.variable = Variable()
        self.fname = fname

    def _start(self, txtl):
        for i,l in enumerate(txtl):
            self.linenr += 1
            _match = self.startRE.match(l)
            if _match:
                self.pos[0] = self.linenr
                self.remainder = [_match.group(1)] + txtl[i + 1:]
                return True
        return False

    def _end(self, txtl):
        for i,l in enumerate(txtl):
            self.linenr += 1
            _match = self.endRE.match(l)
            if _match:
                self.pos[1] = self.linenr - 1
                self.comment += [_match.group(1)]
                _r = _match.group(2)
                if _r.strip() != '':
                    self.remainder = [_r] + txtl[i + 1:]
                    # correct for line duplication
                    self.linenr -= 2
                else:
                    self.remainder = txtl[i + 1:]
                    self.linenr -= 1
                    
                return True
            self.comment += [l]
        return False

    def read(self):
        self.remainder = self.txtl
        if self._start(self.remainder):
            if not self._end(self.remainder):
                raise RuntimeError('Unmatched fox comment started in line: %d' % _start)
        else:
            return False
        _comment = []
        for c in self.comment:
            _match = self.commentRE.match(c)
            if _match:
                _comment += [_match.group(1)]
            else:
                _comment += [c]
        self.comment = ' '.join(_comment)

        for l in re.split('(@[^@]*)', self.comment):
            _match = self.varRE.match(l)
            if _match:
                a = _match.groups()
                self.variable.addTag(a[0][1:].strip(), ' '.join([x.strip() for x in a[1:]]))
            elif l.strip() != '':
                self.variable.addTag('description', l.strip())

        self.variable.fname = self.fname
        self.variable.descrPos = self.pos

        _cr = self.variable.getCodeRange()

        self.variable.parseCode(self.remainder, self.linenr)

        return True


class Variables(object):

    def __init__(self):
        self.variables = []

    def addVariable(self, var):
        self.variables += [var]

    def resetAll(self):
        for v in self:
            v.reset()

    def __getitem__(self, name):
        for x in self:
            if x.name == name:
                return x
        raise IndexError('no such variable: %s' % name)

    def getVariables(self, groups = None, levels = None, sort = None):
        print groups
        _d = [x for x in self.variables 
                if (not groups or x.group in groups) and 
                (not levels or x.level in levels)]
        if sort:
            if sort == True:
                return sorted(_d, key=operator.attrgetter('name'))
            else:
                return sorted(_d, key=operator.attrgetter(*sort))
        else:
            return _d

    def __iter__(self):
        for v in self.variables:
            yield v

    def getGroups(self):
        groups = []
        for v in self:
            if v.group:
                groups += [v.group]
        return list(set(groups))

class HeaderFile(object):

    def __init__(self, fname, variables):
        self.fname = fname
        self.fname_orig = fname + '.orig'
        self.variables = variables
        self.replacePositions = []
        self.myvars = Variables()
        self.backup = True

    def addVariable(self, var):
        self.variables.addVariable(var)
        self.myvars.addVariable(var)
        self.addRPositions(var.position)

    def addRPositions(self, pos):
        self.replacePositions += [pos]

    def hasChanged(self):
        for v in self.myvars:
            if v.changed:
                return True
        return False

    def getCode(self):
        _txt = self._txt.split('\n')
        for v in self.myvars:
            if v.changed:
                _txt[v.position[0] - 1:v.position[1]] = v.getCode()
        return '\n'.join(_txt)

    def read(self):
        with open(self.fname, 'r') as f:
            self._txt = f.read()

    def doBackup(self):
        shutil.copy(self.fname, self.fname_orig)

    def resetAll(self):
        self.myvars.resetAll()

    def write(self):
        if self.backup:
            self.doBackup()
        with open(self.fname, 'w') as f:
            f.write(self.getCode())

    def generate(self):
        if self.hasChanged():
            self.write()
        
    def collect(self):
        linenr = 0
        txt = self._txt.split('\n')
        while 1:
            c = CommentExtractor(txt, linenr, fname = self.fname)
            found = c.read()
            linenr = c.linenr
            txt = c.remainder
            if found:
                self.addVariable(c.variable)
            else:
                break


class SourceTree(object):

    def __init__(self, root = '.', variables = None):
        self.root = root
        self.files = []
        self.variables = variables

    def collect(self):
        for f in hfiles(self.root):
            hf = HeaderFile(f, self.variables)
            hf.read()
            hf.collect()
            self.files += [hf]

    def generate(self):
        for f in self.files:
            if f.hasChanged() or 1:
                print >>sys.stderr, "writing %s ..." % f.fname,
                print >>sys.stderr, "done"

def main():
    variables = Variables()
    try:
        _root = sys.argv[1]
    except:
        _root = '.'
    s = SourceTree(_root, variables)
    s.collect()
    s.generate()

    '''
    for x in variables.getVariables(sort = True):
        print x.name, x.fname
    '''

def kmain():

    var = Variables()
    hf = HeaderFile(sys.argv[1], var)
    hf.read()
    hf.collect()
    hf.myvars['number of temperature sensors'].setValue(23)
    hf.resetAll()
    hf.generate()
    print var.getGroups()

    '''
    print hf.hasChanged()
    print var['number of temperature sensors'].value
    for x in var.getVariables(sort = True):
        print x.name, x.fname
    '''


if __name__ == '__main__':
    main()



