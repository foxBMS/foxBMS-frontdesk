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
www.foxbms.org

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
