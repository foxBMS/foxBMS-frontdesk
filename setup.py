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

:since:     Wed Dec 02 11:17:09 CET 2015
:author:    Tim Fuehner <tim.fuehner@iisb.fraunhofer.de>
"""

import setuptools
from setuptools import setup, find_packages
import sys

if sys.platform.startswith('win'):
    _entry_points = {
            'gui_scripts': ['foxbms = foxbms.foxfdd:main']
            }
else:
    _entry_points = {}

setup(
        name = "foxbms",
        version = "0.7",
        packages = find_packages(),
        author = "foxBMS",
        author_email = "info@foxbms.org",
        package_data={'foxbms': ['xrc/*',]},
        zip_safe = False,
        entry_points=_entry_points
        )


