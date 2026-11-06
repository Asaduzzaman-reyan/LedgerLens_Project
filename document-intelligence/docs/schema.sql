
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
