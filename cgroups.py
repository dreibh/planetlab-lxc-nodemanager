# Simple wrapper arround cgroups so we don't have to worry the type of
# virtualization the sliver runs on (lxc, qemu/kvm, etc.) managed by libvirt
#
# Xavi Leon <xleon@ac.upc.edu>

import os, os.path
import pyinotify
import logger
from functools import reduce

# Base dir for libvirt
BASE_DIR = '/sys/fs/cgroup'

def get_cgroup_paths(subsystem="cpuset"):
    subsystem_bases = [ 
        # observed on f16-f18
        os.path.join(BASE_DIR, subsystem, 'libvirt', 'lxc'),
        # as observed on f20
        os.path.join(BASE_DIR, subsystem ),
        # f21
        os.path.join(BASE_DIR, subsystem, 'machine.slice'),
        # as observed on f16 libvirt 1.2.1
        os.path.join(BASE_DIR, subsystem, 'machine'),
        ]
    # try several locations and return all the results
    # get_cgroup_path will sort it out
    
    # just return all the subdirs in the listed bases 
    return [ subdir
                 # scan the bases
                 for subsystem_base in subsystem_bases if os.path.isdir(subsystem_base)
                     # in each base search the immediate sons that are also dirs
                     for subdir in [ os.path.join(subsystem_base, f) for f in os.listdir(subsystem_base) ]
                         if os.path.isdir(subdir) ]

def get_cgroup_path(name, subsystem="cpuset"):
    """
    Returns the base path for the cgroup with a specific name or None.
    """
    result = reduce(lambda a, b: b if name in os.path.basename(b) else a,
                    get_cgroup_paths(subsystem), None)

    if result is None:
        name = name + ".libvirt-lxc"
        result = reduce(lambda a, b: b if name in os.path.basename(b) else a,
                        get_cgroup_paths(subsystem), None)

    return result

def get_base_path():
    return BASE_DIR

def get_cgroups():
    """ Returns the list of cgroups active at this moment on the node """
    return list(map(os.path.basename, get_cgroup_paths()))

def write(name, key, value, subsystem="cpuset"):
    """ Writes a value to the file key with the cgroup with name """
    base_path = get_cgroup_path(name, subsystem)
    with open(os.path.join(base_path, key), 'w') as f:
        print(value, file=f)
    logger.verbose("cgroups.write: overwrote {}".format(base_path))

def append(name, key, value, subsystem="cpuset"):
    """ Appends a value to the file key with the cgroup with name """
    base_path = get_cgroup_path(name, subsystem)
    with open(os.path.join(base_path, key), 'a') as f:
        print(value, file=f)
    logger.verbose("cgroups.append: appended {}".format(base_path))

if __name__ == '__main__':

    # goes with the system tests
    name='inri_sl1' 

    subsystems = 'blkio cpu cpu,cpuacct cpuacct cpuset devices freezer memory net_cls perf_event systemd'.split()

    for subsystem in subsystems:
        print('get_cgroup_path({}, {}) =  {}'.\
            format(name, subsystem, get_cgroup_path(name, subsystem)))

#        print 'get_cgroup_paths = {}'.format(get_cgroup_paths(subsystem))
