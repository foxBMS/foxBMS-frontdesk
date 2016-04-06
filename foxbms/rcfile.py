import yaml
import appdirs
import foxbms
import os

class FoxBMSConfig(object):

    fname = 'foxbms.rc'

    defaults = {
            'workspace': os.path.expanduser(os.path.join('~', 'foxbms'))
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


