### 

"""
Functionality common to all account classes.

Each subclass of Account must provide five methods:
  (*) create() and destroy(), which are static;
  (*) configure(), start(), and stop(), which are not.

configure(), which takes a record as its only argument, does
things like set up ssh keys. In addition, an Account subclass must
provide static member variables SHELL, which contains the unique shell
that it uses; and TYPE, a string that is used by the account creation
code.  For no particular reason, TYPE is divided hierarchically by
periods; at the moment the only convention is that all sliver accounts
have type that begins with sliver.

There are any number of race conditions that may result from the fact
that account names are not unique over time.  Moreover, it's a bad
idea to perform lengthy operations while holding the database lock.
In order to deal with both of these problems, we use a worker thread
for each account name that ever exists.  On 32-bit systems with large
numbers of accounts, this may cause the NM process to run out of
*virtual* memory!  This problem may be remedied by decreasing the
maximum stack size.
"""

import os
import pwd, grp
import threading
import subprocess

import logger
import tools


# shell path -> account class association
shell_acct_class = {}
# account type -> account class association
type_acct_class = {}

# these semaphores are acquired before creating/destroying an account
create_sem = threading.Semaphore(1)
destroy_sem = threading.Semaphore(1)

def register_class(acct_class):
    """
    Call once for each account class. This method adds the class
    to the dictionaries used to look up account classes
    by shell and type.
    """
    shell_acct_class[acct_class.SHELL] = acct_class
    type_acct_class[acct_class.TYPE] = acct_class


# private account name -> worker object association and associated lock
name_worker_lock = threading.Lock()
name_worker = {}

def allpwents():
    return [pw_ent for pw_ent in pwd.getpwall() if pw_ent[6] in shell_acct_class]

def all():
    """Return the names of all accounts on the system with recognized shells."""
    return [pw_ent[0] for pw_ent in allpwents()]

def get(name):
    """
    Return the worker object for a particular username.
    If no such object exists, create it first.
    """
    name_worker_lock.acquire()
    try:
        if name not in name_worker:
            name_worker[name] = Worker(name)
        return name_worker[name]
    finally:
        name_worker_lock.release()


class Account:
    """
    Base class for all types of account
    """

    def __init__(self, name):
        self.name = name
        self.keys = ''
        logger.verbose('account: Initing account {}'.format(name))

    @staticmethod
    def create(name, vref = None):
        abstract

    @staticmethod
    def destroy(name):
        abstract

    def configure(self, rec):
        """
        Write <rec['keys']> to my authorized_keys file.
        """
        new_keys = rec['keys']
        nb_keys = len(new_keys) if isinstance(new_keys, list) else 1
        logger.verbose('account: configuring {} with {} keys'.format(self.name, nb_keys))
        if new_keys != self.keys:
            # get the unix account info
            gid = grp.getgrnam("slices")[2]
            pw_info = pwd.getpwnam(self.name)
            uid = pw_info[2]
            pw_dir = pw_info[5]

            # write out authorized_keys file and conditionally create
            # the .ssh subdir if need be.
            dot_ssh = os.path.join(pw_dir, '.ssh')
            if not os.path.isdir(dot_ssh):
                if not os.path.isdir(pw_dir):
                    logger.verbose('account: WARNING: homedir {} does not exist for {}!'
                                   .format(pw_dir, self.name))
                    os.mkdir(pw_dir)
                    os.chown(pw_dir, uid, gid)
                os.mkdir(dot_ssh)

            auth_keys = os.path.join(dot_ssh, 'authorized_keys')
            tools.write_file(auth_keys, lambda f: f.write(new_keys))

            # set access permissions and ownership properly
            os.chmod(dot_ssh, 0o700)
            os.chown(dot_ssh, uid, gid)
            os.chmod(auth_keys, 0o600)
            os.chown(auth_keys, uid, gid)

            # set self.keys to new_keys only when all of the above ops succeed
            self.keys = new_keys

            logger.log('account: {}: installed ssh keys'.format(self.name))

    def start(self, delay=0):
        pass
    def stop(self):
        pass
    def is_running(self):
        pass
    def needs_reimage(self, target_slicefamily):
        stampname = "/vservers/{}/etc/slicefamily".format(self.name)
        try:
            with open(stampname) as f:
                current_slicefamily = f.read().strip()
                return current_slicefamily != target_slicefamily
        except IOError as e:
            logger.verbose("Account.needs_reimage: missing slicefamily {} - left as-is"
                           .format(self.name))
            return False

    ### this used to be a plain method but because it needs to be invoked by destroy
    # which is a static method, they need to become static as well
    # needs to be done before sliver starts (checked with vs and lxc)
    @staticmethod
    def mount_ssh_dir (slicename):
        return Account._manage_ssh_dir (slicename, do_mount=True)
    @staticmethod
    def umount_ssh_dir (slicename):
        return Account._manage_ssh_dir (slicename, do_mount=False)

    # bind mount / umount root side dir to sliver side
    @staticmethod
    def _manage_ssh_dir (slicename, do_mount):
        logger.log("_manage_ssh_dir, requested to " +
                   ( "mount" if do_mount else "umount" ) +
                   " ssh dir for "+ slicename)
        try:
            root_ssh = "/home/{}/.ssh".format(slicename)
            sliver_ssh = "/vservers/{}/home/{}/.ssh".format(slicename, slicename)
            def is_mounted (root_ssh):
                with open('/proc/mounts') as mountsfile:
                    for mount_line in mountsfile.readlines():
                        if mount_line.find (root_ssh) >= 0:
                            return True
                return False
            if do_mount:
                # any of both might not exist yet
                for path in [root_ssh, sliver_ssh]:
                    if not os.path.exists (path):
                        os.mkdir(path)
                    if not os.path.isdir (path):
                        raise Exception
                if not is_mounted(root_ssh):
                    command = ['mount', '--bind', '-o', 'ro', root_ssh, sliver_ssh]
                    mounted = logger.log_call (command)
                    msg = "OK" if mounted else "WARNING: FAILED"
                    logger.log("_manage_ssh_dir: mounted {} into slice {} - {}"
                               .format(root_ssh, slicename, msg))
            else:
                if is_mounted (sliver_ssh):
                    command = ['umount', sliver_ssh]
                    umounted = logger.log_call(command)
                    msg = "OK" if umounted else "WARNING: FAILED"
                    logger.log("_manage_ssh_dir: umounted {} - {}"
                               .format(sliver_ssh, msg))
        except Exception as e:
            logger.log_exc("_manage_ssh_dir failed : {}".format(e), name=slicename)

class Worker:

    def __init__(self, name):
        self.name = name  # username
        self._acct = None  # the account object currently associated with this worker

    def ensure_created(self, rec):
        """
        Check account type is still valid.  If not, recreate sliver.
        If still valid, check if running and configure/start if not.
        """
        logger.log_data_in_file(rec, "/var/lib/nodemanager/{}.rec.txt".format(rec['name']),
                                'raw rec captured in ensure_created', logger.LOG_VERBOSE)
        curr_class = self._get_class()
        next_class = type_acct_class[rec['type']]
        if next_class != curr_class:
            self._destroy(curr_class)
            create_sem.acquire()
            try: next_class.create(self.name, rec)
            finally: create_sem.release()
        if not isinstance(self._acct, next_class):
            self._acct = next_class(rec)
        logger.verbose("account.Worker.ensure_created: {}, running={}"
                       .format(self.name, self.is_running()))

        # reservation_alive is set on reservable nodes, and its value is a boolean
        if 'reservation_alive' in rec:
            # reservable nodes
            if rec['reservation_alive']:
                # this sliver has the lease, it is safe to start it
                if not self.is_running():
                    self.start(rec)
                else:
                    self.configure(rec)
            else:
                # not having the lease, do not start it
                self.configure(rec)
        # usual nodes - preserve old code
        # xxx it's not clear what to do when a sliver changes type/class
        # in a reservable node
        else:
            if not self.is_running() or self.needs_reimage(rec['vref']) or next_class != curr_class:
                self.start(rec)
            else:
                self.configure(rec)

    def ensure_destroyed(self):
        self._destroy(self._get_class())

    # take rec as an arg here for api_calls
    def start(self, rec, d = 0):
        self._acct.configure(rec)
        self._acct.start(delay=d)

    def configure(self, rec):
        self._acct.configure(rec)

    def stop(self):
        self._acct.stop()

    def is_running(self):
        if self._acct and self._acct.is_running():
            return True
        else:
            logger.verbose("Worker.is_running ({}) - no account or not running".format(self.name))
            return False

    def needs_reimage(self, target_slicefamily):
        if not self._acct:
            logger.verbose("Worker.needs_reimage ({}) - no account -> True".format(self.name))
            return True
        else:
            account_needs_reimage = self._acct.needs_reimage(target_slicefamily)
            if account_needs_reimage:
                logger.log("Worker.needs_reimage ({}) - account needs reimage (tmp: DRY RUN)"
                           .format(self.name))
            else:
                logger.verbose("Worker.needs_reimage ({}) - everything fine"
                               .format(self.name))
            return account_needs_reimage
    
    def _destroy(self, curr_class):
        self._acct = None
        if curr_class:
            destroy_sem.acquire()
            try:
                logger.verbose("account._destroy is callling destroy from {}"
                               .format(curr_class.__name__))
                curr_class.destroy(self.name)
            finally:
                destroy_sem.release()

    def _get_class(self):
        try:
            shell = pwd.getpwnam(self.name)[6]
        except KeyError:
            return None
        return shell_acct_class[shell]

