"""
:since:     Mon Apr 18 11:45:48 CEST 2016
:author:    Tim Fuehner <tim.fuehner@iisb.fraunhofer.de>
$Id$
"""

import subprocess
import os.path
import os
import sys

def main():
    # add xconda path to 
    _fbenv = os.environ.copy()
    if sys.platform.startswith('win'):
        _path = _fbenv['PATH'].split(os.path.pathsep)
        _path = [sys.prefix, os.path.join(sys.prefix, 'Scripts'),
                os.path.join(sys.prefix, 'bin')] + _path
        _fbenv['PATH'] = os.path.pathsep.join(_path)
        subprocess.call(['start', 'cmd'], shell=True, env = _fbenv)
    elif sys.platform.startswith('darwin'):
        _fbenv['PATH'] = os.path.join(sys.prefix, 'bin') + os.path.pathsep + _fbenv['PATH']
        subprocess.call([
            'open', os.path.join(os.path.dirname(__file__), 'xrc',
                'fbterminal.command')], env = _fbenv)
    else: # linux
        _TERM = _fbenv.get('TERM', 'xterm')
        _fbenv['PATH'] = os.path.join(sys.prefix, 'bin') + os.path.pathsep + _fbenv['PATH']
        subprocess.Popen([_TERM], env = _fbenv)

if __name__ == '__main__':
    pass
