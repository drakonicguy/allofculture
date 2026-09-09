-- allofculture: an explorable relational database of culture.
-- Nodes = cultural artifacts/actors; Edges = ATTRIBUTED claims about relations.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS nodes (
  id          INTEGER PRIMARY KEY,
  type        TEXT NOT NULL,          -- work | person | band | movement | genre | place | concept | medium
  name        TEXT NOT NULL,
  year        INTEGER,
  description TEXT,
  meta        TEXT,                    -- JSON blob for extra fields
  qid         TEXT                     -- Wikidata QID (for dedup)
);

-- Every edge is a CLAIM. It must be attributable:
--   source       -> URL or citation backing the claim
--   source_type  -> wikidata | musicbrainz | whosampled | wikipedia | manual | ...
--   confidence   -> 0..1 (how sure we are)
--   verified     -> 1 if a human confirmed it, else 0
CREATE TABLE IF NOT EXISTS edges (
  id          INTEGER PRIMARY KEY,
  source_id   INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
  target_id   INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
  relation    TEXT NOT NULL,           -- references | samples | collages | covers | remixes | quotes | parodies | inspired_by | member_of | located_in | performed | founded | uses | exemplifies | ...
  weight      REAL DEFAULT 1.0,
  note        TEXT,
  source      TEXT,                    -- citation / URL
  source_type TEXT,
  confidence  REAL DEFAULT 0.5,
  verified    INTEGER DEFAULT 0,
  UNIQUE(source_id, target_id, relation, source)
);

CREATE INDEX IF NOT EXISTS idx_edge_source ON edges(source_id);
CREATE INDEX IF NOT EXISTS idx_edge_target ON edges(target_id);
CREATE INDEX IF NOT EXISTS idx_edge_rel    ON edges(relation);
CREATE INDEX IF NOT EXISTS idx_node_type   ON nodes(type);
CREATE INDEX IF NOT EXISTS idx_node_name   ON nodes(name);
CREATE UNIQUE INDEX IF NOT EXISTS idx_node_qid ON nodes(qid);  -- one Wikidata item = one node
