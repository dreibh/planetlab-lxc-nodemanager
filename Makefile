#
# Node Manager Makefile
#
# David Eisenstat <deisenst@cs.princeton.edu>
# Mark Huang <mlhuang@cs.princeton.edu>
# Copyright (C) 2006 The Trustees of Princeton University
#

# autoconf compatible variables
datadir := /usr/share
bindir := /usr/bin
initdir=/etc/rc.d/init.d
systemddir := /usr/lib/systemd/system

PYTHON = python3

# call with either WITH_SYSTEMD=true or WITH_INIT=true
# otherwise we try to guess some reasonable default
ifeq "$(WITH_INIT)$(WITH_SYSTEMD)" ""
ifeq "$(wildcard $systemddir/*)" ""
WITH_INIT=true
else
WITH_SYSTEMD=true
endif
endif
####################
all: forward_api_calls
	$(PYTHON) setup.py build

forward_api_calls: forward_api_calls.c
	$(CC) -Wall -Os -o $@ $?
	strip $@

#################### install
install: install-miscell install-startup
	$(PYTHON) setup.py install \
		--install-purelib=$(DESTDIR)/$(datadir)/NodeManager \
		--install-platlib=$(DESTDIR)/$(datadir)/NodeManager \
		--install-scripts=$(DESTDIR)/$(bindir)

# might be better in setup.py ?
# NOTE: the sliver-initscripts/ and sliver-systemd stuff, being, well, for slivers,
# need to ship on all nodes regardless of WITH_INIT and WITH_SYSTEMD that
# impacts how nodemanager itself gets started
install-miscell:
	install -D -m 755 forward_api_calls $(DESTDIR)/$(bindir)/forward_api_calls
	install -d -m 755 $(DESTDIR)/var/lib/nodemanager
	install -D -m 644 /dev/null $(DESTDIR)/etc/sysconfig/nodemanager
	install -D -m 444 README $(DESTDIR)/$(datadir)/NodeManager/README
	install -D -m 644 logrotate/nodemanager $(DESTDIR)/etc/logrotate.d/nodemanager
	mkdir -p $(DESTDIR)/$(datadir)/NodeManager/sliver-initscripts
	rsync -av sliver-initscripts/ $(DESTDIR)/$(datadir)/NodeManager/sliver-initscripts/
	chmod 755 $(DESTDIR)/$(datadir)/NodeManager/sliver-initscripts/
	mkdir -p $(DESTDIR)/$(datadir)/NodeManager/sliver-systemd
	rsync -av sliver-systemd/ $(DESTDIR)/$(datadir)/NodeManager/sliver-systemd/
	chmod 755 $(DESTDIR)/$(datadir)/NodeManager/sliver-systemd/

# this now is for the startup of nodemanager itself
ifneq "$(WITH_SYSTEMD)" ""
install-startup: install-systemd
endif
ifneq "$(WITH_INIT)" ""
install-startup: install-init
endif

install-init:
	mkdir -p $(DESTDIR)$(initdir)
	chmod 755 initscripts/*
	rsync -av initscripts/ $(DESTDIR)$(initdir)/

install-systemd:
	mkdir -p $(DESTDIR)/$(systemddir)
	rsync -av systemd/ $(DESTDIR)/$(systemddir)

#################### clean
clean:
	$(PYTHON) setup.py clean
	rm -f forward_api_calls *.pyc build

.PHONY: all install clean

################################################## devel-oriented
tags:
	git ls-files | xargs etags

.PHONY: tags

########## sync
# for use with the test framework; push local stuff on a test node
# howto use: go on testmaster in the build you want to use and just run
# $ exp
# cut'n paste the result in a terminal in your working dir, e.g. (although all are not required)
# $ export BUILD=2013.07.02--lxc18
# $ export PLCHOSTLXC=gotan.pl.sophia.inria.fr
# $ export GUESTNAME=2013.07.02--lxc18-1-vplc01
# $ export GUESTHOSTNAME=vplc01.pl.sophia.inria.fr
# $ export KVMHOST=kvm64-6.pl.sophia.inria.fr
# $ export NODE=vnode01.pl.sophia.inria.fr
# and then just run
# $ make sync

LOCAL_RSYNC_EXCLUDES	:= --exclude '*.pyc'
RSYNC_EXCLUDES		:= --exclude .git  --exclude .svn --exclude '*~' --exclude TAGS $(LOCAL_RSYNC_EXCLUDES)
RSYNC_COND_DRY_RUN	:= $(if $(findstring n,$(MAKEFLAGS)),--dry-run,)
RSYNC			:= rsync -e "ssh -i $(NODE).key.rsa" -a -v $(RSYNC_COND_DRY_RUN) $(RSYNC_EXCLUDES)

ifdef NODE
NODEURL:=root@$(NODE):/
endif

# this is for lxc only, we need to exclude the vs stuff that otherwise messes up everything on node
# WARNING: keep this in sync with setup.spec
LXC_EXCLUDES= --exclude sliver_vs.py --exclude coresched_vs.py --exclude drl.py

# run with make SYNC_RESTART=false if you want to skip restarting nm
SYNC_RESTART=true

sync:synclxc

synclxc: $(NODE).key.rsa
ifeq (,$(NODEURL))
	@echo "sync: You must define NODE on the command line"
	@echo "  e.g. make sync NODE=vnode01.inria.fr"
	@exit 1
else
	@echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
	@echo WARNING : this target might not be very reliable - use with care
	@echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
	+$(RSYNC) $(LXC_EXCLUDES) --delete-excluded ./ $(NODEURL)/usr/share/NodeManager/
#	+$(RSYNC) ./initscripts/ $(NODEURL)/etc/init.d/
	+$(RSYNC) ./systemd/ $(NODEURL)/usr/lib/systemd/system/
	-$(SYNC_RESTART) && { ssh -i $(NODE).key.rsa root@$(NODE) service nm restart ; } ||:
endif

# this is for vs only, we need to exclude the lxc stuff that otherwise messes up everything on node
# xxx keep this in sync with setup.spec
VS_EXCLUDES= --exclude sliver_libvirt.py --exclude sliver_lxc.py --exclude cgroups.py --exclude coresched_lxc.py --exclude privatebridge.py

syncvs: $(NODE).key.rsa
ifeq (,$(NODEURL))
	@echo "syncvs: You must define NODE on the command line"
	@echo "  e.g. make sync NODE=vnode01.inria.fr"
	@exit 1
else
	@echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
	@echo WARNING : this target might not be very reliable - use with care
	@echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
	+$(RSYNC) $(VS_EXCLUDES) --delete-excluded ./ $(NODEURL)/usr/share/NodeManager/
	+$(RSYNC) ./initscripts/ $(NODEURL)/etc/init.d/
#	+$(RSYNC) ./systemd/ $(NODEURL)/usr/lib/systemd/system/
	-$(SYNC_RESTART) && { ssh -i $(NODE).key.rsa root@$(NODE) service nm restart ; } ||:
endif


### fetching the key

TESTMASTER ?= testmaster.onelab.eu

ifdef BUILD
KEYURL:=root@$(TESTMASTER):$(BUILD)/keys/key_admin.rsa
endif

key: $(NODE).key.rsa

$(NODE).key.rsa:
ifeq (,$(KEYURL))
	@echo "sync: fetching $@ - You must define TESTMASTER, BUILD and NODE on the command line"
	@echo "  e.g. make sync TESTMASTER=testmaster.onelab.eu BUILD=2010.01.22--1l-f8-32 NODE=vnode01.inria.fr"
	@echo "  note that for now all test builds use the same key, so any BUILD would do"
	@exit 1
else
	@echo "FETCHING key"
	+scp $(KEYURL) $@
endif

########## exp. too
SLICE=inri_sl1

syncvinit:
	$(RSYNC) sliver-systemd/vinit.st* $(NODEURL)/vservers/$(SLICE)/usr/bin/
	$(RSYNC) sliver-systemd/vinit.service $(NODEURL)/vservers/$(SLICE)/usr/lib/systemd/system/
	echo "remember to run 'systemctl --system daemon-reload' within this slice"
