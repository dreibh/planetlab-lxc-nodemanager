# we define this in a separate specfile because we cannot produce all the 3 packages
# nodemanager-lib nodemanager-vs nodemanager-lxc in a single build

%define slicefamily %{pldistro}-%{distroname}-%{_arch}

%define name nodemanager-vs
%define version 2.1
%define taglevel 11

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

# our interface to the vserver patch
Requires: util-vserver >= 0.30.208-17
# and the planetlab utilities
Requires: util-vserver-python > 0.3-16
# the common package for nodemanager
Requires: nodemanager-lib
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

