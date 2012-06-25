#

"""LXC slivers"""

import subprocess
import sys
import os, os.path
import grp
from string import Template

import libvirt

import logger
import bwlimitlxc as bwlimit
from initscript import Initscript
from sliver_libvirt import Sliver_Libvirt

class Sliver_LXC(Sliver_Libvirt, Initscript):
    """This class wraps LXC commands"""

    SHELL = '/bin/sshsh'
    TYPE = 'sliver.LXC'
    # Need to add a tag at myplc to actually use this account
    # type = 'sliver.LXC'

    REF_IMG_BASE_DIR = '/vservers/.lvref'
    CON_BASE_DIR     = '/vservers'

    def __init__ (self, rec):
        name=rec['name']
        Sliver_Libvirt.__init__ (self,rec)
        Initscript.__init__ (self,name)

    def configure (self, rec):
        Sliver_Libvirt.configure (self,rec)

        # in case we update nodemanager..
        self.install_and_enable_vinit()
        # do the configure part from Initscript
        Initscript.configure(self,rec)

    def start(self, delay=0):
        if 'enabled' in self.rspec and self.rspec['enabled'] <= 0:
            logger.log('sliver_lxc: not starting %s, is not enabled'%self.name)
            return
        # the generic /etc/init.d/vinit script is permanently refreshed, and enabled
        self.install_and_enable_vinit()
        Sliver_Libvirt.start (self, delay)
        # if a change has occured in the slice initscript, reflect this in /etc/init.d/vinit.slice
        self.refresh_slice_vinit()

    def rerun_slice_vinit (self):
        """This is called whenever the initscript code changes"""
        # xxx - todo - not sure exactly how to:
        # (.) invoke something in the guest
        # (.) which options of systemctl should be used to trigger a restart
        # should not prevent the first run from going fine hopefully
        logger.log("WARNING: sliver_lxc.rerun_slice_vinit not implemented yet")

    @staticmethod
    def create(name, rec=None):
        ''' Create dirs, copy fs image, lxc_create '''
        logger.verbose ('sliver_lxc: %s create'%(name))
        conn = Sliver_Libvirt.getConnection(Sliver_LXC.TYPE)

        # Get the type of image from vref myplc tags specified as:
        # pldistro = lxc
        # fcdistro = squeeze
        # arch x86_64
        vref = rec['vref']
        if vref is None:
            logger.log('sliver_libvirt: %s: WARNING - no vref attached defaults to lxc-f14' % (name))
            vref = "lxc-f14-x86_64"

        refImgDir    = os.path.join(Sliver_LXC.REF_IMG_BASE_DIR, vref)
        containerDir = os.path.join(Sliver_LXC.CON_BASE_DIR, name)

        # check the template exists -- there's probably a better way..
        if not os.path.isdir(refImgDir):
            logger.log('sliver_lxc: %s: ERROR Could not create sliver - reference image %s not found' % (name,vref))
            logger.log('sliver_lxc: %s: ERROR Expected reference image in %s'%(name,refImgDir))
            return

        # Snapshot the reference image fs (assume the reference image is in its own
        # subvolume)
        command = ['btrfs', 'subvolume', 'snapshot', refImgDir, containerDir]
        if not logger.log_call(command, timeout=15*60):
            logger.log('sliver_lxc: ERROR Could not create BTRFS snapshot at', containDir)
            return
        command = ['chmod', '755', containerDir]
        logger.log_call(command, timeout=15*60)

        # customize prompt for slice owner
        dot_profile=os.path.join(containerDir,"root/.profile")
        with open(dot_profile,'w') as f:
            f.write("export PS1='%s@\H \$ '\n"%(name))

        # TODO: set quotas...

        # Set hostname. A valid hostname cannot have '_'
        #with open(os.path.join(containerDir, 'etc/hostname'), 'w') as f:
        #    print >>f, name.replace('_', '-')

        # Add slices group if not already present
        try:
            group = grp.getgrnam('slices')
        except:
            command = ['/usr/sbin/groupadd', 'slices']
            logger.log_call(command, timeout=15*60)

        # Add unix account (TYPE is specified in the subclass)
        command = ['/usr/sbin/useradd', '-g', 'slices', '-s', Sliver_LXC.SHELL, name, '-p', '*']
        logger.log_call(command, timeout=15*60)
        command = ['mkdir', '/home/%s/.ssh'%name]
        logger.log_call(command, timeout=15*60)

        # Create PK pair keys to connect from the host to the guest without
        # password... maybe remove the need for authentication inside the
        # guest?
        command = ['su', '-s', '/bin/bash', '-c', 'ssh-keygen -t rsa -N "" -f /home/%s/.ssh/id_rsa'%(name)]
        logger.log_call(command, timeout=60)

        command = ['chown', '-R', '%s.slices'%name, '/home/%s/.ssh'%name]
        logger.log_call(command, timeout=30)

        command = ['mkdir', '%s/root/.ssh'%containerDir]
        logger.log_call(command, timeout=10)

        command = ['cp', '/home/%s/.ssh/id_rsa.pub'%name, '%s/root/.ssh/authorized_keys'%containerDir]
        logger.log_call(command, timeout=30)

        # Lookup for xid and create template after the user is created so we
        # can get the correct xid based on the name of the slice
        xid = bwlimit.get_xid(name)

        # Template for libvirt sliver configuration
        template_filename_sliceimage = os.path.join(Sliver_LXC.REF_IMG_BASE_DIR,'lxc_template.xml')
        if os.path.isfile (template_filename_sliceimage):
            logger.log("WARNING: using compat template %s"%template_filename_sliceimage)
            template_filename=template_filename_sliceimage
        else:
            logger.log("Cannot find XML template %s"%template_filename_sliceimage)
            return
        try:
            with open(template_filename) as f:
                template = Template(f.read())
                xml  = template.substitute(name=name, xid=xid)
        except IOError:
            logger.log('Failed to parse or use XML template file %s'%template_filename)
            return

        # Lookup for the sliver before actually
        # defining it, just in case it was already defined.
        try:
            dom = conn.lookupByName(name)
        except:
            dom = conn.defineXML(xml)
        logger.verbose('lxc_create: %s -> %s'%(name, Sliver_Libvirt.debuginfo(dom)))


    @staticmethod
    def destroy(name):
        logger.verbose ('sliver_lxc: %s destroy'%(name))
        conn = Sliver_Libvirt.getConnection(Sliver_LXC.TYPE)

        containerDir = Sliver_LXC.CON_BASE_DIR + '/%s'%(name)

        try:
            # Destroy libvirt domain
            dom = conn.lookupByName(name)
        except:
            logger.verbose('sliver_lxc: Domain %s does not exist!' % name)

        try:
            dom.destroy()
        except:
            logger.verbose('sliver_lxc: Domain %s not running... continuing.' % name)

        try:
            dom.undefine()
        except:
            logger.verbose('sliver_lxc: Domain %s is not defined... continuing.' % name)

        # Remove user after destroy domain to force logout
        command = ['/usr/sbin/userdel', '-f', '-r', name]
        logger.log_call(command, timeout=15*60)

        # Remove rootfs of destroyed domain
        command = ['btrfs', 'subvolume', 'delete', containerDir]
        logger.log_call(command, timeout=60)

        logger.verbose('sliver_libvirt: %s destroyed.'%name)

