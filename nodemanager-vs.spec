# we define this in a separate specfile because we cannot produce all the 3 packages
# nodemanager-lib nodemanager-vs nodemanager-lxc in a single build

%define slicefamily %{pldistro}-%{distroname}-%{_arch}

%define name nodemanager-vs
%define version 5.2
%define taglevel 12

%define release %{taglevel}%{?pldistro:.%{pldistro}}%{?date:.%{date}}

Summary: PlanetLab Node Manager Plugin for vserver nodes
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

# old name, when all came as a single package with vserver wired in
Obsoletes: NodeManager
# for nodeupdate 
Provides: nodemanager

# our interface to the vserver patch
Requires: util-vserver >= 0.30.208-17
# and the planetlab utilities
Requires: util-vserver-python > 0.3-16
# the common package for nodemanager
Requires: nodemanager-lib = %{version}
# the vserver-specific tools for using slice images
Requires: vserver-sliceimage

%description
nodemanager-vs provides the vserver code for the PlanetLab Node Manager.

%prep
%setup -q

%build
# make manages the C and Python stuff
%{__make} %{?_smp_mflags} vs

%install
# make manages the C and Python stuff
rm -rf $RPM_BUILD_ROOT
%{__make} %{?_smp_mflags} install-vs DESTDIR="$RPM_BUILD_ROOT"

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root,-)
%{_datadir}/NodeManager/

%changelog
* Fri Apr 04 2014 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - nodemanager-5.2-12
- this tag for the first time passes the full range of tests on fedora20
- robustified slice teardown wrt vsys
- Scott's fix for repairing veth devs
- removed sshsh
- tools.has_systemctl

* Tue Mar 25 2014 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - nodemanager-5.2-11
- ship /etc/sysconfig/nodemanager
- trash sshsh

* Fri Mar 21 2014 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - nodemanager-5.2-10
- comes with systemd native unit files on >= f18
- user-provided initscript gets started through systemd in slivers >= f18
- smarter to locate cgroups for various versions of libvirt
- nicer log format - and log program termination
- tweaks in codemux plugin
- bug fixes in libvirt driver, esp. for finding out if domain is running

* Wed Dec 11 2013 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - nodemanager-5.2-9
- fixes in hostmap, and in interfaces
- new vsys_sysctl
- privatebridge now comes with nodemanager-lib

* Fri Sep 20 2013 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - nodemanager-5.2-8
- omf plugin does not block any longer when running trigger script
- log goes into sliver's /var/log instead

* Wed Aug 28 2013 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - nodemanager-5.2-7
- new install-scripts target in Makefile
- conf_files and fuse-pl initscripts chmod'ed +x
- omf_resctl config template tweaked to use _slicename_%_hostname_

* Sun Jul 14 2013 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - nodemanager-5.2-6
- make sure to create /etc/planetlab/virt so others can read that
- expose get_node_virt() and command_in_slice()
- refined omf_resctl plugin (fetches trigger, and calls it on expire change)
- user's .profile now has right owner
- other tweaks in lxc slivers

* Wed Jul 03 2013 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - nodemanager-5.2-5
- lxc slice creation: slice user was created with unknown gid - fixed
- lxc slice creation: .profile for root and user - fixed

* Sat Jun 29 2013 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - nodemanager-5.2-4
- fix umounting of ssh directory when deleting omf-friendly slivers
- support for writing cgroups in subsystems other than cpuset
- add xid to template match
- finer-grained split between -lib -vs and -lxc
- first roughly complete omf_resctl for omfv6
- minor fix for when getslivers does not have minexemptrate

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

