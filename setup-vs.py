#!/usr/bin/python
#
# Setup script for the Node Manager application
#
# Mark Huang <mlhuang@cs.princeton.edu>
# Copyright (C) 2006 The Trustees of Princeton University
#

from distutils.core import setup, Extension

# vserver-specific stuff
setup(
    py_modules=[
        'sliver_vs',
        'coresched_vs',
        # this plugin uses vserver for now
        'plugins.drl',
        ],
    scripts = [
        ],
    packages =[
        ],
    )
