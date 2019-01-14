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

# with fedora24 and (broken) libvirt-python-1.3.3-3,
# the following symbols are not available
# kashyap on IRC reported that libvirt-python-1.3.5-1.fc24.x86_64
# did not have the issue though
try:
    REASONS = {
        # 0
        libvirt.VIR_CONNECT_CLOSE_REASON_ERROR: 'Misc I/O error',
        # 1
        libvirt.VIR_CONNECT_CLOSE_REASON_EOF: 'End-of-file from server',
        # 2
        libvirt.VIR_CONNECT_CLOSE_REASON_KEEPALIVE: 'Keepalive timer triggered',
        # 3
        libvirt.VIR_CONNECT_CLOSE_REASON_CLIENT: 'Client requested it',
    }
except:
    REASONS = {
        # libvirt.VIR_CONNECT_CLOSE_REASON_ERROR
        0 : 'Misc I/O error',
        # libvirt.VIR_CONNECT_CLOSE_REASON_EOF
        1 : 'End-of-file from server',
        # libvirt.VIR_CONNECT_CLOSE_REASON_KEEPALIVE
        2 : 'Keepalive timer triggered',
        # libvirt.VIR_CONNECT_CLOSE_REASON_CLIENT
        3 : 'Client requested it',
    }
    logger.log("WARNING : using hard-wired constants instead of symbolic names for CONNECT_CLOSE*")

connections = dict()

# Common Libvirt code

class Sliver_Libvirt(Account):

    # Helper methods

    @staticmethod
    def getConnection(sliver_type):
        """
        returns a connection to the underlying libvirt service
        a single connection is created and shared among slivers
        this call ensures the connection is alive
        and will reconnect if it appears to be necessary
        """
        # sliver_type comes from rec['type'] and is of the form sliver.{LXC,QEMU}
        # so we need to lower case to lxc/qemu
        vtype = sliver_type.split('.')[1].lower()
        uri = vtype + ':///'
        if uri not in connections:
            # create connection
            conn = libvirt.open(uri)
            connections[uri] = conn
            return conn
        else:
            # connection already available : check for health
            conn = connections[uri]
            # see if a reconnection is needed
            try:
                numDomains = conn.numOfDomains()
            except:
                logger.log("libvirt connection to {} looks broken - reconnecting".format(uri))
                conn = libvirt.open(uri)
                # if this fails then an expection is thrown outside of this function
                numDomains = conn.numOfDomains()
            return conn

    def __init__(self, rec):
        self.name = rec['name']
        logger.verbose ('sliver_libvirt: {} init'.format(self.name))

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
            logger.log('sliver_libvirt: Domain {} does not exist. ' \
                       'Will try to create it again.'.format(self.name))
            self.__class__.create(rec['name'], rec)
            dom = self.conn.lookupByName(self.name)
        self.dom = dom

    @staticmethod
    def dom_details (dom):
        output = ""
        output += " id={} - OSType={}".format(dom.ID(), dom.OSType())
        # calling state() seems to be working fine
        (state, reason) = dom.state()
        output += " state={}, reason={}".format(STATES.get(state, state),
                                                REASONS.get(reason, reason))
        try:
            # try to use info() - this however does not work for some reason on f20
            # info cannot get info operation failed: Cannot read cputime for domain
            [state, maxmem, mem, ncpu, cputime] = dom.info()
            output += " [info: state={}, maxmem = {}, mem = {}, ncpu = {}, cputime = {}]"\
                      .format(STATES.get(state, state), maxmem, mem, ncpu, cputime)
        except:
            # too bad but libvirt.py prints out stuff on stdout when this fails, don't know how to get rid of that..
            output += " [info: not available]"
        return output

    def __repr__(self):
        ''' Helper method to get a "nice" output of the domain struct for debug purposes'''
        output = "Domain {}".format(self.name)
        dom = self.dom
        if dom is None: 
            output += " [no attached dom ?!?]"
        else:
            output += Sliver_Libvirt.dom_details (dom)
        return output

    # Thierry : I am not quite sure if /etc/libvirt/lxc/<>.xml holds a reliably up-to-date
    # copy of the sliver XML config; I feel like issuing a virsh dumpxml first might be safer
    def repair_veth(self):
        # See workaround email, 2-14-2014, "libvirt 1.2.1 rollout"
        xmlfilename = "/etc/libvirt/lxc/{}.xml".format(self.name)
        with open(xmlfilename) as xmlfile:
            xml = xmlfile.read()
        veths = re.findall("<target dev='veth[0-9]*'/>", xml)
        veths = [x[13:-3] for x in veths]
        for veth in veths:
            command = ["ip", "link", "delete", veth]
            logger.log_call(command)

        logger.log("trying to redefine the VM")
        command = [ "virsh", "define", xmlfilename ]
        logger.log_call(command)

    def start(self, delay=0):
        '''Just start the sliver'''
        logger.verbose('sliver_libvirt: {} start'.format(self.name))

        # TD: Added OpenFlow rules to avoid OpenVSwitch-based slivers'
        # auto-configuration issues when IPv6 auto-config and/or DHCP are
        # available in the node's network. Sliver configuration is static.
        if os.path.exists('/usr/bin/ovs-ofctl'):
            logger.log('Adding OpenFlow rules to prevent IPv6 auto-config and DHCP in OpenVSwitch slivers')
            # IPv6 ICMP Router Solicitation and Advertisement
            logger.log_call([ '/usr/bin/ovs-ofctl', 'add-flow', 'public0', 'priority=100,icmp6,icmp_type=133,idle_timeout=0,hard_timeout=0,actions=drop' ])
            logger.log_call([ '/usr/bin/ovs-ofctl', 'add-flow', 'public0', 'priority=100,icmp6,icmp_type=134,idle_timeout=0,hard_timeout=0,actions=drop' ])
            # IPv4 DHCP
            logger.log_call([ '/usr/bin/ovs-ofctl', 'add-flow', 'public0', 'priority=101,udp,nw_src=0.0.0.0,nw_dst=255.255.255.255,tp_src=68,tp_dst=67,idle_timeout=0,hard_timeout=0,actions=drop' ])
            logger.log_call([ '/usr/bin/ovs-ofctl', 'add-flow', 'public0', 'priority=101,udp,tp_src=67,tp_dst=68,idle_timeout=0,hard_timeout=0,actions=drop' ])
        else:
            logger.log('NOTE: /usr/bin/ovs-ofctl not found!')

        # Check if it's running to avoid throwing an exception if the
        # domain was already running
        if not self.is_running():
            try:
                # create actually means start
                self.dom.create()
            except Exception as e:
                # XXX smbaker: attempt to resolve slivers that are stuck in
                #   "failed to allocate free veth".
                if "ailed to allocate free veth" in str(e):
                     logger.log("failed to allocate free veth on {}".format(self.name))
                     self.repair_veth()
                     logger.log("trying dom.create again")
                     self.dom.create()
                else:
                    raise
        else:
            logger.verbose('sliver_libvirt: sliver {} already started'.format(self.name))

        # After the VM is started... we can play with the virtual interface
        # Create the ebtables rule to mark the packets going out from the virtual
        # interface to the actual device so the filter canmatch against the mark
        bwlimit.ebtables("-A INPUT -i veth{} -j mark --set-mark {}"
                         .format(self.xid, self.xid))

        # TD: Turn off SCTP checksum offloading. It is currently not working. FIXME: check for a kernel fix!
        result = logger.log_call(['/usr/sbin/lxcsu', '-r', self.name, '--', '/usr/sbin/ethtool', '-K', 'eth0', 'tx-checksum-sctp', 'off'])
        if not result:
            logger.log('unable to apply SCTP checksum bug work-around for %s' % self.name)

        # TD: Work-around for missing interface configuration: ensure that networking service is running.
        result = logger.log_call(['/usr/sbin/lxcsu', '-r', self.name, '/sbin/service', 'network', 'restart'])
        if not result:
            logger.log('unable to restart networking service for %s' % self.name)

    ### this is confusing, because it seems it is not used in fact
    def stop(self):
        logger.verbose('sliver_libvirt: {} stop'.format(self.name))

        # Remove the ebtables rule before stopping 
        bwlimit.ebtables("-D INPUT -i veth{} -j mark --set-mark {}"
                         .format(self.xid, self.xid))

        logger.log('CHECK: STOPPING %s ' % (self.name))
        try:
            self.dom.destroy()
        except:
            logger.log_exc("in sliver_libvirt.stop", name=self.name)

    def is_running(self):
        ''' Return True if the domain is running '''
        (state, _) = self.dom.state()
        result = (state == libvirt.VIR_DOMAIN_RUNNING)
        logger.verbose('sliver_libvirt.is_running: {} => {}'
                       .format(self, result))
        return result

    def configure(self, rec):

        #sliver.[LXC/QEMU] tolower case
        #sliver_type = rec['type'].split('.')[1].lower() 

        #BASE_DIR = '/cgroup/libvirt/{}/{}/'.format(sliver_type, self.name)

        # Disk allocation
        # No way through cgroups... figure out how to do that with user/dir quotas.
        # There is no way to do quota per directory. Chown-ing would create
        # problems as username namespaces are not yet implemented (and thus, host
        # and containers share the same name ids

        # Btrfs support quota per volumes

        if "rspec" in rec and "tags" in rec["rspec"]:
            if cgroups.get_cgroup_path(self.name) == None:
                # If configure is called before start, then the cgroups won't exist
                # yet. NM will eventually re-run configure on the next iteration.
                # TODO: Add a post-start configure, and move this stuff there
                logger.log("Configure: postponing tag check on {} as cgroups are not yet populated"
                           .format(self.name))
            else:
                tags = rec["rspec"]["tags"]
                # It will depend on the FS selection
                if 'disk_max' in tags:
                    disk_max = tags['disk_max']
                    if disk_max == 0:
                        # unlimited
                        pass
                    else:
                        # limit to certain number
                        pass

                # Memory allocation
                if 'memlock_hard' in tags:
                    mem = str(int(tags['memlock_hard']) * 1024) # hard limit in bytes
                    cgroups.write(self.name, 'memory.limit_in_bytes', mem, subsystem="memory")
                if 'memlock_soft' in tags:
                    mem = str(int(tags['memlock_soft']) * 1024) # soft limit in bytes
                    cgroups.write(self.name, 'memory.soft_limit_in_bytes', mem, subsystem="memory")

                # CPU allocation
                # Only cpu_shares until figure out how to provide limits and guarantees
                # (RT_SCHED?)
                if 'cpu_share' in tags:
                    cpu_share = tags['cpu_share']
                    cgroups.write(self.name, 'cpu.shares', cpu_share)

        # Call the upper configure method (ssh keys...)
        Account.configure(self, rec)

    @staticmethod
    def get_unique_vif():
        return 'veth{}'.format(random.getrandbits(32))

    # A placeholder until we get true VirtualInterface objects
    @staticmethod
    def get_interfaces_xml(rec):
        xml = """
    <interface type='network'>
      <source network='default'/>
      <target dev='{}'/>
    </interface>
""".format(Sliver_Libvirt.get_unique_vif())
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
                        vlanxml = "<vlan><tag id='{}'/></vlan>".format(interface['vlan'])
                    else:
                        vlanxml = ""
                    if 'bridge' in interface:
                        tag_xml = tag_xml + """
        <interface type='bridge'>
          <source bridge='{}'/>
          {}
          <virtualport type='openvswitch'/>
          <target dev='{}'/>
        </interface>
    """.format(interface['bridge'], vlanxml, Sliver_Libvirt.get_unique_vif())
                    else:
                        tag_xml = tag_xml + """
        <interface type='network'>
          <source network='default'/>
          <target dev='{}'/>
        </interface>
    """.format(Sliver_Libvirt.get_unique_vif())

                xml = tag_xml
                logger.log('sliver_libvirty.py: interface XML is: {}'.format(xml))

        except:
            logger.log('sliver_libvirt.py: ERROR parsing "interface" tag for slice {}'.format(rec['name']))
            logger.log('sliver_libvirt.py: tag value: {}'.format(tags['interface']))

        return xml
