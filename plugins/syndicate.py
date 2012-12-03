#!/usr/bin/python

""" Syndicate configurator.  """

import httplib
import os
import shutil

from threading import Thread
import logger
import tools

def start():
    logger.log('syndicate plugin starting up...')

def syndicate_op(op, mountpoint, syndicate_ip):
    #op="GET"
    #syndicate_ip="www.vicci.org"

    logger.log("Syndicate: Http op %s on url %s to host %s" % (op, mountpoint, syndicate_ip))

    try:
        conn = httplib.HTTPSConnection(syndicate_ip, timeout=60)
        conn.request(op, mountpoint)
        r1 = conn.getresponse()
    except:
        logger.log_exc("Exception when contacting syndicate sliver", "Syndicate")

    if (r1.status / 100) != 2:
       logger.log("Syndicate: Error: Got http result %d on %s" % (r1.status, mountpoint))
       return False

    return result


def enable_syndicate_mount(sliver, mountpoint, syndicate_ip):
    if not os.path.exists(mountpoint):
       try:
           os.mkdir(mountpoint)
       except:
           logger.log_exc("failed to mkdir syndicate mountpoint", "Syndicate")
           return

    syndicate_op("PUT", mountpoint, syndicate_ip)

def disable_syndicate_mount(sliver, mountpoint, syndicate_ip):
    syndicate_op("DELETE", mountpoint, syndicate_ip)

    if os.path.exists(mountpoint):
       try:
           os.rmdir(mountpoint)
       except:
           logger.log_exc("failed to delete syndicate mountpoint", "Syndicate")

def get_syndicate_ip():
    fn = "/vservers/princeton_syndicate/var/lib/dhclient/dhclient-eth0.leases"
    if not os.path.exists(fn):
        logger.log("Syndicate: cannot find princeton_syndicate's dhclient lease db")
        return None

    fixed_address = None
    for line in open(fn).readlines():
        line = line.strip()
        if line.startswith("fixed-address"):
            fixed_address = line

    if not fixed_address:
        logger.log("Syndicate: no fixed_address line in dhclient lease db")
        return None

    parts=fixed_address.split(" ")
    if len(parts)!=2:
        logger.log("Syndicate: malformed fixed-address line in dhclient: %s" % line)
        return None

    ip = parts[1].strip(";")

    #logger.log("Syndicate ip is %s" % ip)

    return ip

def GetSlivers(data, conf = None, plc = None):
    node_id = tools.node_id()

    if 'slivers' not in data:
        logger.log_missing_data("syndicate.GetSlivers",'slivers')
        return

    for sliver in data['slivers']:
        enable_syndicate = False

        # build a dict of attributes, because it's more convenient
        attributes={}
        for attribute in sliver['attributes']:
           attributes[attribute['tagname']] = attribute['value']

        sliver_name = sliver['name']
        syndicate_mountpoint = os.path.join("/vservers", sliver_name, "syndicate")
        enable_syndicate = attributes.get("enable_syndicate", False)
        has_syndicate = os.path.exists(syndicate_mountpoint)

        if enable_syndicate and (not has_syndicate):
            logger.log("Syndicate: enabling syndicate for %s" % sliver_name)
            #enable_syndicate_mount(sliver, syndicate_mountpoint, get_syndicate_ip())
            t = Thread(target=enable_syndicate_mount, args=(sliver, syndicate_mountpoint, get_syndicate_ip()))
            t.start()

        elif (not enable_syndicate) and (has_syndicate):
            logger.log("Syndicate: disabling syndicate for %s" % sliver_name)
            #disable_syndicate_mount(sliver, syndicate_mountpoint, get_syndicate_ip())
            t = Thread(target=disable_syndicate_mount, args=(sliver, syndicate_mountpoint, get_syndicate_ip()))
            t.start()

