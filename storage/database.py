import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

class Database:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.conn.execute('PRAGMA journal_mode=WAL')
        self.conn.execute('PRAGMA synchronous=FULL')
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS wallet(id INTEGER PRIMARY KEY CHECK(id=1), ms INTEGER NOT NULL CHECK(ms>=0));
        INSERT OR IGNORE INTO wallet VALUES(1,0);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS games(path TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS solved(round INTEGER, task TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(round,task));
        CREATE TABLE IF NOT EXISTS ledger(id INTEGER PRIMARY KEY, delta_ms INTEGER NOT NULL, reason TEXT NOT NULL, created TEXT DEFAULT CURRENT_TIMESTAMP);
        """)
    @contextmanager
    def transaction(self):
        with self.lock:
            self.conn.execute('BEGIN IMMEDIATE')
            try:
                yield self.conn
                self.conn.execute('COMMIT')
            except BaseException:
                self.conn.execute('ROLLBACK')
                raise
    def setting(self, key, default=None):
        with self.lock:
            row=self.conn.execute('SELECT value FROM settings WHERE key=?',(key,)).fetchone()
            return json.loads(row[0]) if row else default
    def set_setting(self,key,value):
        with self.transaction() as c:
            c.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',(key,json.dumps(value)))
    def games(self):
        with self.lock:
            return [r[0] for r in self.conn.execute('SELECT path FROM games ORDER BY path')]
    def add_game(self,path):
        with self.transaction() as c: c.execute('INSERT OR IGNORE INTO games VALUES(?)',(path,))
    def remove_game(self,path):
        with self.transaction() as c: c.execute('DELETE FROM games WHERE path=?',(path,))
    def solved(self,round_id):
        with self.lock:
            return {r[0] for r in self.conn.execute('SELECT task FROM solved WHERE round=?',(round_id,))}
    def count(self):
        with self.lock: return self.conn.execute('SELECT count(*) FROM solved').fetchone()[0]
    def close(self):
        with self.lock: self.conn.close()
