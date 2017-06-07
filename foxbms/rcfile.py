"""
foxBMS Software License

Copyright 2010-2016, Fraunhofer-Gesellschaft zur Foerderung 
                     der angewandten Forschung e.V.
All rights reserved.

BSD 3-Clause License

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

  1.  Redistributions of source code must retain the above copyright notice,
      this list of conditions and the following disclaimer.
  2.  Redistributions in binary form must reproduce the above copyright
      notice, this list of conditions and the following disclaimer in the
      documentation and/or other materials provided with the distribution.
  3.  Neither the name of the copyright holder nor the names of its
      contributors may be used to endorse or promote products derived from
      this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
POSSIBILITY OF SUCH DAMAGE.

We kindly request you to use one or more of the following phrases to refer
to foxBMS in your hardware, software, documentation or advertising
materials:

"This product uses parts of foxBMS"
"This product includes parts of foxBMS"
"This product is derived from foxBMS"

If you use foxBMS in your products, we encourage you to contact us at:

CONTACT INFORMATION
Fraunhofer IISB ; Schottkystrasse 10 ; 91058 Erlangen, Germany
Dr.-Ing. Vincent LORENTZ
+49 9131-761-346
info@foxbms.org

:since:     Tue Mar 29 11:57:50 CEST 2016
:author:    Tim Fuehner <tim.fuehner@iisb.fraunhofer.de>
"""

import yaml
import appdirs
import foxbms
import os

class FoxBMSConfig(object):

    fname = 'foxbms.rc'

    defaults = {
            'workspace': os.path.expanduser(os.path.join('~', 'foxbms')),
            'projects': [],
            'gitrepo': 'https://github.com/foxBMS/foxBMS-setup',
            'sphinxdir': 'build/sphinx/foxBMS-documentation/sphinx/html/index.html',
            'doxygendir': 'build/%(board)s/doxygen/html/index.html'
            }

    def __init__(self, fpath = None):
        self.entries = {}
        self.fpath = fpath
        if self.fpath is None:
            self.fdir = appdirs.user_data_dir(foxbms.__appname__, foxbms.__author__)
            self.fpath = os.path.join(self.fdir, self.fname)
        else:
            self.fdir = os.path.dirname(self.fpath)
        if self.configExists():
            self.read()
            self.cleanProjects()
        else:
            self.create()

    def getProjectNameAndPath(self, name, path = None):
        if path is None:
            _name = name.lower().replace(' ', '_')
            path = os.path.join(self.get('workspace'), _name)
        return name, path

    def addProject(self, name, path = None, repo = None):
        name, path = self.getProjectNameAndPath(name, path)
        projects = self.entries.get('projects', [])
        projects += [{'name': name, 'path': path}]
        if not repo is None:
            projects[-1]['repo'] = repo
        self.set('projects', projects)

    def isGIT(self, name):
        projects = self.entries.get('projects', [])
        for i,p in enumerate(projects):
            if p['name'] == name:
                return 'repo' in projects[i]
        return False

    def getProject(self, name):
        projects = self.entries.get('projects', [])
        for i,p in enumerate(projects):
            if p['name'] == name:
                return projects[i]

    def removeProject(self, name):
        projects = self.entries.get('projects', [])
        for i,p in enumerate(projects):
            if p['name'] == name:
                del projects[i]
        self.set('projects', projects)

    def cleanProjects(self):
        projects = self.entries.get('projects', [])
        _projects = []
        for p in projects:
            if os.path.exists(p['path']):
                _projects += [p]
        self.set('projects', _projects)


    def read(self):
        with open(self.fpath) as f:
            self.entries = yaml.load(f.read())

    def write(self):
        with open(self.fpath, 'w') as f:
            f.write(yaml.dump(self.entries, default_flow_style=False))

    def create(self):
        if not os.path.exists(self.fdir):
            os.makedirs(self.fdir)
        self.set('workspace', self.defaults['workspace'])
        self.set('gitrepo', self.defaults['gitrepo'])

    def configExists(self):
        return os.path.isfile(self.fpath)

    def set(self, key, value):
        self.entries[key] = value
        self.write()

    def get(self, key):
        _default = self.defaults.get(key, None)
        return self.entries.get(key, _default)

    def dump(self):
        return self.entries


if __name__ == '__main__':
    fc = FoxBMSConfig()
    print fc.dump()


