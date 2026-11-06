import json
import sqlite3
import time
from contextlib import contextmanager

SCHEMA = '''
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS documents (
 id TEXT PRIMARY KEY, filename TEXT NOT NULL, extension TEXT NOT NULL,
 sha256 TEXT NOT NULL, size INTEGER NOT NULL, status TEXT NOT NULL,
 progress INTEGER DEFAULT 0, unit_count INTEGER DEFAULT 0,
 result TEXT, errors TEXT DEFAULT '[]', failure TEXT,
 created REAL NOT NULL, updated REAL NOT NULL, elapsed REAL,
 version INTEGER DEFAULT 1, attempts INTEGER DEFAULT 0,
 lease_owner TEXT, lease_until REAL
);
CREATE INDEX IF NOT EXISTS documents_hash ON documents(sha256);
CREATE INDEX IF NOT EXISTS documents_queue ON documents(status,created);
CREATE TABLE IF NOT EXISTS units (
 document_id TEXT NOT NULL REFERENCES documents(id), ordinal INTEGER NOT NULL,
 source TEXT NOT NULL, text TEXT NOT NULL, method TEXT NOT NULL, confidence REAL,
 vector TEXT, PRIMARY KEY(document_id,ordinal)
);
CREATE TABLE IF NOT EXISTS history (
 id INTEGER PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id),
 time REAL NOT NULL, event TEXT NOT NULL, detail TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS history_document ON history(document_id);
CREATE VIRTUAL TABLE IF NOT EXISTS unit_search USING fts5(document_id UNINDEXED, text);
'''

class Database:
    def __init__(self, path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as con:
            con.executescript(SCHEMA)
    @contextmanager
    def connect(self):
        con = sqlite3.connect(self.path, timeout=30)
        con.row_factory = sqlite3.Row
        con.execute('PRAGMA foreign_keys=ON')
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()
    def history(self, con, id, event, detail):
        con.execute('INSERT INTO history(document_id,time,event,detail) VALUES(?,?,?,?)',
                    (id,time.time(),event,json.dumps(detail,default=str)))
    def get(self, id):
        with self.connect() as con:
            row = con.execute('SELECT * FROM documents WHERE id=?',(id,)).fetchone()
            if not row:
                return None
            doc = dict(row)
            for key in ('result','errors'):
                doc[key] = json.loads(doc[key]) if doc[key] else None
            doc['history'] = [dict(r) for r in con.execute('SELECT time,event,detail FROM history WHERE document_id=? ORDER BY id',(id,))]
            for h in doc['history']:
                h['detail'] = json.loads(h['detail'])
            return doc
