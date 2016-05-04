"""
:since:     Wed Dec 02 11:17:09 CET 2015
:author:    Tim Fuehner <tim.fuehner@iisb.fraunhofer.de>
$Id$
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
        version = "0.5",
        packages = find_packages(),
        author = "foxBMS",
        author_email = "info@foxbms.org",
        package_data={'foxbms': ['xrc/*',]},
        zip_safe = False,
        entry_points=_entry_points
        )


