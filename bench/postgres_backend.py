import os, os.path
from time import sleep
#import subprocess  # Needs Python 2.4
import popen2
from indexed_search import DB
import psycopg2 as db2

CLUSTER_NAME = "bench"
DATA_DIR = "/scratch/faltet/postgres/%s" % CLUSTER_NAME
DSN = "dbname=%s port=%s"
CREATE_DB = "createdb %s"
DROP_DB = "dropdb %s"
TABLE_NAME = "intsfloats"
PORT = 5434

class StreamChar(object):
    "Object simulating a file for reading"

    def __init__(self, db):
        self.db = db
        self.nrows = db.nrows
        self.step = db.step
        self.read_it = self.read_iter()

    def values_generator(self):
        j = 0
        for i in xrange(self.nrows):
            if i >= j*self.step:
                stop = (j+1)*self.step
                if stop > self.nrows:
                    stop = self.nrows
                arr_i4, arr_f8 = self.db.fill_arrays(i, stop)
                j += 1
                k = 0
            yield (arr_i4[k], arr_i4[k], arr_f8[k], arr_f8[k])
            k += 1

    def read_iter(self):
        sout = ""
        n = self.nbytes
        for tup in self.values_generator():
            sout += "%s\t%s\t%s\t%s\n" % tup
            if n is not None and len(sout) > n:
                for i in xrange(n, len(sout), n):
                    rout = sout[:n]
                    sout = sout[n:]
                    yield rout
        yield sout

    def read(self, n=None):
        self.nbytes = n
        try:
            str = self.read_it.next()
        except StopIteration:
            str = ""
        return str

    # required by postgres2 driver, but not used
    def readline(self):
        pass


class Postgres_DB(DB):

    def __init__(self, nrows, rng, userandom):
        DB.__init__(self, nrows, rng, userandom)
        self.port = PORT

    def flatten(self, l):
        """Flattens list of tuples l."""
        return map(lambda x: x[0], l)
        #return map(lambda x: x[col], l)

    # Overloads the method in DB class
    def get_db_size(self):
#         sout = subprocess.Popen("du -s %s" % DATA_DIR, shell=True,
#                                 stdout=subprocess.PIPE).stdout
        (sout, sin) = popen2.popen2("sync;du -s %s" % DATA_DIR)
        line = [l for l in sout][0]
        return int(line.split()[0])

    def open_db(self, remove=0):
        if remove:
#             sout = subprocess.Popen(DROP_DB % self.filename, shell=True,
#                                     stdout=subprocess.PIPE).stdout
            (sout, sin) = popen2.popen2(DROP_DB % self.filename)
            for line in sout: print line
#             sout = subprocess.Popen(CREATE_DB % self.filename, shell=True,
#                                     stdout=subprocess.PIPE).stdout
            (sout, sin) = popen2.popen2(CREATE_DB % self.filename)
            for line in sout: print line

        print "Processing database:", self.filename
        con = db2.connect(DSN % (self.filename, self.port))
        self.cur = con.cursor()
        return con

    def create_table(self, con):
        self.cur.execute("""create table %s(
                          col1 integer,
                          col2 integer,
                          col3 double precision,
                          col4 double precision)""" % TABLE_NAME)
        con.commit()

    def fill_table(self, con):
        st = StreamChar(self)
        self.cur.copy_from(st, TABLE_NAME)
        con.commit()

    def index_col(self, con, colname):
        self.cur.execute("create index %s on %s(%s)" % \
                         (colname+'_idx', TABLE_NAME, colname))
        con.commit()

    def do_query(self, con, column, base):
        self.cur.execute(
#             "select %s from %s where %s >= %s and %s <= %s" % \
#             (column, TABLE_NAME,
#              column, base+self.rng[0],
#              column, base+self.rng[1]))
            "select * from %s where %s >= %s and %s <= %s" % \
            (TABLE_NAME,
             column, base+self.rng[0],
             column, base+self.rng[1]))
        #results = self.flatten(self.cur.fetchall())
        results = self.cur.fetchall()
        return results

    def close_db(self, con):
        self.cur.close()
        con.close()