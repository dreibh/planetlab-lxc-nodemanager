#!/usr/bin/python3
#
# Setup script for the Node Manager application
#
# Mark Huang <mlhuang@cs.princeton.edu>
# Copyright (C) 2006 The Trustees of Princeton University
#

from distutils.core import setup

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
        'plugins.codemux',
        'plugins.hostmap',
        'plugins.interfaces',
        'plugins.omf_resctl',
        'plugins.rawdisk',
        'plugins.reservation',
        'plugins.sfagids',
        'plugins.sliverauth',
        'plugins.specialaccounts',
        'plugins.syndicate',
        'plugins.vsys',
        'plugins.vsys_privs',
        'plugins.ipv6',
        'plugins.update_ipv6addr_slivertag',
# lxc
        'sliver_libvirt',
        'sliver_lxc',
        'cgroups',
        'coresched_lxc',
        'plugins.privatebridge',
# vs
        'sliver_vs',
        'coresched_vs',
        # this plugin uses vserver for now
        'plugins.drl',
        ],
    )
