#
# NodeManager plugin - first step of handling omf_controlled slices
#

"""
Overwrites the 'resctl' tag of slivers controlled by OMF so slivermanager.py does the right thing
"""

import os, os.path
import glob
import subprocess

import tools
import logger

priority = 50

def start():
    pass

### the new template for v6
# hard-wire this for now
# once the variables are expanded, this is expected to go into
config_ple_template="""---
# Example:
# _slicename_ = nicta_ruby
# _hostname_ = planetlab1.research.nicta.com.au
# _xmpp_server_ = xmpp.planet-lab.eu
 
:uid: _slicename_@_hostname_
:uri: xmpp://_slicename_-_hostname_-<%= "#{Process.pid}" %>:_slicename_-_hostname_-<%= "#{Process.pid}" %>@_xmpp_server_
:environment: production
:debug: false
 
:auth:
  :root_cert_dir: /home/_slicename_/root_certs
  :entity_cert: /home/_slicename_/entity.crt
  :entity_key: /home/_slicename_/.ssh/id_rsa
"""

# the path where the config is expected from within the sliver
yaml_slice_path="/etc/omf_rc/config.yml"
# the path for the script that we call when a change occurs
omf_rc_trigger_script="/some/path/to/the/change/script"

def GetSlivers(data, conf = None, plc = None):
    logger.log("omf_resctl.GetSlivers")
    if 'accounts' not in data:
        logger.log_missing_data("omf_resctl.GetSlivers",'accounts')
        return

    try:
        xmpp_server=data['xmpp']['server']
        if not xmpp_server: 
            # we have the key but no value, just as bad
            raise Exception
    except:
        # disabled feature - bailing out
        # xxx might need to clean up more deeply..
        logger.log("PLC config unsufficient (not enabled, or no server set), see the PLC_OMF category -- plugin exiting")
        return

    hostname = data['hostname']

    def is_omf_friendly (sliver):
        for chunk in sliver['attributes']:
            if chunk['tagname']=='omf_control': return True

    for sliver in data['slivers']:
        # skip non OMF-friendly slices
        if not is_omf_friendly (sliver): continue
        slicename=sliver['name']
        yaml_template = config_ple_template
        yaml_contents = yaml_template\
            .replace('_xmpp_server_',xmpp_server)\
            .replace('_slicename_',slicename)\
            .replace('_hostname_',hostname)
        yaml_full_path="/vservers/%s/%s"%(slicename,yaml_slice_path)
        yaml_full_dir=os.path.dirname(yaml_full_path)
        if not os.path.isdir(yaml_full_dir):
            try: os.makedirs(yaml_full_dir)
            except OSError: pass

        changes=tools.replace_file_with_string(yaml_full_path,yaml_contents)
        logger.log("yaml_contents length=%d, changes=%r"%(len(yaml_contents),changes))
        if changes:
            # instead of restarting the service we call a companion script
            try:
                sp=subprocess.Popen([omf_rc_trigger_script],
                                    stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
                (output,retcod)=sp.communicate()
                logger.log("omf_resctl: %s: called OMF rc control script (retcod=%r)"%(slicename,retcod))
                logger.log("omf_resctl: got output\n%s"%output)
            except:
                logger.log("omf_resctl: WARNING: Could not call trigger script %s"%omf_rc_trigger_script)
        else:
            logger.log("omf_resctl: %s: omf_control'ed sliver has no change" % slicename)
