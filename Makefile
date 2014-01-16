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
initdir=/etc/init.d
systemddir := /usr/lib/systemd/system

####################
# call with either WITH_SYSTEMD=true or WITH_INIT=true
ifneq "$(WITH_SYSTEMD)" ""
use_sytemd=true
else
ifneq "$(WITH_INIT)" ""
use_systemd=""
else # if not set then try to guess
use_systemd=$(bash -c 'type -p systemctl')
endif
endif

####################
lib: forward_api_calls
	python setup-lib.py build

vs: 
	python setup-vs.py build

lxc: 
	python setup-lxc.py build

forward_api_calls: forward_api_calls.c
	$(CC) -Wall -Os -o $@ $?
	strip $@

#################### install
install-lib: install-miscell install-startup
	python setup-lib.py install \
		--install-purelib=$(DESTDIR)/$(datadir)/NodeManager \
		--install-platlib=$(DESTDIR)/$(datadir)/NodeManager \
		--install-scripts=$(DESTDIR)/$(bindir)

# might be better in setup.py ?
install-miscell:
	install -d -m 755 $(DESTDIR)/var/lib/nodemanager
	install -D -m 444 README $(DESTDIR)/$(datadir)/NodeManager/README
	install -D -m 644 logrotate/nodemanager $(DESTDIR)/etc/logrotate.d/nodemanager
	install -D -m 755 sshsh $(DESTDIR)/bin/sshsh
	mkdir -p $(DESTDIR)/$(datadir)/NodeManager/sliver-initscripts
	rsync -av sliver-initscripts/ $(DESTDIR)/$(datadir)/sliver-initscripts/
	chmod 755 $(DESTDIR)/$(datadir)/sliver-initscripts/

ifneq "$use_systemd" ""
install-startup: install-systemd
else
install-startup: install-init
endif

install-init:
	mkdir -p $(DESTDIR)$(initdir)
	chmod 755 initscripts/*
	rsync -av initscripts/ $(DESTDIR)$(initdir)/

install-systemd:
	mkdir -p $(DESTDIR)/$(systemddir)
	rsync -av systemd/ $(DESTDIR)/$(systemddir)

install-vs:
	python setup-vs.py install \
		--install-purelib=$(DESTDIR)/$(datadir)/NodeManager \
		--install-platlib=$(DESTDIR)/$(datadir)/NodeManager \
		--install-scripts=$(DESTDIR)/$(bindir)
	install -m 444 README $(DESTDIR)/$(datadir)/NodeManager

install-lxc:
	python setup-lxc.py install \
		--install-purelib=$(DESTDIR)/$(datadir)/NodeManager \
		--install-platlib=$(DESTDIR)/$(datadir)/NodeManager \
		--install-scripts=$(DESTDIR)/$(bindir)
	install -m 444 README $(DESTDIR)/$(datadir)/NodeManager

#################### clean
clean:
	python setup-lib.py clean
	python setup-vs.py clean
	python setup-lxc.py clean
	rm -f forward_api_calls *.pyc build

.PHONY: all install clean

##########
tags:
	(find . '(' -name '*.py' -o -name '*.c' -o -name '*.spec' ')' ; ls initscripts/*) | xargs etags 

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
# keep this in sync with setup-vs.spec
LXC_EXCLUDES= --exclude sliver_vs.py --exclude coresched_vs.py

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
	+$(RSYNC) --exclude sshsh $(LXC_EXCLUDES) --delete-excluded ./ $(NODEURL)/usr/share/NodeManager/
	+$(RSYNC) ./sshsh $(NODEURL)/bin/
#	+$(RSYNC) ./initscripts/ $(NODEURL)/etc/init.d/
	+$(RSYNC) ./systemd/ $(NODEURL)/usr/lib/systemd/system/
#	ssh -i $(NODE).key.rsa root@$(NODE) service nm restart
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
