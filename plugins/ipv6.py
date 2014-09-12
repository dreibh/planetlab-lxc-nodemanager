"""
IPv6 test! version: 0.3
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
ipv6addrtag = 'ipv6_address'

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
                                logger.log("ipv6: the configuration already have an IPv6 address/prefix set for the slivers! %s/%s" % (ip.getAttribute('address'), ip.getAttribute('prefix')) )
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
			if ip.getAttribute('family')=='ipv6' and not( re.match(r'fe80(.*)', ip.getAttribute("address"), re.I) ) and (ip.getAttribute('address')!=ipv6addr or ip.getAttribute('prefix')!=prefix):
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
        prefix %s
        {
                AdvOnLink on;
                AdvAutonomous on;
                AdvRouterAddr off;
        };

};
""" % (ipv6addr+"/"+prefix)
	f=open(radvdConfFile,'w')
        f.write(configRadvd)
	f.close()
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

def getSliverTagId(slivertags):
	for slivertag in slivertags:
		if slivertag['tagname']==ipv6addrtag:
			return slivertag['slice_tag_id']


def SetSliverTag(plc, data, tagname):

    for sliver in data['slivers']:
	# TODO: what about the prefixlen? should we add on it as well?
	# here, I'm just taking the ipv6addr (value)
	value,prefixlen = tools.get_sliver_ipv6(sliver['name'])

    	node_id = tools.node_id()
	logger.log("ipv6: slice %s" % (slice) )
	logger.log("ipv6: nodeid %s" % (node_id) )
	slivertags = plc.GetSliceTags({"name":slice['name'],"node_id":node_id,"tagname":tagname})
	logger.log(repr(str(slivertags)))
	for tag in slivertags:
		logger.log(repr(str(tag)))

	ipv6addr = plc.GetSliceIPv6Address(slice['name'])
	# if the value to set is null...
	if value is None:
		if ipv6addr is not None or len(ipv6addr)==0:
			# then, let's remove the slice tag
			slivertag_id = getSliverTagId(slivertags)
			plc.DeleteSliceTag(slivertag_id)
	else:
		# if the ipv6 addr set on the slice does not exist yet, so, let's add it
		if (len(ipv6addr)==0 or ipv6addr is None) and len(value)>0:
			try:
				slivertag_id=plc.AddSliceTag(slice['name'],tagname,value,node_id)
				logger.log("ipv6: slice tag added to slice %s" % (slice['name']) )
			except:
				logger.log_exc ("ipv6: could not set ipv6 addr tag to the slive. slice=%(slice['name'])s tag=%(tagname)s node_id=%(node_id)d" % locals() )
		# if the ipv6 addr set on the slice is different on the value provided, let's update it
		if len(value)>0 and ipv6addr!=value:
			#slivertag_id=slivertags[0]['slice_tag_id']
			slivertag_id = getSliverTagId(slivertags)
	        	plc.UpdateSliceTag(slivertag_id,value)
	

def GetSlivers(data, config, plc):

    #return
    #for sliver in data['slivers']:
    	#ipv6addr,prefixlen = tools.get_sliver_ipv6(sliver['name'])
	#tools.add_ipv6addr_hosts_line(sliver['name'], data['hostname'], ipv6addr)
	#result = tools.search_ipv6addr_hosts(sliver['name'], ipv6addr)
	#logger.log("tools: result=%s" % (str(result)) )
        #tools.remove_all_ipv6addr_hosts(sliver['name'], data['hostname'])
    #return
    

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
								logger.log("ipv6: the tag 'sliversipv6prefix' was modified! Updating the configuration with the new one...")
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
