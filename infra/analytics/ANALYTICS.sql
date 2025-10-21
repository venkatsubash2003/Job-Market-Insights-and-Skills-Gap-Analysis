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

-- Salary distribution by skill (simple aggregates)
DROP MATERIALIZED VIEW IF EXISTS mv_salary_by_skill;
CREATE MATERIALIZED VIEW mv_salary_by_skill AS
SELECT
  s.skill_id,
  COALESCE(s.skill_norm, s.skill_raw) AS skill,
  AVG(c.min) AS avg_min,
  AVG(c.max) AS avg_max,
  COUNT(*)   AS n
FROM skills s
JOIN jobs_skills js ON js.skill_id = s.skill_id
JOIN compensation c ON c.job_id = js.job_id
WHERE c.min IS NOT NULL AND c.max IS NOT NULL
GROUP BY s.skill_id, COALESCE(s.skill_norm, s.skill_raw);

CREATE INDEX IF NOT EXISTS idx_mv_salary_by_skill_n
ON mv_salary_by_skill (n DESC);

-- Jobs by country
DROP MATERIALIZED VIEW IF EXISTS mv_jobs_by_country;
CREATE MATERIALIZED VIEW mv_jobs_by_country AS
SELECT
  COALESCE(country, 'Unknown') AS country,
  COUNT(*) AS jobs
FROM locations
GROUP BY COALESCE(country, 'Unknown');

CREATE INDEX IF NOT EXISTS idx_mv_jobs_by_country
ON mv_jobs_by_country (jobs DESC);


-- ========== STEP 5: TREND ANALYTICS ==========

-- A) Monthly skill counts (already created in Step 3, ensure present)
DROP MATERIALIZED VIEW IF EXISTS mv_monthly_skill_counts;
CREATE MATERIALIZED VIEW mv_monthly_skill_counts AS
WITH j_clean AS (
  SELECT job_id, DATE_TRUNC('month', post_date)::date AS month
  FROM jobs WHERE post_date IS NOT NULL
)
SELECT
  s.skill_id,
  COALESCE(s.skill_norm, s.skill_raw) AS skill,
  j_clean.month,
  COUNT(DISTINCT js.job_id) AS job_count
FROM skills s
JOIN jobs_skills js ON js.skill_id = s.skill_id
JOIN j_clean        ON j_clean.job_id = js.job_id
GROUP BY s.skill_id, COALESCE(s.skill_norm, s.skill_raw), j_clean.month;
CREATE INDEX IF NOT EXISTS idx_mv_monthly_skill_counts_skill_month
  ON mv_monthly_skill_counts (skill, month);

-- B) Monthly salary by skill (avg min/max per month)
DROP MATERIALIZED VIEW IF EXISTS mv_monthly_salary_by_skill;
CREATE MATERIALIZED VIEW mv_monthly_salary_by_skill AS
WITH base AS (
  SELECT
    DATE_TRUNC('month', j.post_date)::date AS month,
    COALESCE(s.skill_norm, s.skill_raw)    AS skill,
    c.min, c.max, c.currency, c.period
  FROM jobs j
  JOIN jobs_skills js ON js.job_id = j.job_id
  JOIN skills s       ON s.skill_id = js.skill_id
  JOIN compensation c ON c.job_id = j.job_id
  WHERE j.post_date IS NOT NULL
    AND c.min IS NOT NULL AND c.max IS NOT NULL
    -- Optional: filter to annual only for consistency
    AND (c.period IS NULL OR c.period = 'year')
)
SELECT
  month, skill,
  AVG(min) AS avg_min,
  AVG(max) AS avg_max,
  COUNT(*) AS n
FROM base
GROUP BY month, skill;
CREATE INDEX IF NOT EXISTS idx_mv_monthly_salary_by_skill
  ON mv_monthly_salary_by_skill (skill, month);

-- C) Monthly location demand (jobs by country)
DROP MATERIALIZED VIEW IF EXISTS mv_monthly_jobs_by_country;
CREATE MATERIALIZED VIEW mv_monthly_jobs_by_country AS
WITH base AS (
  SELECT
    DATE_TRUNC('month', j.post_date)::date AS month,
    COALESCE(l.country, 'Unknown') AS country,
    j.job_id
  FROM jobs j
  LEFT JOIN locations l ON l.job_id = j.job_id
  WHERE j.post_date IS NOT NULL
)
SELECT month, country, COUNT(DISTINCT job_id) AS job_count
FROM base
GROUP BY month, country;
CREATE INDEX IF NOT EXISTS idx_mv_monthly_jobs_by_country
  ON mv_monthly_jobs_by_country (country, month);

-- D) Rising/Falling skills (MoM growth)
DROP MATERIALIZED VIEW IF EXISTS mv_skill_mom_growth;
CREATE MATERIALIZED VIEW mv_skill_mom_growth AS
WITH m AS (
  SELECT skill, month, job_count
  FROM mv_monthly_skill_counts
),
w AS (
  SELECT
    skill, month, job_count,
    LAG(job_count) OVER (PARTITION BY skill ORDER BY month) AS prev_job_count
  FROM m
)
SELECT
  skill, month, job_count, prev_job_count,
  CASE
    WHEN prev_job_count IS NULL OR prev_job_count = 0 THEN NULL
    ELSE ROUND(100.0 * (job_count - prev_job_count) / prev_job_count, 2)
  END AS mom_growth_pct
FROM w;
CREATE INDEX IF NOT EXISTS idx_mv_skill_mom_growth
  ON mv_skill_mom_growth (month DESC, mom_growth_pct DESC, skill);

-- Helpful indexes for interactive filters
CREATE INDEX IF NOT EXISTS idx_jobs_post_date ON jobs (post_date);
CREATE INDEX IF NOT EXISTS idx_locations_country ON locations (country);
CREATE INDEX IF NOT EXISTS idx_jobs_skills_skill_job ON jobs_skills (skill_id, job_id);

-- Ensure trend MVs are indexed for (skill, month) & (country, month)
CREATE INDEX IF NOT EXISTS idx_mv_msc_skill_month ON mv_monthly_skill_counts (skill, month);
CREATE INDEX IF NOT EXISTS idx_mv_msal_skill_month ON mv_monthly_salary_by_skill (skill, month);
CREATE INDEX IF NOT EXISTS idx_mv_mcountry_country_month ON mv_monthly_jobs_by_country (country, month);
