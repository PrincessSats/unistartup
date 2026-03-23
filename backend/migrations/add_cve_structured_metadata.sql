-- Add structured CVE metadata columns to kb_entries
-- Extracted from NVD API: CWE types, CVSS scores, attack vectors, affected products

ALTER TABLE kb_entries ADD COLUMN IF NOT EXISTS cwe_ids TEXT[] DEFAULT '{}';
ALTER TABLE kb_entries ADD COLUMN IF NOT EXISTS cvss_base_score REAL;
ALTER TABLE kb_entries ADD COLUMN IF NOT EXISTS cvss_vector TEXT;
ALTER TABLE kb_entries ADD COLUMN IF NOT EXISTS attack_vector TEXT;
ALTER TABLE kb_entries ADD COLUMN IF NOT EXISTS attack_complexity TEXT;
ALTER TABLE kb_entries ADD COLUMN IF NOT EXISTS affected_products TEXT[] DEFAULT '{}';
ALTER TABLE kb_entries ADD COLUMN IF NOT EXISTS cve_metadata JSONB;

-- GIN index for array overlap queries (cwe_ids && ARRAY['CWE-79', ...])
CREATE INDEX IF NOT EXISTS idx_kb_entries_cwe_ids_gin ON kb_entries USING gin(cwe_ids);

-- B-tree index for CVSS score range queries
CREATE INDEX IF NOT EXISTS idx_kb_entries_cvss_score ON kb_entries(cvss_base_score)
    WHERE cvss_base_score IS NOT NULL;

-- B-tree index for attack_vector filtering
CREATE INDEX IF NOT EXISTS idx_kb_entries_attack_vector ON kb_entries(attack_vector)
    WHERE attack_vector IS NOT NULL;
