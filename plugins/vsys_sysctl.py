""" vsys_sysctl

    Touches a slice with lxcsu if it has vsys_sysctl attributes
"""

import logger
import os

def start():
    logger.log("vsys_sysctl: plugin starting up...")

def GetSlivers(data, config=None, plc=None):
    """For each sliver with the vsys attribute, set the script ACL, create the vsys directory in the slice, and restart vsys."""

    if 'slivers' not in data:
        logger.log_missing_data("vsys.GetSlivers",'slivers')
        return

    slices = []

    for sliver in data['slivers']:
        slicename = sliver["name"]
        for attribute in sliver['attributes']:
            if attribute['tagname'].startswith('vsys_sysctl.'):
                dir = "/vservers/%s/vsys_sysctl" % slicename
                if not os.path.exists(dir):
                    try:
                        logger.log("vsys_sysctl: create dir %s" % dir)
                        os.mkdir(dir)
                    except:
                        logger.log("vsys_sysctl: failed to create dir %s" % dir)

                (junk, key) = attribute['tagname'].split(".",1)
                value = str(attribute['value'])

                fn = os.path.join(dir, key)
                if not test_value(fn, value):
                    # All we need to do to make vsys_sysctl work is to lxcsu
                    # into the slice and do anything.
                    result = os.system("lxcsu -r %s :" % slicename)
                    if result != 0:
                        logger.log("vsys_sysctl: failed to lxcsu into %s" % slicename)
                        continue

                    # Store the key name and value inside of /vsys_sysctl in the
                    # slice. This lets us know that we've done the sysctl.
                    try:
                        logger.log("vsys_sysctl: create file %s value %s" % (fn, value))
                        file(fn,"w").write(value+"\n")
                    except:
                        logger.log("vsys_sysctl: failed to create file %s" % fn)

def test_value(fn, value):
    try:
        slice_value = file(fn,"r").readline().strip()
    except:
        slice_value = None

    return (value == slice_value)

