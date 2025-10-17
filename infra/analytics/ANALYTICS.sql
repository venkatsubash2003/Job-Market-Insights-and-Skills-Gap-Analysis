-- 1) Overall counts per skill
DROP MATERIALIZED VIEW IF EXISTS mv_skill_counts;
CREATE MATERIALIZED VIEW mv_skill_counts AS
SELECT
  s.skill_id,
  COALESCE(s.skill_norm, s.skill_raw) AS skill,
  COUNT(DISTINCT js.job_id)           AS job_count,
  MAX(j.post_date)                    AS last_seen
FROM skills s
JOIN jobs_skills js ON js.skill_id = s.skill_id
JOIN jobs j         ON j.job_id = js.job_id
GROUP BY s.skill_id, COALESCE(s.skill_norm, s.skill_raw);

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_skill_counts_skill_id
  ON mv_skill_counts (skill_id);

-- 2) Monthly counts per skill (trendlines)
DROP MATERIALIZED VIEW IF EXISTS mv_monthly_skill_counts;
CREATE MATERIALIZED VIEW mv_monthly_skill_counts AS
WITH j_clean AS (
  SELECT job_id, DATE_TRUNC('month', post_date)::date AS month
  FROM jobs
  WHERE post_date IS NOT NULL
)
SELECT
  s.skill_id,
  COALESCE(s.skill_norm, s.skill_raw) AS skill,
  j_clean.month,
  COUNT(DISTINCT js.job_id)           AS job_count
FROM skills s
JOIN jobs_skills js ON js.skill_id = s.skill_id
JOIN j_clean        ON j_clean.job_id = js.job_id
GROUP BY s.skill_id, COALESCE(s.skill_norm, s.skill_raw), j_clean.month;

CREATE INDEX IF NOT EXISTS idx_mv_monthly_skill_counts_skill_month
  ON mv_monthly_skill_counts (skill_id, month);

-- 3) Skill co-occurrence (unordered pairs in the same job)
DROP MATERIALIZED VIEW IF EXISTS mv_skill_cooccurrence;
CREATE MATERIALIZED VIEW mv_skill_cooccurrence AS
WITH pairs AS (
  SELECT
    LEAST(js1.skill_id, js2.skill_id)   AS skill_id_a,
    GREATEST(js1.skill_id, js2.skill_id) AS skill_id_b,
    js1.job_id
  FROM jobs_skills js1
  JOIN jobs_skills js2
    ON js1.job_id = js2.job_id
   AND js1.skill_id < js2.skill_id
)
SELECT
  a.skill_id AS skill_id_a,
  COALESCE(a.skill_norm, a.skill_raw) AS skill_a,
  b.skill_id AS skill_id_b,
  COALESCE(b.skill_norm, b.skill_raw) AS skill_b,
  COUNT(DISTINCT job_id) AS pair_count
FROM pairs
JOIN skills a ON a.skill_id = pairs.skill_id_a
JOIN skills b ON b.skill_id = pairs.skill_id_b
GROUP BY a.skill_id, COALESCE(a.skill_norm, a.skill_raw),
         b.skill_id, COALESCE(b.skill_norm, b.skill_raw)
HAVING COUNT(DISTINCT job_id) >= 1;

CREATE INDEX IF NOT EXISTS idx_mv_skill_cooccurrence_counts
  ON mv_skill_cooccurrence (pair_count DESC, skill_id_a, skill_id_b);
