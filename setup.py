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
        'bwlimit',
        'cgroups',
        'conf_files',
        'config',
        'controller',
        'coresched',
        'curlwrapper',
        'database',
        'iptables',
        'logger',
        'net',
        'nodemanager',
        'plcapi',
        'safexmlrpc',
        'sliver_libvirt',
        'sliver_lxc',
        'sliver_vs',
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
