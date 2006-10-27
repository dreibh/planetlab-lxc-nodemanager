import cPickle
import threading
import time

try: from bwlimit import bwmin, bwmax
except ImportError: bwmin, bwmax = 8, 1000000000
import accounts
import logger
import tools


DB_FILE = '/root/node_mgr_db.pickle'

LOANABLE_RESOURCES = ['cpu_min', 'cpu_share', 'net_min', 'net_max', 'net2_min', 'net2_max', 'net_share', 'disk_max']

DEFAULT_ALLOCATIONS = {'enabled': 1, 'cpu_min': 0, 'cpu_share': 32, 'net_min': bwmin, 'net_max': bwmax, 'net2_min': bwmin, 'net2_max': bwmax, 'net_share': 1, 'disk_max': 5000000}


# database object and associated lock
db_lock = threading.RLock()
db = None

# these are used in tandem to request a database dump from the dumper daemon
db_cond = threading.Condition(db_lock)
dump_requested = False

# decorator that acquires and releases the database lock before and after the decorated operation
def synchronized(fn):
    def sync_fn(*args, **kw_args):
        db_lock.acquire()
        try: return fn(*args, **kw_args)
        finally: db_lock.release()
    sync_fn.__doc__ = fn.__doc__
    sync_fn.__name__ = fn.__name__
    return sync_fn


class Database(dict):
    def __init__(self):
        self._min_timestamp = 0

    def _compute_effective_rspecs(self):
        """Calculate the effects of loans and store the result in field _rspec.  At the moment, we allow slivers to loan only those resources that they have received directly from PLC.  In order to do the accounting, we store three different rspecs: field 'rspec', which is the resources given by PLC; field '_rspec', which is the actual amount of resources the sliver has after all loans; and variable resid_rspec, which is the amount of resources the sliver has after giving out loans but not receiving any."""
        slivers = {}
        for name, rec in self.iteritems():
            if 'rspec' in rec:
                rec['_rspec'] = rec['rspec'].copy()
                slivers[name] = rec
        for rec in slivers.itervalues():
            eff_rspec = rec['_rspec']
            resid_rspec = rec['rspec'].copy()
            for target, resname, amt in rec.get('_loans', []):
                if target in slivers and amt < resid_rspec[resname]:
                    eff_rspec[resname] -= amt
                    resid_rspec[resname] -= amt
                    slivers[target]['_rspec'][resname] += amt

    def deliver_record(self, rec):
        """A record is simply a dictionary with 'name' and 'timestamp' keys.  We keep some persistent private data in the records under keys that start with '_'; thus record updates should not displace such keys."""
        name = rec['name']
        old_rec = self.get(name)
        if old_rec != None and rec['timestamp'] > old_rec['timestamp']:
            for key in old_rec.keys():
                if not key.startswith('_'): del old_rec[key]
            old_rec.update(rec)
        elif rec['timestamp'] >= self._min_timestamp: self[name] = rec

    def set_min_timestamp(self, ts):
        self._min_timestamp = ts
        for name, rec in self.items():
            if rec['timestamp'] < ts: del self[name]

    def sync(self):
        # delete expired records
        now = time.time()
        for name, rec in self.items():
            if rec.get('expires', now) < now: del self[name]

        self._compute_effective_rspecs()

        # create and destroy accounts as needed
        existing_acct_names = accounts.all()
        for name in existing_acct_names:
            if name not in self: accounts.get(name).ensure_destroyed()
        for name, rec in self.iteritems():
            if rec['instantiation'] == 'plc-instantiated': accounts.get(name).ensure_created(rec)

        # request a database dump
        global dump_requested
        dump_requested = True
        db_cond.notify()


@synchronized
def GetSlivers_callback(data):
    for d in data:
        for sliver in d['slivers']:
            rec = sliver.copy()
            attr_dict = {}
            for attr in rec.pop('attributes'): attr_dict[attr['name']] = attr_dict[attr['value']]
            keys = rec.pop('keys')
            rec['keys'] = '\n'.join([key_struct['key'] for key_struct in keys])
            rspec = {}
            rec['rspec'] = rspec
            for resname, default_amt in DEFAULT_ALLOCATIONS.iteritems():
                try: amt = int(attr_dict[resname])
                except (KeyError, ValueError): amt = default_amt
                rspec[resname] = amt
        db.set_min_timestamp(d['timestamp'])
    db.sync()


def start():
    """The database dumper daemon.  When it starts up, it populates the database with the last dumped database.  It proceeds to handle dump requests forever."""
    def run():
        global dump_requested
        while True:
            db_lock.acquire()
            while not dump_requested: db_cond.wait()
            db_copy = tools.deepcopy(db)
            dump_requested = False
            db_lock.release()
            try: tools.write_file(DB_FILE, lambda f: cPickle.dump(db_copy, f, -1))
            except: logger.log_exc()
    global db
    try:
        f = open(DB_FILE)
        try: db = cPickle.load(f)
        finally: f.close()
    except:
        logger.log_exc()
        db = Database()
    tools.as_daemon_thread(run)
