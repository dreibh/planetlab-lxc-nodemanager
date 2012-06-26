# we define this in a separate specfile because we cannot produce all the 3 packages
# nodemanager-lib nodemanager-vs nodemanager-vs in a single build

%define slicefamily %{pldistro}-%{distroname}-%{_arch}

%define name nodemanager-vs
%define version 2.0
%define taglevel 38

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

# Uses function decorators
Requires: nodemanager-lib
# vserver-sliceimage or lxc-sliceimage to be added explicitly in nodeimage.pkgs
Requires: vserver-sliceimage
# our interface to the vserver patch
Requires: util-vserver >= 0.30.208-17
# vserver.py
Requires: util-vserver-python > 0.3-16

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
* Tue Jun 26 2012 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - nodemanager-2.0-38
- split packaging, nodemanager-vs (obsoletes NodeManager) and nodemanager-lib

