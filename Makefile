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

lib: forward_api_calls
	python setup-lib.py build

vs: 
	python setup-vs.py build

lxc: 
	python setup-lxc.py build

forward_api_calls: forward_api_calls.c
	$(CC) -Wall -Os -o $@ $?
	strip $@

install-lib:
	python setup-lib.py install \
		--install-purelib=$(DESTDIR)/$(datadir)/NodeManager \
		--install-platlib=$(DESTDIR)/$(datadir)/NodeManager \
		--install-scripts=$(DESTDIR)/$(bindir)
	install -m 444 README $(DESTDIR)/$(datadir)/NodeManager

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

install-scripts: 
	mkdir -p $(DESTDIR)/$(datadir)/NodeManager/sliver-initscripts
	rsync -av sliver-initscripts/ $(DESTDIR)/$(datadir)/sliver-initscripts/
	chmod 755 $(DESTDIR)/$(datadir)/sliver-initscripts/

	mkdir -p $(DESTDIR)/etc/init.d
	chmod 755 initscripts/*
	rsync -av initscripts/ $(DESTDIR)/etc/init.d/

	install -d -m 755 $(DESTDIR)/var/lib/nodemanager

	install -D -m 644 logrotate/nodemanager $(DESTDIR)/etc/logrotate.d/nodemanager
	install -D -m 755 sshsh $(DESTDIR)/bin/sshsh


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

sync: $(NODE).key.rsa
ifeq (,$(NODEURL))
	@echo "sync: You must define NODE on the command line"
	@echo "  e.g. make sync NODE=vnode01.inria.fr"
	@exit 1
else
	+$(RSYNC) --exclude sshsh ./ $(NODEURL)/usr/share/NodeManager/
	+$(RSYNC) ./sshsh $(NODEURL)/bin/
	+$(RSYNC) ./initscripts/nm $(NODEURL)/etc/init.d/nm
	ssh -i $(NODE).key.rsa root@$(NODE) service nm restart
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
