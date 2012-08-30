#!/usr/bin/python
#
# Setup script for the Node Manager application
#
# Mark Huang <mlhuang@cs.princeton.edu>
# Copyright (C) 2006 The Trustees of Princeton University
#

from distutils.core import setup, Extension

setup(
    py_modules=[
        'sliver_vs',
        'coresched_vs',
        ],
    scripts = [
        ],
    packages =[
        ],
    )