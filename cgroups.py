# Simple wrapper arround cgroups so we don't have to worry the type of
# virtualization the sliver runs on (lxc, qemu/kvm, etc.) managed by libvirt
#
# Xavi Leon <xleon@ac.upc.edu>

import os
import pyinotify
import logger

# Base dir for libvirt
BASE_DIR = '/sys/fs/cgroup'
SUB_SYSTEMS = ['blkio', 'freezer', 'devices', 'memory', 'cpu,cpuacct', 'cpuset']
VIRT_TECHS = ['lxc']

# Global cgroup mapping. 
CGROUPS = dict()

class CgroupWatch(pyinotify.ProcessEvent):

    def process_IN_CREATE(self, event):
	path = os.path.join(event.path, event.name)
	CGROUPS[event.name] = path
	logger.verbose("Cgroup Notify: Created cgroup %s on %s" % \
			(event.name, event.path))
        
    def process_IN_DELETE(self, event):
        try:
	    del CGROUPS[event.name]
        except:
            logger.verbose("Cgroup Notify: Cgroup %s does not exist, continuing..."%event.name)
	logger.verbose("Cgroup Notify: Deleted cgroup %s on %s" % \
			(event.name, event.path))


#logger.verbose("Cgroups: Recognizing already existing cgroups...")
#for virt in VIRT_TECHS:
#    filenames = os.listdir(os.path.join(BASE_DIR, virt))
#    for filename in filenames:
#        path = os.path.join(BASE_DIR, virt, filename)
#        if os.path.isdir(path):
#            CGROUPS[filename] = path

#logger.verbose("Cgroups: Initializing watchers...")
#wm = pyinotify.WatchManager()
#notifier = pyinotify.ThreadedNotifier(wm, CgroupWatch())
#for virt in VIRT_TECHS:
#    wdd = wm.add_watch(os.path.join(BASE_DIR, virt),
#               pyinotify.IN_DELETE | pyinotify.IN_CREATE,
#               rec=False)
#notifier.daemon = True
#notifier.start()

def get_cgroup_paths(subsystem="cpuset"):
    cpusetBases = [ 
        # observed on f16-f18
        os.path.join(BASE_DIR, subsystem, 'libvirt', 'lxc'),
        # as observed on f20
        os.path.join(BASE_DIR, subsystem ),
        # as observed on f16 libvirt 1.2.1
        os.path.join(BASE_DIR, subsystem, 'machine'),
        ]
    # try several locations and return all the results
    # get_cgroup_path will sort it out
    def merge(l1,l2): return l1+l2
    return reduce (lambda l1,l2: l1+l2, 
                   [ [ dir for dir in 
                       [ os.path.join(cpusetBase, f) for f in os.listdir(cpusetBase) ]
                       if os.path.isdir(dir) ]
                     for cpusetBase in cpusetBases if os.path.isdir (cpusetBase) ])

def get_cgroup_path(name, subsystem="cpuset"):
    """ Returns the base path for the cgroup with a specific name or None."""
    result = reduce(lambda a, b: b if os.path.basename(b) == name else a,
                  get_cgroup_paths(subsystem), None)

    if result is None:
        name = name + ".libvirt-lxc"
        result = reduce(lambda a, b: b if os.path.basename(b) == name else a,
                      get_cgroup_paths(subsystem), None)

    return result

def get_base_path():
    return BASE_DIR

def get_cgroups():
    """ Returns the list of cgroups active at this moment on the node """
    return map(os.path.basename, get_cgroup_paths())

def write(name, key, value, subsystem="cpuset"):
    """ Writes a value to the file key with the cgroup with name """
    base_path = get_cgroup_path(name, subsystem)
    with open(os.path.join(base_path, key), 'w') as f:
        print >>f, value

def append(name, key, value, subsystem="cpuset"):
    """ Appends a value to the file key with the cgroup with name """
    base_path = get_cgroup_path(name, subsystem)
    with open(os.path.join(base_path, key), 'a') as f:
        print >>f, value
