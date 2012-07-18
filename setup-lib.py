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
        'account',
        'api',
        'api_calls',
        'bwmon',
        'conf_files',
        'config',
        'controller',
        'curlwrapper',
        'database',
        'initscript',
        'iptables',
        'logger',
        'net',
        'nodemanager',
        'plcapi',
        'safexmlrpc',
        'slivermanager',
        'ticket',
        'tools',
        ],
    scripts = [
        'forward_api_calls',
        ],
    packages =[
        'plugins',
        ],
    )
