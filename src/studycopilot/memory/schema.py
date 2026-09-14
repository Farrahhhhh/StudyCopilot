"""Version 1: portable IDs, explicit ownership and local full-text indexing."""

SCHEMA_V1 = """
CREATE TABLE projects (
 id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, description TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE sources (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 source_type TEXT NOT NULL DEFAULT 'book', title TEXT NOT NULL,
 author TEXT, edition TEXT, file_name TEXT, external_identifier TEXT,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, last_opened_at TEXT,
 UNIQUE(project_id, title)
);
CREATE TABLE topics (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 source_id TEXT REFERENCES sources(id), name TEXT NOT NULL,
 parent_topic_id TEXT REFERENCES topics(id), created_at TEXT NOT NULL
);
CREATE TABLE study_sessions (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 source_id TEXT REFERENCES sources(id), topic_id TEXT REFERENCES topics(id),
 started_at TEXT NOT NULL, ended_at TEXT
);
CREATE TABLE concepts (
 id TEXT PRIMARY KEY, canonical_name TEXT NOT NULL UNIQUE, english_name TEXT,
 chinese_name TEXT, description TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE concept_aliases (
 id TEXT PRIMARY KEY, concept_id TEXT NOT NULL REFERENCES concepts(id),
 alias TEXT NOT NULL, language TEXT, UNIQUE(concept_id, alias)
);
CREATE INDEX aliases_lookup ON concept_aliases(alias);
CREATE TABLE concept_links (
 id TEXT PRIMARY KEY, source_concept_id TEXT NOT NULL REFERENCES concepts(id),
 target_concept_id TEXT NOT NULL REFERENCES concepts(id),
 relation_type TEXT NOT NULL CHECK(relation_type IN
 ('related_to','prerequisite_of','used_in','same_as','derived_from','contrasts_with')),
 confidence REAL NOT NULL DEFAULT 1 CHECK(confidence BETWEEN 0 AND 1),
 created_at TEXT NOT NULL, UNIQUE(source_concept_id,target_concept_id,relation_type),
 CHECK(source_concept_id != target_concept_id)
);
CREATE TABLE source_concepts (
 id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources(id),
 concept_id TEXT NOT NULL REFERENCES concepts(id), importance REAL NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL, UNIQUE(source_id,concept_id)
);
CREATE TABLE memories (
 id TEXT PRIMARY KEY, scope TEXT NOT NULL CHECK(scope IN ('project','global','user')),
 project_id TEXT REFERENCES projects(id), source_id TEXT REFERENCES sources(id),
 concept_id TEXT REFERENCES concepts(id), memory_type TEXT NOT NULL DEFAULT 'note',
 content TEXT NOT NULL CHECK(length(trim(content)) > 0), search_text TEXT NOT NULL,
 importance REAL NOT NULL DEFAULT 1 CHECK(importance BETWEEN 0 AND 5),
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 CHECK((scope='project' AND project_id IS NOT NULL) OR
       (scope IN ('global','user') AND project_id IS NULL AND source_id IS NULL))
);
CREATE INDEX memory_scope ON memories(scope,project_id);
CREATE VIRTUAL TABLE memories_fts USING fts5(search_text, content='memories', content_rowid='rowid');
CREATE TRIGGER memories_ai AFTER INSERT ON memories BEGIN
 INSERT INTO memories_fts(rowid,search_text) VALUES(new.rowid,new.search_text);
END;
CREATE TRIGGER memories_ad AFTER DELETE ON memories BEGIN
 INSERT INTO memories_fts(memories_fts,rowid,search_text) VALUES('delete',old.rowid,old.search_text);
END;
CREATE TRIGGER memories_au AFTER UPDATE ON memories BEGIN
 INSERT INTO memories_fts(memories_fts,rowid,search_text) VALUES('delete',old.rowid,old.search_text);
 INSERT INTO memories_fts(rowid,search_text) VALUES(new.rowid,new.search_text);
END;
CREATE TABLE questions (
 id TEXT PRIMARY KEY, project_id TEXT REFERENCES projects(id), source_id TEXT REFERENCES sources(id),
 topic_id TEXT REFERENCES topics(id), session_id TEXT REFERENCES study_sessions(id),
 question TEXT NOT NULL, context_text TEXT, answer_summary TEXT, created_at TEXT NOT NULL
);
CREATE TABLE translation_history (
 id TEXT PRIMARY KEY, project_id TEXT REFERENCES projects(id), source_id TEXT REFERENCES sources(id),
 topic_id TEXT REFERENCES topics(id), session_id TEXT REFERENCES study_sessions(id),
 source_text TEXT NOT NULL, translated_text TEXT, terms_json TEXT NOT NULL DEFAULT '[]',
 source_app TEXT, created_at TEXT NOT NULL
);
CREATE TABLE user_preferences (
 id TEXT PRIMARY KEY, key TEXT NOT NULL UNIQUE, value TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE project_preferences (
 project_id TEXT NOT NULL REFERENCES projects(id), key TEXT NOT NULL, value TEXT NOT NULL,
 PRIMARY KEY(project_id,key)
);
"""
