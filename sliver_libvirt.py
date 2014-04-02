"""LibVirt slivers"""

import sys
import os, os.path
import re
import subprocess
import pprint
import random

import libvirt

from account import Account
import logger
import plnode.bwlimit as bwlimit
import cgroups

STATES = {
    libvirt.VIR_DOMAIN_NOSTATE:  'no state',
    libvirt.VIR_DOMAIN_RUNNING:  'running',
    libvirt.VIR_DOMAIN_BLOCKED:  'blocked on resource',
    libvirt.VIR_DOMAIN_PAUSED:   'paused by user',
    libvirt.VIR_DOMAIN_SHUTDOWN: 'being shut down',
    libvirt.VIR_DOMAIN_SHUTOFF:  'shut off',
    libvirt.VIR_DOMAIN_CRASHED:  'crashed',
}

REASONS = {
    libvirt.VIR_CONNECT_CLOSE_REASON_ERROR: 'Misc I/O error',
    libvirt.VIR_CONNECT_CLOSE_REASON_EOF: 'End-of-file from server',
    libvirt.VIR_CONNECT_CLOSE_REASON_KEEPALIVE: 'Keepalive timer triggered',
    libvirt.VIR_CONNECT_CLOSE_REASON_CLIENT: 'Client requested it',
}

connections = dict()

# Common Libvirt code

class Sliver_Libvirt(Account):

    # Helper methods

    @staticmethod
    def getConnection(sliver_type):
        # TODO: error checking
        # vtype is of the form sliver.[LXC/QEMU] we need to lower case to lxc/qemu
        vtype = sliver_type.split('.')[1].lower()
        uri = vtype + '://'
        return connections.setdefault(uri, libvirt.open(uri))

    def __init__(self, rec):
        self.name = rec['name']
        logger.verbose ('sliver_libvirt: %s init'%(self.name))

        # Assume the directory with the image and config files
        # are in place

        self.keys = ''
        self.rspec = {}
        self.slice_id = rec['slice_id']
        self.enabled = True
        self.conn = Sliver_Libvirt.getConnection(rec['type'])
        self.xid = bwlimit.get_xid(self.name)

        dom = None
        try:
            dom = self.conn.lookupByName(self.name)
        except:
            logger.log('sliver_libvirt: Domain %s does not exist. ' \
                       'Will try to create it again.' % (self.name))
            self.__class__.create(rec['name'], rec)
            dom = self.conn.lookupByName(self.name)
        self.dom = dom

    @staticmethod
    def dom_details (dom):
        output=""
        output += " id=%s - OSType=%s"%(dom.ID(),dom.OSType())
        # calling state() seems to be working fine
        (state,reason)=dom.state()
        output += " state=%s, reason=%s"%(STATES.get(state,state),REASONS.get(reason,reason))
        try:
            # try to use info() - this however does not work for some reason on f20
            # info cannot get info operation failed: Cannot read cputime for domain
            [state, maxmem, mem, ncpu, cputime] = dom.info()
            output += " [info: maxmem = %s, mem = %s, ncpu = %s, cputime = %s]" % (STATES.get(state, state), maxmem, mem, ncpu, cputime)
        except:
            # too bad but libvirt.py prints out stuff on stdout when this fails, don't know how to get rid of that..
            output += " [info: not available]"
        return output

    def __repr__(self):
        ''' Helper method to get a "nice" output of the domain struct for debug purposes'''
        output="Domain %s"%self.name
        dom=self.dom
        if dom is None: 
            output += " [no attached dom ?!?]"
        else:
            output += Sliver_Libvirt.dom_details (dom)
        return output

    def repair_veth(self):
        # See workaround email, 2-14-2014, "libvirt 1.2.1 rollout"
        xml = open("/etc/libvirt/lxc/%s.xml" % self.name).read()
        veths = re.findall("<target dev='veth[0-9]*'/>", xml)
        veths = [x[13:-3] for x in veths]
        for veth in veths:
            command = ["ip", "link", "delete", veth]
            logger.log_call(command)

        logger.log("trying to redefine the VM")
        command = ["virsh", "define", "/etc/libvirt/lxc/%s.xml" % self.name]
        logger.log_call(command)

    def start(self, delay=0):
        ''' Just start the sliver '''
        logger.verbose('sliver_libvirt: %s start'%(self.name))

        # Check if it's running to avoid throwing an exception if the
        # domain was already running, create actually means start
        if not self.is_running():
            try:
                self.dom.create()
            except Exception, e:
                # XXX smbaker: attempt to resolve slivers that are stuck in
                #   "failed to allocate free veth".
                if "ailed to allocate free veth" in str(e):
                     logger.log("failed to allocate free veth on %s" % self.name)
                     self.repair_veth()
                     logger.log("trying dom.create again")
                     self.dom.create()
                else:
                    raise
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
            logger.log_exc("in sliver_libvirt.stop",name=self.name)

    def is_running(self):
        ''' Return True if the domain is running '''
        (state,_) = self.dom.state()
        result = (state == libvirt.VIR_DOMAIN_RUNNING)
        logger.verbose('sliver_libvirt.is_running: %s => %s'%(self,result))
        return result

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

        if rec.has_key("rspec") and rec["rspec"].has_key("tags"):
            if cgroups.get_cgroup_path(self.name) == None:
                # If configure is called before start, then the cgroups won't exist
                # yet. NM will eventually re-run configure on the next iteration.
                # TODO: Add a post-start configure, and move this stuff there
                logger.log("Configure: postponing tag check on %s as cgroups are not yet populated" % self.name)
            else:
                tags = rec["rspec"]["tags"]
                # It will depend on the FS selection
                if tags.has_key('disk_max'):
                    disk_max = tags['disk_max']
                    if disk_max == 0:
                        # unlimited
                        pass
                    else:
                        # limit to certain number
                        pass

                # Memory allocation
                if tags.has_key('memlock_hard'):
                    mem = str(int(tags['memlock_hard']) * 1024) # hard limit in bytes
                    cgroups.write(self.name, 'memory.limit_in_bytes', mem, subsystem="memory")
                if tags.has_key('memlock_soft'):
                    mem = str(int(tags['memlock_soft']) * 1024) # soft limit in bytes
                    cgroups.write(self.name, 'memory.soft_limit_in_bytes', mem, subsystem="memory")

                # CPU allocation
                # Only cpu_shares until figure out how to provide limits and guarantees
                # (RT_SCHED?)
                if tags.has_key('cpu_share'):
                    cpu_share = tags['cpu_share']
                    cgroups.write(self.name, 'cpu.shares', cpu_share)

        # Call the upper configure method (ssh keys...)
        Account.configure(self, rec)

    @staticmethod
    def get_unique_vif():
        return 'veth%s' % random.getrandbits(32)

    # A placeholder until we get true VirtualInterface objects
    @staticmethod
    def get_interfaces_xml(rec):
        xml = """
    <interface type='network'>
      <source network='default'/>
      <target dev='%s'/>
    </interface>
""" % (Sliver_Libvirt.get_unique_vif())
        try:
            tags = rec['rspec']['tags']
            if 'interface' in tags:
                interfaces = eval(tags['interface'])
                if not isinstance(interfaces, (list, tuple)):
                    # if interface is not a list, then make it into a singleton list
                    interfaces = [interfaces]
                tag_xml = ""
                for interface in interfaces:
                    if 'vlan' in interface:
                        vlanxml = "<vlan><tag id='%s'/></vlan>" % interface['vlan']
                    else:
                        vlanxml = ""
                    if 'bridge' in interface:
                        tag_xml = tag_xml + """
        <interface type='bridge'>
          <source bridge='%s'/>
          %s
          <virtualport type='openvswitch'/>
          <target dev='%s'/>
        </interface>
    """ % (interface['bridge'], vlanxml, Sliver_Libvirt.get_unique_vif())
                    else:
                        tag_xml = tag_xml + """
        <interface type='network'>
          <source network='default'/>
          <target dev='%s'/>
        </interface>
    """ % (Sliver_Libvirt.get_unique_vif())

                xml = tag_xml
                logger.log('sliver_libvirty.py: interface XML is: %s' % xml)

        except:
            logger.log('sliver_libvirt.py: ERROR parsing "interface" tag for slice %s' % rec['name'])
            logger.log('sliver_libvirt.py: tag value: %s' % tags['interface'])

        return xml
