"""vsys configurator.  Maintains ACLs and script pipes inside vservers based on slice attributes."""

import os
import subprocess

import logger
import tools

VSYSCONF="/etc/vsys.conf"
VSYSBKEND="/vsys"

def start():
    logger.log("vsys: plugin starting up...")

def GetSlivers(data, config=None, plc=None):
    """For each sliver with the vsys attribute, set the script ACL, create the vsys directory in the slice, and restart vsys."""

    if 'slivers' not in data:
        logger.log_missing_data("vsys.GetSlivers",'slivers')
        return

    # Touch ACLs and create dict of available
    scripts = {}
    for script in touchAcls(): scripts[script] = []
    # slices that need to be written to the conf
    slices = []
    _restart = False
    # Parse attributes and update dict of scripts
    if 'slivers' not in data:
        logger.log_missing_data("vsys.GetSlivers",'slivers')
        return
    for sliver in data['slivers']:
        for attribute in sliver['attributes']:
            if attribute['tagname'] == 'vsys':
                if sliver['name'] not in slices:
                    # add to conf
                    slices.append(sliver['name'])
                    _restart = createVsysDir(sliver['name']) or _restart
                if attribute['value'] in scripts.keys():
                    scripts[attribute['value']].append(sliver['name'])

    # Write the conf
    _restart = writeConf(slices, parseConf()) or _restart
    # Write out the ACLs
    if writeAcls(scripts, parseAcls()) or _restart:
        restartService()

# check for systemctl, use it if present
def restartService ():
    if tools.has_systemctl():
        logger.log("vsys: restarting vsys service through systemctl")
        logger.log_call(["systemctl", "restart", "vsys"])
    else:
        logger.log("vsys: restarting vsys service through /etc/init.d/vsys")
        logger.log_call(["/etc/init.d/vsys", "restart", ])

def createVsysDir(sliver):
    '''Create /vsys directory in slice.  Update vsys conf file.'''
    try:
        os.mkdir("/vservers/%s/vsys" % sliver)
        return True
    except OSError:
        return False


def touchAcls():
    '''Creates empty acl files for scripts.
    To be ran in case of new scripts that appear in the backend.
    Returns list of available scripts.'''
    acls = []
    scripts = []
    for (root, dirs, files) in os.walk(VSYSBKEND):
        for file in files:
            # ingore scripts that start with local_
            if file.startswith("local_"): continue
            if file.endswith(".acl"):
                acls.append(file.replace(".acl", ""))
            else:
                scripts.append(file)
    for new in (set(scripts) - set(acls)):
        logger.log("vsys: Found new script %s.  Writing empty acl." % new)
        f = open("%s/%s.acl" %(VSYSBKEND, new), "w")
        f.write("\n")
        f.close()

    return scripts


def writeAcls(currentscripts, oldscripts):
    '''Creates .acl files for script in the script repo.'''
    # Check each oldscript entry to see if we need to modify
    _restartvsys = False
    # for iteritems along dict(oldscripts), if length of values
    # not the same as length of values of new scripts,
    # and length of non intersection along new scripts is not 0,
    # then dicts are different.
    for (acl, oldslivers) in oldscripts.iteritems():
        try:
            if (len(oldslivers) != len(currentscripts[acl])) or \
            (len(set(oldslivers) - set(currentscripts[acl])) != 0):
                _restartvsys = True
                logger.log("vsys: Updating %s.acl w/ slices %s" % (acl, currentscripts[acl]))
                f = open("%s/%s.acl" % (VSYSBKEND, acl), "w")
                for slice in currentscripts[acl]: f.write("%s\n" % slice)
                f.close()
        except KeyError:
            logger.log("vsys: #:)# Warning,Not a valid Vsys script,%s"%acl)
    # Trigger a restart
    return _restartvsys


def parseAcls():
    '''Parse the frontend script acls.  Return {script: [slices]} in conf.'''
    # make a dict of what slices are in what acls.
    scriptacls = {}
    for (root, dirs, files) in os.walk(VSYSBKEND):
        for file in files:
            if file.endswith(".acl") and not file.startswith("local_"):
                f = open(root+"/"+file,"r+")
                scriptname = file.replace(".acl", "")
                scriptacls[scriptname] = []
                for slice in f.readlines():
                    scriptacls[scriptname].append(slice.rstrip())
                f.close()
    # return what scripts are configured for which slices.
    return scriptacls


def writeConf(slivers, oldslivers):
    # Check if this is needed
    # The assumption here is if lengths are the same,
    # and the non intersection of both arrays has length 0,
    # then the arrays are identical.
    if (len(slivers) != len(oldslivers)) or \
    (len(set(oldslivers) - set(slivers)) != 0):
        logger.log("vsys:  Updating %s" % VSYSCONF)
        f = open(VSYSCONF,"w")
        for sliver in slivers:
            f.write("/vservers/%(name)s/vsys %(name)s\n" % {"name": sliver})
        f.truncate()
        f.close()
        return True
    else:
        return False


def parseConf():
    '''Parse the vsys conf and return list of slices in conf.'''
    scriptacls = {}
    slicesinconf = []
    try:
        f = open(VSYSCONF)
        for line in f.readlines():
            (path, slice) = line.split()
            slicesinconf.append(slice)
        f.close()
    except: logger.log_exc("vsys: failed parseConf")
    return slicesinconf


# before shutting down slivers, it is safe to first remove them from vsys's scope
# so that we are sure that no dangling open file remains
# this will also restart vsys if needed
def removeSliverFromVsys (sliver):
    current_slivers=parseConf()
    new_slivers= [ s for s in current_slivers if s != sliver ]
    if writeConf (current_slivers, new_slivers):
        restartService()
        trashVsysHandleInSliver (sliver)
    else:
        logger.log("vsys.removeSliverFromConf: no need to remove %s"%sliver)


def trashVsysHandleInSliver (sliver):
    slice_vsys_area = "/vservers/%s/vsys"%sliver
    if not os.path.exists(slice_vsys_area):
        logger.log("vsys.trashVsysHandleInSliver: no action needed, %s not found"%slice_vsys_area)
        return
    retcod=subprocess.call([ 'rm', '-rf' , slice_vsys_area])
    logger.log ("vsys.trashVsysHandleInSliver: Removed %s (retcod=%s)"%(slice_vsys_area,retcod))
