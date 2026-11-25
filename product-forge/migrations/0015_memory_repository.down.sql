-- EDP-21 down: additive columns (content/source/owner/embedding) are DATA and are intentionally kept.
-- Only derived/index objects are removed.
DROP INDEX IF EXISTS idx_memory_embedding;
DROP INDEX IF EXISTS idx_memory_owner;
DROP INDEX IF EXISTS idx_memory_source;
DROP INDEX IF EXISTS idx_memory_acl;
DROP INDEX IF EXISTS idx_memory_tsv;
ALTER TABLE memory DROP COLUMN IF EXISTS tsv;
