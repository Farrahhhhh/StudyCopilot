SCHEMA_V3 = """
CREATE TABLE reading_results (
 id TEXT PRIMARY KEY,
 screenshot_id TEXT REFERENCES screenshots(id) ON DELETE CASCADE,
 project_id TEXT REFERENCES projects(id),
 source_id TEXT REFERENCES sources(id),
 session_id TEXT REFERENCES study_sessions(id),
 task_type TEXT NOT NULL CHECK(task_type IN ('translate','explain')),
 question TEXT NOT NULL DEFAULT '',
 answer TEXT NOT NULL,
 model TEXT NOT NULL,
 created_at TEXT NOT NULL
);
CREATE INDEX reading_results_scope ON reading_results(project_id,source_id,session_id,created_at);
"""
