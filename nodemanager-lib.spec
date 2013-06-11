%define slicefamily %{pldistro}-%{distroname}-%{_arch}

%define name nodemanager-lib
%define version 5.2
%define taglevel 3

%define release %{taglevel}%{?pldistro:.%{pldistro}}%{?date:.%{date}}
%global python_sitearch %( python -c "from distutils.sysconfig import get_python_lib; print get_python_lib(1)" )

Summary: PlanetLab Node Manager Library
Name: %{name}
Version: %{version}
Release: %{release}
License: PlanetLab
Group: System Environment/Daemons
Source0: %{name}-%{version}.tar.gz
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root

Vendor: PlanetLab
Packager: PlanetLab Central <support@planet-lab.org>
Distribution: PlanetLab %{plrelease}
URL: %{SCMURL}

# not possible because of forward_api_calls
#BuildArch: noarch

# Uses function decorators
Requires: python >= 2.4
# connecting PLC
Requires: python-pycurl
# Signed tickets
Requires: gnupg
# sioc/plnet
Requires: pyplnet >= 4.3
# we do need the slice images in any case
Requires: sliceimage-%{slicefamily}
# for bwlimit
Requires: plnode-utils

%description
The PlanetLab Node Manager manages all aspects of PlanetLab node and
slice management once the node has been initialized and configured by
the Boot Manager. It periodically contacts its management authority
for configuration updates. It provides an XML-RPC API for performing
local operations on slices.
nodemanager-lib only provides a skeleton and needs as a companion
either nodemanager-vs or nodemanager-lxc

%prep
%setup -q

%build
# make manages the C and Python stuff
%{__make} %{?_smp_mflags} lib

%install
# make manages the C and Python stuff
rm -rf $RPM_BUILD_ROOT
%{__make} %{?_smp_mflags} install-lib DESTDIR="$RPM_BUILD_ROOT"
PYTHON_SITEARCH=`python -c 'from distutils.sysconfig import get_python_lib; print get_python_lib(1)'`

# install the sliver initscript (that triggers the slice initscript if any)
mkdir -p $RPM_BUILD_ROOT/usr/share/NodeManager/sliver-initscripts/
rsync -av sliver-initscripts/ $RPM_BUILD_ROOT/usr/share/NodeManager/sliver-initscripts/
chmod 755 $RPM_BUILD_ROOT/usr/share/NodeManager/sliver-initscripts/

mkdir -p $RPM_BUILD_ROOT/%{_initrddir}/
rsync -av initscripts/ $RPM_BUILD_ROOT/%{_initrddir}/
chmod 755 $RPM_BUILD_ROOT/%{_initrddir}/*

install -d -m 755 $RPM_BUILD_ROOT/var/lib/nodemanager

install -D -m 644 logrotate/nodemanager $RPM_BUILD_ROOT/%{_sysconfdir}/logrotate.d/nodemanager
install -D -m 755 sshsh $RPM_BUILD_ROOT/bin/sshsh

##########
%post
# tmp - handle file renamings; old names are from 2.0-8
renamings="
/var/lib/misc/bwmon.dat@/var/lib/nodemanager/bwmon.pickle
/root/sliver_mgr_db.pickle@/var/lib/nodemanager/database.pickle
/var/log/getslivers.txt@/var/lib/nodemanager/getslivers.txt
/var/log/nm@/var/log/nodemanager
/var/log/nm.daemon@/var/log/nodemanager.daemon
/var/run/nm.pid@/var/run/nodemanager.pid
/tmp/sliver_mgr.api@/tmp/nodemanager.api
/etc/logrotate.d/nm@/etc/logrotate.d/nodemanager
"
for renaming in $renamings; do
  old=$(echo $renaming | cut -d@ -f1)
  new=$(echo $renaming | cut -d@ -f2)
  newdir=$(dirname $new)
  if [ -e "$old" -a ! -e "$new" ] ; then
      mkdir -p $newdir
      mv -f $old $new
  fi
done
#
chkconfig --add conf_files
chkconfig conf_files on
chkconfig --add nm
chkconfig nm on
chkconfig --add fuse-pl
chkconfig fuse-pl on
if [ "$PL_BOOTCD" != "1" ] ; then
	service nm restart
	service fuse-pl restart
fi

##########
%preun
# 0 = erase, 1 = upgrade
if [ $1 -eq 0 ] ; then
    chkconfig fuse-pl off
    chkconfig --del fuse-pl
    chkconfig nm off
    chkconfig --del nm
    chkconfig conf_files off
    chkconfig --del conf_files
fi

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root,-)
%{_datadir}/NodeManager/
%{_bindir}/forward_api_calls
%{_initrddir}/
%{_sysconfdir}/logrotate.d/nodemanager
/var/lib/
/bin/sshsh

%changelog
* Fri May 24 2013 Andy Bavier <acb@cs.princeton.edu> - nodemanager-5.2-3
- Fix path, machine arch in slivers

* Tue Apr 30 2013 Stephen Soltesz <soltesz@opentechinstitute.org> - nodemanager-5.2-2

* Thu Mar 07 2013 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - nodemanager-5.2-1
- no-op bump to 5.2 to be in line with the rest of the system

* Thu Feb 21 2013 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - nodemanager-2.1-22
- improvements to privatebridge

* Sat Jan 19 2013 Scott Baker <smbaker@gmail.com> - nodemanager-2.1-21
- change hostnames related to private IPs to use pvt.hostname instead of slice_name.hostname

* Mon Jan 14 2013 Scott Baker <smbaker@gmail.com> - nodemanager-2.1-20
- fix wrong gre tunnel deleted when topology changes

* Mon Jan 14 2013 Scott Baker <smbaker@gmail.com> - nodemanager-2.1-19
- Update /etc/hosts in slivers from sliver_hostmap tag.

* Mon Jan 07 2013 Scott Baker <smbaker@gmail.com> - nodemanager-2.1-18
- Support passing a list of interfaces in slice interface tag to configure multiple interfaces,
- initial check-in of privatebridge plugin.

* Fri Dec 14 2012 Scott Baker <smbaker@gmail.com> - nodemanager-2.1-17
- set ownership of slice homedir, att slice user to etc/sudoers inside of slice

* Wed Dec 12 2012 Scott Baker <smbaker@gmail.com> - nodemanager-2.1-16
- fix slices not deleted properly when they use vsys

* Mon Dec 10 2012 Scott Baker <smbaker@gmail.com> - nodemanager-2.1-15
- fix error in syndicate plugin, add error message to nodemanager for attributeerror during load/start

* Mon Dec 10 2012 Scott Baker <smbaker@gmail.com> - nodemanager-2.1-14
- Add syndicate plugin, create /etc/hostname and home directory in LXC guests

* Tue Nov 13 2012 Andy Bavier <acb@cs.princeton.edu> - nodemanager-2.1-13
- Bridge virtual interfaces to VLANs

* Wed Oct 24 2012 Andy Bavier <acb@cs.princeton.edu> - nodemanager-2.1-12
- Add support for L2 bridged interfaces with public IPs inside a slice

* Thu Oct 18 2012 Scott Baker <smbaker@gmail.com> - nodemanager-2.1-11
- Support for freezing BestEffort slices for Vicci

* Wed Sep 05 2012 Andy Bavier <acb@cs.princeton.edu> - nodemanager-2.1-10
- Change to use new vsh (wrapper for lxcsu)

* Fri Aug 31 2012 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - nodemanager-2.1-9
- add missing import
- 2.1-8 is less broken than 2.1-7 for omf-friendly slices, in that the slivers would get created, but the OMF-feature probably won't work as .ssh won't get exposed to the sliver

* Thu Aug 30 2012 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - nodemanager-2.1-8
- tag 2.1-7 was broken for OMF-friendly slices
- expose_ssh_dir was erroneously defined on the Worker class

* Thu Jul 19 2012 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - nodemanager-2.1-7
- bwlimitlxc now ships with plnode-utils

* Mon Jul 09 2012 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - nodemanager-2.1-6
- set LD_PRELOAD for linux-containers nodes

* Thu Jun 28 2012 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - nodemanager-2.1-5
- first complete version for vs and lxc - functional but not thoroughly tested though

* Tue Jun 26 2012 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - nodemanager-2.1-4
- split packaging in 3 (lib, lxc, vs)
- this tag will only work with lxc though

* Tue Jun 26 2012 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - nodemanager-2.0-38
- split packaging, nodemanager-vs (obsoletes NodeManager) and nodemanager-lib

* Mon Jun 25 2012 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - nodemanager-2.1-3
- renamed bwlimit as bwlimitlxc to avoid conflicts with util-vserver-pl
- purpose being to be able to run this branch on vserver nodes as well

* Thu Jun 21 2012 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - nodemanager-2.1-2
- merged nodemanager-2.0-37 in 2.1/lxc_devel and add initscript support to lxc
- passes tests with lxc but won't build against vs due to conflict
- as bwlimit.py also ships with util-vserver-pl

* Thu Jun 21 2012 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - nodemanager-2.0-37
- refactoring: isolate initscript functionality
- aimed at making initscript implementation with lxc straightforward
- show stack trace when module loading fails
- accounts.py renamed into account.py for consistency

* Sun Jun 03 2012 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - nodemanager-2.0-36
- /var/log/nodemanager shows duration of mainloop

* Fri Apr 13 2012 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - nodemanager-2.1-1
- first working draft for dealing with libvirt/lxc on f16 nodes
- not expected to work with mainline nodes (use 2.0 for that for now)

* Fri Apr 13 2012 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - nodemanager-2.0-35
- remove Requires to deprecated vserver-* rpms, use sliceimage-* instead

* Fri Dec 09 2011 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - nodemanager-2.0-34
- Added memory scheduling to core scheduler
- Core scheduler will now attempt to schedule cores on the same CPU to a slice, if a slice uses multiple cores

* Thu Jul 07 2011 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - nodemanager-2.0-33
- tweaked log policy for the core scheduler
- curlwrapper has an optional verbose mode

* Mon Jun 06 2011 Baris Metin <bmetin@verivue.com> - nodemanager-2.0-32
- fixes for hmac and omf_control tags
- optional besteffort flag to core scheduler
- logrotate entry for /var/log/nodemanager.daemon
- a template for bash initscripts

* Tue Mar 22 2011 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - nodemanager-2.0-31
- rename initscript_body into initscript_code
- fix generic vinit for broken bash syntax &>>

* Mon Mar 21 2011 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - nodemanager-2.0-30
- new initscript_body slice tag, with stop and restart
- generic vinit script live updated
- new coresched module
- protect against non-existing vsys scripts
- use Config. instead of globals

* Sun Feb 20 2011 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - nodemanager-2.0-29
- more robust reservation plugin

* Thu Feb 17 2011 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - nodemanager-2.0-28
- bind-mount slice's .ssh into sliver for omf-friendly slices - no need to use dotsshmount (vsys) anymore
- reservation plugin more robust

* Tue Feb 01 2011 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - nodemanager-2.0-27
- pass device to bwlimit

* Tue Jan 25 2011 S.Çağlar Onur <caglar@cs.princeton.edu> - nodemanager-2.0-26
- start to use /etc/vservers/<guest>/sysctl/<id>/{setting,value} files as new kernels don't support old syntax

* Tue Jan 04 2011 S.Çağlar Onur <caglar@cs.princeton.edu> - nodemanager-2.0-25
- Catch all exceptions for sfa plugin

* Wed Dec 22 2010 S.Çağlar Onur <caglar@cs.princeton.edu> - nodemanager-2.0-24
- Handle exception AttributeError: ComponentAPI instance has no attribute 'get_registry'

* Mon Nov 29 2010 S.Çağlar Onur <caglar@cs.princeton.edu> - nodemanager-2.0-23
- Use networks key if interfaces is missing to solve the incompatibility between new NM and old API

* Mon Nov 29 2010 S.Çağlar Onur <caglar@cs.princeton.edu> - nodemanager-2.0-22
- plugins/sliverauth.py improvements

* Mon Oct 11 2010 S.Çağlar Onur <caglar@cs.princeton.edu> - nodemanager-2.0-21
- Disable sfagids plugin

* Mon Oct 11 2010 S.Çağlar Onur <caglar@cs.princeton.edu> - nodemanager-2.0-20
- Re-tag nodemanager to include conflicted commits

* Thu Sep 23 2010 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - nodemanager-2.0-19
- hotfix - make the UpdateSliceTag for ssh_key really incremental (was storming the API)
- sfagids plugin deleted
- band-aid patch for lack of GetSliceFamily removed

* Mon Aug 23 2010 S.Çağlar Onur <caglar@cs.princeton.edu> - nodemanager-2.0-18

* Fri Jul 16 2010 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - nodemanager-2.0-17
- revert curlwrapper to former forking-curl version
- fixes in the omf plugin for ssh key location and node hrn
- set umask 0022 in tools.daemon

* Thu Jul 08 2010 Baris Metin <Talip-Baris.Metin@sophia.inria.fr> - nodemanager-2.0-16
- configure omf-resctl for keys

* Mon Jul 05 2010 Baris Metin <Talip-Baris.Metin@sophia.inria.fr> - NodeManager-2.0-15
- fix key generation

* Mon Jul 05 2010 Baris Metin <Talip-Baris.Metin@sophia.inria.fr> - NodeManager-2.0-14
- name changes and fix typos

* Mon Jun 28 2010 S.Çağlar Onur <caglar@cs.princeton.edu> - NodeManager-2.0-13
- remove config and options parameters from start function

* Sat Jun 26 2010 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - NodeManager-2.0-12
- working version of reservable nodes
- sliverauth generates an ssh keypair and export pub part as 'ssh_key' tag
- dismantled the -s|--startup option (no convincing need for that)
- simpler and more robust init.d/nm
- initscript content management through replace_file_with_string
- sliverauth uses replace_file_with_string
- curlwrapper has a debug mode

* Wed Jun 23 2010 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - NodeManager-2.0-11
- pretty-printing/normalized python code - hopefully neutral

* Tue Jun 22 2010 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - NodeManager-2.0-10
- (1) unconditionnally install and chkconfig-like a generic 'vinit' service
- that triggers /etc/init.d/vinit.slice if present and executable
- (2) install the slice-provided initscript (as per the initscript tag) as
- /etc/init.d/vinit.slice
- (3) as a result the initscript are now triggered by rc as part of the
- standard vserver .. start, properly attached to the vserver,
- and properly killed upon vserver .. stop
- (4) this works best with util-vserver-pl 0.3-31 or 0.4-12

* Wed Jun 16 2010 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - NodeManager-2.0-9
- fix for 64bits nodes: add newline to the personality files that instruct util-vserver to create 32bits slivers
- basic/partial support from reservable nodes through the 'reservation plugin' (not fully working yet)
- plugins can set 'persistent_data' to receive the latests know GetSlivers in case the connection is down
- cleanup: moved runtime files in /var/lib/nodemanager, and logs as /var/log/nodemanager* (see specfile)
- cleanup: some modules renamed (e.g. nm.py becomes nodemanager.py)
- cleanup: nodemanger now is a class; however plugins are still dumb modules
- cleanup: does not depend on obsolete Set

* Fri May 14 2010 Talip Baris Metin <Talip-Baris.Metin@sophia.inria.fr> - NodeManager-2.0-8
- tagging before RC

* Wed May 12 2010 S.Çağlar Onur <caglar@cs.princeton.edu> - NodeManager-2.0-7
- Fix typos in plugins/drl.py and doc/NMAPI.xml.in
- Added some precautions to the slice id-saving code
- Added log message to code that records the slice id

* Mon Apr 26 2010 Sapan Bhatia <sapanb@cs.princeton.edu> - NodeManager-2.0-6
- This version changes the location of the slice id for components such as PlanetFlow to look up. Previously this piece
- of information was stored in the 'vserver name' field of the per-vserver context structure in the kernel but we needed
- to move it elsewhere since Daniel decided to use that for something else (the vserver name... pedantic!).

* Wed Apr 14 2010 Talip Baris Metin <Talip-Baris.Metin@sophia.inria.fr> - NodeManager-2.0-5
- fix log_call in plugins/drl.py

* Fri Apr 02 2010 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - NodeManager-2.0-4
- protect against nodes in migrated PLC's not having the hrn tag yet

* Fri Mar 12 2010 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - NodeManager-2.0-3
- new omf-resctl and drl plugins
- specialaccount optimized to overwrite authorized keys only upon changes
- codemux plugin has support for a new 'ip' setting
- mainloop to display ordered modules&plugins at all times

* Thu Feb 11 2010 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - NodeManager-2.0-2
- modules and plugins have a priority
- specialaccounts appears soon in the priority chain
- logger.log_call logs process output, and has a timeout
- vuser{add,del} run through bash -x
- nm initscript has support for 'service nm restartverbose'
- logs reviewed for consistency
- use hashlib module instead of sha when available

* Fri Jan 29 2010 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - NodeManager-2.0-1
- first working version of 5.0:
- pld.c/, db-config.d/ and nodeconfig/ scripts should now sit in the module they belong to
- nodefamily is 3-fold with pldistro-fcdistro-arch
- relies on GetSlivers to expose 'GetSliceFamily' for slivers
- (in addition to the 'vref' tag that's still exposed too)
- logging reviewed for more convenience
- support for 'service nm restartdebug'
- make sync knows how to publish uncommitted code on a test node

* Tue Jan 12 2010 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - NodeManager-1.8-23
- emergency tag - make the setting of hmac by the sliverauth plugin more robust

* Mon Jan 11 2010 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - NodeManager-1.8-22
- support for f10 and f12 in the vref slice tag

* Sat Jan 09 2010 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - NodeManager-1.8-21
- build on fedora12
- uses slicename 'sfacm' instead of 'genicw'

* Fri Oct 30 2009 Sapan Bhatia <sapanb@cs.princeton.edu> - NodeManager-1.8-20
- This tag is identical to 1.8-19. The main addition is PLC-controllable vsys scripts. The reason I am
- retagging is to eliminate any confusion associated with the -19 tag which was (temporarily) modified a few
- days ago.

* Tue Oct 27 2009 Sapan Bhatia <sapanb@cs.princeton.edu> - NodeManager-1.8-19
- This patch makes vsys scripts PLC-configurable. Previously, vsys scripts needed to be
- self-contained. With this change, they will be able to refer to the attributes associated with a
- slice.

* Thu Oct 22 2009 Baris Metin <Talip-Baris.Metin@sophia.inria.fr> - NodeManager-1.8-18
- fix for syntax error

* Wed Oct 21 2009 anil vengalil <avengali@sophia.inria.fr> - NodeManager-1.8-17
- -fixed problem with sioc import at the build side
- -bwlimit.set() now accepts the device and does not asume that it is eth0

* Tue Oct 20 2009 Baris Metin <Talip-Baris.Metin@sophia.inria.fr> - NodeManager-1.8-16
- - don't hardcode the device name (depends on util-vserver-pl change rev. 15385)

* Fri Oct 09 2009 Marc Fiuczynski <mef@cs.princeton.edu> - NodeManager-1.8-15
- The seed for random previously was the meaning of life (i.e., 42) but
- that resulted in a not so random choice for the hmac.  This
- implementation now uses a random.seed that is based on the current
- time.

* Tue Oct 06 2009 Marc Fiuczynski <mef@cs.princeton.edu> - NodeManager-1.8-14
- Minor fix such that sliverauth.py makes a more specific call to
- GetSliceTags that include that specific tagname it is looking for.

* Sat Sep 19 2009 Stephen Soltesz <soltesz@cs.princeton.edu> - NodeManager-1.8-13
- Fix bug that prevented 'OVERRIDES' for working correctly.

* Tue Sep 08 2009 Faiyaz Ahmed <faiyaza@cs.princeton.edu> - NodeManager-1.8-12
- Increase disk limits to 10G per sliver
- Sanity check slice for home directory before starting (hack)
- Check codemux arguments

* Thu Aug 06 2009 Faiyaz Ahmed <faiyaza@cs.princeton.edu> - NodeManager-1.8-11
- * Fix Delegation
- * Move plcapi in plugin-api GetSlivers() calls.
- * Persistent Authcheck and resync session when auth failure

* Tue Aug 04 2009 Faiyaz Ahmed <faiyaza@cs.princeton.edu> - NodeManager-1.8-10
- Disabling sliverauth module.  Not ready for deployment.

* Mon Aug 03 2009 Faiyaz Ahmed <faiyaza@cs.princeton.edu> - NodeManager-1.8-9
- Fixing overrides semantics.

* Mon Aug 03 2009 Faiyaz Ahmed <faiyaza@cs.princeton.edu> - NodeManager-1.8-8
- Generalized plugins
- Fixed initscript start up bug.

* Tue Jun 30 2009 Faiyaz Ahmed <faiyaza@cs.princeton.edu> - NodeManager-1.8-7
- * Fix delegation authentication problem
- * Can now disable codemux using _default slice, and setting tag {codemux: -1}

* Tue May 26 2009 Stephen Soltesz <soltesz@cs.princeton.edu> - NodeManager-1.8-4
- * Rerun initscripts when slice goes from disabled to enabled.

* Tue May 26 2009 Stephen Soltesz <soltesz@cs.princeton.edu> - NodeManager-1.8-4
- * Update session key when out of synch with PLC
- * PLCDefaults uses tagname

* Fri Apr 17 2009 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - NodeManager-1.8-3
- log invokations of vsys

* Fri Mar 27 2009 Faiyaz Ahmed <faiyaza@cs.princeton.edu> - NodeManager-1.8-2

* Tue Mar 24 2009 Faiyaz Ahmed <faiyaza@cs.princeton.edu> - NodeManager-1.8-1

* Wed Apr 02 2008 Faiyaz Ahmed <faiyaza@cs.prineton.edu - NodeManager-1.7.4
- Codemux supports multiple hosts mapping to single slice
- Fixed bug in delegation support where tickets delivered weren't
  being passed to sm.deliver_ticket().

* Fri Mar 28 2008 Faiyaz Ahmed <faiyaza@cs.prineton.edu - NodeManager-1.7.3
- Codemux now configured via slice attribute (host,port)
- Support for multiple vserver reference images (including different archs)
- Mom BW emails are sent to list defined by MyPLC's config
- Sirius BW loans honored correctly.  Fixed.
- BW totals preserved for dynamic slices so as not to game the system.

* Thu Feb 14 2008 Faiyaz Ahmed <faiyaza@cs.princeton.edu> - NodeManager-1.7-1 NodeManager-1.7-2
- Configures vsys via vsys slice attribute {name: vsys, value: script}
- CPU reservations are now calculated via percentages instead of shares
- BW totals preserved for dynamic slices
- Closes bug where node cap sets off bw slice alarms for all slices.

* Wed Oct 03 2007 Faiyaz Ahmed <faiyaza@cs.princeton.edu> .
- Switched to SVN.

* Mon Nov 13 2006 Mark Huang <mlhuang@paris.CS.Princeton.EDU> - 
- Initial build.
