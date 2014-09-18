# -*- python-indent: 4 -*-

"""
Description: IPv6 Support and Management to Slices
ipv6 nodemanager plugin
Version: 0.7
Author: Guilherme Sperb Machado <gsm@machados.org>

Requirements:
* The 'sliversipv6prefix' tag must have this format:
  ipv6_address/prefix -- e.g., 2002:1000::1/64
* The prefix specified on 'sliversipv6prefix' tag must be at least 64
  It should vary between 1 and 64, since it is the minimum amount of bits to
  have native IPv6 auto-configuration.
* The ipv6_address on 'sliversipv6prefix' tag can be any valid IPv6 address.
  E.g., 2002:1000:: or 2002:1000::1
* It is the node manager/admin responsibility to properly set the IPv6 routing,
  since slivers should receive/send any kind of traffic.
"""

import logger
import os
import socket
import re

import tools
import libvirt
import uuid
from sliver_libvirt import Sliver_Libvirt
from xml.dom.minidom import parseString

priority=4

radvd_conf_file = '/etc/radvd.conf'
sliversipv6prefixtag = 'sliversipv6prefix'

def start():
    logger.log("ipv6: plugin starting up...")

def build_libvirt_default_net_config(dom):

    # create the <network> element
    networkElem = dom.createElement("network")
    # create <name> element
    nameElem = dom.createElement("name")
    textName = dom.createTextNode("default")
    nameElem.appendChild(textName)
    # create <uuid> element
    uuidElem = dom.createElement("uuid")
    textUUID = dom.createTextNode(str(uuid.uuid1()))
    uuidElem.appendChild(textUUID)
    # create <forward> element
    forwardElem = dom.createElement("forward")
    forwardElem.setAttribute("mode", "nat")
    # create <nat> element
    natElem = dom.createElement("nat")
    # create <port> element
    portElem = dom.createElement("port")
    portElem.setAttribute("end", "65535")
    portElem.setAttribute("start", "1024")
    # create the ipv4 <ip> element
    ipElem0 = dom.createElement("ip")
    ipElem0.setAttribute("address", "192.168.122.1")
    ipElem0.setAttribute("netmask", "255.255.255.0")
    # create the <dhcp> element
    dhcpElem = dom.createElement("dhcp")
    # create the <range> element
    rangeElem = dom.createElement("range")
    rangeElem.setAttribute("end", "192.168.122.254")
    rangeElem.setAttribute("start", "192.168.122.2")
    # create the <bridge> element
    bridgeElem = dom.createElement("bridge")
    bridgeElem.setAttribute("delay", "0")
    bridgeElem.setAttribute("name", "virbr0")
    bridgeElem.setAttribute("stp", "on")

    # build the whole thing
    natElem.appendChild(portElem)
    forwardElem.appendChild(natElem)

    dhcpElem.appendChild(rangeElem)
    ipElem0.appendChild(dhcpElem)
    networkElem.appendChild(nameElem)
    networkElem.appendChild(uuidElem)
    networkElem.appendChild(forwardElem)
    networkElem.appendChild(bridgeElem)
    networkElem.appendChild(ipElem0)
    return networkElem

def check_for_ipv6(defaultNetworkConfig):
    netnodes = defaultNetworkConfig.getElementsByTagName('network')
    hasIPv6 = False
    for netnode in netnodes:
        ips = netnode.getElementsByTagName('ip')
        for ip in ips:
            if ip.getAttribute('family')=='ipv6':
                logger.log("ipv6: IPv6 address/prefix already set for slivers! %s/%s" % \
                           (ip.getAttribute('address'), ip.getAttribute('prefix')) )
                hasIPv6 = True
    return hasIPv6


def add_ipv6(defaultNetworkConfig, ipv6addr, prefix):

    netnodes = defaultNetworkConfig.getElementsByTagName('network')
    for netnode in netnodes:
        # create the ipv6 <ip> element 1
        ipElem1 = defaultNetworkConfig.createElement("ip")
        ipElem1.setAttribute("family", "ipv6")
        ipElem1.setAttribute("address", ipv6addr)
        ipElem1.setAttribute("prefix", prefix)
        # create the ipv6 <ip> element 2
        # it's ugly, I know, but we need a link-local address on the interface!
        ipElem2 = defaultNetworkConfig.createElement("ip")
        ipElem2.setAttribute("family", "ipv6")
        ipElem2.setAttribute("address", "fe80:1234::1")
        ipElem2.setAttribute("prefix", "64")
        # adding to the 'defaultNetworkConfig'
        netnode.appendChild(ipElem1)
        netnode.appendChild(ipElem2)
    return defaultNetworkConfig

def change_ipv6(dom, ipv6addr, prefix):
    ips = dom.getElementsByTagName('ip')
    for ip in ips:
        if ip.getAttribute("family")=='ipv6' and not(re.match(r'fe80(.*)', ip.getAttribute("address"), re.I)):
            ip.setAttribute("address", ipv6addr)
            ip.setAttribute("prefix", prefix)
    return dom


def remove_ipv6(dom):
    networks = dom.getElementsByTagName('network')
    for network in networks:
        ips = network.getElementsByTagName('ip')
        for ip in ips:
            if ip.getAttribute("family")=='ipv6':
                network.removeChild(ip)
    return dom


def check_if_ipv6_is_different(dom, ipv6addr, prefix):
    netnodes = dom.getElementsByTagName('network')
    for netnode in netnodes:
        ips = netnode.getElementsByTagName('ip')
        for ip in ips:
            if ip.getAttribute('family')=='ipv6' and \
                   not ( re.match(r'fe80(.*)', ip.getAttribute("address"), re.I) ) and \
                   (ip.getAttribute('address')!=ipv6addr or ip.getAttribute('prefix')!=prefix) :
                logger.log("ipv6: IPv6 address or prefix are different. Change detected!")
                return True
    return False


def set_autostart(network):
    try:
        network.setAutostart(1)
    except:
        logger.log("ipv6: network could not set to autostart")


def set_up(networkLibvirt, connLibvirt, networkElem, ipv6addr, prefix):
    newXml = networkElem.toxml()
    #logger.log(networkElem.toxml())
    #ret = dir(conn)
    #for method in ret:
    #    logger.log(repr(method))
    networkLibvirt.undefine()
    networkLibvirt.destroy()
    connLibvirt.networkCreateXML(newXml)
    networkDefault = connLibvirt.networkDefineXML(newXml)
    set_autostart(networkDefault)
    commandForwarding = ['sysctl', '-w', 'net.ipv6.conf.all.forwarding=1']
    logger.log_call(commandForwarding, timeout=15*60)
    configRadvd = """
interface virbr0
{
        AdvSendAdvert on;
        MinRtrAdvInterval 30;
        MaxRtrAdvInterval 100;
        prefix %(ipv6addr)s/%(prefix)s
        {
                AdvOnLink on;
                AdvAutonomous on;
                AdvRouterAddr off;
        };

};
""" % locals()
    with open(radvd_conf_file,'w') as f:
        f.write(configRadvd)
    kill_radvd()
    start_radvd()
    logger.log("ipv6: set up process finalized -- enabled IPv6 address to the slivers!")

def clean_up(networkLibvirt, connLibvirt, networkElem):
    dom = remove_ipv6(networkElem)
    newXml = dom.toxml()
    networkLibvirt.undefine()
    networkLibvirt.destroy()
    # TODO: set autostart for the network
    connLibvirt.networkCreateXML(newXml)
    networkDefault = connLibvirt.networkDefineXML(newXml)
    set_autostart(networkDefault)
    kill_radvd()
    logger.log("ipv6: cleanup process finalized. The IPv6 support on the slivers was removed.")

def kill_radvd():
    command_kill_radvd = ['killall', 'radvd']
    logger.log_call(command_kill_radvd, timeout=15*60)

def start_radvd():
    commandRadvd = ['radvd']
    logger.log_call(commandRadvd, timeout=15*60)

def GetSlivers(data, config, plc):

    type = 'sliver.LXC'

    interfaces = data['interfaces']
    logger.log(repr(interfaces))
    for interface in interfaces:
        logger.log('ipv6: get interface: %r'%(interface))
        if 'interface_tag_ids' in interface:
            interface_tag_ids = "interface_tag_ids"
            interface_tag_id = "interface_tag_id"
            settings = plc.GetInterfaceTags({interface_tag_id:interface[interface_tag_ids]})
            is_slivers_ipv6_prefix_set = False
            for setting in settings:
                if setting['tagname']==sliversipv6prefixtag:
                    ipv6addrprefix = setting['value'].split('/', 1)
                    ipv6addr = ipv6addrprefix[0]
                    valid_prefix = False
                    logger.log("ipv6: len(ipv6addrprefix)=%s" % (len(ipv6addrprefix)) )
                    if len(ipv6addrprefix)>1:
                        prefix = ipv6addrprefix[1]
                        logger.log("ipv6: prefix=%s" % (prefix) )
                        if int(prefix)>0 and int(prefix)<=64:
                            valid_prefix = True
                        else:
                            valid_prefix = False
                    else:
                        valid_prefix = False
                    logger.log("ipv6: '%s'=%s" % (sliversipv6prefixtag,ipv6addr) )
                    valid_ipv6 = tools.is_valid_ipv6(ipv6addr)
                    if not(valid_ipv6):
                        logger.log("ipv6: the 'sliversipv6prefix' tag presented a non-valid IPv6 address!")
                    elif not(valid_prefix):
                            logger.log("ipv6: the '%s' tag does not present a valid prefix (e.g., '/64', '/58')!" % \
                                       (sliversipv6prefixtag))
                    else:
                        # connecting to the libvirtd
                        connLibvirt = Sliver_Libvirt.getConnection(type)
                        list = connLibvirt.listAllNetworks()
                        for networkLibvirt in list:
                            xmldesc = networkLibvirt.XMLDesc()
                            dom = parseString(xmldesc)
                            has_ipv6 = check_for_ipv6(dom)
                            if has_ipv6:
                                # let's first check if the IPv6 is different or is it the same...
                                is_different = check_if_ipv6_is_different(dom, ipv6addr, prefix)
                                if is_different:
                                    logger.log("ipv6: tag 'sliversipv6prefix' was modified! " +
                                           "Updating configuration with the new one...")
                                    network_elem = change_ipv6(dom, ipv6addr, prefix)
                                    set_up(networkLibvirt, connLibvirt, network_elem, ipv6addr, prefix)
                                    logger.log("ipv6: trying to reboot the slivers...")
                                    tools.reboot_slivers()
                            else:
                                logger.log("ipv6: starting to redefine the virtual network...")
                                #network_elem = buildLibvirtDefaultNetConfig(dom,ipv6addr,prefix)
                                network_elem = add_ipv6(dom, ipv6addr, prefix)
                                set_up(networkLibvirt, connLibvirt, network_elem, ipv6addr, prefix)
                                logger.log("ipv6: trying to reboot the slivers...")
                                tools.reboot_slivers()
                        is_slivers_ipv6_prefix_set = True
            if not(is_slivers_ipv6_prefix_set):
                # connecting to the libvirtd
                connLibvirt = Sliver_Libvirt.getConnection(type)
                list = connLibvirt.listAllNetworks()
                for networkLibvirt in list:
                    xmldesc = networkLibvirt.XMLDesc()
                    dom = parseString(xmldesc)
                    if check_for_ipv6(dom):
                        clean_up(networkLibvirt, connLibvirt, dom)
                        logger.log("ipv6: trying to reboot the slivers...")
                        tools.reboot_slivers()

    logger.log("ipv6: all done!")
