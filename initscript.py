import os, os.path
import tools

import logger

class Initscript:

    def __init__(self, name):
        self.name = name
        self.initscript = ''

    def configure(self, rec):
        # install or remove the slice inistscript, as instructed by the initscript tag
        new_initscript = rec['initscript']
        if new_initscript == self.initscript:
            return
        logger.log("initscript.configure {}".format(self.name))
        self.initscript = new_initscript
        code = self.initscript
        sliver_initscript = "/vservers/%s/etc/rc.d/init.d/vinit.slice" % self.name
        if tools.replace_file_with_string(sliver_initscript, code, remove_if_empty=True, chmod=0o755):
            if code:
                logger.log("Initscript: %s: Installed new initscript in %s" % (self.name, sliver_initscript))
                if self.is_running():
                    # Only need to rerun the initscript if the vserver is
                    # already running. If the vserver isn't running, then the
                    # initscript will automatically be started by
                    # /etc/rc.d/vinit when the vserver is started.
                    self.rerun_slice_vinit()
            else:
                logger.log("Initscript: %s: Removed obsolete initscript %s" % (self.name, sliver_initscript))

    def install_and_enable_vinit(self):
        "prepare sliver rootfs init and systemd so the vinit service kicks in"
        # the fact that systemd attempts to run old-style services 
        # says we should do either one or the other and not both
        # but actually if that was true we could just do it for init and be fine
        # which is not what we've seen starting with f18
        # so we try for a systemd system, and if it fails it means 
        # one of the dir does not exist and so we are dealing with an init-based rootfs
        try:
            self.install_and_enable_vinit_for_systemd ()
        except:
            self.install_and_enable_vinit_for_init ()

    # unconditionnally install and enable the generic vinit script
    # mimicking chkconfig for enabling the generic vinit script
    # this is hardwired for runlevel 3
    def install_and_enable_vinit_for_init(self):
        """
        suitable for init-based VMs
        """
        vinit_source = "/usr/share/NodeManager/sliver-initscripts/vinit"
        vinit_script = "/vservers/%s/etc/rc.d/init.d/vinit" % self.name
        enable_link = "/vservers/%s/etc/rc.d/rc3.d/S99vinit" % self.name
        enable_target = "../init.d/vinit"
        # install in sliver
        with open(vinit_source) as f:
            code = f.read()
        if tools.replace_file_with_string(vinit_script, code, chmod=0o755):
            logger.log("Initscript: %s: installed generic vinit rc script" % self.name)
        # create symlink for runlevel 3
        if not os.path.islink(enable_link):
            try:
                logger.log("Initscript: %s: creating runlevel3 symlink %s" % (self.name, enable_link))
                os.symlink(enable_target, enable_link)
            except:
                logger.log_exc("Initscript failed to create runlevel3 symlink %s" % enable_link, name=self.name)

    # very similar but with systemd unit files - we target 'multi-user' in this context
    def install_and_enable_vinit_for_systemd(self):
        """
        suitable for systemd-based VMs
        """

        ##########
        ########## initscripts : current status - march 2015
        ##########
        #
        # the initscripts business worked smoothly up to f18 inclusive
        # with f20 and the apparition of machinectl, things started to
        # behave really weird
        #
        # so starting with f20, after having tried pretty hard to get this right,
        # but to no success obviously, and in order to stay on the safe side
        # of the force, I am turning off the initscript machinery completely
        # that is to say: the vinit.service does not get installed at all
        # 
        if os.path.isfile('/usr/bin/machinectl'):
            logger.log("WARNING: initscripts are not supported anymore in nodes that have machinectl")
            return

        vinit_source = "/usr/share/NodeManager/sliver-systemd/vinit.service"
        vinit_unit_file = "/vservers/%s/usr/lib/systemd/system/vinit.service" % self.name
        enable_link = "/vservers/%s/etc/systemd/system/multi-user.target.wants/vinit.service" % self.name
        enable_target = "/usr/lib/systemd/system/vinit.service"
        # install in sliver
        with open(vinit_source) as f:
            code = f.read()
        if tools.replace_file_with_string(vinit_unit_file, code, chmod=0o755):
            logger.log("Initscript: %s: installed vinit.service unit file" % self.name)
        # create symlink for enabling this unit
        if not os.path.islink(enable_link):
            try:
                logger.log("Initscript: %s: creating enabling symlink %s" % (self.name, enable_link))
                os.symlink(enable_target, enable_link)
            except:
                logger.log_exc("Initscript failed to create enabling symlink %s" % enable_link, name=name)
