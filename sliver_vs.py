#

"""VServer slivers.

There are a couple of tricky things going on here.  First, the kernel
needs disk usage information in order to enforce the quota.  However,
determining disk usage redundantly strains the disks.  Thus, the
Sliver_VS.disk_usage_initialized flag is used to determine whether
this initialization has been made.

Second, it's not currently possible to set the scheduler parameters
for a sliver unless that sliver has a running process.  /bin/vsh helps
us out by reading the configuration file so that it can set the
appropriate limits after entering the sliver context.  Making the
syscall that actually sets the parameters gives a harmless error if no
process is running.  Thus we keep vm_running on when setting scheduler
parameters so that set_sched_params() always makes the syscall, and we
don't have to guess if there is a running process or not.
"""

import errno
import traceback
import os, os.path
import sys
import time
from threading import BoundedSemaphore
import subprocess

# the util-vserver-pl module
import vserver

import logger
import tools
from account import Account
from initscript import Initscript

# special constant that tells vserver to keep its existing settings
KEEP_LIMIT = vserver.VC_LIM_KEEP

# populate the sliver/vserver specific default allocations table,
# which is used to look for slice attributes
DEFAULT_ALLOCATION = {}
for rlimit in vserver.RLIMITS.keys():
    rlim = rlimit.lower()
    DEFAULT_ALLOCATION["{}_min".format(rlim)] = KEEP_LIMIT
    DEFAULT_ALLOCATION["{}_soft".format(rlim)] = KEEP_LIMIT
    DEFAULT_ALLOCATION["{}_hard".format(rlim)] = KEEP_LIMIT

class Sliver_VS(vserver.VServer, Account, Initscript):
    """This class wraps vserver.VServer to make its interface closer to what we need."""

    SHELL = '/bin/vsh'
    TYPE = 'sliver.VServer'
    _init_disk_info_sem = BoundedSemaphore()

    def __init__(self, rec):
        name = rec['name']
        logger.verbose ('sliver_vs: {} init'.format(name))
        try:
            logger.log("sliver_vs: {}: first chance...".format(name))
            vserver.VServer.__init__(self, name, logfile='/var/log/nodemanager')
            Account.__init__ (self, name)
            Initscript.__init__ (self, name)
        except Exception, err:
            if not isinstance(err, vserver.NoSuchVServer):
                # Probably a bad vserver or vserver configuration file
                logger.log_exc("sliver_vs:__init__ (first chance)", name=name)
                logger.log('sliver_vs: {}: recreating bad vserver'.format(name))
                self.destroy(name)
            self.create(name, rec)
            vserver.VServer.__init__(self, name, logfile='/var/log/nodemanager')
            Account.__init__ (self, name)
            Initscript.__init__ (self, name)

        self.rspec = {}
        self.slice_id = rec['slice_id']
        self.disk_usage_initialized = False
        self.enabled = True
        # xxx this almost certainly is wrong...
        self.configure(rec)

    @staticmethod
    def create(name, rec = None):
        logger.verbose('sliver_vs: {}: create'.format(name))
        vref = rec['vref']
        if vref is None:
            # added by caglar
            # band-aid for short period as old API doesn't have GetSliceFamily function
            vref = "planetlab-f8-i386"
            logger.log("sliver_vs: {}: ERROR - no vref attached, using hard-wired default {}"
                       .format(name, vref))

        # used to look in /etc/planetlab/family,
        # now relies on the 'GetSliceFamily' extra attribute in GetSlivers()
        # which for legacy is still exposed here as the 'vref' key

        # check the template exists -- there's probably a better way..
        if not os.path.isdir ("/vservers/.vref/{}".format(vref)):
            logger.log ("sliver_vs: {}: ERROR Could not create sliver - vreference image {} not found"
                        .format(name, vref))
            return

        # compute guest personality
        try:
            (x, y, arch) = vref.split('-')
        # mh, this of course applies when 'vref' is e.g. 'netflow'
        # and that's not quite right
        except:
            arch = 'i386'

        def personality (arch):
            return "linux64" if arch.find("64") >= 0 else "linux32"

        command = []
        # be verbose
        command += ['/bin/bash', '-x', ]
        command += ['/usr/sbin/vuseradd', ]
        if 'attributes' in rec and 'isolate_loopback' in rec['attributes'] and rec['attributes']['isolate_loopback'] == '1':
            command += [ "-i", ]
        # the vsliver imge to use
        command += [ '-t', vref, ]
        # slice name
        command += [ name, ]            
        logger.log_call(command, timeout=15*60)
        # export slicename to the slice in /etc/slicename
        with open('/vservers/{}/etc/slicename'.format(name), 'w') as slicenamefile:
            slicenamefile.write(name)
        with open('/vservers/{}/etc/slicefamily'.format(name), 'w') as slicefamilyfile:
            slicefamilyfile.write(vref)
        # set personality: only if needed (if arch's differ)
        if tools.root_context_arch() != arch:
            with open('/etc/vservers/{}/personality'.format(name), 'w') as personalityfile:
                personalityfile.write(personality(arch)+"\n")
            logger.log('sliver_vs: {}: set personality to {}'.format(name, personality(arch)))

    @staticmethod
    def destroy(name):
        # need to umount before we trash, otherwise we end up with sequels in 
        # /vservers/slicename/ (namely in home/ )
        # also because this is a static method we cannot check for 'omf_control'
        # but it is no big deal as umount_ssh_dir checks before it umounts..
        Account.umount_ssh_dir(name)
        logger.log("sliver_vs: destroying {}".format(name))
        logger.log_call(['/bin/bash', '-x', '/usr/sbin/vuserdel', name, ])


    def configure(self, rec):
        # in case we update nodemanager..
        self.install_and_enable_vinit()

        new_rspec = rec['_rspec']
        if new_rspec != self.rspec:
            self.rspec = new_rspec
            self.set_resources()

        # do the configure part from Initscript
        # i.e. install slice initscript if defined
        Initscript.configure(self, rec)
        # install ssh keys
        Account.configure(self, rec)

    # remember configure() always gets called *before* start()
    # in particular the slice initscript
    # is expected to be in place already at this point
    def start(self, delay=0):
        if self.rspec['enabled'] <= 0:
            logger.log('sliver_vs: not starting {}, is not enabled'.format(self.name))
            return
        logger.log('sliver_vs: {}: starting in {} seconds'.format(self.name, delay))
        time.sleep(delay)
        # the generic /etc/init.d/vinit script is permanently refreshed, and enabled
        self.install_and_enable_vinit()
        # expose .ssh for omf_friendly slivers
        if 'omf_control' in self.rspec['tags']:
            Account.mount_ssh_dir(self.name)
        child_pid = os.fork()
        if child_pid == 0:
            # VServer.start calls fork() internally,
            # so just close the nonstandard fds and fork once to avoid creating zombies
            tools.close_nonstandard_fds()
            vserver.VServer.start(self)
            os._exit(0)
        else:
            os.waitpid(child_pid, 0)

    def stop(self):
        logger.log('sliver_vs: {}: stopping'.format(self.name))
        vserver.VServer.stop(self)

    def is_running(self):
        return vserver.VServer.is_running(self)

    # this one seems to belong in Initscript at first sight, 
    # but actually depends on the underlying vm techno
    # so let's keep it here
    def rerun_slice_vinit(self):
        command = "/usr/sbin/vserver {} exec /etc/rc.d/init.d/vinit restart"\
            .format(self.name)
        logger.log("vsliver_vs: {}: Rerunning slice initscript: {}"
                   .format(self.name, command))
        subprocess.call(command + "&", stdin=open('/dev/null', 'r'),
                        stdout=open('/dev/null', 'w'), stderr=subprocess.STDOUT, shell=True)

    def set_resources(self):
        disk_max = self.rspec['disk_max']
        logger.log('sliver_vs: {}: setting max disk usage to {} KiB'
                   .format(self.name, disk_max))
        try:  # if the sliver is over quota, .set_disk_limit will throw an exception
            if not self.disk_usage_initialized:
                self.vm_running = False
                Sliver_VS._init_disk_info_sem.acquire()
                logger.log('sliver_vs: {}: computing disk usage: beginning'.format(self.name))
                # init_disk_info is inherited from VServer
                try: self.init_disk_info()
                finally: Sliver_VS._init_disk_info_sem.release()
                logger.log('sliver_vs: {}: computing disk usage: ended'.format(self.name))
                self.disk_usage_initialized = True
            vserver.VServer.set_disklimit(self, max(disk_max, self.disk_blocks))
        except:
            logger.log_exc('sliver_vs: failed to set max disk usage', name=self.name)

        # get/set the min/soft/hard values for all of the vserver
        # related RLIMITS.  Note that vserver currently only
        # implements support for hard limits.
        for limit in vserver.RLIMITS.keys():
            type = limit.lower()
            minimum  = self.rspec['{}_min'.format(type)]
            soft = self.rspec['{}_soft'.format(type)]
            hard = self.rspec['{}_hard'.format(type)]
            update = self.set_rlimit(limit, hard, soft, minimum)
            if update:
                logger.log('sliver_vs: {}: setting rlimit {} to ({}, {}, {})'
                           .format(self.name, type, hard, soft, minimum))

        self.set_capabilities_config(self.rspec['capabilities'])
        if self.rspec['capabilities']:
            logger.log('sliver_vs: {}: setting capabilities to {}'
                       .format(self.name, self.rspec['capabilities']))

        cpu_pct = self.rspec['cpu_pct']
        cpu_share = self.rspec['cpu_share']

        count = 1
        for key in self.rspec.keys():
            if key.find('sysctl.') == 0:
                sysctl = key.split('.')
                try:
                    # /etc/vservers/<guest>/sysctl/<id>/
                    dirname = "/etc/vservers/{}/sysctl/{}".format(self.name, count)
                    try:
                        os.makedirs(dirname, 0755)
                    except:
                        pass
                    with open("{}/setting".format(dirname), "w") as setting:
                        setting.write("{}\n".format(key.lstrip("sysctl.")))
                    with open("{}/value".format(dirname), "w") as value:
                        value.write("{}\n".format(self.rspec[key]))
                    count += 1

                    logger.log("sliver_vs: {}: writing {}={}"
                               .format(self.name, key, self.rspec[key]))
                except IOError, e:
                    logger.log("sliver_vs: {}: could not set {}={}"
                               .format(self.name, key, self.rspec[key]))
                    logger.log("sliver_vs: {}: error = {}".format(self.name, e))


        if self.rspec['enabled'] > 0:
            if cpu_pct > 0:
                logger.log('sliver_vs: {}: setting cpu reservation to {}%'
                           .format(self.name, cpu_pct))
            else:
                cpu_pct = 0

            if cpu_share > 0:
                logger.log('sliver_vs: {}: setting cpu share to {}'
                           .format(self.name, cpu_share))
            else:
                cpu_share = 0

            self.set_sched_config(cpu_pct, cpu_share)
            # if IP address isn't set (even to 0.0.0.0), sliver won't be able to use network
            if self.rspec['ip_addresses'] != '0.0.0.0':
                logger.log('sliver_vs: {}: setting IP address(es) to {}'
                           .format(self.name, self.rspec['ip_addresses']))
            add_loopback = True
            if 'isolate_loopback' in self.rspec['tags']:
                add_loopback = self.rspec['tags']['isolate_loopback'] != "1"
            self.set_ipaddresses_config(self.rspec['ip_addresses'], add_loopback)

            #logger.log("sliver_vs: {}: Setting name to {}".format(self.name, self.slice_id))
            #self.setname(self.slice_id)
            #logger.log("sliver_vs: {}: Storing slice id of {} for PlanetFlow".format(self.name, self.slice_id))
            try:
                vserver_config_path = '/etc/vservers/{}'.format(self.name)
                if not os.path.exists (vserver_config_path):
                    os.makedirs (vserver_config_path)
                with open('{}/slice_id'.format(vserver_config_path), 'w') as sliceidfile:
                    sliceidfile.write("{}\n".format(self.slice_id))
                logger.log("sliver_vs: Recorded slice id {} for slice {}"
                           .format(self.slice_id, self.name))
            except IOError as e:
                logger.log("sliver_vs: Could not record slice_id for slice {}. Error: {}"
                           .format(self.name, str(e)))
            except Exception as e:
                logger.log_exc("sliver_vs: Error recording slice id: {}".format(e), name=self.name)


            if self.enabled == False:
                self.enabled = True
                self.start()

            if False: # Does not work properly yet.
                if self.have_limits_changed():
                    logger.log('sliver_vs: {}: limits have changed --- restarting'.format(self.name))
                    stopcount = 10
                    while self.is_running() and stopcount > 0:
                        self.stop()
                        delay = 1
                        time.sleep(delay)
                        stopcount = stopcount - 1
                    self.start()

        else:  # tell vsh to disable remote login by setting CPULIMIT to 0
            logger.log('sliver_vs: {}: disabling remote login'.format(self.name))
            self.set_sched_config(0, 0)
            self.enabled = False
            self.stop()
