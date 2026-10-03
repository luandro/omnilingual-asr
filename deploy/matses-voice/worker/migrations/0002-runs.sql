CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id TEXT NOT NULL UNIQUE,
  profile TEXT NOT NULL DEFAULT 'mcf',
  model TEXT NOT NULL,
  language TEXT NOT NULL DEFAULT 'mcf_Latn',
  audio_key TEXT NOT NULL,
  transcript TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_runs_profile ON runs(profile, created_at);
