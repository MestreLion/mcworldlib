#!/usr/bin/env python3

from setuptools import setup, find_packages
from os import path

from importlib import import_module

packages = find_packages()
projname = packages[0]
project = import_module(projname)
projdir = path.abspath(path.dirname(__file__))

with open(path.join(projdir, 'README.md'), encoding='utf-8') as f:
    readme = f.read().strip()

setup(
    name             = project.__project__,
    version          = project.__version__,
    author           = project.__author__,
    author_email     = project.__email__,
    description      = project.__doc__.strip(),
    long_description = readme,
    long_description_content_type = 'text/markdown',
    keywords         = "minecraft save nbt chunk region world library",
    url              = f"https://github.com/MestreLion/{projname}",
    project_urls     = {
        "Bug Tracker": f"https://github.com/MestreLion/{projname}/issues",
        "Source Code": f"https://github.com/MestreLion/{projname}",
    },
    classifiers      = [
        "Development Status :: 1 - Planning",
        "Intended Audience :: Developers",
        "License :: DFSG approved",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Topic :: Games/Entertainment",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    packages         = packages,
    package_data     = {
        '': ['*.md', 'LICENSE*'],
    },
    python_requires  = '>=3.6',
    install_requires = [
        'nbtlib',
        'tqdm',
    ],
)
