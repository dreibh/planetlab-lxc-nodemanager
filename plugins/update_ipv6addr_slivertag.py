"""
Description: Update the IPv6 Address sliver tag accordingly to the IPv6 address set
update_ipv6addr_slivertag nodemanager plugin
Version: 0.5
Author: Guilherme Sperb Machado <gsm@machados.org>
"""

import logger
import os
import socket
import re

import tools
import uuid
from xml.dom.minidom import parseString

# TODO: is there anything better to do if the "libvirt", "sliver_libvirt",
# and are not in place in the VS distro?
try:
    import libvirt
    from sliver_libvirt import Sliver_Libvirt
except:
    logger.log("Could not import 'sliver_lxc' or 'libvirt'.")

priority=150

ipv6addrtag = 'ipv6_address'

def start():
    logger.log("update_ipv6addr_slivertag: plugin starting up...")


def get_sliver_tag_id_value(slivertags):
    for slivertag in slivertags:
        if slivertag['tagname']==ipv6addrtag:
            return slivertag['slice_tag_id'], slivertag['value']

def SetSliverTag(plc, data, tagname):

    virt=tools.get_node_virt()
    if virt!='lxc':
        return

    for slice in data['slivers']:
#        logger.log("update_ipv6addr_slivertag: starting with slice=%s" % (slice['name']) )

        # TODO: what about the prefixlen? should we add on it as well?
        # here, I'm just taking the ipv6addr (value)
        value,prefixlen = tools.get_sliver_ipv6(slice['name'])

        node_id = tools.node_id()
        slivertags = plc.GetSliceTags({"name":slice['name'],"node_id":node_id,"tagname":tagname})
        #logger.log(repr(str(slivertags)))
        #for tag in slivertags:
            #    logger.log(repr(str(tag)))

        try:
            slivertag_id,ipv6addr = get_sliver_tag_id_value(slivertags)
        except:
            slivertag_id,ipv6addr = None,None
        logger.log("update_ipv6addr_slivertag: slice=%s getSliceIPv6Address=%s" % \
               (slice['name'],ipv6addr) )
        # if the value to set is null...
        if value is None:
            if ipv6addr is not None:
                # then, let's remove the slice tag
                if slivertag_id:
                    try:
                        plc.DeleteSliceTag(slivertag_id)
                        logger.log("update_ipv6addr_slivertag: slice tag deleted for slice=%s" % \
                               (slice['name']) )
                    except:
                        logger.log("update_ipv6addr_slivertag: slice tag not deleted for slice=%s" % \
                               (slice['name']) )
            result = tools.search_ipv6addr_hosts(slice['name'], value)
            if result:
                # if there's any ipv6 address, then remove everything from the /etc/hosts
                tools.remove_all_ipv6addr_hosts(slice['name'], data['hostname'])
        else:
            # if the ipv6 addr set on the slice does not exist yet, so, let's add it
            if (ipv6addr is None) and len(value)>0:
                try:
                    logger.log("update_ipv6addr_slivertag: slice name=%s" % (slice['name']) )
                    slivertag_id=plc.AddSliceTag(slice['name'],tagname,value,node_id)
                    logger.log("update_ipv6addr_slivertag: slice tag added to slice %s" % \
                           (slice['name']) )
                except:
                    logger.log("update_ipv6addr_slivertag: could not set ipv6 addr tag to sliver. "+
                           "slice=%s tag=%s node_id=%d" % (slice['name'],tagname,node_id) )
            # if the ipv6 addr set on the slice is different on the value provided, let's update it
            if (ipv6addr is not None) and (len(value)>0) and (ipv6addr!=value):
                plc.UpdateSliceTag(slivertag_id,value)
            # ipv6 entry on /etc/hosts of each slice
            result = tools.search_ipv6addr_hosts(slice['name'], value)
            if not result:
                tools.remove_all_ipv6addr_hosts(slice['name'], data['hostname'])
                tools.add_ipv6addr_hosts_line(slice['name'], data['hostname'], value)
#        logger.log("update_ipv6addr_slivertag: finishing the update process for " +
#               "slice=%s" % (slice['name']) )

def GetSlivers(data, config, plc):
    SetSliverTag(plc, data, ipv6addrtag)
    logger.log("update_ipv6addr_slivertag: all done!")
