#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-
import os
from setuptools import setup
from jpydict import __version__

setup(
    name='jpydict',
    version=__version__,
    description='Japanese-English dictionary, interface for JMdict',
    url='https://github.com/benoitryder/jpydict',
    author='Benoît Ryder',
    author_email='benoit@ryder.fr',
    license='MIT',
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Operating System :: OS Independent',
        'Environment :: X11 Applications :: GTK',
    ],
    py_modules=['jpydict'],
    install_requires=['appdirs'],
    entry_points={
        'gui_scripts': [
            'jpydict = jpydict:main',
        ]
    }
)

