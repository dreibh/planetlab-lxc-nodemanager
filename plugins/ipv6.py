# -*- python-indent: 4 -*-

"""
Description: IPv6 Support and Management to Slices
ipv6 nodemanager plugin
Version: 0.5
Author: Guilherme Sperb Machado <gsm@machados.org>
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

radvdConfFile = '/etc/radvd.conf'

def start():
    logger.log("ipv6: plugin starting up...")

def buildLibvirtDefaultNetConfig(dom):

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

def checkForIPv6(defaultNetworkConfig):
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


def addIPv6(defaultNetworkConfig, ipv6addr, prefix):

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

def changeIPv6(dom, ipv6addr, prefix):
    ips = dom.getElementsByTagName('ip')
    for ip in ips:
        if ip.getAttribute("family")=='ipv6' and not(re.match(r'fe80(.*)', ip.getAttribute("address"), re.I)):
            ip.setAttribute("address", ipv6addr)
            ip.setAttribute("prefix", prefix)
    return dom


def removeIPv6(dom):
    networks = dom.getElementsByTagName('network')
    for network in networks:
        ips = network.getElementsByTagName('ip')
        for ip in ips:
            if ip.getAttribute("family")=='ipv6':
                network.removeChild(ip)
    return dom


def checkIfIPv6IsDifferent(dom, ipv6addr, prefix):
    netnodes = dom.getElementsByTagName('network')
    for netnode in netnodes:
        ips = netnode.getElementsByTagName('ip')
        for ip in ips:
            if ip.getAttribute('family')=='ipv6' and \
                   not ( re.match(r'fe80(.*)', ip.getAttribute("address"), re.I) ) and \
                   (ip.getAttribute('address')!=ipv6addr or ip.getAttribute('prefix')!=prefix) :
                logger.log("ipv6: the IPv6 address or prefix are different. Change detected!")
                return True
    return False


def setAutostart(network):
    try:
        network.setAutostart(1)
    except:
        logger.log("ipv6: network could not set to autostart")


def setUp(networkLibvirt, connLibvirt, networkElem, ipv6addr, prefix):
    newXml = networkElem.toxml()
    #logger.log(networkElem.toxml())
    #ret = dir(conn)
    #for method in ret:
    #	logger.log(repr(method))
    networkLibvirt.undefine()
    networkLibvirt.destroy()
    connLibvirt.networkCreateXML(newXml)
    networkDefault = connLibvirt.networkDefineXML(newXml)
    setAutostart(networkDefault)
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
    with open(radvdConfFile,'w') as f:
        f.write(configRadvd)
    killRadvd()
    startRadvd()
    logger.log("ipv6: set up process finalized. Enabled IPv6 address to the slivers!")

def cleanUp(networkLibvirt, connLibvirt, networkElem):
    dom = removeIPv6(networkElem)
    newXml = dom.toxml()
    networkLibvirt.undefine()
    networkLibvirt.destroy()
    # TODO: set autostart for the network
    connLibvirt.networkCreateXML(newXml)
    networkDefault = connLibvirt.networkDefineXML(newXml)
    setAutostart(networkDefault)
    killRadvd()
    logger.log("ipv6: cleanup process finalized. The IPv6 support on the slivers was removed.")

def killRadvd():
    commandKillRadvd = ['killall', 'radvd']
    logger.log_call(commandKillRadvd, timeout=15*60)

def startRadvd():
    commandRadvd = ['radvd']
    logger.log_call(commandRadvd, timeout=15*60)

def GetSlivers(data, config, plc):

    type = 'sliver.LXC'

    interfaces = data['interfaces']
    logger.log(repr(interfaces))
    for interface in interfaces:
	logger.log('ipv6: get interface 1: %r'%(interface))
	if 'interface_tag_ids' in interface:
            interface_tag_ids = "interface_tag_ids"
        interface_tag_id = "interface_tag_id"
        settings = plc.GetInterfaceTags({interface_tag_id:interface[interface_tag_ids]})
        isSliversIPv6PrefixSet = False
        for setting in settings:
            #logger.log(repr(setting))
            # TODO: create a static variable to describe the "sliversipv6prefix" tag
            if setting['tagname']=='sliversipv6prefix':
                ipv6addrprefix = setting['value'].split('/', 1)
                ipv6addr = ipv6addrprefix[0]
                prefix = ipv6addrprefix[1]
                logger.log("ipv6: %s" % (ipv6addr) )
                validIPv6 = tools.isValidIPv6(ipv6addr)
                if not(validIPv6):
                    logger.log("ipv6: the 'sliversipv6prefix' tag presented a non-valid IPv6 address!")
                else:
                    # connecting to the libvirtd
                    connLibvirt = Sliver_Libvirt.getConnection(type)
                    list = connLibvirt.listAllNetworks()
                    for networkLibvirt in list:
                        xmldesc = networkLibvirt.XMLDesc()
                        dom = parseString(xmldesc)
                        hasIPv6 = checkForIPv6(dom)
                        if hasIPv6:
                            # let's first check if the IPv6 is different or is it the same...
                            isDifferent = checkIfIPv6IsDifferent(dom, ipv6addr, prefix)
                            if isDifferent:
                                logger.log("ipv6: tag 'sliversipv6prefix' was modified! " + 
                                           "Updating configuration with the new one...")
                                networkElem = changeIPv6(dom, ipv6addr, prefix)
                                setUp(networkLibvirt, connLibvirt, networkElem, ipv6addr, prefix)
                                logger.log("ipv6: trying to reboot the slivers...")
                                tools.reboot_sliver('blah')
                        else:
                            logger.log("ipv6: starting to redefine the virtual network...")
                            #networkElem = buildLibvirtDefaultNetConfig(dom,ipv6addr,prefix)
                            networkElem = addIPv6(dom, ipv6addr, prefix)
                            setUp(networkLibvirt, connLibvirt, networkElem, ipv6addr, prefix)
                            logger.log("ipv6: trying to reboot the slivers...")
                            tools.reboot_sliver('blah')
            isSliversIPv6PrefixSet = True
        if not(isSliversIPv6PrefixSet):
            # connecting to the libvirtd
            connLibvirt = Sliver_Libvirt.getConnection(type)
            list = connLibvirt.listAllNetworks()
            for networkLibvirt in list:
                xmldesc = networkLibvirt.XMLDesc()
                dom = parseString(xmldesc)
                if checkForIPv6(dom):
                    cleanUp(networkLibvirt, connLibvirt, dom)
                    logger.log("ipv6: trying to reboot the slivers...")
                    tools.reboot_sliver('blah')

    logger.log("ipv6: all done!")
