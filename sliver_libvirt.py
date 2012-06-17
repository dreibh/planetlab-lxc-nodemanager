"""LibVirt slivers"""

import account
import logger
import subprocess
import os
import os.path
import libvirt
import sys
import shutil
import bwlimit
import cgroups
import pprint

from string import Template

STATES = {
    libvirt.VIR_DOMAIN_NOSTATE:  'no state',
    libvirt.VIR_DOMAIN_RUNNING:  'running',
    libvirt.VIR_DOMAIN_BLOCKED:  'blocked on resource',
    libvirt.VIR_DOMAIN_PAUSED:   'paused by user',
    libvirt.VIR_DOMAIN_SHUTDOWN: 'being shut down',
    libvirt.VIR_DOMAIN_SHUTOFF:  'shut off',
    libvirt.VIR_DOMAIN_CRASHED:  'crashed',
}

connections = dict()

# Helper methods

def getConnection(sliver_type):
    # TODO: error checking
    # vtype is of the form sliver.[LXC/QEMU] we need to lower case to lxc/qemu
    vtype = sliver_type.split('.')[1].lower()
    uri = vtype + '://'
    return connections.setdefault(uri, libvirt.open(uri))

def debuginfo(dom):
    ''' Helper method to get a "nice" output of the info struct for debug'''
    [state, maxmem, mem, ncpu, cputime] = dom.info()
    return '%s is %s, maxmem = %s, mem = %s, ncpu = %s, cputime = %s' % (dom.name(), STATES.get(state, state), maxmem, mem, ncpu, cputime)

# Common Libvirt code

class Sliver_Libvirt(account.Account):

    def __init__(self, rec):
        self.name = rec['name']
        logger.verbose ('sliver_libvirt: %s init'%(self.name))

        # Assume the directory with the image and config files
        # are in place

        self.keys = ''
        self.rspec = {}
        self.slice_id = rec['slice_id']
        self.enabled = True
        self.conn = getConnection(rec['type'])
        self.xid = bwlimit.get_xid(self.name)

        try:
            self.dom = self.conn.lookupByName(self.name)
        except:
            logger.log('sliver_libvirt: Domain %s does not exist ' \
                       'UNEXPECTED: %s'%(self.name, sys.exc_info()[1]))

    def start(self, delay=0):
        ''' Just start the sliver '''
        logger.verbose('sliver_libvirt: %s start'%(self.name))

        # Check if it's running to avoid throwing an exception if the
        # domain was already running, create actually means start
        if not self.is_running():
            self.dom.create()
        else:
            logger.verbose('sliver_libvirt: sliver %s already started'%(self.name))

        # After the VM is started... we can play with the virtual interface
        # Create the ebtables rule to mark the packets going out from the virtual
        # interface to the actual device so the filter canmatch against the mark
        bwlimit.ebtables("-A INPUT -i veth%d -j mark --set-mark %d" % \
            (self.xid, self.xid))

    def stop(self):
        logger.verbose('sliver_libvirt: %s stop'%(self.name))

        # Remove the ebtables rule before stopping 
        bwlimit.ebtables("-D INPUT -i veth%d -j mark --set-mark %d" % \
            (self.xid, self.xid))

        try:
            self.dom.destroy()
        except:
            logger.verbose('sliver_libvirt: Domain %s not running ' \
                           'UNEXPECTED: %s'%(self.name, sys.exc_info()[1]))
            print 'sliver_libvirt: Domain %s not running ' \
                  'UNEXPECTED: %s'%(self.name, sys.exc_info()[1])

    def is_running(self):
        ''' Return True if the domain is running '''
        logger.verbose('sliver_libvirt: %s is_running'%self.name)
        try:
            [state, _, _, _, _] = self.dom.info()
            if state == libvirt.VIR_DOMAIN_RUNNING:
                logger.verbose('sliver_libvirt: %s is RUNNING'%self.name)
                return True
            else:
                info = debuginfo(self.dom)
                logger.verbose('sliver_libvirt: %s is ' \
                               'NOT RUNNING...\n%s'%(self.name, info))
                return False
        except:
            logger.verbose('sliver_libvirt: UNEXPECTED ERROR in ' \
                           '%s: %s'%(self.name, sys.exc_info()[1]))
            print 'sliver_libvirt: UNEXPECTED ERROR in ' \
                  '%s: %s'%(self.name, sys.exc_info()[1])
            return False

    def configure(self, rec):

        #sliver.[LXC/QEMU] tolower case
        #sliver_type = rec['type'].split('.')[1].lower() 

        #BASE_DIR = '/cgroup/libvirt/%s/%s/'%(sliver_type, self.name)

        # Disk allocation
        # No way through cgroups... figure out how to do that with user/dir quotas.
        # There is no way to do quota per directory. Chown-ing would create
        # problems as username namespaces are not yet implemented (and thus, host
        # and containers share the same name ids

        # Btrfs support quota per volumes

        # It will depend on the FS selection
        if rec.has_key('disk_max'):
            disk_max = rec['disk_max']
            if disk_max == 0:
                # unlimited 
                pass
            else:
                # limit to certain number
                pass

        # Memory allocation
        if rec.has_key('memlock_hard'):
            mem = rec['memlock_hard'] * 1024 # hard limit in bytes
            cgroups.write(self.name, 'memory.limit_in_bytes', mem)
        if rec.has_key('memlock_soft'):
            mem = rec['memlock_soft'] * 1024 # soft limit in bytes
            cgroups.write(self.name, 'memory.soft_limit_in_bytes', mem)

        # CPU allocation
        # Only cpu_shares until figure out how to provide limits and guarantees
        # (RT_SCHED?)
        if rec.has_key('cpu_share'):
            cpu_share = rec['cpu_share']
            cgroups.write(self.name, 'cpu.shares', cpu_share)

        # Call the upper configure method (ssh keys...)
        account.Account.configure(self, rec)

