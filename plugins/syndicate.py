#!/usr/bin/python

""" Syndicate configurator.  """

import os
import shutil

import logger
import tools


def start():
    logger.log('syndicate plugin starting up...')

def syndicate_op(op, mountpoint):
    # here is where the magic happens
    pass

def enable_syndicate_mount(sliver, mountpoint):
    if not os.path.exists(mountpoint):
       try:
           os.mkdir(mountpoint)
       except:
           logger.log_exc("failed to mkdir syndicate mountpoint", "Syndicate")
           return

    syndicate_op("PUT", mountpoint)

def dsiable_syndicate_mount(sliver, mountpoint):
    syndicate_op("DELETE", mountpoint)

    if os.path.exists(mountpoint):
       try:
           os.rmdir(mountpoint)
       except:
           logger.log_exc("failed to delete syndicate mountpoint", "Syndicate")

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
            enable_syndicate_mount(sliver, syndicate_mountpoint)

        elif (not enable_syndicate) and (has_syndicate):
            logger.log("Syndicate: disabling syndicate for %s" % sliver_name)
            disable_syndicate_mount(sliver, syndicate_mountpoint)

