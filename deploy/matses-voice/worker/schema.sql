CREATE TABLE IF NOT EXISTS feedback (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  client_id TEXT NOT NULL UNIQUE,
  job_id TEXT NOT NULL,
  model TEXT NOT NULL,
  language TEXT NOT NULL DEFAULT 'mcf_Latn',
  transcript TEXT NOT NULL,
  word_index INTEGER NOT NULL,
  word_count INTEGER NOT NULL DEFAULT 1,
  original TEXT NOT NULL,
  correction TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_feedback_job ON feedback(job_id);
CREATE INDEX IF NOT EXISTS idx_feedback_original ON feedback(original);

CREATE TABLE IF NOT EXISTS rate_log (
  ip TEXT NOT NULL,
  kind TEXT NOT NULL,
  ts INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rate_log_lookup ON rate_log(kind, ts);
