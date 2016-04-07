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
import logging
import json
import codecs
import probeenc

def hfiles(root = '.'):
    for root, dirnames, filenames in os.walk(root):
        for filename in fnmatch.filter(filenames, '*.h'):
            yield os.path.join(root, filename)

class Macro(object):

    def __init__(self, name, value, comment, activated = True, linenr = 0,
            type = None):
        self.name = name
        self.value = value
        self.type = None
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
            _repl['value'] = ' ' + str(self.__dict__['value'])
            '''
            FIXME consider including type check
            if type(self.__dict__['value']) in [unicode, str]:
                _repl['value'] = ' "' + self.__dict__['value'] + '"'
            else:
                _repl['value'] = ' ' + repr(self.__dict__['value'])
            '''
        if self.__dict__['comment'] is None:
            _repl['comment'] = ''
        else: 
            _repl['comment'] = ' ' + self.__dict__['comment']

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
        self.group = 'misc'
        self.changed = False
        self.unit = None
        self.default = None
        self.description = 'n/a'

    def validate(self, x):

        if not type(self.type) in [str, unicode]:
            if not isinstance(x, self.type):
                return False
        else:
            if self.type in ['select', 'switch']:
                if not isinstance(x, int):
                    return False
                if x < 0:
                    return False
                if x >= self.typeargs[0]:
                    return False
            elif self.type == 'toggle':
                if not isinstance(x, bool):
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
                    if k == 'level' and not value in self.LEVELS:
                        logging.warning("%s:%d: Unknown level: %s. Resetting to read-only." % (self.fname, self.descrPos[0], value))
                    else:
                        self.__dict__[k] = value

    def setType(self, value):
        _match = self.functionRE.match(value.strip())
        if _match:
            self.type = _match.group(1)
            #if self.type == 'switch':
            #    self.type = 'select'
            # FIXME recursive descent required
            self.typeargs = eval(_match.group(2))
            if not type(self.typeargs) in [list, tuple]:
                self.typeargs = [self.typeargs]
        else:
            if value in ['toggle']:
                self.type = 'toggle'
            else:
                try:
                    self.type = eval(value.strip())
                except:
                    raise RuntimeError('unknown type: %s' % value.strip())
            self.typeargs = []

    def setValue(self, value):
        if self.value != value:
            if not self.validate(value):
                logging.warning('variable %s: %s:%d: value not valid: %s. Refuse to change.' % (self.name, self.fname, self.descrPos[0], str(value)))
            else:
                self.changed = True
                self.value = value

    def reset(self):
        if not self.default is None:
            self.setValue(self.default)

    def getCodeRange(self):
        if self.type in ['select', 'switch']:
            return self.typeargs[0]
        else:
            return 1

    def addMacro(self, _match, _lines, activated, linenr):
        self.macros += [Macro(_match.group(1), _match.group(3),
            _match.group(4), activated = activated, linenr = linenr)]
        self.code += ["%(" + str(_lines) + ")s"]
        if self.type in ['select', 'switch']: 
            if self.type == 'select':
                if _match.group(2) in [None, ''] or _match.group(2) == '':
                    raise RuntimeError('Macro definition expected for type select, did you want to use switch?')
                self.choices += [_match.group(2).strip()]
            else:
                self.choices += [_match.group(1).strip()]
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


    def toReST(self):
        _d = {}
        _var = self
        _d['name'] = _var.name
        _d['underline'] = '=' * len(_var.name)
        _d['description'] = _var.description
        _d['type'] = repr(_var.type)
        _h = '''\
%(name)s
%(underline)s

%(description)s

:type: %(type)s
'''% _d
        if not _var.unit is None:
            _h += ':unit: ' +  _var.unit + '\n'
        if not _var.valid is None:
            _h += ':valid: ' +  _var.valid + '\n'
        if not _var.default is None:
            _h += ':default: ' +  repr(_var.default) + '\n'
        if _var.type in ['select', 'switch']:
            _h += ':choices: ' + ", ".join(_var.choices) + '\n'
        _h += ':file: ' +  os.path.abspath(_var.fname) + ':%d\n' % _var.descrPos[0]
        _h += '\n'
        return _h


    def getCode(self):

        if self.type in ['select', 'switch']:
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
        self.default = None

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
        self.variable.fname = self.fname
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
            self.variable.descrPos = self.pos
            _match = self.varRE.match(l)
            if _match:
                a = _match.groups()
                try:
                    self.variable.addTag(a[0][1:].strip(), ' '.join([x.strip() for x in a[1:]]))
                except Exception, e:
                    raise RuntimeError('%s:%s: %s' % (self.fname, self.linenr, str(e)))
            elif l.strip() != '':
                self.variable.addTag('description', l.strip())

        self.variable.fname = self.fname
        self.variable.descrPos = self.pos

        _cr = self.variable.getCodeRange()

        if self.variable.type is None:
            raise RuntimeError('%s:%s: %s' % (self.fname, self.linenr, 'no type defined'))

        if self.variable.default is None:
            logging.warning('%s:%d: %s' % (self.fname, self.pos[0], 'no default value specified'))

        try:
            self.variable.parseCode(self.remainder, self.linenr)
        except Exception, e:
            raise RuntimeError('%s:%s: %s' % (self.fname, self.linenr, str(e)))

        return True


class Variables(object):

    def __init__(self):
        self.variables = []
        self.description = "No description"

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

    def __setitem__(self, name, value):
        for i,x in enumerate(self.variables):
            if x.name == name:
                self.variables[i].value = value
                return
        raise IndexError('no such variable: %s' % name)

    def getVariables(self, groups = None, levels = None, sort = None):
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

    def fixDuplicates(self):
        counter = 0
        _pname = None
        _vars = self.getVariables(sort = True)
        for i,v in enumerate(_vars):
            if not _pname is None and _pname == v.name:
                co += 1
                v.name = _pname + "-%.3d" % co
                logging.warning("%s:%d: duplicate variable name found.\n" % (v.fname, v.descrPos[0]) + 
                        "    first occurence: %s:%d" % (_vars[i - co].fname, _vars[i - co].descrPos[0]) +
                        ".\n    Renaming it to: %s." %  v.name)
                if co == 1:
                    _vars[i - 1].name = _pname + '-000'
            else:
                co = 0
                _pname = v.name

    def setValuesFromDict(self, d, full = False):
        if full:
            for k,v in d.iteritems():
                if k == '@description':
                    self.description = v
                    continue
                try:
                    self[k].setValue(v['value'])
                except Exception, e:
                    try:
                        logging.warning('variable %s:%s:%d: %s' % (k, self[k].fname, self[k].descrPos[0], str(e)))
                    except Exception, e:
                        logging.warning('variable %s: %s' % (k, str(e)))
        else:
            for k,v in d.iteritems():
                try:
                    self[k].setValue(v)
                except Exception, e:
                    try:
                        logging.warning('variable %s:%s:%d: %s' % (k, self[k].fname, self[k].descrPos[0], str(e)))
                    except Exception, e:
                        logging.warning('variable %s: %s' % (k, str(e)))

    def getValuesAsDict(self, full = False):
        _d = {}
        if full:
            _d['@description'] = self.description
            for v in self.variables:
                try:
                    _d[v.name] = {}
                    _d[v.name]['value'] = v.value
                    _d[v.name]['default'] = v.default
                    _d[v.name]['descrPos'] = v.descrPos
                    if not v.choices is None:
                        _d[v.name]['choices'] = v.choices
                    _d[v.name]['descrPos'] = v.descrPos
                    for k in ['type', 'description', 'valid', 'unit',
                            'fname', 'group', 'level']:
                        try:
                            _d[v.name][k] = unicode(v.__dict__[k])
                        except UnicodeDecodeError:
                            _d[v.name][k] = v.__dict__[k].decode('utf-8')
                except Exception, e:
                    logging.warning('variable %s:%s:%d: %s' % (v.name, v.fname, v.descrPos[0], str(e)))
        else:
            for v in self.variables:
                try:
                    _d[v.name] = v.value
                except Exception, e:
                    logging.warning('variable %s:%s:%d: %s' % (v.name, v.fname, v.descrPos[0], str(e)))
        return _d

    def dumpJson(self, fname):
        with open(fname, 'w') as f:
            json.dump(self.getValuesAsDict(full = True), f, sort_keys=True, indent=4, separators=(',', ': '))

    def loadJson(self, fname):
        with open(fname, 'r') as f:
            self.setValuesFromDict(json.load(f), full = True)


class HeaderFile(object):

    def __init__(self, fname, variables):
        self.fname = fname
        self.fname_orig = fname + '.orig'
        self.variables = variables
        self.replacePositions = []
        self.myvars = Variables()
        self.backup = True
        self.encoding = 'utf-8'

    def addVariable(self, var):
        if var.name is None:
            var.name = var.group
            logging.warning("%s:%d: variable has no name." % (self.fname, var.descrPos[0]))
            
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
        self.encoding = probeenc.guessEncoding(self.fname)
        with codecs.open(self.fname, 'r', encoding = self.encoding) as f:
            self._txt = f.read()

    def doBackup(self):
        shutil.copy(self.fname, self.fname_orig)

    def resetAll(self):
        self.myvars.resetAll()

    def write(self):
        if self.backup:
            self.doBackup()
        logging.info("writing %s" % self.fname)
        with codecs.open(self.fname, 'w', encoding = self.encoding) as f:
            f.write(self.getCode())

    def generate(self):
        if self.hasChanged():
            self.write()
        
    def collect(self):
        linenr = 0
        txt = self._txt.split('\n')
        while 1:
            c = CommentExtractor(txt, linenr, fname = self.fname)
            error = False
            try:
                found = c.read()
            except Exception, e:
                logging.warning(str(e) + ". ignoring variable")
                error = True
            linenr = c.linenr
            txt = c.remainder
            if error:
                continue
            if found:
                self.addVariable(c.variable)
            else:
                break


class SourceTree(object):

    def __init__(self, root = '.', variables = None):
        self.root = root
        self.files = []
        self.variables = variables
        self.backup = True

    def collect(self):
        if os.path.isfile(self.root):
            _files = [self.root]
        else:
            _files = hfiles(self.root)
        for f in _files:
            hf = HeaderFile(f, self.variables)
            hf.backup = self.backup
            hf.read()
            hf.collect()
            self.files += [hf]

    def resetAll(self):
        for f in self.files:
            f.resetAll()

    def generate(self, backup = None):
        for f in self.files:
            if not backup is None:
                f.backup = backup
            f.generate()
            f.backup = self.backup

def getpath(parser, arg, mode = 'r'):
    if mode == 'r' and not os.path.isfile(arg):
        parser.error("The file %s does not exist!" % arg)
    elif mode == 'r|d' and not os.path.exists(arg):
        parser.error("The file/directory %s does not exist!" % arg)
    elif mode == 'w' and not os.path.isdir(os.path.dirname(os.path.abspath(arg))):
        parser.error("%s is not a valid directory!" % os.path.dirname(os.path.abspath(arg)))
    else:
        return os.path.abspath(arg)

def main():
    import argparse

    parser = argparse.ArgumentParser(description='foxBMS---foxyGen', 
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog = '''\
Examples:
# generate configured files in ``/home/me/foxbms/foxbms-vehicle`` from
# ``mysettings.json``:
%s --generate mysettings.json /home/me/foxbms/foxbms-vehicle

# extract configuration from ``/home/me/foxbms/foxbms-vehicle`` and
# store it into ``mysettings.json``:
%s --extract mysettings.json /home/me/foxbms/foxbms-vehicle

# validate foxyGen syntax of files in /home/me/foxbms/foxbms-vehicle
%s /home/me/foxbms/foxbms-vehicle

Copyright (c) 2015, 2016 Fraunhofer IISB.
All rights reserved.
This program has been released under the conditions of the 3-clause BSD
license.

author: Tim Fuehner <tim.fuehner@iisb.fraunhofer.de>

''' % (sys.argv[0], sys.argv[0], sys.argv[0]))

    parser.add_argument('-v', '--verbosity', action='count', default=0, help="increase output verbosity")

    parser.add_argument('--extract',  '-e', type=lambda x: getpath(parser, x, 'w'),
            metavar='JSON FILE',
            help='read configuration from sources and write to JSON file')
    parser.add_argument('--generate',  '-g', type=lambda x: getpath(parser, x, 'r'),
            metavar='JSON FILE',
            help='read configuration from JSON file and write')
    parser.add_argument('--reset',  '-r', action='store_true', help='reset to default values')
    parser.add_argument('--backup',  '-b', action='store_true', help='backup original files (.orig)')
    parser.add_argument('source', metavar = 'SOURCE or SOURCETREE', help='source or source tree')

    args = parser.parse_args()

    if args.verbosity == 1:
        logging.basicConfig(level = logging.INFO)
    elif args.verbosity > 1:
        logging.basicConfig(level = logging.DEBUG)
    else:
        logging.basicConfig(level = logging.WARNING)

    if not args.extract is None and not args.generate is None:
        parser.error('Cannot use --extract together with --generate')

    if (not args.extract is None or not args.generate is None) and args.reset:
        parser.error('Cannot use --extract or --generate with --reset')

    variables = Variables()
    s = SourceTree(args.source, variables)
    s.collect()
    variables.fixDuplicates()

    if not args.extract is None:
        variables.dumpJson(args.extract)
    if not args.generate is None:
        variables.loadJson(args.generate)
        s.generate(backup = args.backup)
    if args.reset:
        s.resetAll()
        s.generate(backup = args.backup)

if __name__ == '__main__':
    main()



