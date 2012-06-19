#

"""LXC slivers"""

import subprocess
import sys
import os, os.path
import grp
import libvirt
from string import Template

import logger
import bwlimit
from sliver_libvirt import Sliver_Libvirt

class Sliver_LXC(Sliver_Libvirt):
    """This class wraps LXC commands"""

    SHELL = '/bin/sshsh'
    TYPE = 'sliver.LXC'
    # Need to add a tag at myplc to actually use this account
    # type = 'sliver.LXC'

    REF_IMG_BASE_DIR = '/vservers/.lvref'
    CON_BASE_DIR     = '/vservers'

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
        logger.log_call(command, timeout=15*60)

        command = ['chown', '-R', '%s.slices'%name, '/home/%s/.ssh'%name]
        logger.log_call(command, timeout=15*60)

        command = ['mkdir', '%s/root/.ssh'%containerDir]
        logger.log_call(command, timeout=15*60)

        command = ['cp', '/home/%s/.ssh/id_rsa.pub'%name, '%s/root/.ssh/authorized_keys'%containerDir]
        logger.log_call(command, timeout=15*60)

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
        logger.log_call(command, timeout=15*60)

        logger.verbose('sliver_libvirt: %s destroyed.'%name)

