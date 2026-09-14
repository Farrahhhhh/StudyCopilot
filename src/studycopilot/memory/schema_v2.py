SCHEMA_V2 = """
CREATE TABLE screenshots (
 id TEXT PRIMARY KEY,
 project_id TEXT REFERENCES projects(id),
 source_id TEXT REFERENCES sources(id),
 topic_id TEXT REFERENCES topics(id),
 session_id TEXT REFERENCES study_sessions(id),
 file_path TEXT NOT NULL UNIQUE,
 capture_type TEXT NOT NULL DEFAULT 'region',
 task_type TEXT NOT NULL CHECK(task_type IN ('translate','explain')),
 width INTEGER NOT NULL CHECK(width > 0),
 height INTEGER NOT NULL CHECK(height > 0),
 screen_region TEXT NOT NULL,
 is_persistent INTEGER NOT NULL DEFAULT 0 CHECK(is_persistent IN (0,1)),
 created_at TEXT NOT NULL
);
CREATE INDEX screenshots_session ON screenshots(session_id, created_at);
CREATE TABLE memory_screenshots (
 memory_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
 screenshot_id TEXT NOT NULL REFERENCES screenshots(id),
 PRIMARY KEY(memory_id,screenshot_id)
);
CREATE TABLE recent_context (
 id TEXT PRIMARY KEY,
 project_id TEXT REFERENCES projects(id),
 source_id TEXT REFERENCES sources(id),
 session_id TEXT REFERENCES study_sessions(id),
 screenshot_id TEXT REFERENCES screenshots(id) ON DELETE SET NULL,
 task_type TEXT NOT NULL CHECK(task_type IN ('translate','explain')),
 selected_text TEXT NOT NULL DEFAULT '',
 question TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL
);
CREATE INDEX recent_context_session ON recent_context(session_id, created_at);
"""
