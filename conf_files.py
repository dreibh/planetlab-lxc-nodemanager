#!/usr/bin/env python3

# pylint: disable=c0111

"""
update local configuration files from PLC
"""

import grp
import os
import pwd
from hashlib import sha1 as sha
import xmlrpc.client

import curlwrapper
import logger
import tools
from config import Config

# right after net
priority = 2

class conf_files:
    def __init__(self, noscripts=False):
        self.config = Config()
        self.noscripts = noscripts
        self.data = None

    def checksum(self, path):
        try:
            with open(path) as feed:
                return sha(feed.read()).digest()
        except IOError:
            return None

    def system(self, cmd):
        if not self.noscripts and cmd:
            logger.verbose('conf_files: running command %s' % cmd)
            return tools.fork_as(None, os.system, cmd)
        else: return 0

    def update_conf_file(self, cf_rec):
        if not cf_rec['enabled']:
            return
        dest = cf_rec['dest']
        err_cmd = cf_rec['error_cmd']
        mode = int(cf_rec['file_permissions'], base=8)
        try:
            uid = pwd.getpwnam(cf_rec['file_owner'])[2]
        except:
            logger.log('conf_files: cannot find user %s -- %s not updated'
                       %(cf_rec['file_owner'], dest))
            return
        try:
            gid = grp.getgrnam(cf_rec['file_group'])[2]
        except:
            logger.log('conf_files: cannot find group %s -- %s not updated'
                       %(cf_rec['file_group'], dest))
            return
        url = 'https://%s/%s' % (self.config.PLC_BOOT_HOST, cf_rec['source'])
        # set node_id at the end of the request - hacky
        if tools.node_id():
            if url.find('?') > 0:
                url += '&'
            else:
                url += '?'
            url += "node_id=%d"%tools.node_id()
        else:
            logger.log('conf_files: %s -- WARNING, cannot add node_id to request'
                       % dest)
        try:
            logger.verbose("conf_files: retrieving URL=%s"%url)
            contents = curlwrapper.retrieve(url, self.config.cacert)
        except xmlrpc.client.ProtocolError as e:
            logger.log('conf_files: failed to retrieve %s from %s, skipping' % (dest, url))
            return
        if not cf_rec['always_update'] and sha(contents).digest() == self.checksum(dest):
            return
        if self.system(cf_rec['preinstall_cmd']):
            self.system(err_cmd)
            if not cf_rec['ignore_cmd_errors']:
                return
        logger.log('conf_files: installing file %s from %s' % (dest, url))
        try:
            os.makedirs(os.path.dirname(dest))
        except OSError:
            pass
        tools.write_file(dest, lambda f: f.write(contents),
                         mode=mode, uidgid=(uid, gid))
        if self.system(cf_rec['postinstall_cmd']):
            self.system(err_cmd)

    def run_once(self, data):
        if "conf_files" in data:
            for file in data['conf_files']:
                try:
                    self.update_conf_file(file)
                except:
                    logger.log_exc("conf_files: failed to update conf_file")
        else:
            logger.log_missing_data("conf_files.run_once", 'conf_files')


def start():
    pass


def GetSlivers(data, config=None, plc=None):
    logger.log("conf_files: Running.")
    instance = conf_files()
    instance.run_once(data)
    logger.log("conf_files: Done.")


def main():
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument('-f', '--config', action='store', dest='config',
                        default='/etc/planetlab/plc_config',
                        help='PLC configuration file')
    parser.add_argument('-k', '--session', action='store', dest='session',
                        default='/etc/planetlab/session',
                        help='API session key (or file)')
    parser.add_argument('--noscripts', action='store_true', dest='noscripts',
                        default=False,
                        help='Do not run pre- or post-install scripts')
    args = parser.parse_args()

    # Load /etc/planetlab/plc_config
    config = Config(args.config)

    # Load /etc/planetlab/session
    if os.path.exists(args.session):
        with open(args.session) as feed:
            session = feed.read().strip()
    else:
        session = args.session

    # Initialize XML-RPC client
    from plcapi import PLCAPI
    plc = PLCAPI(config.plc_api_uri, config.cacert, auth=session)
    data = plc.GetSlivers()

    instance = conf_files(args.noscripts)
    instance.run_once(data)


if __name__ == '__main__':
    main()
