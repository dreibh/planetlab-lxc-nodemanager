# we define this in a separate specfile because we cannot produce all the 3 packages
# nodemanager-lib nodemanager-vs nodemanager-lxc in a single build

%define slicefamily %{pldistro}-%{distroname}-%{_arch}

%define name nodemanager-lxc
%define version 2.1
%define taglevel 6

%define release %{taglevel}%{?pldistro:.%{pldistro}}%{?date:.%{date}}

Summary: PlanetLab Node Manager Plugin for lxc nodes
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

# we use libvirt
Requires: libvirt
Requires: libvirt-python
# cgroups.py needs this
Requires: python-inotify
# the common package for nodemanager
Requires: nodemanager-lib
# the lxc-specific tools for using slice images
Requires: lxc-sliceimage

%description
nodemanager-lxc provides the lxc code for the PlanetLab Node Manager.

%prep
%setup -q

%build
# make manages the C and Python stuff
%{__make} %{?_smp_mflags} lxc

%install
# make manages the C and Python stuff
rm -rf $RPM_BUILD_ROOT
%{__make} %{?_smp_mflags} install-lxc DESTDIR="$RPM_BUILD_ROOT"

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root,-)
%{_datadir}/NodeManager/

%changelog
* Mon Jul 09 2012 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - nodemanager-2.1-6
- set LD_PRELOAD for linux-containers nodes

* Thu Jun 28 2012 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - nodemanager-2.1-5
- first complete version for vs and lxc - functional but not thoroughly tested though

* Tue Jun 26 2012 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - nodemanager-2.1-4
- split packaging in 3 (lib, lxc, vs)
- this tag will only work with lxc though

