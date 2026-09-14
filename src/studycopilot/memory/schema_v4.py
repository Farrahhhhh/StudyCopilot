"""Explicit questions and immutable sent context on bounded reading history."""
SCHEMA_V4 = """
ALTER TABLE memories ADD COLUMN status TEXT NOT NULL DEFAULT 'pending'
 CHECK(status IN ('pending','resolved'));
ALTER TABLE memories ADD COLUMN reading_result_id TEXT REFERENCES reading_results(id) ON DELETE SET NULL;
ALTER TABLE memories ADD COLUMN source_snapshot TEXT NOT NULL DEFAULT '{}';
ALTER TABLE reading_results ADD COLUMN context_snapshot TEXT NOT NULL DEFAULT '';
"""
